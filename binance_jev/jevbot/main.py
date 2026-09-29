from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .binance import BinanceFutures
from .paper import PaperFutures
from .runner import Settings, TradingRunner
from .store import Journal


def apply_control(journal: Journal, command: str) -> None:
    if command == "pause":
        journal.set("paused", "1")
        journal.event("operator", {"command": command})
    elif command == "resume":
        journal.set("paused", "0")
        journal.event("operator", {"command": command})
    elif command == "flatten-and-halt":
        journal.set("command", "flatten_and_halt")
        journal.event("operator", {"command": command})
    else:
        raise ValueError("unknown command")


def status_payload(path: Path) -> dict:
    journal = Journal(path)
    try:
        return {
            "equity_usdt": journal.get("equity"),
            "initial_equity_usdt": journal.get("initial_equity"),
            "day_start_equity_usdt": journal.get("day_start_equity"),
            "halt_reason": journal.get("halt_reason"),
            "paused": journal.get("paused") == "1",
            "open_slot": journal.get("open_slot"),
            "last_account_ms": journal.get("last_account_ms"),
            "last_slot": journal.get("last_slot"),
            "recent_events": journal.recent_events(20),
        }
    finally:
        journal.close()


@contextmanager
def execution_lock(db_path: Path):
    path = db_path.with_suffix(db_path.suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        handle.close()


def _status_server(path: Path, token: str, host: str, port: int) -> ThreadingHTTPServer:
    class StatusHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            authorization = self.headers.get("Authorization", "")
            if not hmac.compare_digest(authorization, "Bearer " + token):
                self.send_error(401)
                return
            if self.path != "/status":
                self.send_error(404)
                return
            body = json.dumps(status_payload(path), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((host, port), StatusHandler)


def run() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    settings = Settings.from_env()
    import typesafe_sdk  # noqa: F401 - fail startup if the official SDK is unavailable

    early_journal = Journal(settings.db_path)
    try:
        early_journal.bind_environment(settings.mode)
    finally:
        early_journal.close()

    if settings.mode == "testnet":
        exchange = BinanceFutures(settings.api_key, settings.api_secret, "https://demo-fapi.binance.com")
    elif settings.mode == "live":
        exchange = BinanceFutures(settings.api_key, settings.api_secret)
    else:
        starting = os.getenv("JEVBOT_PAPER_START_USDT")
        if not starting:
            raise ValueError("paper mode requires JEVBOT_PAPER_START_USDT")
        exchange = PaperFutures(BinanceFutures("", ""), settings.db_path, Decimal(starting))
    journal = Journal(settings.db_path)
    server = None
    try:
        with execution_lock(settings.db_path):
            token = os.getenv("JEVBOT_DASHBOARD_TOKEN", "")
            if token:
                if len(token) < 24:
                    raise ValueError("dashboard token needs at least 24 characters")
                host = os.getenv("JEVBOT_DASHBOARD_HOST", "127.0.0.1")
                server = _status_server(settings.db_path, token, host, int(os.getenv("JEVBOT_DASHBOARD_PORT", "8765")))
                threading.Thread(target=server.serve_forever, daemon=True, name="status-http").start()
            runner = TradingRunner(settings, exchange, journal)
            try:
                runner.run_forever()
            except KeyboardInterrupt:
                runner.stop_event.set()
                return 0
    finally:
        if server:
            server.shutdown()
            server.server_close()
        journal.close()
        exchange.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(prog="jevbot")
    parser.add_argument("command", choices=("run", "status", "health", "pause", "resume", "flatten-and-halt"))
    args = parser.parse_args(argv)
    if args.command == "run":
        return run()
    path = Path(os.getenv("JEVBOT_DB_PATH", "data/jevbot.db"))
    if args.command == "status":
        print(json.dumps(status_payload(path), ensure_ascii=False, indent=2))
        return 0
    if args.command == "health":
        payload = status_payload(path)
        updated = payload["last_account_ms"]
        return 0 if updated and int(time.time() * 1000) - int(updated) < 15_000 else 1
    journal = Journal(path)
    try:
        apply_control(journal, args.command)
    finally:
        journal.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
