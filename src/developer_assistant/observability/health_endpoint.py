"""Per-runtime localhost-only health endpoint.

Implements OBSERVABILITY-CONTRACT.md v0.1.1 § 11 (FR-OBS-08).
Binds to 127.0.0.1 only. Serves GET /health with JSON response.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from http import HTTPStatus
from typing import Any, Optional

_HEALTH_ROLES = {
    "orchestrator": 8181,
    "business-planner": 8182,
    "architect": 8183,
    "executor": 8184,
    "reviewer": 8185,
}


class HealthEndpoint:
    def __init__(
        self,
        runtime_role: str,
        port: int,
        operational_db_path: str,
    ) -> None:
        self._role = runtime_role
        self._port = port
        self._db_path = operational_db_path
        self._start_time: float = 0.0
        self._server: Optional[asyncio.AbstractServer] = None
        self._current_work_item_id: Optional[str] = None
        self._current_model: Optional[str] = None
        self._version = "0.1.0"
        self._build_commit = "unknown"

    def set_current_work_item(self, work_item_id: Optional[str]) -> None:
        self._current_work_item_id = work_item_id

    def set_current_model(self, model: Optional[str]) -> None:
        self._current_model = model

    async def start(self) -> None:
        self._start_time = time.monotonic()
        self._server = await asyncio.start_server(
            self._handle_request,
            host="127.0.0.1",
            port=self._port,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def port(self) -> int:
        return self._port

    async def _handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        except (asyncio.TimeoutError, ConnectionError):
            writer.close()
            return

        parts = line.decode("utf-8", errors="replace").strip().split()
        if len(parts) < 2 or parts[0] != "GET" or parts[1] != "/health":
            body = b"Not Found"
            writer.write(
                f"HTTP/1.1 {HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Content-Type: text/plain\r\n"
                f"Connection: close\r\n\r\n".encode()
            )
            writer.write(body)
            await writer.drain()
            writer.close()
            return

        response = self._build_response()
        body = json.dumps(response, indent=2).encode("utf-8")
        writer.write(
            f"HTTP/1.1 {HTTPStatus.OK.value} {HTTPStatus.OK.phrase}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Content-Type: application/json\r\n"
            f"Connection: close\r\n\r\n".encode()
        )
        writer.write(body)
        await writer.drain()
        writer.close()

    def _build_response(self) -> dict[str, Any]:
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        uptime_s = int(time.monotonic() - self._start_time) if self._start_time else 0
        state = "running"
        heartbeat_age_s = 0

        db_ok = True
        last_error_at: Optional[str] = None
        queue_stats: Optional[dict[str, int]] = None

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                five_min_ago = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() - 300),
                )
                cur = conn.execute(
                    "SELECT MAX(ts) AS last_ts FROM errors WHERE runtime = ? AND ts > ?",
                    (self._role, five_min_ago),
                )
                row = cur.fetchone()
                if row and row["last_ts"] is not None:
                    state = "degraded"
                    last_error_at = row["last_ts"]

                cur2 = conn.execute(
                    "SELECT MAX(ts) AS last_ts FROM errors WHERE runtime = ?",
                    (self._role,),
                )
                row2 = cur2.fetchone()
                if row2 and row2["last_ts"] is not None:
                    if last_error_at is None:
                        last_error_at = row2["last_ts"]

                if self._role == "orchestrator":
                    cur3 = conn.execute(
                        "SELECT status, COUNT(*) AS cnt FROM work_items GROUP BY status"
                    )
                    qs: dict[str, int] = {
                        "pending": 0,
                        "in_progress": 0,
                        "escalated": 0,
                        "failed": 0,
                    }
                    for r in cur3.fetchall():
                        s = r["status"]
                        c = r["cnt"]
                        if s == "pending":
                            qs["pending"] = c
                        elif s == "claimed":
                            qs["in_progress"] = c
                        elif s == "escalated":
                            qs["escalated"] = c
                        elif s == "failed":
                            qs["failed"] = c
                    queue_stats = qs
            finally:
                conn.close()
        except Exception:
            db_ok = False
            state = "degraded"

        result: dict[str, Any] = {
            "ts_iso": now_iso,
            "role": self._role,
            "state": state,
            "uptime_s": uptime_s,
            "current_work_item_id": self._current_work_item_id,
            "current_model": self._current_model,
            "heartbeat_age_s": heartbeat_age_s,
            "version": self._version,
            "build_commit": self._build_commit,
        }
        if queue_stats is not None:
            result["queue_stats"] = queue_stats
        return result
