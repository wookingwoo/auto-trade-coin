from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.market import Candle, MarketSnapshot, SymbolRules
from app.services.technical_indicators import TechnicalIndicatorService


def _build_candles(count: int, interval_hours: int = 1) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    price = 50_000.0
    for index in range(count):
        price += 25 + (index % 5)
        candles.append(
            Candle(
                open_time=start + timedelta(hours=index * interval_hours),
                close_time=start + timedelta(hours=(index + 1) * interval_hours),
                open=price - 10,
                high=price + 20,
                low=price - 25,
                close=price,
                volume=1_000 + index * 3,
                quote_volume=10_000 + index * 5,
                trade_count=100 + index,
            )
        )
    return candles


def test_indicator_service_calculates_core_values() -> None:
    snapshot = MarketSnapshot(
        run_id="run-1",
        symbol="BTCUSDT",
        collected_at=datetime.now(tz=UTC),
        current_price=55_000.0,
        mark_price=55_001.0,
        funding_rate=0.0001,
        open_interest=123.0,
        candles_1h=_build_candles(120, 1),
        candles_4h=_build_candles(120, 4),
        candles_1d=_build_candles(120, 24),
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

    indicators = TechnicalIndicatorService().calculate(snapshot)

    assert indicators.h1.rsi is not None
    assert indicators.h1.macd is not None
    assert indicators.h1.ema_fast is not None
    assert indicators.h1.atr is not None
    assert indicators.h4.bollinger_upper is not None
    assert indicators.d1.sma_20 is not None

