"""SQLite L3 episodic store.

Tables (already created in DGX setup):
  events    — one row per significant agent action or task outcome
  audit_log — audit trail for T2–T4 actions (Phase 2)

This module provides:
  - log_event()            — write a row to events
  - get_episodic_context() — retrieve recent events for a user/session
"""
import asyncio
import os
import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AGENT_DATA_DIR = os.environ.get("AGENT_DATA_DIR", "/opt/qnoe-agent/memory")
EPISODIC_DB = os.path.join(AGENT_DATA_DIR, "episodic.db")

# Max events returned per context query
CONTEXT_LIMIT = 10


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(EPISODIC_DB)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    """Create tables if they don't exist (idempotent)."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY,
                session_id  TEXT NOT NULL,
                user_id     TEXT,
                agent_id    TEXT NOT NULL,
                task_type   TEXT NOT NULL,
                repo        TEXT,
                outcome     TEXT NOT NULL,
                summary     TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id           INTEGER PRIMARY KEY,
                operation_id TEXT NOT NULL,
                tier         INTEGER NOT NULL,
                description  TEXT NOT NULL,
                manifest     TEXT,
                approved_by  TEXT,
                timestamp    TEXT NOT NULL
            );
        """)


def _log_event_sync(
    session_id: str,
    agent_id: str,
    task_type: str,
    outcome: str,
    summary: str,
    user_id: str | None,
    repo: str | None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO events
               (session_id, user_id, agent_id, task_type, repo, outcome, summary, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, agent_id, task_type, repo, outcome, summary, ts),
        )


async def log_event(
    *,
    session_id: str,
    agent_id: str,
    task_type: str,
    outcome: str,
    summary: str,
    user_id: str | None = None,
    repo: str | None = None,
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, _log_event_sync,
        session_id, agent_id, task_type, outcome, summary, user_id, repo,
    )


def _get_episodic_context_sync(
    session_id: str | None,
    user_id: str | None,
    limit: int,
) -> list[dict]:
    with _get_conn() as conn:
        if user_id:
            rows = conn.execute(
                """SELECT agent_id, task_type, repo, outcome, summary, timestamp
                   FROM events WHERE user_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        elif session_id:
            rows = conn.execute(
                """SELECT agent_id, task_type, repo, outcome, summary, timestamp
                   FROM events WHERE session_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        else:
            return []

    return [
        {
            "source": "sqlite",
            "task_type": r["task_type"],
            "repo": r["repo"],
            "outcome": r["outcome"],
            "summary": r["summary"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


async def get_episodic_context(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    limit: int = CONTEXT_LIMIT,
) -> list[dict]:
    """Return recent task events for this session or user, newest first."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _get_episodic_context_sync, session_id, user_id, limit,
    )
