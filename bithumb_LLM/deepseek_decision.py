from openai import OpenAI
import json
import re


def parse_json_content(response_content):
    try:
        # JSON만 추출하기 위해 정규식 사용
        json_match = re.search(r"\{[\s\S]*\}", response_content)
        if json_match:
            json_content = json_match.group(0)
            # JSON 파싱
            decision_json = json.loads(json_content)
            return decision_json
        else:
            raise ValueError("Valid JSON not found in the content.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON: {str(e)}")


def get_trading_decision(api_key, user_message):
    """
    Uses DeepSeek API to get a trading decision based on user input.
    """
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": user_message},
        ],
        stream=False,
    )

    response_content = response.choices[0].message.content
    decision_json = parse_json_content(response_content)
    return decision_json
