"""MCP-name skill exclusion at skill-loader init time.

Implements TKT-040 AC-3 + AC-4: a defensive check at the
`dev-assist-work-queue` plugin's `register(hooks)` init path that
rejects any registered skill whose name or on-disk path matches the
MCP exclusion pattern, BEFORE the skill content is loaded into the
runtime's static context.

Per `MULTI-HERMES-CONTRACT.md` § 5.0.1 (added by this same TKT-040
implementation pass), the rule is:

  - Skill names starting with the literal `mcp:` prefix are excluded.
  - Skill names starting with the literal `mcp/` prefix are excluded.
  - Skill on-disk paths containing the `/mcp/` path segment are excluded.

Per TKT-040 § 8 Hard Rule 4, the match is path-segment / prefix-strict;
substring `mcp` is NOT a match. This means future legitimate skills
such as a hypothetical `dev-assist-mcp-bridge` are explicitly NOT
rejected — that case is one of the AC-5 unit tests.

Per TKT-040 § 8 Hard Rule 2, this is forward-only defensive: nothing
in the v0.1 allowlist (`MULTI-HERMES-CONTRACT.md` § 5.0) currently
matches, and no MCP-named skill is enabled. Verified at AC-7 by grep
of the contract.

Per `MULTI-HERMES-CONTRACT.md` § 5.0.1 last sentence and
`OBSERVABILITY-CONTRACT.md` § 4, each rejection emits a structured
journald-compatible log entry with `event: skill_loader.mcp_exclusion`.

Public surface:

  - ``is_mcp_excluded(skill_name, skill_path=None) -> bool``
  - ``filter_skills(skills, *, logger=None) -> list``

Both are pure-ish (no I/O beyond the logger emission) and used both
by the plugin's `register(hooks)` integration and by the AC-5 unit
tests in `tests/test_skill_loader_mcp_exclusion.py`.

The functions are exported through the plugin's `register(hooks)`
function in `tools.py` as
``hooks["skill_loader"] = {"is_excluded": is_mcp_excluded, "filter": filter_skills}``,
mirroring the hook-dict shape used by `dev_assist_escalation_policy`'s
``hooks["pre_tool_call"]`` integration so a single Hermes runtime can
discover and call into the loader extension at init time.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional


def is_mcp_excluded(skill_name: str, skill_path: Optional[str] = None) -> bool:
    """Return True iff the skill is excluded by the MCP rule.

    Path-segment / prefix-strict per TKT-040 § 8 Hard Rule 4:

    - ``mcp:foo`` -> excluded (prefix match on ``mcp:``)
    - ``mcp/bar`` -> excluded (prefix match on ``mcp/``)
    - any path containing the ``/mcp/`` segment -> excluded
    - ``dev-assist-mcp-bridge`` -> NOT excluded (substring; not a match)
    - ``mcphelper`` -> NOT excluded (no separator after ``mcp``)
    - ``dev-assist-classifier`` -> NOT excluded (control case)

    Args:
        skill_name: The skill's registered name (e.g. ``"dev-assist-classifier"``).
        skill_path: Optional on-disk path to the skill content
            (e.g. ``"/srv/devassist/shared-skills/mcp/foo/SKILL.md"``).

    Returns:
        True if the skill is MCP-excluded and must be rejected at
        loader init time before any content is read.
    """
    if not isinstance(skill_name, str):
        return False
    if skill_name.startswith("mcp:"):
        return True
    if skill_name.startswith("mcp/"):
        return True
    if skill_path and isinstance(skill_path, str) and "/mcp/" in skill_path:
        return True
    return False


def _emit_rejection_log(
    skill_name: str, skill_path: Optional[str], logger: Any
) -> None:
    """Emit a structured journald-compatible rejection log entry.

    Uses the project's structured_logger if a logger is not provided,
    so the entry conforms to OBSERVABILITY-CONTRACT.md § 4. The log
    payload matches the contract field shape:

    ``event: skill_loader.mcp_exclusion``
    ``message: rejected MCP-named skill at loader init``
    ``_extra_payload: {skill_name, skill_path, rule}``

    The function is fail-open: an exception during log emission must
    not prevent the rejection itself.
    """
    payload = {
        "skill_name": skill_name,
        "skill_path": skill_path,
        "rule": "mcp:* / mcp/* / /mcp/ path-segment exclusion (MULTI-HERMES-CONTRACT.md § 5.0.1)",
    }
    try:
        if logger is None:
            from developer_assistant.observability.structured_logger import get_logger

            logger = get_logger("dev_assist_work_queue.skill_loader")
        logger.info(
            "rejected MCP-named skill at loader init",
            extra={
                "event": "skill_loader.mcp_exclusion",
                "_extra_payload": payload,
            },
        )
    except Exception:
        pass


def filter_skills(
    skills: Iterable[Mapping[str, Any]],
    *,
    logger: Any = None,
) -> list[Mapping[str, Any]]:
    """Return the subset of ``skills`` not matching the MCP exclusion.

    Each rejection emits a structured log entry per
    ``OBSERVABILITY-CONTRACT.md`` § 4 so the rejection is visible in
    journald and the SQLite observability store.

    Args:
        skills: Iterable of skill descriptors. Each descriptor must
            be a mapping with at least a ``"name"`` key; an optional
            ``"path"`` key triggers the path-segment rule.
        logger: Optional logger override for testability. When
            omitted, the project's structured logger is used.

    Returns:
        A new list containing only the descriptors that survived
        the exclusion check. Order is preserved.
    """
    accepted: list[Mapping[str, Any]] = []
    for descriptor in skills:
        name = descriptor.get("name", "") if isinstance(descriptor, Mapping) else ""
        path = descriptor.get("path") if isinstance(descriptor, Mapping) else None
        if is_mcp_excluded(name, path):
            _emit_rejection_log(name, path, logger)
            continue
        accepted.append(descriptor)
    return accepted


__all__ = ["is_mcp_excluded", "filter_skills"]
