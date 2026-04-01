from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from langsmith import traceable

from app.config import Settings
from app.models.market import PositionState
from app.repositories.trading_repository import TradingRepository
from app.services.market_data import BinanceMarketDataService
from app.services.news_signal import NewsSignalService
from app.services.order_executor import OrderExecutor
from app.services.position_manager import PositionManager
from app.services.technical_indicators import TechnicalIndicatorService
from app.services.trading_context_builder import TradingContextBuilder
from app.services.trading_decision_agent import TradingDecisionAgent
from app.utils.time import build_run_idempotency_key


class TradingOrchestrator:
    """Coordinate the end-to-end hourly trading pipeline."""

    def __init__(
        self,
        settings: Settings,
        repository: TradingRepository,
        market_service: BinanceMarketDataService,
        indicator_service: TechnicalIndicatorService,
        news_service: NewsSignalService,
        position_manager: PositionManager,
        context_builder: TradingContextBuilder,
        decision_agent: TradingDecisionAgent,
        order_executor: OrderExecutor,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.market_service = market_service
        self.indicator_service = indicator_service
        self.news_service = news_service
        self.position_manager = position_manager
        self.context_builder = context_builder
        self.decision_agent = decision_agent
        self.order_executor = order_executor
        self.logger = structlog.get_logger(__name__)

    @traceable(name="trading_pipeline", run_type="chain")
    def run_once(self, symbol: str) -> dict:
        run_id = uuid4().hex
        run_at = datetime.now(tz=UTC)
        idempotency_key = build_run_idempotency_key(
            symbol=symbol,
            mode=self.settings.trading_mode.value,
            run_at=run_at,
            interval_minutes=self.settings.run_interval_minutes,
        )
        created = self.repository.create_strategy_run(
            run_id=run_id,
            symbol=symbol,
            mode=self.settings.trading_mode.value,
            idempotency_key=idempotency_key,
        )
        if not created:
            existing = self.repository.get_strategy_run_by_idempotency_key(idempotency_key)
            self.logger.info(
                "strategy_run_skipped_duplicate",
                symbol=symbol,
                idempotency_key=idempotency_key,
                existing_run_id=existing["run_id"] if existing else None,
            )
            return {
                "run_id": existing["run_id"] if existing else None,
                "symbol": symbol,
                "decision": None,
                "execution_status": "skipped_duplicate",
            }

        self.repository.upsert_system_config(
            {
                "config_key": "runtime_settings",
                "app_env": self.settings.app_env,
                "trading_mode": self.settings.trading_mode.value,
                "trading_symbols": self.settings.trading_symbols,
                "llm_model": self.settings.llm_model,
                "updated_by_run_id": run_id,
            }
        )

        try:
            snapshot = self.market_service.fetch_market_snapshot(run_id, symbol)
            self.repository.save_market_snapshot(snapshot.model_dump(mode="python"))

            indicators = self.indicator_service.calculate(snapshot)
            self.repository.save_technical_indicators(indicators)

            news_signals = self.news_service.collect(run_id, symbol)
            self.repository.save_news_signals(news_signals)

            position_state = self.position_manager.get_position_state(symbol, snapshot.current_price)
            recent_decisions = self.repository.get_recent_decisions(
                symbol=symbol,
                limit=self.settings.decision_history_limit,
            )
            performance_summary = self.position_manager.build_performance_summary(symbol)
            context = self.context_builder.build(
                snapshot=snapshot,
                indicators=indicators,
                news_signals=news_signals,
                position_state=position_state,
                recent_decisions=recent_decisions,
                performance_summary=performance_summary,
            )
            self.repository.save_context(context)

            decision = self.decision_agent.decide(context)
            self.repository.save_llm_decision(
                run_id=run_id,
                symbol=symbol,
                mode=self.settings.trading_mode.value,
                model_name=self.settings.llm_model,
                prompt_version=self.decision_agent.prompt_version,
                market_price=snapshot.current_price,
                decision=decision,
            )
            self.repository.save_execution_log(
                run_id=run_id,
                symbol=symbol,
                stage="llm_decision",
                payload={
                    "market_price": snapshot.current_price,
                    **decision.model_dump(mode="python"),
                },
            )

            execution = self.order_executor.execute(run_id, snapshot, position_state, decision)
            self._persist_execution(run_id, symbol, position_state, execution)

            self.repository.finish_strategy_run(
                run_id,
                status="completed",
                metadata={
                    "decision": decision.decision.value,
                    "execution_status": execution.status.value,
                },
            )
            self.logger.info(
                "strategy_run_completed",
                run_id=run_id,
                symbol=symbol,
                decision=decision.decision.value,
                execution_status=execution.status.value,
            )
            return {
                "run_id": run_id,
                "symbol": symbol,
                "decision": decision.decision.value,
                "execution_status": execution.status.value,
            }
        except Exception as exc:  # noqa: BLE001
            self.repository.save_execution_log(
                run_id=run_id,
                symbol=symbol,
                stage="error",
                payload={"message": str(exc)},
            )
            self.repository.finish_strategy_run(run_id, status="failed", metadata={"error": str(exc)})
            self.logger.exception("strategy_run_failed", run_id=run_id, symbol=symbol, error=str(exc))
            raise

    def _persist_execution(
        self,
        run_id: str,
        symbol: str,
        previous_position: PositionState,
        execution,
    ) -> None:
        for index, request in enumerate(execution.order_requests):
            response = execution.exchange_responses[index] if index < len(execution.exchange_responses) else None
            self.repository.save_trade_order(
                {
                    "run_id": run_id,
                    "symbol": symbol,
                    "mode": self.settings.trading_mode.value,
                    "client_order_id": request.client_order_id,
                    "side": request.side,
                    "quantity": request.quantity,
                    "reduce_only": request.reduce_only,
                    "status": execution.status.value,
                    "average_price": self._resolve_average_price(response, execution),
                    "exchange_order_id": response.get("orderId") if response else response.get("algoId") if response else None,
                    "order_type": request.order_type,
                    "stop_price": request.stop_price,
                    "close_position": request.close_position,
                    "working_type": request.working_type,
                    "metadata": request.metadata,
                    "executed_at": execution.executed_at,
                    "realized_pnl": execution.realized_pnl,
                    "message": execution.message,
                    "raw_response": response,
                    "all_responses": execution.exchange_responses,
                }
            )

        if execution.status.value in {"simulated", "filled", "skipped"}:
            if execution.status.value == "skipped":
                new_position = previous_position.model_copy(
                    update={
                        "captured_at": datetime.now(tz=UTC),
                    }
                )
            else:
                balance = execution.paper_balance if execution.paper_balance is not None else previous_position.available_balance
                new_position = previous_position.model_copy(
                    update={
                        "captured_at": datetime.now(tz=UTC),
                        "available_balance": balance,
                        "wallet_balance": balance,
                        "side": execution.resulting_side,
                        "quantity": execution.resulting_quantity,
                        "entry_price": execution.resulting_entry_price,
                        "position_notional": abs(execution.resulting_quantity) * (execution.resulting_entry_price or 0),
                    }
                )
            self.repository.save_position(new_position)

        self.repository.save_execution_log(
            run_id=run_id,
            symbol=symbol,
            stage="execution",
            payload=execution.model_dump(mode="python"),
        )

    @staticmethod
    def _resolve_average_price(response: dict | None, execution) -> float | None:
        if not response:
            return execution.resulting_entry_price
        if response.get("avgPrice") not in {None, "", "0", 0, 0.0}:
            return float(response["avgPrice"])
        if response.get("fill_price") is not None:
            return float(response["fill_price"])
        return execution.resulting_entry_price
