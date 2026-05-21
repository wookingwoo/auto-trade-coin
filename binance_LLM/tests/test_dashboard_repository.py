from __future__ import annotations

from app.repositories.trading_repository import TradingRepository


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.sort_args = None
        self.limit_value = None

    def sort(self, *args):
        self.sort_args = args
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def __iter__(self):
        return iter(self.docs[: self.limit_value])


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = docs or []
        self.find_calls: list[dict] = []
        self.find_one_calls: list[dict] = []
        self.last_cursor: FakeCursor | None = None

    def create_index(self, *args, **kwargs):
        return None

    def find(self, query=None):
        self.find_calls.append(query or {})
        self.last_cursor = FakeCursor(self.docs)
        return self.last_cursor

    def find_one(self, query=None, *args, **kwargs):
        self.find_one_calls.append(query or {})
        return self.docs[0] if self.docs else None


class FakeDatabase(dict):
    def __getitem__(self, name: str):
        if name not in self:
            self[name] = FakeCollection()
        return dict.__getitem__(self, name)


def _repo() -> TradingRepository:
    db = FakeDatabase()
    db["strategy_runs"] = FakeCollection([{"run_id": "run-1", "symbol": "BTCUSDT"}])
    db["market_snapshots"] = FakeCollection([{"run_id": "run-1", "current_price": 100}])
    db["technical_indicators"] = FakeCollection([{"run_id": "run-1"}])
    db["llm_decisions"] = FakeCollection([{"run_id": "run-1", "decision": "hold"}])
    db["trade_orders"] = FakeCollection([{"run_id": "run-1", "symbol": "BTCUSDT"}])
    db["positions"] = FakeCollection([{"symbol": "BTCUSDT", "mode": "dry_run"}])
    db["execution_logs"] = FakeCollection([{"run_id": "run-1", "stage": "error"}])
    db["system_configs"] = FakeCollection([{"config_key": "runtime_settings"}])
    return TradingRepository(db)


def test_dashboard_repository_lists_latest_strategy_runs_with_filters() -> None:
    repo = _repo()

    result = repo.get_latest_strategy_runs(limit=25, symbol="BTCUSDT", status="completed")

    assert result == [{"run_id": "run-1", "symbol": "BTCUSDT"}]
    assert repo.strategy_runs.find_calls[-1] == {"symbol": "BTCUSDT", "status": "completed"}
    assert repo.strategy_runs.last_cursor.limit_value == 25


def test_dashboard_repository_gets_run_related_documents() -> None:
    repo = _repo()

    assert repo.get_strategy_run("run-1")["run_id"] == "run-1"
    assert repo.get_market_snapshot("run-1")["current_price"] == 100
    assert repo.get_technical_indicators_for_run("run-1")["run_id"] == "run-1"
    assert repo.get_llm_decision_for_run("run-1")["decision"] == "hold"
    assert repo.get_system_config()["config_key"] == "runtime_settings"


def test_dashboard_repository_lists_decisions_for_dashboard() -> None:
    repo = _repo()

    result = repo.get_decisions_for_dashboard(symbol="BTCUSDT", limit=12)

    assert result == [{"run_id": "run-1", "decision": "hold"}]
    assert repo.llm_decisions.find_calls[-1] == {"symbol": "BTCUSDT"}
    assert repo.llm_decisions.last_cursor.limit_value == 12


def test_dashboard_repository_lists_orders_positions_and_logs() -> None:
    repo = _repo()

    assert repo.get_trade_orders_for_dashboard(run_id="run-1", symbol="BTCUSDT", limit=10)
    assert repo.trade_orders.find_calls[-1] == {"run_id": "run-1", "symbol": "BTCUSDT"}
    assert repo.trade_orders.last_cursor.limit_value == 10

    assert repo.get_positions_for_dashboard(symbol="BTCUSDT", mode="dry_run", limit=5)
    assert repo.positions.find_calls[-1] == {"symbol": "BTCUSDT", "mode": "dry_run"}
    assert repo.positions.last_cursor.limit_value == 5

    assert repo.get_execution_logs_for_dashboard(run_id="run-1", symbol="BTCUSDT", limit=7)
    assert repo.execution_logs.find_calls[-1] == {"run_id": "run-1", "symbol": "BTCUSDT"}
    assert repo.execution_logs.last_cursor.limit_value == 7
