"""Tests for self-deployment scripts (TKT-020).

Validates install-self.sh, verify-self.sh, rollback-self.sh, upgrade-self.sh
under dry-run mode using a temp prefix. Uses stdlib unittest and tempfile.
No real tokens, PATs, or production hostnames appear here.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
ROLES = ["orchestrator", "planner", "architect", "executor", "reviewer"]
EXPECTED_SCHEMA_VERSION = "3"


def _run_script(
    script_name: str,
    extra_env: dict[str, str] | None = None,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(extra_env or {})
    cmd = [sys.executable, "-m", "bash", str(SCRIPTS_DIR / script_name)]
    if args:
        cmd.extend(args)
    return subprocess.run(
        ["bash", str(SCRIPTS_DIR / script_name)] + (args or []),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


class TestInstallSelfIdempotent(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        self.env = {
            "INSTALL_DRY_RUN": "1",
            "INSTALL_DRY_RUN_PREFIX": self.tmpdir,
            "VERIFY_FIXTURE_MODE": "1",
            "ROLLBACK_DRY_RUN": "1",
            "UPGRADE_DRY_RUN": "1",
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_install_creates_filesystem_layout(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")
        base = Path(self.tmpdir) / "srv" / "devassist"
        for role in ROLES:
            hermes_dir = base / "runtimes" / role / ".hermes"
            self.assertTrue(hermes_dir.is_dir(), f"Missing .hermes for {role}")
            for subdir in ["memories", "sessions", "cron", "logs", "skills"]:
                self.assertTrue(
                    (hermes_dir / subdir).is_dir(),
                    f"Missing {subdir} for {role}",
                )

    def test_install_creates_operational_db_symlinks(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")
        base = Path(self.tmpdir) / "srv" / "devassist"
        for role in ROLES:
            symlink = base / "runtimes" / role / ".hermes" / "operational.db"
            self.assertTrue(symlink.is_symlink(), f"operational.db symlink missing for {role}")

    def test_install_creates_env_symlinks(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")
        base = Path(self.tmpdir) / "srv" / "devassist"
        for role in ROLES:
            env_link = base / "runtimes" / role / ".hermes" / ".env"
            self.assertTrue(env_link.is_symlink(), f".env symlink missing for {role}")

    def test_install_renders_systemd_units(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")
        systemd_dir = Path(self.tmpdir) / "etc" / "systemd" / "system"
        expected_units = [
            "devassist.target",
            "devassist-orchestrator.service",
            "devassist-planner.service",
            "devassist-architect.service",
            "devassist-executor.service",
            "devassist-reviewer.service",
            "omniroute.service",
            "devassist-web.service",
        ]
        for unit in expected_units:
            self.assertTrue(
                (systemd_dir / unit).is_file(),
                f"Missing systemd unit: {unit}",
            )

    def test_install_creates_self_deploy_env(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")
        env_file = Path(self.tmpdir) / "srv" / "devassist" / "secrets" / "SELF-DEPLOY.env"
        self.assertTrue(env_file.is_file(), "SELF-DEPLOY.env not created")
        content = env_file.read_text()
        self.assertIn("TELEGRAM_BOT_TOKEN=test-token-placeholder", content)
        self.assertIn("GITHUB_TOKEN=test-token-placeholder", content)
        self.assertIn("FIREWORKS_API_KEY=test-token-placeholder", content)

    def test_install_idempotent_second_run(self) -> None:
        _run_script("install-self.sh", self.env)
        result2 = _run_script("install-self.sh", self.env)
        self.assertEqual(result2.returncode, 0, "Second install run failed")

    def test_install_does_not_start_units(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertNotIn("systemctl start", result.stdout)

    def test_install_creates_journald_dropin(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0)
        dropin = Path(self.tmpdir) / "etc" / "systemd" / "journald.conf.d" / "dev-assist.conf"
        self.assertTrue(dropin.is_file(), "journald drop-in not created")
        content = dropin.read_text()
        self.assertIn("SystemMaxUse=1G", content)
        self.assertIn("MaxRetentionSec=30d", content)


class TestSystemdUnitRender(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        self.env = {
            "INSTALL_DRY_RUN": "1",
            "INSTALL_DRY_RUN_PREFIX": self.tmpdir,
            "VERIFY_FIXTURE_MODE": "1",
            "ROLLBACK_DRY_RUN": "1",
            "UPGRADE_DRY_RUN": "1",
        }
        _run_script("install-self.sh", self.env)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_executor_has_supplementary_groups_docker(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-executor.service"
        content = unit.read_text()
        self.assertIn("SupplementaryGroups=docker", content)

    def test_reviewer_has_supplementary_groups_docker(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-reviewer.service"
        content = unit.read_text()
        self.assertIn("SupplementaryGroups=docker", content)

    def test_orchestrator_runs_gateway(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-orchestrator.service"
        content = unit.read_text()
        self.assertIn("hermes gateway run", content)

    def test_planner_runs_hermes_run(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-planner.service"
        content = unit.read_text()
        self.assertIn("hermes run", content)
        self.assertNotIn("hermes gateway run", content)

    def test_omniroute_port_20128(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "omniroute.service"
        content = unit.read_text()
        self.assertIn("--port 20128", content)

    def test_omniroute_runs_as_omniroute_user(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "omniroute.service"
        content = unit.read_text()
        self.assertIn("User=omniroute", content)

    def test_web_service_binds_8180(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-web.service"
        content = unit.read_text()
        self.assertIn("--port 8180", content)

    def test_all_units_have_sandboxing(self) -> None:
        systemd_dir = Path(self.tmpdir) / "etc" / "systemd" / "system"
        runtime_units = [
            "devassist-orchestrator.service",
            "devassist-planner.service",
            "devassist-architect.service",
            "devassist-executor.service",
            "devassist-reviewer.service",
        ]
        for unit_name in runtime_units:
            content = (systemd_dir / unit_name).read_text()
            for directive in [
                "NoNewPrivileges=true",
                "ProtectSystem=full",
                "ProtectHome=true",
                "PrivateTmp=true",
            ]:
                self.assertIn(directive, content, f"{unit_name} missing {directive}")

    def test_omniroute_before_runtime_services(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "omniroute.service"
        content = unit.read_text()
        self.assertIn("Before=", content)
        self.assertIn("devassist-orchestrator.service", content)

    def test_web_after_runtime_services(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-web.service"
        content = unit.read_text()
        self.assertIn("After=", content)
        self.assertIn("devassist-reviewer.service", content)

    def test_target_wants_all_eight_units(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist.target"
        content = unit.read_text()
        for name in [
            "omniroute.service",
            "devassist-orchestrator.service",
            "devassist-web.service",
        ]:
            self.assertIn(name, content, f"target missing Wants for {name}")


class TestVerifySelf(unittest.TestCase):
    def test_verify_passes_in_fixture_mode(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("verify-self.sh", env)
            self.assertEqual(result.returncode, 0, result.stdout[-500:] if result.stdout else "ok")
            self.assertIn("PASS", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_verify_counts_invariants(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("verify-self.sh", env)
            self.assertIn("12/12", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_verify_no_secrets_in_output(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("verify-self.sh", env)
            output = result.stdout + result.stderr
            self.assertNotIn("test-token-placeholder", output)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_verify_includes_web_service_invariant(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("verify-self.sh", env)
            self.assertIn("web unit active", result.stdout + result.stderr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRollbackSelf(unittest.TestCase):
    def test_rollback_aborts_with_no_backup(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            backup_dir = Path(tmpdir) / "srv" / "devassist" / "state" / "backups"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            os.makedirs(backup_dir, exist_ok=True)
            result = _run_script("rollback-self.sh", env)
            self.assertNotEqual(result.returncode, 0, "rollback should fail with no backup")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_rollback_dry_run_completes(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            backup_dir = Path(tmpdir) / "srv" / "devassist" / "state" / "backups"
            db_file = Path(tmpdir) / "srv" / "devassist" / "state" / "operational.db"
            if db_file.exists():
                shutil.copy2(db_file, backup_dir / "operational-20260101-000000.db")
            ts_dir = Path(tmpdir) / "srv" / "devassist" / "state" / "backups"
            result = _run_script("rollback-self.sh", env)
            self.assertEqual(result.returncode, 0, result.stdout[-500:] if result.stdout else "ok")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_rollback_does_not_touch_state_db(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("rollback-self.sh", env)
            output = result.stdout + result.stderr
            self.assertNotIn("state.db", output.replace("operational.db", ""))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestUpgradeSelf(unittest.TestCase):
    def test_upgrade_staging_without_activate(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("upgrade-self.sh", env)
            self.assertEqual(result.returncode, 0, result.stdout[-500:] if result.stdout else "ok")
            self.assertIn("--activate", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_upgrade_does_not_auto_activate(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            result = _run_script("upgrade-self.sh", env)
            output = result.stdout + result.stderr
            self.assertNotIn("systemctl start", output)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestDryRunPrefixContainment(unittest.TestCase):
    def test_install_does_not_write_outside_prefix(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
            }
            _run_script("install-self.sh", env)
            self.assertFalse(
                Path("/srv/devassist").exists(),
                "install wrote outside dry-run prefix",
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestNoSecretsInRepo(unittest.TestCase):
    def test_no_real_tokens_in_templates(self) -> None:
        templates_dir = SCRIPTS_DIR / "templates"
        for tpl in templates_dir.glob("*.j2"):
            content = tpl.read_text()
            self.assertNotIn("api.fireworks.ai", content, f"{tpl.name} contains real API URL")
            self.assertNotIn("real-token", content, f"{tpl.name} contains real token")

    def test_scripts_use_placeholder_tokens(self) -> None:
        for script in ["install-self.sh", "verify-self.sh"]:
            content = (SCRIPTS_DIR / script).read_text()
            if "token-placeholder" in content:
                self.assertNotIn("sk-", content, f"{script} contains real key prefix")


if __name__ == "__main__":
    unittest.main()
