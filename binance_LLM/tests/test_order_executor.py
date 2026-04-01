from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings
from app.models.enums import DecisionType, PositionSide, RiskLevel, TradingMode
from app.models.market import Candle, MarketSnapshot, PositionState, SymbolRules
from app.schemas.decision import LLMDecision, SignalsUsed
from app.services.order_executor import OrderExecutor


class DummyBinanceClient:
    def __init__(self, fail_on_trigger_order: bool = False) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail_on_trigger_order = fail_on_trigger_order

    def cancel_all_open_orders(self, symbol: str) -> dict:
        payload = {"symbol": symbol}
        self.calls.append(("cancel_all_open_orders", payload))
        return {"code": 200}

    def cancel_all_algo_open_orders(self, symbol: str) -> dict:
        payload = {"symbol": symbol}
        self.calls.append(("cancel_all_algo_open_orders", payload))
        return {"code": 200}

    def change_leverage(self, symbol: str, leverage: int) -> dict:
        payload = {"symbol": symbol, "leverage": leverage}
        self.calls.append(("change_leverage", payload))
        return payload

    def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        client_order_id: str,
        reduce_only: bool = False,
    ) -> dict:
        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "client_order_id": client_order_id,
            "reduce_only": reduce_only,
        }
        self.calls.append(("create_market_order", payload))
        return {
            "orderId": len(self.calls),
            "avgPrice": "60010",
            "status": "FILLED",
            **payload,
        }

    def create_trigger_close_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        stop_price: float,
        client_order_id: str,
        working_type: str = "MARK_PRICE",
        ) -> dict:
        payload = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "stop_price": stop_price,
            "client_order_id": client_order_id,
            "working_type": working_type,
        }
        self.calls.append(("create_trigger_close_order", payload))
        if self.fail_on_trigger_order:
            raise RuntimeError("protective order failure")
        return {
            "orderId": len(self.calls),
            "status": "NEW",
            **payload,
        }


def _settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        trading_mode=TradingMode.DRY_RUN,
        trading_symbols=["BTCUSDT"],
    )


def _live_settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        trading_mode=TradingMode.LIVE,
        trading_symbols=["BTCUSDT"],
        enable_protective_orders=True,
        protective_order_working_type="MARK_PRICE",
    )


def _snapshot() -> MarketSnapshot:
    candle = Candle(
        open_time=datetime.now(tz=UTC),
        close_time=datetime.now(tz=UTC),
        open=60_000,
        high=60_500,
        low=59_500,
        close=60_000,
        volume=1000,
    )
    return MarketSnapshot(
        run_id="run-1",
        symbol="BTCUSDT",
        collected_at=datetime.now(tz=UTC),
        current_price=60_000,
        mark_price=60_010,
        funding_rate=0.0001,
        open_interest=1_000_000,
        candles_1h=[candle] * 120,
        candles_4h=[candle] * 120,
        candles_1d=[candle] * 120,
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


def _decision(decision: DecisionType) -> LLMDecision:
    return LLMDecision(
        decision=decision,
        confidence=0.8,
        reasoning="Trend and momentum are aligned.",
        risk_level=RiskLevel.MEDIUM,
        recommended_leverage=2,
        position_size_pct=0.1,
        stop_loss_pct=0.01,
        take_profit_pct=0.02,
        invalidate_if=["1h EMA cross flips"],
        signals_used=SignalsUsed(
            trend="bullish",
            momentum="positive",
            volume="stable",
            volatility="medium",
            news="neutral",
        ),
    )


def test_order_executor_simulates_long_from_flat() -> None:
    executor = OrderExecutor(_settings(), DummyBinanceClient())
    position = PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0,
    )

    result = executor.execute("run-1", _snapshot(), position, _decision(DecisionType.LONG))

    assert result.status.value == "simulated"
    assert result.resulting_side == PositionSide.LONG
    assert result.resulting_quantity > 0
    assert result.paper_balance == 10_000


def test_order_executor_skips_hold() -> None:
    executor = OrderExecutor(_settings(), DummyBinanceClient())
    position = PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0,
    )

    result = executor.execute("run-1", _snapshot(), position, _decision(DecisionType.HOLD))

    assert result.status.value == "skipped"
    assert result.resulting_side == PositionSide.FLAT


def test_live_order_executor_places_protective_orders() -> None:
    client = DummyBinanceClient()
    executor = OrderExecutor(_live_settings(), client)
    position = PositionState(
        mode=TradingMode.LIVE,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0,
    )

    result = executor.execute("run-1", _snapshot(), position, _decision(DecisionType.LONG))

    assert result.status.value == "filled"
    assert result.resulting_side == PositionSide.LONG
    assert result.resulting_entry_price == 60010
    assert [name for name, _ in client.calls] == [
        "cancel_all_open_orders",
        "cancel_all_algo_open_orders",
        "change_leverage",
        "create_market_order",
        "create_trigger_close_order",
        "create_trigger_close_order",
    ]
    assert client.calls[4][1]["order_type"] == "STOP_MARKET"
    assert client.calls[5][1]["order_type"] == "TAKE_PROFIT_MARKET"


def test_live_order_executor_uses_mark_price_to_meet_min_notional() -> None:
    client = DummyBinanceClient()
    executor = OrderExecutor(_live_settings(), client)
    position = PositionState(
        mode=TradingMode.LIVE,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0,
    )
    snapshot = _snapshot().model_copy(update={"current_price": 100.0, "mark_price": 101.0})
    decision = _decision(DecisionType.LONG).model_copy(
        update={
            "recommended_leverage": 1,
            "position_size_pct": 0.0005,
        }
    )

    result = executor.execute("run-1", snapshot, position, decision)

    assert result.status.value == "filled"
    market_call = [payload for name, payload in client.calls if name == "create_market_order"][0]
    assert market_call["quantity"] == 0.05


def test_order_executor_skips_same_side_reentry() -> None:
    executor = OrderExecutor(_settings(), DummyBinanceClient())
    position = PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.LONG,
        quantity=0.01,
        entry_price=59_000,
    )

    result = executor.execute("run-1", _snapshot(), position, _decision(DecisionType.LONG))

    assert result.status.value == "skipped"
    assert result.resulting_side == PositionSide.LONG
    assert result.resulting_quantity == 0.01


def test_order_executor_skips_below_minimum_filters() -> None:
    executor = OrderExecutor(_settings(), DummyBinanceClient())
    position = PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=100,
        wallet_balance=100,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0,
    )
    decision = _decision(DecisionType.LONG).model_copy(
        update={"position_size_pct": 0.0001}
    )

    result = executor.execute("run-1", _snapshot(), position, decision)

    assert result.status.value == "skipped"
    assert "minimum filters" in result.message


def test_order_executor_simulates_flip_from_long_to_short() -> None:
    executor = OrderExecutor(_settings(), DummyBinanceClient())
    position = PositionState(
        mode=TradingMode.DRY_RUN,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.LONG,
        quantity=0.02,
        entry_price=59_000,
    )

    result = executor.execute("run-1", _snapshot(), position, _decision(DecisionType.SHORT))

    assert result.status.value == "simulated"
    assert result.resulting_side == PositionSide.SHORT
    assert result.resulting_quantity < 0
    assert result.realized_pnl == 20.0
    assert result.paper_balance == 10_020


def test_live_order_executor_rolls_back_when_protective_order_fails() -> None:
    client = DummyBinanceClient(fail_on_trigger_order=True)
    executor = OrderExecutor(_live_settings(), client)
    position = PositionState(
        mode=TradingMode.LIVE,
        symbol="BTCUSDT",
        captured_at=datetime.now(tz=UTC),
        available_balance=10_000,
        wallet_balance=10_000,
        leverage=1,
        side=PositionSide.FLAT,
        quantity=0,
    )

    try:
        executor.execute("run-1", _snapshot(), position, _decision(DecisionType.LONG))
    except Exception as exc:  # noqa: BLE001
        assert "Live order execution failed" in str(exc)
    else:
        raise AssertionError("Expected live execution to fail when protective orders fail.")

    assert [name for name, _ in client.calls] == [
        "cancel_all_open_orders",
        "cancel_all_algo_open_orders",
        "change_leverage",
        "create_market_order",
        "create_trigger_close_order",
        "cancel_all_open_orders",
        "cancel_all_algo_open_orders",
        "create_market_order",
    ]
