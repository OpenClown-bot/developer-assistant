"""Tests for developer_assistant.runtime_check.

All tests are offline-only, use placeholder values, and do not require
real Hermes binary, real LLM credentials, real Telegram bot, or real GitHub access.
Uses fixture mode with real temp SQLite files.

Platform guard: tests that require symlinks skip gracefully on Windows.

Test layering follows TKT-033 § 4 AC-4 / AC-5:
  - TestRoleValueError ... TestTelegramGatewayNonOrchestrator: TKT-021 § 1 (a)-(e)
    invariants preserved per AC-5 (raise-side contract unchanged); each test
    additionally asserts the structured RUNTIME_CHECK_FAILED marker is emitted
    on stderr immediately before the raise.
  - TestRuntimeCheckInvariantsEnum: AC-5 enum equality / public surface.
  - TestDelegateTaskCallable / TestSkillManageCallable: AC-3 (i) / (ii).
  - TestPromptManifest: AC-3 (iii) -- prompt_manifest_missing + prompt_sha_mismatch.
  - TestRuntimeCheckCli: CLI shim returns RUNTIME_CHECK_ABORT_EXIT_CODE on fail.
  - TestAllRolesPass: end-to-end fixture for all five roles with manifest set up.
"""

from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.runtime_check import (
    DelegateTaskCallableError,
    INVARIANT_DELEGATE_TASK_CALLABLE,
    INVARIANT_LOADED_SKILLS_MISMATCH,
    INVARIANT_NON_ORCHESTRATOR_TELEGRAM_SKILL_LOADED,
    INVARIANT_OPERATIONAL_DB_PATH_MISMATCH,
    INVARIANT_ORCHESTRATOR_TELEGRAM_TOKEN_MISSING,
    INVARIANT_PROMPT_MANIFEST_MISSING,
    INVARIANT_PROMPT_SHA_MISMATCH,
    INVARIANT_ROLE_ENV_INVALID,
    INVARIANT_ROLE_ENV_UNSET,
    INVARIANT_SCHEMA_VERSION_MISMATCH,
    INVARIANT_SKILL_MANAGE_CALLABLE,
    OperationalDbPathError,
    PROMPT_FILE_BY_ROLE,
    PromptManifestMissingError,
    PromptShaMismatchError,
    RUNTIME_CHECK_ABORT_EXIT_CODE,
    RUNTIME_CHECK_INVARIANTS,
    RoleValueError,
    SchemaVersionMismatchError,
    SkillManageCallableError,
    SkillsMismatchError,
    TelegramGatewayLoadedError,
    TelegramTokenMissingError,
    _attempt_hermes_filter_assertion,
    check_runtime,
)


def _symlink_works() -> bool:
    if sys.platform != "win32":
        return True
    try:
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src")
            dst = os.path.join(td, "dst")
            with open(src, "w") as fh:
                fh.write("test")
            os.symlink(src, dst)
            return True
    except (OSError, NotImplementedError):
        return False


def _write_minimal_config(path: str, built_in_skills: list[str], include_external_dirs: bool = False) -> None:
    lines_arr = ["agent:", "  model: accounts/fireworks/models/glm-5p1", "", "skills:", "  built_in:"]
    for skill in built_in_skills:
        lines_arr.append("  - " + skill)
    if include_external_dirs:
        lines_arr.extend([
            "  external_dirs:",
            "    - /srv/devassist/shared-skills/",
        ])
    lines_arr.extend([
        "",
        "plugins:",
        "  enabled:",
        "    - dev-assist-escalation-policy",
        "    - dev-assist-work-queue",
        "  disabled:",
        "    - skill_manage",
        "    - delegate_task",
        "",
        "approvals:",
        "  mode: manual",
        "",
        "gateway:",
        "  enabled: false",
    ])
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines_arr) + "\n")


def _create_operational_db(path: str, schema_version: str = "3") -> None:
    conn = sqlite3.connect(path, timeout=1.0)
    conn.execute("CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
    conn.execute("INSERT OR REPLACE INTO _schema_meta (key, value) VALUES (?, ?);", ("schema_version", schema_version))
    conn.commit()
    conn.close()


def _setup_prompt_fixture(
    td: str,
    role: str,
    *,
    body: str = "# fixture-prompt\n",
    inject_sha: str | None = None,
    omit_role_entry: bool = False,
) -> tuple[str, str]:
    """Build a (prompt_path, manifest_path) fixture in tempdir ``td``.

    The prompt body is hashed (SHA-256) and the digest written to a
    ``prompt-manifest.json`` file under ``td/manifest.json``. Pass
    ``inject_sha`` to deliberately produce a manifest whose entry for
    ``role`` differs from the on-disk file's hash (used by the
    ``prompt_sha_mismatch`` test). Pass ``omit_role_entry=True`` to render a
    manifest without an entry for ``role`` (used by the manifest-missing
    role-entry test).
    """
    prompt_path = os.path.join(td, "fixture-prompt-{r}.md".format(r=role))
    with open(prompt_path, "w", encoding="utf-8") as fh:
        fh.write(body)
    actual_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    manifest_path = os.path.join(td, "prompt-manifest.json")
    prompts = {}
    if not omit_role_entry:
        prompts[role] = inject_sha or actual_sha
    manifest = {
        "schema_version": "1.0",
        "rendered_at": "2026-05-08T00:00:00Z",
        "prompts": prompts,
    }
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return prompt_path, manifest_path


def _capture_marker_call(call: callable) -> tuple[type | None, str]:
    """Run ``call()`` and return ``(exception_type_or_None, stderr_text)``."""
    buf = io.StringIO()
    captured_exc: type | None = None
    with contextlib.redirect_stderr(buf):
        try:
            call()
        except BaseException as exc:
            captured_exc = type(exc)
    return captured_exc, buf.getvalue()


class TestRoleValueError(unittest.TestCase):
    def test_unknown_role(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            with self.assertRaises(RoleValueError):
                check_runtime(role="unknown-role", config_path=cfg, operational_db_path=db, env={})

    def test_orchestrator_role_valid_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            check_runtime(
                role="orchestrator",
                config_path=cfg,
                operational_db_path=db,
                env={"TELEGRAM_BOT_TOKEN": "abcdef123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
                prompt_manifest_path="",
            )


class TestSkillsMismatch(unittest.TestCase):
    def test_orchestrator_missing_telegram_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            with self.assertRaises(SkillsMismatchError):
                check_runtime(role="orchestrator", config_path=cfg, operational_db_path=db, env={"TELEGRAM_BOT_TOKEN": "real-token"})

    def test_executor_missing_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            with self.assertRaises(SkillsMismatchError):
                check_runtime(role="executor", config_path=cfg, operational_db_path=db, env={})

    def test_correct_skills_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={}, prompt_manifest_path="")


class TestOperationalDbPath(unittest.TestCase):
    def test_no_symlink_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hermes_home = os.path.join(td, ".hermes")
            os.makedirs(hermes_home)
            cfg = os.path.join(hermes_home, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            open(os.path.join(hermes_home, "operational.db"), "w").close()
            with self.assertRaises(OperationalDbPathError):
                check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={"HERMES_HOME": hermes_home})

    @unittest.skipUnless(_symlink_works(), "symlinks require Unix or Developer Mode on Windows")
    def test_state_db_collision_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hermes_home = os.path.join(td, ".hermes")
            os.makedirs(hermes_home)
            cfg = os.path.join(hermes_home, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            os.symlink(db, os.path.join(hermes_home, "operational.db"))
            open(os.path.join(hermes_home, "state.db"), "w").close()
            with self.assertRaises(OperationalDbPathError):
                check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={"HERMES_HOME": hermes_home})

    @unittest.skipUnless(_symlink_works(), "symlinks require Unix or Developer Mode on Windows")
    def test_correct_symlink_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hermes_home = os.path.join(td, ".hermes")
            os.makedirs(hermes_home)
            cfg = os.path.join(hermes_home, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            os.symlink(db, os.path.join(hermes_home, "operational.db"))
            check_runtime(
                role="planner",
                config_path=cfg,
                operational_db_path=db,
                env={"HERMES_HOME": hermes_home},
                prompt_manifest_path="",
            )

    @unittest.skipUnless(_symlink_works(), "symlinks require Unix or Developer Mode on Windows")
    def test_symlink_wrong_target_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hermes_home = os.path.join(td, ".hermes")
            os.makedirs(hermes_home)
            cfg = os.path.join(hermes_home, "config.yaml")
            wrong_target = os.path.join(td, "wrong.db")
            open(wrong_target, "w").close()
            os.symlink(wrong_target, os.path.join(hermes_home, "operational.db"))
            _write_minimal_config(cfg, ["cronjob", "memory"])
            with self.assertRaises(OperationalDbPathError):
                check_runtime(role="planner", config_path=cfg, operational_db_path="/srv/devassist/state/operational.db", env={"HERMES_HOME": hermes_home})


class TestSchemaVersion(unittest.TestCase):
    def test_schema_version_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db, "2")
            with self.assertRaises(SchemaVersionMismatchError):
                check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={})

    def test_schema_version_correct_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db, "3")
            check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={}, prompt_manifest_path="")

    def test_missing_schema_version_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
            conn.commit()
            conn.close()
            with self.assertRaises(SchemaVersionMismatchError):
                check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={})


class TestTelegramBotToken(unittest.TestCase):
    def test_orchestrator_empty_token_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            with self.assertRaises(TelegramTokenMissingError):
                check_runtime(role="orchestrator", config_path=cfg, operational_db_path=db, env={"TELEGRAM_BOT_TOKEN": ""})

    def test_orchestrator_placeholder_token_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            with self.assertRaises(TelegramTokenMissingError):
                check_runtime(role="orchestrator", config_path=cfg, operational_db_path=db, env={"TELEGRAM_BOT_TOKEN": "test-token-placeholder"})

    def test_orchestrator_real_token_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            check_runtime(
                role="orchestrator",
                config_path=cfg,
                operational_db_path=db,
                env={"TELEGRAM_BOT_TOKEN": "abcdef123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
                prompt_manifest_path="",
            )


class TestTelegramGatewayNonOrchestrator(unittest.TestCase):
    def test_planner_loads_telegram_gateway_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            with self.assertRaises(TelegramGatewayLoadedError):
                check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={})

    def test_architect_loads_telegram_gateway_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            with self.assertRaises(TelegramGatewayLoadedError):
                check_runtime(role="architect", config_path=cfg, operational_db_path=db, env={})

    def test_executor_loads_telegram_gateway_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            with self.assertRaises(TelegramGatewayLoadedError):
                check_runtime(role="executor", config_path=cfg, operational_db_path=db, env={})

    def test_reviewer_loads_telegram_gateway_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            with self.assertRaises(TelegramGatewayLoadedError):
                check_runtime(role="reviewer", config_path=cfg, operational_db_path=db, env={})


class TestAllRolesPass(unittest.TestCase):
    @unittest.skipUnless(_symlink_works(), "symlinks require Unix or Developer Mode on Windows")
    def test_all_five_roles_pass_in_fixture_mode(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            with self.subTest(role=role):
                with tempfile.TemporaryDirectory() as td:
                    hermes_home = os.path.join(td, ".hermes")
                    os.makedirs(hermes_home)
                    cfg = os.path.join(hermes_home, "config.yaml")
                    db = os.path.join(td, "operational.db")
                    if role == "orchestrator":
                        skills = ["telegram-gateway", "cronjob", "memory"]
                        env = {"HERMES_HOME": hermes_home, "TELEGRAM_BOT_TOKEN": "123456789:AAABBCCCDDEEFFGGHHIJKKLLMMNNOOPPQQRRSS"}
                    elif role in ("executor", "reviewer"):
                        skills = ["terminal", "cronjob", "memory"]
                        env = {"HERMES_HOME": hermes_home}
                    else:
                        skills = ["cronjob", "memory"]
                        env = {"HERMES_HOME": hermes_home}
                    prompt_path, manifest_path = _setup_prompt_fixture(td, role)
                    config_lines = ["agent:", "  model: accounts/fireworks/models/glm-5p1", "", "skills:", "  built_in:"]
                    for s in skills:
                        config_lines.append("  - " + s)
                    config_lines.extend([
                        "  external_dirs:",
                        "    - /srv/devassist/shared-skills/",
                        "",
                        "plugins:",
                        "  enabled:",
                        "    - dev-assist-escalation-policy",
                        "    - dev-assist-work-queue",
                        "  disabled:",
                        "    - skill_manage",
                        "    - delegate_task",
                        "",
                        "approvals:",
                        "  mode: manual",
                        "",
                        "gateway:",
                        "  enabled: false",
                        "",
                        "system_prompt:",
                        "  path: " + prompt_path,
                    ])
                    with open(cfg, "w", encoding="utf-8") as fh:
                        fh.write("\n".join(config_lines) + "\n")
                    _create_operational_db(db)
                    os.symlink(db, os.path.join(hermes_home, "operational.db"))
                    check_runtime(
                        role=role,
                        config_path=cfg,
                        operational_db_path=db,
                        env=env,
                        prompt_manifest_path=manifest_path,
                    )


class TestRuntimeCheckInvariantsEnum(unittest.TestCase):
    """AC-5: 11-name invariant enum is the public stable surface."""

    EXPECTED_NAMES = frozenset(
        {
            "role_env_unset",
            "role_env_invalid",
            "loaded_skills_mismatch",
            "operational_db_path_mismatch",
            "schema_version_mismatch",
            "orchestrator_telegram_token_missing",
            "non_orchestrator_telegram_skill_loaded",
            "delegate_task_callable",
            "skill_manage_callable",
            "prompt_manifest_missing",
            "prompt_sha_mismatch",
        }
    )

    def test_invariants_set_equals_expected_eleven(self) -> None:
        self.assertEqual(RUNTIME_CHECK_INVARIANTS, self.EXPECTED_NAMES)
        self.assertEqual(len(RUNTIME_CHECK_INVARIANTS), 11)

    def test_individual_constants_match_set(self) -> None:
        constants = {
            INVARIANT_ROLE_ENV_UNSET,
            INVARIANT_ROLE_ENV_INVALID,
            INVARIANT_LOADED_SKILLS_MISMATCH,
            INVARIANT_OPERATIONAL_DB_PATH_MISMATCH,
            INVARIANT_SCHEMA_VERSION_MISMATCH,
            INVARIANT_ORCHESTRATOR_TELEGRAM_TOKEN_MISSING,
            INVARIANT_NON_ORCHESTRATOR_TELEGRAM_SKILL_LOADED,
            INVARIANT_DELEGATE_TASK_CALLABLE,
            INVARIANT_SKILL_MANAGE_CALLABLE,
            INVARIANT_PROMPT_MANIFEST_MISSING,
            INVARIANT_PROMPT_SHA_MISMATCH,
        }
        self.assertEqual(constants, RUNTIME_CHECK_INVARIANTS)

    def test_prompt_file_by_role_keys_match_allowed_roles(self) -> None:
        self.assertEqual(
            set(PROMPT_FILE_BY_ROLE.keys()),
            {"orchestrator", "planner", "architect", "executor", "reviewer"},
        )
        self.assertEqual(
            PROMPT_FILE_BY_ROLE["orchestrator"],
            "docs/prompts/runtime-hermes-orchestrator.md",
        )

    def test_abort_exit_code_is_seventy_eight(self) -> None:
        # AC-2: EX_CONFIG=78 per sysexits.h; systemd unit's
        # RestartPreventExitStatus= must list this value.
        self.assertEqual(RUNTIME_CHECK_ABORT_EXIT_CODE, 78)


class TestMarkerEmits(unittest.TestCase):
    """AC-5: each invariant emits the structured RUNTIME_CHECK_FAILED marker
    on stderr immediately before raising the existing exception type. The
    grammar is RUNTIME_CHECK_FAILED:<role>:<invariant_name> (one line, LF).
    """

    def _assert_marker(self, stderr: str, role: str, invariant: str) -> None:
        expected = "RUNTIME_CHECK_FAILED:{r}:{n}".format(r=role, n=invariant)
        self.assertIn(expected, stderr, msg="missing marker in stderr: {s!r}".format(s=stderr))

    def test_role_env_unset_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(role="", config_path=cfg, operational_db_path=db, env={}, prompt_manifest_path="")
            )
        self.assertIs(exc, RoleValueError)
        # role token is empty for unset/invalid since the role is not in the
        # allowed set; grammar is "RUNTIME_CHECK_FAILED::<invariant_name>".
        self._assert_marker(stderr, "", INVARIANT_ROLE_ENV_UNSET)

    def test_role_env_invalid_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="not-a-role",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path="",
                )
            )
        self.assertIs(exc, RoleValueError)
        self._assert_marker(stderr, "", INVARIANT_ROLE_ENV_INVALID)

    def test_loaded_skills_mismatch_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["memory"])  # missing 'cronjob'
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path="",
                )
            )
        self.assertIs(exc, SkillsMismatchError)
        self._assert_marker(stderr, "planner", INVARIANT_LOADED_SKILLS_MISMATCH)

    def test_non_orchestrator_telegram_skill_loaded_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="architect",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path="",
                )
            )
        self.assertIs(exc, TelegramGatewayLoadedError)
        self._assert_marker(stderr, "architect", INVARIANT_NON_ORCHESTRATOR_TELEGRAM_SKILL_LOADED)

    @unittest.skipUnless(_symlink_works(), "symlinks require Unix or Developer Mode on Windows")
    def test_operational_db_path_mismatch_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hermes_home = os.path.join(td, ".hermes")
            os.makedirs(hermes_home)
            cfg = os.path.join(hermes_home, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            open(os.path.join(hermes_home, "operational.db"), "w").close()
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={"HERMES_HOME": hermes_home},
                    prompt_manifest_path="",
                )
            )
        self.assertIs(exc, OperationalDbPathError)
        self._assert_marker(stderr, "planner", INVARIANT_OPERATIONAL_DB_PATH_MISMATCH)

    def test_schema_version_mismatch_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db, schema_version="2")
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path="",
                )
            )
        self.assertIs(exc, SchemaVersionMismatchError)
        self._assert_marker(stderr, "planner", INVARIANT_SCHEMA_VERSION_MISMATCH)

    def test_orchestrator_telegram_token_missing_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["telegram-gateway", "cronjob", "memory"], include_external_dirs=True)
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="orchestrator",
                    config_path=cfg,
                    operational_db_path=db,
                    env={"TELEGRAM_BOT_TOKEN": ""},
                    prompt_manifest_path="",
                )
            )
        self.assertIs(exc, TelegramTokenMissingError)
        self._assert_marker(stderr, "orchestrator", INVARIANT_ORCHESTRATOR_TELEGRAM_TOKEN_MISSING)


class TestDelegateTaskCallable(unittest.TestCase):
    """AC-3 (i): delegate_task is callable -> raise + emit marker."""

    def test_callable_raises_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path="",
                    delegate_task_caller=lambda _cfg: "callable",
                )
            )
        self.assertIs(exc, DelegateTaskCallableError)
        self.assertIn(
            "RUNTIME_CHECK_FAILED:planner:" + INVARIANT_DELEGATE_TASK_CALLABLE,
            stderr,
        )

    def test_gated_passes_via_default_caller(self) -> None:
        # The default caller forwards to ``_attempt_hermes_skill_round_trip``
        # which calls ``importlib.import_module("hermes.skills.delegate_task")``.
        # The upstream Hermes package is not installed in the offline test
        # environment, so the import raises ImportError and the helper
        # returns "gated". The test confirms the production round-trip
        # default path is wired up and reaches the gating branch on a
        # vanilla offline interpreter.
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            check_runtime(
                role="planner",
                config_path=cfg,
                operational_db_path=db,
                env={},
                prompt_manifest_path="",
            )


class TestSkillManageCallable(unittest.TestCase):
    """AC-3 (ii): skill_manage is callable -> raise + emit marker."""

    def test_callable_raises_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="architect",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path="",
                    skill_manage_caller=lambda _cfg: "callable",
                )
            )
        self.assertIs(exc, SkillManageCallableError)
        self.assertIn(
            "RUNTIME_CHECK_FAILED:architect:" + INVARIANT_SKILL_MANAGE_CALLABLE,
            stderr,
        )

    def test_gated_passes_via_default_caller(self) -> None:
        # Same shape as the delegate_task counterpart: in the offline test
        # environment ``import hermes.skills.skill_manage`` raises
        # ImportError, so ``_attempt_hermes_skill_round_trip`` returns
        # "gated" and the invariant passes.
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            check_runtime(
                role="architect",
                config_path=cfg,
                operational_db_path=db,
                env={},
                prompt_manifest_path="",
            )


def _make_named_function(
    name: str, params: tuple[str, ...]
) -> "object":
    """Build a fake top-level function with given name and positional params.

    Used to mirror the upstream ``hermes-agent`` v2026.4.30 signatures of
    ``tools.delegate_tool.delegate_task`` and
    ``tools.skill_manager_tool.skill_manage`` for the AC-4 (d)
    ``inspect.signature`` probe-shape verification. The fake never accepts
    ``config_path=`` -- per TKT-033 v0.3.0 § 8 Amendment notes recon at
    ``tools/delegate_tool.py:1812`` and
    ``tools/skill_manager_tool.py:692-708``, neither upstream signature
    accepts that keyword.
    """
    src = "def {n}({p}) -> str:\n    return ''\n".format(
        n=name, p=", ".join(params)
    )
    namespace: dict[str, object] = {}
    exec(src, namespace)  # noqa: S102 -- fixture-only synthetic function
    return namespace[name]


class TestHermesFilterAssertionDefault(unittest.TestCase):
    """AC-3 (i)/(ii) + AC-4 (d): ``_attempt_hermes_filter_assertion`` round-trips
    Hermes' definitions-time filter rather than invoking the upstream handler.

    The TKT-033 v0.3.0 amendment realigned the AC-3 (i)/(ii) round-trip
    semantics with the actual ``hermes-agent`` v2026.4.30 gating model
    (commit ``73bf3ab1b22314ed9dfecbb59242c03742fe72af``): tools are gated
    at definitions assembly time via
    ``model_tools.get_tool_definitions(disabled_toolsets=...)``, NOT via a
    handler-side gating exception. The iter-2 broad-catch helper
    ``_attempt_hermes_skill_round_trip`` (with its ``except BaseException``
    fallback) is replaced by this filter-assertion helper which performs
    a positive membership check on the assembled definition list.

    Tests stub ``tools.registry``, ``tools.delegate_tool``,
    ``tools.skill_manager_tool``, and ``model_tools`` via ``sys.modules``
    injection so the helper's ``import`` statements succeed deterministically
    without requiring the upstream ``hermes-agent`` package to be installed
    in the offline test environment. Synthetic ``config.yaml`` fixtures
    exercise the YAML-parsing side of the round-trip.

    AC-4 (d) probe-shape verification uses ``inspect.signature`` to assert
    that the upstream-mirrored stubs do NOT accept ``config_path=`` --
    documenting that any helper which passed ``config_path=`` to the
    upstream callable (as iter-2 did to its synthetic invoke) would have
    raised ``TypeError`` at the upstream call boundary, NOT a gating
    exception, which the iter-2 ``except BaseException`` would have
    silently swallowed as ``"gated"`` (Reviewer Finding 2 false-positive
    that escalated to v0.3.0 spec amendment).
    """

    UPSTREAM_KEYS = (
        "tools",
        "tools.registry",
        "tools.delegate_tool",
        "tools.skill_manager_tool",
        "model_tools",
    )

    def setUp(self) -> None:
        # Save current sys.modules state for the upstream module names so
        # tearDown can restore the offline-VM baseline (where every key is
        # absent). Each setUp records what was there; each tearDown
        # restores or pops.
        self._added_module_keys: list[str] = []
        self._captured_disabled_toolsets: list[list[str]] = []
        self._saved_modules: dict[str, types.ModuleType | None] = {}
        for key in self.UPSTREAM_KEYS:
            self._saved_modules[key] = sys.modules.get(key)
            # Pre-condition for ImportError branch: every upstream key
            # MUST be absent at setUp; if not, a prior test leaked.
            if key in sys.modules:
                sys.modules.pop(key, None)

    def tearDown(self) -> None:
        for key in self.UPSTREAM_KEYS:
            sys.modules.pop(key, None)
        for key, value in self._saved_modules.items():
            if value is not None:
                sys.modules[key] = value
        for key in self._added_module_keys:
            sys.modules.pop(key, None)

    def _inject_fake_upstream(
        self,
        *,
        definitions_by_disabled: dict[
            tuple[str, ...], list[dict[str, object]]
        ]
        | None = None,
        delegate_task_signature: tuple[str, ...] = (
            "goal",
            "context",
            "toolsets",
        ),
        skill_manage_signature: tuple[str, ...] = ("action", "name"),
    ) -> None:
        """Inject fake upstream modules into ``sys.modules``.

        ``definitions_by_disabled`` keys are tuples of the disabled
        toolsets passed to ``get_tool_definitions`` (sorted); values are
        the synthetic OpenAI-shape definition lists to return for that
        key. If a call's disabled-toolsets key is not in the mapping,
        the stub returns ``[]``.

        The ``delegate_task`` / ``skill_manage`` signatures intentionally
        omit ``config_path`` to mirror the upstream v2026.4.30 shape; the
        ``test_inspect_signature_rejects_config_path_kwarg`` case asserts
        this directly.
        """
        # Namespace package "tools" + child modules. We also bind each
        # submodule as an attribute of the parent stub so dotted-attribute
        # access (``tools.delegate_tool``) resolves after ``import
        # tools.delegate_tool``: when sys.modules is pre-populated by hand
        # the import machinery does not always set the attribute on the
        # parent automatically.
        if "tools" not in sys.modules:
            pkg = types.ModuleType("tools")
            pkg.__path__ = []  # mark as namespace package
            sys.modules["tools"] = pkg
            self._added_module_keys.append("tools")
        tools_pkg = sys.modules["tools"]
        # tools.registry stub (the helper just imports it for side-effect).
        registry_mod = types.ModuleType("tools.registry")
        sys.modules["tools.registry"] = registry_mod
        tools_pkg.registry = registry_mod
        self._added_module_keys.append("tools.registry")
        # tools.delegate_tool stub with delegate_task callable.
        delegate_mod = types.ModuleType("tools.delegate_tool")
        delegate_mod.delegate_task = _make_named_function(
            "delegate_task", delegate_task_signature
        )
        sys.modules["tools.delegate_tool"] = delegate_mod
        tools_pkg.delegate_tool = delegate_mod
        self._added_module_keys.append("tools.delegate_tool")
        # tools.skill_manager_tool stub with skill_manage callable.
        skill_mod = types.ModuleType("tools.skill_manager_tool")
        skill_mod.skill_manage = _make_named_function(
            "skill_manage", skill_manage_signature
        )
        sys.modules["tools.skill_manager_tool"] = skill_mod
        tools_pkg.skill_manager_tool = skill_mod
        self._added_module_keys.append("tools.skill_manager_tool")
        # model_tools stub with a get_tool_definitions function that
        # records its disabled_toolsets argument and returns the configured
        # fixture (or [] for unknown keys).
        model_mod = types.ModuleType("model_tools")
        captured = self._captured_disabled_toolsets
        defs_by_key = definitions_by_disabled or {}

        def get_tool_definitions(
            *,
            disabled_toolsets: list[str] | None = None,
            quiet_mode: bool = False,
            enabled_toolsets: list[str] | None = None,
            **_extra: object,
        ) -> list[dict[str, object]]:
            captured.append(list(disabled_toolsets or []))
            key = tuple(sorted(disabled_toolsets or []))
            return list(defs_by_key.get(key, []))

        model_mod.get_tool_definitions = get_tool_definitions
        sys.modules["model_tools"] = model_mod
        self._added_module_keys.append("model_tools")

    def _write_config_with_disabled_toolsets(
        self, path: str, disabled_toolsets: list[str]
    ) -> None:
        lines = [
            "agent:",
            "  model: accounts/fireworks/models/glm-5p1",
        ]
        if disabled_toolsets:
            lines.append("  disabled_toolsets:")
            for toolset in disabled_toolsets:
                lines.append("  - " + toolset)
        lines.extend(["", "skills:", "  built_in:", "  - cronjob", "  - memory"])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def test_import_error_returns_gated(self) -> None:
        # No upstream stubs injected -- ``import tools.registry`` raises
        # ModuleNotFoundError (an ImportError subclass), so the helper
        # returns "gated" via the only allowed catch (the AC-3 pass branch
        # on the offline Devin VM and on minimal-dependency CI images).
        for key in self.UPSTREAM_KEYS:
            self.assertNotIn(
                key,
                sys.modules,
                "{k} unexpectedly in sys.modules at setUp".format(k=key),
            )
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            self._write_config_with_disabled_toolsets(cfg, ["delegation"])
            self.assertEqual(
                _attempt_hermes_filter_assertion(cfg, "delegate_task"),
                "gated",
            )

    def test_filter_excludes_delegate_task_returns_gated(self) -> None:
        # Filter correctly excludes delegate_task when delegation toolset
        # is disabled -- assembled definitions list does NOT contain
        # delegate_task; helper returns "gated" (AC-3 (i) pass branch).
        self._inject_fake_upstream(
            definitions_by_disabled={
                ("delegation",): [
                    {"type": "function", "function": {"name": "other_tool"}},
                ],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            self._write_config_with_disabled_toolsets(cfg, ["delegation"])
            self.assertEqual(
                _attempt_hermes_filter_assertion(cfg, "delegate_task"),
                "gated",
            )
        self.assertEqual(self._captured_disabled_toolsets, [["delegation"]])

    def test_filter_includes_delegate_task_returns_callable(self) -> None:
        # Filter FAILS to exclude delegate_task despite delegation being in
        # disabled_toolsets -- assembled definitions list contains
        # delegate_task; helper returns "callable" (AC-3 (i) live failure
        # mode that surfaces as DelegateTaskCallableError at the
        # check_runtime layer for non-orchestrator roles).
        self._inject_fake_upstream(
            definitions_by_disabled={
                ("delegation",): [
                    {"type": "function", "function": {"name": "delegate_task"}},
                ],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            self._write_config_with_disabled_toolsets(cfg, ["delegation"])
            self.assertEqual(
                _attempt_hermes_filter_assertion(cfg, "delegate_task"),
                "callable",
            )

    def test_filter_excludes_skill_manage_returns_gated(self) -> None:
        # Same shape as the delegate_task gated case but for skill_manage
        # under the skills toolset (AC-3 (ii) pass branch). All five
        # roles disable the skills toolset per HERMES-SKILL-ALLOWLIST
        # v0.1.2 § 4, so a correctly-filtered runtime must return
        # "gated" for skill_manage on every role.
        self._inject_fake_upstream(
            definitions_by_disabled={
                ("skills",): [
                    {"type": "function", "function": {"name": "delegate_task"}},
                ],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            self._write_config_with_disabled_toolsets(cfg, ["skills"])
            self.assertEqual(
                _attempt_hermes_filter_assertion(cfg, "skill_manage"),
                "gated",
            )

    def test_filter_includes_skill_manage_returns_callable(self) -> None:
        # AC-3 (ii) live failure mode -- skill_manage assembled into the
        # definitions list despite skills toolset being disabled.
        self._inject_fake_upstream(
            definitions_by_disabled={
                ("skills",): [
                    {"type": "function", "function": {"name": "skill_manage"}},
                ],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            self._write_config_with_disabled_toolsets(cfg, ["skills"])
            self.assertEqual(
                _attempt_hermes_filter_assertion(cfg, "skill_manage"),
                "callable",
            )

    def test_no_disabled_toolsets_passes_empty_list(self) -> None:
        # When agent.disabled_toolsets is absent (e.g., orchestrator role
        # which uses delegation), the helper passes an empty list to
        # get_tool_definitions; the filter does NOT exclude delegate_task,
        # and the helper returns "callable". The orchestrator-role
        # caller-injection at the check_runtime layer guards against
        # raising on this branch -- AC-3 (i) only enforces the invariant
        # for non-orchestrator roles whose delegation toolset MUST be
        # disabled.
        self._inject_fake_upstream(
            definitions_by_disabled={
                (): [
                    {"type": "function", "function": {"name": "delegate_task"}},
                    {"type": "function", "function": {"name": "skill_manage"}},
                ],
            },
        )
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            self._write_config_with_disabled_toolsets(cfg, [])
            self.assertEqual(
                _attempt_hermes_filter_assertion(cfg, "delegate_task"),
                "callable",
            )
        self.assertEqual(self._captured_disabled_toolsets, [[]])

    def test_inspect_signature_rejects_config_path_kwarg(self) -> None:
        # AC-4 (d) probe-shape verification. Per TKT-033 v0.3.0 § 8
        # Amendment notes recon at tools/delegate_tool.py:1812 and
        # tools/skill_manager_tool.py:692-708, neither upstream signature
        # accepts config_path=. The fake-upstream stubs mirror that shape;
        # this test asserts it via inspect.signature.
        #
        # The runtime-check helper does NOT pass config_path= to either
        # upstream callable (it uses the filter-based round-trip rather
        # than direct invoke). This test documents that the iter-2
        # broad-catch helper, which DID pass config_path=, would have
        # raised TypeError at the upstream call boundary -- which the
        # iter-2 ``except BaseException`` would have silently swallowed
        # as "gated", not catching a gating exception (Reviewer Finding 2).
        self._inject_fake_upstream()
        import tools.delegate_tool  # type: ignore[import-not-found]
        import tools.skill_manager_tool  # type: ignore[import-not-found]

        delegate_params = inspect.signature(
            tools.delegate_tool.delegate_task
        ).parameters
        skill_params = inspect.signature(
            tools.skill_manager_tool.skill_manage
        ).parameters
        self.assertNotIn("config_path", delegate_params)
        self.assertNotIn("config_path", skill_params)
        # Confirm the stubs DO carry the documented v2026.4.30 parameter
        # surface (positive shape assertion, not just the negative one):
        self.assertIn("goal", delegate_params)
        self.assertIn("toolsets", delegate_params)
        self.assertIn("action", skill_params)
        self.assertIn("name", skill_params)


class TestCallerInjectionFallback(unittest.TestCase):
    """Finding 2 regression: ``check_runtime`` selects the injected
    ``delegate_task_caller`` / ``skill_manage_caller`` via an explicit
    ``is not None`` guard rather than truthiness. A falsy-but-callable
    sentinel (e.g., a class instance whose ``__bool__`` returns False)
    must be invoked, not silently fall through to the default production
    caller.
    """

    def _make_falsy_caller(self, captured: list[str]) -> object:
        class FalsyCaller:
            def __bool__(self) -> bool:
                return False

            def __call__(self, config_path: str) -> str:
                captured.append(config_path)
                return "gated"

        instance = FalsyCaller()
        # Guard the test's own preconditions: instance is falsy under
        # bool() and callable under callable().
        assert bool(instance) is False
        assert callable(instance)
        return instance

    def test_falsy_callable_delegate_caller_is_invoked(self) -> None:
        captured: list[str] = []
        caller = self._make_falsy_caller(captured)
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            check_runtime(
                role="planner",
                config_path=cfg,
                operational_db_path=db,
                env={},
                prompt_manifest_path="",
                delegate_task_caller=caller,
            )
        self.assertEqual(captured, [cfg])

    def test_falsy_callable_skill_manage_caller_is_invoked(self) -> None:
        captured: list[str] = []
        caller = self._make_falsy_caller(captured)
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            check_runtime(
                role="architect",
                config_path=cfg,
                operational_db_path=db,
                env={},
                prompt_manifest_path="",
                skill_manage_caller=caller,
            )
        self.assertEqual(captured, [cfg])


class TestPromptManifest(unittest.TestCase):
    """AC-3 (iii): prompt_manifest_missing + prompt_sha_mismatch hard-fail."""

    def test_manifest_missing_raises_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            absent_manifest = os.path.join(td, "no-such-manifest.json")
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path=absent_manifest,
                )
            )
        self.assertIs(exc, PromptManifestMissingError)
        self.assertIn(
            "RUNTIME_CHECK_FAILED:planner:" + INVARIANT_PROMPT_MANIFEST_MISSING,
            stderr,
        )

    def test_manifest_role_entry_missing_raises_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            _write_minimal_config(cfg, ["cronjob", "memory"])
            _create_operational_db(db)
            _, manifest_path = _setup_prompt_fixture(td, "planner", omit_role_entry=True)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path=manifest_path,
                )
            )
        self.assertIs(exc, PromptManifestMissingError)
        self.assertIn(
            "RUNTIME_CHECK_FAILED:planner:" + INVARIANT_PROMPT_MANIFEST_MISSING,
            stderr,
        )

    def test_sha_mismatch_raises_with_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prompt_path, manifest_path = _setup_prompt_fixture(
                td,
                "planner",
                inject_sha="0" * 64,
            )
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write(
                    "agent:\n  model: x\n\nskills:\n  built_in:\n  - cronjob\n  - memory\n\n"
                    "plugins:\n  disabled:\n    - skill_manage\n    - delegate_task\n\n"
                    "system_prompt:\n  path: {p}\n".format(p=prompt_path)
                )
            _create_operational_db(db)
            exc, stderr = _capture_marker_call(
                lambda: check_runtime(
                    role="planner",
                    config_path=cfg,
                    operational_db_path=db,
                    env={},
                    prompt_manifest_path=manifest_path,
                )
            )
        self.assertIs(exc, PromptShaMismatchError)
        self.assertIn(
            "RUNTIME_CHECK_FAILED:planner:" + INVARIANT_PROMPT_SHA_MISMATCH,
            stderr,
        )

    def test_matching_sha_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prompt_path, manifest_path = _setup_prompt_fixture(td, "planner")
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write(
                    "agent:\n  model: x\n\nskills:\n  built_in:\n  - cronjob\n  - memory\n\n"
                    "plugins:\n  disabled:\n    - skill_manage\n    - delegate_task\n\n"
                    "system_prompt:\n  path: {p}\n".format(p=prompt_path)
                )
            _create_operational_db(db)
            check_runtime(
                role="planner",
                config_path=cfg,
                operational_db_path=db,
                env={},
                prompt_manifest_path=manifest_path,
            )


class TestRuntimeCheckCli(unittest.TestCase):
    """AC-2: ``python3 -m developer_assistant.runtime_check`` CLI entrypoint
    returns RUNTIME_CHECK_ABORT_EXIT_CODE (78, EX_CONFIG) on any
    RuntimeCheckError; 0 on full pass. The systemd unit's
    RestartPreventExitStatus=78 matches this code so an invariant abort
    surfaces as ``failed`` and never auto-restarts.
    """

    SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")

    def _run_cli(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        full_env = {**env}
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        full_env["PYTHONPATH"] = (
            self.SRC_DIR + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        )
        if "PATH" in os.environ:
            full_env.setdefault("PATH", os.environ["PATH"])
        return subprocess.run(
            [sys.executable, "-m", "developer_assistant.runtime_check"],
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def test_cli_unset_role_returns_exit_code_seventy_eight(self) -> None:
        # No HERMES_DEVASSIST_ROLE -> role_env_unset -> raise RuntimeCheckError
        # -> exit 78. Does not require any fixture.
        result = self._run_cli({})
        self.assertEqual(result.returncode, RUNTIME_CHECK_ABORT_EXIT_CODE)
        self.assertIn(
            "RUNTIME_CHECK_FAILED::" + INVARIANT_ROLE_ENV_UNSET,
            result.stderr,
        )

    def test_cli_invalid_role_returns_exit_code_seventy_eight(self) -> None:
        result = self._run_cli({"HERMES_DEVASSIST_ROLE": "not-a-role"})
        self.assertEqual(result.returncode, RUNTIME_CHECK_ABORT_EXIT_CODE)
        self.assertIn(
            "RUNTIME_CHECK_FAILED::" + INVARIANT_ROLE_ENV_INVALID,
            result.stderr,
        )

    def test_cli_full_pass_returns_zero(self) -> None:
        # Exercises the same RuntimeCheckError-trapping branch of _main_cli
        # via an inline shim that forwards explicit paths; the production
        # _main_cli reads HERMES_HOME-derived defaults that point at
        # /srv/devassist/state/..., which is not writable in the offline
        # CI environment. The fixture omits HERMES_HOME so the
        # operational.db symlink invariant (which insists on the production
        # /srv/devassist/state/ target) is bypassed -- baseline tests under
        # TestOperationalDbPath cover that invariant directly.
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.yaml")
            db = os.path.join(td, "operational.db")
            prompt_path, manifest_path = _setup_prompt_fixture(td, "planner")
            config_lines = [
                "agent:",
                "  model: accounts/fireworks/models/glm-5p1",
                "",
                "skills:",
                "  built_in:",
                "  - cronjob",
                "  - memory",
                "  external_dirs:",
                "    - /srv/devassist/shared-skills/",
                "",
                "plugins:",
                "  disabled:",
                "    - skill_manage",
                "    - delegate_task",
                "",
                "system_prompt:",
                "  path: " + prompt_path,
            ]
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("\n".join(config_lines) + "\n")
            _create_operational_db(db)

            shim = (
                "import os\n"
                "from developer_assistant.runtime_check import check_runtime, "
                "RuntimeCheckError, RUNTIME_CHECK_ABORT_EXIT_CODE\n"
                "try:\n"
                "    check_runtime(\n"
                "        role=os.environ['HERMES_DEVASSIST_ROLE'],\n"
                "        config_path=os.environ['DEVASSIST_CONFIG_PATH'],\n"
                "        operational_db_path=os.environ['DEVASSIST_DB_PATH'],\n"
                "        env={k: v for k, v in os.environ.items() if k != 'HERMES_HOME'},\n"
                "        prompt_manifest_path=os.environ['DEVASSIST_MANIFEST_PATH'],\n"
                "    )\n"
                "except RuntimeCheckError:\n"
                "    raise SystemExit(RUNTIME_CHECK_ABORT_EXIT_CODE)\n"
                "raise SystemExit(0)\n"
            )
            env = {
                "HERMES_DEVASSIST_ROLE": "planner",
                "DEVASSIST_CONFIG_PATH": cfg,
                "DEVASSIST_DB_PATH": db,
                "DEVASSIST_MANIFEST_PATH": manifest_path,
                "PYTHONPATH": self.SRC_DIR,
                "PATH": os.environ.get("PATH", ""),
            }
            result = subprocess.run(
                [sys.executable, "-c", shim],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
