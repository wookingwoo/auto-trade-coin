from __future__ import annotations

import argparse
import json

from app.clients.binance import BinanceFuturesClient
from app.clients.mongo import MongoDatabase
from app.config import Settings, get_settings
from app.exceptions import PreflightCheckError
from app.logging import setup_logging
from app.repositories.trading_repository import TradingRepository
from app.services.market_data import BinanceMarketDataService
from app.services.news_signal import NewsSignalService
from app.services.order_executor import OrderExecutor
from app.services.position_manager import PositionManager
from app.services.preflight import run_preflight, validate_runtime_settings
from app.services.technical_indicators import TechnicalIndicatorService
from app.services.trading_context_builder import TradingContextBuilder
from app.services.trading_decision_agent import TradingDecisionAgent
from app.services.trading_orchestrator import TradingOrchestrator


def build_orchestrator() -> tuple[Settings, TradingOrchestrator]:
    """Build the orchestrator with all required dependencies."""

    settings = get_settings()
    setup_logging(settings.log_level)
    validate_runtime_settings(settings)

    mongo = MongoDatabase(settings)
    repository = TradingRepository(mongo.db)
    binance_client = BinanceFuturesClient(settings)

    orchestrator = TradingOrchestrator(
        settings=settings,
        repository=repository,
        market_service=BinanceMarketDataService(binance_client),
        indicator_service=TechnicalIndicatorService(),
        news_service=NewsSignalService(settings),
        position_manager=PositionManager(settings, repository, binance_client),
        context_builder=TradingContextBuilder(),
        decision_agent=TradingDecisionAgent(settings),
        order_executor=OrderExecutor(settings, binance_client),
    )
    return settings, orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the trading orchestrator once.")
    parser.add_argument("--once", action="store_true", help="Run the pipeline once and exit.")
    parser.add_argument("--symbol", help="Optional single symbol override.")
    parser.add_argument("--preflight", action="store_true", help="Run dependency preflight checks and exit.")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)
    symbols = [args.symbol.upper()] if args.symbol else settings.trading_symbols

    if args.preflight:
        try:
            result = run_preflight(settings, symbols[0])
        except PreflightCheckError as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}))
            raise SystemExit(1) from exc
        print(json.dumps({"status": "ok", "checks": result}))
        return

    _, orchestrator = build_orchestrator()

    for symbol in symbols:
        orchestrator.run_once(symbol)


if __name__ == "__main__":
    main()
