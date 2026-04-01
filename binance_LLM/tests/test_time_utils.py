from __future__ import annotations

from datetime import UTC, datetime

from app.utils.time import build_run_idempotency_key, floor_to_interval


def test_floor_to_interval_uses_scheduler_slot() -> None:
    run_at = datetime(2026, 4, 1, 12, 34, 56, tzinfo=UTC)
    floored = floor_to_interval(run_at, 60)

    assert floored == datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


def test_build_run_idempotency_key_is_deterministic() -> None:
    run_at = datetime(2026, 4, 1, 12, 34, 56, tzinfo=UTC)
    key = build_run_idempotency_key("BTCUSDT", "dry_run", run_at, 60)

    assert key == "dry_run:BTCUSDT:2026-04-01T12:00:00+00:00"
