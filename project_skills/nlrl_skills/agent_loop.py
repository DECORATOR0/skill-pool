from __future__ import annotations

import json
from pathlib import Path

from .config import LLMConfig
from .llm import JSON_OBJECT_RESPONSE_FORMAT, OpenAICompatibleLLM, log_llm_call
from .prompting import load_prompt
from .schemas import LLMMessage, ToolCallRecord
from .tools import Toolbox
from .utils import extract_json_object


def _summarize_large_value(value, *, list_head: int = 20, list_tail: int = 20):
    if isinstance(value, list) and len(value) > list_head + list_tail:
        return {
            "truncated": True,
            "item_count": len(value),
            "head": value[:list_head],
            "tail": value[-list_tail:],
        }
    if isinstance(value, dict):
        summarized = {}
        for key, item in value.items():
            if isinstance(item, list) and len(item) > list_head + list_tail:
                summarized[key] = {
                    "truncated": True,
                    "item_count": len(item),
                    "head": item[:list_head],
                    "tail": item[-list_tail:],
                }
            elif isinstance(item, str) and len(item) > 2000:
                summarized[key] = {
                    "truncated": True,
                    "char_count": len(item),
                    "head": item[:1200],
                    "tail": item[-400:],
                }
            else:
                summarized[key] = item
        return summarized
    return value


def _observation_for_prompt(raw_result, *, limit: int = 6000) -> str:
    observation = json.dumps(raw_result, ensure_ascii=False, default=str)
    if len(observation) <= limit:
        return observation
    summarized = _summarize_large_value(raw_result)
    compact = json.dumps(summarized, ensure_ascii=False, default=str)
    if len(compact) <= limit:
        return compact
    return json.dumps(
        {
            "truncated": True,
            "char_count": len(observation),
            "head": observation[:4000],
            "tail": observation[-1200:],
        },
        ensure_ascii=False,
    )


class JSONToolAgent:
    def __init__(self, llm_config: LLMConfig, prompt_root: Path, toolbox: Toolbox):
        self.llm = OpenAICompatibleLLM(llm_config)
        self.prompt_root = prompt_root
        self.toolbox = toolbox

    def run(
        self,
        *,
        role_name: str,
        base_system_prompt: str,
        user_prompt: str,
        allowed_tools: list[str] | None,
        max_steps: int,
        log_dir: Path,
    ) -> tuple[dict, str, list[ToolCallRecord]]:
        tool_protocol = load_prompt(self.prompt_root / "tool_agent_protocol.md")
        messages = [
            LLMMessage(
                role="system",
                content=base_system_prompt
                + "\n\n"
                + tool_protocol.format(tools_json=self.toolbox.tool_prompt(allowed_tools)),
            ),
            LLMMessage(role="user", content=user_prompt),
        ]
        raw_outputs: list[str] = []
        records: list[ToolCallRecord] = []
        final_payload: dict = {
            "action": "final",
            "final_answer": "",
            "choice_label": "",
            "summary": "",
        }
        for step_idx in range(1, max_steps + 1):
            result = self.llm.chat(messages, response_format=JSON_OBJECT_RESPONSE_FORMAT)
            log_llm_call(log_dir / f"{role_name}_steps", f"{role_name}_step_{step_idx}", result)
            raw_outputs.append(result.text)
            payload = extract_json_object(result.text)
            messages.append(LLMMessage(role="assistant", content=json.dumps(payload, ensure_ascii=False)))
            action = str(payload.get("action", "")).strip().lower()
            if action == "final":
                final_payload = payload
                break
            if action != "tool":
                raise ValueError(f"Unsupported action from {role_name}: {action}")
            tool_name = str(payload.get("tool_name", "")).strip()
            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object.")
            thought = str(payload.get("thought", ""))
            allowed_set = set(allowed_tools or [])
            try:
                if allowed_set and tool_name not in allowed_set:
                    raise PermissionError(f"Tool `{tool_name}` is not allowed by the active skill.")
                raw_result = self.toolbox.execute(tool_name, arguments)
                if isinstance(raw_result, dict) and raw_result.get("returncode") not in (None, 0):
                    success = False
                    error = str(raw_result.get("stderr") or raw_result.get("stdout") or f"returncode={raw_result.get('returncode')}")
                else:
                    success = True
                    error = ""
                observation = _observation_for_prompt(raw_result)
            except Exception as exc:
                raw_result = {"error": str(exc)}
                observation = json.dumps(raw_result, ensure_ascii=False)
                success = False
                error = str(exc)
            records.append(
                ToolCallRecord(
                    step_index=step_idx,
                    thought=thought,
                    tool_name=tool_name,
                    arguments=arguments,
                    observation=observation,
                    success=success,
                    raw_result=raw_result,
                    error=error,
                )
            )
            messages.append(
                LLMMessage(
                    role="user",
                    content=(
                        f"Tool result for step {step_idx}:\n"
                        f"- tool_name: {tool_name}\n"
                        f"- success: {success}\n"
                        f"- observation: {observation}\n"
                        "Decide the next step using the same JSON protocol."
                    ),
                )
            )
        return final_payload, "\n\n".join(raw_outputs), records
