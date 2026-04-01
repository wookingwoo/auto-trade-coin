from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import TradingMode


class TrendSummary(BaseModel):
    short_term_trend: str
    medium_term_trend: str
    long_term_trend: str
    volatility_state: str
    market_regime: str
    change_since_last_decision: str


class PerformanceSummary(BaseModel):
    recent_win_rate: float | None = None
    recent_realized_pnl: float = 0.0
    profitable_trades: int = 0
    losing_trades: int = 0
    decision_accuracy_hint: str = "insufficient_history"


class PreviousDecisionSummary(BaseModel):
    timestamp: datetime
    decision: str
    confidence: float
    reasoning: str
    outcome: str | None = None


class TradingContext(BaseModel):
    run_id: str
    generated_at: datetime
    symbol: str
    mode: TradingMode
    market: dict
    indicators: dict
    market_context: TrendSummary
    external_signals: dict
    account_state: dict
    history: dict = Field(default_factory=dict)

