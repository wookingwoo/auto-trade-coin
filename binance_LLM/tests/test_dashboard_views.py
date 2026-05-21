from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.dashboard.views import create_dashboard_app


class FakeDashboardRepository:
    def get_latest_strategy_runs(self, limit=50, symbol=None, status=None):
        return [
            {
                "run_id": "run-1",
                "symbol": "BTCUSDT",
                "status": "completed",
                "started_at": "2026-05-21T00:00:00Z",
                "metadata": {"decision": "hold", "execution_status": "skipped"},
            }
        ]

    def get_strategy_run(self, run_id: str):
        return {"run_id": run_id, "symbol": "BTCUSDT", "status": "completed"}

    def get_market_snapshot(self, run_id: str):
        return {"run_id": run_id, "current_price": 77_000}

    def get_technical_indicators_for_run(self, run_id: str):
        return {"run_id": run_id, "h1": {"rsi": 50}}

    def get_llm_decision_for_run(self, run_id: str):
        return {"run_id": run_id, "decision": "hold", "reasoning": "Signals are mixed."}

    def get_decisions_for_dashboard(self, symbol=None, limit=100):
        return [
            {
                "run_id": "run-1",
                "symbol": "BTCUSDT",
                "decision": "hold",
                "confidence": 0.7,
                "reasoning": "Signals are mixed.",
            }
        ]

    def get_trade_orders_for_dashboard(self, run_id=None, symbol=None, limit=100):
        return [{"run_id": "run-1", "symbol": "BTCUSDT", "status": "skipped"}]

    def get_positions_for_dashboard(self, symbol=None, mode=None, limit=100):
        return [{"symbol": "BTCUSDT", "mode": "dry_run", "side": "flat"}]

    def get_execution_logs_for_dashboard(self, run_id=None, symbol=None, limit=100):
        return [{"run_id": "run-1", "stage": "execution", "payload": {"message": "ok"}}]

    def get_system_config(self):
        return {
            "config_key": "runtime_settings",
            "openai_api_key": "secret-key",
            "mongodb_uri": "mongodb+srv://user:password@example.net",
            "trading_mode": "dry_run",
        }


def _client() -> TestClient:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        dashboard_enabled=True,
        dashboard_username="operator",
        dashboard_password="secret",
    )
    return TestClient(create_dashboard_app(settings, FakeDashboardRepository()))


def test_dashboard_requires_authentication() -> None:
    response = _client().get("/dashboard")

    assert response.status_code == 401


def test_dashboard_overview_renders_recent_state_and_masks_secrets() -> None:
    response = _client().get("/dashboard", auth=("operator", "secret"))

    assert response.status_code == 200
    assert "BTCUSDT" in response.text
    assert "run-1" in response.text
    assert "secret-key" not in response.text
    assert "password@example.net" not in response.text


def test_dashboard_run_detail_renders_decision_context() -> None:
    response = _client().get("/runs/run-1", auth=("operator", "secret"))

    assert response.status_code == 200
    assert "Signals are mixed." in response.text
    assert "77000" in response.text


def test_dashboard_index_routes_render_authenticated_pages() -> None:
    client = _client()

    for path in ("/runs", "/decisions", "/orders", "/positions"):
        response = client.get(path, auth=("operator", "secret"))

        assert response.status_code == 200
