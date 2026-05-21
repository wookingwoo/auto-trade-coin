from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.dashboard.auth import require_dashboard_user


def _settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        dashboard_enabled=True,
        dashboard_username="operator",
        dashboard_password="secret",
    )


def test_dashboard_basic_auth_rejects_missing_credentials() -> None:
    app = FastAPI()
    settings = _settings()

    @app.get("/protected")
    def protected(_=Depends(require_dashboard_user(settings))):
        return {"ok": True}

    response = TestClient(app).get("/protected")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_dashboard_basic_auth_accepts_valid_credentials() -> None:
    app = FastAPI()
    settings = _settings()

    @app.get("/protected")
    def protected(_=Depends(require_dashboard_user(settings))):
        return {"ok": True}

    response = TestClient(app).get("/protected", auth=("operator", "secret"))

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_dashboard_basic_auth_rejects_empty_configured_credentials() -> None:
    app = FastAPI()
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        openai_api_key="test-key",
        dashboard_enabled=False,
        dashboard_username="",
        dashboard_password="",
    )

    @app.get("/protected")
    def protected(_=Depends(require_dashboard_user(settings))):
        return {"ok": True}

    response = TestClient(app).get("/protected", auth=("", ""))

    assert response.status_code == 401
