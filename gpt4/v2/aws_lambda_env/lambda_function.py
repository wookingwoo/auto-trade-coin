import sys
from gpt4.main import make_decision_and_execute


def handler(event, context):
    print("Hello from AWS Lambda using Python" + sys.version + "!")
    return make_decision_and_execute()
