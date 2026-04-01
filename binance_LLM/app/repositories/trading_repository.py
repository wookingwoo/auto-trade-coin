from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.market import NewsSignal, PositionState, TechnicalIndicators
from app.schemas.decision import LLMDecision
from app.schemas.context import TradingContext


class TradingRepository:
    """Repository wrapper for MongoDB collections used by the MVP."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.market_snapshots = db["market_snapshots"]
        self.technical_indicators = db["technical_indicators"]
        self.llm_decisions = db["llm_decisions"]
        self.trade_orders = db["trade_orders"]
        self.positions = db["positions"]
        self.execution_logs = db["execution_logs"]
        self.strategy_runs = db["strategy_runs"]
        self.news_signals = db["news_signals"]
        self.system_configs = db["system_configs"]

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.strategy_runs.create_index([("run_id", DESCENDING)], unique=True)
        self.strategy_runs.create_index([("idempotency_key", DESCENDING)], unique=True)
        self.llm_decisions.create_index([("symbol", DESCENDING), ("created_at", DESCENDING)])
        self.trade_orders.create_index([("symbol", DESCENDING), ("executed_at", DESCENDING)])
        self.positions.create_index([("symbol", DESCENDING), ("captured_at", DESCENDING)])

    def upsert_system_config(self, payload: dict[str, Any]) -> None:
        self.system_configs.update_one(
            {"config_key": "runtime_settings"},
            {"$set": {"updated_at": datetime.now(tz=UTC), **payload}},
            upsert=True,
        )

    def create_strategy_run(self, run_id: str, symbol: str, mode: str, idempotency_key: str) -> bool:
        try:
            self.strategy_runs.insert_one(
                {
                    "run_id": run_id,
                    "symbol": symbol,
                    "mode": mode,
                    "idempotency_key": idempotency_key,
                    "status": "started",
                    "started_at": datetime.now(tz=UTC),
                }
            )
            return True
        except DuplicateKeyError:
            return False

    def finish_strategy_run(self, run_id: str, status: str, metadata: dict[str, Any] | None = None) -> None:
        self.strategy_runs.update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "status": status,
                    "finished_at": datetime.now(tz=UTC),
                    "metadata": metadata or {},
                }
            },
        )

    def save_market_snapshot(self, payload: dict[str, Any]) -> None:
        self.market_snapshots.insert_one(payload)

    def save_technical_indicators(self, indicators: TechnicalIndicators) -> None:
        self.technical_indicators.insert_one(indicators.model_dump(mode="python"))

    def save_news_signals(self, signals: list[NewsSignal]) -> None:
        if signals:
            self.news_signals.insert_many([signal.model_dump(mode="python") for signal in signals])

    def save_context(self, context: TradingContext) -> None:
        self.execution_logs.insert_one(
            {
                "run_id": context.run_id,
                "symbol": context.symbol,
                "stage": "context_built",
                "payload": context.model_dump(mode="python"),
                "created_at": datetime.now(tz=UTC),
            }
        )

    def save_llm_decision(
        self,
        run_id: str,
        symbol: str,
        mode: str,
        model_name: str,
        prompt_version: str,
        market_price: float,
        decision: LLMDecision,
    ) -> None:
        self.llm_decisions.insert_one(
            {
                "run_id": run_id,
                "symbol": symbol,
                "mode": mode,
                "model_name": model_name,
                "prompt_version": prompt_version,
                "market_price": market_price,
                "created_at": datetime.now(tz=UTC),
                **decision.model_dump(mode="python"),
            }
        )

    def save_trade_order(self, payload: dict[str, Any]) -> None:
        self.trade_orders.insert_one(payload)

    def save_position(self, position: PositionState) -> None:
        self.positions.insert_one(position.model_dump(mode="python"))

    def save_execution_log(self, run_id: str, symbol: str, stage: str, payload: dict[str, Any]) -> None:
        self.execution_logs.insert_one(
            {
                "run_id": run_id,
                "symbol": symbol,
                "stage": stage,
                "payload": payload,
                "created_at": datetime.now(tz=UTC),
            }
        )

    def get_recent_decisions(self, symbol: str, limit: int = 5) -> list[dict]:
        cursor = self.llm_decisions.find({"symbol": symbol}).sort("created_at", DESCENDING).limit(limit)
        return list(cursor)

    def get_latest_position(self, symbol: str, mode: str) -> dict | None:
        return self.positions.find_one({"symbol": symbol, "mode": mode}, sort=[("captured_at", DESCENDING)])

    def get_recent_orders(self, symbol: str, mode: str, limit: int = 20) -> list[dict]:
        cursor = self.trade_orders.find({"symbol": symbol, "mode": mode}).sort("executed_at", DESCENDING).limit(limit)
        return list(cursor)

    def get_strategy_run_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        return self.strategy_runs.find_one({"idempotency_key": idempotency_key})
