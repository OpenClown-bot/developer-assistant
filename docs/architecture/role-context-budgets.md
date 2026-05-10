---
id: ROLE-CONTEXT-BUDGETS
version: 0.1.0
status: draft
updated: 2026-05-10
---

# Per-Role Static Context Budgets (v0.1)

## 1. Purpose

This document is the empirical reference table for the per-role
static context budget cited as one-line footers in
`MULTI-HERMES-CONTRACT.md` § 5.1–5.5. Numbers are mechanically
derived from `scripts/measure_role_context.py`; this file is the
human-readable rendering of the JSON report it emits.

The "static context" budget covers the load-once content each
runtime carries on every dispatch: the role's system prompt, the
in-repo custom `dev-assist-*` skill content, and the source of the
two custom Hermes plugins (`dev-assist-escalation-policy`,
`dev-assist-work-queue`) loaded by all five runtimes per
`MULTI-HERMES-CONTRACT.md` § 5.6.

It does **not** cover Hermes built-in skills (`telegram-gateway`,
`cronjob`, `memory`, `terminal`) — those live in the upstream
`hermes-agent` repo and are external to this project's measurement
surface; they are listed per-role under `notes` in the JSON report
so future readers know what is and isn't included.

## 2. Per-Role Table

Numbers below were captured at TKT-040 implementation time.

| Role | Prompt | Custom skills (in-repo) | Plugins | Total |
| --- | --- | --- | --- | --- |
| orchestrator | 1727 (1.7k) | 0 (0.00k) | 10191 (10.2k) | 11918 (11.9k) |
| planner | 659 (0.66k) | 0 (0.00k) | 10191 (10.2k) | 10850 (10.8k) |
| architect | 931 (0.93k) | 0 (0.00k) | 10191 (10.2k) | 11122 (11.1k) |
| executor | 1898 (1.9k) | 0 (0.00k) | 10191 (10.2k) | 12089 (12.1k) |
| reviewer | 1700 (1.7k) | 0 (0.00k) | 10191 (10.2k) | 11891 (11.9k) |

Tokenizer used at capture time: `cl100k_base_chars_per_token_fallback`
(stdlib fallback path; tiktoken was not importable in the measurement
environment).

## 3. Methodology

### 3.1 What is measured

For each of the five Hermes runtime roles defined in
`MULTI-HERMES-CONTRACT.md` § 5.1–5.5:

- **`prompt_tokens`** — token count of the role's system prompt file,
  read from `docs/prompts/<role>.md`. The Orchestrator runtime row
  uses `docs/prompts/runtime-hermes-orchestrator.md` (see § 4 below).
- **`custom_skills_tokens`** — token count of all files inside
  `docs/architecture/shared-skills/<skill-name>/` for each custom
  skill listed in the role's loadout table. Custom skill content is
  not yet on disk (TKT-021 / TKT-025 will populate the
  `shared-skills/dev-assist-*/SKILL.md` files); each missing skill
  is reported with `status: not_on_disk` and contributes zero tokens.
  The script auto-discovers any file content placed under that path
  in the future without code changes.
- **`plugins_tokens`** — token count of the Python source of every
  plugin loaded by that role per § 5.6. All five runtimes load both
  plugins, so `plugins_tokens` is identical across roles at the time
  of writing; the per-role accounting structure is preserved so a
  future role-asymmetric loadout (e.g., a Reviewer-only static
  analysis plugin) is captured automatically.
- **`total_tokens`** — `prompt_tokens + custom_skills_tokens + plugins_tokens`.

### 3.2 What is not measured

Hermes built-in skills (`telegram-gateway`, `cronjob`, `memory`,
`terminal`) are external to this repo and not measured. The JSON
report records them per role under `notes` as
`"external_to_repo: <name1>, <name2>, ... (Hermes built-in, skipped — not present in this repo)"`.
Operators tracking the actual deployed runtime context budget should
add the upstream tokenization of those skills to the totals reported
here.

`runtime-hermes-orchestrator.md` is the role prompt file used for
the Orchestrator measurement; the prompt loadout that is actually
wired into the deployed runtime via `agent.system_prompt_path` is the
same file (`SELF-DEPLOYMENT-CONTRACT.md` § 5.2).

### 3.3 Tokenizer choice

The script attempts `tiktoken.get_encoding("cl100k_base")` first.
This matches the tokenization shape used by OpenAI / Anthropic /
DeepSeek / Moonshot and most LLM-in-the-loop systems sufficiently
well for tracking budget growth in static context.

If `tiktoken` is not importable (e.g., on a fresh box without it
pre-installed), the script falls back to a deterministic stdlib
estimator: `tokens = max(1, ceil(len(text) / 4))` per file. The
~4 chars/token ratio is the cl100k_base average for English
markdown; the fallback is accurate to approximately ±15% for the
content categories measured here.

The JSON report records which path was taken via the `tokenizer`
field (`"cl100k_base"` for the tiktoken path,
`"cl100k_base_chars_per_token_fallback"` for the stdlib path) and
the `tokenizer_path` field (`"tiktoken"` or `"stdlib_fallback"`).
The `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 footers include a
`(tokenizer: <name>)` parenthetical so future readers can
distinguish fallback-derived numbers from native-tokenizer numbers
at a glance.

Per TKT-040 § 8 Hard Rule 1, no new pip dependency is added to the
project for tokenization; tiktoken is used opportunistically only.
Per TKT-040 § 7 risk note, the methodology choice is informational —
it does not enforce a budget cap; v0.1 documents the cap, it does
not refuse-to-load runs that exceed it.

### 3.4 Reproduce

```
python3 scripts/measure_role_context.py
python3 scripts/measure_role_context.py --markdown
python3 scripts/measure_role_context.py --check-deterministic
```

The default invocation prints sorted-keys JSON on stdout. Running
the script twice on the same tree must produce byte-identical
output; the `--check-deterministic` flag asserts this mechanically
and exits non-zero if it ever drifts (TKT-040 § 6 Test Strategy
self-validation).

## 4. Known Drift

### 4.1 Orchestrator role prompt path

`MULTI-HERMES-CONTRACT.md` § 2 line 27 references
`docs/prompts/orchestrator.md` for the Orchestrator runtime, but
that file does not exist in the repo at TKT-040 capture time. The
actual on-disk prompt file is `docs/prompts/runtime-hermes-orchestrator.md`,
which is the runtime persona prompt loaded by the deployed
Orchestrator runtime per `SELF-DEPLOYMENT-CONTRACT.md` § 5.2.

`scripts/measure_role_context.py` resolves the Orchestrator row to
`runtime-hermes-orchestrator.md` for measurement. Editing
MULTI-HERMES-CONTRACT.md § 2 is out of TKT-040 scope; this drift is
surfaced for a follow-up Architect cycle. No action required from
TKT-040 implementer.

### 4.2 Custom skill content

The 15 `dev-assist-*` custom skills enumerated in
`MULTI-HERMES-CONTRACT.md` § 5.0 are aspirational at v0.1 capture
time — none have an on-disk `SKILL.md` under
`docs/architecture/shared-skills/`. TKT-021 (skill source-review
batch) and TKT-025 (Orchestrator skill bundle) will populate them.
The measurement script picks up any content added to those paths
without code changes; this document's table will need a refresh
after each population pass.

## 5. Cross-References

- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.0.1 (MCP exclusion at load
  time) and § 5.1–5.5 (per-role loadout tables, each carrying the
  one-line context-budget footer derived from § 2 above).
- `ARCH-002-multi-agent-synthesis.md` § 3.5 (App-5) and § 6.3 (the
  amendment proposal that motivated TKT-040).
- `RESEARCH-002-multi-agent-dev-systems-survey.md` § 6.5 (OpenCastle
  context-management deep-dive — `opencastle@18c6f2cf4e5c:README.md:L110-L114`)
  and § 6.2 (ORCH MCP-name skip — `ORCH@0c0694896b3a:CLAUDE.md:L86-L93`).
- `ARCH-001.md` v0.3.0 § 21 (MCP HTTP servers exclusion baseline,
  cross-referenced from MULTI-HERMES-CONTRACT.md § 5.0.1).
- `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 2 (deny-by-default policy —
  the skill-loader exclusion is forward-only defensive, aligned with
  the existing posture).
- `TKT-040-skill-loadout-context-budget-mcp-exclusion.md` § 4
  (Acceptance Criteria) and § 8 Spec Amendment Notes (Hard Rules 1–4).
