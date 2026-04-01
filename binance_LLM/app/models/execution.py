from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DecisionType, OrderStatus, PositionSide, TradingMode


class OrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    stop_price: float | None = None
    reduce_only: bool = False
    close_position: bool = False
    working_type: str | None = None
    leverage: int
    client_order_id: str
    metadata: dict[str, str | float | int | None] = Field(default_factory=dict)


class OrderExecutionResult(BaseModel):
    run_id: str
    symbol: str
    mode: TradingMode
    decision: DecisionType
    status: OrderStatus
    executed_at: datetime
    order_requests: list[OrderRequest] = Field(default_factory=list)
    exchange_responses: list[dict] = Field(default_factory=list)
    message: str
    resulting_side: PositionSide
    resulting_quantity: float = 0.0
    resulting_entry_price: float | None = None
    realized_pnl: float | None = None
    paper_balance: float | None = None
