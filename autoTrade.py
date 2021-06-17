import time
import pyupbit
import datetime
import schedule
import requests
from fbprophet import Prophet

import data.apiKey
import data.coin_option
from write_log import *


# upbit API Keys
upbit_access = data.apiKey.upbit_access
upbit_secret = data.apiKey.upbit_secret

# slack API Keys
slack_token = data.apiKey.slack_token
slack_channel = data.apiKey.slack_channel

K = data.coin_option.option_FLUCTUATION  # 상수 K 값 (범위: 0~1)


def post_message(text, setDatetime=True):

    token = slack_token
    channel = slack_channel

    if setDatetime:
        logMSG = datetime.datetime.now().strftime(
            '[%Y/%m/%d %H:%M:%S] ') + text  # 시간 추가
    else:
        logMSG = text
    print(logMSG)  # 콘솔 출력
    response = requests.post("https://slack.com/api/chat.postMessage",
                             headers={"Authorization": "Bearer "+token},
                             data={"channel": channel, "text": logMSG}
                             )  # 슬랙 메시지 전송
    write_all_log(logMSG)  # 로그 데이터 기록


# 변동성 돌파 전략으로 매수 목표가 조회
def get_target_price(ticker, k):
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    target_price = df.iloc[0]['close'] + \
        (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price


# 시작 시간 조회
def get_start_time(ticker):
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time


# 잔고 조회
def get_balance(ticker):
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0


# 현재가 조회
def get_current_price(ticker):
    return pyupbit.get_orderbook(tickers=ticker)[0]["orderbook_units"][0]["ask_price"]


# 15일 이동 평균선 조회
def get_ma15(ticker):
    df = pyupbit.get_ohlcv(ticker, interval="day", count=15)
    ma15 = df['close'].rolling(15).mean().iloc[-1]
    return ma15


predicted_close_price = 0


# Prophet으로 당일 종가 가격 예측
def predict_price(ticker):
    post_message(
        "Prophet로 종가 가격을 다시 예측합니다. (1시간을 주기로 업데이트)")

    global predicted_close_price
    df = pyupbit.get_ohlcv(ticker, interval="minute60")
    df = df.reset_index()
    df['ds'] = df['index']
    df['y'] = df['close']
    data = df[['ds', 'y']]
    model = Prophet()
    model.fit(data)
    future = model.make_future_dataframe(periods=24, freq='H')
    forecast = model.predict(future)
    closeDf = forecast[forecast['ds'] ==
                       forecast.iloc[-1]['ds'].replace(hour=9)]
    if len(closeDf) == 0:
        closeDf = forecast[forecast['ds'] ==
                           data.iloc[-1]['ds'].replace(hour=9)]
    closeValue = closeDf['yhat'].values[0]
    predicted_close_price = closeValue


post_message(
    "\n====================================================", False)
post_message("프로그램을 시작합니다.")


predict_price("KRW-BTC")
schedule.every().hour.do(lambda: predict_price("KRW-BTC"))  # 1시간마다 실행

post_message("로그인을 합니다.")

# 로그인
upbit = pyupbit.Upbit(upbit_access, upbit_secret)

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC")
        end_time = start_time + datetime.timedelta(days=1)
        schedule.run_pending()

        # 09시와 다음날 08시59분50초 사이일때
        if start_time < now < end_time - datetime.timedelta(seconds=10):
            # post_message(myToken, "#crypto", "target_price, ma15, current_price를 다시 계산합니다.")
            print("target_price, ma15, current_price를 다시 계산합니다.")
            target_price = get_target_price("KRW-BTC", K)
            ma15 = get_ma15("KRW-BTC")
            current_price = get_current_price("KRW-BTC")

            # 변동성 돌파전략, 15일 이동 평균선, Prophet 종가 예측 적용
            if target_price < current_price and ma15 < current_price and current_price < predicted_close_price:
                post_message("매수 조건에 만족합니다.")
                krw = get_balance("KRW")
                if krw > 5000:
                    buy_result = upbit.buy_market_order(
                        "KRW-BTC", krw*0.9995)  # 수수료 (0.05%) 제외
                    post_message("BTC buy : " + str(buy_result))

    # 08시59분50초 ~ 09시 00분 00초 (전량 매도)
        else:
            post_message("매도 시간입니다.")
            btc = get_balance("BTC")
            if btc > 0.00008:
                sell_result = upbit.sell_market_order(
                    "KRW-BTC", btc*0.9995)  # 수수료 (0.05%) 제외
                post_message(
                    "전량 매도 (수수료 0.05% 제외) : " + str(sell_result))

        time.sleep(1)
    except Exception as e:
        post_message("[에러가 발생했습니다]\n에러 메시지: " + str(e))
        time.sleep(60*3)
