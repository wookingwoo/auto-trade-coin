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

    checks["mongodb"] = _check_mongodb(settings)
    checks["binance_public"] = _check_binance_public(settings, symbol)

    if settings.trading_mode == TradingMode.LIVE:
        checks["binance_private"] = _check_binance_private(settings)

    checks["llm"] = _check_llm(settings)
    return checks


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
