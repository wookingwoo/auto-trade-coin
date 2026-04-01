from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.models.enums import TradingMode


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="auto-trade-coin", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    trading_mode: TradingMode = Field(default=TradingMode.DRY_RUN, alias="TRADING_MODE")
    trading_symbols: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["BTCUSDT"],
        alias="TRADING_SYMBOLS",
    )
    binance_base_url: str = Field(default="https://fapi.binance.com", alias="BINANCE_BASE_URL")
    binance_api_key: str | None = Field(default=None, alias="BINANCE_API_KEY")
    binance_api_secret: str | None = Field(default=None, alias="BINANCE_API_SECRET")
    default_leverage: int = Field(default=2, alias="DEFAULT_LEVERAGE")
    max_position_size_pct: float = Field(default=0.10, alias="MAX_POSITION_SIZE_PCT")
    paper_starting_balance: float = Field(default=10_000.0, alias="PAPER_STARTING_BALANCE")
    enable_protective_orders: bool = Field(default=True, alias="ENABLE_PROTECTIVE_ORDERS")
    protective_order_working_type: str = Field(default="MARK_PRICE", alias="PROTECTIVE_ORDER_WORKING_TYPE")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="auto_trade_coin", alias="MONGODB_DB_NAME")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    langsmith_api_key: str | None = Field(default=None, alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="auto-trade-coin", alias="LANGSMITH_PROJECT")
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")

    news_headline_limit: int = Field(default=5, alias="NEWS_HEADLINE_LIMIT")
    news_rss_urls: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["https://www.coindesk.com/arc/outboundfeeds/rss/"],
        alias="NEWS_RSS_URLS",
    )
    fear_greed_api_url: str = Field(
        default="https://api.alternative.me/fng/?limit=1",
        alias="FEAR_GREED_API_URL",
    )
    decision_history_limit: int = Field(default=5, alias="DECISION_HISTORY_LIMIT")
    run_interval_minutes: int = Field(default=60, alias="RUN_INTERVAL_MINUTES")

    @field_validator("trading_symbols", mode="before")
    @classmethod
    def parse_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]

    @field_validator("news_rss_urls", mode="before")
    @classmethod
    def parse_urls(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
