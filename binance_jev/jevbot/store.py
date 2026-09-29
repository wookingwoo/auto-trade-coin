from __future__ import annotations

import json
import sqlite3
import time
from decimal import Decimal
from pathlib import Path


class Journal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS intents (
            slot_key TEXT PRIMARY KEY, client_id TEXT NOT NULL UNIQUE, symbol TEXT NOT NULL,
            side TEXT NOT NULL, quantity TEXT NOT NULL, stop_price TEXT NOT NULL,
            take_price TEXT NOT NULL, status TEXT NOT NULL, created_ms INTEGER NOT NULL,
            updated_ms INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at_ms INTEGER NOT NULL,
            kind TEXT NOT NULL, details TEXT NOT NULL)""")

    def close(self) -> None:
        self.db.close()

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def get_decimal(self, key: str) -> Decimal | None:
        value = self.get(key)
        return Decimal(value) if value is not None else None

    def bind_environment(self, mode: str) -> None:
        if mode not in ("paper", "testnet", "live"):
            raise ValueError("invalid environment")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.get("environment")
            if existing is not None and existing != mode:
                raise ValueError(f"database belongs to {existing}, not {mode}")
            if existing is None and self.get("initial_equity") is not None:
                raise ValueError("legacy database has no environment binding")
            now = int(time.time() * 1000)
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('environment',?)", (mode,))
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('started_ms',?)", (str(now),))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def set(self, key: str, value: object) -> None:
        self.db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def initialize(self, initial_equity: Decimal, day_key: str) -> None:
        if initial_equity <= 0:
            raise ValueError("initial equity must be positive")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('initial_equity',?)", (str(initial_equity),))
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('day_key',?)", (day_key,))
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('day_start_equity',?)", (str(initial_equity),))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def roll_day(self, day_key: str, current_equity: Decimal) -> None:
        if self.get("day_key") == day_key:
            return
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO meta VALUES('day_key',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (day_key,))
            self.db.execute("INSERT INTO meta VALUES('day_start_equity',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(current_equity),))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def halt(self, reason: str) -> None:
        self.set("halt_reason", reason)
        self.event("halt", {"reason": reason})

    def begin_intent(self, slot_key: str, client_id: str, symbol: str, side: str, quantity: str, stop_price: str, take_price: str) -> bool:
        now = int(time.time() * 1000)
        try:
            self.db.execute("INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?)", (
                slot_key, client_id, symbol, side, quantity, stop_price, take_price, "INTENT", now, now,
            ))
        except sqlite3.IntegrityError:
            return False
        return True

    def intent(self, slot_key: str) -> dict | None:
        row = self.db.execute("SELECT * FROM intents WHERE slot_key=?", (slot_key,)).fetchone()
        return dict(row) if row else None

    def pending_intents(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM intents WHERE status IN ('INTENT','UNKNOWN','ENTERING','PROTECTING','EXITING') ORDER BY created_ms").fetchall()
        return [dict(row) for row in rows]

    def update_intent(self, slot_key: str, status: str) -> None:
        result = self.db.execute("UPDATE intents SET status=?,updated_ms=? WHERE slot_key=?", (status, int(time.time() * 1000), slot_key))
        if result.rowcount != 1:
            raise LookupError(f"intent not found: {slot_key}")

    def latest_protected_intent(self, symbol: str) -> dict | None:
        row = self.db.execute("SELECT * FROM intents WHERE symbol=? AND status IN ('PROTECTED','PROTECTING','ENTERING','UNKNOWN','EXITING') ORDER BY created_ms DESC LIMIT 1", (symbol,)).fetchone()
        return dict(row) if row else None

    def event(self, kind: str, details: dict) -> None:
        self.db.execute("INSERT INTO events(at_ms,kind,details) VALUES(?,?,?)", (
            int(time.time() * 1000), kind, json.dumps(details, ensure_ascii=False, default=str),
        ))

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) | {"details": json.loads(row["details"])} for row in rows]
