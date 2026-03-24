import json

import requests

API_KEY = "sk-sssaicode-XXXXXX"
URL = "https://node-hk.sssaicode.com/api/v1/responses"


# https://node-hk.sssaicode.com/api/v1/responses
# https://claude2.sssaicode.com/api/v1/responses
# https://anti.sssaicode.com/api/v1/responses


def parse_response_sse(raw_text: str) -> str:
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

        if payload.get("type") != "response.completed":
            continue

        response = payload.get("response", {})
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text", "").strip()
                    if text:
                        return text

    raise RuntimeError("No output_text found in SSE response.")


def main() -> str:
    payload = {
        "model": "gpt-5.4",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "你好"}],
            }
        ],
    }

    with requests.Session() as session:
        session.trust_env = False
        response = session.post(
            URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return parse_response_sse(response.text)


if __name__ == "__main__":
    print(main())
