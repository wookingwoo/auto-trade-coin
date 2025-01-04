import streamlit as st
import pandas as pd
from datetime import datetime
import pyupbit
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import plotly.graph_objects as go

# Load environment variables
load_dotenv()


def load_data():
    MONGO_URI = os.getenv("MONGO_URI")
    client = MongoClient(MONGO_URI)
    db = client["autoTradeCoin"]
    decisions_collection = db["decisions"]

    decisions = list(decisions_collection.find().sort("timestamp", -1))
    df = pd.DataFrame(decisions)

    # Ensure the DataFrame has the correct columns
    df = df[
        [
            "timestamp",
            "ai_model",
            "decision",
            "percentage",
            "reason",
            "btc_balance",
            "krw_balance",
            "btc_avg_buy_price",
            "btc_krw_price",
        ]
    ]

    return df


def calculate_profit(current_price, btc_balance, krw_balance, start_value):
    current_value = int(btc_balance * current_price + krw_balance)
    profit_rate = round((current_value - start_value) / start_value * 100, 2)
    return current_value, profit_rate


def format_time_diff(timestamp):
    time_diff = datetime.now() - pd.to_datetime(timestamp)
    days, seconds = time_diff.days, time_diff.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{days}일 {hours}시간 {minutes}분"


def main():
    st.set_page_config(layout="wide")
    st.title("wookingwoo Auto Trading Dashboard")
    st.write("- [GitHub](https://github.com/wookingwoo/auto-trade-coin)")
    st.write("---")

    df = load_data()
    if df.empty:
        st.warning("데이터가 존재하지 않습니다.")
        return

    # 초기 투자 금액 및 현재 비트코인 가격
    start_value = 883000
    current_price = pyupbit.get_current_price("KRW-BTC")

    # 가장 최근 데이터
    latest_row = df.iloc[0]  # 가장 최신 데이터를 가져옴
    btc_balance = latest_row["btc_balance"]
    krw_balance = latest_row["krw_balance"]
    btc_avg_buy_price = latest_row["btc_avg_buy_price"]

    # 수익률 및 현재 가치 계산
    current_value, profit_rate = calculate_profit(
        current_price, btc_balance, krw_balance, start_value
    )
    time_diff_str = format_time_diff(df.iloc[-1]["timestamp"])

    # UI 표시
    st.header(f"수익률: {profit_rate}%")
    st.write(f"현재 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
    st.write("투자기간:", time_diff_str)
    st.write("시작 원금:", f"{start_value:,}원")
    st.write("현재 비트코인 가격:", f"{round(current_price):,}원")
    st.write("현재 보유 현금:", f"{round(krw_balance):,}원")
    st.write("현재 보유 비트코인:", f"{btc_balance} BTC")
    st.write("BTC 매수 평균가격:", f"{round(btc_avg_buy_price):,}원")
    st.write("현재 원화 가치 평가:", f"{current_value:,}원")

    # 수익률 그래프 추가
    df["profit_rate"] = (
        ((df["btc_balance"] * current_price + df["krw_balance"]) - start_value)
        / start_value
        * 100
    )
    st.line_chart(df[["timestamp", "profit_rate"]].set_index("timestamp"))

    # Add a Plotly graph for Bitcoin price with buy/sell markers
    fig = go.Figure()

    # Add line for Bitcoin price
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"], y=df["btc_krw_price"], mode="lines", name="BTC Price"
        )
    )

    # Add markers for buy/sell decisions
    buy_decisions = df[df["decision"] == "buy"]
    sell_decisions = df[df["decision"] == "sell"]

    fig.add_trace(
        go.Scatter(
            x=buy_decisions["timestamp"],
            y=buy_decisions["btc_krw_price"],
            mode="markers",
            name="Buy",
            marker=dict(color="green", size=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sell_decisions["timestamp"],
            y=sell_decisions["btc_krw_price"],
            mode="markers",
            name="Sell",
            marker=dict(color="red", size=3),
        )
    )

    fig.update_layout(
        title="Bitcoin Price with Buy/Sell Decisions",
        xaxis_title="Time",
        yaxis_title="Price (KRW)",
    )

    st.plotly_chart(fig)

    # 데이터프레임 출력
    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
