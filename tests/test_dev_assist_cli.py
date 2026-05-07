"""Tests for dev_assist_cli operator CLI.

All offline: mock subprocess.run for journalctl/systemctl, mock urllib for health,
fixture DB via make_fixture_db.py. No real network, no real API keys.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.cli.dev_assist_cli import (
    cmd_costs,
    cmd_errors,
    cmd_escalations,
    cmd_logs,
    cmd_status,
    main,
    parse_duration,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "dev_assist_cli"


def _build_fixture_db(tmpdir: str) -> str:
    db_path = os.path.join(tmpdir, "operational.db")
    from tests.fixtures.dev_assist_cli.make_fixture_db import build_fixture_db
    build_fixture_db(db_path)
    return db_path


class TestParseDuration(unittest.TestCase):
    def test_parse_hours(self):
        result = parse_duration("1h")
        self.assertIn("T", result)
        self.assertIn("Z", result)

    def test_parse_minutes(self):
        result = parse_duration("30m")
        self.assertIn("T", result)

    def test_parse_days(self):
        result = parse_duration("7d")
        self.assertIn("T", result)

    def test_parse_today(self):
        result = parse_duration("today")
        self.assertIn("T00:00:00", result)

    def test_parse_iso_date(self):
        result = parse_duration("2026-05-06")
        self.assertIn("2026-05-06", result)

    def test_parse_invalid_raises(self):
        with self.assertRaises(SystemExit):
            parse_duration("xyz")


class TestStatusCommand(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = _build_fixture_db(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_args(self, fmt="json"):
        args = MagicMock()
        args.db_path = self.db_path
        args.format = fmt
        return args

    def test_status_json_output(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = {
                "ok": True, "status_code": 200,
                "body": {
                    "role": "executor", "state": "running", "uptime_s": 86400,
                    "current_model": "glm-5.1", "current_work_item_id": "1",
                    "heartbeat_age_s": 12,
                }
            }
            mock_sysctl.return_value = "active"

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(self._mock_args("json"))
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            self.assertIn("ts_iso", data)
            self.assertIn("runtimes", data)
            self.assertIn("queue", data)
            self.assertIn("recent_escalations", data)
            self.assertIn("today_token_totals", data)
            self.assertIsInstance(data["runtimes"], list)
            self.assertGreaterEqual(len(data["runtimes"]), 5)

    def test_status_human_output(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = {
                "ok": True, "status_code": 200,
                "body": {
                    "role": "executor", "state": "running", "uptime_s": 86400,
                    "current_model": "glm-5.1", "current_work_item_id": "1",
                    "heartbeat_age_s": 12,
                }
            }
            mock_sysctl.return_value = "active"

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(self._mock_args("human"))
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            self.assertIn("Runtimes:", output)
            self.assertIn("Queue:", output)

    def test_status_health_unreachable(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = {"ok": False, "error": "Connection refused"}
            mock_sysctl.return_value = "unknown"

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(self._mock_args("json"))
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            runtimes = data["runtimes"]
            unreachable = [r for r in runtimes if r.get("health_endpoint_status") == "unreachable"]
            self.assertGreater(len(unreachable), 0)

    def test_status_db_unreachable(self):
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            args = MagicMock()
            args.db_path = "/nonexistent/path/operational.db"
            args.format = "json"
            code = cmd_status(args)
        finally:
            stderr_out = sys.stderr.getvalue()
            sys.stderr = old_stderr

        self.assertNotEqual(code, 0)
        self.assertIn("unreachable", stderr_out)


class TestLogsCommand(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = _build_fixture_db(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_args(self, work_item="1", recursive=False):
        args = MagicMock()
        args.db_path = self.db_path
        args.work_item = work_item
        args.recursive = recursive
        args.since = "today"
        return args

    def test_logs_with_fixture(self):
        fixture_path = str(FIXTURES_DIR / "journal_fixture.jsonl")
        with patch.dict(os.environ, {"DEV_ASSIST_CLI_JOURNAL_FIXTURE": fixture_path}):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_logs(self._mock_args(work_item="1"))
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

        self.assertEqual(code, 0)
        lines = [l for l in output.strip().split("\n") if l]
        self.assertGreater(len(lines), 0)
        for line in lines:
            entry = json.loads(line)
            msg = json.loads(entry["MESSAGE"])
            self.assertEqual(str(msg.get("work_item_id")), "1")

    def test_logs_recursive_with_fixture(self):
        fixture_path = str(FIXTURES_DIR / "journal_fixture.jsonl")
        with patch.dict(os.environ, {"DEV_ASSIST_CLI_JOURNAL_FIXTURE": fixture_path}):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_logs(self._mock_args(work_item="1", recursive=True))
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

        self.assertEqual(code, 0)

    def test_logs_journalctl_unavailable(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("journalctl not found")
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                code = cmd_logs(self._mock_args())
            finally:
                stderr_out = sys.stderr.getvalue()
                sys.stderr = old_stderr
            self.assertNotEqual(code, 0)
            self.assertIn("unavailable", stderr_out)


class TestErrorsCommand(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = _build_fixture_db(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_args(self, since="1h", role=None, fmt="json"):
        args = MagicMock()
        args.db_path = self.db_path
        args.since = since
        args.role = role
        args.format = fmt
        return args

    def test_errors_json_output(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_errors(self._mock_args(since="24h"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIsInstance(data, list)
        if data:
            self.assertIn("err_id", data[0])
            self.assertIn("error_class", data[0])

    def test_errors_human_output(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_errors(self._mock_args(since="24h", fmt="human"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)

    def test_errors_with_role_filter(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_errors(self._mock_args(since="24h", role="executor"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        for row in data:
            self.assertEqual(row["runtime"], "executor")

    def test_errors_db_unreachable(self):
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            args = MagicMock()
            args.db_path = "/nonexistent/path/operational.db"
            args.since = "1h"
            args.role = None
            args.format = "json"
            code = cmd_errors(args)
        finally:
            stderr_out = sys.stderr.getvalue()
            sys.stderr = old_stderr

        self.assertNotEqual(code, 0)
        self.assertIn("unreachable", stderr_out)


class TestCostsCommand(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = _build_fixture_db(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_args(self, since="today", role=None, model=None, fmt="json"):
        args = MagicMock()
        args.db_path = self.db_path
        args.since = since
        args.role = role
        args.model = model
        args.format = fmt
        return args

    def test_costs_json_output_today(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_costs(self._mock_args(since="today"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("since_iso", data)
        self.assertIn("totals", data)
        self.assertIn("by_role_model", data)
        self.assertIn("tables_queried", data)
        self.assertIn("llm_calls", data["tables_queried"])

    def test_costs_human_output(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_costs(self._mock_args(since="today", fmt="human"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        self.assertIn("Tables queried:", output)

    def test_costs_old_window_forces_daily(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_costs(self._mock_args(since="14d"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("tables_queried", data)
        self.assertIn("llm_calls_daily", data["tables_queried"])

    def test_costs_with_role_filter(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_costs(self._mock_args(since="today", role="executor"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        for b in data["by_role_model"]:
            self.assertEqual(b["role"], "executor")


class TestEscalationsCommand(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = _build_fixture_db(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_args(self, since="24h", fmt="json"):
        args = MagicMock()
        args.db_path = self.db_path
        args.since = since
        args.format = fmt
        return args

    def test_escalations_json_output(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_escalations(self._mock_args(since="48h"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("id", data[0])
        self.assertIn("trigger_kind", data[0])
        self.assertIn("status", data[0])

    def test_escalations_human_output(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_escalations(self._mock_args(since="48h", fmt="human"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        self.assertIn("trigger", output.lower())

    def test_escalations_empty_window(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_escalations(self._mock_args(since="1m"))
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)


class TestIter2Fixes(unittest.TestCase):
    """Iter-2 regression tests for BLOCKER and IMPORTANT fixes."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = _build_fixture_db(cls.tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _mock_health(self, heartbeat_age_s=12):
        return {
            "ok": True, "status_code": 200,
            "body": {
                "role": "executor", "state": "running", "uptime_s": 86400,
                "current_model": "glm-5.1", "current_work_item_id": "1",
                "heartbeat_age_s": heartbeat_age_s,
            }
        }

    # T1
    def test_status_escalated_count_from_escalations_table(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = self._mock_health()
            mock_sysctl.return_value = "active"

            args = MagicMock()
            args.db_path = self.db_path
            args.format = "json"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(args)
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            self.assertIn("queue", data)
            self.assertIn("escalated", data["queue"])
            self.assertGreater(data["queue"]["escalated"], 0)

    # T4
    def test_status_heartbeat_degraded_at_60s(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = self._mock_health(heartbeat_age_s=61)
            mock_sysctl.return_value = "active"

            args = MagicMock()
            args.db_path = self.db_path
            args.format = "json"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(args)
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            for rt in data["runtimes"]:
                if rt["role"] == "executor" and rt["health_endpoint_status"] == 200:
                    self.assertEqual(rt["state"], "degraded")

    # T4b
    def test_status_heartbeat_running_at_59s(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = self._mock_health(heartbeat_age_s=59)
            mock_sysctl.return_value = "active"

            args = MagicMock()
            args.db_path = self.db_path
            args.format = "json"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(args)
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            not_degraded = False
            for rt in data["runtimes"]:
                if rt["role"] in ("planner", "architect") and rt["health_endpoint_status"] == 200:
                    if rt["state"] == "running":
                        not_degraded = True
            self.assertTrue(not_degraded, "At least one runtime without recent errors should be running at 59s heartbeat")

    # T2
    def test_costs_7day_boundary_split_merge(self):
        args = MagicMock()
        args.db_path = self.db_path
        args.since = "8d"
        args.role = None
        args.model = None
        args.format = "json"
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_costs(args)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("tables_queried", data)
        self.assertEqual(data["tables_queried"], ["llm_calls", "llm_calls_daily"])
        self.assertIn("totals", data)
        self.assertGreater(data["totals"]["tokens_in"], 0)
        self.assertGreater(data["totals"]["estimated_usd"], 0)
        self.assertIn("by_role_model", data)
        self.assertIsInstance(data["by_role_model"], list)

    # T3
    def test_costs_7day_boundary_split_merge_fixture(self):
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            recent = conn.execute(
                "SELECT COUNT(*) as cnt FROM llm_calls WHERE ts >= ?",
                ((datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000Z"),)
            ).fetchone()
            older = conn.execute(
                "SELECT COUNT(*) as cnt FROM llm_calls_daily WHERE day < ?",
                ((datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"),)
            ).fetchone()
            self.assertGreater(recent["cnt"], 0, "Fixture must have llm_calls rows <= 7 days old")
            self.assertGreater(older["cnt"], 0, "Fixture must have llm_calls_daily rows > 7 days old")
        finally:
            conn.close()

    # T5
    def test_logs_recursive_stderr_unresolvable_parent(self):
        fixture_path = str(FIXTURES_DIR / "journal_fixture.jsonl")
        with patch.dict(os.environ, {"DEV_ASSIST_CLI_JOURNAL_FIXTURE": fixture_path}):
            args = MagicMock()
            args.db_path = self.db_path
            args.work_item = "9999"
            args.recursive = True
            args.since = "today"
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                code = cmd_logs(args)
            finally:
                stderr_out = sys.stderr.getvalue()
                sys.stderr = old_stderr

            self.assertEqual(code, 0)
            self.assertIn("parent_work_item_id 9999", stderr_out)
            self.assertIn("not found", stderr_out)

    # Iter-3 T1: daily call_count
    def test_costs_daily_call_count(self):
        args = MagicMock()
        args.db_path = self.db_path
        args.since = "14d"
        args.role = None
        args.model = None
        args.format = "json"
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cmd_costs(args)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        data = json.loads(output)
        executor_entry = next((e for e in data["by_role_model"] if e["role"] == "executor"), None)
        self.assertIsNotNone(executor_entry)
        self.assertGreater(executor_entry["calls"], 1)

    # Iter-3 T3: last_error from errors table
    def test_status_last_error_from_errors_table(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = self._mock_health()
            mock_sysctl.return_value = "active"

            args = MagicMock()
            args.db_path = self.db_path
            args.format = "json"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(args)
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            for rt in data["runtimes"]:
                if rt["role"] == "executor" and rt["health_endpoint_status"] == 200:
                    self.assertIsNotNone(rt["last_error"])
                    self.assertIn("ts_iso", rt["last_error"])
                    self.assertIn("error_class", rt["last_error"])

    # Iter-3 T4: degraded on recent error
    def test_status_degraded_on_recent_error(self):
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = self._mock_health(heartbeat_age_s=12)
            mock_sysctl.return_value = "active"

            args = MagicMock()
            args.db_path = self.db_path
            args.format = "json"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cmd_status(args)
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(output)
            for rt in data["runtimes"]:
                if rt["role"] == "executor" and rt["health_endpoint_status"] == 200:
                    self.assertEqual(rt["state"], "degraded")

    # Iter-3 T5: logs --role filter
    def test_logs_role_filter(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            args = MagicMock()
            args.work_item = None
            args.role = "executor"
            args.recursive = False
            args.since = "today"
            cmd_logs(args)
            mock_run.assert_called_once()
            called_cmd = mock_run.call_args[0][0]
            self.assertIn("-u", called_cmd)
            self.assertIn("devassist-executor.service", called_cmd)
            self.assertNotIn("devassist-planner.service", called_cmd)


class TestMainAndHelp(unittest.TestCase):
    def test_help_shows_all_subcommands(self):
        with patch.dict(os.environ, {"DEV_ASSIST_DB_PATH": ":memory:"}):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = main(["--help"])
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout

        self.assertNotEqual(code, 2)
        for cmd_name in ["status", "logs", "errors", "costs", "escalations"]:
            self.assertIn(cmd_name, output)

    def test_status_subcommand_in_main(self):
        with patch.dict(os.environ, {"DEV_ASSIST_DB_PATH": ":memory:"}):
            with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
                 patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
                mock_health.return_value = {
                    "ok": True, "status_code": 200,
                    "body": {
                        "role": "executor", "state": "running", "uptime_s": 86400,
                        "current_model": "glm-5.1", "current_work_item_id": "1",
                        "heartbeat_age_s": 12,
                    }
                }
                mock_sysctl.return_value = "active"

                tmpdir = tempfile.mkdtemp()
                db_path = _build_fixture_db(tmpdir)
                try:
                    old_stdout = sys.stdout
                    sys.stdout = io.StringIO()
                    try:
                        code = main(["--db-path", db_path, "status"])
                    finally:
                        output = sys.stdout.getvalue()
                        sys.stdout = old_stdout

                    self.assertEqual(code, 0)
                    data = json.loads(output)
                    self.assertIn("runtimes", data)
                finally:
                    import shutil
                    shutil.rmtree(tmpdir, ignore_errors=True)

    def test_no_command_produces_error(self):
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            code = main([])
        finally:
            sys.stderr = old_stderr
        self.assertNotEqual(code, 0)


class TestJsonSchemas(unittest.TestCase):
    """Verify outputs match the checked-in JSON schemas."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.db_path = _build_fixture_db(cls.tmpdir)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _capture_stdout(self, func, args):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = func(args)
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
        return code, output

    def _load_schema(self, name):
        schema_path = FIXTURES_DIR / "schemas" / name
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)

    def test_status_matches_schema(self):
        schema = self._load_schema("status_schema.json")
        with patch("developer_assistant.observability.status_query._check_health_endpoint") as mock_health, \
             patch("developer_assistant.observability.status_query._check_systemctl_unit") as mock_sysctl:
            mock_health.return_value = {
                "ok": True, "status_code": 200,
                "body": {
                    "role": "executor", "state": "running", "uptime_s": 86400,
                    "current_model": "glm-5.1", "current_work_item_id": "1",
                    "heartbeat_age_s": 12,
                }
            }
            mock_sysctl.return_value = "active"

            args = MagicMock()
            args.db_path = self.db_path
            args.format = "json"
            code, output = self._capture_stdout(cmd_status, args)
            self.assertEqual(code, 0)
            data = json.loads(output)
            self.assertIsInstance(data["runtimes"], list)
            self.assertIsInstance(data["queue"], dict)
            self.assertIn("pending", data["queue"])
            self.assertIsInstance(data["recent_escalations"], list)
            self.assertIsInstance(data["today_token_totals"], list)

    def test_errors_json_is_valid_array(self):
        schema = self._load_schema("errors_schema.json")
        args = MagicMock()
        args.db_path = self.db_path
        args.since = "24h"
        args.role = None
        args.format = "json"
        code, output = self._capture_stdout(cmd_errors, args)
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIsInstance(data, list)

    def test_costs_matches_schema(self):
        schema = self._load_schema("costs_schema.json")
        args = MagicMock()
        args.db_path = self.db_path
        args.since = "today"
        args.role = None
        args.model = None
        args.format = "json"
        code, output = self._capture_stdout(cmd_costs, args)
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("totals", data)
        self.assertIn("tokens_in", data["totals"])
        self.assertIn("by_role_model", data)
        self.assertIsInstance(data["by_role_model"], list)

    def test_escalations_matches_schema(self):
        schema = self._load_schema("escalations_schema.json")
        args = MagicMock()
        args.db_path = self.db_path
        args.since = "48h"
        args.format = "json"
        code, output = self._capture_stdout(cmd_escalations, args)
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIsInstance(data, list)
        if data:
            self.assertIn("trigger_kind", data[0])
            self.assertIn("status", data[0])


if __name__ == "__main__":
    unittest.main()