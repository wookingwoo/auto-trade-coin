from __future__ import annotations

import pandas as pd
import numpy as np
import ta


def candles_to_df(candles):
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
        "ignore",
    ]
    df = pd.DataFrame(candles, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    return df[["open_time", "open", "high", "low", "close", "volume"]]


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema9"] = ta.trend.ema_indicator(df["close"], window=9, fillna=True)
    df["ema21"] = ta.trend.ema_indicator(df["close"], window=21, fillna=True)
    df["rsi"] = ta.momentum.rsi(df["close"], window=14, fillna=True)
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14, fillna=True)
    return df


def fallback_rule_based(df: pd.DataFrame):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    action = "HOLD"
    reason = ""
    if last["ema9"] > last["ema21"] and prev["ema9"] <= prev["ema21"]:
        action = "BUY"
        reason = "EMA9 crossed above EMA21"
    elif last["ema9"] < last["ema21"] and prev["ema9"] >= prev["ema21"]:
        action = "SELL"
        reason = "EMA9 crossed below EMA21"
    return action, reason

