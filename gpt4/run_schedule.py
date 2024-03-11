import schedule
import time

from slack_bot import send_slack_message
from main import make_decision_and_execute


send_slack_message("주식 자동매매 봇을 시작합니다. :robot_face:")
make_decision_and_execute()
schedule.every().minute.do(make_decision_and_execute)
# schedule.every().hour.do(make_decision_and_execute)

while True:
    schedule.run_pending()
    time.sleep(1)
