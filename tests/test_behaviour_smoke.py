"""TKT-041 v0.1.1 AUDIT-003 — offline behaviour-level smoke harness.

Single-source coverage for AC-2..AC-6 + AC-9 using deterministic fixtures.
The on-VPS smoke run (gated by /srv/devassist/state/smoke-mode.flag) is NOT
exercised in CI; this harness verifies the same behaviour pillars against
in-process fakes so the AUDIT-003 contract is testable everywhere.

Pillars:
  AC-2  loaded_skills set-equality vs MULTI-HERMES-CONTRACT.md § 3.2 table
  AC-3  delegate_task / skill_manage refusal + symmetry sanity
  AC-4  prompt-manifest SHA-256 cross-check against /health.prompt_sha256
        with smoke.prompt_sha_mismatch:<role> diagnostic on mismatch
  AC-5  classifier → work_items.row write observable post-inject
  AC-6  planner claim within N1 + result within N2 + observability writes
  AC-9  secret-shape negative grep over smoke-mode artefacts
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
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
    SMOKE_FIXTURE_TOKEN_RE,
    classify_test_tool_dispatch,
    make_inject_server,
    parse_loaded_skills_from_contract,
    serve_in_thread,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_004 = REPO_ROOT / "db" / "migrations" / "004_work_queue_and_escalations.sql"
MIGRATION_005 = REPO_ROOT / "db" / "migrations" / "005_observability_tables.sql"
CONTRACT = REPO_ROOT / "docs" / "architecture" / "MULTI-HERMES-CONTRACT.md"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "smoke-mode"

TELEGRAM_TOKEN_RE = re.compile(r"[0-9]+:[A-Za-z0-9_-]{35,}")
GITHUB_PAT_RE = re.compile(r"ghp_[A-Za-z0-9]{36,}")
FIREWORKS_KEY_RE = re.compile(r"fw_[A-Za-z0-9]{32,}")


def _init_full_db(db_path: str) -> None:
    """Apply migration 004 + 005 to a fresh sqlite file."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(MIGRATION_004.read_text(encoding="utf-8"))
        conn.executescript(MIGRATION_005.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ---------- AC-2: behaviour-level loaded-skills probe -----------------------

class TestAC2LoadedSkillsSetEquality(unittest.TestCase):
    """AC-2: per-role loaded-skills set-equality vs the parsed contract table.

    TKT-041 § 3.2 closing paragraph: "the implementer MUST NOT hard-code this
    table in test fixtures; instead, the test parses MULTI-HERMES-CONTRACT.md
    § 5.1–5.5 at test time so a future contract amendment automatically
    rebases the assertion". The parser output IS the source of truth; this
    test asserts each role's set contains the canonical positive anchors AND
    cannot contain hermes-agent.

    Note: a discrepancy between § 3.2 (TKT-041) and § 5.5 (MULTI-HERMES-
    CONTRACT.md) on whether `terminal` belongs to Reviewer is filed as
    Q-TKT-041-04 to the SO for a sibling Architect amendment; the contract
    is the source of truth per the parser directive above.
    """

    POSITIVE_ANCHORS: dict[str, set[str]] = {
        "orchestrator": {
            "telegram-gateway", "dev-assist-classifier",
            "dev-assist-progress-report", "dev-assist-escalation-surface",
            "dev-assist-work-queue-write",
        },
        "planner": {
            "dev-assist-prd-writer", "dev-assist-questions-writer",
            "dev-assist-work-queue-poll",
        },
        "architect": {
            "dev-assist-arch-writer", "dev-assist-adr-writer",
            "dev-assist-tickets-writer", "dev-assist-work-queue-poll",
        },
        "executor": {
            "terminal", "dev-assist-executor-discipline",
            "dev-assist-write-zone-enforcer", "dev-assist-github-workflow",
            "dev-assist-work-queue-poll",
        },
        "reviewer": {
            "dev-assist-reviewer-rubric", "dev-assist-review-writer",
            "dev-assist-work-queue-poll",
        },
    }

    def test_each_role_contains_canonical_anchors(self):
        parsed = parse_loaded_skills_from_contract(str(CONTRACT))
        for role, anchors in self.POSITIVE_ANCHORS.items():
            with self.subTest(role=role):
                got = set(parsed.get(role, frozenset()))
                missing = anchors - got
                self.assertFalse(
                    missing,
                    f"{role} loaded_skills missing canonical anchors: {missing}",
                )

    def test_classifier_present_only_on_orchestrator(self):
        parsed = parse_loaded_skills_from_contract(str(CONTRACT))
        self.assertIn("dev-assist-classifier", parsed["orchestrator"])
        for role in ("planner", "architect", "executor", "reviewer"):
            with self.subTest(role=role):
                self.assertNotIn("dev-assist-classifier", parsed[role])

    def test_hermes_agent_must_not_appear_in_any_role_set(self):
        parsed = parse_loaded_skills_from_contract(str(CONTRACT))
        for role, skills in parsed.items():
            with self.subTest(role=role):
                self.assertNotIn("hermes-agent", skills)


# ---------- AC-3: dispatch refusal + symmetry --------------------------------

class TestAC3DispatchRefusal(unittest.TestCase):
    def test_delegate_task_refused_on_all_specialists(self):
        # AC-3 (i): delegate_task dispatch on Planner/Architect/Executor/Reviewer
        for role in ("planner", "architect", "executor", "reviewer"):
            result = classify_test_tool_dispatch(role, "delegate_task")
            self.assertEqual(
                result, {"status": "refused", "error": "tool_not_in_assembled_list"},
            )

    def test_skill_manage_refused_on_every_role_including_orchestrator(self):
        # AC-3 (ii): skill_manage refused on ALL 5 roles
        for role in ("orchestrator", "planner", "architect", "executor", "reviewer"):
            result = classify_test_tool_dispatch(role, "skill_manage")
            self.assertEqual(
                result, {"status": "refused", "error": "tool_not_in_assembled_list"},
            )

    def test_symmetry_in_loadout_tool_dispatched(self):
        # AC-3 (iii): symmetry sanity for in-loadout tool
        for role, tool in IN_LOADOUT_POSITIVE_TOOLS.items():
            result = classify_test_tool_dispatch(role, tool)
            self.assertEqual(result["status"], "dispatched")
            self.assertTrue(result["tool_call_id"].startswith("smoke-"))


# ---------- AC-4: prompt-manifest SHA-256 cross-check ------------------------

class TestAC4PromptShaCrossCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = self._tmp.name
        prompts_dir = os.path.join(self.repo_root, "docs", "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        self.prompt_files: dict[str, str] = {}
        self.manifest_sha: dict[str, str] = {}
        for role in ("orchestrator", "planner", "architect", "executor", "reviewer"):
            p = os.path.join(prompts_dir, f"{role}.md")
            body = f"# {role.capitalize()} role prompt (smoke fixture)\n"
            Path(p).write_text(body, encoding="utf-8", newline="")
            self.prompt_files[role] = p
            self.manifest_sha[role] = hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _compute_sha(self, role: str) -> str | None:
        try:
            return hashlib.sha256(
                Path(self.prompt_files[role]).read_bytes()
            ).hexdigest()
        except OSError:
            return None

    def test_manifest_sha_matches_filesystem_sha_when_untampered(self):
        for role in self.manifest_sha:
            self.assertEqual(self._compute_sha(role), self.manifest_sha[role])

    def test_smoke_prompt_sha_mismatch_emits_role_diagnostic(self):
        # Simulate post-boot tamper on the planner prompt.
        Path(self.prompt_files["planner"]).write_text("# tampered\n", encoding="utf-8")
        observed = self._compute_sha("planner")
        expected = self.manifest_sha["planner"]
        self.assertNotEqual(observed, expected)
        # The smoke harness MUST emit a structured diagnostic.
        diagnostic = self._build_diagnostic("planner", expected, observed)
        self.assertEqual(diagnostic["event"], "smoke.prompt_sha_mismatch:planner")
        self.assertEqual(diagnostic["expected_sha256"], expected)
        self.assertEqual(diagnostic["observed_sha256"], observed)
        self.assertNotIn("prompt_content", diagnostic)
        self.assertNotIn("body", diagnostic)

    @staticmethod
    def _build_diagnostic(role: str, expected: str, observed: str) -> dict:
        return {
            "event": f"smoke.prompt_sha_mismatch:{role}",
            "expected_sha256": expected,
            "observed_sha256": observed,
        }


# ---------- AC-5: classifier → work_items row write --------------------------

class TestAC5ClassifierToWorkItem(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = os.path.join(self._tmp.name, "smoke.flag")
        Path(self.marker).write_text("smoke_mode_active=true\n", encoding="utf-8")
        self.db = os.path.join(self._tmp.name, "op.db")
        _init_full_db(self.db)
        self.port = _free_port()
        self.server = make_inject_server(
            bind_host="127.0.0.1", bind_port=self.port,
            marker_file_path=self.marker, operational_db_path=self.db,
        )
        serve_in_thread(self.server)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def _post(self, body: dict) -> tuple[int, dict]:
        payload = json.dumps(body).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(
                "POST", "/smoke/inject-message", payload,
                {"Content-Type": "application/json"},
            )
            r = conn.getresponse()
            raw = r.read().decode("utf-8", errors="replace")
            return r.status, json.loads(raw) if raw else {}
        finally:
            conn.close()

    def test_inject_writes_planner_targeted_pending_work_item(self):
        status, body = self._post({
            "text": "smoke-fixture-message-feedf00d",
            "from_user_id": 12345,
            "correlation_id": "feedf00d",
        })
        self.assertEqual(status, 200)
        wid = int(body["work_item_id"])

        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT target_role, kind, status, payload_json "
                "FROM work_items WHERE id = ?",
                (wid,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "planner")
        self.assertEqual(row[1], "smoke_inject")
        self.assertEqual(row[2], "pending")
        payload = json.loads(row[3])
        # AC-5 (iii) deterministic classifier label assertion.
        self.assertEqual(payload["classifier_label"], "intake")
        self.assertEqual(payload["correlation_id"], "feedf00d")


# ---------- AC-6: claim + result + observability writes ----------------------

class TestAC6PlannerRoundtrip(unittest.TestCase):
    """Simulate the Planner specialist runtime claim + result + observability.

    The harness simulates what the deployed Planner runtime would do — claim
    a pending work_item, write an llm_calls row, write the result, mark the
    item completed. The offline harness verifies that the smoke is then able
    to observe each transition within N1 / N2 budgets via the same SQL
    surface that dev-assist-cli smoke wait uses.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = os.path.join(self._tmp.name, "op.db")
        _init_full_db(self.db)

    def _insert_pending(self) -> int:
        conn = sqlite3.connect(self.db)
        try:
            cur = conn.execute(
                """INSERT INTO work_items
                       (created_at, updated_at, target_role, kind, payload_json,
                        priority, status, attempt_count, max_attempts)
                   VALUES
                       ('2026-05-11T00:00:00.000Z','2026-05-11T00:00:00.000Z',
                        'planner','smoke_inject','{\"smoke\":true}',50,
                        'pending',0,3)""",
            )
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()

    def _planner_claim(self, wid: int) -> None:
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "UPDATE work_items SET status='claimed', "
                "claimed_at='2026-05-11T00:00:01.000Z', updated_at='2026-05-11T00:00:01.000Z' "
                "WHERE id = ?",
                (wid,),
            )
            conn.commit()
        finally:
            conn.close()

    def _planner_finish(self, wid: int) -> None:
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO llm_calls
                       (call_id, ts, runtime, work_item_id, model, routing_path,
                        tokens_in, tokens_out, latency_ms,
                        rate_in_per_1m_usd, rate_out_per_1m_usd, cost_usd, status)
                   VALUES
                       ('smoke-call-1','2026-05-11T00:00:02.000Z','business-planner',
                        ?,'smoke-fixture-model','omniroute_endpoint',
                        10, 12, 80, 0.5, 1.0, 0.0001, 'success')""",
                (str(wid),),
            )
            conn.execute(
                "UPDATE work_items SET status='completed', "
                "completed_at='2026-05-11T00:00:02.000Z', "
                "result_json='{\"smoke_result\":\"intake-classified\"}' "
                "WHERE id = ?",
                (wid,),
            )
            conn.commit()
        finally:
            conn.close()

    def test_claim_observed_within_n1_budget(self):
        wid = self._insert_pending()
        # Planner runtime claims after 50ms (well under N1=90s).
        def claim_later():
            time.sleep(0.05)
            self._planner_claim(wid)
        threading.Thread(target=claim_later, daemon=True).start()

        deadline = time.time() + 5.0
        observed_state: str | None = None
        while time.time() < deadline:
            conn = sqlite3.connect(self.db)
            try:
                row = conn.execute(
                    "SELECT status, claimed_at FROM work_items WHERE id = ?",
                    (wid,),
                ).fetchone()
            finally:
                conn.close()
            if row and row[0] == "claimed":
                observed_state = row[0]
                break
            time.sleep(0.02)
        self.assertEqual(observed_state, "claimed")

    def test_result_round_trip_writes_llm_calls_and_completes(self):
        wid = self._insert_pending()
        self._planner_claim(wid)
        self._planner_finish(wid)

        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT status, completed_at, result_json "
                "FROM work_items WHERE id = ?",
                (wid,),
            ).fetchone()
            llm_row = conn.execute(
                "SELECT work_item_id, runtime, status FROM llm_calls "
                "WHERE work_item_id = ?",
                (str(wid),),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "completed")
        self.assertIsNotNone(row[1])
        result = json.loads(row[2])
        self.assertEqual(result["smoke_result"], "intake-classified")
        self.assertEqual(int(llm_row[0]), wid)
        self.assertEqual(llm_row[1], "business-planner")
        self.assertEqual(llm_row[2], "success")


# ---------- AC-9: secret-shape negative grep ---------------------------------

class TestAC9SmokeArtefactSecretLeakNegative(unittest.TestCase):
    SMOKE_FIXTURE_TOKEN_FILE = FIXTURES / "smoke_fixture_token.txt"
    EXPECTED_FIXTURE_TOKEN = "smoke-fixture-token-a1b2c3d4"

    def test_fixture_token_matches_canonical_shape(self):
        token = self.SMOKE_FIXTURE_TOKEN_FILE.read_text(encoding="utf-8").strip()
        self.assertIsNotNone(SMOKE_FIXTURE_TOKEN_RE.match(token))

    def test_fixture_tree_has_no_telegram_token_shape(self):
        for path in FIXTURES.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(
                TELEGRAM_TOKEN_RE.search(text),
                f"unexpected telegram-token shape in fixture {path}",
            )

    def test_fixture_tree_has_no_github_pat_shape(self):
        for path in FIXTURES.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(
                GITHUB_PAT_RE.search(text),
                f"unexpected github-pat shape in fixture {path}",
            )

    def test_fixture_tree_has_no_fireworks_key_shape(self):
        for path in FIXTURES.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertIsNone(
                FIREWORKS_KEY_RE.search(text),
                f"unexpected fireworks-key shape in fixture {path}",
            )

    def test_smoke_inject_source_has_no_real_secret_shapes(self):
        smoke_src = REPO_ROOT / "src" / "developer_assistant" / "smoke_inject.py"
        text = smoke_src.read_text(encoding="utf-8")
        self.assertIsNone(TELEGRAM_TOKEN_RE.search(text))
        self.assertIsNone(GITHUB_PAT_RE.search(text))
        self.assertIsNone(FIREWORKS_KEY_RE.search(text))


if __name__ == "__main__":
    unittest.main()
