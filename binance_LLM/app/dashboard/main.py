from __future__ import annotations

import uvicorn

from app.clients.mongo import MongoDatabase
from app.config import get_settings
from app.dashboard.views import create_dashboard_app
from app.logging import setup_logging
from app.repositories.trading_repository import TradingRepository
from app.services.preflight import validate_dashboard_settings


def build_app():
    settings = get_settings()
    setup_logging(settings.log_level)
    validate_dashboard_settings(settings)
    repository = TradingRepository(MongoDatabase(settings).db)
    return create_dashboard_app(settings, repository)


app = build_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run("app.dashboard.main:app", host=settings.dashboard_host, port=settings.dashboard_port)


if __name__ == "__main__":
    main()

