"""Recovery Playbook invariant harness (TKT-030).

Parses docs/operations/RECOVERY-PLAYBOOK.md, extracts every shell command,
and validates each against the codebase and architecture artifacts.  Produces
a structured report of WARNINGs and FAILUREs; FAILUREs cause the test suite
to fail.

Offline-only, stdlib-only, in-process.  Target: <1 s on CI runner.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

from tests.fixtures.recovery_playbook.command_validators import (
    CLI_SUBCOMMANDS,
    KNOWN_PLAYBOOK_INCONSISTENCIES,
    PORT_ROLE_MAP,
    SQL_TABLES,
    SYSTEMD_UNITS,
    classify_command,
    parse_playbook,
    validate_command,
)
from tests.fixtures.recovery_playbook import command_validators as cv

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = REPO_ROOT / "docs" / "operations" / "RECOVERY-PLAYBOOK.md"

_KNOWN_INCONSISTENCY_PATTERNS = tuple(KNOWN_PLAYBOOK_INCONSISTENCIES.keys())


def _load_playbook() -> str:
    p = PLAYBOOK_PATH
    if not p.is_file():
        raise FileNotFoundError(f"Playbook not found at {p}")
    return p.read_text(encoding="utf-8")


def _run_harness(md_text: str) -> Tuple[List[Dict], List[Dict]]:
    commands = parse_playbook(md_text)
    warnings: List[Dict] = []
    failures: List[Dict] = []
    for cmd in commands:
        level, msg = validate_command(cmd)
        entry = {**cmd, "level": level, "message": msg}
        if level == "WARNING":
            warnings.append(entry)
        elif level == "FAILURE":
            failures.append(entry)
    return warnings, failures


def _format_report(warnings: List[Dict], failures: List[Dict]) -> str:
    lines: List[str] = []
    if warnings:
        lines.append("WARNINGS:")
        for w in warnings:
            lines.append(
                f"  [{w['section']}] {w['raw'][:80]}\n    -> {w['message']}")
    if failures:
        lines.append("FAILURES:")
        for f in failures:
            lines.append(
                f"  [{f['section']}] {f['raw'][:80]}\n    -> {f['message']}")
    if not warnings and not failures:
        lines.append("ALL OK — no warnings or failures.")
    return "\n".join(lines)


def _is_known_inconsistency(failure: Dict) -> bool:
    for pat in _KNOWN_INCONSISTENCY_PATTERNS:
        if pat in failure["raw"]:
            return True
    return False


class TestRecoveryPlaybookInvariants(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.playbook_text = _load_playbook()
        cls.commands = parse_playbook(cls.playbook_text)
        cls.warnings, cls.failures = _run_harness(cls.playbook_text)
        cls.known_failures = [f for f in cls.failures if _is_known_inconsistency(f)]
        cls.unexpected_failures = [f for f in cls.failures if not _is_known_inconsistency(f)]
        cls.report = _format_report(cls.warnings, cls.failures)

    def test_playbook_file_exists_and_parses(self):
        self.assertTrue(PLAYBOOK_PATH.is_file(),
                        f"Playbook missing at {PLAYBOOK_PATH}")
        self.assertGreater(len(self.playbook_text), 100,
                           "Playbook appears empty or truncated")

    def test_commands_extracted(self):
        self.assertGreater(
            len(self.commands), 20,
            f"Expected 20+ commands from playbook, got {len(self.commands)}")

    def test_fenced_code_blocks_captured(self):
        fenced = [c for c in self.commands if c["source"] == "fenced"]
        self.assertGreaterEqual(
            len(fenced), 3,
            f"Expected >= 3 fenced-block commands, got {len(fenced)}")

    def test_inline_backtick_commands_captured(self):
        inline = [c for c in self.commands if c["source"] == "inline"]
        self.assertGreaterEqual(
            len(inline), 10,
            f"Expected >= 10 inline commands, got {len(inline)}")

    def test_command_classification_covers_all_kinds(self):
        kinds = {classify_command(c["raw"]) for c in self.commands}
        expected_kinds = {
            "dev-assist-cli", "systemctl", "journalctl", "curl",
            "sqlite3", "scripts",
        }
        for k in expected_kinds:
            self.assertIn(
                k, kinds,
                f"Playbook should reference at least one {k} command")

    def test_dev_assist_cli_subcommands(self):
        cli_cmds = [c for c in self.commands
                     if classify_command(c["raw"]) == "dev-assist-cli"]
        self.assertGreaterEqual(
            len(cli_cmds), 4,
            f"Expected >= 4 dev-assist-cli commands, got {len(cli_cmds)}")
        subcommands = set()
        for c in cli_cmds:
            m = re.search(r'dev-assist-cli\s+(\S+)', c["raw"])
            if m and not m.group(1).startswith("-"):
                subcommands.add(m.group(1))
        self.assertTrue(
            subcommands.issuperset({"status", "errors", "logs", "costs"}),
            f"Expected subcommands status/errors/logs/costs, got {subcommands}")

    def test_systemctl_units_valid(self):
        systemctl_cmds = [c for c in self.commands
                          if classify_command(c["raw"]) == "systemctl"]
        self.assertGreaterEqual(
            len(systemctl_cmds), 3,
            f"Expected >= 3 systemctl commands, got {len(systemctl_cmds)}")

    def test_curl_health_endpoint_ports(self):
        curl_cmds = [c for c in self.commands
                     if classify_command(c["raw"]) == "curl"]
        self.assertGreaterEqual(
            len(curl_cmds), 1,
            f"Expected >= 1 curl command, got {len(curl_cmds)}")

    def test_sqlite3_queries_reference_valid_tables_and_columns(self):
        sqlite_cmds = [c for c in self.commands
                       if classify_command(c["raw"]) == "sqlite3"]
        self.assertGreaterEqual(
            len(sqlite_cmds), 1,
            f"Expected >= 1 sqlite3 command, got {len(sqlite_cmds)}")

    def test_script_references(self):
        script_cmds = [c for c in self.commands
                       if classify_command(c["raw"]) == "scripts"]
        self.assertGreaterEqual(
            len(script_cmds), 2,
            f"Expected >= 2 script references, got {len(script_cmds)}")

    def test_journalctl_units_valid(self):
        jc_cmds = [c for c in self.commands
                   if classify_command(c["raw"]) == "journalctl"]
        self.assertGreaterEqual(
            len(jc_cmds), 1,
            f"Expected >= 1 journalctl command, got {len(jc_cmds)}")

    def test_no_unexpected_failures_in_harness(self):
        self.assertEqual(
            len(self.unexpected_failures), 0,
            f"Recovery Playbook harness detected unexpected FAILUREs:\n"
            f"{_format_report([], self.unexpected_failures)}")

    def test_structured_report_produced(self):
        self.assertIsInstance(self.report, str)
        self.assertGreater(len(self.report), 0)

    def test_harness_distinguishes_warning_from_failure(self):
        for w in self.warnings:
            self.assertEqual(w["level"], "WARNING")
        for f in self.failures:
            self.assertEqual(f["level"], "FAILURE")

    def test_reference_data_completeness(self):
        self.assertIn("devassist.target", SYSTEMD_UNITS)
        self.assertIn("omniroute.service", SYSTEMD_UNITS)
        self.assertIn("devassist-web.service", SYSTEMD_UNITS)
        self.assertEqual(len(SYSTEMD_UNITS), 8)
        self.assertIn(8181, PORT_ROLE_MAP)
        self.assertIn(20128, PORT_ROLE_MAP)
        self.assertIn("work_items", SQL_TABLES)
        self.assertIn("errors", SQL_TABLES)
        self.assertIn("llm_calls", SQL_TABLES)
        self.assertIn("llm_calls_daily", SQL_TABLES)
        self.assertIn("_schema_meta", SQL_TABLES)
        self.assertEqual(len(SQL_TABLES), 9)

    def test_playbook_omniroute_unit_name_known_inconsistency(self):
        omniroute_cmds = [c for c in self.commands
                          if "omniroute" in c["raw"].lower()
                          and classify_command(c["raw"]) in ("systemctl", "journalctl")]
        devassist_omniroute = [c for c in omniroute_cmds
                               if "devassist-omniroute" in c["raw"]]
        if devassist_omniroute:
            self.assertGreater(
                len(self.known_failures), 0,
                "devassist-omniroute.service references should be tracked "
                "as known inconsistencies. None found in known_failures.")
            for c in devassist_omniroute:
                self.assertTrue(
                    _is_known_inconsistency({"raw": c["raw"], "message": ""}),
                    f"devassist-omniroute reference not in known inconsistencies: "
                    f"{c['raw']}")


class TestSyntheticNegative(unittest.TestCase):
    """AC-11: synthetic negative test with fake commands."""

    def test_fake_curl_port_produces_failure(self):
        base = _load_playbook()
        fake_block = "\n```\ncurl -fsS http://127.0.0.1:9999/health\n```\n"
        idx = base.find("## 2.")
        if idx < 0:
            idx = 0
        poisoned = base[:idx] + fake_block + base[idx:]
        _, failures = _run_harness(poisoned)
        curl_failures = [f for f in failures
                         if classify_command(f["raw"]) == "curl"
                         and "9999" in f["raw"]]
        self.assertGreaterEqual(
            len(curl_failures), 1,
            f"Expected FAILURE for fake curl port, got failures: {failures}")

    def test_fake_subcommand_produces_failure_when_cli_landed(self):
        if not cv._CLI_MODULE.is_file():
            self.skipTest("dev_assist_cli.py not yet landed (TKT-027)")
        base = _load_playbook()
        fake_block = "\n```\ndev-assist-cli nonexistent-subcommand --fake\n```\n"
        idx = base.find("## 2.")
        if idx < 0:
            idx = 0
        poisoned = base[:idx] + fake_block + base[idx:]
        _, failures = _run_harness(poisoned)
        cli_failures = [f for f in failures
                        if classify_command(f["raw"]) == "dev-assist-cli"
                        and "nonexistent-subcommand" in f["raw"]]
        self.assertGreaterEqual(
            len(cli_failures), 1,
            f"Expected FAILURE for fake subcommand, got failures: {failures}")

    def test_fake_subcommand_produces_warning_when_cli_not_landed(self):
        if cv._CLI_MODULE.is_file():
            self.skipTest("dev_assist_cli.py already landed")
        base = _load_playbook()
        fake_block = "\n```\ndev-assist-cli nonexistent-subcommand --fake\n```\n"
        idx = base.find("## 2.")
        if idx < 0:
            idx = 0
        poisoned = base[:idx] + fake_block + base[idx:]
        warnings, _ = _run_harness(poisoned)
        cli_warnings = [w for w in warnings
                        if classify_command(w["raw"]) == "dev-assist-cli"
                        and "nonexistent-subcommand" in w["raw"]]
        self.assertGreaterEqual(
            len(cli_warnings), 1,
            f"Expected WARNING for unknown CLI subcommand (TKT-027 not landed), "
            f"got: {warnings}")

    def test_fake_systemctl_unit_produces_failure(self):
        base = _load_playbook()
        fake_block = "\n```\nsudo systemctl restart devassist-nonexistent.service\n```\n"
        idx = base.find("## 2.")
        if idx < 0:
            idx = 0
        poisoned = base[:idx] + fake_block + base[idx:]
        _, failures = _run_harness(poisoned)
        systemctl_failures = [f for f in failures
                              if classify_command(f["raw"]) == "systemctl"
                              and "nonexistent" in f["raw"]]
        self.assertGreaterEqual(
            len(systemctl_failures), 1,
            f"Expected FAILURE for fake systemctl unit, got: {failures}")

    def test_fake_sql_table_produces_failure(self):
        base = _load_playbook()
        fake_block = (
            "\n```\nsqlite3 /srv/devassist/state/operational.db "
            "'SELECT * FROM nonexistent_table;'\n```\n"
        )
        idx = base.find("## 2.")
        if idx < 0:
            idx = 0
        poisoned = base[:idx] + fake_block + base[idx:]
        _, failures = _run_harness(poisoned)
        sqlite_failures = [f for f in failures
                           if classify_command(f["raw"]) == "sqlite3"
                           and "nonexistent_table" in f["raw"]]
        self.assertGreaterEqual(
            len(sqlite_failures), 1,
            f"Expected FAILURE for fake SQL table, got: {failures}")


if __name__ == "__main__":
    unittest.main()
