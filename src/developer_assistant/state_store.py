"""Operational state store for Telegram-first Hermes orchestration.

This module implements the minimal SQLite-backed operational state store
required by v0.1. It stores:

- Telegram chat/user allowlist references (sanitized keys, not raw private
  identifiers unless explicitly sanitized by the caller).
- Project registry entries mapping Telegram conversations to GitHub
  repositories and local workspaces.
- Scheduled progress report timestamps.
- Hermes run IDs, retry/idempotency keys, and in-flight task metadata.

This is operational metadata only. Product, architecture, security, merge,
and deployment decisions remain in repository artifacts under docs/.
Secrets must never be stored in this database.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping, Optional


_SCHEMA_VERSION = 1

_CREATE_PROJECT_BINDINGS = """
CREATE TABLE IF NOT EXISTS project_bindings (
    chat_key TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    repo_owner_name TEXT,
    workspace_path TEXT,
    phase TEXT,
    updated_at TEXT NOT NULL
)
"""

_CREATE_SCHEDULED_PROGRESS = """
CREATE TABLE IF NOT EXISTS scheduled_progress (
    project_key TEXT PRIMARY KEY,
    last_report_at TEXT,
    next_report_at TEXT,
    interval_minutes INTEGER,
    updated_at TEXT NOT NULL
)
"""

_CREATE_HERMES_RUNS = """
CREATE TABLE IF NOT EXISTS hermes_runs (
    run_id TEXT PRIMARY KEY,
    project_key TEXT NOT NULL,
    role TEXT,
    task_type TEXT,
    status TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    in_flight_meta TEXT,
    updated_at TEXT NOT NULL
)
"""

_CREATE_IDEMPOTENCY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_hermes_runs_idempotency
ON hermes_runs (idempotency_key)
"""

_CREATE_SCHEMA_META = """
CREATE TABLE IF NOT EXISTS _schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_ALL_DDL = [
    _CREATE_SCHEMA_META,
    _CREATE_PROJECT_BINDINGS,
    _CREATE_SCHEDULED_PROGRESS,
    _CREATE_HERMES_RUNS,
    _CREATE_IDEMPOTENCY_INDEX,
]


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def init_schema(db: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not exist."""
    cur = db.cursor()
    for ddl in _ALL_DDL:
        cur.execute(ddl)
    cur.execute(
        "INSERT OR IGNORE INTO _schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(_SCHEMA_VERSION)),
    )
    db.commit()


def open_store(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and initialize schema.

    Args:
        db_path: Filesystem path to the SQLite database file.
                 Use ``:memory:`` for transient in-process databases.

    Returns:
        A sqlite3.Connection with schema initialized and
        ``row_factory`` set to ``sqlite3.Row``.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def upsert_project_binding(
    db: sqlite3.Connection,
    *,
    chat_key: str,
    repo_url: str,
    repo_owner_name: Optional[str] = None,
    workspace_path: Optional[str] = None,
    phase: Optional[str] = None,
) -> None:
    """Insert or update a project binding row."""
    now = _now_iso()
    db.execute(
        """INSERT INTO project_bindings
               (chat_key, repo_url, repo_owner_name, workspace_path, phase, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(chat_key) DO UPDATE SET
               repo_url = excluded.repo_url,
               repo_owner_name = excluded.repo_owner_name,
               workspace_path = excluded.workspace_path,
               phase = excluded.phase,
               updated_at = excluded.updated_at
        """,
        (chat_key, repo_url, repo_owner_name, workspace_path, phase, now),
    )
    db.commit()


def read_project_binding(
    db: sqlite3.Connection, chat_key: str
) -> Optional[Mapping[str, Any]]:
    """Read a single project binding by chat_key.

    Returns ``None`` if no row matches.
    """
    cur = db.execute(
        "SELECT * FROM project_bindings WHERE chat_key = ?", (chat_key,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def list_project_bindings(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all project binding rows."""
    cur = db.execute("SELECT * FROM project_bindings ORDER BY chat_key")
    return [dict(r) for r in cur.fetchall()]


def upsert_scheduled_progress(
    db: sqlite3.Connection,
    *,
    project_key: str,
    last_report_at: Optional[str] = None,
    next_report_at: Optional[str] = None,
    interval_minutes: Optional[int] = None,
) -> None:
    """Insert or update a scheduled-progress row."""
    now = _now_iso()
    db.execute(
        """INSERT INTO scheduled_progress
               (project_key, last_report_at, next_report_at, interval_minutes, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(project_key) DO UPDATE SET
               last_report_at = COALESCE(excluded.last_report_at, scheduled_progress.last_report_at),
               next_report_at = COALESCE(excluded.next_report_at, scheduled_progress.next_report_at),
               interval_minutes = COALESCE(excluded.interval_minutes, scheduled_progress.interval_minutes),
               updated_at = excluded.updated_at
        """,
        (project_key, last_report_at, next_report_at, interval_minutes, now),
    )
    db.commit()


def read_scheduled_progress(
    db: sqlite3.Connection, project_key: str
) -> Optional[Mapping[str, Any]]:
    """Read a single scheduled-progress row by project_key."""
    cur = db.execute(
        "SELECT * FROM scheduled_progress WHERE project_key = ?",
        (project_key,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_hermes_run(
    db: sqlite3.Connection,
    *,
    run_id: str,
    project_key: str,
    role: Optional[str] = None,
    task_type: Optional[str] = None,
    status: str = "pending",
    idempotency_key: Optional[str] = None,
    in_flight_meta: Optional[dict[str, Any]] = None,
) -> None:
    """Insert or update a Hermes run metadata row.

    ``in_flight_meta`` is serialized as JSON text.
    """
    now = _now_iso()
    meta_json = json.dumps(in_flight_meta) if in_flight_meta is not None else None
    db.execute(
        """INSERT INTO hermes_runs
               (run_id, project_key, role, task_type, status,
                idempotency_key, in_flight_meta, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(run_id) DO UPDATE SET
               project_key = excluded.project_key,
               role = excluded.role,
               task_type = excluded.task_type,
               status = excluded.status,
               idempotency_key = COALESCE(excluded.idempotency_key, hermes_runs.idempotency_key),
               in_flight_meta = excluded.in_flight_meta,
               updated_at = excluded.updated_at
        """,
        (run_id, project_key, role, task_type, status, idempotency_key, meta_json, now),
    )
    db.commit()


def read_hermes_run(
    db: sqlite3.Connection, run_id: str
) -> Optional[Mapping[str, Any]]:
    """Read a single Hermes run row by run_id."""
    cur = db.execute("SELECT * FROM hermes_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    if row is None:
        return None
    result = dict(row)
    if result.get("in_flight_meta") is not None:
        result["in_flight_meta"] = json.loads(result["in_flight_meta"])
    return result


def read_hermes_run_by_idempotency(
    db: sqlite3.Connection, idempotency_key: str
) -> Optional[Mapping[str, Any]]:
    """Read a single Hermes run row by idempotency_key."""
    cur = db.execute(
        "SELECT * FROM hermes_runs WHERE idempotency_key = ?",
        (idempotency_key,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    result = dict(row)
    if result.get("in_flight_meta") is not None:
        result["in_flight_meta"] = json.loads(result["in_flight_meta"])
    return result


def reset_store(db: sqlite3.Connection) -> None:
    """Delete all operational data rows (for tests or documented reset).

    Schema tables are preserved so the database can be reused immediately.
    """
    db.execute("DELETE FROM hermes_runs")
    db.execute("DELETE FROM scheduled_progress")
    db.execute("DELETE FROM project_bindings")
    db.commit()
