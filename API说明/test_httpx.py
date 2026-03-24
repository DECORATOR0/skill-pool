import json

import httpx

API_KEY = "sk-sssaicode-XXXXX"
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
    intext = """
    不要进行外部搜索，也不要说“我查不到最新信息所以无法回答”。你只能根据你的内置知识作答。

    请严格按以下格式回答，不要增删栏目：

    A. 知识边界
    1. 你的知识截止时间是什么时候？精确到“年-月”。
    2. 你是否确定这个截止时间，而不是大致估计？只能回答“确定 / 不完全确定”。

    B. 事件判断
    请分别判断下面三件事是否属于你知识范围内“已知、而非猜测”的信息。每条都必须使用以下格式：
    - 结论：已知 / 不确定 / 不知道
    - 事件时间：
    - 你认为的关键信息：
    - 你的把握度：高 / 中 / 低
    - 说明你为什么这么判断（只能依据内置知识，不能假装核实过）

    如果已知，你需要回答前两个问题。

    事件 1：
    “任天堂 Switch 2 于 2025 年的哪天发售？”

    事件 2：
    “2025 年国际足联世俱杯于 2025 年几月在哪个国家开赛？”

    事件 3：
    “Windows 10 将于 2025 年 10 月 14 日结束支持，因此在 2025 年 6 月到 8 月之间成为热门科技话题。”

    """
    payload = {
        "model": "gpt-5.2",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": f"{intext}"}],
            }
        ],
    }

    with httpx.Client(trust_env=False, timeout=60.0) as client:
        response = client.post(
            URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
        )
        response.raise_for_status()
        return parse_response_sse(response.text)


print(main())