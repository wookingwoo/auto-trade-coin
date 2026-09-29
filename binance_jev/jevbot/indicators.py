from __future__ import annotations

from collections.abc import Mapping, Sequence

from .domain import Candle


INTERVAL_MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000}


def _ema(values: list[float], span: int) -> float:
    alpha = 2 / (span + 1)
    result = values[0]
    for value in values[1:]:
        result += alpha * (value - result)
    return result


def _rsi(values: list[float]) -> float:
    changes = [new - old for old, new in zip(values, values[1:])]
    gains = [max(value, 0.0) for value in changes]
    losses = [max(-value, 0.0) for value in changes]
    gain = sum(gains[:14]) / 14
    loss = sum(losses[:14]) / 14
    for g, l in zip(gains[14:], losses[14:]):
        gain = (gain * 13 + g) / 14
        loss = (loss * 13 + l) / 14
    if loss == 0:
        return 100.0 if gain > 0 else 50.0
    return 100 - 100 / (1 + gain / loss)


def _atr(candles: list[Candle]) -> float:
    ranges = []
    for old, new in zip(candles, candles[1:]):
        ranges.append(max(float(new.high - new.low), abs(float(new.high - old.close)), abs(float(new.low - old.close))))
    result = sum(ranges[:14]) / 14
    for value in ranges[14:]:
        result = (result * 13 + value) / 14
    return result


def build_features(candles_by_interval: Mapping[str, Sequence[Candle]], now_ms: int) -> dict:
    output: dict = {}
    for interval, duration in INTERVAL_MS.items():
        available = [c for c in candles_by_interval[interval] if c.close_time_ms < now_ms]
        if len(available) < 300:
            raise ValueError(f"{interval}: fewer than 300 closed candles")
        selected = available[-300:]
        if any(new.open_time_ms - old.open_time_ms != duration for old, new in zip(selected, selected[1:])):
            raise ValueError(f"{interval}: missing or duplicate candle")
        if any(c.close_time_ms != c.open_time_ms + duration - 1 for c in selected):
            raise ValueError(f"{interval}: invalid close time")
        closes = [float(c.close) for c in selected]
        volumes = [float(c.volume) for c in selected]
        avg_volume = sum(volumes[-20:]) / 20
        output[interval] = {
            "close": closes[-1],
            "ema20": _ema(closes, 20),
            "ema50": _ema(closes, 50),
            "rsi14": _rsi(closes),
            "atr14": _atr(selected),
            "volume_ratio": volumes[-1] / avg_volume if avg_volume > 0 else 0.0,
            "return_5": closes[-1] / closes[-6] - 1,
        }
        if interval == "5m":
            output["candle_close_ms"] = selected[-1].close_time_ms
    return output
