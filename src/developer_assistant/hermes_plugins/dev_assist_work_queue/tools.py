from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Optional

from developer_assistant import state_store
from developer_assistant.hermes_plugins.dev_assist_work_queue.skill_loader import (
    filter_skills as _filter_mcp_excluded_skills,
    is_mcp_excluded as _is_mcp_excluded,
)
from developer_assistant.work_queue import (
    claim_work_item,
    complete_work_item,
    release_work_item,
    write_work_item,
)

ALLOWED_TARGET_ROLES = frozenset({
    "orchestrator", "planner", "architect", "executor", "reviewer"
})

_DB_PATH = os.environ.get("DEV_ASSIST_OPERATIONAL_DB", ":memory:")


def _get_role() -> str:
    return os.environ.get("HERMES_DEVASSIST_ROLE", "unknown")


TOOL_SCHEMAS = {
    "work_queue.claim": {
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "lease_minutes": {"type": "integer", "default": 30},
        },
        "required": ["role"],
    },
    "work_queue.complete": {
        "type": "object",
        "properties": {
            "work_item_id": {"type": "integer"},
            "result": {"type": "object"},
        },
        "required": ["work_item_id", "result"],
    },
    "work_queue.release": {
        "type": "object",
        "properties": {
            "work_item_id": {"type": "integer"},
            "increment_attempts": {"type": "boolean", "default": False},
        },
        "required": ["work_item_id"],
    },
    "work_queue.write": {
        "type": "object",
        "properties": {
            "target_role": {"type": "string"},
            "kind": {"type": "string"},
            "payload": {"type": "object"},
            "priority": {"type": "integer", "default": 50},
            "dedup_key": {"type": "string"},
        },
        "required": ["target_role", "kind", "payload"],
    },
}


def _get_conn() -> sqlite3.Connection:
    return state_store.open_store(_DB_PATH)


def work_queue_claim(
    role: str,
    lease_minutes: int = 30,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    runtime_role = _get_role()
    if role != runtime_role:
        return {
            "status": "error",
            "error": f"Role mismatch: claimed as {role!r} but runtime role is {runtime_role!r}",
        }
    if conn is None:
        conn = _get_conn()
    result = claim_work_item(
        conn,
        runtime_id=runtime_role,
        target_role=role,
        lease_minutes=lease_minutes,
    )
    if result is None:
        return {"status": "ok", "work_item": None}
    return {"status": "ok", "work_item": dict(result)}


def work_queue_complete(
    work_item_id: int,
    result: dict,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    if conn is None:
        conn = _get_conn()
    row = complete_work_item(conn, item_id=work_item_id, result=result)
    if row is None:
        return {"status": "error", "error": "Work item not found or not claimed"}
    return {"status": "ok", "work_item": dict(row)}


def work_queue_release(
    work_item_id: int,
    increment_attempts: bool = False,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    if conn is None:
        conn = _get_conn()
    row = release_work_item(
        conn, item_id=work_item_id, increment_attempts=increment_attempts
    )
    if row is None:
        return {"status": "error", "error": "Work item not found"}
    return {"status": "ok", "work_item": dict(row)}


def work_queue_write(
    target_role: str,
    kind: str,
    payload: dict,
    priority: int = 50,
    dedup_key: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> dict:
    if target_role not in ALLOWED_TARGET_ROLES:
        return {
            "status": "error",
            "error": f"Invalid target_role: {target_role!r}. Must be one of {sorted(ALLOWED_TARGET_ROLES)}",
        }
    if conn is None:
        conn = _get_conn()
    try:
        item_id = write_work_item(
            conn,
            target_role=target_role,
            kind=kind,
            payload=payload,
            priority=priority,
            dedup_key=dedup_key,
        )
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    return {"status": "ok", "id": item_id}


def register(hooks: dict) -> None:
    hooks["tools"] = {
        "work_queue.claim": {
            "schema": TOOL_SCHEMAS["work_queue.claim"],
            "handler": work_queue_claim,
        },
        "work_queue.complete": {
            "schema": TOOL_SCHEMAS["work_queue.complete"],
            "handler": work_queue_complete,
        },
        "work_queue.release": {
            "schema": TOOL_SCHEMAS["work_queue.release"],
            "handler": work_queue_release,
        },
        "work_queue.write": {
            "schema": TOOL_SCHEMAS["work_queue.write"],
            "handler": work_queue_write,
        },
    }
    hooks["skill_loader"] = {
        "is_excluded": _is_mcp_excluded,
        "filter": _filter_mcp_excluded_skills,
    }
