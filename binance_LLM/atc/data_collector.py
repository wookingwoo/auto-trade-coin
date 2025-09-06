from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import select

from .binance_client import SimpleBinance
from .config import get_settings
from .db import Candle, make_session
from .features import candles_to_df


def upsert_candles() -> int:
    s = get_settings()
    client = SimpleBinance(futures=(s.market == "futures"))
    raw = client.klines(s.symbol, s.interval, limit=500)
    df = candles_to_df(raw)
    session = make_session(s.db_path)
    inserted = 0
    try:
        for _, row in df.iterrows():
            exists = session.scalar(
                select(Candle).where(
                    (Candle.symbol == s.symbol)
                    & (Candle.interval == s.interval)
                    & (Candle.open_time == row["open_time"].to_pydatetime())
                )
            )
            if exists:
                continue
            session.add(
                Candle(
                    symbol=s.symbol,
                    interval=s.interval,
                    open_time=row["open_time"].to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
            inserted += 1
        session.commit()
        return inserted
    finally:
        session.close()

