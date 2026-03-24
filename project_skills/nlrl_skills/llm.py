from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout_seconds,
            http_client=httpx.Client(
                timeout=config.timeout_seconds,
                trust_env=self._should_trust_env(config.base_url),
            ),
        )
        self.max_retries = 5
        self.retry_delay_seconds = 6

    @staticmethod
    def _should_trust_env(base_url: str) -> bool:
        host = (urlparse(base_url).hostname or "").lower()
        if host in {"127.0.0.1", "localhost"}:
            return False
        if host in {"35.220.164.252", "api.boyuerichdata.opensphereai.com"}:
            return False
        if host.startswith("192.168.") or host.startswith("10."):
            return False
        if host.startswith("172.16.") or host.startswith("172.17.") or host.startswith("172.18.") or host.startswith("172.19."):
            return False
        if host.startswith("172.2") or host.startswith("172.3"):
            return False
        return True

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
        use_streaming_thinking = self.config.enable_thinking is True
        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.config.temperature if temperature is None else temperature,
        }
        resolved_max_tokens = self.config.max_tokens if max_tokens is None else max_tokens
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
                if use_streaming_thinking:
                    response = self._streaming_chat(payload)
                else:
                    response = self.client.chat.completions.create(**payload)
                break
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
                if attempt >= self.max_retries or not self._should_retry(exc):
                    raise
                time.sleep(self.retry_delay_seconds)
        else:  # pragma: no cover - defensive
            raise RuntimeError(f"LLM call failed: {last_error}")
        if use_streaming_thinking:
            return response
        text = ""
        if response.choices:
            message = response.choices[0].message
            text = message.content or ""
        raw_response = json.loads(response.model_dump_json())
        return LLMCallResult(text=text, raw_response=raw_response, request_payload=payload)

    def _streaming_chat(self, payload: dict[str, Any]) -> LLMCallResult:
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
