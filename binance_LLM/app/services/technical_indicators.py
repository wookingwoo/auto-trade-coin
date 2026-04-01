from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from app.models.market import Candle, IndicatorSnapshot, MarketSnapshot, TechnicalIndicators


class TechnicalIndicatorService:
    """Compute technical indicators from candle data."""

    def calculate(self, snapshot: MarketSnapshot) -> TechnicalIndicators:
        return TechnicalIndicators(
            run_id=snapshot.run_id,
            symbol=snapshot.symbol,
            calculated_at=datetime.now(tz=UTC),
            h1=self._calculate_for_timeframe(snapshot.candles_1h, "1h"),
            h4=self._calculate_for_timeframe(snapshot.candles_4h, "4h"),
            d1=self._calculate_for_timeframe(snapshot.candles_1d, "1d"),
        )

    def _calculate_for_timeframe(self, candles: list[Candle], timeframe: str) -> IndicatorSnapshot:
        frame = pd.DataFrame([candle.model_dump() for candle in candles])
        close = frame["close"]
        high = frame["high"]
        low = frame["low"]
        volume = frame["volume"]

        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.where(avg_loss != 0, 100.0)
        rsi = rsi.where(avg_gain != 0, 0.0)

        sma_20 = close.rolling(window=20).mean()
        rolling_std = close.rolling(window=20).std()
        bollinger_upper = sma_20 + (rolling_std * 2)
        bollinger_lower = sma_20 - (rolling_std * 2)

        previous_close = close.shift(1)
        true_range = pd.concat(
            [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(window=14).mean()

        volume_ratio = volume.iloc[-1] / volume.rolling(window=20).mean().iloc[-1]
        lowest_rsi = rsi.rolling(window=14).min()
        highest_rsi = rsi.rolling(window=14).max()
        stochastic_rsi = ((rsi - lowest_rsi) / (highest_rsi - lowest_rsi).replace(0, float("nan"))) * 100

        return IndicatorSnapshot(
            timeframe=timeframe,
            rsi=self._last_value(rsi),
            macd=self._last_value(macd),
            macd_signal=self._last_value(macd_signal),
            macd_hist=self._last_value(macd_hist),
            ema_fast=self._last_value(ema_fast),
            ema_slow=self._last_value(ema_slow),
            sma_20=self._last_value(sma_20),
            bollinger_upper=self._last_value(bollinger_upper),
            bollinger_mid=self._last_value(sma_20),
            bollinger_lower=self._last_value(bollinger_lower),
            atr=self._last_value(atr),
            volume_ratio=float(volume_ratio) if pd.notna(volume_ratio) else None,
            stochastic_rsi=self._last_value(stochastic_rsi),
            adx=None,
        )

    @staticmethod
    def _last_value(series: pd.Series) -> float | None:
        value = series.iloc[-1]
        return float(value) if pd.notna(value) else None
