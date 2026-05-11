# Contributing

This repository is managed through role-separated LLM delivery. The rules below exist to prevent scope drift, hidden state, and unreviewed changes.

## Roles

| Role | Default model | Runtime | Purpose | Allowed Write Zone |
| --- | --- | --- | --- | --- |
| Strategic Orchestrator | GPT-5.5 high (main) / DeepSeek V4 Pro (fallback) | opencode (Founder's Windows PC) | Session-level conductor: ticket selection, TO delegation, ratification audit pass-2, merge-safe sign-off, founder-facing teaching | `docs/session-log/`, `docs/meta/`, `docs/orchestration/`, `docs/backlog/` (light edits / new entries), ticket frontmatter promotions (`status`, `arch_ref`, `version`, `updated`) + `§10 Execution Log` append-only fills, `docs/questions/` (light edits / new questions), `.github/workflows/`, `.pr_agent.toml`, `CONTRIBUTING.md`, `AGENTS.md`, `README.md`, `docs/prompts/` (when adapting role prompts) |
| Ticket Orchestrator | GPT-5.5 high (main) / GLM 5.1 (fallback) | opencode (Founder's Windows PC) | Per-TKT cycle runner: drafts Executor + Reviewer NUDGE files, runs cross-reviewer audit pass-1, hands back to Strategic Orchestrator | Per-ticket clerical sub-PRs scoped to one TKT, frontmatter promotion of own TKT, BACKLOG entries scoped to own TKT, NUDGE files (Founder-pasted, generally not committed) |
| Runtime Hermes Orchestrator | runtime persona | Hermes Agent (deployed v0.1 product) | Live operator persona inside the deployed product (Telegram-facing, ContextBlock-driven, skill-allowlist-bound) | None in dev-time. Runtime-only. See `docs/prompts/runtime-hermes-orchestrator.md` |
| Business Planner | GPT-5.5 thinking / Claude Opus 4.7 thinking | ChatGPT Plus (web) | Clarifies product intent and MVP scope | `docs/prd/` |
| Architect | GPT-5.5 xhigh / GPT-5.5 thinking / Opus 4.6 thinking | Codex CLI / opencode CLI / Windsurf | Defines system architecture, ADRs, and implementation tickets | `docs/architecture/`, `docs/tickets/` |
| Code Executor | DeepSeek V4 Pro (main) / GLM 5.1 (fallback), Codex GPT-5.5 (specialist) | opencode + OmniRoute | Implements one approved ticket at a time | `src/`, `tests/`, explicitly allowed config files, and ticket Section 10 Execution Log only |
| Reviewer | Kimi K2.6 (main) / Qwen 3.6 Plus (fallback) | opencode + OmniRoute | Reviews PRs against ticket, architecture, ADRs, and CI | `docs/reviews/` |
| CI/Automation (incl. Qodo PR-Agent) | DeepSeek V4 Pro (PR-Agent) | GitHub Actions | Produces deterministic validation output and supplementary reviewer findings | generated reports or explicitly configured output paths |

If a role needs to modify files outside its write zone, it must stop and surface the rule violation instead of silently working around it.

**On the three orchestrator rows.** "Orchestrator" is intentionally split:
- **Strategic Orchestrator** is the dev-time session-level conductor (GPT-5.5 high in an opencode tab on the Founder's PC; DeepSeek V4 Pro as fallback model via opencode + OmniRoute). It is the partner the Ticket Orchestrator hands back to.
- **Ticket Orchestrator** is the dev-time per-TKT cycle runner (GPT-5.5 high in a separate opencode tab; GLM 5.1 as fallback model via opencode + OmniRoute). One TO session per TKT, never reused.
- **Runtime Hermes Orchestrator** is the in-product persona inside the deployed Hermes Agent runtime. It is NOT a dev-time pipeline role; it has no write-zone in this repo's dev-time process. Its prompt lives in `docs/prompts/runtime-hermes-orchestrator.md` to keep it next to the other prompts, but it is loaded by the runtime, not by dev-time agents.

The full SO portable system prompt lives in `docs/meta/strategic-orchestrator.md`. The TO portable system prompt lives in `docs/prompts/ticket-orchestrator.md`. Session-handoff snapshots between SO sessions live in `docs/session-log/` (auto-cold rule fires after every closed TKT cycle).

## Ticket Lifecycle

Tickets move through these states:

```text
draft -> ready -> in_progress -> in_review -> done
```

- `draft`: not ready for implementation.
- `ready`: approved for Executor.
- `in_progress`: Executor is working.
- `in_review`: PR is open and awaiting review.
- `done`: merged and verified.

Do not skip statuses unless the reason is documented in the ticket or orchestration state.

## PR Contract

Every meaningful implementation change must go through a PR. A PR must include:

- Linked ticket.
- Summary of changes.
- Acceptance criteria checklist status.
- Tests run.
- Known limitations.
- Risk notes, when relevant.

Executors must not expand scope beyond the ticket. If the implementation reveals missing scope, create or request a follow-up ticket.

## Review Gates

Before merge, every implementation PR requires:

1. Automated checks.
2. Reviewer LLM verdict in `docs/reviews/`.
3. Explicit user acknowledgement.

Allowed Reviewer verdicts:

- `pass`
- `pass_with_changes`
- `fail`

### Reviewer artifact naming convention

Reviewer artifacts in `docs/reviews/` use one of three prefixes that signal what was reviewed and the audit shape:

- **`RV-CODE-NNN.md`** — Reviews of **code-PR implementations**. The Reviewer audits the PR diff against the ticket's § 4 Acceptance Criteria, runs targeted tests, and triages CI / PR-Agent findings. This is the default form used for the vast majority of PRs (TKT-NNN implementation cycles).
- **`RV-SPEC-NNN.md`** — Reviews of **architecture-spec PRs** (Architect-authored spec / contract / ADR introductions or revisions). The Reviewer audits the spec change against the prior architecture baseline. Verdict shape includes scope-compliance and cross-reference integrity, not AC-against-code (specs have no implementation surface to test).
- **`RV-ARCH-NN.md`** — Reviews of **Architect-cycle clerical or amendment PRs** that touch only `docs/architecture/` (e.g. stale-ref corrections, ADR promotions `proposed → accepted`, append-only § 12 amendment-history entries). The Reviewer performs byte-equality and scope-compliance audits against an Architect-zone diff. No AC-against-code and no test runs — these are clerical-amendment cycles, not implementation cycles.

The numbering within each prefix is sequential and independent (`RV-CODE-001`..`RV-CODE-036`, `RV-SPEC-001`..`RV-SPEC-018`, `RV-ARCH-001`..). Early-era artifacts that predate this convention (e.g. `RV-023.md`) are preserved as-is for forensic continuity; new artifacts must use one of the three prefixes above.

### § 10 Execution Log attribution convention

Every entry in a ticket's `## 10. Execution Log` section MUST begin with a
header line that names exactly three things:

1. **Entry type and number** — `iter-N` (Executor implementation iteration),
   `review-N` (Reviewer review pass), `Closure amendment` (SO ratify or
   clerical post-merge update), or `Architect amendment` (Architect amendment
   landed in § 10).
2. **Date in ISO format** — `YYYY-MM-DD`, the date the entry was written or
   back-filled.
3. **Role of the writing agent** — exactly one of `Code Executor`,
   `Reviewer`, `Strategic Orchestrator`, or `Architect`.

Canonical header format:

```
### iter-N — DATE — Code Executor
### review-N — DATE — Reviewer
### Closure amendment — DATE — Strategic Orchestrator
### Architect amendment — DATE — Architect
```

Use em-dash `—` (U+2014), not hyphen-minus `-`. The body remains free-form
narrative; runtime, model family, branch, PR number, and commit SHAs belong
in the body, not the header.

**Personal information is not permitted in any § 10 entry or any other repo
artifact (including PR descriptions, PR comments, commit messages, and
review artifacts under `docs/reviews/`).** Personal information means: Devin
session identifiers (`devin-<hex>`), Devin session URLs
(`https://app.devin.ai/sessions/<id>`), email addresses, GitHub handles for
individual humans, local-machine usernames, or any similar account-level
identifier. Model family + runtime + host descriptors (`DeepSeek V4 Pro
main via opencode + OmniRoute on Founder PC`, `Anthropic Claude Sonnet 4.5
on Devin VM`) are NOT personal information and are permitted — but optional,
because model identity is not always reliably observable at write time.

**Redaction-when-citing rule.** When a review artifact
(`docs/reviews/RV-*-NNN.md`), an audit document, a session-log, a PR
description, a TKT prose section, or any committed text needs to *cite*
leaked personal information (e.g., to report a finding, document a
remediation, trace a violation, or describe a test fixture's negative
case), the citation MUST use redacted placeholders rather than reproducing
the verbatim value. Canonical placeholders:

- `<redacted-handle>` (single handle) or `<github-handle-A>`,
  `<github-handle-B>`, … (multiple identities in one artifact, labeled in
  order of first occurrence).
- `<redacted-email>` (single email) or `<email-A>`, `<email-B>`, …
  (multiple emails, paired with the corresponding `<github-handle-X>`).
- `<personal-domain>` for personal email domains when the domain itself is
  identifying.
- `<redacted-URL>` or `https://<host>/<redacted>/<repo-name>` when the
  identifier appears inside a URL.

Citing leaked PII verbatim — *even to flag that it is leaked* — perpetuates
the leak in the citing artifact and counts as a fresh violation of this
rule. If the verbatim value is required for downstream forensic
remediation (e.g., to construct a `.mailmap` entry, a `git-filter-repo`
script, or a `validate_identities.py` test fixture), it MUST be passed
through an out-of-repo channel (direct message to the Founder, paste-relay
between agent sessions) and never committed to the repository — including
as a synthetic-looking string in commit messages, test fixtures, or PR
comments.

**Back-filled entries** use the same header format with an explicit
provenance label:

```
### iter-N (SHA) — DATE — Code Executor [back-filled DATE — Strategic Orchestrator]
```

A back-filled entry MUST include a `**Provenance note.**` paragraph at the
top of the body distinguishing reconstruction from primary-source narrative.

**Pre-existing entries** were normalized to this convention in the
2026-05-10 F1 closure sweep PR. Future entries from convention adoption
forward must conform from creation.

### Identity policy

All commits in this repository MUST be authored by one of the
whitelisted identities listed in `scripts/validate_identities.py`. As of
2026-05-11 the whitelist is:

| Name | Email |
|---|---|
| `OpenClown-bot` | `bot@openclown-bot.dev` |
| `Devin AI` | `158243242+devin-ai-integration[bot]@users.noreply.github.com` |
| `devin-ai-integration[bot]` | `158243242+devin-ai-integration[bot]@users.noreply.github.com` |
| `GitHub` | `noreply@github.com` |
| `Strategic Orchestrator` | `strategic-orchestrator@developer-assistant.local` |
| `dependabot[bot]` | `49699333+dependabot[bot]@users.noreply.github.com` |

Personal GitHub handles, personal email addresses, local-machine
usernames, or any other non-whitelisted identity are forbidden in:

1. The `author` field of any commit.
2. The `committer` field of any commit (exception: `GitHub <noreply@github.com>`
   is the legitimate committer on web-merged PRs).
3. Any `Co-authored-by:` trailer in a commit message.

In addition, **commit message bodies MUST NOT contain** any of the
following PII patterns:

- Devin session identifiers (`devin-<hex>`, where `<hex>` is 8+
  hexadecimal characters). The word `devin` itself is allowed; only the
  specific hex-identifier portion is forbidden. Use `devin-[REDACTED]`
  in attestation prose if a placeholder is needed.
- Devin session URLs (`https://app.devin.ai/sessions/<id>`).
- Personal email addresses (any address with a non-whitelisted domain).

Model identity, runtime, and host descriptors (`Anthropic Claude Sonnet
4.5 on Devin VM`, `DeepSeek V4 Pro main via opencode + OmniRoute on
Founder PC`, etc.) are **NOT** PII and are permitted — but optional,
because model identity is not always reliably observable at write time.

**Configuring your local git identity.** Executors running on Devin or
any other automated runtime MUST configure their local git identity
before committing:

```
git config user.name "OpenClown-bot"
git config user.email "bot@openclown-bot.dev"
```

**Enforcement.** Three layers of enforcement guard this policy:

1. **CI:** `.github/workflows/identity-check.yml` runs
   `python scripts/validate_identities.py` on every PR and push to
   `main`. The job fails if any commit introduced by the branch (relative
   to the base) violates the whitelist or contains a PII pattern in its
   message body.
2. **Pre-commit hook (recommended for local development):**
   `.pre-commit-config.yaml` runs `validate_identities.py --pre-commit`
   on every commit, validating the local git identity before the commit
   object is created. Install once per clone with:
   `pre-commit install --hook-type pre-commit --hook-type commit-msg`.
3. **Reviewer gate:** Reviewers MUST refuse any PR whose
   `identity-check` CI job is failing, regardless of whether the change
   would otherwise pass review.

**Mailmap.** A repository-root `.mailmap` file defensively remaps every
historical pre-rewrite author email to the bot identity. This protects
against accidental resurfacing of old commits via cherry-pick or
backup-restore. The mailmap is consumed by `git log --use-mailmap`,
GitHub's UI rendering, and the identity-check CI.

**Why this policy exists.** The project's pre-2026-05-11 history
contained 15 distinct personal identifiers (email addresses and
GitHub-style handles) across author/committer fields and
`Co-authored-by:` trailers, plus Devin session identifiers in
attestation prose. The 2026-05-10 F1 closure cycle (PR #165 +
Phase 2 force-push) eliminated all of these from current state; this
policy prevents reintroduction. The companion ADR-019 documents the
v1.0 milestone migration that will eliminate the remaining
GitHub-side edit-history residue at project deployment time.

## CI Baseline

Minimum validation:

- `python scripts/validate_docs.py`
- Relevant tests when code exists.
- Lint/typecheck when configured.
- Static/security checks when configured.

## Versioning

Core artifacts use YAML frontmatter with semantic versions:

```yaml
---
id: ARCH-001
version: 0.1.0
status: draft
---
```

Architecture-changing version bumps require an ADR.

## Secrets

Never commit secrets, including GitHub PATs, LLM API keys, VPS SSH keys, `.env` files, private repository credentials, or service tokens.

## Recovery Playbook Discipline

If you change a CLI subcommand, systemd unit name, port assignment, SQLite table schema, or install/verify script name, update `docs/operations/RECOVERY-PLAYBOOK.md` in the same PR. The playbook is the authoritative operator surface and CI verifies it does not drift (TKT-030 harness: `tests/test_recovery_playbook_invariants.py`).
