import streamlit as st
import pandas as pd
from datetime import datetime
import pyupbit
from pymongo import MongoClient
import os
from dotenv import load_dotenv

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


def main():
    st.set_page_config(layout="wide")
    st.title("wookingwoo Auto Trading Dashboard")
    st.write("- [GitHub](https://github.com/wookingwoo/auto-trade-coin)")
    st.write("---")

    df = load_data()

    if df.empty:
        st.warning("데이터가 존재하지 않습니다.")
        return

    # 초기 투자 금액
    start_value = 883000

    current_price = pyupbit.get_current_price("KRW-BTC")

    # 가장 최근 row
    latest_row = df.iloc[1]
    btc_balance = latest_row["btc_balance"]
    krw_balance = latest_row["krw_balance"]
    btc_avg_buy_price = latest_row["btc_avg_buy_price"]

    # 현재 자산 가치 계산
    current_value = int(btc_balance * current_price + krw_balance)

    # 투자 기간 계산
    time_diff = datetime.now() - pd.to_datetime(latest_row["timestamp"])
    days = time_diff.days
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    time_diff_str = f"{days}일 {hours}시간 {minutes}분"

    # 수익률
    profit_rate = round((current_value - start_value) / start_value * 100, 2)

    # UI에 표시
    st.header(f"수익률: {profit_rate}%")
    st.write(f"현재 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
    st.write("투자기간:", time_diff_str)
    st.write("시작 원금:", f"{start_value:,}원")
    st.write("현재 비트코인 가격:", f"{round(current_price):,}원")
    st.write("현재 보유 현금:", f"{round(krw_balance):,}원")
    st.write("현재 보유 비트코인:", f"{btc_balance}BTC")
    st.write("BTC 매수 평균가격:", f"{round(btc_avg_buy_price):,}원")
    st.write("현재 원화 가치 평가:", f"{current_value:,}원")

    # 데이터프레임 출력
    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
