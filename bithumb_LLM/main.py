from trade_USDT import (
    fetch_candle_data,
    fetch_recent_trades,
    fetch_ticker,
    fetch_orderbook,
)
from deepseek_decision import get_trading_decision
from order_execution import execute_order
import os
from dotenv import load_dotenv
from config import MARKET, SIMBOL
from accounts import get_simbol_accounts

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
    with open("prompt.md", "r", encoding="utf-8") as file:
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

    # Get trading decision from DeepSeek
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    decision = get_trading_decision(deepseek_api_key, user_message)
    print("Trading Decision:", decision)

    # Get account balance
    bithumb_access_key = os.getenv("BITHUMB_API_KEY")
    bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")

    # Execute order based on decision
    if decision["decision"] in ["buy", "sell"]:
        side = "bid" if decision["decision"] == "buy" else "ask"
        price = ticker_data[0]["trade_price"]  # Use closing price (current price)

        # Determine account type and price adjustment based on decision
        account_currency = "KRW" if decision["decision"] == "buy" else SIMBOL
        price_multiplier = 1.05 if decision["decision"] == "buy" else 0.95

        # Fetch account balance and calculate volume
        simbol_accounts = get_simbol_accounts(
            bithumb_access_key, bithumb_secret_key, account_currency
        )
        balance = float(simbol_accounts[0]["balance"])
        volume = int(
            balance
            * decision["percentage"]
            / (price if decision["decision"] == "buy" else 1)
        )

        # Adjust price
        price = int(price * price_multiplier)

        print("volume(주문량):", volume)
        print("price(주문가격):", price)

        execute_order(
            bithumb_access_key, bithumb_secret_key, MARKET, side, volume, price
        )


if __name__ == "__main__":
    main()
