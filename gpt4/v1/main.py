import os
import pyupbit
import pandas as pd
import pandas_ta as ta
import json
from openai import OpenAI
import traceback

from slack_bot import send_slack_message

from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
GPT_MODEL = os.getenv("GPT_MODEL")

# Setup
client = OpenAI(api_key=OPENAI_API_KEY)
upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)


# 한화로 환산한 총 보유 자산 (KRW, BTC 포함)
def calculate_total_assets(json_data):
    total_assets = 0
    for entry in json_data:
        if entry["currency"] == "KRW":
            total_assets += float(entry["balance"])
        if entry["currency"] == "BTC":
            total_assets += float(entry["balance"]) * pyupbit.get_current_price(
                "KRW-BTC"
            )
    return total_assets


def format_json_to_slack(json_data):
    formatted_message = "```"
    for entry in json_data:
        formatted_message += f"\nCurrency: {entry['currency']}\nBalance: {entry['balance']}\nLocked: {entry['locked']}\nAvg Buy Price: {entry['avg_buy_price']}\nAvg Buy Price Modified: {entry['avg_buy_price_modified']}\nUnit Currency: {entry['unit_currency']}\n"

    formatted_message += "\n총 보유 금액: "
    formatted_message += "{:,.2f}".format(calculate_total_assets(json_data))
    formatted_message += "KRW\n```"
    return formatted_message


def get_current_status():
    orderbook = pyupbit.get_orderbook(ticker="KRW-BTC")
    current_time = orderbook["timestamp"]
    btc_balance = 0
    krw_balance = 0
    btc_avg_buy_price = 0
    balances = upbit.get_balances()
    send_slack_message(format_json_to_slack(balances))
    for b in balances:
        if b["currency"] == "BTC":
            btc_balance = b["balance"]
            btc_avg_buy_price = b["avg_buy_price"]
        if b["currency"] == "KRW":
            krw_balance = b["balance"]

    current_status = {
        "current_time": current_time,
        "orderbook": orderbook,
        "btc_balance": btc_balance,
        "krw_balance": krw_balance,
        "btc_avg_buy_price": btc_avg_buy_price,
    }
    return json.dumps(current_status)


def fetch_and_prepare_data():
    global btc_balance
    # Fetch data
    df_daily = pyupbit.get_ohlcv("KRW-BTC", "day", count=30)
    df_hourly = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=24)

    # Define a helper function to add indicators
    def add_indicators(df):
        # Moving Averages
        df["SMA_10"] = ta.sma(df["close"], length=10)
        df["EMA_10"] = ta.ema(df["close"], length=10)

        # RSI
        df["RSI_14"] = ta.rsi(df["close"], length=14)

        # Stochastic Oscillator
        stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
        df = df.join(stoch)

        # MACD
        ema_fast = df["close"].ewm(span=12, adjust=False).mean()
        ema_slow = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema_fast - ema_slow
        df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Histogram"] = df["MACD"] - df["Signal_Line"]

        # Bollinger Bands
        df["Middle_Band"] = df["close"].rolling(window=20).mean()
        # Calculate the standard deviation of closing prices over the last 20 days
        std_dev = df["close"].rolling(window=20).std()
        # Calculate the upper band (Middle Band + 2 * Standard Deviation)
        df["Upper_Band"] = df["Middle_Band"] + (std_dev * 2)
        # Calculate the lower band (Middle Band - 2 * Standard Deviation)
        df["Lower_Band"] = df["Middle_Band"] - (std_dev * 2)

        return df

    # Add indicators to both dataframes
    df_daily = add_indicators(df_daily)
    df_hourly = add_indicators(df_hourly)

    combined_df = pd.concat([df_daily, df_hourly], keys=["daily", "hourly"])
    combined_data = combined_df.to_json(orient="split")

    # make combined data as string and print length
    print(len(combined_data))

    return json.dumps(combined_data)


def get_instructions(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            instructions = file.read()
        return instructions
    except FileNotFoundError:
        send_slack_message("File not found.")
    except Exception as e:
        send_slack_message(
            ":bug: `An error occurred while reading the file`:\n```{e}```"
        )


def analyze_data_with_gpt4(data_json):
    gpt_prompt_path = "gpt_prompt.md"
    try:
        instructions = get_instructions(gpt_prompt_path)
        if not instructions:
            send_slack_message("No instructions found.")

        current_status = get_current_status()
        print("current_status:", current_status)
        # send_slack_message(f"**current_status**\n```{current_status}```")

        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": data_json},
                {"role": "user", "content": current_status},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content
    except Exception as e:
        send_slack_message(f":bug: `Error in analyzing data with GPT-4`\n```{e}```")
        print(traceback.format_exc())
        return None


def execute_buy():
    print("Attempting to buy BTC...")
    try:
        krw = upbit.get_balance("KRW")
        if krw > 5000:
            result = upbit.buy_market_order("KRW-BTC", krw * 0.9995)
            send_slack_message(f"**Buy order successful**\n```{result}```")
    except Exception as e:
        send_slack_message(f"**:bug: `Failed to execute buy order**`\n```{e}```")


def execute_sell():
    print("Attempting to sell BTC...")
    try:
        btc = upbit.get_balance("BTC")
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")["orderbook_units"][0][
            "ask_price"
        ]
        if current_price * btc > 5000:
            result = upbit.sell_market_order("KRW-BTC", btc)
            send_slack_message(f"**Sell order successful**\n```{result}```")
    except Exception as e:
        send_slack_message(f"**:bug: Failed to execute sell order**\n```{e}```")


def make_decision_and_execute():
    print("Making decision and executing...")
    data_json = fetch_and_prepare_data()
    advice = analyze_data_with_gpt4(data_json)

    try:
        decision = json.loads(advice)
        print(decision)
        if decision.get("decision") == "buy":
            execute_buy()
            message_text = f"""
**비트코인을 매수합니다.** :moneybag:
- reason
```{decision.get('reason')}```
"""
        elif decision.get("decision") == "sell":
            execute_sell()
            message_text = f"""
**비트코인을 매도합니다.** :money_with_wings:
- reason
```{decision.get('reason')}```
"""
        elif decision.get("decision") == "hold":
            message_text = f"""
**비트코인을 보유합니다.** :eyes:
- reason
```{decision.get('reason')}```
"""
        else:
            message_text = f"""
**결정을 내릴 수 없습니다.** :thinking_face:
- decision
```{decision}```
"""
        send_slack_message(message_text)
    except Exception as e:
        send_slack_message(f":bug: `Failed to parse the advice as JSON`: {e}")


if __name__ == "__main__":
    send_slack_message("주식 자동매매 봇을 시작합니다. :robot_face: v1")
    make_decision_and_execute()
