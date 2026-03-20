from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_ROLE = "executor"
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_TARGET_PROMPT_TOKENS = 12000
DEFAULT_MAX_OUTPUT_TOKENS = 16
DEFAULT_MAX_ROUNDS = 12
DEFAULT_SLEEP_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 180


@dataclass
class ProbeEvent:
    round_index: int
    timestamp_utc: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    rolling_prompt_tokens: int
    rolling_completion_tokens: int
    rolling_total_tokens: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone TPM probe for a Qwen3-compatible OpenAI endpoint."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional JSON config file with a role block such as configs/system.train20_router_gpt54_executor_qwen.local.json.",
    )
    parser.add_argument(
        "--role",
        default=DEFAULT_ROLE,
        help="Role name to read from --config. Default: executor.",
    )
    parser.add_argument("--base-url", help="OpenAI-compatible base URL, for example http://host:port/v1.")
    parser.add_argument("--api-key", help="API key for the target endpoint.")
    parser.add_argument("--model", default=None, help=f"Model name. Default: {DEFAULT_MODEL}.")
    parser.add_argument(
        "--target-prompt-tokens",
        type=int,
        default=DEFAULT_TARGET_PROMPT_TOKENS,
        help="Approximate prompt token target per request before calibration.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help="Small completion budget so the probe is mostly prompt-token bound.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help="Maximum number of requests to send before stopping.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Delay between successful requests.",
    )
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=DEFAULT_WINDOW_SECONDS,
        help="Rolling window size used to estimate TPM.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Client timeout in seconds.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Optional directory for JSONL probe logs.",
    )
    parser.add_argument(
        "--no-calibration",
        action="store_true",
        help="Disable prompt-size calibration after the first successful response.",
    )
    return parser.parse_args()


def load_role_config(config_path: Path, role: str) -> dict[str, Any]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if role not in payload:
        raise KeyError(f"Role {role!r} not found in {config_path}")
    role_config = payload[role]
    if not isinstance(role_config, dict):
        raise TypeError(f"Role {role!r} in {config_path} is not a JSON object")
    return role_config


def resolve_endpoint(args: argparse.Namespace) -> tuple[str, str, str]:
    config_values: dict[str, Any] = {}
    if args.config is not None:
        config_values = load_role_config(args.config, args.role)
    base_url = args.base_url or config_values.get("base_url")
    api_key = args.api_key or config_values.get("api_key")
    model = args.model or config_values.get("model") or DEFAULT_MODEL
    missing = [name for name, value in (("base_url", base_url), ("api_key", api_key), ("model", model)) if not value]
    if missing:
        raise ValueError(f"Missing required endpoint values: {', '.join(missing)}")
    return str(base_url), str(api_key), str(model)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_probe_prompt(word_count: int, round_index: int) -> str:
    header = (
        "This is a throughput probe.\n"
        "Read the payload and reply with exactly OK.\n"
        "Do not summarize or repeat the payload.\n"
    )
    words = ("alpha " * max(1, word_count)).strip()
    return f"{header}Round={round_index}\n{words}"


def calibrate_word_count(current_word_count: int, observed_prompt_tokens: int, target_prompt_tokens: int) -> int:
    if observed_prompt_tokens <= 0:
        return current_word_count
    scaled = int(current_word_count * target_prompt_tokens / observed_prompt_tokens)
    return max(128, scaled)


def extract_usage(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        raise RuntimeError("Response does not include usage metrics.")
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    if total_tokens <= 0:
        raise RuntimeError("Response usage.total_tokens is missing or zero.")
    return prompt_tokens, completion_tokens, total_tokens


def detect_rate_limit_kind(message: str) -> str | None:
    lowered = message.lower()
    if "tpm limit reached" in lowered:
        return "TPM"
    if "rpm limit reached" in lowered:
        return "RPM"
    return None


def jsonl_writer(log_dir: Path | None):
    if log_dir is None:
        return None
    ensure_dir(log_dir)
    log_path = log_dir / f"qwen3_tpm_probe_{utc_now().strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    return log_path.open("a", encoding="utf-8")


def write_log_line(handle: Any, payload: dict[str, Any]) -> None:
    if handle is None:
        return
    handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    handle.flush()


def main() -> int:
    args = parse_args()
    try:
        base_url, api_key, model = resolve_endpoint(args)
    except Exception as exc:
        print(f"config_error: {exc}", file=sys.stderr)
        return 1

    print(f"base_url={base_url}")
    print(f"model={model}")
    print(f"window_seconds={args.window_seconds}")
    print(f"target_prompt_tokens={args.target_prompt_tokens}")

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=args.timeout_seconds)
    window: deque[tuple[datetime, ProbeEvent]] = deque()
    rolling_prompt = 0
    rolling_completion = 0
    rolling_total = 0
    word_count = args.target_prompt_tokens
    last_success_total = None
    log_handle = jsonl_writer(args.log_dir)

    try:
        for round_index in range(1, args.max_rounds + 1):
            prompt = build_probe_prompt(word_count, round_index)
            started_at = utc_now()
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "Reply with exactly OK."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                    max_tokens=args.max_output_tokens,
                )
                prompt_tokens, completion_tokens, total_tokens = extract_usage(response)
            except Exception as exc:
                error_text = str(exc)
                limit_kind = detect_rate_limit_kind(error_text)
                print(f"round={round_index} status=error kind={limit_kind or 'other'}")
                print(f"message={error_text}")
                print(f"last_success_rolling_{args.window_seconds}s_total_tokens={rolling_total}")
                if last_success_total is not None and limit_kind == "TPM":
                    print(
                        "approx_tpm_limit_range="
                        f"[{rolling_total}, {rolling_total + last_success_total}]"
                    )
                write_log_line(
                    log_handle,
                    {
                        "timestamp_utc": started_at.isoformat(),
                        "round_index": round_index,
                        "status": "error",
                        "kind": limit_kind,
                        "message": error_text,
                        "rolling_total_tokens": rolling_total,
                        "rolling_prompt_tokens": rolling_prompt,
                        "rolling_completion_tokens": rolling_completion,
                    },
                )
                return 2 if limit_kind == "TPM" else 1

            while window and started_at - window[0][0] >= timedelta(seconds=args.window_seconds):
                _, expired = window.popleft()
                rolling_prompt -= expired.prompt_tokens
                rolling_completion -= expired.completion_tokens
                rolling_total -= expired.total_tokens

            event = ProbeEvent(
                round_index=round_index,
                timestamp_utc=started_at.isoformat(),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                rolling_prompt_tokens=rolling_prompt + prompt_tokens,
                rolling_completion_tokens=rolling_completion + completion_tokens,
                rolling_total_tokens=rolling_total + total_tokens,
            )
            window.append((started_at, event))
            rolling_prompt = event.rolling_prompt_tokens
            rolling_completion = event.rolling_completion_tokens
            rolling_total = event.rolling_total_tokens
            last_success_total = total_tokens

            print(
                f"round={round_index} status=ok "
                f"prompt_tokens={prompt_tokens} completion_tokens={completion_tokens} "
                f"total_tokens={total_tokens} rolling_{args.window_seconds}s_total={rolling_total}"
            )
            write_log_line(
                log_handle,
                {
                    "status": "ok",
                    **asdict(event),
                    "word_count": word_count,
                },
            )

            if round_index == 1 and not args.no_calibration:
                calibrated = calibrate_word_count(word_count, prompt_tokens, args.target_prompt_tokens)
                if calibrated != word_count:
                    print(f"calibration word_count={word_count}->{calibrated}")
                    word_count = calibrated

            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)
    finally:
        if log_handle is not None:
            log_handle.close()

    print("probe_finished_without_tpm")
    print(f"max_observed_rolling_{args.window_seconds}s_total_tokens={rolling_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
