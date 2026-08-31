import sqlite3
from datetime import datetime
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_thresholds (
    chat_id INTEGER PRIMARY KEY,
    threshold_hours REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_tiers (
    chat_id INTEGER PRIMARY KEY,
    tier TEXT NOT NULL CHECK (tier IN ('close', 'family'))
);
CREATE TABLE IF NOT EXISTS flagged_chats (
    chat_id INTEGER PRIMARY KEY,
    flagged_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_run_at TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_threshold(conn: sqlite3.Connection, chat_id: int) -> Optional[float]:
    row = conn.execute(
        "SELECT threshold_hours FROM chat_thresholds WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row[0] if row else None


def set_threshold(conn: sqlite3.Connection, chat_id: int, hours: float) -> None:
    conn.execute(
        "INSERT INTO chat_thresholds (chat_id, threshold_hours) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET threshold_hours = excluded.threshold_hours",
        (chat_id, hours),
    )
    conn.commit()


def clear_threshold(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("DELETE FROM chat_thresholds WHERE chat_id = ?", (chat_id,))
    conn.commit()


def get_tier(conn: sqlite3.Connection, chat_id: int) -> Optional[str]:
    row = conn.execute(
        "SELECT tier FROM chat_tiers WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row[0] if row else None


def set_tier(conn: sqlite3.Connection, chat_id: int, tier: str) -> None:
    conn.execute(
        "INSERT INTO chat_tiers (chat_id, tier) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET tier = excluded.tier",
        (chat_id, tier),
    )
    conn.commit()


def clear_tier(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("DELETE FROM chat_tiers WHERE chat_id = ?", (chat_id,))
    conn.commit()


def is_flagged(conn: sqlite3.Connection, chat_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM flagged_chats WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row is not None


def mark_flagged(conn: sqlite3.Connection, chat_id: int, flagged_at: datetime) -> None:
    conn.execute(
        "INSERT INTO flagged_chats (chat_id, flagged_at) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET flagged_at = excluded.flagged_at",
        (chat_id, flagged_at.isoformat()),
    )
    conn.commit()


def unmark_flagged(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("DELETE FROM flagged_chats WHERE chat_id = ?", (chat_id,))
    conn.commit()


def get_last_run_at(conn: sqlite3.Connection) -> Optional[datetime]:
    row = conn.execute("SELECT last_run_at FROM run_state WHERE id = 1").fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def set_last_run_at(conn: sqlite3.Connection, when: datetime) -> None:
    conn.execute(
        "INSERT INTO run_state (id, last_run_at) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_run_at = excluded.last_run_at",
        (when.isoformat(),),
    )
    conn.commit()
