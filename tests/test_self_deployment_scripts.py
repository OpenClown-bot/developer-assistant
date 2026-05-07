"""Tests for self-deployment scripts (TKT-020).

Validates install-self.sh, verify-self.sh, rollback-self.sh, upgrade-self.sh
under dry-run mode using a temp prefix. Uses stdlib unittest and tempfile.
No real tokens, PATs, or production hostnames appear here.

Platform note: The shell scripts target Ubuntu VPS. Tests that invoke them
skip gracefully on Windows where bash is unavailable. CI (GitHub Actions) runs
on Linux where bash is present.
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


def _bash_available() -> bool:
    try:
        subprocess.run(
            ["bash", "--version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def _skip_on_no_bash(cls: type) -> type:
    if not _bash_available():
        for name in dir(cls):
            if name.startswith("test_"):
                method = getattr(cls, name)
                setattr(cls, name, unittest.skip("bash unavailable on this platform")(method))
    return cls
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


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
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
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if "systemctl start devassist" in line and "To start, run:" not in line:
                self.fail(f"install should not start units in dry-run: {line}")

    def test_install_creates_journald_dropin(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0)
        dropin = Path(self.tmpdir) / "etc" / "systemd" / "journald.conf.d" / "dev-assist.conf"
        self.assertTrue(dropin.is_file(), "journald drop-in not created")
        content = dropin.read_text()
        self.assertIn("SystemMaxUse=1G", content)
        self.assertIn("MaxRetentionSec=30d", content)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
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

    def test_orchestrator_uses_runner(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-orchestrator.service"
        content = unit.read_text()
        self.assertIn("devassist-orchestrator-runner", content)

    def test_planner_uses_worker_runner(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist-planner.service"
        content = unit.read_text()
        self.assertIn("devassist-worker-runner", content)

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

    def test_target_wants_five_runtime_units(self) -> None:
        unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / "devassist.target"
        content = unit.read_text()
        for name in [
            "devassist-orchestrator.service",
            "devassist-planner.service",
            "devassist-architect.service",
            "devassist-executor.service",
            "devassist-reviewer.service",
        ]:
            self.assertIn(name, content, f"target missing Wants for {name}")
        self.assertNotIn("omniroute.service", content, "target should not reference omniroute (remote)")
        self.assertNotIn("devassist-web.service", content, "target should not reference web (removed)")


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
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
            self.assertIn("11/11", result.stdout)
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

    def test_verify_includes_health_endpoint_invariant(self) -> None:
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
            self.assertIn("per-runtime health endpoints", result.stdout + result.stderr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
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


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestUpgradeSelfPrimary(unittest.TestCase):
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
            for line in output.splitlines():
                if "systemctl start devassist" in line and "To start, run:" not in line:
                    self.fail(f"upgrade should not auto-activate units in dry-run: {line}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
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
            before = {}
            for check_path in [Path("/usr/local/bin/devassist-worker-runner"),
                               Path("/usr/local/bin/devassist-orchestrator-runner")]:
                if check_path.exists():
                    before[str(check_path)] = check_path.stat().st_mtime_ns
            _run_script("install-self.sh", env)
            modified = []
            for check_path in [Path("/usr/local/bin/devassist-worker-runner"),
                               Path("/usr/local/bin/devassist-orchestrator-runner")]:
                if str(check_path) in before:
                    if check_path.stat().st_mtime_ns != before[str(check_path)]:
                        modified.append(str(check_path))
                else:
                    if check_path.exists():
                        modified.append(str(check_path))
            self.assertFalse(
                modified,
                f"install modified/created files outside dry-run prefix: {modified}",
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
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
