from __future__ import annotations

from app.config import Settings
from app.exceptions import OrderExecutionError
from app.models.market import SymbolRules
from app.services.live_smoke_order import LiveSmokeOrderRequest, LiveSmokeOrderService


class FakeSmokeBinanceClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.position_amt = "0"
        self.open_orders: list[dict] = []
        self.open_algo_orders: list[dict] = []
        self.fail_trigger_after = 0
        self.trigger_count = 0

    def get_account_information(self) -> dict:
        return {"availableBalance": "100", "totalWalletBalance": "100"}

    def get_position_risk(self, symbol: str) -> list[dict]:
        return [
            {
                "symbol": symbol,
                "positionAmt": self.position_amt,
                "notional": "0",
            }
        ]

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        return SymbolRules(
            symbol=symbol,
            tick_size=0.1,
            step_size=0.001,
            min_qty=0.001,
            min_notional=50.0,
            price_precision=2,
            quantity_precision=3,
        )

    def get_mark_price(self, symbol: str) -> dict:
        return {"mark_price": 77_000.0, "last_funding_rate": 0.0, "next_funding_time": 0}

    def get_open_orders(self, symbol: str) -> list[dict]:
        return self.open_orders

    def get_open_algo_orders(self, symbol: str) -> list[dict]:
        return self.open_algo_orders

    def cancel_all_open_orders(self, symbol: str) -> dict:
        self.calls.append(("cancel_all_open_orders", {"symbol": symbol}))
        return {"code": 200}

    def cancel_all_algo_open_orders(self, symbol: str) -> dict:
        self.calls.append(("cancel_all_algo_open_orders", {"symbol": symbol}))
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
            "avgPrice": "77000",
            "orderId": len(self.calls) + 1,
        }
        self.calls.append(("create_market_order", payload))
        return payload

    def create_trigger_close_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        stop_price: float,
        client_order_id: str,
        working_type: str = "MARK_PRICE",
    ) -> dict:
        self.trigger_count += 1
        payload = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "stop_price": stop_price,
            "client_order_id": client_order_id,
            "working_type": working_type,
            "algoId": len(self.calls) + 1,
        }
        self.calls.append(("create_trigger_close_order", payload))
        if self.fail_trigger_after and self.trigger_count >= self.fail_trigger_after:
            raise RuntimeError("trigger failed")
        return payload

    def cancel_algo_order(self, client_algo_id: str) -> dict:
        payload = {"client_algo_id": client_algo_id}
        self.calls.append(("cancel_algo_order", payload))
        return {"code": 200}


def _settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        trading_mode="live",
        trading_symbols=["BTCUSDT"],
        live_trading_ack=True,
        binance_api_key="binance-key",
        binance_api_secret="binance-secret",
        enable_protective_orders=True,
        require_protective_order_params=True,
        max_leverage=3,
    )


def _request(**updates) -> LiveSmokeOrderRequest:
    data = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "max_notional": 80.0,
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.02,
        "cancel_existing_orders": False,
    }
    data.update(updates)
    return LiveSmokeOrderRequest(**data)


def test_live_smoke_order_rejects_existing_orders_when_not_allowed_to_cancel() -> None:
    client = FakeSmokeBinanceClient()
    client.open_orders = [{"orderId": 123}]
    service = LiveSmokeOrderService(_settings(), client)

    try:
        service.execute(_request())
    except OrderExecutionError as exc:
        assert "existing BTCUSDT open orders" in str(exc)
    else:
        raise AssertionError("Expected live smoke order to abort.")

    assert client.calls == []


def test_live_smoke_order_always_rejects_existing_position() -> None:
    client = FakeSmokeBinanceClient()
    client.position_amt = "0.001"
    service = LiveSmokeOrderService(_settings(), client)

    try:
        service.execute(_request(cancel_existing_orders=True))
    except OrderExecutionError as exc:
        assert "Existing BTCUSDT position" in str(exc)
    else:
        raise AssertionError("Expected live smoke order to abort.")

    assert client.calls == []


def test_live_smoke_order_rejects_notional_below_symbol_filters() -> None:
    client = FakeSmokeBinanceClient()
    service = LiveSmokeOrderService(_settings(), client)

    try:
        service.execute(_request(max_notional=6.0))
    except OrderExecutionError as exc:
        assert "below Binance minimum filters" in str(exc)
    else:
        raise AssertionError("Expected live smoke order to abort.")

    assert client.calls == []


def test_live_smoke_order_places_entry_and_protective_orders_without_canceling_existing_orders() -> None:
    client = FakeSmokeBinanceClient()
    service = LiveSmokeOrderService(_settings(), client)

    result = service.execute(_request())

    assert result.status == "filled"
    assert result.quantity == 0.001
    assert result.notional <= 80.0
    assert [name for name, _ in client.calls] == [
        "change_leverage",
        "create_market_order",
        "create_trigger_close_order",
        "create_trigger_close_order",
    ]
    assert client.calls[1][1]["side"] == "BUY"
    assert client.calls[2][1]["side"] == "SELL"
    assert client.calls[2][1]["order_type"] == "STOP_MARKET"
    assert client.calls[3][1]["order_type"] == "TAKE_PROFIT_MARKET"


def test_live_smoke_order_rolls_back_created_resources_without_canceling_unrelated_orders() -> None:
    client = FakeSmokeBinanceClient()
    client.fail_trigger_after = 2
    service = LiveSmokeOrderService(_settings(), client)

    try:
        service.execute(_request())
    except OrderExecutionError as exc:
        assert "Live smoke order failed" in str(exc)
    else:
        raise AssertionError("Expected live smoke order to fail.")

    assert [name for name, _ in client.calls] == [
        "change_leverage",
        "create_market_order",
        "create_trigger_close_order",
        "create_trigger_close_order",
        "cancel_algo_order",
        "create_market_order",
    ]
    assert client.calls[-1][1]["side"] == "SELL"
    assert client.calls[-1][1]["reduce_only"] is True
