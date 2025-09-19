from __future__ import annotations

import os
from pydantic import Field
from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv(override=False)

class Settings(BaseModel):
    symbol: str = Field(default=os.getenv("ATC_SYMBOL", "BTCUSDT"))
    interval: str = Field(default=os.getenv("ATC_INTERVAL", "1m"))
    db_path: str = Field(default=os.getenv("ATC_DB_PATH", "atc.db"))
    mode: str = Field(default=os.getenv("ATC_MODE", "paper"))  # paper | live
    market: str = Field(default=os.getenv("ATC_MARKET", "spot"))  # spot | futures

    binance_api_key: str | None = Field(default=os.getenv("BINANCE_API_KEY"))
    binance_api_secret: str | None = Field(default=os.getenv("BINANCE_API_SECRET"))

    openai_api_key: str | None = Field(default=os.getenv("OPENAI_API_KEY"))

    # Risk
    risk_budget_usdt: float | None = Field(default=(float(os.getenv("ATC_RISK_BUDGET_USDT")))
    )
    max_leverage: int = Field(default=int(os.getenv("ATC_MAX_LEVERAGE", 3)))


def get_settings() -> Settings:
    return Settings()
