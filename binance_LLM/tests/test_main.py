from __future__ import annotations

import json

from app.config import Settings
from app.exceptions import OrderExecutionError
from app.services.live_smoke_order import LiveSmokeOrderResult


def test_main_runs_live_smoke_order(monkeypatch, capsys) -> None:
    from app import main as app_main

    captured = {}

    class FakeClient:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

    class FakeService:
        def __init__(self, settings: Settings, client: FakeClient) -> None:
            self.settings = settings
            self.client = client

        def execute(self, request):
            captured["request"] = request
            return LiveSmokeOrderResult(
                status="filled",
                symbol=request.symbol,
                side=request.side,
                quantity=0.001,
                entry_price=77_000,
                notional=77.0,
                stop_loss_price=76_230,
                take_profit_price=78_540,
                client_order_id="smoke-open-test",
                protective_client_order_ids=["smoke-sl-test", "smoke-tp-test"],
                responses=[],
                executed_at="2026-05-21T00:00:00Z",
            )

    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        trading_mode="live",
        live_trading_ack=True,
        binance_api_key="binance-key",
        binance_api_secret="binance-secret",
    )
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(app_main, "setup_logging", lambda level: None)
    monkeypatch.setattr(app_main, "BinanceFuturesClient", FakeClient)
    monkeypatch.setattr(app_main, "LiveSmokeOrderService", FakeService)
    monkeypatch.setattr(
        "sys.argv",
        [
            "app.main",
            "--live-smoke-order",
            "--symbol",
            "btcusdt",
            "--side",
            "BUY",
            "--max-notional",
            "80",
            "--stop-loss-pct",
            "0.01",
            "--take-profit-pct",
            "0.02",
            "--cancel-existing-orders",
            "false",
        ],
    )

    app_main.main()

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "filled"
    assert output["symbol"] == "BTCUSDT"
    assert captured["request"].symbol == "BTCUSDT"
    assert captured["request"].side == "BUY"
    assert captured["request"].max_notional == 80
    assert captured["request"].cancel_existing_orders is False


def test_main_prints_json_failure_when_live_smoke_order_aborts(monkeypatch, capsys) -> None:
    from app import main as app_main

    class FakeClient:
        def __init__(self, settings: Settings) -> None:
            self.settings = settings

    class FakeService:
        def __init__(self, settings: Settings, client: FakeClient) -> None:
            self.settings = settings
            self.client = client

        def execute(self, request):
            raise OrderExecutionError("below Binance minimum filters")

    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        trading_mode="live",
        live_trading_ack=True,
        binance_api_key="binance-key",
        binance_api_secret="binance-secret",
    )
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(app_main, "setup_logging", lambda level: None)
    monkeypatch.setattr(app_main, "BinanceFuturesClient", FakeClient)
    monkeypatch.setattr(app_main, "LiveSmokeOrderService", FakeService)
    monkeypatch.setattr(
        "sys.argv",
        [
            "app.main",
            "--live-smoke-order",
            "--symbol",
            "BTCUSDT",
            "--side",
            "BUY",
            "--max-notional",
            "6",
            "--stop-loss-pct",
            "0.01",
            "--take-profit-pct",
            "0.02",
        ],
    )

    try:
        app_main.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("Expected smoke order failure to exit non-zero.")

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "status": "failed",
        "error": "below Binance minimum filters",
    }
