from __future__ import annotations

import pytest

from app.config import Settings
from app.exceptions import PreflightCheckError
from app.models.enums import TradingMode
from app.services import preflight


def test_preflight_rejects_unsupported_provider() -> None:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        llm_provider="unsupported",
        openai_api_key="dummy",
    )

    with pytest.raises(PreflightCheckError, match="Unsupported LLM provider"):
        preflight._check_llm(settings)


def test_preflight_requires_openai_key() -> None:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        llm_provider="openai",
        openai_api_key="",
    )

    with pytest.raises(PreflightCheckError, match="OPENAI_API_KEY is missing or empty"):
        preflight._check_llm(settings)


def test_run_preflight_includes_live_private_check(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        llm_provider="openai",
        openai_api_key="dummy",
        trading_mode=TradingMode.LIVE,
    )
    called = {"mongodb": 0, "public": 0, "private": 0, "llm": 0}

    monkeypatch.setattr(preflight, "_check_mongodb", lambda s: called.__setitem__("mongodb", called["mongodb"] + 1) or "ok")
    monkeypatch.setattr(preflight, "_check_binance_public", lambda s, symbol: called.__setitem__("public", called["public"] + 1) or "ok")
    monkeypatch.setattr(preflight, "_check_binance_private", lambda s: called.__setitem__("private", called["private"] + 1) or "ok")
    monkeypatch.setattr(preflight, "_check_llm", lambda s: called.__setitem__("llm", called["llm"] + 1) or "ok")

    result = preflight.run_preflight(settings, "BTCUSDT")

    assert result == {
        "mongodb": "ok",
        "binance_public": "ok",
        "binance_private": "ok",
        "llm": "ok",
    }
    assert called == {"mongodb": 1, "public": 1, "private": 1, "llm": 1}

