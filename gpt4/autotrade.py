import os
import json
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
import pyupbit
import pandas as pd
import pandas_ta as ta
from openai import OpenAI
from slack_bot import send_slack_message

load_dotenv()
GPT_MODEL = os.getenv("GPT_MODEL")
MONGO_URI = os.getenv("MONGO_URI")

# Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["autoTradeCoin"]
decisions_collection = db["decisions"]


def save_decision_to_db(decision, current_status):
    status_dict = json.loads(current_status)
    current_price = pyupbit.get_orderbook(ticker="KRW-BTC")["orderbook_units"][0][
        "ask_price"
    ]

    data_to_insert = {
        "timestamp": datetime.now(timezone.utc),
        "ai_model": GPT_MODEL,
        "decision": decision.get("decision"),
        "percentage": decision.get("percentage", 100),
        "reason": decision.get("reason", ""),
        "btc_balance": float(status_dict.get("btc_balance", 0)),
        "krw_balance": float(status_dict.get("krw_balance", 0)),
        "btc_avg_buy_price": float(status_dict.get("btc_avg_buy_price", 0)),
        "btc_krw_price": current_price,
    }

    decisions_collection.insert_one(data_to_insert)


def fetch_last_decisions(num_decisions=10):
    decisions = decisions_collection.find().sort("timestamp", -1).limit(num_decisions)
    formatted_decisions = [
        {
            "timestamp": int(decision["timestamp"].timestamp() * 1000),
            "decision": decision["decision"],
            "percentage": decision["percentage"],
            "reason": decision["reason"],
            "btc_balance": decision["btc_balance"],
            "krw_balance": decision["krw_balance"],
            "btc_avg_buy_price": decision["btc_avg_buy_price"],
        }
        for decision in decisions
    ]
    return (
        "\n".join(map(str, formatted_decisions))
        if formatted_decisions
        else "No decisions found."
    )


def get_current_status():
    orderbook = pyupbit.get_orderbook(ticker="KRW-BTC")
    current_time = orderbook["timestamp"]
    btc_balance = 0
    krw_balance = 0
    btc_avg_buy_price = 0
    balances = upbit.get_balances()
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

    return json.dumps(combined_data)


def get_news_data():
    ### Get news data from SERPAPI

    url = f"https://serpapi.com/search.json?engine=google_news&q=btc&api_key={os.getenv('SERPAPI_API_KEY')}"
    result = "No news data available."

    try:
        response = requests.get(url)
        news_results = response.json()["news_results"]

        simplified_news = []

        for news_item in news_results:
            # Check if this news item contains 'stories'
            if "stories" in news_item:
                for story in news_item["stories"]:
                    timestamp = int(
                        datetime.strptime(
                            story["date"], "%m/%d/%Y, %H:%M %p, %z %Z"
                        ).timestamp()
                        * 1000
                    )
                    simplified_news.append(
                        (
                            story["title"],
                            story.get("source", {}).get("name", "Unknown source"),
                            timestamp,
                        )
                    )
            else:
                # Process news items that are not categorized under stories but check date first
                if news_item.get("date"):
                    timestamp = int(
                        datetime.strptime(
                            news_item["date"], "%m/%d/%Y, %H:%M %p, %z %Z"
                        ).timestamp()
                        * 1000
                    )
                    simplified_news.append(
                        (
                            news_item["title"],
                            news_item.get("source", {}).get("name", "Unknown source"),
                            timestamp,
                        )
                    )
                else:
                    simplified_news.append(
                        (
                            news_item["title"],
                            news_item.get("source", {}).get("name", "Unknown source"),
                            "No timestamp provided",
                        )
                    )
        result = str(simplified_news)
    except Exception as e:
        send_slack_message(f"Error fetching news data: {e}")

    return result


def fetch_fear_and_greed_index(limit=1, date_format=""):
    """
    Fetches the latest Fear and Greed Index data.
    Parameters:
    - limit (int): Number of results to return. Default is 1.
    - date_format (str): Date format ('us', 'cn', 'kr', 'world'). Default is '' (unixtime).
    Returns:
    - dict or str: The Fear and Greed Index data in the specified format.
    """
    base_url = "https://api.alternative.me/fng/"
    params = {"limit": limit, "format": "json", "date_format": date_format}
    try:
        response = requests.get(base_url, params=params)
        return "".join(map(str, response.json().get("data", [])))
    except Exception as e:
        send_slack_message(f"Error fetching Fear and Greed Index: {e}")
        return ""


def get_instructions(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        send_slack_message("File not found.")
    except Exception as e:
        send_slack_message(f"An error occurred while reading the file: {e}")


def analyze_data_with_gpt4(
    news_data, data_json, last_decisions, fear_and_greed, current_status
):
    instructions_path = "instructions.md"
    try:
        instructions = get_instructions(instructions_path)
        if not instructions:
            send_slack_message("No instructions found.")
            return None

        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": news_data},
                {"role": "user", "content": data_json},
                {"role": "user", "content": last_decisions},
                {"role": "user", "content": fear_and_greed},
                {"role": "user", "content": current_status},
            ],
            response_format={"type": "json_object"},
        )
        advice = response.choices[0].message.content
        return advice
    except Exception as e:
        send_slack_message(f"Error in analyzing data with GPT-4: {e}")
        return None


def execute_buy(percentage):
    print("Attempting to buy BTC with a percentage of KRW balance...")
    try:
        krw_balance = upbit.get_balance("KRW")
        amount_to_invest = krw_balance * (percentage / 100)
        if amount_to_invest > 5000:  # Ensure the order is above the minimum threshold
            result = upbit.buy_market_order(
                "KRW-BTC", amount_to_invest * 0.9995
            )  # Adjust for fees
            send_slack_message("Buy order successful:", result)
    except Exception as e:
        send_slack_message(f"Failed to execute buy order: {e}")


def execute_sell(percentage):
    print("Attempting to sell a percentage of BTC...")
    try:
        btc_balance = upbit.get_balance("BTC")
        amount_to_sell = btc_balance * (percentage / 100)
        current_price = pyupbit.get_orderbook(ticker="KRW-BTC")["orderbook_units"][0][
            "ask_price"
        ]
        if (
            current_price * amount_to_sell > 5000
        ):  # Ensure the order is above the minimum threshold
            result = upbit.sell_market_order("KRW-BTC", amount_to_sell)
            send_slack_message("Sell order successful:", result)
    except Exception as e:
        send_slack_message(f"Failed to execute sell order: {e}")


def make_decision_and_execute():
    print("Making decision and executing...")
    try:
        news_data = get_news_data()
        data_json = fetch_and_prepare_data()
        last_decisions = fetch_last_decisions()
        fear_and_greed = fetch_fear_and_greed_index(limit=30)
        current_status = get_current_status()
    except Exception as e:
        send_slack_message(f"Error: {e}")
        return

    max_retries = 5
    retry_delay_seconds = 5
    decision = None
    for attempt in range(max_retries):
        try:
            advice = analyze_data_with_gpt4(
                news_data, data_json, last_decisions, fear_and_greed, current_status
            )
            decision = json.loads(advice)
            break
        except json.JSONDecodeError as e:
            send_slack_message(
                f"JSON parsing failed: {e}. Retrying in {retry_delay_seconds} seconds..."
            )
            time.sleep(retry_delay_seconds)
            send_slack_message(f"Attempt {attempt + 2} of {max_retries}")

    if not decision:
        send_slack_message("Failed to make a decision after maximum retries.")
        return

    try:
        percentage = decision.get("percentage", 100)
        decision_type = decision.get("decision")
        reason = decision.get("reason", "")

        if decision_type == "buy":
            execute_buy(percentage)
            message_text = f"비트코인을 *{percentage}% 매수* 합니다. :moneybag:\n- reason\n```{reason}```"
        elif decision_type == "sell":
            execute_sell(percentage)
            message_text = f"비트코인을 *{percentage}% 매도* 합니다. :money_with_wings:\n- reason\n```{reason}```"
        elif decision_type == "hold":
            message_text = f"비트코인을 *보유* 합니다. :eyes:\n- reason\n```{reason}```"
        else:
            message_text = "No valid decision type provided."

        send_slack_message(message_text)
        save_decision_to_db(decision, current_status)
    except Exception as e:
        send_slack_message(f"Failed to execute the decision or save to DB: {e}")


if __name__ == "__main__":
    send_slack_message(
        f"코인 자동매매 봇을 시작합니다. :bank: UPbit, :gpt: {GPT_MODEL}"
    )
    make_decision_and_execute()
