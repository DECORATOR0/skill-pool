from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from .config import LLMConfig
from .schemas import LLMMessage
from .utils import ensure_dir, extract_json_object, utc_timestamp, write_json

JSON_OBJECT_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}


@dataclass
class LLMCallResult:
    text: str
    raw_response: dict[str, Any]
    request_payload: dict[str, Any]


class OpenAICompatibleLLM:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None if self._uses_responses_sse() else OpenAI(base_url=config.base_url, api_key=config.api_key, timeout=config.timeout_seconds)
        self.max_retries = 5
        self.retry_delay_seconds = 6

    def _uses_responses_sse(self) -> bool:
        return self.config.api_mode.strip().lower() == "responses_sse"

    def _responses_endpoint(self) -> str:
        endpoint = self.config.base_url.rstrip("/")
        if endpoint.endswith("/responses"):
            return endpoint
        if endpoint.endswith("/v1"):
            return endpoint + "/responses"
        return endpoint

    def _extract_responses_output_text(self, payload: dict[str, Any]) -> str:
        response = payload.get("response", {})
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = str(content.get("text", ""))
                    if text.strip():
                        return text
        raise RuntimeError("No output_text found in responses SSE response.")

    def _extract_responses_error(self, payload: dict[str, Any]) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message
        response = payload.get("response", {})
        response_error = response.get("error")
        if isinstance(response_error, dict):
            message = response_error.get("message")
            if isinstance(message, str) and message.strip():
                return message
        return json.dumps(payload, ensure_ascii=False)

    def _responses_chat(self, payload: dict[str, Any]) -> LLMCallResult:
        with httpx.Client(trust_env=False, timeout=float(self.config.timeout_seconds)) as client:
            response = client.post(
                self._responses_endpoint(),
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Accept": "text/event-stream",
                },
                json=payload,
            )
            response.raise_for_status()
        return self._parse_responses_sse_text(response.text, payload)

    def _build_responses_payload(self, messages: list[LLMMessage]) -> dict[str, Any]:
        instructions_parts = [message.content for message in messages if message.role == "system" and message.content.strip()]
        conversation_input = [
            {
                "role": message.role,
                "content": [{"type": "input_text", "text": message.content}],
            }
            for message in messages
            if message.role != "system"
        ]
        if not conversation_input:
            conversation_input = [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Follow the provided instructions."}],
                }
            ]
        payload: dict[str, Any] = {
            "model": self.config.model,
            "input": conversation_input,
        }
        if instructions_parts:
            payload["instructions"] = "\n\n".join(instructions_parts)
        return payload

    def _parse_responses_sse_text(self, raw_text: str, request_payload: dict[str, Any]) -> LLMCallResult:
        last_payload: dict[str, Any] | None = None
        completed_payload: dict[str, Any] | None = None
        for block in raw_text.split("\n\n"):
            lines = block.strip().splitlines()
            if not lines:
                continue
            data_lines = [line[6:] for line in lines if line.startswith("data: ")]
            if not data_lines:
                continue
            try:
                payload = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                continue
            last_payload = payload
            payload_type = str(payload.get("type", ""))
            if payload_type == "response.completed":
                completed_payload = payload
                break
            if payload_type in {"error", "response.failed"}:
                raise RuntimeError(self._extract_responses_error(payload))

        if completed_payload is None:
            error_message = "No response.completed event found in responses SSE output."
            if last_payload is not None:
                error_message += f" Last payload: {self._extract_responses_error(last_payload)}"
            raise RuntimeError(error_message)

        text = self._extract_responses_output_text(completed_payload)
        return LLMCallResult(text=text, raw_response=completed_payload, request_payload=request_payload)

    def _should_retry(self, exc: Exception) -> bool:
        message = str(exc).lower()
        retry_markers = (
            "400",
            "408",
            "409",
            "429",
            "500",
            "502",
            "503",
            "504",
            "bad gateway",
            "timeout",
            "timed out",
            "connection",
            "network",
            "temporarily unavailable",
            "bad_response_status_code",
        )
        return any(marker in message for marker in retry_markers)

    def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        resolved_max_tokens = self.config.max_tokens if max_tokens is None else max_tokens
        use_responses_sse = self._uses_responses_sse()
        use_streaming_thinking = self.config.enable_thinking is True and not use_responses_sse
        if use_responses_sse:
            payload = self._build_responses_payload(messages)
        else:
            payload = {
                "model": self.config.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": self.config.temperature if temperature is None else temperature,
            }
            if resolved_max_tokens is not None:
                payload["max_tokens"] = resolved_max_tokens
            if response_format is not None and not use_streaming_thinking:
                payload["response_format"] = response_format
            if self.config.enable_thinking is not None:
                payload["extra_body"] = {"enable_thinking": self.config.enable_thinking}
        if use_streaming_thinking:
            payload["stream"] = True
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if use_responses_sse:
                    response = self._responses_chat(payload)
                elif use_streaming_thinking:
                    response = self._streaming_chat(payload)
                else:
                    assert self.client is not None
                    response = self.client.chat.completions.create(**payload)
                break
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
                if attempt >= self.max_retries or not self._should_retry(exc):
                    raise
                time.sleep(self.retry_delay_seconds)
        else:  # pragma: no cover - defensive
            raise RuntimeError(f"LLM call failed: {last_error}")
        if use_streaming_thinking or use_responses_sse:
            return response
        text = ""
        if response.choices:
            message = response.choices[0].message
            text = message.content or ""
        raw_response = json.loads(response.model_dump_json())
        return LLMCallResult(text=text, raw_response=raw_response, request_payload=payload)

    def _streaming_chat(self, payload: dict[str, Any]) -> LLMCallResult:
        if self.client is None:  # pragma: no cover - defensive
            raise RuntimeError("Streaming chat is unavailable for responses_sse API mode.")
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        chunk_count = 0
        for chunk in self.client.chat.completions.create(**payload):
            chunk_count += 1
            raw_chunk = json.loads(chunk.model_dump_json())
            for choice in raw_chunk.get("choices", []):
                delta = choice.get("delta", {}) or {}
                content = delta.get("content")
                if isinstance(content, str):
                    text_parts.append(content)
                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str):
                    reasoning_parts.append(reasoning)
        text = "".join(text_parts)
        raw_response = {
            "stream": True,
            "chunk_count": chunk_count,
            "content": text,
            "reasoning_content": "".join(reasoning_parts),
        }
        return LLMCallResult(text=text, raw_response=raw_response, request_payload=payload)

    def chat_json(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[dict[str, Any], LLMCallResult]:
        result = self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=JSON_OBJECT_RESPONSE_FORMAT,
        )
        return extract_json_object(result.text), result


def log_llm_call(log_dir: Path, role_name: str, result: LLMCallResult) -> None:
    ensure_dir(log_dir)
    stamp = utc_timestamp()
    write_json(
        log_dir / f"{stamp}_{role_name}_request.json",
        result.request_payload,
    )
    write_json(
        log_dir / f"{stamp}_{role_name}_response.json",
        {
            "text": result.text,
            "raw_response": result.raw_response,
        },
    )
