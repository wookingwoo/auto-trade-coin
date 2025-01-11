from trade_USDT import (
    fetch_candle_data,
    fetch_recent_trades,
    fetch_ticker,
    fetch_orderbook,
)

data_count = 1


def main():
    # Example usage
    minute_candle_data = fetch_candle_data("minutes/60", data_count)
    print("Minute Candle Data:", minute_candle_data)

    day_candle_data = fetch_candle_data("days", data_count)
    print("Day Candle Data:", day_candle_data)

    week_candle_data = fetch_candle_data("weeks", data_count)
    print("Week Candle Data:", week_candle_data)

    month_candle_data = fetch_candle_data("months", data_count)
    print("Month Candle Data:", month_candle_data)

    tick_data = fetch_recent_trades(data_count)
    print("Tick Data:", tick_data)

    ticker_data = fetch_ticker()
    print("Ticker Data:", ticker_data)

    orderbook_data = fetch_orderbook()
    print("Orderbook Data:", orderbook_data)


if __name__ == "__main__":
    main()
