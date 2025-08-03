import requests
from config import HEADERS


def fetch_candle_data(market, timeframe, count):
    """
    Fetches candle data for a given timeframe and count. (캔들 조회)
    """
    url = (
        f"https://api.bithumb.com/v1/candles/{timeframe}?market={market}&count={count}"
    )
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()


def fetch_recent_trades(market, count):
    """
    Fetches recent trade data for the specified market. (최근 체결 내역)
    """
    url = f"https://api.bithumb.com/v1/trades/ticks?market={market}&count={count}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()


def fetch_ticker(market):
    """
    Fetches the current ticker data for the specified market. (현재가 조회)
    """
    url = f"https://api.bithumb.com/v1/ticker?markets={market}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()


def fetch_orderbook(market):
    """
    Fetches the orderbook data for the specified market. (호가 정보 조회)
    """
    url = f"https://api.bithumb.com/v1/orderbook?markets={market}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return response.json()
