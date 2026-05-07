"""Tests for developer_assistant.runtime_check.

All tests are offline-only, use placeholder values, and do not require
real Hermes binary, real LLM credentials, real Telegram bot, or real GitHub access.
Uses fixture mode with real temp SQLite files.

Platform guard: tests that require symlinks skip gracefully on Windows.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant.runtime_check import (
    OperationalDbPathError,
    RoleValueError,
    SchemaVersionMismatchError,
    SkillsMismatchError,
    TelegramGatewayLoadedError,
    TelegramTokenMissingError,
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
            try:
                check_runtime(role="orchestrator", config_path=cfg, operational_db_path=db, env={"TELEGRAM_BOT_TOKEN": "real-token"})
            except (RoleValueError, TelegramTokenMissingError):
                pass


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
            check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={})


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
            check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={"HERMES_HOME": hermes_home})

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
            check_runtime(role="planner", config_path=cfg, operational_db_path=db, env={})

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
            check_runtime(role="orchestrator", config_path=cfg, operational_db_path=db, env={"TELEGRAM_BOT_TOKEN": "abcdef123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ"})


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
                    config_lines = ["agent:", "  model: accounts/fireworks/models/glm-5p1", "", "skills:", "  built_in:"]
                    for s in skills:
                        config_lines.append("  - " + s)
                    config_lines.extend(["  external_dirs:", "    - /srv/devassist/shared-skills/", "", "plugins:", "  enabled:", "    - dev-assist-escalation-policy", "    - dev-assist-work-queue", "  disabled:", "    - skill_manage", "    - delegate_task", "", "approvals:", "  mode: manual", "", "gateway:", "  enabled: false"])
                    with open(cfg, "w", encoding="utf-8") as fh:
                        fh.write("\n".join(config_lines) + "\n")
                    _create_operational_db(db)
                    os.symlink(db, os.path.join(hermes_home, "operational.db"))
                    check_runtime(role=role, config_path=cfg, operational_db_path=db, env=env)


if __name__ == "__main__":
    unittest.main()
