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
from config import MARKET
from order_chance import get_order_chance

# Load environment variables
load_dotenv()

data_count = 30


def main():

    # Get account balance
    bithumb_access_key = os.getenv("BITHUMB_API_KEY")
    bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")

    # Get coin data
    minute_candle_data = fetch_candle_data("minutes/60", data_count)
    day_candle_data = fetch_candle_data("days", data_count)
    week_candle_data = fetch_candle_data("weeks", data_count)
    month_candle_data = fetch_candle_data("months", data_count)
    tick_data = fetch_recent_trades(data_count)
    ticker_data = fetch_ticker()
    orderbook_data = fetch_orderbook()

    status_code, order_chance = get_order_chance(
        bithumb_access_key, bithumb_secret_key, MARKET
    )

    if status_code != 200:
        print("Error getting order chance:", order_chance)
        return

    # Define maker fees
    maker_bid_fee = order_chance["maker_bid_fee"]
    maker_ask_fee = order_chance["maker_ask_fee"]

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
        maker_bid_fee=maker_bid_fee,
        maker_ask_fee=maker_ask_fee,
    )

    print("user_message>>>", user_message)

    # Get trading decision from DeepSeek
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    decision = get_trading_decision(deepseek_api_key, user_message)
    print("Trading Decision:", decision)

    # Execute order based on decision
    if decision["decision"] in ["buy", "sell"]:
        side = "bid" if decision["decision"] == "buy" else "ask"
        price = ticker_data[0]["trade_price"]  # Use closing price (current price)

        # Determine account type and price adjustment based on decision
        price_multiplier = 1.05 if decision["decision"] == "buy" else 0.95

        volume = 0

        if decision["decision"] == "buy":
            print(f"{MARKET}을 매수합니다.")
            volume = (
                float(order_chance["bid_account"]["balance"])
                / price
                * decision["trade_ratio"]
            )

        elif decision["decision"] == "sell":
            print(f"{MARKET}을 매도합니다.")
            volume = (
                float(order_chance["ask_account"]["balance"]) * decision["trade_ratio"]
            )

        price = int(price * price_multiplier)

        print("volume(주문량):", volume)
        print("price(주문가격):", price)

        execute_order(
            bithumb_access_key, bithumb_secret_key, MARKET, side, volume, price
        )


if __name__ == "__main__":
    main()
