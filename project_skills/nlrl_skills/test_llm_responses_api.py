from __future__ import annotations

from project_skills.nlrl_skills.config import LLMConfig
from project_skills.nlrl_skills.llm import OpenAICompatibleLLM
from project_skills.nlrl_skills.schemas import LLMMessage


def _responses_llm() -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        LLMConfig(
            name="actor",
            model="gpt-5.2",
            base_url="https://node-hk.sssaicode.com/api/v1/responses",
            api_key="test-key",
            api_mode="responses_sse",
        )
    )


def test_parse_responses_sse_text_extracts_output_text() -> None:
    llm = _responses_llm()
    raw_text = (
        'event: response.created\n'
        'data: {"type":"response.created","response":{"id":"resp_1"}}\n\n'
        'event: response.completed\n'
        'data: {"type":"response.completed","response":{"id":"resp_1","output":[{"type":"message","content":[{"type":"output_text","text":"{\\"ok\\": true}"}]}]}}\n\n'
    )

    result = llm._parse_responses_sse_text(raw_text, {"model": "gpt-5.2"})

    assert result.text == '{"ok": true}'
    assert result.raw_response["type"] == "response.completed"


def test_responses_endpoint_appends_suffix_when_needed() -> None:
    llm = OpenAICompatibleLLM(
        LLMConfig(
            name="critic",
            model="gpt-5.2",
            base_url="https://node-hk.sssaicode.com/api/v1",
            api_key="test-key",
            api_mode="responses_sse",
        )
    )

    assert llm._responses_endpoint() == "https://node-hk.sssaicode.com/api/v1/responses"


def test_build_responses_payload_moves_system_prompt_to_instructions() -> None:
    llm = _responses_llm()

    payload = llm._build_responses_payload(
        [
            LLMMessage(role="system", content="System rules."),
            LLMMessage(role="user", content="User request."),
        ]
    )

    assert payload["instructions"] == "System rules."
    assert payload["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "User request."}],
        }
    ]
