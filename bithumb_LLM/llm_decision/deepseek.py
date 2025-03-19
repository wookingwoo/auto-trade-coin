from openai import OpenAI
import json
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")


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


def get_trading_decision(user_message):
    """
    Uses DeepSeek API to get a trading decision based on user input.
    """
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a financial expert assistant. Analyze the provided market data thoroughly and offer a well-reasoned decision on whether to buy, sell, or hold. Consider all relevant factors, including market trends and fees, to maximize the user's financial benefit.",
            },
            {"role": "user", "content": user_message},
        ],
        stream=False,
    )

    response_content = response.choices[0].message.content
    decision_json = parse_json_content(response_content)
    return decision_json
