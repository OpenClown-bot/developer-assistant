"""Startup check helper for developer-assistant Hermes runtimes.

Each runtime invokes this module before normal operation. It verifies:
  (a) HERMES_DEVASSIST_ROLE is one of the five allowed values.
  (b) Loaded skills match the per-role expected set from MULTI-HERMES-CONTRACT.md § 5.
  (c) The per-runtime config references /srv/devassist/state/operational.db via symlink
      (NOT the per-runtime ~/.hermes/state.db Hermes native sessions database).
  (d) Schema version of the operational store matches the expected version.
  (e) For Orchestrator only: Telegram bot token env var is non-empty.
      For non-Orchestrator: telegram-gateway skill is NOT loaded.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Mapping

_ALLOWED_ROLES = frozenset({"orchestrator", "planner", "architect", "executor", "reviewer"})

_SCHEMA_VERSION_EXPECTED = "3"

_ROLE_SKILLS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "orchestrator": (
        ("telegram-gateway", "cronjob", "memory"),
        (
            "dev-assist-classifier",
            "dev-assist-progress-report",
            "dev-assist-escalation-surface",
            "dev-assist-work-queue-write",
        ),
    ),
    "planner": (
        ("cronjob", "memory"),
        (
            "dev-assist-prd-writer",
            "dev-assist-questions-writer",
            "dev-assist-work-queue-poll",
        ),
    ),
    "architect": (
        ("cronjob", "memory"),
        (
            "dev-assist-arch-writer",
            "dev-assist-adr-writer",
            "dev-assist-tickets-writer",
            "dev-assist-work-queue-poll",
        ),
    ),
    "executor": (
        ("terminal", "cronjob", "memory"),
        (
            "dev-assist-executor-discipline",
            "dev-assist-write-zone-enforcer",
            "dev-assist-github-workflow",
            "dev-assist-work-queue-poll",
        ),
    ),
    "reviewer": (
        ("terminal", "cronjob", "memory"),
        (
            "dev-assist-reviewer-rubric",
            "dev-assist-review-writer",
            "dev-assist-work-queue-poll",
        ),
    ),
}


class RuntimeCheckError(Exception):
    pass


class RoleValueError(RuntimeCheckError):
    pass


class SkillsMismatchError(RuntimeCheckError):
    pass


class OperationalDbPathError(RuntimeCheckError):
    pass


class SchemaVersionMismatchError(RuntimeCheckError):
    pass


class TelegramTokenMissingError(RuntimeCheckError):
    pass


class TelegramGatewayLoadedError(RuntimeCheckError):
    pass


def _read_config_skills(config_path: str) -> frozenset[str]:
    if not os.path.exists(config_path):
        return frozenset()
    result = frozenset()
    with open(config_path, encoding="utf-8") as fh:
        content = fh.read()
    in_built_in = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "skills:":
            continue
        if stripped == "built_in:":
            in_built_in = True
            continue
        if stripped.startswith("plugins:") or stripped.startswith("provider:") or stripped == "external_dirs:":
            in_built_in = False
            continue
        if stripped.startswith("- ") and in_built_in:
            skill = stripped[2:].strip()
            if skill:
                result = result | {skill}
    return result


def _check_operational_db_symlink(hermes_home: str) -> bool:
    operational_db = os.path.join(hermes_home, "operational.db")
    state_db = os.path.join(hermes_home, "state.db")

    if not os.path.islink(operational_db):
        return False

    target = os.readlink(operational_db)
    if not target.startswith("/srv/devassist/state/operational.db"):
        return False

    if os.path.exists(state_db):
        return False

    return True


def check_runtime(
    role: str,
    config_path: str,
    operational_db_path: str,
    env: Mapping[str, str],
) -> None:
    if role not in _ALLOWED_ROLES:
        raise RoleValueError(
            "HERMES_DEVASSIST_ROLE='{r}' is not one of the five allowed values: {a}".format(
                r=role, a=", ".join(sorted(_ALLOWED_ROLES))
            )
        )

    built_in = _read_config_skills(config_path)
    expected_built_in, _ = _ROLE_SKILLS[role]
    expected_built_in_f = frozenset(expected_built_in)

    if role != "orchestrator" and "telegram-gateway" in built_in:
        raise TelegramGatewayLoadedError(
            "telegram-gateway skill is loaded by non-Orchestrator runtime (role={r}). "
            "Only the Orchestrator may load telegram-gateway.".format(r=role)
        )

    if built_in != expected_built_in_f:
        raise SkillsMismatchError(
            "Built-in skills mismatch for role '{r}': got {g}, expected {e}".format(
                r=role, g=sorted(built_in), e=sorted(expected_built_in_f)
            )
        )

    hermes_home = env.get("HERMES_HOME", "")
    if hermes_home:
        if not _check_operational_db_symlink(hermes_home):
            operational_db_file = os.path.join(hermes_home, "operational.db")
            state_db_file = os.path.join(hermes_home, "state.db")
            if not os.path.islink(operational_db_file):
                raise OperationalDbPathError(
                    "$HERMES_HOME/operational.db is not a symlink; "
                    "must point to /srv/devassist/state/operational.db"
                )
            if os.path.exists(state_db_file):
                raise OperationalDbPathError(
                    "Per-runtime state.db exists at {s} (collision with shared operational.db). "
                    "Only operational.db symlink should exist.".format(s=state_db_file)
                )
            target = os.readlink(operational_db_file)
            raise OperationalDbPathError(
                "operational.db symlink target '{t}' does not point to "
                "/srv/devassist/state/operational.db".format(t=target)
            )

    if os.path.exists(operational_db_path):
        try:
            conn = sqlite3.connect(operational_db_path, timeout=1.0)
            try:
                cur = conn.execute(
                    "SELECT value FROM _schema_meta WHERE key='schema_version'"
                )
                row = cur.fetchone()
                if row is None:
                    raise SchemaVersionMismatchError(
                        "No schema_version found in _schema_meta for operational.db"
                    )
                version = row[0]
                if version != _SCHEMA_VERSION_EXPECTED:
                    raise SchemaVersionMismatchError(
                        "Schema version mismatch: got {g}, expected {e}".format(
                            g=version, e=_SCHEMA_VERSION_EXPECTED
                        )
                    )
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise RuntimeCheckError("operational.db unreadable: {exc}".format(exc=exc)) from exc

    if role == "orchestrator":
        token = env.get("TELEGRAM_BOT_TOKEN", "")
        if not token or token == "test-token-placeholder":
            raise TelegramTokenMissingError(
                "TELEGRAM_BOT_TOKEN env var is empty or placeholder; "
                "Orchestrator runtime requires a real Telegram bot token"
            )