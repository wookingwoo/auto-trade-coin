import pyupbit
import numpy as np


def get_ror(stock_symbol, k=0.5):

    try:

        df = pyupbit.get_ohlcv(stock_symbol, count=7)
        df['range'] = (df['high'] - df['low']) * k
        df['target'] = df['open'] + df['range'].shift(1)

        df['ror'] = np.where(df['high'] > df['target'],
                             df['close'] / df['target'],
                             1)

        ror = df['ror'].cumprod()[-2]
        return ror

    except:
        # print("수익률을 계산할 수 없습니다.")
        return None


def find_optimal_k(stock_symbol):
    # print("[{}의 optimal한 k값을 찾습니다.]".format(stock_symbol))
    max_ror = 0
    max_k = None

    for k in np.arange(0.1, 1.0, 0.1):

        ror = get_ror(stock_symbol, k)

        if not (ror == None):

            # print("k={} -> 수익률: {}%".format(round(k, 1), round((ror-1)*100, 2)))

            if ror > max_ror:
                max_ror = ror
                max_k = round(k, 1)

    if max_k == None:
        print("{}를 계산할 수 없습니다.".format(stock_symbol))
    else:
        print("[optimal case] {} -> k={} -> 수익률: {}%".format(stock_symbol,
                                                             max_k, round((max_ror-1)*100, 2)))

    # print("%.1f -> %f" % (k, ror))
    print()


if __name__ == "__main__":

    symbol_list = ["KRW-BTC", "KRW-ETH", "KRW-DOGE", "KRW-XRP", "KRW-ADA", "KRW-SRM",
                   "KRW-WAXP", "KRW-SAND", "KRW-XTZ", "KRW-ATOM", "KRW-BCHA", "KRW-BSV", "KRW-BTG", "KRW-BCH"]

    for symbol in symbol_list:
        find_optimal_k(symbol)
