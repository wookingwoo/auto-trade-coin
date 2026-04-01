from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PositionSide, TradingMode


class Candle(BaseModel):
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float | None = None
    trade_count: int | None = None


class SymbolRules(BaseModel):
    symbol: str
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float
    price_precision: int
    quantity_precision: int


class MarketSnapshot(BaseModel):
    run_id: str
    symbol: str
    collected_at: datetime
    current_price: float
    mark_price: float | None = None
    funding_rate: float | None = None
    open_interest: float | None = None
    candles_1h: list[Candle]
    candles_4h: list[Candle]
    candles_1d: list[Candle]
    symbol_rules: SymbolRules


class IndicatorSnapshot(BaseModel):
    timeframe: str
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    ema_fast: float | None = None
    ema_slow: float | None = None
    sma_20: float | None = None
    bollinger_upper: float | None = None
    bollinger_mid: float | None = None
    bollinger_lower: float | None = None
    atr: float | None = None
    volume_ratio: float | None = None
    stochastic_rsi: float | None = None
    adx: float | None = None


class TechnicalIndicators(BaseModel):
    run_id: str
    symbol: str
    calculated_at: datetime
    h1: IndicatorSnapshot
    h4: IndicatorSnapshot
    d1: IndicatorSnapshot


class NewsSignal(BaseModel):
    run_id: str
    symbol: str
    collected_at: datetime
    signal_type: str
    source: str
    title: str
    summary: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    metadata: dict[str, str | float | int | None] = Field(default_factory=dict)


class OrderSummary(BaseModel):
    order_id: str
    side: str
    status: str
    quantity: float
    average_price: float | None = None
    realized_pnl: float | None = None
    executed_at: datetime


class PositionState(BaseModel):
    mode: TradingMode
    symbol: str
    captured_at: datetime
    available_balance: float
    wallet_balance: float
    leverage: int
    side: PositionSide
    quantity: float
    entry_price: float | None = None
    position_notional: float = 0.0
    unrealized_pnl: float = 0.0
    recent_orders: list[OrderSummary] = Field(default_factory=list)
    consecutive_losses: int = 0

