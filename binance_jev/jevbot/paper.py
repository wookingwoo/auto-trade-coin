from __future__ import annotations

import json
import threading
from decimal import Decimal
from pathlib import Path

from .binance import BinanceError
from .domain import decimal_text
from .store import Journal


class PaperFutures:
    """Persistent paper ledger using live public Binance market data."""

    def __init__(self, public, path: str | Path, starting_usdt: Decimal) -> None:
        if starting_usdt <= 0:
            raise ValueError("paper starting balance must be positive")
        self.public = public
        self.path = Path(path)
        self.lock = threading.RLock()
        journal = Journal(self.path)
        try:
            if journal.get("paper_wallet") is None:
                journal.set("paper_wallet", starting_usdt)
            if journal.get("paper_position") is None:
                journal.set("paper_position", "")
            if journal.get("paper_algos") is None:
                journal.set("paper_algos", "[]")
            if journal.get("paper_orders") is None:
                journal.set("paper_orders", "{}")
        finally:
            journal.close()

    def __getattr__(self, name: str):
        return getattr(self.public, name)

    def _read(self, key: str) -> str | None:
        journal = Journal(self.path)
        try:
            return journal.get(key)
        finally:
            journal.close()

    def _write(self, values: dict[str, object]) -> None:
        journal = Journal(self.path)
        try:
            journal.db.execute("BEGIN IMMEDIATE")
            try:
                for key, value in values.items():
                    journal.set(key, value)
                journal.db.execute("COMMIT")
            except Exception:
                journal.db.execute("ROLLBACK")
                raise
        finally:
            journal.close()

    def get_position_mode(self) -> dict:
        return {"dualSidePosition": False}

    def get_account_config(self) -> dict:
        return {"canTrade": True}

    def get_multi_asset_mode(self) -> dict:
        return {"multiAssetsMargin": False}

    def get_symbol_config(self, symbol: str) -> dict:
        return {"symbol": symbol, "marginType": "ISOLATED", "leverage": 2}

    def get_commission(self, symbol: str) -> dict:
        return {"symbol": symbol, "takerCommissionRate": "0.0005"}

    def get_positions(self) -> list[dict]:
        with self.lock:
            raw = self._read("paper_position")
            return [json.loads(raw)] if raw else []

    def get_account(self) -> dict:
        with self.lock:
            wallet = Decimal(self._read("paper_wallet"))
            position = self.get_positions()
            unrealized = Decimal("0")
            margin = Decimal("0")
            if position:
                item = position[0]
                quantity = Decimal(item["positionAmt"])
                entry = Decimal(item["entryPrice"])
                mark = Decimal(str(self.public.get_mark(item["symbol"])["markPrice"]))
                unrealized = quantity * (mark - entry)
                margin = abs(quantity) * entry / 2
            return {
                "canTrade": True,
                "totalWalletBalance": decimal_text(wallet),
                "totalUnrealizedProfit": decimal_text(unrealized),
                "totalMarginBalance": decimal_text(wallet + unrealized),
                "availableBalance": decimal_text(wallet - margin),
            }

    def open_orders(self, symbol: str) -> list[dict]:
        return []

    def open_algo_orders(self, symbol: str) -> list[dict]:
        with self.lock:
            return [item for item in json.loads(self._read("paper_algos")) if item["symbol"] == symbol]

    def query_order(self, symbol: str, client_id: str) -> dict:
        with self.lock:
            orders = json.loads(self._read("paper_orders"))
            if client_id not in orders:
                raise BinanceError("paper order not found")
            return orders[client_id]

    def query_algo(self, client_id: str) -> dict:
        with self.lock:
            for item in json.loads(self._read("paper_algos")):
                if item["clientAlgoId"] == client_id:
                    return item
            raise BinanceError("paper algo not found")

    def place_ioc(self, symbol: str, side: str, quantity: Decimal, price: Decimal, client_id: str) -> dict:
        with self.lock:
            existing = json.loads(self._read("paper_orders"))
            if client_id in existing:
                raise BinanceError("duplicate paper order")
            if self.get_positions():
                raise BinanceError("paper position already open")
            bid, ask, _ = self.public.get_book(symbol)
            crosses = price >= ask if side == "BUY" else price <= bid
            if not crosses:
                order = {"status": "EXPIRED", "executedQty": "0", "clientOrderId": client_id}
                existing[client_id] = order
                self._write({"paper_orders": json.dumps(existing)})
                return order
            signed = quantity if side == "BUY" else -quantity
            fill_price = price  # pessimistic fill at the allowed IOC limit
            fee = quantity * fill_price * Decimal("0.0005")
            wallet = Decimal(self._read("paper_wallet")) - fee
            position = {"symbol": symbol, "positionAmt": decimal_text(signed), "entryPrice": decimal_text(fill_price), "positionSide": "BOTH"}
            order = {"status": "FILLED", "executedQty": decimal_text(quantity), "avgPrice": decimal_text(fill_price), "clientOrderId": client_id}
            existing[client_id] = order
            self._write({"paper_wallet": wallet, "paper_position": json.dumps(position), "paper_orders": json.dumps(existing)})
            return order

    def place_close_algo(self, symbol: str, side: str, order_type: str, trigger_price: Decimal, client_id: str) -> dict:
        with self.lock:
            orders = json.loads(self._read("paper_algos"))
            if any(item["clientAlgoId"] == client_id for item in orders):
                raise BinanceError("duplicate paper algo")
            order = {"symbol": symbol, "side": side, "orderType": order_type, "triggerPrice": decimal_text(trigger_price), "clientAlgoId": client_id}
            orders.append(order)
            self._write({"paper_algos": json.dumps(orders)})
            return order

    def place_reduce_market(self, symbol: str, side: str, quantity: Decimal, client_id: str, worst_price: Decimal | None = None) -> dict:
        with self.lock:
            orders = json.loads(self._read("paper_orders"))
            if client_id in orders:
                raise BinanceError("duplicate paper exit")
            position = self.get_positions()
            if not position or position[0]["symbol"] != symbol:
                raise BinanceError("no paper position")
            amount = Decimal(position[0]["positionAmt"])
            if quantity != abs(amount) or side != ("SELL" if amount > 0 else "BUY"):
                raise BinanceError("paper exit must reduce the entire position")
            bid, ask, _ = self.public.get_book(symbol)
            exit_price = bid if side == "SELL" else ask
            if worst_price is not None:
                exit_price = min(exit_price, worst_price) if side == "SELL" else max(exit_price, worst_price)
            pnl = amount * (exit_price - Decimal(position[0]["entryPrice"]))
            fee = quantity * exit_price * Decimal("0.0005")
            wallet = Decimal(self._read("paper_wallet")) + pnl - fee
            order = {"status": "FILLED", "executedQty": decimal_text(quantity), "avgPrice": decimal_text(exit_price), "clientOrderId": client_id}
            orders[client_id] = order
            self._write({"paper_wallet": wallet, "paper_position": "", "paper_orders": json.dumps(orders)})
            return order

    def place_reduce_ioc(self, symbol: str, side: str, quantity: Decimal, price: Decimal, client_id: str) -> dict:
        bid, ask, _ = self.public.get_book(symbol)
        if (side == "SELL" and price > bid) or (side == "BUY" and price < ask):
            raise BinanceError("paper reduce-only IOC did not cross book")
        return self.place_reduce_market(symbol, side, quantity, client_id, price)

    def cancel_algo(self, client_id: str) -> dict:
        with self.lock:
            orders = json.loads(self._read("paper_algos"))
            self._write({"paper_algos": json.dumps([item for item in orders if item["clientAlgoId"] != client_id])})
            return {"clientAlgoId": client_id}

    def check_triggers(self) -> str | None:
        with self.lock:
            position = self.get_positions()
            if not position:
                return None
            symbol = position[0]["symbol"]
            amount = Decimal(position[0]["positionAmt"])
            mark = Decimal(str(self.public.get_mark(symbol)["markPrice"]))
            for order in self.open_algo_orders(symbol):
                trigger = Decimal(order["triggerPrice"])
                stop = order["orderType"] == "STOP_MARKET"
                reached = (mark <= trigger if stop else mark >= trigger) if amount > 0 else (mark >= trigger if stop else mark <= trigger)
                if reached:
                    self.place_reduce_market(symbol, "SELL" if amount > 0 else "BUY", abs(amount), "paper-trigger-" + order["clientAlgoId"], mark)
                    self.cancel_algo(order["clientAlgoId"])
                    return order["orderType"]
            return None
