"""
memory.py — Shared Consciousness (الذاكرة المشتركة)
====================================================
A simple SQLite-backed long-term memory shared by the master agent
and all of its clones. When one clone learns something, it writes it
here and every other clone can read it immediately.

Design goals (kept intentionally simple so the AI can read & understand
its own memory layer and evolve it later):
  - Zero external services (just a local SQLite file).
  - Thread-safe writes via a short-lived connection per call.
  - Two tables:
      * lessons   -> reusable knowledge ("how to do X")
      * events    -> append-only timeline of what happened
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Any, Optional

# The memory database lives next to the backend so it persists across restarts.
DB_PATH = Path(__file__).parent / "shared_memory.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables on first run. Safe to call repeatedly."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                topic     TEXT NOT NULL,
                content   TEXT NOT NULL,
                author    TEXT NOT NULL DEFAULT 'master',
                score     REAL NOT NULL DEFAULT 0,
                created   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                kind      TEXT NOT NULL,
                payload   TEXT NOT NULL,
                author    TEXT NOT NULL DEFAULT 'master',
                created   REAL NOT NULL
            );
            """
        )


def add_lesson(topic: str, content: str, author: str = "master", score: float = 0) -> int:
    """Store a reusable piece of knowledge shared with every clone."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO lessons (topic, content, author, score, created) VALUES (?,?,?,?,?)",
            (topic, content, author, score, time.time()),
        )
        return cur.lastrowid


def search_lessons(topic: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
    """Retrieve lessons, optionally filtered by a topic substring."""
    with _connect() as conn:
        if topic:
            rows = conn.execute(
                "SELECT * FROM lessons WHERE topic LIKE ? ORDER BY score DESC, created DESC LIMIT ?",
                (f"%{topic}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY score DESC, created DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def log_event(kind: str, payload: Any, author: str = "master") -> int:
    """Append an event to the shared timeline (thinking, tool calls, etc.)."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO events (kind, payload, author, created) VALUES (?,?,?,?)",
            (kind, json.dumps(payload, ensure_ascii=False), author, time.time()),
        )
        return cur.lastrowid


def recent_events(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
            out.append(d)
        return out


# Initialize on import so the rest of the system can rely on the tables existing.
init_db()
