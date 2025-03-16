import requests
from config import MARKET, HEADERS


def fetch_candle_data(timeframe, count):
    """
    Fetches candle data for a given timeframe and count. (캔들 조회)
    """
    url = (
        f"https://api.bithumb.com/v1/candles/{timeframe}?market={MARKET}&count={count}"
    )
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()


def fetch_recent_trades(count):
    """
    Fetches recent trade data for the specified market. (최근 체결 내역)
    """
    url = f"https://api.bithumb.com/v1/trades/ticks?market={MARKET}&count={count}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()


def fetch_ticker():
    """
    Fetches the current ticker data for the specified market. (현재가 조회)
    """
    url = f"https://api.bithumb.com/v1/ticker?markets={MARKET}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()


def fetch_orderbook():
    """
    Fetches the orderbook data for the specified market. (호가 정보 조회)
    """
    url = f"https://api.bithumb.com/v1/orderbook?markets={MARKET}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()
