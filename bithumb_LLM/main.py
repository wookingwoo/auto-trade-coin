from fetch_trade import (
    fetch_candle_data,
    fetch_recent_trades,
    fetch_ticker,
    fetch_orderbook,
)
from llm_decision.deepseek import get_trading_decision
from order_execution import execute_order
import os
from dotenv import load_dotenv
from config import MARKET_LIST
from order_chance import get_order_chance
from slack_bot import send_slack_message


# Load environment variables
load_dotenv()
LLM_MODEL = os.getenv("LLM_MODEL")

data_count = 30


def main():

    # Get account balance
    bithumb_access_key = os.getenv("BITHUMB_API_KEY")
    bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")

    all_market_data = ""

    for market in MARKET_LIST:
        print(f"market: {market}")

        # Get coin data
        minute_candle_data = fetch_candle_data(market, "minutes/60", data_count)
        day_candle_data = fetch_candle_data(market, "days", data_count)
        week_candle_data = fetch_candle_data(market, "weeks", data_count)
        month_candle_data = fetch_candle_data(market, "months", data_count)
        tick_data = fetch_recent_trades(market, data_count)
        ticker_data = fetch_ticker(market)
        orderbook_data = fetch_orderbook(market)

        status_code, order_chance = get_order_chance(
            bithumb_access_key, bithumb_secret_key, market
        )

        if status_code != 200:
            send_slack_message(f"Error getting order chance: {order_chance}")
            return

        # Define maker fees
        maker_bid_fee = order_chance["maker_bid_fee"]
        maker_ask_fee = order_chance["maker_ask_fee"]

        market_data = f"""
        {market} Market Data:
        
        - Market: {market}
        - Minute Candle Data: {minute_candle_data}
        - Day Candle Data: {day_candle_data}
        - Week Candle Data: {week_candle_data}
        - Month Candle Data: {month_candle_data}
        - Tick Data: {tick_data}
        - Ticker Data: {ticker_data}
        - Orderbook Data: {orderbook_data}
        - Maker Bid Fee: {maker_bid_fee}
        - Maker Ask Fee: {maker_ask_fee}
        """

        all_market_data += market_data

    # Read prompt from file
    with open("prompt.md", "r", encoding="utf-8") as file:
        prompt_template = file.read()

    # Format the prompt with market data
    user_message = prompt_template.replace("{{market_data}}", all_market_data)
    user_message = user_message.replace("{{market_list}}", "/".join(MARKET_LIST))

    print("\nuser_message:", user_message)

    # Get trading decision from DeepSeek
    decision_list = get_trading_decision(user_message)
    print()
    send_slack_message(f"Trading Decisions: {decision_list}")

    for decision in decision_list:
        market = decision["market"]

        # Execute order based on decision
        if decision["decision"] in ["buy", "sell"]:
            side = "bid" if decision["decision"] == "buy" else "ask"
            price = ticker_data[0]["trade_price"]  # Use closing price (current price)

            # Determine account type and price adjustment based on decision
            # price_multiplier = 1.05 if decision["decision"] == "buy" else 0.95
            price_multiplier = 1

            volume = 0

            print("현재 잔고:", float(order_chance["ask_account"]["balance"]))
            print(f"{market} 현재가: {price}")

            print()
            if decision["decision"] == "buy":
                send_slack_message(f"{market}을 매수합니다.")
                volume = (
                    float(order_chance["bid_account"]["balance"])
                    / price
                    * decision["trade_ratio"]
                )

            elif decision["decision"] == "sell":
                send_slack_message(f"{market}을 매도합니다.")
                volume = (
                    float(order_chance["ask_account"]["balance"])
                    * decision["trade_ratio"]
                )

            price = int(price * price_multiplier)

            send_slack_message(f"volume(주문량): {volume}")
            send_slack_message(f"price(주문가격): {price}")

            execute_order(
                bithumb_access_key, bithumb_secret_key, market, side, volume, price
            )


if __name__ == "__main__":
    send_slack_message(f"코인 자동매매 봇을 시작합니다. :bank: bithumb, {LLM_MODEL}")
    main()
