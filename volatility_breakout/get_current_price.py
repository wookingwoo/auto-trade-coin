import pandas as pd
import pyupbit

print(pyupbit.Upbit)
print()


# # 모든 종목 코드 확인
print("모든 종목 코드 확인")
tickers = pyupbit.get_tickers()
print(tickers)
print()


# # KRW로 표기된 종목의 코드 확인
print("KRW로 표기된 종목의 코드 확인")
tickers = pyupbit.get_tickers(fiat="KRW")
print(tickers)
print()

# 개별 가격 조회
print("개별 가격 조회")
price_KRW = pyupbit.get_current_price(
    ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-DOGE"])
print("BTC : {0:>10,} 원".format(int(price_KRW["KRW-BTC"])))  # 딕셔너리 type
print("ETH : {0:>10,} 원".format(int(price_KRW["KRW-ETH"])))
print("XRP : {0:>10,} 원".format(int(price_KRW["KRW-XRP"])))
print("DOGE : {0:>9,} 원".format(int(price_KRW["KRW-DOGE"])))


print()

# 아래와 같이 BTC로도 가격 조회가 가능함
print("BTC로 가격 조회")
price_BTC = pyupbit.get_current_price("BTC-ETH")
print("ETH : {} BTC\n".format(price_BTC))


# 참고 표준 출력 : https://wikidocs.net/20403
