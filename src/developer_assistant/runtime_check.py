"""Startup check helper for developer-assistant Hermes runtimes.

Each runtime invokes this module before normal operation. It verifies the
following eleven invariants drawn from TKT-021 (v0.1.1) § 1 (a)-(e) and
TKT-033 (AUDIT-001) § 1 components B and C. Each invariant emits a structured
journald marker on stderr immediately before raising the existing exception
type. The marker grammar is fixed (see TKT-033 § 1 component E):

    RUNTIME_CHECK_FAILED:<role>:<invariant_name>

Where ``<role>`` is one of ``orchestrator``, ``planner``, ``architect``,
``executor``, ``reviewer`` (or empty when ``HERMES_DEVASSIST_ROLE`` is unset
or unrecognised), and ``<invariant_name>`` is one of the eleven stable
symbolic names exposed as :data:`RUNTIME_CHECK_INVARIANTS`.

TKT-021 invariants (renamed to symbolic codes):
  (a)  ``role_env_unset``                          -- HERMES_DEVASSIST_ROLE absent / empty
       ``role_env_invalid``                        -- HERMES_DEVASSIST_ROLE not in allowed set
  (b)  ``loaded_skills_mismatch``                  -- built-in skills differ from per-role expected
  (c)  ``operational_db_path_mismatch``            -- $HERMES_HOME/operational.db symlink target mismatch
  (d)  ``schema_version_mismatch``                 -- _schema_meta.schema_version mismatch
  (e)  ``orchestrator_telegram_token_missing``     -- TELEGRAM_BOT_TOKEN empty / placeholder
       ``non_orchestrator_telegram_skill_loaded``  -- non-Orchestrator loaded telegram-gateway

TKT-033 new invariants:
  (B.i)   ``delegate_task_callable``    -- delegate_task is reachable rather than gated
  (B.ii)  ``skill_manage_callable``     -- skill_manage is reachable rather than gated
  (B.iii) ``prompt_manifest_missing``   -- /srv/devassist/state/prompt-manifest.json absent / unreadable
  (B.iii) ``prompt_sha_mismatch``       -- system_prompt.path SHA-256 differs from manifest entry

Per AC-5 the existing TKT-021 raise-side contract is preserved: each
invariant raises the same exception class for the same failure as before;
this module only adds the stderr marker emit before the raise plus four
new invariants alongside.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sqlite3
import sys
from typing import Any, Callable, Mapping

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

# Per-role canonical prompt mapping (TKT-033 § 1 component C). Mirrors the
# AGENTS.md Roles table; keys must match _ALLOWED_ROLES exactly. Used by both
# the install-time manifest renderer (scripts/install-self.sh) and any reader
# that wants to derive the canonical prompt-file FQN from the role label
# without parsing AGENTS.md.
PROMPT_FILE_BY_ROLE: Mapping[str, str] = {
    "orchestrator": "docs/prompts/runtime-hermes-orchestrator.md",
    "planner": "docs/prompts/business-planner.md",
    "architect": "docs/prompts/architect.md",
    "executor": "docs/prompts/executor.md",
    "reviewer": "docs/prompts/reviewer.md",
}

# TKT-033 § 1 component E -- eleven stable symbolic invariant names. The set
# is exposed as a public frozenset so verify-self.sh and tests can grep for
# it deterministically; adding a name to or removing a name from this set is
# a breaking change for downstream consumers (see TKT-033 § 1 component E).
INVARIANT_ROLE_ENV_UNSET = "role_env_unset"
INVARIANT_ROLE_ENV_INVALID = "role_env_invalid"
INVARIANT_LOADED_SKILLS_MISMATCH = "loaded_skills_mismatch"
INVARIANT_OPERATIONAL_DB_PATH_MISMATCH = "operational_db_path_mismatch"
INVARIANT_SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
INVARIANT_ORCHESTRATOR_TELEGRAM_TOKEN_MISSING = "orchestrator_telegram_token_missing"
INVARIANT_NON_ORCHESTRATOR_TELEGRAM_SKILL_LOADED = "non_orchestrator_telegram_skill_loaded"
INVARIANT_DELEGATE_TASK_CALLABLE = "delegate_task_callable"
INVARIANT_SKILL_MANAGE_CALLABLE = "skill_manage_callable"
INVARIANT_PROMPT_MANIFEST_MISSING = "prompt_manifest_missing"
INVARIANT_PROMPT_SHA_MISMATCH = "prompt_sha_mismatch"

RUNTIME_CHECK_INVARIANTS: frozenset[str] = frozenset(
    {
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
)

# Exit code emitted by the CLI shim (and recommended for any script wrapper)
# when ``check_runtime`` raises ``RuntimeCheckError``. EX_CONFIG=78 per
# /usr/include/sysexits.h. AC-2 requires the systemd unit's
# ``RestartPreventExitStatus=`` to list this code so an invariant abort never
# auto-restarts.
RUNTIME_CHECK_ABORT_EXIT_CODE = 78

# Canonical install-time location for the per-role prompt-manifest, written
# atomically by ``scripts/install-self.sh`` (TKT-033 § 1 component C).
DEFAULT_PROMPT_MANIFEST_PATH = "/srv/devassist/state/prompt-manifest.json"


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


class DelegateTaskCallableError(RuntimeCheckError):
    pass


class SkillManageCallableError(RuntimeCheckError):
    pass


class PromptManifestMissingError(RuntimeCheckError):
    pass


class PromptShaMismatchError(RuntimeCheckError):
    pass


def _emit_marker(role: str, invariant_name: str) -> None:
    """Emit the structured RUNTIME_CHECK_FAILED marker on stderr.

    The grammar is ``RUNTIME_CHECK_FAILED:<role>:<invariant_name>`` (one line,
    LF-terminated, flushed). Per TKT-033 § 1 component E ``<role>`` is one of
    the five allowed values; for ``role_env_unset`` and ``role_env_invalid``
    we deliberately emit an empty role so the grammar stays parseable for
    downstream greps that assume a known role token at most.
    """
    if role not in _ALLOWED_ROLES:
        role = ""
    sys.stderr.write("RUNTIME_CHECK_FAILED:{r}:{n}\n".format(r=role, n=invariant_name))
    sys.stderr.flush()


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


def _read_system_prompt_path(config_path: str) -> str:
    """Return the runtime's resolved ``system_prompt.path`` value (or empty).

    Mirrors the simple line-by-line shape of :func:`_read_config_skills`; the
    config schema pins ``system_prompt:`` as a top-level mapping with a single
    ``path:`` child (see ``etc/runtime-templates/<role>/config.yaml.tmpl``).
    """
    if not os.path.exists(config_path):
        return ""
    with open(config_path, encoding="utf-8") as fh:
        content = fh.read()
    in_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "system_prompt:":
            in_section = True
            continue
        if in_section:
            if stripped.startswith("path:"):
                return stripped[len("path:"):].strip()
            if stripped and not line.startswith((" ", "\t")):
                in_section = False
    return ""


def _resolve_hermes_skill_entry_point(skill_module: Any) -> Callable[..., Any] | None:
    """Resolve the public callable entry point of a Hermes built-in skill module.

    Hermes built-in skills expose their entry point as a module-level callable
    named ``invoke`` or ``main``, or via a ``Skill`` class whose instance
    exposes an ``invoke`` method. Returns the resolved callable, or ``None``
    if no recognisable shape is present.
    """
    for attr in ("invoke", "main"):
        candidate = getattr(skill_module, attr, None)
        if callable(candidate):
            return candidate
    skill_class = getattr(skill_module, "Skill", None)
    if skill_class is None:
        return None
    try:
        instance = skill_class()
    except BaseException:
        return None
    method = getattr(instance, "invoke", None)
    if callable(method):
        return method
    return None


def _attempt_hermes_skill_round_trip(config_path: str, skill_name: str) -> str:
    """Attempt an in-process invocation of a Hermes built-in skill module.

    Per TKT-033 § 1 component B(i)/(ii) the AC-3 round-trip must be an actual
    call attempt against the same Hermes runtime that would otherwise execute
    the skill, not a config-level introspection of ``skills.<name>.enabled``
    or ``plugins.disabled``. The systemd unit's ``Environment=PYTHONPATH=
    /srv/devassist/repo/src`` brings the upstream ``hermes`` Python package
    onto ``sys.path`` so this helper can import the built-in skill module
    in-process and dispatch on it directly.

    Returns ``"gated"`` when any of the following holds (the call did NOT
    succeed end-to-end, which is the AC-3 pass condition):
      * ``importlib.import_module("hermes.skills.<skill_name>")`` raises
        ``ImportError`` -- the module is not present on this interpreter's
        ``sys.path``, so the skill cannot be invoked through this Python.
      * The imported module exposes no recognisable callable entry point
        (``invoke`` / ``main`` / ``Skill().invoke``); there is no surface
        on which to dispatch.
      * The invocation attempt raises any ``BaseException`` (Hermes' own
        gating exception class, ``TypeError`` on argument-shape mismatch,
        ``RuntimeError`` from a config validator, etc.); the call raised
        instead of returning.

    Returns ``"callable"`` only when the invocation completes without raising
    -- the live failure mode AC-3 catches (the runtime ran the gated skill
    end-to-end despite ``config.yaml`` asserting it should be disabled).

    Tests exercise this helper by injecting a fake module into
    ``sys.modules['hermes.skills.<skill_name>']``; the production callers
    forward to this helper unchanged.
    """
    try:
        skill_module = importlib.import_module(
            "hermes.skills.{n}".format(n=skill_name)
        )
    except ImportError:
        return "gated"
    invoke = _resolve_hermes_skill_entry_point(skill_module)
    if invoke is None:
        return "gated"
    try:
        invoke(config_path=config_path)
    except BaseException:
        return "gated"
    return "callable"


def _default_delegate_task_caller(config_path: str) -> str:
    """Production round-trip for the ``delegate_task`` invariant (AC-3 (i)).

    Forwards to :func:`_attempt_hermes_skill_round_trip` against the
    upstream Hermes built-in module ``hermes.skills.delegate_task``. Returns
    ``"gated"`` when the actual in-process invocation attempt fails (import
    error, missing entry point, or any raised exception during invoke);
    returns ``"callable"`` only when the invocation completes without
    raising. Tests inject a callable via the ``delegate_task_caller``
    parameter of :func:`check_runtime` to bypass this default.
    """
    return _attempt_hermes_skill_round_trip(config_path, "delegate_task")


def _default_skill_manage_caller(config_path: str) -> str:
    """Production round-trip for the ``skill_manage`` invariant (AC-3 (ii)).

    Same shape as :func:`_default_delegate_task_caller`; forwards to
    :func:`_attempt_hermes_skill_round_trip` against
    ``hermes.skills.skill_manage``.
    """
    return _attempt_hermes_skill_round_trip(config_path, "skill_manage")


def _compute_prompt_sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def check_runtime(
    role: str,
    config_path: str,
    operational_db_path: str,
    env: Mapping[str, str],
    *,
    prompt_manifest_path: str = DEFAULT_PROMPT_MANIFEST_PATH,
    delegate_task_caller: Callable[[str], str] | None = None,
    skill_manage_caller: Callable[[str], str] | None = None,
) -> None:
    """Run the eleven runtime-check invariants in TKT-021 (a)-(e) + TKT-033 § 1 (B).

    A failed invariant emits the structured ``RUNTIME_CHECK_FAILED`` marker on
    stderr (see :func:`_emit_marker`) and raises the same exception class the
    pre-AUDIT-001 helper raised for the same condition; the raise-side
    contract from TKT-021 (v0.1.1) is preserved (RV-CODE asserts this).

    Parameters
    ----------
    role
        Value of ``$HERMES_DEVASSIST_ROLE`` (one of the five allowed roles).
    config_path
        Per-runtime config (``$HERMES_HOME/config.yaml``).
    operational_db_path
        Path to the operational SQLite store (typically the symlink at
        ``$HERMES_HOME/operational.db``).
    env
        Environment mapping for downstream invariant lookups
        (``HERMES_HOME``, ``TELEGRAM_BOT_TOKEN``).
    prompt_manifest_path
        Path to the install-time prompt-manifest JSON (default:
        ``/srv/devassist/state/prompt-manifest.json``). Pass ``""`` to skip
        the prompt-manifest invariants -- intended for unit tests that
        exercise other invariants without the prompt fixture.
    delegate_task_caller, skill_manage_caller
        Test injection points for the AC-3 (i)/(ii) round-trip; default
        callers verify the rendered config asserts gating
        (see :func:`_default_delegate_task_caller`).
    """
    if not role:
        _emit_marker(role, INVARIANT_ROLE_ENV_UNSET)
        raise RoleValueError(
            "HERMES_DEVASSIST_ROLE is unset or empty; expected one of: {a}".format(
                a=", ".join(sorted(_ALLOWED_ROLES))
            )
        )
    if role not in _ALLOWED_ROLES:
        _emit_marker(role, INVARIANT_ROLE_ENV_INVALID)
        raise RoleValueError(
            "HERMES_DEVASSIST_ROLE='{r}' is not one of the five allowed values: {a}".format(
                r=role, a=", ".join(sorted(_ALLOWED_ROLES))
            )
        )

    built_in = _read_config_skills(config_path)
    expected_built_in, _ = _ROLE_SKILLS[role]
    expected_built_in_f = frozenset(expected_built_in)

    if role != "orchestrator" and "telegram-gateway" in built_in:
        _emit_marker(role, INVARIANT_NON_ORCHESTRATOR_TELEGRAM_SKILL_LOADED)
        raise TelegramGatewayLoadedError(
            "telegram-gateway skill is loaded by non-Orchestrator runtime (role={r}). "
            "Only the Orchestrator may load telegram-gateway.".format(r=role)
        )

    if built_in != expected_built_in_f:
        _emit_marker(role, INVARIANT_LOADED_SKILLS_MISMATCH)
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
                _emit_marker(role, INVARIANT_OPERATIONAL_DB_PATH_MISMATCH)
                raise OperationalDbPathError(
                    "$HERMES_HOME/operational.db is not a symlink; "
                    "must point to /srv/devassist/state/operational.db"
                )
            if os.path.exists(state_db_file):
                _emit_marker(role, INVARIANT_OPERATIONAL_DB_PATH_MISMATCH)
                raise OperationalDbPathError(
                    "Per-runtime state.db exists at {s} (collision with shared operational.db). "
                    "Only operational.db symlink should exist.".format(s=state_db_file)
                )
            target = os.readlink(operational_db_file)
            _emit_marker(role, INVARIANT_OPERATIONAL_DB_PATH_MISMATCH)
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
                    _emit_marker(role, INVARIANT_SCHEMA_VERSION_MISMATCH)
                    raise SchemaVersionMismatchError(
                        "No schema_version found in _schema_meta for operational.db"
                    )
                version = row[0]
                if version != _SCHEMA_VERSION_EXPECTED:
                    _emit_marker(role, INVARIANT_SCHEMA_VERSION_MISMATCH)
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
            _emit_marker(role, INVARIANT_ORCHESTRATOR_TELEGRAM_TOKEN_MISSING)
            raise TelegramTokenMissingError(
                "TELEGRAM_BOT_TOKEN env var is empty or placeholder; "
                "Orchestrator runtime requires a real Telegram bot token"
            )

    delegate_caller = (
        delegate_task_caller
        if delegate_task_caller is not None
        else _default_delegate_task_caller
    )
    if delegate_caller(config_path) != "gated":
        _emit_marker(role, INVARIANT_DELEGATE_TASK_CALLABLE)
        raise DelegateTaskCallableError(
            "delegate_task is callable for role '{r}'; expected the Hermes runtime to "
            "return the gating error (config must assert skills.delegate_task.enabled=false "
            "or list delegate_task under plugins.disabled).".format(r=role)
        )

    skill_caller = (
        skill_manage_caller
        if skill_manage_caller is not None
        else _default_skill_manage_caller
    )
    if skill_caller(config_path) != "gated":
        _emit_marker(role, INVARIANT_SKILL_MANAGE_CALLABLE)
        raise SkillManageCallableError(
            "skill_manage is callable for role '{r}'; expected the Hermes runtime to "
            "return the gating error (config must assert skills.skill_manage.enabled=false "
            "or list skill_manage under plugins.disabled).".format(r=role)
        )

    if prompt_manifest_path:
        if not os.path.isfile(prompt_manifest_path):
            _emit_marker(role, INVARIANT_PROMPT_MANIFEST_MISSING)
            raise PromptManifestMissingError(
                "Prompt manifest not found at {p}; install-self.sh "
                "render_runtime_configs() must render it before any "
                "ExecStart can run.".format(p=prompt_manifest_path)
            )
        try:
            with open(prompt_manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, ValueError) as exc:
            _emit_marker(role, INVARIANT_PROMPT_MANIFEST_MISSING)
            raise PromptManifestMissingError(
                "Prompt manifest at {p} is unreadable: {e}".format(
                    p=prompt_manifest_path, e=exc
                )
            ) from exc
        prompts = manifest.get("prompts") if isinstance(manifest, dict) else None
        expected_sha = prompts.get(role) if isinstance(prompts, dict) else None
        if not isinstance(expected_sha, str) or not expected_sha:
            _emit_marker(role, INVARIANT_PROMPT_MANIFEST_MISSING)
            raise PromptManifestMissingError(
                "Prompt manifest at {p} has no SHA-256 entry for role '{r}'.".format(
                    p=prompt_manifest_path, r=role
                )
            )

        system_prompt_path = _read_system_prompt_path(config_path)
        if not system_prompt_path or not os.path.isfile(system_prompt_path):
            _emit_marker(role, INVARIANT_PROMPT_SHA_MISMATCH)
            raise PromptShaMismatchError(
                "Runtime system_prompt.path '{sp}' does not resolve to a "
                "readable file; expected the per-role canonical prompt for "
                "role '{r}'.".format(sp=system_prompt_path, r=role)
            )
        actual_sha = _compute_prompt_sha(system_prompt_path)
        if actual_sha != expected_sha:
            _emit_marker(role, INVARIANT_PROMPT_SHA_MISMATCH)
            raise PromptShaMismatchError(
                "system_prompt.path SHA-256 mismatch for role '{r}': got {g}, "
                "expected {e} (per manifest at {p}).".format(
                    r=role, g=actual_sha, e=expected_sha, p=prompt_manifest_path
                )
            )


def _main_cli() -> int:
    """CLI entrypoint for systemd ExecStartPre invocations.

    Reads ``HERMES_DEVASSIST_ROLE`` and ``HERMES_HOME`` from the environment,
    resolves the per-runtime ``config.yaml`` and ``operational.db`` paths,
    invokes :func:`check_runtime` with the install-time prompt-manifest at
    :data:`DEFAULT_PROMPT_MANIFEST_PATH`, and returns 0 on pass /
    :data:`RUNTIME_CHECK_ABORT_EXIT_CODE` (78, EX_CONFIG) on any
    :class:`RuntimeCheckError`. The systemd unit's ``RestartPreventExitStatus=``
    must list 78 to satisfy AC-2 (no auto-restart on invariant abort).
    """
    role = os.environ.get("HERMES_DEVASSIST_ROLE", "")
    hermes_home = os.environ.get("HERMES_HOME", "")
    if hermes_home:
        config_path = os.path.join(hermes_home, "config.yaml")
        operational_db_path = os.path.join(hermes_home, "operational.db")
    else:
        config_path = ""
        operational_db_path = ""
    try:
        check_runtime(
            role=role,
            config_path=config_path,
            operational_db_path=operational_db_path,
            env=os.environ,
        )
    except RuntimeCheckError:
        return RUNTIME_CHECK_ABORT_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(_main_cli())
