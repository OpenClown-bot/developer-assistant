"""Per-runtime Hermes configuration rendering for developer-assistant multi-Hermes deployment.

This module produces rendered config.yaml, auth.json skeleton, and SOUL.md skeleton
for each of the five Hermes runtime roles: orchestrator, planner, architect, executor, reviewer.

No real tokens, PATs, or production hostnames appear in any rendered output.
All identifiers come from MODEL-CATALOG.md v0.1.1 § 4.1.

Templates are consumed from etc/runtime-templates/<role>/ as reference data files.
Rendering uses safe str.replace() to avoid format-string brace conflicts.
"""

from __future__ import annotations

import os
from typing import Mapping

_EXPECTED_SCHEMA_VERSION = "3"
_OMNIROUTE_BASE_URL = os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1")

_ALLOWED_ROLES = frozenset({"orchestrator", "planner", "architect", "executor", "reviewer"})
ALLOWED_ROLES = _ALLOWED_ROLES

_ROLE_MODEL_ASSIGNMENT: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "orchestrator": (
        "accounts/fireworks/models/minimax-m2p7",
        (
            "accounts/fireworks/models/kimi-k2p6",
            "accounts/fireworks/models/qwen3p6-plus",
            "accounts/fireworks/models/deepseek-v4-pro",
        ),
    ),
    "planner": (
        "accounts/fireworks/models/qwen3p6-plus",
        (
            "accounts/fireworks/models/kimi-k2p6",
            "accounts/fireworks/models/minimax-m2p7",
            "accounts/fireworks/models/deepseek-v4-pro",
        ),
    ),
    "architect": (
        "accounts/fireworks/models/deepseek-v4-pro",
        (
            "accounts/fireworks/models/kimi-k2p6",
            "accounts/fireworks/models/glm-5p1",
            "accounts/fireworks/models/qwen3p6-plus",
        ),
    ),
    "executor": (
        "accounts/fireworks/models/glm-5p1",
        (
            "accounts/fireworks/models/deepseek-v4-pro",
            "accounts/fireworks/models/kimi-k2p6",
            "accounts/fireworks/models/qwen3p6-plus",
        ),
    ),
    "reviewer": (
        "accounts/fireworks/models/kimi-k2p6",
        (
            "accounts/fireworks/models/deepseek-v4-pro",
            "accounts/fireworks/models/glm-5p1",
            "accounts/fireworks/models/qwen3p6-plus",
        ),
    ),
}

_ROLE_PROMPT_PATH: Mapping[str, str] = {
    "orchestrator": "docs/prompts/orchestrator.md",
    "planner": "docs/prompts/business_planner.md",
    "architect": "docs/prompts/architect.md",
    "executor": "docs/prompts/executor.md",
    "reviewer": "docs/prompts/reviewer.md",
}

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


def _load_template(role: str, filename: str) -> str:
    tmpl_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "etc",
        "runtime-templates",
        role,
    )
    tmpl_path = os.path.join(tmpl_dir, filename)
    with open(tmpl_path, encoding="utf-8") as fh:
        return fh.read()


def _render_config_yaml(
    role: str,
    secrets_env_path: str,
    state_db_path: str,
    repo_path: str,
    omniroute_base_url: str = _OMNIROUTE_BASE_URL,
) -> str:
    model_main, model_fallbacks = _ROLE_MODEL_ASSIGNMENT[role]
    built_in_skills, custom_skills = _ROLE_SKILLS[role]
    system_prompt_rel = _ROLE_PROMPT_PATH[role]
    prompt_file = os.path.basename(system_prompt_rel)

    built_in_lines = "\n".join("    - " + s for s in built_in_skills)

    terminal_block = ""
    if role in ("executor", "reviewer"):
        terminal_block = "\nterminal:\n  backend: docker"

    gateway_enabled = "true" if role == "orchestrator" else "false"

    tmpl = _load_template(role, "config.yaml.tmpl")
    return (
        tmpl.replace("{{role}}", role)
        .replace("{{repo_path}}", repo_path)
        .replace("{{prompt_file}}", prompt_file)
        .replace("{{model_main}}", model_main)
        .replace("{{fallback_1}}", model_fallbacks[0])
        .replace("{{fallback_2}}", model_fallbacks[1])
        .replace("{{fallback_3}}", model_fallbacks[2])
        .replace("{{omniroute_base_url}}", omniroute_base_url)
        .replace("{{built_in_skills}}", built_in_lines)
        .replace("{{terminal_block}}", terminal_block)
        .replace("{{gateway_enabled}}", gateway_enabled)
    )


def _render_auth_json(_role: str, _repo_path: str) -> str:
    return (
        '{\n'
        '  "telegram_bot_token": "",\n'
        '  "github_token": "",\n'
        '  "omniroute_api_key": ""\n'
        '}\n'
    )


def _render_soul_md(role: str, repo_path: str) -> str:
    system_prompt_rel = _ROLE_PROMPT_PATH[role]
    prompt_file = os.path.basename(system_prompt_rel)
    model_main, _ = _ROLE_MODEL_ASSIGNMENT[role]
    return (
        "# SOUL.md \u2014 {r} runtime\n\n"
        "Role: {r}\n"
        "Model: {m}\n"
        "Prompt: {p}\n"
        "Repo: {repo}\n"
    ).format(r=role, m=model_main, p=prompt_file, repo=repo_path)


def render_runtime_config(
    role: str,
    secrets_env_path: str,
    state_db_path: str,
    repo_path: str,
    omniroute_base_url: str = _OMNIROUTE_BASE_URL,
) -> dict[str, str]:
    """Render per-runtime Hermes configuration files.

    Args:
        role: One of 'orchestrator', 'planner', 'architect', 'executor', 'reviewer'.
        secrets_env_path: Path to the secrets env file (e.g., /srv/devassist/secrets/SELF-DEPLOY.env).
        state_db_path: Path to the shared operational store (e.g., /srv/devassist/state/operational.db).
        repo_path: Path to the repository checkout (e.g., /srv/devassist/repo).
        omniroute_base_url: OmniRoute base URL (default: http://127.0.0.1:20128/v1).

    Returns:
        A dict mapping filename to file content (e.g., 'config.yaml' -> '...yaml content...').

    Raises:
        ValueError: If role is not one of the five allowed values.
    """
    if role not in _ALLOWED_ROLES:
        raise ValueError(
            "Unknown role '{r}'. Allowed values: {a}".format(
                r=role, a=", ".join(sorted(_ALLOWED_ROLES))
            )
        )

    return {
        "config.yaml": _render_config_yaml(role, secrets_env_path, state_db_path, repo_path, omniroute_base_url),
        "auth.json": _render_auth_json(role, repo_path),
        "SOUL.md": _render_soul_md(role, repo_path),
    }


def get_role_skills(role: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (built_in_skills, custom_skills) for the given role."""
    if role not in _ALLOWED_ROLES:
        raise ValueError("Unknown role: {r}".format(r=role))
    return _ROLE_SKILLS[role]


def get_role_model_assignment(role: str) -> tuple[str, tuple[str, ...]]:
    """Return (main_model, fallback_models) for the given role."""
    if role not in _ALLOWED_ROLES:
        raise ValueError("Unknown role: {r}".format(r=role))
    return _ROLE_MODEL_ASSIGNMENT[role]