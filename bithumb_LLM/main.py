from trade_USDT import (
    fetch_candle_data,
    fetch_recent_trades,
    fetch_ticker,
    fetch_orderbook,
)
from deepseek_decision import get_trading_decision
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

data_count = 1


def main():
    # Example usage
    minute_candle_data = fetch_candle_data("minutes/60", data_count)
    day_candle_data = fetch_candle_data("days", data_count)
    week_candle_data = fetch_candle_data("weeks", data_count)
    month_candle_data = fetch_candle_data("months", data_count)
    tick_data = fetch_recent_trades(data_count)
    ticker_data = fetch_ticker()
    orderbook_data = fetch_orderbook()

    # Read prompt from file
    with open("prompt.md", "r") as file:
        prompt_template = file.read()

    # Format the prompt with market data
    user_message = prompt_template.format(
        minute_candle_data=minute_candle_data,
        day_candle_data=day_candle_data,
        week_candle_data=week_candle_data,
        month_candle_data=month_candle_data,
        tick_data=tick_data,
        ticker_data=ticker_data,
        orderbook_data=orderbook_data,
    )

    print("user_message", user_message)

    # Get trading decision from DeepSeek
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    decision = get_trading_decision(deepseek_api_key, user_message)
    print("Trading Decision:", decision)


if __name__ == "__main__":
    main()
