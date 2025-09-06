from __future__ import annotations

import argparse
import time
from datetime import datetime

import pandas as pd
from sqlalchemy import select

from .config import get_settings
from .db import init_db, make_session, Candle, Signal
from .data_collector import upsert_candles
from .binance_client import SimpleBinance
from .features import add_indicators
from .strategy_llm import llm_decide
from .trader import PaperBroker, LiveBroker


def _load_recent_candles(n: int = 200) -> pd.DataFrame:
    s = get_settings()
    session = make_session(s.db_path)
    try:
        rows = (
            session.execute(
                select(Candle)
                .where((Candle.symbol == s.symbol) & (Candle.interval == s.interval))
                .order_by(Candle.open_time.desc())
                .limit(n)
            )
            .scalars()
            .all()
        )
        rows = list(reversed(rows))
        df = pd.DataFrame(
            [
                {
                    "open_time": r.open_time,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in rows
            ]
        )
        return add_indicators(df)
    finally:
        session.close()


def _risk_budget_usdt() -> float:
    s = get_settings()
    return s.base_balance_usdt * s.risk_per_trade


def _price_now() -> float:
    s = get_settings()
    client = SimpleBinance(futures=(s.market == "futures"))
    return client.ticker_price(s.symbol)


def loop_once() -> None:
    s = get_settings()
    inserted = upsert_candles()
    df = _load_recent_candles(200)
    budget = _risk_budget_usdt()
    decision = llm_decide(df, budget)

    session = make_session(s.db_path)
    try:
        sig = Signal(
            symbol=s.symbol,
            interval=s.interval,
            action=decision["action"],
            confidence=decision.get("confidence", 0.5),
            reason=decision.get("reason", ""),
            size_usdt=float(decision.get("size_usdt", 0.0)),
        )
        session.add(sig)
        session.commit()
    finally:
        session.close()

    action = decision["action"].upper()
    if action == "HOLD" or decision.get("size_usdt", 0.0) <= 0:
        return

    price = _price_now()
    broker = (
        LiveBroker(futures=(s.market == "futures")) if s.mode == "live" else PaperBroker(s.db_path)
    )

    if action in ("BUY", "LONG"):
        broker.market_order(s.symbol, "BUY", price, decision["size_usdt"])
    elif action in ("SELL", "SHORT"):
        broker.market_order(s.symbol, "SELL", price, decision["size_usdt"])


def main():
    parser = argparse.ArgumentParser(description="ATC Binance LLM Trader")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("init", help="Initialize database")
    sub.add_parser("collect", help="Collect recent candles once")
    runp = sub.add_parser("run", help="Run continuous loop")
    runp.add_argument("--interval-seconds", type=int, default=60)

    args = parser.parse_args()
    s = get_settings()

    if args.cmd == "init":
        init_db(s.db_path)
        print(f"DB initialized at {s.db_path}")
        return
    if args.cmd == "collect":
        init_db(s.db_path)
        inserted = upsert_candles()
        print(f"Inserted {inserted} candles")
        return
    if args.cmd == "run":
        init_db(s.db_path)
        print(
            f"Running loop mode={s.mode} market={s.market} symbol={s.symbol} interval={s.interval} every {args.interval_seconds}s"
        )
        while True:
            try:
                loop_once()
            except Exception as e:
                print("Error in loop:", e)
            time.sleep(args.interval_seconds)
        return
    parser.print_help()


if __name__ == "__main__":
    main()

