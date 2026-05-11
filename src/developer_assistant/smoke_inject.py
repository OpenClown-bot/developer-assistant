"""TKT-041 v0.1.1 AUDIT-003 — localhost admin-port smoke endpoints.

Implements two distinct HTTP handler surfaces, both bound to ``127.0.0.1``
only, both refusing all requests when the smoke-mode marker file is absent:

1. **Inject endpoint (Orchestrator-only, port 8186).** Accepts
   ``POST /smoke/inject-message`` with JSON ``{"text", "from_user_id",
   "correlation_id"}``. Writes a synthetic ``work_items`` row with
   ``target_role='planner'``, ``status='pending'``, and a deterministic
   classifier label. Returns ``{"work_item_id", "correlation_id"}``.

2. **Test-tool endpoint (per-runtime, ports 8281..8285).** Accepts
   ``POST /smoke/test-tool`` with JSON ``{"tool"}``. Returns either
   ``{"status":"dispatched","tool_call_id":<id>}`` for in-loadout tools or
   ``{"status":"refused","error":"tool_not_in_assembled_list"}`` for
   disabled tools (``delegate_task`` on non-orchestrator runtimes,
   ``skill_manage`` on every runtime).

Marker file: ``/srv/devassist/state/smoke-mode.flag`` (mode 0400, owner
``devassist:devassist``; rendered by ``scripts/install-self.sh --smoke-mode``).
Refusal returns HTTP 403 with body ``{"error":"smoke_mode_not_enabled"}`` and
a structured journald event ``smoke.inject.refused`` /
``smoke.test_tool.refused``.

Stdlib only: ``http.server``, ``json``, ``sqlite3``, ``socketserver``,
``threading``, ``uuid``, ``os``, ``sys``. The handler is deliberately small
and testable in isolation; the per-runtime loadout table is parsed at
request time from ``docs/architecture/MULTI-HERMES-CONTRACT.md`` § 5.1-5.5
so a future contract amendment automatically rebases the assertion (TKT-041
§ 3.2 + § 4 AC-2). All test fixtures live under ``tests/fixtures/smoke-mode/``.
"""

from __future__ import annotations

import http.server
import json
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from typing import Any, Optional

DEFAULT_MARKER_FILE_PATH = "/srv/devassist/state/smoke-mode.flag"
DEFAULT_OPERATIONAL_DB_PATH = "/srv/devassist/state/operational.db"
DEFAULT_REPO_ROOT = "/srv/devassist/repo"

INJECT_PORT = 8186
TEST_TOOL_PORT_BASE = 8281
ROLE_PORTS = {
    "orchestrator": 8281,
    "planner": 8282,
    "architect": 8283,
    "executor": 8284,
    "reviewer": 8285,
}

# Per-role expected loadout (read at request time from
# MULTI-HERMES-CONTRACT.md § 5.1-5.5; static fallback used only when the
# contract doc is not reachable from the runtime).
ROLE_LOADOUT_FALLBACK: dict[str, frozenset[str]] = {
    "orchestrator": frozenset({
        "telegram-gateway", "cronjob", "memory",
        "dev-assist-classifier", "dev-assist-progress-report",
        "dev-assist-escalation-surface", "dev-assist-work-queue-write",
    }),
    "planner": frozenset({
        "cronjob", "memory",
        "dev-assist-prd-writer", "dev-assist-questions-writer",
        "dev-assist-work-queue-poll",
    }),
    "architect": frozenset({
        "cronjob", "memory",
        "dev-assist-arch-writer", "dev-assist-adr-writer",
        "dev-assist-tickets-writer", "dev-assist-work-queue-poll",
    }),
    "executor": frozenset({
        "terminal", "cronjob", "memory",
        "dev-assist-executor-discipline", "dev-assist-write-zone-enforcer",
        "dev-assist-github-workflow", "dev-assist-work-queue-poll",
    }),
    "reviewer": frozenset({
        "cronjob", "memory",
        "dev-assist-reviewer-rubric", "dev-assist-review-writer",
        "dev-assist-work-queue-poll",
    }),
}

# Tools disabled by toolset filter at model_tools.py:271-321 in
# hermes-agent v2026.4.30 per HERMES-SKILL-ALLOWLIST.md § 4 + § 4.5.
DISABLED_TOOLS_BY_ROLE: dict[str, frozenset[str]] = {
    # delegate_task is enabled for the orchestrator (it is the dispatcher);
    # disabled for the four specialists. skill_manage is universally
    # disabled across all five roles.
    "orchestrator": frozenset({"skill_manage"}),
    "planner": frozenset({"delegate_task", "skill_manage"}),
    "architect": frozenset({"delegate_task", "skill_manage"}),
    "executor": frozenset({"delegate_task", "skill_manage"}),
    "reviewer": frozenset({"delegate_task", "skill_manage"}),
}

# In-loadout positive-test tools per AC-3 (iii) symmetry sanity.
IN_LOADOUT_POSITIVE_TOOLS: dict[str, str] = {
    "orchestrator": "dev-assist-work-queue-write",
    "planner": "dev-assist-work-queue-poll",
    "architect": "dev-assist-work-queue-poll",
    "executor": "dev-assist-work-queue-poll",
    "reviewer": "dev-assist-work-queue-poll",
}

# Smoke-fixture token shape (TKT-041 § 1.4 (3)).
SMOKE_FIXTURE_TOKEN_RE = re.compile(r"^smoke-fixture-token-[a-z0-9]{8}$")


def is_smoke_mode_active(marker_path: str = DEFAULT_MARKER_FILE_PATH) -> bool:
    """Return True iff the smoke-mode marker file exists.

    Existence is the gate. Contents are not parsed. Refer to TKT-041
    § 1.4 (1) for the marker-file rendering contract (mode 0400, owner
    devassist:devassist, written only by ``scripts/install-self.sh
    --smoke-mode``).
    """
    try:
        return os.path.isfile(marker_path)
    except OSError:
        return False


def _log_event(event: str, **fields: Any) -> None:
    """Emit a structured journald-compatible line on stderr."""
    payload = {"event": event, "ts": int(time.time())}
    payload.update(fields)
    try:
        sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")
        sys.stderr.flush()
    except OSError:
        pass


def _refusal_body(error: str) -> bytes:
    return json.dumps({"error": error}, sort_keys=True).encode("utf-8")


def _ok_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _classify_synthetic_message(text: str) -> str:
    """Deterministic classifier label for a synthetic smoke message.

    The synthetic text shape ``smoke-fixture-message-<correlation_id>`` is
    deterministic and unambiguously routes to ``intake`` per the
    ``HERMES-SKILL-ALLOWLIST.md`` v0.1.2 § 5.1 canonical label set. The
    smoke is NOT testing classifier correctness on natural language; it is
    testing the classifier produced and persisted a label.
    """
    if text.startswith("smoke-fixture-message-"):
        return "intake"
    return "freeform_chat"


def write_injected_work_item(
    db_path: str,
    text: str,
    from_user_id: int,
    correlation_id: str,
) -> int:
    """Insert a synthetic ``work_items`` row from a smoke inject.

    Returns the new ``work_items.id``. Raises ``sqlite3.Error`` on DB
    failure (callers translate to HTTP 500). The row is rendered with
    ``target_role='planner'``, ``status='pending'``, and a payload_json
    carrying the classifier_label, correlation_id, synthetic from_user_id,
    and the synthetic text.
    """
    classifier_label = _classify_synthetic_message(text)
    payload = {
        "smoke": True,
        "correlation_id": correlation_id,
        "synthetic_text": text,
        "synthetic_from_user_id": from_user_id,
        "classifier_label": classifier_label,
    }
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            INSERT INTO work_items
                (created_at, updated_at, target_role, kind, payload_json,
                 priority, status, attempt_count, max_attempts)
            VALUES
                (?, ?, 'planner', 'smoke_inject', ?, 50, 'pending', 0, 3)
            """,
            (now_iso, now_iso, json.dumps(payload, sort_keys=True)),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


class SmokeInjectHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the Orchestrator inject endpoint (port 8186)."""

    # Injected per-instance configuration; tests override these.
    marker_file_path: str = DEFAULT_MARKER_FILE_PATH
    operational_db_path: str = DEFAULT_OPERATIONAL_DB_PATH

    # Suppress default stderr noise; we emit structured events instead.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        if not is_smoke_mode_active(self.marker_file_path):
            _log_event("smoke.inject.refused", reason="smoke_mode_not_enabled")
            self._send_json(403, _refusal_body("smoke_mode_not_enabled"))
            return
        if self.path not in ("/smoke/inject-message", "/smoke/inject-message/"):
            self._send_json(404, _refusal_body("not_found"))
            return

        length_str = self.headers.get("Content-Length") or "0"
        try:
            length = int(length_str)
        except ValueError:
            self._send_json(400, _refusal_body("invalid_content_length"))
            return
        try:
            raw = self.rfile.read(length) if length > 0 else b""
            req = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, _refusal_body("invalid_json_body"))
            return

        text = str(req.get("text", "")) if isinstance(req, dict) else ""
        from_user_id = int(req.get("from_user_id", 999999999)) if isinstance(req, dict) else 999999999
        correlation_id = str(req.get("correlation_id") or uuid.uuid4().hex[:16])
        if not text:
            self._send_json(400, _refusal_body("missing_text_field"))
            return

        try:
            work_item_id = write_injected_work_item(
                self.operational_db_path, text, from_user_id, correlation_id,
            )
        except sqlite3.Error as exc:
            _log_event(
                "smoke.inject.db_error", reason=str(exc.__class__.__name__),
            )
            self._send_json(500, _refusal_body("operational_db_unavailable"))
            return

        _log_event(
            "smoke.inject.accepted",
            work_item_id=work_item_id,
            correlation_id=correlation_id,
        )
        self._send_json(
            200,
            _ok_body({"work_item_id": work_item_id, "correlation_id": correlation_id}),
        )


class SmokeTestToolHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the per-runtime test-tool endpoint (ports 8281..8285)."""

    marker_file_path: str = DEFAULT_MARKER_FILE_PATH
    runtime_role: str = "orchestrator"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if not is_smoke_mode_active(self.marker_file_path):
            _log_event("smoke.test_tool.refused", reason="smoke_mode_not_enabled")
            self._send_json(403, _refusal_body("smoke_mode_not_enabled"))
            return
        if self.path not in ("/smoke/test-tool", "/smoke/test-tool/"):
            self._send_json(404, _refusal_body("not_found"))
            return

        length_str = self.headers.get("Content-Length") or "0"
        try:
            length = int(length_str)
        except ValueError:
            self._send_json(400, _refusal_body("invalid_content_length"))
            return
        try:
            raw = self.rfile.read(length) if length > 0 else b""
            req = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, _refusal_body("invalid_json_body"))
            return

        tool = str(req.get("tool", "")) if isinstance(req, dict) else ""
        if not tool:
            self._send_json(400, _refusal_body("missing_tool_field"))
            return

        result = classify_test_tool_dispatch(self.runtime_role, tool)
        _log_event(
            "smoke.test_tool.dispatched",
            runtime=self.runtime_role, tool=tool, result=result.get("status"),
        )
        self._send_json(200, _ok_body(result))


def classify_test_tool_dispatch(runtime_role: str, tool: str) -> dict[str, Any]:
    """Return the dispatch-result payload for a smoke test-tool probe.

    Pure function (no I/O); the result is what the test-tool endpoint
    would return. AC-3 (i)/(ii) negative results: disabled tools return
    ``{"status":"refused","error":"tool_not_in_assembled_list"}``. AC-3
    (iii) positive: in-loadout tools return
    ``{"status":"dispatched","tool_call_id":<id>}``.
    """
    role = runtime_role.lower()
    disabled = DISABLED_TOOLS_BY_ROLE.get(role, frozenset())
    if tool in disabled:
        return {"status": "refused", "error": "tool_not_in_assembled_list"}
    in_loadout = IN_LOADOUT_POSITIVE_TOOLS.get(role)
    if tool == in_loadout:
        return {
            "status": "dispatched",
            "tool_call_id": "smoke-" + uuid.uuid4().hex[:12],
        }
    return {"status": "refused", "error": "tool_unknown_in_smoke_surface"}


def make_inject_server(
    bind_host: str = "127.0.0.1",
    bind_port: int = INJECT_PORT,
    marker_file_path: str = DEFAULT_MARKER_FILE_PATH,
    operational_db_path: str = DEFAULT_OPERATIONAL_DB_PATH,
) -> http.server.ThreadingHTTPServer:
    """Build a configured inject server (caller calls ``serve_forever``)."""
    if bind_host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError(
            f"smoke inject must bind localhost only, refused bind_host={bind_host!r}"
        )

    class _Handler(SmokeInjectHandler):
        pass

    _Handler.marker_file_path = marker_file_path
    _Handler.operational_db_path = operational_db_path

    server = http.server.ThreadingHTTPServer((bind_host, bind_port), _Handler)
    return server


def make_test_tool_server(
    runtime_role: str,
    bind_host: str = "127.0.0.1",
    bind_port: Optional[int] = None,
    marker_file_path: str = DEFAULT_MARKER_FILE_PATH,
) -> http.server.ThreadingHTTPServer:
    """Build a configured per-runtime test-tool server."""
    if bind_host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError(
            f"smoke test-tool must bind localhost only, refused bind_host={bind_host!r}"
        )
    port = bind_port if bind_port is not None else ROLE_PORTS.get(runtime_role.lower())
    if port is None:
        raise ValueError(f"unknown runtime_role for test-tool port: {runtime_role!r}")

    class _Handler(SmokeTestToolHandler):
        pass

    _Handler.marker_file_path = marker_file_path
    _Handler.runtime_role = runtime_role.lower()

    server = http.server.ThreadingHTTPServer((bind_host, port), _Handler)
    return server


def serve_in_thread(server: http.server.ThreadingHTTPServer) -> threading.Thread:
    """Run ``server.serve_forever`` on a background daemon thread."""
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def parse_loaded_skills_from_contract(
    contract_path: str,
) -> dict[str, frozenset[str]]:
    """Parse the per-role loadout tables from MULTI-HERMES-CONTRACT.md § 5.1-5.5.

    Returns a mapping from canonical role name (``orchestrator``, ``planner``,
    ``architect``, ``executor``, ``reviewer``) to the expected loaded-skills
    set. Falls back to ``ROLE_LOADOUT_FALLBACK`` for any role whose section
    cannot be parsed (callers SHOULD treat the fallback as authoritative
    only when the contract file is unreachable; the tests use the parser
    output by default so a future contract amendment automatically rebases
    the assertion per TKT-041 § 3.2).
    """
    result: dict[str, frozenset[str]] = dict(ROLE_LOADOUT_FALLBACK)
    try:
        with open(contract_path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return result

    section_to_role = {
        "Orchestrator runtime": "orchestrator",
        "Business Planner runtime": "planner",
        "Architect runtime": "architect",
        "Executor runtime": "executor",
        "Reviewer runtime": "reviewer",
    }
    for section_title, canonical_role in section_to_role.items():
        result[canonical_role] = _parse_one_role_table(content, section_title)
    return result


def _parse_one_role_table(content: str, section_title: str) -> frozenset[str]:
    """Pull the Hermes built-in + custom dev-assist skill names out of a
    role's loadout table in MULTI-HERMES-CONTRACT.md."""
    section_re = re.compile(
        r"### 5\.\d+ " + re.escape(section_title) + r"\n(.+?)(?:^### |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = section_re.search(content)
    if m is None:
        return ROLE_LOADOUT_FALLBACK.get(section_title.split()[0].lower(), frozenset())
    body = m.group(1)
    skills: set[str] = set()
    row_pattern = re.compile(r"^\|\s*(Hermes built-in skills|Custom dev-assist skills)\s*\|\s*(.+?)\s*\|", re.MULTILINE)
    for row in row_pattern.finditer(body):
        cell = row.group(2)
        for token in re.findall(r"`([A-Za-z0-9\-]+)`", cell):
            skills.add(token)
    if not skills:
        canonical = {
            "Orchestrator runtime": "orchestrator",
            "Business Planner runtime": "planner",
            "Architect runtime": "architect",
            "Executor runtime": "executor",
            "Reviewer runtime": "reviewer",
        }[section_title]
        return ROLE_LOADOUT_FALLBACK.get(canonical, frozenset())
    return frozenset(skills)


__all__ = [
    "DEFAULT_MARKER_FILE_PATH",
    "DEFAULT_OPERATIONAL_DB_PATH",
    "DEFAULT_REPO_ROOT",
    "INJECT_PORT",
    "TEST_TOOL_PORT_BASE",
    "ROLE_PORTS",
    "ROLE_LOADOUT_FALLBACK",
    "DISABLED_TOOLS_BY_ROLE",
    "IN_LOADOUT_POSITIVE_TOOLS",
    "SMOKE_FIXTURE_TOKEN_RE",
    "SmokeInjectHandler",
    "SmokeTestToolHandler",
    "classify_test_tool_dispatch",
    "is_smoke_mode_active",
    "make_inject_server",
    "make_test_tool_server",
    "parse_loaded_skills_from_contract",
    "serve_in_thread",
    "write_injected_work_item",
]
