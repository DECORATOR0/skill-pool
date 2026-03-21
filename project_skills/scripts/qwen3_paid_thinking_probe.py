from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


@dataclass
class ProbeCase:
    name: str
    stream: bool
    enable_thinking: bool | None
    response_format: dict[str, Any] | None
    prompt: str
    max_tokens: int = 128


def load_role_config(config_path: Path, role: str) -> dict[str, Any]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return data[role]


def chunk_to_dict(chunk: Any) -> dict[str, Any]:
    if hasattr(chunk, "model_dump"):
        return chunk.model_dump()
    if hasattr(chunk, "to_dict"):
        return chunk.to_dict()
    return json.loads(chunk.model_dump_json())


def run_case(client: OpenAI, model: str, case: ProbeCase) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": case.prompt}],
        "temperature": 0.0,
        "max_tokens": case.max_tokens,
        "stream": case.stream,
    }
    if case.response_format is not None:
        kwargs["response_format"] = case.response_format
    if case.enable_thinking is not None:
        kwargs["extra_body"] = {"enable_thinking": case.enable_thinking}

    result: dict[str, Any] = {
        "case": asdict(case),
        "request": kwargs,
    }
    try:
        if case.stream:
            chunks = []
            text_parts: list[str] = []
            for chunk in client.chat.completions.create(**kwargs):
                raw_chunk = chunk_to_dict(chunk)
                chunks.append(raw_chunk)
                for choice in raw_chunk.get("choices", []):
                    delta = choice.get("delta", {}) or {}
                    content = delta.get("content")
                    if isinstance(content, str):
                        text_parts.append(content)
            result["success"] = True
            result["text"] = "".join(text_parts)
            result["chunks_preview"] = chunks[:8]
            result["chunk_count"] = len(chunks)
        else:
            response = client.chat.completions.create(**kwargs)
            raw = response.model_dump()
            result["success"] = True
            result["text"] = (response.choices[0].message.content or "") if response.choices else ""
            result["raw_response"] = raw
    except Exception as exc:
        result["success"] = False
        result["error"] = str(exc)
    return result


def build_cases() -> list[ProbeCase]:
    json_prompt = 'Return exactly {"ok":true,"n":1} as a JSON object.'
    plain_prompt = "Answer in one short sentence: what is 2+2?"
    return [
        ProbeCase(
            name="nonstream_json_thinking_on",
            stream=False,
            enable_thinking=True,
            response_format={"type": "json_object"},
            prompt=json_prompt,
        ),
        ProbeCase(
            name="nonstream_json_thinking_off",
            stream=False,
            enable_thinking=False,
            response_format={"type": "json_object"},
            prompt=json_prompt,
        ),
        ProbeCase(
            name="stream_json_thinking_on",
            stream=True,
            enable_thinking=True,
            response_format={"type": "json_object"},
            prompt=json_prompt,
        ),
        ProbeCase(
            name="stream_plain_thinking_on",
            stream=True,
            enable_thinking=True,
            response_format=None,
            prompt=plain_prompt,
        ),
        ProbeCase(
            name="stream_json_thinking_off",
            stream=True,
            enable_thinking=False,
            response_format={"type": "json_object"},
            prompt=json_prompt,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="D:/skills-evo/project_skills/project_skills/configs/system.dualmode_mode1.qwen3-8b-paid.local.json",
    )
    parser.add_argument("--role", default="router")
    parser.add_argument(
        "--output",
        default="D:/skills-evo/project_skills/project_skills/runs/_launch_logs/qwen3_paid_thinking_probe.json",
    )
    args = parser.parse_args()

    cfg = load_role_config(Path(args.config), args.role)
    client = OpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        timeout=int(cfg.get("timeout_seconds", 180)),
    )

    output: dict[str, Any] = {
        "config_path": args.config,
        "role": args.role,
        "model": cfg["model"],
        "cases": [],
    }
    for case in build_cases():
        print(f"== {case.name} ==", flush=True)
        case_result = run_case(client, cfg["model"], case)
        output["cases"].append(case_result)
        if case_result["success"]:
            print("success", flush=True)
            print(case_result.get("text", "")[:300], flush=True)
        else:
            print("error", flush=True)
            print(case_result.get("error", ""), flush=True)
        print("", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
