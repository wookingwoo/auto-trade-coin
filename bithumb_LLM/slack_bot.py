import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


from dotenv import load_dotenv

load_dotenv()
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_COINBOT_CHANNEL_NAME = os.getenv("SLACK_COINBOT_CHANNEL_NAME")


app = App(token=SLACK_BOT_TOKEN)


def send_slack_message(text, channel=SLACK_COINBOT_CHANNEL_NAME):
    try:
        response = app.client.chat_postMessage(
            channel=channel,
            text=text,
        )
        # print(response)
        print(text)
    except Exception as e:
        print(f"Failed to send message: {str(e)}")


@app.event("app_mention")
def who_am_i(event, client, message, say):
    print("event:", event)
    print("client:", client)
    print("message:", message)

    say(f'hello! <@{event["user"]}>')


if __name__ == "__main__":
    send_slack_message("Hello, wookingwoo :wave: This is bithumb LLM test message")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
