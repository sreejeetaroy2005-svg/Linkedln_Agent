"""SQLite storage primitives with explicit transactions and timezone-aware day keys."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from app.config import settings


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = str(db_path or settings.database_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(db_path: str | Path | None = None, immediate: bool = False) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    with transaction(db_path, immediate=True) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS outreach_records (
            profile_url TEXT PRIMARY KEY,
            candidate_name TEXT NOT NULL,
            persona TEXT NOT NULL CHECK(persona IN ('Fresher','1-2_YOE','Career_Switcher')),
            relevance_score INTEGER NOT NULL CHECK(relevance_score BETWEEN 1 AND 10),
            headline TEXT NOT NULL DEFAULT '', snippet TEXT NOT NULL DEFAULT '',
            connection_note TEXT NOT NULL DEFAULT '', follow_up_dm TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'discovered' CHECK(status IN ('discovered','handoff_initiated','contacted')),
            handoff_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            last_handoff_at TEXT, contacted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS confirmed_sends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_url TEXT NOT NULL,
            local_day TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            UNIQUE(profile_url, local_day),
            FOREIGN KEY(profile_url) REFERENCES outreach_records(profile_url) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS handoff_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_url TEXT NOT NULL,
            local_day TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(profile_url) REFERENCES outreach_records(profile_url) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_records(status);
        CREATE INDEX IF NOT EXISTS idx_sends_day ON confirmed_sends(local_day);
        CREATE INDEX IF NOT EXISTS idx_handoffs_day ON handoff_events(local_day);
        """)


def local_now() -> datetime:
    try:
        tz = ZoneInfo(settings.timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)
