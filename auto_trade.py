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

# trade option
option_symbol_list = data.coin_option.option_symbol_list  # 매수할 종목들
option_target_buy_count = data.coin_option.option_target_buy_count  # 매수할 종목 수
option_buy_percent = data.coin_option.option_buy_percent  # 총 주문 금액 비율
K = data.coin_option.option_FLUCTUATION  # K값 (범위: 0~1)


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
                             headers={"Authorization": "Bearer " + token},
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


predicted_close_price = {}


# Prophet으로 당일 종가 가격 예측
def predict_price(ticker):
    print("Prophet로 {}의 종가 가격을 다시 예측합니다. (1시간을 주기로 업데이트)".format(ticker))

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
    predicted_close_price[ticker] = closeValue
    print("{}의 종가 예측 결과: {}".format(ticker, closeValue))
    print()

    arrow_emoji = ""

    if closeValue > get_current_price(ticker):
        arrow_emoji = "🔺"

    elif closeValue < get_current_price(ticker):
        arrow_emoji = "⬇"

    elif closeValue == get_current_price(ticker):
        arrow_emoji = "◾"

    predict_rate_of_return = round(
        closeValue / get_current_price(ticker) * 100 - 100, 2)  # 예상 수익률

    return_msg = "{}: {} {}원 ({}%)".format(
        ticker, arrow_emoji, format(round(closeValue, 2), ","), predict_rate_of_return)

    return return_msg


def run_symbollist_predict_price(symbol_list):
    predict_msg = "<Prophet 종가 예측>\n"

    for sym in symbol_list:
        predict_msg += predict_price(sym)
        predict_msg += "\n"

    post_message(predict_msg)


def setting_msg_post():
    global option_symbol_list, option_target_buy_count, option_buy_percent, K, bought_list
    post_message("<자동화 세팅값>\n매수할 종목 후보({}개): {}\n매수할 종목 수: {}\n주문 금액 비율: {}\nK값 (범위:0~1): {}\n매수 완료한 종목: {}\n".format(
        len(option_symbol_list), option_symbol_list, option_target_buy_count, option_buy_percent, K, bought_list))


# == main program ==

minimum_order_amount = 5000  # 최소 주문 금액 (상수)
FEE = 0.05 / 100   # 수수료 0.05% (상수)

bought_list = []  # 매수 완료된 종목 리스트 초기화

post_message(
    "\n====================================================", False)
post_message("프로그램을 시작합니다.")
setting_msg_post()

run_symbollist_predict_price(option_symbol_list)
schedule.every().hour.do(lambda: run_symbollist_predict_price(
    option_symbol_list))  # 1시간마다 실행

post_message("upbit api에 access 합니다.")

# 로그인
upbit = pyupbit.Upbit(upbit_access, upbit_secret)


buy_amount = get_balance("KRW") * option_buy_percent * \
    (1-FEE)  # 종목별 주문할 금액 [한화] (수수료 0.05% 제외)

# 자동매매 시작
while True:
    try:

        for code in option_symbol_list:

            now = datetime.datetime.now()
            start_time = get_start_time(code)  # 대부분 오전 9시
            end_time = start_time + \
                datetime.timedelta(days=1)  # 대부분 오전 9시 + 1일
            schedule.run_pending()

            # 09시와 다음날 08시50분00초 사이일때
            if start_time < now < end_time - datetime.timedelta(seconds=60*10):
                print("{}의 target_price, ma15, current_price를 다시 계산합니다.".format(code))
                target_price = get_target_price(code, K)
                ma15 = get_ma15(code)
                current_price = get_current_price(code)

                # 변동성 돌파전략, 15일 이동 평균선, Prophet 종가 예측(+1% 이상) 적용
                if target_price < current_price and ma15 < current_price and (predicted_close_price[code] / current_price * 100 - 100) >= 1:
                    print("{}가 매수 조건에 만족합니다.".format(code))
                    krw = get_balance("KRW")
                    if krw > minimum_order_amount:

                        if buy_amount > minimum_order_amount:

                            if len(bought_list) < option_target_buy_count:

                                if not (code in bought_list):

                                    buy_result = upbit.buy_market_order(
                                        code, buy_amount)  # 매수

                                    bought_list.append(code)
                                    post_message("`{} 매수 완료!!` : {}".format(
                                        code, str(buy_result)))

                                    setting_msg_post()

                                else:
                                    print(
                                        "{}는 이미 매수한 종목이므로 pass합니다.".format(code))

                            else:
                                print("{}개의 종목을 모두 매수 했기 때문에 pass합니다.".format(
                                    option_target_buy_count))
                        else:
                            print("종목별 주문할 금액이 {}원 미만이기 때문에 {}를 메수하지 않습니다. (종목별 주문할 금액: {}원)".format(
                                minimum_order_amount,   code, buy_amount))

                    else:
                        print(
                            "잔고가 {}원 미만이기 때문에 {}를 메수하지 않습니다. (잔고: {}원)".format(minimum_order_amount, code, krw))

            # 08시50분00초 ~ 09시 00분 00초 (전량 매도)
            else:
                print("매도 시간입니다.")

                coin_balance = get_balance(code[4:])  # 보유한 코인 금액 (코인 단위)
                price_KRW = pyupbit.get_current_price([code])
                current_krw_price = int(price_KRW[code])

                my_coin_balance_krw = coin_balance * \
                    current_krw_price  # 보유한 코인 평가금액 (원화 단위)
                print("my_coin_balance_krw:", my_coin_balance_krw)

                if my_coin_balance_krw > minimum_order_amount * 1.05:
                    sell_result = upbit.sell_market_order(
                        code, coin_balance * (1-FEE))  # 수수료 (0.05%) 제외
                    post_message("`전량 매도 (수수료 {}% 제외) : {}`".format(
                        (1-FEE)*100, str(sell_result)))

            time.sleep(1)
    except Exception as e:
        post_message("[에러가 발생했습니다]\n에러 메시지: " + str(e))
        time.sleep(60 * 3)
