from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.dashboard.auth import require_dashboard_user


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["pretty_json"] = lambda value: json.dumps(
    {} if value is None else value,
    ensure_ascii=False,
    indent=2,
    default=str,
)


def create_dashboard_app(settings: Settings, repository) -> FastAPI:
    """Create the read-only dashboard application."""

    app = FastAPI(title="Auto Trade Coin Dashboard")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    auth_dependency = Depends(require_dashboard_user(settings))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse("/dashboard")

    @app.get("/dashboard")
    def dashboard(request: Request, _user: str = auth_dependency):
        runs = repository.get_latest_strategy_runs(limit=10)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "title": "Dashboard",
                "config": _mask_mapping(repository.get_system_config() or {}),
                "runs": runs,
                "decisions": _recent_decisions(repository, limit=10),
                "orders": repository.get_trade_orders_for_dashboard(limit=10),
                "positions": repository.get_positions_for_dashboard(limit=10),
                "errors": [
                    item
                    for item in repository.get_execution_logs_for_dashboard(limit=20)
                    if item.get("stage") == "error"
                ],
            },
        )

    @app.get("/runs")
    def runs(request: Request, symbol: str | None = None, status: str | None = None, _user: str = auth_dependency):
        return templates.TemplateResponse(
            request,
            "runs.html",
            {
                "title": "Runs",
                "runs": repository.get_latest_strategy_runs(limit=100, symbol=symbol, status=status),
                "symbol": symbol or "",
                "status": status or "",
            },
        )

    @app.get("/runs/{run_id}")
    def run_detail(run_id: str, request: Request, _user: str = auth_dependency):
        return templates.TemplateResponse(
            request,
            "run_detail.html",
            {
                "title": f"Run {run_id}",
                "run": repository.get_strategy_run(run_id),
                "snapshot": repository.get_market_snapshot(run_id),
                "indicators": repository.get_technical_indicators_for_run(run_id),
                "decision": repository.get_llm_decision_for_run(run_id),
                "orders": repository.get_trade_orders_for_dashboard(run_id=run_id, limit=100),
                "logs": repository.get_execution_logs_for_dashboard(run_id=run_id, limit=100),
            },
        )

    @app.get("/decisions")
    def decisions(request: Request, symbol: str | None = None, _user: str = auth_dependency):
        return templates.TemplateResponse(
            request,
            "decisions.html",
            {
                "title": "Decisions",
                "decisions": _recent_decisions(repository, limit=100, symbol=symbol),
                "symbol": symbol or "",
            },
        )

    @app.get("/orders")
    def orders(request: Request, symbol: str | None = None, _user: str = auth_dependency):
        return templates.TemplateResponse(
            request,
            "orders.html",
            {
                "title": "Orders",
                "orders": repository.get_trade_orders_for_dashboard(symbol=symbol, limit=100),
                "symbol": symbol or "",
            },
        )

    @app.get("/positions")
    def positions(request: Request, symbol: str | None = None, mode: str | None = None, _user: str = auth_dependency):
        return templates.TemplateResponse(
            request,
            "positions.html",
            {
                "title": "Positions",
                "positions": repository.get_positions_for_dashboard(symbol=symbol, mode=mode, limit=100),
                "symbol": symbol or "",
                "mode": mode or "",
            },
        )

    return app


def _recent_decisions(repository, limit: int, symbol: str | None = None) -> list[dict]:
    if hasattr(repository, "get_decisions_for_dashboard"):
        return repository.get_decisions_for_dashboard(symbol=symbol, limit=limit)
    if hasattr(repository, "llm_decisions"):
        query = _compact_query({"symbol": symbol})
        cursor = repository.llm_decisions.find(query).sort("created_at", -1).limit(limit)
        return list(cursor)
    return []


def _mask_mapping(value: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, item in value.items():
        lower = key.lower()
        if "key" in lower or "secret" in lower or "password" in lower or "uri" in lower:
            masked[key] = "***"
        elif isinstance(item, dict):
            masked[key] = _mask_mapping(item)
        else:
            masked[key] = item
    return masked


def _compact_query(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}
