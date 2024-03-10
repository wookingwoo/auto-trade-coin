import pyupbit
import data.apiKey


# 로그인
access = data.apiKey.upbit_access
secret = data.apiKey.upbit_secret
upbit = pyupbit.Upbit(access, secret)

# 잔고 조회
print("KRW-BTC:", upbit.get_balance("KRW-BTC"))  # KRW - BTC 조회
print("BTC:", upbit.get_balance("BTC"))  # BTC 조회
print("KRW-ETH:", upbit.get_balance("KRW-ETH"))  # KRW - ETH 조회
print("KRW-DOGE:", upbit.get_balance("KRW-DOGE"))  # KRW - DOGE 조회
print("KRW:", upbit.get_balance("KRW"))  # 보유 현금 조회


print()

print("전체 잔고 조회:", upbit.get_balances())  # 전체 잔고 조회
