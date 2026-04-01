from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_UP


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def round_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    rounded = (decimal_value / decimal_step).quantize(Decimal("1"), rounding=ROUND_DOWN) * decimal_step
    return float(rounded)


def round_up_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    rounded = (decimal_value / decimal_step).quantize(Decimal("1"), rounding=ROUND_UP) * decimal_step
    return float(rounded)
