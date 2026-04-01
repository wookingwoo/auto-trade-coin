from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from app.main import build_orchestrator


def run_scheduler() -> None:
    """Run the orchestrator on a fixed interval."""

    settings, orchestrator = build_orchestrator()
    scheduler = BlockingScheduler(timezone=UTC)

    scheduler.add_job(
        lambda: [orchestrator.run_once(symbol) for symbol in settings.trading_symbols],
        trigger="interval",
        minutes=settings.run_interval_minutes,
        next_run_time=datetime.now(tz=UTC),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


if __name__ == "__main__":
    run_scheduler()

