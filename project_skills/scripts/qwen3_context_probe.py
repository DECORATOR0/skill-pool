from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI
from transformers import AutoTokenizer


DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_ROLE = "executor"
DEFAULT_TARGETS = [28000, 40000, 80000, 110000]
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_SLEEP_SECONDS = 65.0
DEFAULT_MAX_OUTPUT_TOKENS = 8
DEFAULT_TOKENIZER = "Qwen/Qwen3-8B"


@dataclass
class ProbeResult:
    target_prompt_tokens: int
    actual_prompt_tokens: int
    status: str
    finish_reason: str
    response_text: str
    error_text: str
    prompt_tokens_from_usage: int | None
    completion_tokens_from_usage: int | None
    total_tokens_from_usage: int | None
    elapsed_seconds: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe context-window behavior for a Qwen3-compatible OpenAI endpoint."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional JSON config file with a role block, e.g. configs/system.dualmode_mode1.local.json.",
    )
    parser.add_argument(
        "--role",
        default=DEFAULT_ROLE,
        help=f"Role name to read from --config. Default: {DEFAULT_ROLE}.",
    )
    parser.add_argument("--base-url", help="OpenAI-compatible base URL.")
    parser.add_argument("--api-key", help="API key for the endpoint.")
    parser.add_argument("--model", default=None, help=f"Model name. Default: {DEFAULT_MODEL}.")
    parser.add_argument(
        "--targets",
        type=int,
        nargs="+",
        default=DEFAULT_TARGETS,
        help="Target prompt-token sizes to probe.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="OpenAI client timeout in seconds.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Sleep between probe requests to reduce TPM interference.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help="Small completion budget so the probe is prompt-length bound.",
    )
    parser.add_argument(
        "--tokenizer",
        default=DEFAULT_TOKENIZER,
        help=f"Tokenizer name used for prompt construction. Default: {DEFAULT_TOKENIZER}.",
    )
    parser.add_argument(
        "--system-prompt",
        default="Reply with exactly OK.",
        help="System prompt used for probing.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help="Optional JSON path for writing probe results.",
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
    api_key = args.api_key if args.api_key is not None else config_values.get("api_key", "")
    model = args.model or config_values.get("model") or DEFAULT_MODEL
    missing = [name for name, value in (("base_url", base_url), ("model", model)) if not value]
    if missing:
        raise ValueError(f"Missing required endpoint values: {', '.join(missing)}")
    return str(base_url), str(api_key or ""), str(model)


def build_joined_prompt(system_prompt: str, user_prompt: str) -> str:
    return f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"


def count_prompt_tokens(tokenizer: Any, system_prompt: str, user_prompt: str) -> int:
    joined = build_joined_prompt(system_prompt, user_prompt)
    return len(tokenizer.encode(joined, add_special_tokens=False))


def _user_payload(repeat_count: int, label: str) -> str:
    header = (
        "This is a context-window probe.\n"
        f"Target label: {label}.\n"
        "Read the payload and reply with exactly OK.\n"
        "Do not summarize or repeat the payload.\n"
        "Payload:\n"
    )
    filler = (" alpha" * max(1, repeat_count)).strip()
    return header + filler


def build_user_prompt_for_target(tokenizer: Any, system_prompt: str, target_prompt_tokens: int, label: str) -> tuple[str, int]:
    low = 1
    high = max(16, target_prompt_tokens)
    while count_prompt_tokens(tokenizer, system_prompt, _user_payload(high, label)) < target_prompt_tokens:
        high *= 2
        if high > target_prompt_tokens * 64:
            break

    best_prompt = _user_payload(low, label)
    best_tokens = count_prompt_tokens(tokenizer, system_prompt, best_prompt)

    while low <= high:
        mid = (low + high) // 2
        candidate_prompt = _user_payload(mid, label)
        candidate_tokens = count_prompt_tokens(tokenizer, system_prompt, candidate_prompt)
        if candidate_tokens <= target_prompt_tokens:
            best_prompt = candidate_prompt
            best_tokens = candidate_tokens
            low = mid + 1
        else:
            high = mid - 1

    return best_prompt, best_tokens


def classify_error(message: str) -> str:
    lowered = message.lower()
    context_markers = (
        "maximum context length",
        "context length",
        "maximum sequence length",
        "too many tokens",
        "context window",
        "prompt is too long",
        "requested tokens",
        "max context",
    )
    tpm_markers = (
        "tpm limit reached",
        "rate limiting",
        "rate limit",
        "429",
    )
    if any(marker in lowered for marker in context_markers):
        return "context_limit"
    if any(marker in lowered for marker in tpm_markers):
        return "tpm_limit"
    return "other_error"


def extract_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None, None
    return (
        int(getattr(usage, "prompt_tokens", 0) or 0),
        int(getattr(usage, "completion_tokens", 0) or 0),
        int(getattr(usage, "total_tokens", 0) or 0),
    )


def probe_one(
    *,
    client: OpenAI,
    tokenizer: Any,
    model: str,
    system_prompt: str,
    target_prompt_tokens: int,
    max_output_tokens: int,
) -> ProbeResult:
    user_prompt, actual_prompt_tokens = build_user_prompt_for_target(
        tokenizer, system_prompt, target_prompt_tokens, label=f"{target_prompt_tokens}"
    )
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=max_output_tokens,
        )
        elapsed = time.perf_counter() - started
        usage_prompt, usage_completion, usage_total = extract_usage(response)
        choice = response.choices[0] if response.choices else None
        message = getattr(choice, "message", None)
        finish_reason = str(getattr(choice, "finish_reason", "") or "")
        response_text = "" if message is None else str(getattr(message, "content", "") or "")
        return ProbeResult(
            target_prompt_tokens=target_prompt_tokens,
            actual_prompt_tokens=actual_prompt_tokens,
            status="ok",
            finish_reason=finish_reason,
            response_text=response_text,
            error_text="",
            prompt_tokens_from_usage=usage_prompt,
            completion_tokens_from_usage=usage_completion,
            total_tokens_from_usage=usage_total,
            elapsed_seconds=elapsed,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        error_text = str(exc)
        return ProbeResult(
            target_prompt_tokens=target_prompt_tokens,
            actual_prompt_tokens=actual_prompt_tokens,
            status=classify_error(error_text),
            finish_reason="",
            response_text="",
            error_text=error_text,
            prompt_tokens_from_usage=None,
            completion_tokens_from_usage=None,
            total_tokens_from_usage=None,
            elapsed_seconds=elapsed,
        )


def main() -> int:
    args = parse_args()
    try:
        base_url, api_key, model = resolve_endpoint(args)
    except Exception as exc:
        print(f"config_error: {exc}", file=sys.stderr)
        return 1

    print(f"base_url={base_url}")
    print(f"model={model}")
    print(f"tokenizer={args.tokenizer}")
    print(f"targets={args.targets}")
    print(f"sleep_seconds={args.sleep_seconds}")

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=args.timeout_seconds)

    results: list[ProbeResult] = []
    ordered_targets = list(args.targets)
    for index, target in enumerate(ordered_targets, start=1):
        print(f"\n=== probe {index}/{len(ordered_targets)} target={target} ===")
        result = probe_one(
            client=client,
            tokenizer=tokenizer,
            model=model,
            system_prompt=args.system_prompt,
            target_prompt_tokens=target,
            max_output_tokens=args.max_output_tokens,
        )
        results.append(result)
        usage_text = ""
        if result.prompt_tokens_from_usage is not None:
            usage_text = (
                f" usage_prompt={result.prompt_tokens_from_usage}"
                f" usage_completion={result.completion_tokens_from_usage}"
                f" usage_total={result.total_tokens_from_usage}"
            )
        print(
            f"target={result.target_prompt_tokens}"
            f" actual_prompt={result.actual_prompt_tokens}"
            f" status={result.status}"
            f" elapsed_s={result.elapsed_seconds:.2f}"
            f"{usage_text}"
        )
        if result.error_text:
            print(f"error={result.error_text}")
        elif result.response_text:
            print(f"response={result.response_text!r}")
        if index < len(ordered_targets) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    if args.log_path is not None:
        args.log_path.parent.mkdir(parents=True, exist_ok=True)
        args.log_path.write_text(
            json.dumps(
                {
                    "base_url": base_url,
                    "model": model,
                    "tokenizer": args.tokenizer,
                    "targets": ordered_targets,
                    "results": [asdict(item) for item in results],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nlog_path={args.log_path}")

    print("\n=== summary ===")
    for item in results:
        print(
            f"target={item.target_prompt_tokens}"
            f" actual={item.actual_prompt_tokens}"
            f" status={item.status}"
            f" usage_prompt={item.prompt_tokens_from_usage}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
