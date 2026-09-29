from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    close_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    max_qty: Decimal | None = None
    market_step_size: Decimal | None = None


@dataclass(frozen=True)
class EntryPlan:
    side: str
    quantity: Decimal
    entry_price: Decimal
    stop_price: Decimal
    take_price: Decimal
    worst_loss: Decimal
    cost_rate: Decimal


def round_down(value: Decimal, step: Decimal) -> Decimal:
    return value - value % step


def round_up(value: Decimal, step: Decimal) -> Decimal:
    down = round_down(value, step)
    return down if down == value else down + step


def decimal_text(value: Decimal) -> str:
    return format(value, "f")
