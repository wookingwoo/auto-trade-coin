import os
from dotenv import load_dotenv

from autotrade import make_decision_and_execute
from slack_bot import send_slack_message

load_dotenv()
GPT_MODEL = os.getenv("GPT_MODEL")

if __name__ == "__main__":
    send_slack_message(
        f"코인 자동매매 봇을 시작합니다. :bank: UPbit, :gpt: {GPT_MODEL}"
    )
    make_decision_and_execute()
