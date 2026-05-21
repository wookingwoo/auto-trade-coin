from __future__ import annotations

from pymongo.errors import ConfigurationError as MongoConfigurationError
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from langchain_openai import ChatOpenAI

from app.clients.binance import BinanceFuturesClient
from app.clients.mongo import MongoDatabase
from app.config import Settings
from app.exceptions import PreflightCheckError
from app.models.enums import TradingMode


def run_preflight(settings: Settings, symbol: str) -> dict:
    """Run runtime dependency checks and raise a clear error on failure."""

    checks: dict[str, str] = {}

    validate_runtime_settings(settings)
    checks["mongodb"] = _check_mongodb(settings)
    checks["binance_public"] = _check_binance_public(settings, symbol)

    if settings.trading_mode == TradingMode.LIVE:
        checks["binance_private"] = _check_binance_private(settings)

    checks["llm"] = _check_llm(settings)
    return checks


def validate_runtime_settings(settings: Settings) -> str:
    """Validate safety-critical runtime settings before any external side effect."""

    if not settings.trading_symbols:
        raise PreflightCheckError("TRADING_SYMBOLS must contain at least one symbol.")

    if settings.default_leverage > settings.max_leverage:
        raise PreflightCheckError("DEFAULT_LEVERAGE cannot be greater than MAX_LEVERAGE.")

    if settings.protective_order_working_type not in {"MARK_PRICE", "CONTRACT_PRICE"}:
        raise PreflightCheckError("PROTECTIVE_ORDER_WORKING_TYPE must be MARK_PRICE or CONTRACT_PRICE.")

    if settings.trading_mode == TradingMode.LIVE:
        if not settings.live_trading_ack:
            raise PreflightCheckError(
                "LIVE_TRADING_ACK must be true before TRADING_MODE=live can run."
            )
        if not settings.binance_api_key or not settings.binance_api_secret:
            raise PreflightCheckError(
                "BINANCE_API_KEY and BINANCE_API_SECRET are required for TRADING_MODE=live."
            )
        if not settings.enable_protective_orders:
            raise PreflightCheckError(
                "ENABLE_PROTECTIVE_ORDERS must be true for TRADING_MODE=live."
            )
        if not settings.require_protective_order_params:
            raise PreflightCheckError(
                "REQUIRE_PROTECTIVE_ORDER_PARAMS must be true for TRADING_MODE=live."
            )

    return "ok"


def validate_dashboard_settings(settings: Settings) -> str:
    """Validate dashboard settings before starting the web server."""

    if not settings.dashboard_enabled:
        raise PreflightCheckError("DASHBOARD_ENABLED=true is required to start the dashboard.")

    if settings.dashboard_enabled and (
        not settings.dashboard_username or not settings.dashboard_password
    ):
        raise PreflightCheckError(
            "DASHBOARD_USERNAME and DASHBOARD_PASSWORD are required when DASHBOARD_ENABLED=true."
        )
    return "ok"


def _check_mongodb(settings: Settings) -> str:
    try:
        db = MongoDatabase(settings)
        db.ping()
    except MongoConfigurationError as exc:
        raise PreflightCheckError(
            "MongoDB URI is invalid or the SRV host cannot be resolved."
        ) from exc
    except OperationFailure as exc:
        raise PreflightCheckError(
            "MongoDB authentication failed. Check Atlas username/password and database user permissions."
        ) from exc
    except ServerSelectionTimeoutError as exc:
        raise PreflightCheckError(
            "MongoDB server selection timed out. Check Atlas IP access list and network reachability."
        ) from exc
    return "ok"


def _check_binance_public(settings: Settings, symbol: str) -> str:
    client = BinanceFuturesClient(settings)
    client.get_mark_price(symbol)
    return "ok"


def _check_binance_private(settings: Settings) -> str:
    client = BinanceFuturesClient(settings)
    try:
        client.get_account_information()
    except Exception as exc:  # noqa: BLE001
        raise PreflightCheckError(
            "Binance private API check failed. Verify API key, secret, and futures permissions."
        ) from exc
    return "ok"


def _check_llm(settings: Settings) -> str:
    if settings.llm_provider != "openai":
        raise PreflightCheckError(
            f"Unsupported LLM provider for preflight: {settings.llm_provider}."
        )

    if not settings.openai_api_key:
        raise PreflightCheckError("OPENAI_API_KEY is missing or empty.")

    try:
        model = ChatOpenAI(
            model=settings.llm_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )
        response = model.invoke("Reply with exactly OK")
    except Exception as exc:  # noqa: BLE001
        raise PreflightCheckError(
            "LLM provider check failed. Verify OPENAI_API_KEY and model access."
        ) from exc

    content = str(response.content).strip()
    if not content:
        raise PreflightCheckError("LLM provider returned an empty response during preflight.")
    return "ok"
