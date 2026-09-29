from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .binance import BinanceError
from .domain import SymbolRules, round_down, round_up
from .execution import TradeExecutor, order_id
from .indicators import build_features
from .jev import JevDecider, gate_decision
from .risk import loss_halt, size_entry
from .store import Journal


KST = timezone(timedelta(hours=9))
SYMBOLS = ("BTCUSDT", "ETHUSDT")


@dataclass(frozen=True)
class Settings:
    mode: str
    api_key: str
    api_secret: str
    typesafe_key: str
    db_path: Path
    symbols: tuple[str, ...] = SYMBOLS
    strategy_version: str = "v1"
    heartbeat_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("JEVBOT_MODE", "paper").lower()
        if mode not in ("paper", "testnet", "live"):
            raise ValueError("JEVBOT_MODE must be paper, testnet or live")
        if mode == "live" and os.getenv("JEVBOT_LIVE_ENABLED") != "YES":
            raise ValueError("live mode requires JEVBOT_LIVE_ENABLED=YES")
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        if mode != "paper" and (not api_key or not api_secret):
            raise ValueError("Binance credentials required")
        typesafe_key = os.getenv("TYPESAFE_API_KEY", "")
        if not typesafe_key:
            raise ValueError("TYPESAFE_API_KEY required")
        raw_symbols = os.getenv("JEVBOT_SYMBOLS", "BTCUSDT,ETHUSDT")
        symbols = tuple(name.strip().upper() for name in raw_symbols.split(",") if name.strip())
        if not symbols or any(name not in SYMBOLS for name in symbols) or len(set(symbols)) != len(symbols):
            raise ValueError("only distinct BTCUSDT and ETHUSDT are supported")
        heartbeat_url = os.getenv("JEVBOT_HEARTBEAT_URL", "").strip() or None
        if heartbeat_url and (urlparse(heartbeat_url).scheme != "https" or not urlparse(heartbeat_url).hostname):
            raise ValueError("JEVBOT_HEARTBEAT_URL must be an HTTPS URL")
        return cls(mode, api_key, api_secret, typesafe_key, Path(os.getenv("JEVBOT_DB_PATH", "data/jevbot.db")), symbols, heartbeat_url=heartbeat_url)


def closed_slot(now_ms: int) -> int | None:
    elapsed = now_ms % 300_000
    return (now_ms // 300_000) * 300_000 - 1 if 2_000 <= elapsed <= 30_000 else None


def ioc_limit_price(side: str, quote: Decimal, rules: SymbolRules) -> Decimal | None:
    if quote <= 0:
        return None
    if side == "LONG":
        cap = quote * Decimal("1.0005")
        price = round_down(cap, rules.tick_size)
        return price if quote <= price <= cap else None
    if side == "SHORT":
        floor = quote * Decimal("0.9995")
        price = round_up(floor, rules.tick_size)
        return price if floor <= price <= quote else None
    raise ValueError("invalid side")


def verify_account_mode(exchange, symbols: tuple[str, ...]) -> None:
    if exchange.get_position_mode().get("dualSidePosition") is not False:
        raise BinanceError("One-way mode is required")
    if exchange.get_multi_asset_mode().get("multiAssetsMargin") is not False:
        raise BinanceError("Single-Asset mode is required")
    for symbol in symbols:
        config = exchange.get_symbol_config(symbol)
        if config.get("marginType") != "ISOLATED" or int(config.get("leverage", 0)) != 2:
            raise BinanceError(f"{symbol}: isolated margin and 2x leverage are required")


def _equity(account: dict) -> Decimal:
    return Decimal(str(account["totalMarginBalance"]))


def _day_key(now_ms: int) -> str:
    return datetime.fromtimestamp(now_ms / 1000, tz=KST).date().isoformat()


class TradingRunner:
    def __init__(self, settings: Settings, exchange, journal: Journal, decider: JevDecider | None = None) -> None:
        self.settings = settings
        self.exchange = exchange
        self.journal = journal
        self.decider = decider or JevDecider()
        self.executor = TradeExecutor(exchange, journal, settings.symbols)
        self.execution_lock = threading.RLock()
        self.rules: dict[str, SymbolRules] = {}
        self.taker_fees: dict[str, Decimal] = {}
        self.stop_event = threading.Event()

    def startup(self) -> str:
        self.journal.bind_environment(self.settings.mode)
        local_ms = int(time.time() * 1000)
        if abs(self.exchange.server_time() - local_ms) > 1000:
            raise BinanceError("server clock differs from Binance by over 1 second")
        verify_account_mode(self.exchange, self.settings.symbols)
        if self.exchange.get_account_config().get("canTrade") is not True:
            raise BinanceError("account cannot trade")
        account = self.exchange.get_account()
        equity = _equity(account)
        self.journal.initialize(equity, _day_key(local_ms))
        for symbol in self.settings.symbols:
            self.rules[symbol] = self.exchange.get_rules(symbol)
            self.taker_fees[symbol] = Decimal(str(self.exchange.get_commission(symbol)["takerCommissionRate"]))
        with self.execution_lock:
            status = self.executor.recover()
        self._check_transfers(local_ms, force=True)
        self.journal.event("startup", {"mode": self.settings.mode, "status": status})
        return status

    def _check_transfers(self, now_ms: int, force: bool = False) -> bool:
        if self.settings.mode == "paper":
            return False
        start_ms = int(self.journal.get("started_ms"))
        last_checked = int(self.journal.get("last_transfer_check_ms") or "0")
        if now_ms - start_ms > 60 * 24 * 3_600_000:
            self.journal.halt("transfer_history_window_expired")
            return True
        if not force and now_ms - last_checked < 60_000:
            return self.journal.get("halt_reason") in ("external_transfer", "unrecognized_income", "transfer_check_error", "transfer_history_window_expired")
        try:
            for page in range(1, 11):
                rows = self.exchange.get_income_history(start_ms, now_ms, page, 1000, None)
                if not isinstance(rows, list):
                    raise BinanceError("unexpected income response")
                for row in rows:
                    if not isinstance(row, dict):
                        raise BinanceError("invalid income item")
                    kind = row.get("incomeType")
                    if kind == "TRANSFER":
                        self.journal.halt("external_transfer")
                        self.journal.event("external_transfer", {"time": row.get("time"), "asset": row.get("asset")})
                        return True
                    if kind not in ("REALIZED_PNL", "COMMISSION", "FUNDING_FEE") or row.get("asset") != "USDT" or row.get("symbol") not in self.settings.symbols:
                        self.journal.halt("unrecognized_income")
                        self.journal.event("unrecognized_income", {"type": kind, "asset": row.get("asset"), "symbol": row.get("symbol")})
                        return True
                if len(rows) < 1000:
                    self.journal.set("last_transfer_check_ms", now_ms)
                    return False
            raise BinanceError("income history pagination limit reached")
        except (BinanceError, KeyError, TypeError, ValueError):
            self.journal.halt("transfer_check_error")
            return True

    def _cost_rate(self, symbol: str, side: str, now_ms: int) -> Decimal:
        mark = self.exchange.get_mark(symbol)
        rate = Decimal(str(mark["lastFundingRate"]))
        next_funding = int(mark["nextFundingTime"])
        adverse = Decimal("0")
        if now_ms < next_funding <= now_ms + 4 * 3_600_000:
            adverse = max(Decimal("0"), rate if side == "LONG" else -rate)
        return 2 * self.taker_fees[symbol] + Decimal("0.001") + adverse

    def _features(self, symbol: str, now_ms: int, expected_close: int) -> dict:
        candles = {interval: self.exchange.get_candles(symbol, interval, 302) for interval in ("5m", "15m", "1h")}
        features = build_features(candles, now_ms)
        if features["candle_close_ms"] != expected_close:
            raise ValueError("stale 5-minute candle")
        return features

    def _model_state(self, symbol: str, features: dict, side: str | None, held_minutes: float, cost_rate: Decimal) -> dict:
        state: dict = {"symbol": symbol, "position": side or "FLAT", "held_minutes": round(held_minutes, 1), "estimated_round_trip_cost_pct": round(float(cost_rate) * 100, 3)}
        for interval in ("5m", "15m", "1h"):
            values = features[interval]
            rsi = values["rsi14"]
            volume = values["volume_ratio"]
            state[interval] = {
                "close": round(values["close"], 4),
                "ema20": round(values["ema20"], 4),
                "ema50": round(values["ema50"], 4),
                "trend": "up" if values["ema20"] > values["ema50"] else "down",
                "rsi14": round(rsi, 2),
                "rsi_band": "low" if rsi < 30 else "high" if rsi > 70 else "middle",
                "atr14": round(values["atr14"], 4),
                "volume_ratio": round(volume, 2),
                "volume_band": "low" if volume < .8 else "high" if volume > 1.2 else "normal",
                "return_5_pct": round(values["return_5"] * 100, 3),
            }
        return state

    def _record_decision(self, symbol: str, slot: int, state: dict, decision, executed: str) -> None:
        self.journal.event("decision", {
            "symbol": symbol, "slot": slot, "state": state, "action": decision.action,
            "probabilities": decision.probabilities, "confidence": decision.confidence,
            "model": decision.model, "request_id": decision.request_id,
            "duration_ms": decision.duration_ms, "error": decision.error, "executed": executed,
        })

    def _entry_candidate(self, symbol: str, now_ms: int, slot: int, equity: Decimal) -> tuple | None:
        features = self._features(symbol, now_ms, slot)
        long_cost = self._cost_rate(symbol, "LONG", now_ms)
        state = self._model_state(symbol, features, None, 0, long_cost)
        decision = self.decider.decide(state, held=False)
        action = gate_decision(decision, held=False)
        self._record_decision(symbol, slot, state, decision, action)
        if action not in ("OPEN_LONG", "OPEN_SHORT"):
            return None
        side = "LONG" if action == "OPEN_LONG" else "SHORT"
        cost = self._cost_rate(symbol, side, now_ms)
        stop_distance = Decimal(str(features["5m"]["atr14"])) * Decimal("1.5")
        price = Decimal(str(features["5m"]["close"]))
        if stop_distance <= 0 or price <= 0:
            return None
        return (cost * price / stop_distance, symbol, side, features)

    def run_slot(self, now_ms: int | None = None) -> str:
        now_ms = now_ms or int(time.time() * 1000)
        slot = closed_slot(now_ms)
        if slot is None or self.journal.get("last_slot") == str(slot):
            return "NO_SLOT"
        self.journal.set("last_slot", slot)
        if self.journal.get("halt_reason") or self.journal.get("paused") == "1":
            return "BLOCKED"
        if self._check_transfers(now_ms):
            return "HALTED"
        account = self.exchange.get_account()
        equity = _equity(account)
        self.journal.roll_day(_day_key(now_ms), equity)
        if loss_halt(self.journal.get_decimal("initial_equity"), self.journal.get_decimal("day_start_equity"), equity):
            self.journal.halt("loss_limit")
            return "HALTED"
        with self.execution_lock:
            position = self.executor.current_position()
        if position:
            symbol = position["symbol"]
            slot_key = self.journal.get("open_slot")
            if not slot_key:
                self.journal.halt("position_without_slot")
                return "HALTED"
            intent = self.journal.intent(slot_key)
            held_minutes = (now_ms - intent["created_ms"]) / 60_000
            if held_minutes >= 240:
                with self.execution_lock:
                    return self.executor.exit(slot_key, symbol)
            features = self._features(symbol, now_ms, slot)
            side = "LONG" if Decimal(position["positionAmt"]) > 0 else "SHORT"
            cost = self._cost_rate(symbol, side, now_ms)
            state = self._model_state(symbol, features, side, held_minutes, cost)
            decision = self.decider.decide(state, held=True)
            action = gate_decision(decision, held=True)
            self._record_decision(symbol, slot, state, decision, action)
            if action == "CLOSE":
                with self.execution_lock:
                    return self.executor.exit(slot_key, symbol)
            return "KEEP"
        last_close = int(self.journal.get("last_close_ms") or "0")
        if now_ms < last_close + 300_000:
            return "COOLDOWN"
        candidates = []
        for symbol in self.settings.symbols:
            try:
                candidate = self._entry_candidate(symbol, now_ms, slot, equity)
                if candidate:
                    candidates.append(candidate)
            except (BinanceError, ValueError) as exc:
                self.journal.event("skip", {"symbol": symbol, "reason": type(exc).__name__})
        if not candidates or int(time.time() * 1000) > slot + 30_000:
            return "WAIT"
        _, symbol, side, features = min(candidates, key=lambda item: (item[0], self.settings.symbols.index(item[1])))
        with self.execution_lock:
            if self.journal.get("halt_reason") or self.executor.current_position():
                return "BLOCKED"
            if self._check_transfers(int(time.time() * 1000), force=True):
                return "HALTED"
            account = self.exchange.get_account()
            equity = _equity(account)
            if loss_halt(self.journal.get_decimal("initial_equity"), self.journal.get_decimal("day_start_equity"), equity):
                self.journal.halt("loss_limit")
                return "HALTED"
            bid, ask, received_ms = self.exchange.get_book(symbol)
            if int(time.time() * 1000) - received_ms > 3000 or bid <= 0 or ask <= 0 or (ask - bid) / bid > Decimal("0.0005"):
                return "STALE_OR_WIDE_BOOK"
            quote = ask if side == "LONG" else bid
            limit = ioc_limit_price(side, quote, self.rules[symbol])
            if limit is None:
                return "INVALID_LIMIT"
            cost = self._cost_rate(symbol, side, now_ms)
            plan = size_entry(min(self.journal.get_decimal("initial_equity"), equity), limit, Decimal(str(features["5m"]["atr14"])), cost, self.rules[symbol], Decimal(str(account["availableBalance"])), side)
            if plan is None or int(time.time() * 1000) > slot + 30_000:
                return "RISK_SKIP"
            slot_key = f"{self.settings.mode}:{self.settings.strategy_version}:{symbol}:{slot}:e"
            return self.executor.enter(slot_key, symbol, plan)

    def risk_tick(self) -> None:
        now_ms = int(time.time() * 1000)
        if hasattr(self.exchange, "check_triggers"):
            with self.execution_lock:
                self.exchange.check_triggers()
        account = self.exchange.get_account()
        equity = _equity(account)
        self.journal.roll_day(_day_key(now_ms), equity)
        self.journal.set("last_account_ms", now_ms)
        self.journal.set("equity", equity)
        self._check_transfers(now_ms)
        with self.execution_lock:
            position = self.executor.current_position()
            slot_key = self.journal.get("open_slot")
            if position and not slot_key:
                if self.executor.recover() != "PROTECTED":
                    return
                slot_key = self.journal.get("open_slot")
            command = self.journal.get("command")
            if command:
                self.journal.set("command", "")
            if loss_halt(self.journal.get_decimal("initial_equity"), self.journal.get_decimal("day_start_equity"), equity):
                self.journal.halt("loss_limit")
                command = "flatten_and_halt"
            if command == "flatten_and_halt":
                if not self.journal.get("halt_reason"):
                    self.journal.halt("operator_flatten")
                if position and slot_key:
                    self.executor.exit(slot_key, position["symbol"])
                return
            if position and slot_key:
                intent = self.journal.intent(slot_key)
                if not intent:
                    self.journal.halt("position_without_intent")
                    return
                if intent["status"] == "EXITING":
                    self.executor.exit(slot_key, position["symbol"])
                    return
                if now_ms - intent["created_ms"] >= 4 * 3_600_000:
                    self.executor.exit(slot_key, position["symbol"])
                    return
                stop_id = order_id(slot_key, "s")
                take_id = order_id(slot_key, "t")
                active = {item.get("clientAlgoId") for item in self.exchange.open_algo_orders(position["symbol"])}
                if stop_id not in active or take_id not in active:
                    if not self.executor._protect(intent):
                        self.executor._emergency_exit(slot_key, position["symbol"])
            elif slot_key:
                self.executor.exit(slot_key, self.journal.intent(slot_key)["symbol"])

    def run_forever(self) -> None:
        self.startup()
        watcher = threading.Thread(target=self._watch, daemon=True, name="risk-watch")
        watcher.start()
        try:
            while not self.stop_event.is_set():
                try:
                    self.run_slot()
                except Exception as exc:
                    self.journal.halt("strategy_loop_error")
                    self.journal.event("error", {"component": "strategy", "type": type(exc).__name__})
                self.stop_event.wait(1)
        finally:
            self.stop_event.set()
            watcher.join(timeout=20)

    def _watch(self) -> None:
        watcher_journal = Journal(self.journal.path)
        watcher = TradingRunner(self.settings, self.exchange, watcher_journal, self.decider)
        watcher.execution_lock = self.execution_lock
        next_ping = 0.0
        try:
            while not self.stop_event.is_set():
                try:
                    watcher.risk_tick()
                    if self.settings.heartbeat_url and time.monotonic() >= next_ping:
                        next_ping = time.monotonic() + 60
                        try:
                            watcher._send_heartbeat()
                        except httpx.HTTPError as exc:
                            watcher_journal.event("heartbeat_error", {"type": type(exc).__name__})
                except Exception as exc:
                    watcher_journal.halt("risk_watch_error")
                    watcher_journal.event("error", {"component": "risk", "type": type(exc).__name__})
                self.stop_event.wait(1)
        finally:
            watcher_journal.close()

    def _send_heartbeat(self) -> None:
        if self.settings.heartbeat_url:
            httpx.get(self.settings.heartbeat_url, timeout=5).raise_for_status()
