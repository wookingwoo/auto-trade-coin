from __future__ import annotations

from datetime import UTC, datetime

from app.models.enums import PositionSide, TradingMode
from app.models.market import Candle, IndicatorSnapshot, MarketSnapshot, PositionState, SymbolRules, TechnicalIndicators
from app.services.trading_context_builder import TradingContextBuilder


def _snapshot() -> MarketSnapshot:
    candle = Candle(
        open_time=datetime.now(tz=UTC),
        close_time=datetime.now(tz=UTC),
        open=100,
        high=105,
        low=95,
        close=100,
        volume=1000,
    )
    return MarketSnapshot(
        run_id="run-1",
        symbol="BTCUSDT",
        collected_at=datetime.now(tz=UTC),
        current_price=100,
        mark_price=100,
        funding_rate=0.001,
        open_interest=1000,
        candles_1h=[candle] * 20,
        candles_4h=[candle] * 20,
        candles_1d=[candle] * 20,
        symbol_rules=SymbolRules(
            symbol="BTCUSDT",
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=5.0,
            price_precision=2,
            quantity_precision=3,
        ),
    )


def test_context_builder_handles_zero_rsi_without_unknown_regime() -> None:
    indicators = TechnicalIndicators(
        run_id="run-1",
        symbol="BTCUSDT",
        calculated_at=datetime.now(tz=UTC),
        h1=IndicatorSnapshot(timeframe="1h", rsi=0.0, atr=1.0, bollinger_mid=100.0, ema_fast=99, ema_slow=98),
        h4=IndicatorSnapshot(timeframe="4h", rsi=10.0, atr=1.0, bollinger_mid=100.0, ema_fast=99, ema_slow=98),
        d1=IndicatorSnapshot(timeframe="1d", rsi=10.0, atr=1.0, bollinger_mid=100.0, ema_fast=99, ema_slow=98),
    )
    position = PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0.0,
    )

    context = TradingContextBuilder().build(
        snapshot=_snapshot(),
        indicators=indicators,
        news_signals=[],
        position_state=position,
        recent_decisions=[],
        performance_summary={},
    )

    assert context.market_context.market_regime == "trending"

