from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select

from .db import PaperPosition, PaperTrade, make_session
from .config import get_settings
from .binance_client import SimpleBinance


@dataclass
class TradeResult:
    side: str
    qty: float
    price: float
    pnl_usdt: float = 0.0
    note: str = ""


def _calc_qty_usdt(price: float, size_usdt: float) -> float:
    if price <= 0:
        return 0.0
    return round(size_usdt / price, 6)


class PaperBroker:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def market_order(self, symbol: str, side: str, price: float, size_usdt: float) -> TradeResult:
        session = make_session(self.db_path)
        try:
            side = side.upper()
            qty = _calc_qty_usdt(price, size_usdt)

            pos = session.scalar(select(PaperPosition).where(PaperPosition.symbol == symbol))
            if not pos:
                pos = PaperPosition(symbol=symbol, qty=0.0, entry_price=0.0)
                session.add(pos)
                session.flush()

            pnl_usdt = 0.0
            if side == "BUY":
                new_qty = pos.qty + qty
                pos.entry_price = (pos.entry_price * pos.qty + price * qty) / new_qty if new_qty > 0 else 0.0
                pos.qty = new_qty
            else:
                sell_qty = min(qty, pos.qty)
                pnl_usdt = (price - pos.entry_price) * sell_qty
                pos.qty -= sell_qty
                if pos.qty <= 1e-9:
                    pos.qty = 0.0
                    pos.entry_price = 0.0

            trade = PaperTrade(symbol=symbol, side=side, qty=qty, price=price, pnl_usdt=pnl_usdt)
            session.add(trade)
            session.commit()
            return TradeResult(side=side, qty=qty, price=price, pnl_usdt=pnl_usdt)
        finally:
            session.close()


class LiveBroker:
    def __init__(self, futures: bool = False):
        s = get_settings()
        if not s.binance_api_key or not s.binance_api_secret:
            raise RuntimeError("Missing BINANCE_API_KEY/SECRET for live trading")
        self.client = SimpleBinance(s.binance_api_key, s.binance_api_secret, futures=futures)

    def market_order(self, symbol: str, side: str, price: float, size_usdt: float) -> TradeResult:
        qty = _calc_qty_usdt(price, size_usdt)
        resp = self.client.order_market(symbol=symbol, side=side.upper(), quantity=qty)
        executed_price = price
        try:
            if "fills" in resp and resp["fills"]:
                executed_price = float(resp["fills"][0]["price"])  # spot
            elif "avgPrice" in resp:
                executed_price = float(resp["avgPrice"])  # futures
        except Exception:
            pass
        return TradeResult(side=side.upper(), qty=qty, price=executed_price)

