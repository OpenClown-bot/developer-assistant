"""Measure per-role static context budget (prompt + custom skills + plugins).

Implements TKT-040 AC-2: produce a deterministic JSON report of the
static context cost of each Hermes runtime role's prompt + custom
skill loadout + plugin source code, using the same tokenizer Hermes
uses (cl100k_base via tiktoken if available, deterministic stdlib
fallback otherwise).

Output is a single JSON object on stdout with sorted keys; running
the script twice on the same tree must produce byte-identical output
(determinism is part of TKT-040 § 6 Test Strategy).

Per TKT-040 § 8 Hard Rule 1, this script does NOT add any new pip
dependencies. tiktoken is used opportunistically when already
present in the runtime environment; the stdlib fallback is a
deterministic chars-per-token estimator (~4 chars/token for English
markdown, accurate to ±15%; see methodology in
`docs/architecture/role-context-budgets.md`).

Per TKT-040 § 8 Hard Rule 3, all reported numbers are mechanically
derived from on-disk file content; nothing is estimated from line
or character counts at the role level.

Usage:
    python3 scripts/measure_role_context.py
    python3 scripts/measure_role_context.py --markdown > /tmp/report.md
    python3 scripts/measure_role_context.py --check-deterministic
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


ROLE_LOADOUT = {
    "orchestrator": {
        "prompt_path": "docs/prompts/runtime-hermes-orchestrator.md",
        "custom_skill_names": [
            "dev-assist-classifier",
            "dev-assist-progress-report",
            "dev-assist-escalation-surface",
            "dev-assist-work-queue-write",
        ],
        "plugin_packages": [
            "src/developer_assistant/hermes_plugins/dev_assist_escalation_policy",
            "src/developer_assistant/hermes_plugins/dev_assist_work_queue",
        ],
        "hermes_builtin_skills_external": [
            "telegram-gateway",
            "cronjob",
            "memory",
        ],
    },
    "planner": {
        "prompt_path": "docs/prompts/business-planner.md",
        "custom_skill_names": [
            "dev-assist-prd-writer",
            "dev-assist-questions-writer",
            "dev-assist-work-queue-poll",
        ],
        "plugin_packages": [
            "src/developer_assistant/hermes_plugins/dev_assist_escalation_policy",
            "src/developer_assistant/hermes_plugins/dev_assist_work_queue",
        ],
        "hermes_builtin_skills_external": [
            "cronjob",
            "memory",
        ],
    },
    "architect": {
        "prompt_path": "docs/prompts/architect.md",
        "custom_skill_names": [
            "dev-assist-arch-writer",
            "dev-assist-adr-writer",
            "dev-assist-tickets-writer",
            "dev-assist-work-queue-poll",
        ],
        "plugin_packages": [
            "src/developer_assistant/hermes_plugins/dev_assist_escalation_policy",
            "src/developer_assistant/hermes_plugins/dev_assist_work_queue",
        ],
        "hermes_builtin_skills_external": [
            "cronjob",
            "memory",
        ],
    },
    "executor": {
        "prompt_path": "docs/prompts/executor.md",
        "custom_skill_names": [
            "dev-assist-executor-discipline",
            "dev-assist-write-zone-enforcer",
            "dev-assist-github-workflow",
            "dev-assist-work-queue-poll",
        ],
        "plugin_packages": [
            "src/developer_assistant/hermes_plugins/dev_assist_escalation_policy",
            "src/developer_assistant/hermes_plugins/dev_assist_work_queue",
        ],
        "hermes_builtin_skills_external": [
            "terminal",
            "cronjob",
            "memory",
        ],
    },
    "reviewer": {
        "prompt_path": "docs/prompts/reviewer.md",
        "custom_skill_names": [
            "dev-assist-reviewer-rubric",
            "dev-assist-review-writer",
            "dev-assist-work-queue-poll",
        ],
        "plugin_packages": [
            "src/developer_assistant/hermes_plugins/dev_assist_escalation_policy",
            "src/developer_assistant/hermes_plugins/dev_assist_work_queue",
        ],
        "hermes_builtin_skills_external": [
            "terminal",
            "cronjob",
            "memory",
        ],
    },
}

ROLE_ORDER = ["orchestrator", "planner", "architect", "executor", "reviewer"]


def select_tokenizer():
    """Return (encoder, name, path, variance_note).

    Preferred path: tiktoken cl100k_base (matches OpenAI / Anthropic /
    Hermes-style tokenization closely enough for budget tracking).
    Fallback path: deterministic stdlib chars-per-token estimator.
    """
    try:
        import tiktoken
    except ImportError:
        return (
            None,
            "cl100k_base_chars_per_token_fallback",
            "stdlib_fallback",
            "approx +/-15% for English markdown",
        )
    try:
        encoder = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return (
            None,
            "cl100k_base_chars_per_token_fallback",
            "stdlib_fallback",
            "approx +/-15% for English markdown",
        )
    return (encoder, "cl100k_base", "tiktoken", None)


def count_tokens(text: str, encoder) -> int:
    if encoder is None:
        return max(1, math.ceil(len(text) / 4)) if text else 0
    return len(encoder.encode(text))


def measure_file(path: Path, encoder) -> int:
    if not path.is_file():
        return 0
    return count_tokens(path.read_text(encoding="utf-8"), encoder)


def collect_python_sources(package_dir: Path) -> list[Path]:
    if not package_dir.is_dir():
        return []
    return sorted(p for p in package_dir.rglob("*.py") if "__pycache__" not in p.parts)


def measure_plugin_package(package_dir: Path, encoder) -> tuple[int, list[str]]:
    sources = collect_python_sources(package_dir)
    total = 0
    rel_paths: list[str] = []
    for src in sources:
        total += count_tokens(src.read_text(encoding="utf-8"), encoder)
        rel_paths.append(str(src.relative_to(ROOT)))
    return total, rel_paths


def collect_custom_skill_files(skill_name: str) -> list[Path]:
    candidates: list[Path] = []
    base = ROOT / "docs" / "architecture" / "shared-skills" / skill_name
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if p.is_file():
                candidates.append(p)
    runtime_base = ROOT / "shared-skills" / skill_name
    if runtime_base.is_dir():
        for p in sorted(runtime_base.rglob("*")):
            if p.is_file():
                candidates.append(p)
    return candidates


def measure_custom_skill(skill_name: str, encoder) -> dict:
    files = collect_custom_skill_files(skill_name)
    if not files:
        return {
            "name": skill_name,
            "expected_path_root": f"docs/architecture/shared-skills/{skill_name}/",
            "tokens": 0,
            "status": "not_on_disk",
            "files_measured": [],
        }
    total = 0
    rel = []
    for f in files:
        total += count_tokens(f.read_text(encoding="utf-8"), encoder)
        rel.append(str(f.relative_to(ROOT)))
    return {
        "name": skill_name,
        "expected_path_root": f"docs/architecture/shared-skills/{skill_name}/",
        "tokens": total,
        "status": "measured",
        "files_measured": rel,
    }


def measure_role(role: str, encoder) -> dict:
    cfg = ROLE_LOADOUT[role]
    prompt_path = ROOT / cfg["prompt_path"]
    prompt_tokens = measure_file(prompt_path, encoder)

    custom_skills = []
    custom_skills_total = 0
    not_on_disk: list[str] = []
    for name in cfg["custom_skill_names"]:
        result = measure_custom_skill(name, encoder)
        custom_skills.append(result)
        custom_skills_total += result["tokens"]
        if result["status"] == "not_on_disk":
            not_on_disk.append(name)

    plugins = []
    plugins_total = 0
    for pkg_rel in cfg["plugin_packages"]:
        pkg_dir = ROOT / pkg_rel
        tokens, sources = measure_plugin_package(pkg_dir, encoder)
        plugins.append(
            {
                "name": pkg_dir.name.replace("_", "-"),
                "package_path": pkg_rel,
                "tokens": tokens,
                "files_measured": sources,
            }
        )
        plugins_total += tokens

    notes = [
        "external_to_repo: "
        + ", ".join(cfg["hermes_builtin_skills_external"])
        + " (Hermes built-in, skipped — not present in this repo)",
    ]
    if not_on_disk:
        notes.append(
            "custom_skills_not_on_disk: "
            + ", ".join(not_on_disk)
            + " (TKT-021 / TKT-025 will populate `docs/architecture/shared-skills/dev-assist-*/SKILL.md`)"
        )

    total = prompt_tokens + custom_skills_total + plugins_total
    return {
        "prompt_path": cfg["prompt_path"],
        "prompt_tokens": prompt_tokens,
        "custom_skills": custom_skills,
        "custom_skills_tokens": custom_skills_total,
        "plugins": plugins,
        "plugins_tokens": plugins_total,
        "total_tokens": total,
        "notes": notes,
    }


def round_k(n: int) -> str:
    """Render token counts as Xk with one decimal for readability."""
    if n < 1000:
        return f"{n / 1000:.2f}k"
    return f"{n / 1000:.1f}k"


def render_markdown_table(report: dict) -> str:
    tok_name = report["tokenizer"]
    lines = [
        f"| Role | Prompt | Custom skills (in-repo) | Plugins | Total |",
        f"| --- | --- | --- | --- | --- |",
    ]
    for role in ROLE_ORDER:
        r = report["roles"][role]
        lines.append(
            f"| {role} "
            f"| {r['prompt_tokens']} ({round_k(r['prompt_tokens'])}) "
            f"| {r['custom_skills_tokens']} ({round_k(r['custom_skills_tokens'])}) "
            f"| {r['plugins_tokens']} ({round_k(r['plugins_tokens'])}) "
            f"| {r['total_tokens']} ({round_k(r['total_tokens'])}) |"
        )
    lines.append("")
    lines.append(f"Tokenizer: `{tok_name}` (path: `{report['tokenizer_path']}`).")
    if report.get("fallback_variance_estimate"):
        lines.append(f"Fallback variance: {report['fallback_variance_estimate']}.")
    return "\n".join(lines)


def build_report() -> dict:
    encoder, tokenizer_name, tokenizer_path, variance = select_tokenizer()
    roles: dict[str, dict] = {}
    for role in ROLE_ORDER:
        roles[role] = measure_role(role, encoder)
    return {
        "tokenizer": tokenizer_name,
        "tokenizer_path": tokenizer_path,
        "fallback_variance_estimate": variance,
        "reproduce_command": "python3 scripts/measure_role_context.py",
        "roles": roles,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Emit a markdown table on stdout instead of JSON.",
    )
    parser.add_argument(
        "--check-deterministic",
        action="store_true",
        help="Run the measurement twice and exit non-zero if outputs differ.",
    )
    args = parser.parse_args(argv)

    report = build_report()

    if args.check_deterministic:
        first = json.dumps(report, indent=2, sort_keys=True)
        second = json.dumps(build_report(), indent=2, sort_keys=True)
        if first != second:
            print("DETERMINISM FAIL: two consecutive runs produced different output", file=sys.stderr)
            return 2
        print("Deterministic: OK (two consecutive runs produced byte-identical output).")
        return 0

    if args.markdown:
        print(render_markdown_table(report))
        return 0

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
