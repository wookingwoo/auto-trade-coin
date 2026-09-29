from __future__ import annotations

from decimal import Decimal
from math import lcm

from .domain import EntryPlan, SymbolRules, round_down, round_up


def compatible_step(limit_step: Decimal, market_step: Decimal | None) -> Decimal:
    if market_step is None:
        return limit_step
    places = max(-limit_step.as_tuple().exponent, -market_step.as_tuple().exponent, 0)
    scale = 10 ** places
    return Decimal(lcm(int(limit_step * scale), int(market_step * scale))) / scale


def loss_halt(initial_equity: Decimal, day_start_equity: Decimal, current_equity: Decimal) -> bool:
    if initial_equity <= 0 or day_start_equity <= 0 or current_equity <= 0:
        return True
    return current_equity <= day_start_equity * Decimal("0.98") or current_equity <= initial_equity * Decimal("0.90")


def size_entry(
    equity: Decimal,
    price: Decimal,
    atr: Decimal,
    cost_rate: Decimal,
    rules: SymbolRules,
    available_margin: Decimal,
    side: str,
) -> EntryPlan | None:
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT")
    if min(equity, price, atr, available_margin) <= 0 or cost_rate < 0:
        return None
    distance = atr * Decimal("1.5")
    fraction = distance / price
    if not Decimal("0.0035") <= fraction <= Decimal("0.025") or fraction < cost_rate * 2:
        return None
    if side == "LONG":
        stop = round_down(price - distance, rules.tick_size)
        take = round_down(price + distance * 2, rules.tick_size)
        actual_distance = price - stop
    else:
        stop = round_up(price + distance, rules.tick_size)
        take = round_up(price - distance * 2, rules.tick_size)
        actual_distance = stop - price
    if stop <= 0 or take <= 0 or actual_distance <= 0:
        return None
    risk_budget = equity * Decimal("0.005")
    margin_budget = min(equity * Decimal("0.25"), available_margin)
    quantity = min(
        risk_budget / (actual_distance + price * cost_rate),
        equity * Decimal("0.50") / price,
        margin_budget / (price / 2 + price * cost_rate),
    )
    quantity_step = compatible_step(rules.step_size, rules.market_step_size)
    quantity = round_down(quantity, quantity_step)
    if rules.max_qty is not None:
        quantity = min(quantity, round_down(rules.max_qty, quantity_step))
    if quantity < rules.min_qty or quantity * price < rules.min_notional:
        return None
    worst_loss = quantity * (actual_distance + price * cost_rate)
    if worst_loss > risk_budget or quantity * price > equity * Decimal("0.50"):
        return None
    return EntryPlan(side, quantity, price, stop, take, worst_loss, cost_rate)
