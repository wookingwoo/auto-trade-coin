import pyupbit
import numpy as np


def get_ror(k=0.5):

    # 코인 종목
    # stock_symbol = "KRW-BTC"
    stock_symbol = "KRW-ETH"
    # stock_symbol =  "KRW-DOGE"


    df = pyupbit.get_ohlcv(stock_symbol, count=7)
    df['range'] = (df['high'] - df['low']) * k
    df['target'] = df['open'] + df['range'].shift(1)

    df['ror'] = np.where(df['high'] > df['target'],
                         df['close'] / df['target'],
                         1)

    ror = df['ror'].cumprod()[-2]
    return ror


print("optimal한 k값을 찾습니다.")
for k in np.arange(0.1, 1.0, 0.1):
    ror = get_ror(k)
    print("%.1f %f" % (k, ror))
