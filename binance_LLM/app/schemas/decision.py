from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import DecisionType, RiskLevel


class SignalsUsed(BaseModel):
    trend: str
    momentum: str
    volume: str
    volatility: str
    news: str


class LLMDecision(BaseModel):
    decision: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=10)
    risk_level: RiskLevel
    recommended_leverage: int = Field(ge=1, le=125)
    position_size_pct: float = Field(ge=0.0, le=1.0)
    stop_loss_pct: float = Field(ge=0.0, le=1.0)
    take_profit_pct: float = Field(ge=0.0, le=1.0)
    invalidate_if: list[str] = Field(default_factory=list)
    signals_used: SignalsUsed

