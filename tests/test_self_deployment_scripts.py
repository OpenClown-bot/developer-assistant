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
        self.assertIn("TELEGRAM_BOT_TOKEN=", content)
        self.assertIn("GITHUB_TOKEN=", content)
        self.assertIn("FIREWORKS_API_KEY=", content)
        self.assertIn("OMNIROUTE_BASE_URL=", content)
        self.assertIn("TELEGRAM_ALLOWED_USERS=", content)
        self.assertIn("DEVASSIST_FOUNDER_TELEGRAM_USER_ID=", content)

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

    def test_start_limit_in_unit_section(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / f"devassist-{role}.service"
            content = unit.read_text()
            in_unit = False
            in_service = False
            for line in content.splitlines():
                if line.strip() == "[Unit]":
                    in_unit = True
                    in_service = False
                elif line.strip() == "[Service]":
                    in_service = True
                    in_unit = False
                if line.startswith("StartLimitIntervalSec") or line.startswith("StartLimitBurst"):
                    self.assertTrue(in_unit, f"StartLimit* in [Service] for {role}")
                    self.assertFalse(in_service, f"StartLimit* in [Service] for {role}")

    def test_home_env_in_all_services(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            unit = Path(self.tmpdir) / "etc" / "systemd" / "system" / f"devassist-{role}.service"
            content = unit.read_text()
            self.assertIn(f"HOME=/srv/devassist/runtimes/{role}", content, f"HOME not set for {role}")


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestRuntimeConfigRender(unittest.TestCase):
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

    def test_config_yaml_rendered_for_all_roles(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            cfg = Path(self.tmpdir) / "srv" / "devassist" / "runtimes" / role / ".hermes" / "config.yaml"
            self.assertTrue(cfg.is_file(), f"config.yaml not rendered for {role}")

    def test_no_template_placeholders_in_config(self) -> None:
        for role in ["orchestrator", "planner", "architect", "executor", "reviewer"]:
            cfg = Path(self.tmpdir) / "srv" / "devassist" / "runtimes" / role / ".hermes" / "config.yaml"
            content = cfg.read_text()
            self.assertNotIn("{{", content, f"Unsubstituted template placeholder in {role} config")
            self.assertNotIn("}}", content, f"Unsubstituted template placeholder in {role} config")

    def test_orchestrator_config_has_gateway_enabled(self) -> None:
        cfg = Path(self.tmpdir) / "srv" / "devassist" / "runtimes" / "orchestrator" / ".hermes" / "config.yaml"
        content = cfg.read_text()
        self.assertIn("gateway:", content)
        self.assertIn("enabled: true", content)

    def test_worker_configs_have_gateway_disabled(self) -> None:
        for role in ["planner", "architect", "executor", "reviewer"]:
            cfg = Path(self.tmpdir) / "srv" / "devassist" / "runtimes" / role / ".hermes" / "config.yaml"
            content = cfg.read_text()
            self.assertIn("enabled: false", content, f"{role} should have gateway disabled")

    def test_executor_has_terminal_block(self) -> None:
        for role in ["executor", "reviewer"]:
            cfg = Path(self.tmpdir) / "srv" / "devassist" / "runtimes" / role / ".hermes" / "config.yaml"
            content = cfg.read_text()
            self.assertIn("terminal:", content, f"{role} missing terminal block")
            self.assertIn("backend: docker", content, f"{role} missing docker backend")

    def test_config_has_omniroute_base_url(self) -> None:
        cfg = Path(self.tmpdir) / "srv" / "devassist" / "runtimes" / "orchestrator" / ".hermes" / "config.yaml"
        content = cfg.read_text()
        self.assertIn("base_url:", content)

    def test_env_file_reads_from_environment(self) -> None:
        tmpdir2 = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir2,
                "VERIFY_FIXTURE_MODE": "1",
                "ROLLBACK_DRY_RUN": "1",
                "UPGRADE_DRY_RUN": "1",
                "FIREWORKS_API_KEY": "fw-test-key-123",
                "TELEGRAM_ALLOWED_USERS": "12345",
            }
            _run_script("install-self.sh", env)
            env_file = Path(tmpdir2) / "srv" / "devassist" / "secrets" / "SELF-DEPLOY.env"
            content = env_file.read_text()
            self.assertIn("FIREWORKS_API_KEY=", content)
            self.assertIn("CUSTOM_API_KEY=", content)
            self.assertIn("CUSTOM_BASE_URL=", content)
            self.assertIn("TELEGRAM_ALLOWED_USERS=12345", content)
        finally:
            shutil.rmtree(tmpdir2, ignore_errors=True)
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
class TestRuntimeCheckEnforcementInUnits(unittest.TestCase):
    """TKT-033 / AUDIT-001 § 1 components A + D + E:
    every per-role systemd unit invokes runtime_check.check_runtime() at
    ExecStartPre and never auto-restarts on EX_CONFIG=78 (the abort exit
    code the CLI shim emits on RuntimeCheckError). Asserted directly
    against the rendered unit on disk, not the template, to catch any
    install-time mutation that would break enforcement.
    """

    EXPECTED_PRE = "ExecStartPre=/usr/bin/python3 -m developer_assistant.runtime_check"
    EXPECTED_RESTART_PREVENT = "RestartPreventExitStatus=78"
    EXPECTED_PYTHONPATH = "Environment=PYTHONPATH=/srv/devassist/repo/src"

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devassist-test-")
        self.env = {
            "INSTALL_DRY_RUN": "1",
            "INSTALL_DRY_RUN_PREFIX": self.tmpdir,
            "VERIFY_FIXTURE_MODE": "1",
            "ROLLBACK_DRY_RUN": "1",
            "UPGRADE_DRY_RUN": "1",
        }
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _read_unit(self, role: str) -> str:
        path = (
            Path(self.tmpdir)
            / "etc"
            / "systemd"
            / "system"
            / "devassist-{r}.service".format(r=role)
        )
        return path.read_text()

    def test_all_units_have_runtime_check_exec_start_pre(self) -> None:
        # AC-2: every role's unit invokes runtime_check.check_runtime() at
        # ExecStartPre BEFORE its own ExecStart so an invariant abort prevents
        # the runtime from ever launching.
        for role in ROLES:
            content = self._read_unit(role)
            self.assertIn(
                self.EXPECTED_PRE,
                content,
                "{r}.service missing ExecStartPre runtime_check".format(r=role),
            )
            pre_pos = content.find(self.EXPECTED_PRE)
            start_pos = content.find("\nExecStart=")
            self.assertGreater(start_pos, pre_pos, "ExecStartPre must precede ExecStart for {r}".format(r=role))

    def test_all_units_have_restart_prevent_exit_status_78(self) -> None:
        # AC-2: invariant abort (EX_CONFIG=78) MUST NOT auto-restart;
        # systemd RestartPreventExitStatus= takes the abort code (Option A:
        # Restart=always + RestartPreventExitStatus=78).
        for role in ROLES:
            content = self._read_unit(role)
            self.assertIn(
                self.EXPECTED_RESTART_PREVENT,
                content,
                "{r}.service missing RestartPreventExitStatus=78".format(r=role),
            )
            self.assertIn("Restart=always", content)

    def test_all_units_set_pythonpath_for_module_invocation(self) -> None:
        # The ExecStartPre invokes ``python3 -m developer_assistant.runtime_check``
        # under a sandboxed user (devassist); Environment=PYTHONPATH ensures
        # the systemd-spawned interpreter can import the module from
        # /srv/devassist/repo/src without polluting site-packages.
        for role in ROLES:
            content = self._read_unit(role)
            self.assertIn(
                self.EXPECTED_PYTHONPATH,
                content,
                "{r}.service missing PYTHONPATH for runtime_check module".format(r=role),
            )


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestPromptManifestRender(unittest.TestCase):
    """TKT-033 / AUDIT-001 § 1 component C:
    install-self.sh renders an install-time prompt-manifest.json with
    schema_version=1.0, rendered_at ISO8601, prompts {role: sha256} for the
    five canonical per-role prompts. Folded INSIDE render_runtime_configs()
    so it is part of the same atomic rendering phase as per-runtime
    config.yaml; the manifest is guaranteed to exist on disk before any
    ExecStart/ExecStartPre can run.
    """

    REPO_ROOT = Path(__file__).resolve().parents[1]
    PROMPT_FILES = {
        "orchestrator": "docs/prompts/runtime-hermes-orchestrator.md",
        "planner": "docs/prompts/business-planner.md",
        "architect": "docs/prompts/architect.md",
        "executor": "docs/prompts/executor.md",
        "reviewer": "docs/prompts/reviewer.md",
    }

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

    def _manifest_path(self, prefix: str) -> Path:
        return Path(prefix) / "srv" / "devassist" / "state" / "prompt-manifest.json"

    def _expected_sha(self, role: str) -> str:
        import hashlib

        path = self.REPO_ROOT / self.PROMPT_FILES[role]
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def test_manifest_rendered_with_correct_shape(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:] if result.stderr else "ok")
        manifest = self._manifest_path(self.tmpdir)
        self.assertTrue(manifest.is_file(), "prompt-manifest.json was not rendered")
        import json

        with open(manifest, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data.get("schema_version"), "1.0")
        self.assertIn("rendered_at", data)
        self.assertIsInstance(data["rendered_at"], str)
        # ISO8601 UTC with Z suffix is what install-self.sh writes.
        self.assertTrue(
            data["rendered_at"].endswith("Z") and "T" in data["rendered_at"],
            "rendered_at not ISO8601 UTC: {v!r}".format(v=data["rendered_at"]),
        )
        self.assertIn("prompts", data)
        prompts = data["prompts"]
        self.assertEqual(set(prompts.keys()), set(self.PROMPT_FILES.keys()))
        for role in self.PROMPT_FILES:
            self.assertEqual(prompts[role], self._expected_sha(role), "sha mismatch for {r}".format(r=role))

    def test_manifest_render_is_deterministic_modulo_timestamp(self) -> None:
        # Two consecutive renders MUST produce identical SHA-256 entries for
        # the same on-disk inputs; the rendered_at timestamp is the only
        # field allowed to differ. This protects against accidental
        # non-determinism (e.g., dict ordering) introduced by future
        # refactors of the renderer.
        result1 = _run_script("install-self.sh", self.env)
        self.assertEqual(result1.returncode, 0)
        import json

        with open(self._manifest_path(self.tmpdir), encoding="utf-8") as fh:
            data1 = json.load(fh)

        tmpdir2 = tempfile.mkdtemp(prefix="devassist-test-")
        try:
            env2 = dict(self.env)
            env2["INSTALL_DRY_RUN_PREFIX"] = tmpdir2
            result2 = _run_script("install-self.sh", env2)
            self.assertEqual(result2.returncode, 0)
            with open(self._manifest_path(tmpdir2), encoding="utf-8") as fh:
                data2 = json.load(fh)
        finally:
            shutil.rmtree(tmpdir2, ignore_errors=True)

        self.assertEqual(data1["schema_version"], data2["schema_version"])
        self.assertEqual(data1["prompts"], data2["prompts"])

    def test_manifest_rendered_before_systemd_units(self) -> None:
        # The manifest MUST exist before any unit is rendered (and a fortiori
        # before any ExecStart/ExecStartPre runs); this guards the call
        # ordering invariant in render_runtime_configs() folded BEFORE
        # render_systemd_units(). If install-self.sh ever reorders these
        # phases, the test will catch it via mtime comparison.
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0)
        manifest = self._manifest_path(self.tmpdir)
        self.assertTrue(manifest.is_file())
        manifest_mtime = manifest.stat().st_mtime
        for role in ROLES:
            unit = (
                Path(self.tmpdir)
                / "etc"
                / "systemd"
                / "system"
                / "devassist-{r}.service".format(r=role)
            )
            self.assertTrue(unit.is_file())
            self.assertLessEqual(
                manifest_mtime,
                unit.stat().st_mtime,
                "prompt-manifest.json must be rendered no later than {r}.service".format(r=role),
            )


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
