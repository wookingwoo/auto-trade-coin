from enum import Enum


class TradingMode(str, Enum):
    DRY_RUN = "dry_run"
    LIVE = "live"


class DecisionType(str, Enum):
    LONG = "long"
    SHORT = "short"
    HOLD = "hold"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class OrderStatus(str, Enum):
    FILLED = "filled"
    FAILED = "failed"
    SKIPPED = "skipped"
    SIMULATED = "simulated"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"

