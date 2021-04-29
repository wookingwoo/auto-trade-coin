import pyupbit
import data.apiKey

# 로그인
access = data.apiKey.access 
secret = data.apiKey.secret 
upbit = pyupbit.Upbit(access, secret)

# 잔고 조회
print("KRW-BTC:", upbit.get_balance("KRW-BTC")) # KRW - BTC 조회
print("KRW-ETH:", upbit.get_balance("KRW-ETH")) # KRW - ETH 조회
print("KRW-DOGE:", upbit.get_balance("KRW-DOGE")) # KRW - DOGE 조회

print("KRW:", upbit.get_balance("KRW")) # 보유 현금 조회