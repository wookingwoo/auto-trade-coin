from agents import Agent, Runner, set_default_openai_key
from pydantic import BaseModel
from dotenv import load_dotenv
import asyncio
import os
import re

from slack_bot import send_slack_message


load_dotenv()

set_default_openai_key(os.getenv("OPENAI_API_KEY"))


class DecisionType(BaseModel):
    decision: str
    percentage: int
    reason: str


def get_instructions(file_path="instructions.md"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        send_slack_message("File not found.")
    except Exception as e:
        send_slack_message(f"An error occurred while reading the file: {e}")


def replace_placeholders(instructions, bitcoin_context):
    """Replace placeholders in the instructions with actual data."""
    if bitcoin_context:
        real_time_data = ""

        for key, value in bitcoin_context.items():
            if value:  # Check if value exists
                real_time_data += f"""
- {key}
{value}
\n
"""

        instructions = re.sub(r"\{\{real_time_data\}\}", real_time_data, instructions)
    return instructions


async def get_agent_response(bitcoin_context, gpt_model):

    agent = Agent(
        name="Bitcoin Investment Expert",
        instructions="You are a Bitcoin investment expert who provides detailed market analysis, trading strategies, and investment advice. You analyze market trends, technical indicators, and news to offer informed recommendations for Bitcoin trading.",
        model=gpt_model,
        output_type=DecisionType,
    )

    instructions = get_instructions()
    instructions = replace_placeholders(instructions, bitcoin_context)

    # TODO: properties 값도 DB에 저장 (created. id, model, tokens)
    result = await Runner.run(agent, instructions)
    return result.final_output


if __name__ == "__main__":
    bitcoin_context = {
        "news_data": "test news data",
        "data_json": "test data json",
        "last_decisions": "test last decisions",
        "fear_and_greed": "test fear and greed",
        "current_status": "test current status",
    }
    result = asyncio.run(get_agent_response(bitcoin_context, "gpt-4o-mini"))
    print(result)
