class TradingSystemError(Exception):
    """Base exception for the trading system."""


class DataCollectionError(TradingSystemError):
    """Raised when market or external data cannot be collected."""


class LLMDecisionError(TradingSystemError):
    """Raised when the LLM cannot return a valid decision."""


class OrderExecutionError(TradingSystemError):
    """Raised when an order cannot be executed."""


class BinanceAPIError(TradingSystemError):
    """Raised when Binance returns an error response."""


class PreflightCheckError(TradingSystemError):
    """Raised when a runtime dependency preflight check fails."""
