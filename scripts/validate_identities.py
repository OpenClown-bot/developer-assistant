#!/usr/bin/env python3
"""Validate git author/committer/co-author identities and commit-message PII.

This script enforces the repository's Identity Policy documented in
`CONTRIBUTING.md` § Identity policy. It runs in two modes:

1. **CI mode (default in GitHub Actions):** Compares HEAD against the merge-base
   with the configured base branch (`GITHUB_BASE_REF` env var or `--base` flag)
   and checks every commit introduced by the branch.
2. **Local pre-commit mode (`--pre-commit`):** Validates only the staged commit
   metadata (current `git config user.name` / `user.email`) without inspecting
   history. Used by `.pre-commit-config.yaml` to block bad commits early.

The script exits 0 on success, 1 on any violation, with a human-readable error
report enumerating every offending commit and what was wrong with it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Whitelist — only these identities are permitted as commit author, committer,
# or in `Co-authored-by:` trailers. Names are matched case-insensitively;
# emails must match exactly (after lower-casing).
# ---------------------------------------------------------------------------

WHITELIST: list[tuple[str, str]] = [
    ("OpenClown-bot", "bot@openclown-bot.dev"),
    ("Devin AI", "158243242+devin-ai-integration[bot]@users.noreply.github.com"),
    (
        "devin-ai-integration[bot]",
        "158243242+devin-ai-integration[bot]@users.noreply.github.com",
    ),
    ("GitHub", "noreply@github.com"),
    (
        "Strategic Orchestrator",
        "strategic-orchestrator@developer-assistant.local",
    ),
    ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"),
]

WHITELIST_EMAILS = {email.lower() for _name, email in WHITELIST}
WHITELIST_PAIRS = {(name.lower(), email.lower()) for name, email in WHITELIST}

# ---------------------------------------------------------------------------
# PII patterns forbidden in commit message bodies. These are NOT identities
# (those are caught by the whitelist check); these are textual leaks of session
# IDs, vendor URLs, and personal handles that may appear in attestation prose
# or stray Co-author lines that slipped through.
# ---------------------------------------------------------------------------

PII_PATTERNS: list[tuple[str, str]] = [
    # Devin session identifiers (hex blob after `devin-`). Word `devin` itself
    # is allowed; only the specific 8+ hex identifier portion is forbidden.
    (r"devin-[a-f0-9]{8,}", "Devin session identifier"),
    # Devin session URLs (template with real ID).
    (r"app\.devin\.ai/sessions/[A-Za-z0-9_-]+", "Devin session URL"),
    # Personal email domains seen historically in this repo. Whitelist emails
    # explicitly use `@users.noreply.github.com`, `@github.com`, or
    # `@developer-assistant.local`; any other domain in a commit message body
    # is treated as PII.
    (
        r"\b[A-Za-z0-9._%+-]+@(?:yandex\.ru|pinmx\.net|hotmail\.com|outlook\.com|gmail\.com|yahoo\.com|mail\.ru)",
        "Personal email address",
    ),
]

COAUTH_RE = re.compile(r"(?i)^\s*co-authored-by:\s*(.+?)\s*<(.+?)>\s*$")

# ---------------------------------------------------------------------------


@dataclass
class Violation:
    commit: str
    kind: str  # author | committer | coauth | pii
    detail: str


def run(*args: str) -> str:
    return subprocess.check_output(list(args), text=True).strip()


def identity_allowed(name: str, email: str) -> bool:
    """Return True iff the (name, email) pair matches a whitelist entry.

    Both fields are compared case-insensitively. Email-only matches are
    insufficient — a commit must use BOTH a whitelisted name AND its paired
    whitelisted email. This prevents the trivial bypass of authoring a commit
    as `personal_handle <bot@openclown-bot.dev>` (whitelisted email + non-
    whitelisted name).
    """
    return (name.lower(), email.lower()) in WHITELIST_PAIRS


def email_in_whitelist(email: str) -> bool:
    """Return True iff the email alone is in the whitelist (no name check).

    Used by the PII regex pass to exclude defensively any whitelist email
    that the personal-email-domain pattern might match incidentally.
    """
    return email.lower() in WHITELIST_EMAILS


def check_commit(sha: str, body: str) -> list[Violation]:
    violations: list[Violation] = []

    author_name = run("git", "log", "-1", "--format=%aN", sha)
    author_email = run("git", "log", "-1", "--format=%aE", sha)
    committer_name = run("git", "log", "-1", "--format=%cN", sha)
    committer_email = run("git", "log", "-1", "--format=%cE", sha)

    if not identity_allowed(author_name, author_email):
        violations.append(
            Violation(
                sha,
                "author",
                f"author {author_name!r} <{author_email}> not in whitelist",
            )
        )
    if not identity_allowed(committer_name, committer_email):
        violations.append(
            Violation(
                sha,
                "committer",
                f"committer {committer_name!r} <{committer_email}> not in whitelist",
            )
        )

    for line in body.splitlines():
        m = COAUTH_RE.match(line)
        if m:
            name, email = m.group(1), m.group(2)
            if not identity_allowed(name, email):
                violations.append(
                    Violation(
                        sha,
                        "coauth",
                        f"Co-authored-by {name!r} <{email}> not in whitelist",
                    )
                )

    for pat, label in PII_PATTERNS:
        for m in re.finditer(pat, body, flags=re.IGNORECASE):
            # Exclude legitimate whitelist emails that the regex may match
            # incidentally (it should not, but be defensive).
            matched = m.group(0)
            if "@" in matched and email_in_whitelist(matched):
                continue
            violations.append(
                Violation(sha, "pii", f"{label}: {matched!r}")
            )

    return violations


def commits_to_check(base: str) -> list[str]:
    """Return list of SHAs introduced by HEAD relative to base."""

    try:
        merge_base = run("git", "merge-base", base, "HEAD")
    except subprocess.CalledProcessError:
        # No common ancestor (e.g. brand-new orphan branch). Check HEAD only.
        return [run("git", "rev-parse", "HEAD")]

    return run("git", "rev-list", f"{merge_base}..HEAD").splitlines() or [
        run("git", "rev-parse", "HEAD")
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default=os.environ.get("GITHUB_BASE_REF", "main"),
        help="Base branch to diff against (default: $GITHUB_BASE_REF or 'main').",
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Validate the staged commit identity only (used by pre-commit hook).",
    )
    args = parser.parse_args()

    if args.pre_commit:
        name = run("git", "config", "--get", "user.name")
        email = run("git", "config", "--get", "user.email")
        if not identity_allowed(name, email):
            print(
                f"identity-check: refusing to commit — local git identity "
                f"{name!r} <{email}> is not in the whitelist. "
                "Set: git config user.name 'OpenClown-bot'; "
                "git config user.email 'bot@openclown-bot.dev'.",
                file=sys.stderr,
            )
            return 1
        return 0

    base = args.base
    # Resolve `origin/<branch>` form for CI runners.
    try:
        run("git", "rev-parse", base)
    except subprocess.CalledProcessError:
        base = f"origin/{base}"

    shas = commits_to_check(base)
    if not shas:
        print("identity-check: no commits to check against base.")
        return 0

    print(f"identity-check: checking {len(shas)} commit(s) against {base}.")

    all_violations: list[Violation] = []
    for sha in shas:
        body = run("git", "log", "-1", "--format=%B", sha)
        all_violations.extend(check_commit(sha, body))

    if not all_violations:
        print("identity-check: PASS — all commits authored by whitelisted identities, no PII in commit messages.")
        return 0

    print(f"identity-check: FAIL — {len(all_violations)} violation(s) found.\n", file=sys.stderr)
    by_commit: dict[str, list[Violation]] = {}
    for v in all_violations:
        by_commit.setdefault(v.commit, []).append(v)
    for sha, vs in by_commit.items():
        subject = run("git", "log", "-1", "--format=%s", sha)
        print(f"  commit {sha[:12]}  {subject}", file=sys.stderr)
        for v in vs:
            print(f"    [{v.kind}] {v.detail}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "See CONTRIBUTING.md § Identity policy. Whitelisted identities are listed in "
        "scripts/validate_identities.py WHITELIST.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
