from __future__ import annotations

from datetime import UTC, datetime, timedelta


def floor_to_interval(run_at: datetime, interval_minutes: int) -> datetime:
    """Floor a timestamp to the configured run interval."""

    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=UTC)
    run_at = run_at.astimezone(UTC)
    interval_seconds = interval_minutes * 60
    day_start = run_at.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_since_day_start = int((run_at - day_start).total_seconds())
    floored_seconds = (seconds_since_day_start // interval_seconds) * interval_seconds
    return day_start + timedelta(seconds=floored_seconds)


def build_run_idempotency_key(symbol: str, mode: str, run_at: datetime, interval_minutes: int) -> str:
    """Build a deterministic key for one scheduler slot."""

    slot = floor_to_interval(run_at, interval_minutes)
    return f"{mode}:{symbol}:{slot.isoformat()}"

