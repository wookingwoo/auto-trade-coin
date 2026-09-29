from __future__ import annotations

import hashlib
from decimal import Decimal

from .binance import BinanceError, UnknownOrderOutcome
from .domain import EntryPlan, decimal_text, round_down, round_up
from .store import Journal


ZERO_FILL_TERMINAL_STATUSES = {"EXPIRED", "EXPIRED_IN_MATCH", "CANCELED", "REJECTED"}
EXIT_TERMINAL_STATUSES = ZERO_FILL_TERMINAL_STATUSES | {"FILLED"}
MAX_EXIT_ATTEMPTS = 3


def order_id(slot_key: str, stage: str) -> str:
    return "jv" + stage + hashlib.sha256(slot_key.encode()).hexdigest()[:28]


def _amount(position: dict) -> Decimal:
    return Decimal(str(position["positionAmt"]))


class TradeExecutor:
    def __init__(self, exchange, journal: Journal, symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")) -> None:
        self.exchange = exchange
        self.journal = journal
        self.symbols = symbols

    def current_position(self) -> dict | None:
        positions = [p for p in self.exchange.get_positions() if _amount(p) != 0]
        if len(positions) > 1 or any(p["symbol"] not in self.symbols or p.get("positionSide", "BOTH") != "BOTH" for p in positions):
            self.journal.halt("foreign_or_multiple_position")
            raise RuntimeError("foreign, hedged or multiple position")
        return positions[0] if positions else None

    def _owned_algo_ids(self, slot_key: str) -> tuple[str, str]:
        return order_id(slot_key, "s"), order_id(slot_key, "t")

    def _algo_present(self, symbol: str, client_id: str) -> bool:
        return any(item.get("clientAlgoId") == client_id for item in self.exchange.open_algo_orders(symbol))

    def _ensure_algo(self, symbol: str, side: str, kind: str, price: Decimal, client_id: str) -> bool:
        if self._algo_present(symbol, client_id):
            return True
        try:
            self.exchange.place_close_algo(symbol, side, kind, price, client_id)
        except UnknownOrderOutcome:
            try:
                self.exchange.query_algo(client_id)
            except BinanceError:
                return False
        except BinanceError:
            return False
        return self._algo_present(symbol, client_id)

    def _protect(self, intent: dict) -> bool:
        symbol = intent["symbol"]
        slot = intent["slot_key"]
        position = self.current_position()
        if position is None or position["symbol"] != symbol:
            return False
        exiting = intent["status"] == "EXITING"
        if not exiting:
            self.journal.update_intent(slot, "PROTECTING")
        exit_side = "SELL" if _amount(position) > 0 else "BUY"
        stop_id, take_id = self._owned_algo_ids(slot)
        if not self._ensure_algo(symbol, exit_side, "STOP_MARKET", Decimal(intent["stop_price"]), stop_id):
            return False
        if not self._ensure_algo(symbol, exit_side, "TAKE_PROFIT_MARKET", Decimal(intent["take_price"]), take_id):
            return False
        if not exiting:
            self.journal.update_intent(slot, "PROTECTED")
        self.journal.set("open_slot", slot)
        self.journal.event("protected", {"symbol": symbol, "slot": slot, "stop_id": stop_id, "take_id": take_id})
        return True

    def enter(self, slot_key: str, symbol: str, plan: EntryPlan) -> str:
        if self.journal.intent(slot_key):
            return "DUPLICATE"
        if self.journal.get("halt_reason") or self.journal.get("paused") == "1":
            return "BLOCKED"
        if self.current_position() or any(self.exchange.open_orders(name) or self.exchange.open_algo_orders(name) for name in self.symbols):
            self.journal.halt("account_not_flat")
            return "BLOCKED"
        client_id = order_id(slot_key, "e")
        if not self.journal.begin_intent(slot_key, client_id, symbol, plan.side, decimal_text(plan.quantity), decimal_text(plan.stop_price), decimal_text(plan.take_price)):
            return "DUPLICATE"
        self.journal.update_intent(slot_key, "ENTERING")
        side = "BUY" if plan.side == "LONG" else "SELL"
        try:
            order = self.exchange.place_ioc(symbol, side, plan.quantity, plan.entry_price, client_id)
        except UnknownOrderOutcome:
            self.journal.update_intent(slot_key, "UNKNOWN")
            try:
                order = self.exchange.query_order(symbol, client_id)
            except BinanceError:
                self.journal.halt("unknown_entry_outcome")
                return "UNKNOWN"
        except BinanceError:
            self.journal.update_intent(slot_key, "REJECTED")
            return "REJECTED"
        try:
            position = self.current_position()
        except Exception:
            self._emergency_exit(slot_key, symbol)
            return "HALTED"
        if position is None:
            if Decimal(str(order.get("executedQty", "0"))) > 0:
                self.journal.halt("fill_position_mismatch")
                return "HALTED"
            if order.get("status") not in ZERO_FILL_TERMINAL_STATUSES:
                self.journal.update_intent(slot_key, "UNKNOWN")
                self.journal.halt("unresolved_entry_outcome")
                return "UNKNOWN"
            self.journal.update_intent(slot_key, "NO_FILL")
            return "NO_FILL"
        if position["symbol"] != symbol or (_amount(position) > 0) != (plan.side == "LONG"):
            self.journal.halt("position_mismatch")
            return "HALTED"
        if abs(_amount(position)) > plan.quantity:
            self.journal.halt("oversize_position")
            self._emergency_exit(slot_key, symbol)
            return "HALTED"
        actual_price = Decimal(str(position.get("entryPrice") or order.get("avgPrice")))
        actual_loss = abs(_amount(position)) * (abs(actual_price - plan.stop_price) + actual_price * plan.cost_rate)
        if actual_loss > plan.worst_loss:
            self.journal.halt("actual_fill_risk_exceeded")
            self._emergency_exit(slot_key, symbol)
            return "HALTED"
        try:
            protected = self._protect(self.journal.intent(slot_key))
        except Exception:
            protected = False
        if not protected:
            self._emergency_exit(slot_key, symbol)
            return "HALTED"
        return "PROTECTED"

    def _emergency_exit(self, slot_key: str, symbol: str) -> None:
        try:
            self.journal.halt("protection_failed")
        except Exception:
            pass
        try:
            self.exit(slot_key, symbol)
        except Exception:
            # The ledger may be unavailable. A deterministic reduce-only ID is
            # still safer than leaving a confirmed fill without any protection.
            try:
                position = self.current_position()
                if position and position["symbol"] == symbol:
                    side = "SELL" if _amount(position) > 0 else "BUY"
                    self.exchange.place_reduce_market(symbol, side, abs(_amount(position)), order_id(slot_key, "x"))
            except Exception:
                pass

    def exit(self, slot_key: str, symbol: str) -> str:
        position = self.current_position()
        if position is not None and position["symbol"] != symbol:
            self.journal.halt("exit_symbol_mismatch")
            return "HALTED"
        if position is not None:
            quantity = abs(_amount(position))
            exit_id_key = f"exit_client_id:{slot_key}"
            exit_id = self.journal.get(exit_id_key)
            rules = None
            attempt = next((number for number in range(MAX_EXIT_ATTEMPTS)
                            if exit_id in (order_id(slot_key, f"x{number or ''}"),
                                           order_id(slot_key, f"l{number or ''}"))), None)
            if exit_id and attempt is None:
                self.journal.halt("unknown_exit_client_id")
                return "HALTED"
            use_limit = bool(exit_id and exit_id == order_id(slot_key, f"l{attempt or ''}"))
            if not exit_id:
                rules = self.exchange.get_rules(symbol) if hasattr(self.exchange, "get_rules") else None
                market_step = rules.market_step_size if rules else None
                use_limit = bool(market_step and quantity % market_step != 0)
                exit_id = order_id(slot_key, "l" if use_limit else "x")
                self.journal.set(exit_id_key, exit_id)
                attempt = 0
            intent = self.journal.intent(slot_key)
            if intent and intent["status"] == "EXITING":
                try:
                    previous = self.exchange.query_order(symbol, exit_id)
                except BinanceError:
                    self.journal.halt("unknown_exit_outcome")
                    return "UNKNOWN"
                if previous.get("status") not in EXIT_TERMINAL_STATUSES:
                    self.journal.halt("exit_still_pending")
                    return "UNKNOWN"
                if previous.get("status") == "FILLED":
                    self.journal.halt("exit_fill_position_mismatch")
                    return "HALTED"
                if attempt + 1 >= MAX_EXIT_ATTEMPTS:
                    self.journal.halt("exit_retry_exhausted")
                    return "HALTED"
                rules = self.exchange.get_rules(symbol) if hasattr(self.exchange, "get_rules") else None
                market_step = rules.market_step_size if rules else None
                use_limit = bool(market_step and quantity % market_step != 0)
                stage = ("l" if use_limit else "x") + str(attempt + 1)
                exit_id = order_id(slot_key, stage)
                self.journal.set(exit_id_key, exit_id)
            elif intent:
                self.journal.update_intent(slot_key, "EXITING")
            if use_limit and rules is None:
                rules = self.exchange.get_rules(symbol) if hasattr(self.exchange, "get_rules") else None
                if rules is None:
                    self.journal.halt("exit_rules_unavailable")
                    return "HALTED"
            side = "SELL" if _amount(position) > 0 else "BUY"
            try:
                if use_limit:
                    bid, ask, _ = self.exchange.get_book(symbol)
                    price = round_down(bid * Decimal("0.995"), rules.tick_size) if side == "SELL" else round_up(ask * Decimal("1.005"), rules.tick_size)
                    self.exchange.place_reduce_ioc(symbol, side, quantity, price, exit_id)
                else:
                    self.exchange.place_reduce_market(symbol, side, quantity, exit_id)
            except UnknownOrderOutcome:
                try:
                    self.exchange.query_order(symbol, exit_id)
                except BinanceError:
                    self.journal.halt("unknown_exit_outcome")
                    return "UNKNOWN"
            except BinanceError:
                self.journal.halt("exit_rejected")
                return "HALTED"
        remaining = self.current_position()
        if remaining is not None:
            if remaining["symbol"] != symbol or (position is not None and (_amount(remaining) > 0) != (_amount(position) > 0)):
                self.journal.halt("exit_position_mismatch")
                return "HALTED"
            return "EXITING"
        stop_id, take_id = self._owned_algo_ids(slot_key)
        for client_id in (stop_id, take_id):
            if self._algo_present(symbol, client_id):
                try:
                    self.exchange.cancel_algo(client_id)
                except (BinanceError, UnknownOrderOutcome):
                    self.journal.halt("orphan_algo_unknown")
                    return "UNKNOWN"
        if self._algo_present(symbol, stop_id) or self._algo_present(symbol, take_id):
            self.journal.halt("orphan_algo_remains")
            return "HALTED"
        if self.journal.intent(slot_key):
            self.journal.update_intent(slot_key, "CLOSED")
        self.journal.set("open_slot", "")
        self.journal.set("last_close_ms", __import__("time").time_ns() // 1_000_000)
        self.journal.event("closed", {"symbol": symbol, "slot": slot_key})
        return "CLOSED"

    def recover(self) -> str:
        position = self.current_position()
        if position is None:
            open_slot = self.journal.get("open_slot")
            if open_slot:
                owned = self.journal.intent(open_slot)
                if owned is None or self.exit(open_slot, owned["symbol"]) != "CLOSED":
                    self.journal.halt("flat_cleanup_unresolved")
                    return "HALTED"
            pending = self.journal.pending_intents()
            for intent in pending:
                if intent["status"] == "EXITING":
                    if self.exit(intent["slot_key"], intent["symbol"]) != "CLOSED":
                        self.journal.halt("flat_cleanup_unresolved")
                        return "HALTED"
                    continue
                if intent["status"] in ("UNKNOWN", "INTENT", "ENTERING"):
                    try:
                        order = self.exchange.query_order(intent["symbol"], intent["client_id"])
                    except BinanceError:
                        self.journal.halt("unresolved_entry_at_recovery")
                        return "HALTED"
                    if Decimal(str(order.get("executedQty", "0"))) > 0:
                        self.journal.halt("recovery_fill_position_mismatch")
                        return "HALTED"
                    if order.get("status") not in ZERO_FILL_TERMINAL_STATUSES:
                        self.journal.halt("unresolved_entry_at_recovery")
                        return "HALTED"
                self.journal.update_intent(intent["slot_key"], "NO_FILL")
            for symbol in self.symbols:
                if self.exchange.open_orders(symbol) or self.exchange.open_algo_orders(symbol):
                    self.journal.halt("orders_without_position")
                    return "HALTED"
            return "FLAT"
        intent = self.journal.latest_protected_intent(position["symbol"])
        if intent is None:
            self.journal.halt("unowned_position")
            return "HALTED"
        if (_amount(position) > 0) != (intent["side"] == "LONG") or abs(_amount(position)) > Decimal(intent["quantity"]):
            self.journal.halt("recovery_position_mismatch")
            return "HALTED"
        if not self._protect(intent):
            self._emergency_exit(intent["slot_key"], position["symbol"])
            return "HALTED"
        return "PROTECTED"
