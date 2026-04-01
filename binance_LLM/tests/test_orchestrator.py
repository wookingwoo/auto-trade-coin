from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings
from app.models.enums import DecisionType, OrderStatus, PositionSide, RiskLevel, TradingMode
from app.models.execution import OrderExecutionResult
from app.models.market import Candle, IndicatorSnapshot, MarketSnapshot, PositionState, SymbolRules, TechnicalIndicators
from app.schemas.context import TradingContext
from app.schemas.decision import LLMDecision, SignalsUsed
from app.services.trading_orchestrator import TradingOrchestrator


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
        candles_1h=[candle] * 30,
        candles_4h=[candle] * 30,
        candles_1d=[candle] * 30,
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


def _indicators() -> TechnicalIndicators:
    snapshot = IndicatorSnapshot(
        timeframe="1h",
        rsi=50.0,
        macd=1.0,
        macd_signal=0.5,
        macd_hist=0.5,
        ema_fast=99.0,
        ema_slow=98.0,
        sma_20=97.0,
        bollinger_upper=103.0,
        bollinger_mid=100.0,
        bollinger_lower=97.0,
        atr=1.0,
        volume_ratio=1.1,
    )
    return TechnicalIndicators(
        run_id="run-1",
        symbol="BTCUSDT",
        calculated_at=datetime.now(tz=UTC),
        h1=snapshot.model_copy(update={"timeframe": "1h"}),
        h4=snapshot.model_copy(update={"timeframe": "4h"}),
        d1=snapshot.model_copy(update={"timeframe": "1d"}),
    )


def _position() -> PositionState:
    return PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0.0,
    )


def _decision() -> LLMDecision:
    return LLMDecision(
        decision=DecisionType.HOLD,
        confidence=0.4,
        reasoning="Signals are mixed and do not justify a position.",
        risk_level=RiskLevel.LOW,
        recommended_leverage=1,
        position_size_pct=0.0,
        stop_loss_pct=0.0,
        take_profit_pct=0.0,
        invalidate_if=["1h trend aligns strongly"],
        signals_used=SignalsUsed(
            trend="mixed",
            momentum="neutral",
            volume="normal",
            volatility="low",
            news="neutral",
        ),
    )


class FakeRepository:
    def __init__(self, create_ok: bool = True) -> None:
        self.create_ok = create_ok
        self.market_snapshots: list[dict] = []
        self.technical_indicator_docs: list[dict] = []
        self.news_docs: list[list] = []
        self.contexts: list[TradingContext] = []
        self.decisions: list[dict] = []
        self.orders: list[dict] = []
        self.positions: list[PositionState] = []
        self.logs: list[dict] = []
        self.finished: list[dict] = []
        self.existing = {"run_id": "existing-run"}

    def create_strategy_run(self, run_id: str, symbol: str, mode: str, idempotency_key: str) -> bool:
        self.last_create = {
            "run_id": run_id,
            "symbol": symbol,
            "mode": mode,
            "idempotency_key": idempotency_key,
        }
        return self.create_ok

    def get_strategy_run_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        return self.existing

    def upsert_system_config(self, payload: dict) -> None:
        self.system_config = payload

    def save_market_snapshot(self, payload: dict) -> None:
        self.market_snapshots.append(payload)

    def save_technical_indicators(self, indicators: TechnicalIndicators) -> None:
        self.technical_indicator_docs.append(indicators.model_dump(mode="python"))

    def save_news_signals(self, signals: list) -> None:
        self.news_docs.append(signals)

    def get_recent_decisions(self, symbol: str, limit: int = 5) -> list[dict]:
        return []

    def save_context(self, context: TradingContext) -> None:
        self.contexts.append(context)

    def save_llm_decision(self, **kwargs) -> None:
        self.decisions.append(kwargs)

    def save_execution_log(self, run_id: str, symbol: str, stage: str, payload: dict) -> None:
        self.logs.append({"run_id": run_id, "symbol": symbol, "stage": stage, "payload": payload})

    def save_trade_order(self, payload: dict) -> None:
        self.orders.append(payload)

    def save_position(self, position: PositionState) -> None:
        self.positions.append(position)

    def finish_strategy_run(self, run_id: str, status: str, metadata: dict | None = None) -> None:
        self.finished.append({"run_id": run_id, "status": status, "metadata": metadata or {}})


class FakeMarketService:
    def __init__(self) -> None:
        self.called = False

    def fetch_market_snapshot(self, run_id: str, symbol: str) -> MarketSnapshot:
        self.called = True
        snapshot = _snapshot()
        return snapshot.model_copy(update={"run_id": run_id, "symbol": symbol})


class FakeIndicatorService:
    def calculate(self, snapshot: MarketSnapshot) -> TechnicalIndicators:
        indicators = _indicators()
        return indicators.model_copy(update={"run_id": snapshot.run_id, "symbol": snapshot.symbol})


class FakeNewsService:
    def collect(self, run_id: str, symbol: str) -> list:
        return []


class FakePositionManager:
    def get_position_state(self, symbol: str, current_price: float) -> PositionState:
        return _position().model_copy(update={"symbol": symbol})

    def build_performance_summary(self, symbol: str) -> dict:
        return {}


class FakeContextBuilder:
    def build(self, snapshot, indicators, news_signals, position_state, recent_decisions, performance_summary) -> TradingContext:
        return TradingContext(
            run_id=snapshot.run_id,
            generated_at=datetime.now(tz=UTC),
            symbol=snapshot.symbol,
            mode=TradingMode.DRY_RUN,
            market={"current_price": snapshot.current_price},
            indicators={},
            market_context={
                "short_term_trend": "mixed",
                "medium_term_trend": "mixed",
                "long_term_trend": "mixed",
                "volatility_state": "low",
                "market_regime": "ranging",
                "change_since_last_decision": "no previous decision",
            },
            external_signals={"headlines": []},
            account_state={"available_balance": position_state.available_balance},
            history={},
        )


class FakeDecisionAgent:
    prompt_version = "test"

    def decide(self, context: TradingContext) -> LLMDecision:
        return _decision()


class FakeOrderExecutor:
    def execute(self, run_id: str, snapshot: MarketSnapshot, position_state: PositionState, decision: LLMDecision) -> OrderExecutionResult:
        return OrderExecutionResult(
            run_id=run_id,
            symbol=snapshot.symbol,
            mode=TradingMode.DRY_RUN,
            decision=decision.decision,
            status=OrderStatus.SKIPPED,
            executed_at=datetime.now(tz=UTC),
            message="Decision was hold. No order submitted.",
            resulting_side=PositionSide.FLAT,
            resulting_quantity=0.0,
            resulting_entry_price=None,
            paper_balance=position_state.available_balance,
        )


def _settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="dummy",
        trading_mode=TradingMode.DRY_RUN,
        trading_symbols=["BTCUSDT"],
    )


def test_orchestrator_skips_duplicate_slot_without_running_pipeline() -> None:
    repo = FakeRepository(create_ok=False)
    market_service = FakeMarketService()
    orchestrator = TradingOrchestrator(
        settings=_settings(),
        repository=repo,
        market_service=market_service,
        indicator_service=FakeIndicatorService(),
        news_service=FakeNewsService(),
        position_manager=FakePositionManager(),
        context_builder=FakeContextBuilder(),
        decision_agent=FakeDecisionAgent(),
        order_executor=FakeOrderExecutor(),
    )

    result = orchestrator.run_once("BTCUSDT")

    assert result["execution_status"] == "skipped_duplicate"
    assert result["run_id"] == "existing-run"
    assert market_service.called is False


def test_orchestrator_runs_hold_flow_and_persists_position() -> None:
    repo = FakeRepository(create_ok=True)
    orchestrator = TradingOrchestrator(
        settings=_settings(),
        repository=repo,
        market_service=FakeMarketService(),
        indicator_service=FakeIndicatorService(),
        news_service=FakeNewsService(),
        position_manager=FakePositionManager(),
        context_builder=FakeContextBuilder(),
        decision_agent=FakeDecisionAgent(),
        order_executor=FakeOrderExecutor(),
    )

    result = orchestrator.run_once("BTCUSDT")

    assert result["decision"] == "hold"
    assert result["execution_status"] == "skipped"
    assert len(repo.market_snapshots) == 1
    assert len(repo.technical_indicator_docs) == 1
    assert len(repo.contexts) == 1
    assert len(repo.decisions) == 1
    assert len(repo.orders) == 0
    assert len(repo.positions) == 1
    assert repo.finished[-1]["status"] == "completed"
