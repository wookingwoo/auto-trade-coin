import sys
from upbit_LLM.autotrade import make_decision_and_execute


def handler(event, context):
    print("Hello from AWS Lambda using Python" + sys.version + "!")
    return make_decision_and_execute()
