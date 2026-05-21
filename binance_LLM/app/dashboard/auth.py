from __future__ import annotations

import secrets
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import Settings


security = HTTPBasic()


def require_dashboard_user(settings: Settings) -> Callable:
    """Return a FastAPI dependency that enforces dashboard Basic Auth."""

    def _authenticate(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
        expected_username = settings.dashboard_username or ""
        expected_password = settings.dashboard_password or ""
        if not expected_username or not expected_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dashboard credentials are not configured.",
                headers={"WWW-Authenticate": "Basic"},
            )
        username_ok = secrets.compare_digest(credentials.username, expected_username)
        password_ok = secrets.compare_digest(credentials.password, expected_password)
        if not (username_ok and password_ok):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid dashboard credentials.",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    return _authenticate
