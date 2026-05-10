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
            # TKT-034 § 1.B.vi: 11 baseline invariants + 8 new operator-
            # hygiene + prereq invariants = 19 total. The summary line
            # uses the form "PASS  (N/N invariants)".
            self.assertIn("19/19", result.stdout)
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


# ----------------------------------------------------------------------
# TKT-034 § 6 — extended fixture / unit / integration tests for the
# operator-hygiene + interactive-installer surface.
# ----------------------------------------------------------------------


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestSharedSkillsManifestRender(unittest.TestCase):
    """TKT-034 AC-2 (d): render_shared_skills_manifest writes an atomic
    JSON manifest enumerating the 15 dev-assist-* skills from
    MULTI-HERMES-CONTRACT.md § 5.0."""

    EXPECTED_SKILLS = (
        "dev-assist-classifier",
        "dev-assist-progress-report",
        "dev-assist-escalation-surface",
        "dev-assist-work-queue-write",
        "dev-assist-work-queue-poll",
        "dev-assist-prd-writer",
        "dev-assist-questions-writer",
        "dev-assist-arch-writer",
        "dev-assist-adr-writer",
        "dev-assist-tickets-writer",
        "dev-assist-executor-discipline",
        "dev-assist-write-zone-enforcer",
        "dev-assist-github-workflow",
        "dev-assist-reviewer-rubric",
        "dev-assist-review-writer",
    )

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devassist-skills-")
        self.env = {
            "INSTALL_DRY_RUN": "1",
            "INSTALL_DRY_RUN_PREFIX": self.tmpdir,
            "VERIFY_FIXTURE_MODE": "1",
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_manifest_file_exists(self) -> None:
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stdout[-500:])
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        self.assertTrue(manifest.is_file(), "shared-skills-manifest.json not rendered")

    def test_manifest_lists_all_15_skills(self) -> None:
        import json
        _run_script("install-self.sh", self.env)
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        data = json.loads(manifest.read_text())
        self.assertEqual(data["schema_version"], "1.0")
        for skill in self.EXPECTED_SKILLS:
            self.assertIn(skill, data["skills"], f"manifest missing skill: {skill}")
        # No unexpected entries
        self.assertEqual(set(data["skills"].keys()), set(self.EXPECTED_SKILLS))

    def test_manifest_records_release_commit(self) -> None:
        import json
        _run_script("install-self.sh", self.env)
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        data = json.loads(manifest.read_text())
        # release_commit is either a 40-char SHA or "unknown" if git unavailable
        self.assertIn("release_commit", data)
        for entry in data["skills"].values():
            self.assertIn("path", entry)
            self.assertIn("sha256_of_skill_md", entry)
            self.assertIn("pinned_commit", entry)

    def test_manifest_atomic_render(self) -> None:
        # Two consecutive runs must produce identical manifests modulo
        # the rendered_at timestamp; the .tmp.<pid> staging file MUST
        # not survive after mv -f.
        _run_script("install-self.sh", self.env)
        manifest_dir = Path(self.tmpdir) / "srv" / "devassist" / "state"
        for f in manifest_dir.glob("shared-skills-manifest.json.tmp.*"):
            self.fail(f"staging file survived: {f}")

    def test_manifest_skips_no_absent_sentinels(self) -> None:
        # TKT-034 v0.3.1 § 1.A.iv enforcement (RV-CODE-033 HIGH-1):
        # a clean install with all 15 SKILL.md present on disk MUST
        # produce a manifest where every sha256_of_skill_md is a real
        # hex digest. The legacy "absent_at_install_time" sentinel is
        # disallowed.
        import json
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stdout[-500:])
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        data = json.loads(manifest.read_text())
        for skill, entry in data["skills"].items():
            sha = entry["sha256_of_skill_md"]
            self.assertNotEqual(
                sha,
                "absent_at_install_time",
                f"sentinel SHA recorded for {skill}; § 1.A.iv enforcement violated",
            )
            self.assertEqual(
                len(sha), 64, f"{skill}: SHA-256 hex digest must be 64 chars, got {len(sha)}",
            )
            self.assertRegex(
                sha,
                r"^[0-9a-f]{64}$",
                f"{skill}: SHA-256 must be lowercase hex, got {sha!r}",
            )

    def test_render_aborts_when_skill_md_missing(self) -> None:
        # TKT-034 v0.3.1 § 4 AC-2 (A.iv) negative test pair (1/2):
        # if any one shared-skills/<skill>/SKILL.md is absent at install
        # time, render_shared_skills_manifest() MUST abort the install
        # with exit 1 and a FATAL log message naming the missing path.
        # We exercise the renderer in isolation by sourcing install-self.sh
        # and invoking render_shared_skills_manifest() against a sandboxed
        # SCRIPT_DIR/BASE so the production source tree is not mutated.
        import shutil as _shutil
        repo_root = Path(__file__).resolve().parents[1]
        sandbox = Path(self.tmpdir) / "sandbox-repo"
        (sandbox / "scripts").mkdir(parents=True)
        _shutil.copytree(repo_root / "shared-skills", sandbox / "shared-skills")
        victim = sandbox / "shared-skills" / "dev-assist-classifier" / "SKILL.md"
        victim.unlink()
        base_dir = Path(self.tmpdir) / "srv-target"
        bash_cmd = (
            f'set +e; '
            f'source "{repo_root / "scripts" / "install-self.sh"}" 2>/dev/null; '
            f'SCRIPT_DIR="{sandbox}/scripts"; '
            f'BASE="{base_dir}"; '
            f'DRY_RUN=1; '
            f'render_shared_skills_manifest; '
            f'echo "EXIT_CODE:$?"'
        )
        result = subprocess.run(
            ["bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertIn(
            "FATAL: shared-skills source missing: shared-skills/dev-assist-classifier/SKILL.md",
            result.stdout,
            f"FATAL log line missing or wrong format. stdout={result.stdout!r}",
        )
        # The function must exit (non-zero) before reaching the EXIT_CODE
        # echo, since `exit 1` from inside a sourced script terminates the
        # entire shell. The marker MUST NOT appear.
        self.assertNotIn(
            "EXIT_CODE:0",
            result.stdout,
            "render_shared_skills_manifest must abort, not return cleanly",
        )


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestSecretsFileAcl(unittest.TestCase):
    """TKT-034 AC-6: SELF-DEPLOY.env tightened to 0600 in fixture (0400
    on real install); secrets/ dir mode 0710. The verify-self
    `check_secrets_file_acl` invariant accepts both 0400 and 0600 in
    fixture mode."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devassist-acl-")
        self.env = {
            "INSTALL_DRY_RUN": "1",
            "INSTALL_DRY_RUN_PREFIX": self.tmpdir,
            "VERIFY_FIXTURE_MODE": "1",
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_secrets_dir_mode_0710(self) -> None:
        _run_script("install-self.sh", self.env)
        secrets_dir = Path(self.tmpdir) / "srv" / "devassist" / "secrets"
        mode = oct(secrets_dir.stat().st_mode & 0o777)
        self.assertEqual(mode, "0o710", f"secrets/ dir mode {mode}, expected 0o710")

    def test_env_file_mode_0600_in_fixture(self) -> None:
        _run_script("install-self.sh", self.env)
        env_file = Path(self.tmpdir) / "srv" / "devassist" / "secrets" / "SELF-DEPLOY.env"
        mode = oct(env_file.stat().st_mode & 0o777)
        # fixture: 0600 (chown to devassist requires root and is skipped)
        self.assertEqual(mode, "0o600", f"SELF-DEPLOY.env mode {mode}, expected 0o600")


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestVerifySelfNewInvariants(unittest.TestCase):
    """TKT-034 § 1.B.vi: 8 new check_* invariants. PASS path covered by
    install-then-verify; FAIL path covered by hand-crafted env files."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devassist-verify-new-")
        self.env = {
            "INSTALL_DRY_RUN": "1",
            "INSTALL_DRY_RUN_PREFIX": self.tmpdir,
            "VERIFY_FIXTURE_MODE": "1",
        }
        # Establish a fully-installed baseline
        result = _run_script("install-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stdout[-500:])

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_verify_passes_after_clean_install(self) -> None:
        result = _run_script("verify-self.sh", self.env)
        self.assertEqual(result.returncode, 0, result.stdout[-500:])
        # The 8 new invariants must each appear with PASS in the log
        for inv_name in (
            "gh CLI installed",
            "gh CLI authenticated as devassist",
            "devassist git identity configured",
            "origin remote URL token-free",
            "shared-skills manifest parity",
            "secrets file ACL hardened",
            "required env vars set + non-placeholder",
            "VPS prereq baseline",
        ):
            self.assertIn(f"PASS: {inv_name}", result.stdout)

    def test_verify_fails_when_manifest_missing(self) -> None:
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        manifest.unlink()
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shared-skills manifest parity: FAIL", result.stdout)

    def test_verify_fails_when_manifest_malformed(self) -> None:
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        manifest.write_text("not-json{")
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shared-skills manifest parity: FAIL", result.stdout)

    def test_verify_fails_when_manifest_missing_skill(self) -> None:
        import json
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        data = json.loads(manifest.read_text())
        del data["skills"]["dev-assist-classifier"]
        manifest.write_text(json.dumps(data))
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dev-assist-classifier", result.stdout)

    def test_verify_fails_when_manifest_has_absent_sentinel(self) -> None:
        # TKT-034 v0.3.1 § 4 AC-2 (A.iv) negative test pair (2/2)
        # (RV-CODE-033 HIGH-1): a manifest where any
        # sha256_of_skill_md == "absent_at_install_time" MUST cause
        # check_shared_skills_manifest_match to FAIL with no skip clause.
        import json
        manifest = Path(self.tmpdir) / "srv" / "devassist" / "state" / "shared-skills-manifest.json"
        data = json.loads(manifest.read_text())
        data["skills"]["dev-assist-classifier"]["sha256_of_skill_md"] = "absent_at_install_time"
        manifest.write_text(json.dumps(data))
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shared-skills manifest parity: FAIL", result.stdout)
        self.assertIn(
            "dev-assist-classifier(absent_at_install_time-sentinel-disallowed)",
            result.stdout,
            "FAIL message must surface the disallowed sentinel for the offending skill",
        )

    def test_verify_fails_when_gh_hosts_missing(self) -> None:
        marker = Path(self.tmpdir) / "home" / "devassist" / ".config" / "gh" / "hosts.yml"
        if marker.exists():
            marker.unlink()
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gh CLI authenticated as devassist: FAIL", result.stdout)

    def test_verify_fails_when_gitconfig_placeholder(self) -> None:
        gitconfig = Path(self.tmpdir) / "home" / "devassist" / ".gitconfig"
        gitconfig.write_text(
            "[user]\n\tname = YOUR_NAME\n\temail = YOUR_EMAIL\n"
            "[credential]\n\thelper = !gh auth git-credential\n"
        )
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("devassist git identity configured: FAIL", result.stdout)

    def test_verify_fails_when_origin_url_has_token(self) -> None:
        # Stage a fake origin with embedded credential
        repo_dir = Path(self.tmpdir) / "srv" / "devassist" / "repo"
        git_dir = repo_dir / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / "config").write_text(
            "[remote \"origin\"]\n"
            "\turl = https://ghp_TESTTOKEN@github.com/o/r.git\n"
            "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
        )
        result = _run_script("verify-self.sh", self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("origin remote URL token-free: FAIL", result.stdout)

    def test_verify_fails_when_required_env_var_placeholder_in_production_mode(self) -> None:
        # TKT-034 AC-8 (g): in production verify (FIXTURE=0) the strict
        # placeholder-rejection path must reject the test-token-placeholder
        # values. We source verify-self.sh into a clean shell (the
        # BASH_SOURCE != $0 guard prevents main() auto-run) and call
        # check_required_env_vars_present directly so no network probes
        # fire.
        env_file = Path(self.tmpdir) / "srv" / "devassist" / "secrets" / "SELF-DEPLOY.env"
        env_file.write_text(
            "TELEGRAM_BOT_TOKEN=test-token-placeholder\n"
            "TELEGRAM_ALLOWED_USERS=test-user-placeholder\n"
            "DEVASSIST_FOUNDER_TELEGRAM_USER_ID=test-user-placeholder\n"
            "GITHUB_TOKEN=test-token-placeholder\n"
            "FIREWORKS_API_KEY=test-token-placeholder\n"
            "OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1\n"
            "HERMES_DEVASSIST_REPO_URL=https://github.com/o/r.git\n"
            "HERMES_DEVASSIST_REPO_BRANCH=main\n"
            "OPERATOR_GIT_USER_NAME=op\n"
            "OPERATOR_GIT_USER_EMAIL=op@x\n"
        )
        bash_cmd = (
            f'PREFIX="{self.tmpdir}"; '
            f'BASE="${{PREFIX}}/srv/devassist"; '
            f'ENV_FILE="${{BASE}}/secrets/SELF-DEPLOY.env"; '
            f'FIXTURE=0; '
            f'DRY_RUN=0; '
            f'PASS_COUNT=0; FAIL_COUNT=0; FAIL_SUMMARY=""; '
            f'log() {{ :; }}; '
            f'record_pass() {{ PASS_COUNT=$((PASS_COUNT+1)); echo "PASS:$1"; }}; '
            f'record_fail() {{ FAIL_COUNT=$((FAIL_COUNT+1)); echo "FAIL:$1: $2"; }}; '
            f'source "{SCRIPTS_DIR}/verify-self.sh" 2>/dev/null; '
            # Re-set FIXTURE/DRY_RUN/BASE because sourcing reset them
            f'FIXTURE=0; DRY_RUN=0; '
            f'PREFIX="{self.tmpdir}"; '
            f'BASE="${{PREFIX}}/srv/devassist"; '
            f'ENV_FILE="${{BASE}}/secrets/SELF-DEPLOY.env"; '
            f'check_required_env_vars_present'
        )
        result = subprocess.run(
            ["bash", "-c", bash_cmd],
            capture_output=True, text=True,
            timeout=15, check=False,
        )
        # Output is the verify-self log() format: "verify-self: FAIL:
        # required env vars set + non-placeholder -- ..."
        self.assertIn("required env vars set + non-placeholder", result.stdout)
        self.assertIn("placeholder", result.stdout)
        self.assertIn("FAIL", result.stdout)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestForceReinstallFlag(unittest.TestCase):
    """TKT-034 AC-9: --force-reinstall skips prior-deploy detection;
    --rotate-secrets aborts; --reprompt-secrets aborts."""

    def test_force_reinstall_skips_prior_deploy_in_dry_run(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-force-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
            }
            result = _run_script("install-self.sh", env, args=["--force-reinstall"])
            self.assertEqual(result.returncode, 0, result.stdout[-500:])
            # Detection-skipped log message present
            self.assertIn(
                "Prior-deploy detection skipped",
                result.stdout,
                "expected '--force-reinstall' log entry"
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_help_flag_lists_all_new_options(self) -> None:
        result = _run_script("install-self.sh", {}, args=["--help"])
        self.assertEqual(result.returncode, 0)
        for opt in (
            "--interactive",
            "--non-interactive",
            "--gh-auth=pat",
            "--gh-auth=ssh",
            "--force-reinstall",
            "--reprompt-secrets",
            "--rotate-secrets",
        ):
            self.assertIn(opt, result.stdout, f"--help missing {opt}")


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestPreReqVerificationStubsInDryRun(unittest.TestCase):
    """TKT-034 AC-10: verify_prereqs() is a no-op in DRY_RUN /
    INSTALL_FIXTURE_PROBES=1 to keep the test grid offline. Real-mode
    behaviour is exercised on a real Ubuntu 22.04 VPS during the
    operator install."""

    def test_dry_run_install_log_records_prereq_skip(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="devassist-prereq-")
        try:
            env = {
                "INSTALL_DRY_RUN": "1",
                "INSTALL_DRY_RUN_PREFIX": tmpdir,
                "VERIFY_FIXTURE_MODE": "1",
            }
            result = _run_script("install-self.sh", env)
            self.assertEqual(result.returncode, 0)
            self.assertIn("verify_prereqs (8 checks) skipped", result.stdout)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestPrereqBaselineSubChecks(unittest.TestCase):
    """TKT-034 v0.3.1 § 4 AC-8(8) (RV-CODE-033 HIGH-2): verify-time
    check_prereq_baseline() mirrors 7 of the 8 install-time
    verify_prereqs() checks (sudo-posture excluded per Founder
    Decision α). One negative-path test per sub-check + one positive
    aggregation test, exercised by sourcing verify-self.sh and
    overriding the underlying CLIs as bash functions.
    """

    DEFAULT_GOOD_STUBS = r"""
lsb_release() {
    case "$1" in
        -is) echo "Ubuntu" ;;
        -rs) echo "22.04" ;;
        *) echo "" ;;
    esac
}
curl() {
    # Mimic `curl -fsS -o /dev/null -w "%{http_code}" --max-time 10 https://api.github.com`
    echo "200"
    return 0
}
df() {
    # Mimic `df --output=avail /srv` → header line + KB count
    printf 'Avail\n9999999\n'
    return 0
}
docker() { return 0; }
systemctl() { return 0; }
getent() {
    case "$1 $2" in
        "group docker") echo "docker:x:999:devassist" ;;
        *) echo "" ;;
    esac
    return 0
}
id() { return 0; }
python3() {
    if [ "$1" = "--version" ]; then
        echo "Python 3.12.0"
        return 0
    fi
    builtin command python3 "$@"
}
gh() {
    if [ "$1" = "--version" ]; then
        echo "gh version 2.55.0 (2024-08-01)"
        return 0
    fi
    return 1
}
command() {
    if [ "$1" = "-v" ]; then
        case "$2" in
            bash|systemctl|sqlite3|curl|tar|git|python3|sudo|lsb_release|stat|sha256sum|useradd|usermod|chmod|chown|ln|mkdir|gh|docker)
                echo "/stub/$2"
                return 0
                ;;
            *)
                builtin command "$@"
                return $?
                ;;
        esac
    fi
    builtin command "$@"
}
"""

    def _run_check(self, extra_stubs: str = "") -> subprocess.CompletedProcess:
        bash_cmd = (
            "set +e; "
            f'source "{SCRIPTS_DIR}/verify-self.sh" 2>/dev/null; '
            "FIXTURE=0; DRY_RUN=0; "
            "PASS_COUNT=0; FAIL_COUNT=0; FAIL_SUMMARY=\"\"; "
            f"{self.DEFAULT_GOOD_STUBS}\n"
            f"{extra_stubs}\n"
            "check_prereq_baseline; "
            "echo \"--RC:$?\"; "
            "echo \"--PASS_COUNT:$PASS_COUNT\"; "
            "echo \"--FAIL_COUNT:$FAIL_COUNT\"; "
        )
        return subprocess.run(
            ["bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def test_positive_path_all_stubs_satisfied(self) -> None:
        result = self._run_check()
        self.assertIn("PASS: VPS prereq baseline", result.stdout)
        self.assertIn("--PASS_COUNT:1", result.stdout)
        self.assertIn("--FAIL_COUNT:0", result.stdout)

    def test_subcheck_1_os_wrong_distro_fails(self) -> None:
        override = r"""
lsb_release() {
    case "$1" in
        -is) echo "Debian" ;;
        -rs) echo "11" ;;
    esac
}
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("OS(expected Ubuntu 22.04, got Debian 11)", result.stdout)

    def test_subcheck_2_network_unreachable_fails(self) -> None:
        # Stub curl to print non-200 HTTP code
        override = r"""
curl() { echo "503"; return 0; }
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("network(api.github.com HTTP 503)", result.stdout)

    def test_subcheck_3_disk_too_small_fails(self) -> None:
        # Stub df to print only 100 KB free on /srv
        override = r"""
df() { printf 'Avail\n100\n'; return 0; }
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("disk(/srv 100 KB < 5000000)", result.stdout)

    def test_subcheck_4_required_cli_missing_fails(self) -> None:
        # Stub `command -v sqlite3` to fail (rest stay present)
        override = r"""
command() {
    if [ "$1" = "-v" ]; then
        case "$2" in
            sqlite3)
                return 1
                ;;
            bash|systemctl|curl|tar|git|python3|sudo|lsb_release|stat|sha256sum|useradd|usermod|chmod|chown|ln|mkdir|gh|docker)
                echo "/stub/$2"
                return 0
                ;;
            *)
                builtin command "$@"
                return $?
                ;;
        esac
    fi
    builtin command "$@"
}
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("required-CLIs(missing: sqlite3)", result.stdout)

    def test_subcheck_5_docker_daemon_inactive_fails(self) -> None:
        # docker command present, but `systemctl is-active docker` fails
        override = r"""
systemctl() {
    if [ "$1" = "is-active" ] && [ "$2" = "docker" ]; then
        return 1
    fi
    return 0
}
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("docker(daemon-inactive", result.stdout)

    def test_subcheck_6_python_below_311_fails(self) -> None:
        # Stub python3 --version to print 3.10.x
        override = r"""
python3() {
    if [ "$1" = "--version" ]; then
        echo "Python 3.10.12"
        return 0
    fi
    builtin command python3 "$@"
}
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("python(3.10.12 below 3.11)", result.stdout)

    def test_subcheck_7_gh_below_240_fails(self) -> None:
        # Stub gh --version to print 2.39.0
        override = r"""
gh() {
    if [ "$1" = "--version" ]; then
        echo "gh version 2.39.0 (2023-12-01)"
        return 0
    fi
    return 1
}
"""
        result = self._run_check(override)
        self.assertIn("FAIL: VPS prereq baseline", result.stdout)
        self.assertIn("gh(2.39.0 below 2.40.0)", result.stdout)


@unittest.skipUnless(_bash_available(), "bash unavailable on this platform")
class TestNoSecretsInTokenizedSurfaces(unittest.TestCase):
    """TKT-034 AC-12: scan repository surfaces for token-shaped patterns."""

    def test_install_self_has_no_real_token_patterns(self) -> None:
        content = (SCRIPTS_DIR / "install-self.sh").read_text()
        # Real GitHub PAT prefix (ghp_) is permitted in usage examples,
        # but never as a literal key. Forbidden: known fixture-leak
        # patterns observed in past CI failures.
        for forbidden in ("ghp_RealLeakedPattern", "sk-", "AKIA", "AIza"):
            self.assertNotIn(forbidden, content, f"install-self.sh contains pattern: {forbidden}")

    def test_verify_self_has_no_real_token_patterns(self) -> None:
        content = (SCRIPTS_DIR / "verify-self.sh").read_text()
        for forbidden in ("ghp_RealLeakedPattern", "sk-", "AKIA", "AIza"):
            self.assertNotIn(forbidden, content, f"verify-self.sh contains pattern: {forbidden}")


if __name__ == "__main__":
    unittest.main()
