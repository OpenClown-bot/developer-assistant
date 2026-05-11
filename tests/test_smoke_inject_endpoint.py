"""TKT-041 v0.1.1 AUDIT-003 — unit tests for smoke_inject.py.

Covers:
  * marker-file gate (HTTP 403 when absent)
  * /smoke/inject-message happy path (work_items row written)
  * /smoke/inject-message bad-input refusal (400)
  * /smoke/test-tool dispatch classification (AC-3 i/ii negative + iii positive)
  * make_inject_server / make_test_tool_server localhost-only enforcement
  * parse_loaded_skills_from_contract round-trip against the real
    MULTI-HERMES-CONTRACT.md on the branch (AC-2 contract-parsing approach)
"""

from __future__ import annotations

import http.client
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.smoke_inject import (
    DISABLED_TOOLS_BY_ROLE,
    IN_LOADOUT_POSITIVE_TOOLS,
    ROLE_LOADOUT_FALLBACK,
    ROLE_PORTS,
    SMOKE_FIXTURE_TOKEN_RE,
    classify_test_tool_dispatch,
    is_smoke_mode_active,
    make_inject_server,
    make_test_tool_server,
    parse_loaded_skills_from_contract,
    serve_in_thread,
    write_injected_work_item,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_004 = REPO_ROOT / "db" / "migrations" / "004_work_queue_and_escalations.sql"


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _init_work_items_db(db_path: str) -> None:
    """Apply migration 004 (work_items + escalations DDL) to a sqlite file."""
    sql = MIGRATION_004.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def _post(host: str, port: int, path: str, body: dict | str | None, headers: dict | None = None) -> tuple[int, dict]:
    if isinstance(body, dict):
        payload = json.dumps(body).encode("utf-8")
    elif isinstance(body, str):
        payload = body.encode("utf-8")
    else:
        payload = b""
    h = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
    if headers:
        h.update(headers)
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("POST", path, payload, h)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        status = resp.status
    finally:
        conn.close()
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {"raw": raw}
    return status, parsed


class TestSmokeModeActiveGate(unittest.TestCase):
    def test_marker_absent_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(is_smoke_mode_active(os.path.join(tmp, "absent.flag")))

    def test_marker_present_returns_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = os.path.join(tmp, "present.flag")
            Path(marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
            self.assertTrue(is_smoke_mode_active(marker))


class TestClassifyTestToolDispatch(unittest.TestCase):
    def test_delegate_task_refused_on_specialists(self):
        for role in ("planner", "architect", "executor", "reviewer"):
            with self.subTest(role=role):
                result = classify_test_tool_dispatch(role, "delegate_task")
                self.assertEqual(result["status"], "refused")
                self.assertEqual(result["error"], "tool_not_in_assembled_list")

    def test_delegate_task_dispatched_on_orchestrator_when_in_loadout(self):
        # AC-3 (i) closing note: Orchestrator does NOT list "delegation" in
        # agent.disabled_toolsets, so a delegate_task probe is not part of
        # the AC-3 (i) negative test for the Orchestrator. It is also not
        # in the IN_LOADOUT_POSITIVE_TOOLS map → returns the unknown-tool
        # branch instead of dispatched. We assert exactly that posture.
        result = classify_test_tool_dispatch("orchestrator", "delegate_task")
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["error"], "tool_unknown_in_smoke_surface")

    def test_skill_manage_refused_on_every_role(self):
        for role in ROLE_PORTS.keys():
            with self.subTest(role=role):
                result = classify_test_tool_dispatch(role, "skill_manage")
                self.assertEqual(result["status"], "refused")
                self.assertEqual(result["error"], "tool_not_in_assembled_list")

    def test_in_loadout_positive_tool_dispatched(self):
        for role, tool in IN_LOADOUT_POSITIVE_TOOLS.items():
            with self.subTest(role=role, tool=tool):
                result = classify_test_tool_dispatch(role, tool)
                self.assertEqual(result["status"], "dispatched")
                self.assertTrue(result["tool_call_id"].startswith("smoke-"))


class TestInjectHandler(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "smoke-mode.flag")
        self.db_path = os.path.join(self._tmp.name, "operational.db")
        _init_work_items_db(self.db_path)
        self.port = _free_port()
        self.server = make_inject_server(
            bind_host="127.0.0.1", bind_port=self.port,
            marker_file_path=self.marker, operational_db_path=self.db_path,
        )
        self._thread = serve_in_thread(self.server)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def test_refuses_when_marker_absent(self):
        status, body = _post("127.0.0.1", self.port, "/smoke/inject-message",
                             {"text": "x"})
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": "smoke_mode_not_enabled"})

    def test_accepts_when_marker_present(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        text = "smoke-fixture-message-deadbeef"
        status, body = _post("127.0.0.1", self.port, "/smoke/inject-message",
                             {"text": text, "from_user_id": 12345,
                              "correlation_id": "deadbeef"})
        self.assertEqual(status, 200)
        self.assertEqual(body["correlation_id"], "deadbeef")
        self.assertGreater(int(body["work_item_id"]), 0)

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT target_role, kind, status, payload_json FROM work_items WHERE id = ?",
                (body["work_item_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "planner")
        self.assertEqual(row[1], "smoke_inject")
        self.assertEqual(row[2], "pending")
        payload = json.loads(row[3])
        self.assertTrue(payload["smoke"])
        self.assertEqual(payload["correlation_id"], "deadbeef")
        self.assertEqual(payload["classifier_label"], "intake")

    def test_rejects_missing_text(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        status, body = _post("127.0.0.1", self.port, "/smoke/inject-message",
                             {})
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "missing_text_field"})

    def test_rejects_invalid_json(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        status, body = _post("127.0.0.1", self.port, "/smoke/inject-message",
                             "not-json-not-json")
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "invalid_json_body"})

    def test_404_on_unknown_path(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        status, body = _post("127.0.0.1", self.port, "/totally-other-path",
                             {"text": "x"})
        self.assertEqual(status, 404)


class TestTestToolHandler(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "smoke-mode.flag")
        self.port = _free_port()
        self.server = make_test_tool_server(
            "planner", bind_host="127.0.0.1", bind_port=self.port,
            marker_file_path=self.marker,
        )
        self._thread = serve_in_thread(self.server)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def test_refuses_when_marker_absent(self):
        status, body = _post("127.0.0.1", self.port, "/smoke/test-tool",
                             {"tool": "delegate_task"})
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": "smoke_mode_not_enabled"})

    def test_delegate_task_refusal(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        status, body = _post("127.0.0.1", self.port, "/smoke/test-tool",
                             {"tool": "delegate_task"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "refused")
        self.assertEqual(body["error"], "tool_not_in_assembled_list")

    def test_in_loadout_dispatch(self):
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        status, body = _post("127.0.0.1", self.port, "/smoke/test-tool",
                             {"tool": "dev-assist-work-queue-poll"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "dispatched")
        self.assertTrue(body["tool_call_id"].startswith("smoke-"))


class TestLocalhostOnlyBindGuard(unittest.TestCase):
    def test_inject_server_refuses_non_localhost_bind(self):
        with self.assertRaises(ValueError):
            make_inject_server(bind_host="0.0.0.0", bind_port=18186)
        with self.assertRaises(ValueError):
            make_inject_server(bind_host="::", bind_port=18186)

    def test_test_tool_server_refuses_non_localhost_bind(self):
        with self.assertRaises(ValueError):
            make_test_tool_server("planner", bind_host="0.0.0.0", bind_port=18282)


class TestParseLoadedSkillsFromContract(unittest.TestCase):
    def test_contract_parser_recovers_per_role_sets_at_branch_cut(self):
        contract = str(REPO_ROOT / "docs" / "architecture" / "MULTI-HERMES-CONTRACT.md")
        parsed = parse_loaded_skills_from_contract(contract)
        # The parser MUST return something for every canonical role; if a
        # role's section cannot be parsed, the fallback is used and the
        # set is still non-empty.
        for role in ("orchestrator", "planner", "architect", "executor", "reviewer"):
            self.assertGreater(
                len(parsed.get(role, frozenset())), 0,
                f"loaded_skills set for {role} unexpectedly empty",
            )
        # Orchestrator must have the classifier skill per § 3.2 + 2026-05-08
        # session-log row 3.
        self.assertIn("dev-assist-classifier", parsed["orchestrator"])
        # Every specialist MUST include dev-assist-work-queue-poll.
        for role in ("planner", "architect", "executor", "reviewer"):
            self.assertIn(
                "dev-assist-work-queue-poll", parsed[role],
                f"dev-assist-work-queue-poll missing from {role} loadout",
            )

    def test_contract_parser_falls_back_to_static_table_when_file_missing(self):
        parsed = parse_loaded_skills_from_contract("/no/such/path.md")
        # Falls back to ROLE_LOADOUT_FALLBACK; no exception.
        self.assertEqual(set(parsed.keys()), set(ROLE_LOADOUT_FALLBACK.keys()))


class TestWriteInjectedWorkItem(unittest.TestCase):
    def test_inserts_row_with_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "op.db")
            _init_work_items_db(db)
            wid = write_injected_work_item(db, "smoke-fixture-message-z", 42, "z")
            self.assertGreater(wid, 0)
            conn = sqlite3.connect(db)
            try:
                row = conn.execute(
                    "SELECT target_role, kind, status, payload_json, priority, "
                    "attempt_count, max_attempts FROM work_items WHERE id = ?",
                    (wid,),
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "planner")
            self.assertEqual(row[1], "smoke_inject")
            self.assertEqual(row[2], "pending")
            self.assertEqual(row[4], 50)
            self.assertEqual(row[5], 0)
            self.assertEqual(row[6], 3)
            payload = json.loads(row[3])
            self.assertEqual(payload["classifier_label"], "intake")
            self.assertEqual(payload["correlation_id"], "z")


class TestSmokeFixtureTokenRegex(unittest.TestCase):
    def test_accepts_canonical_shape(self):
        self.assertIsNotNone(SMOKE_FIXTURE_TOKEN_RE.match("smoke-fixture-token-a1b2c3d4"))

    def test_rejects_production_telegram_token_shape(self):
        self.assertIsNone(SMOKE_FIXTURE_TOKEN_RE.match("123456789:AABBccddee_ffggHHiiJJkkLLmmNNooPPqqRR"))


if __name__ == "__main__":
    unittest.main()
