---
id: RV-ARCH-003
version: 0.1.0
status: complete
verdict: pass_with_changes
target_pr: 173
target_head_sha: 9d896fcf0ee3cfb70453cb2843a8eed9dd635f6b
reviewer_model: Kimi K2.6
reviewer_family: Moonshot
updated: 2026-05-12
---

# RV-ARCH-003: Review of PR #173 — OBSERVABILITY-CONTRACT v0.1.2 amendment (`loaded_skills` / `prompt_path` / `prompt_sha256`)

## 1. PR Meta

- **PR**: #173
- **Branch**: `arch/observability-contract-loaded-skills-amendment`
- **Head reviewed**: `9d896fcf0ee3cfb70453cb2843a8eed9dd635f6b`
- **Base**: `main@9482edb`
- **Files changed**: 1 (`docs/architecture/OBSERVABILITY-CONTRACT.md`)
- **Diff shape**: +33 / −2
- **Cycle type**: iter-1 FRESH
- **CI checked (local)**: `python3 scripts/validate_docs.py` — PASS (Docs validation passed.)
- **Commit identity**: `OpenClown-bot <bot@openclown-bot.dev>` author = committer — whitelisted per `CONTRIBUTING.md` § Identity policy WHITELIST_PAIRS.
- **Remote CI (`validate-docs` / `validate-identities` / `Run PR Agent`)**: **Not verified** — `gh` CLI not authenticated in this session; local `validate_docs.py` pass and commit-identity manual check are the only verifiable gates.

## 2. Substantive Checks

### 2.1 Contract-mirror fidelity to TKT-041 v0.1.1 § 4 AC-2 + AC-4 — **PASS**

| Field | Amendment spec | TKT-041 AC text | Match |
| --- | --- | --- | --- |
| `loaded_skills` | `list[str]` | AC-2: "`loaded_skills` field whose value is set-equal to the per-role expected set" | ✓ |
| Per-role expected values | Owned by `MULTI-HERMES-CONTRACT.md` § 5.1–5.5; amendment does NOT duplicate values | AC-2: "The implementer MUST NOT hard-code this table ... parses `MULTI-HERMES-CONTRACT.md` § 5.1–5.5" | ✓ |
| `prompt_path` | Resolved `agent.system_prompt_path` relative to `/srv/devassist/repo/` per `SELF-DEPLOYMENT-CONTRACT.md` § 5 | AC-4 (i), (iii): "the resolved `agent.system_prompt_path` ... MUST equal `docs/prompts/<role>.md` ... relative path under `/srv/devassist/repo/`" | ✓ |
| `prompt_sha256` | SHA-256 hex computed at request time (NOT cached at boot) | AC-4 (i), (ii): "SHA-256 hex of the file at the resolved path, computed at runtime each `/health` GET — NOT cached at runtime boot" | ✓ |
| Production-posture gate | Marker file `/srv/devassist/state/smoke-mode.flag` (mode `0400`) OR `?internal=1` query param | TKT-041 § 1.4 (1): "marker file ... mode `0400`, owner `devassist:devassist`"; § 5 Allowed Files note: "production-mode `/health` does NOT include ... unless ... `?internal=1`" | ✓ |

All semantics, types, gates, and source-of-truth cross-references match the AC text exactly.

### 2.2 Sibling-out boundary respect — **PASS**

Diff (`9482edb..9d896fcf`) confirms:
- Exactly 1 file changed: `docs/architecture/OBSERVABILITY-CONTRACT.md`
- Zero edits outside `docs/architecture/`
- `TKT-041-behaviour-level-deployment-smoke.md` untouched
- `ADR-010-observability-shape.md` untouched
- No implementation surface (`src/`, `tests/`, `scripts/` outside `install-self.sh`/`verify-self.sh` which are also untouched) touched

### 2.3 Backward-compatibility claim — **PASS**

The amendment claims existing `/health` consumers ignore unknown fields. I inspected the three cited consumer surfaces:
- **`dev-assist-cli status` (§ 6.1):** Documents an example JSON shape but does NOT specify a strict schema validator. The CLI reads from multiple sources (journald, SQLite, health endpoints); nothing in § 6.1 documents schema-strict parsing of the `/health` JSON. Tolerant/field-optional parsing is implied by the "best-effort" language used for `current_work_item_id` and `current_model`.
- **Daily-digest assembly (§ 8):** Assembles Markdown from `work_items`, `escalations`, `errors`, and `llm_calls` SQLite tables + `uptime` command. It does NOT parse the `/health` JSON at all.
- **Telegram `/status` (§ 7):** Human-readable text summary formatted by the Orchestrator runtime. It does NOT parse `/health` JSON directly (it queries the same underlying data sources or calls the CLI).

No consumer is documented as schema-strict. The claim holds.

### 2.4 Gate-rationale soundness — **PARTIAL (Finding 2.1)**

- **Cited risk bullet:** TKT-041 v0.1.1 § 8 risk bullet 1 states: "`/health` JSON extension exposes loaded-skills enumeration on production endpoints (§ 4 AC-2). Loaded-skills enumeration leaks architecture details." This fully supports the gate rationale. ✓
- **Residual-risk cross-reference:** The amendment states: "mitigated at the VPS firewall layer per `SELF-DEPLOYMENT-CONTRACT.md` § 7."
  - **Problem:** `SELF-DEPLOYMENT-CONTRACT.md` § 7 is "State Preservation Across Rollback And Upgrade" — it contains zero discussion of network firewalls, port exposure, or packet filtering. The network-level sandboxing is documented in § 5.2 (systemd `ReadOnlyPaths`/`BindReadOnlyPaths`) and § 5.4 mentions `ufw` only to say a rule is **not** added by default. There is no "VPS firewall layer" section in `SELF-DEPLOYMENT-CONTRACT.md`.
  - This same erroneous cross-reference already existed in OBSERVABILITY-CONTRACT v0.1.1 § 11 line 341 ("The VPS firewall rules (`SELF-DEPLOYMENT-CONTRACT.md` § 7) ..."); the amendment perpetuates the error when adding the new residual-risk sentence in § 11.1 rather than correcting it.

### 2.5 Semver discipline — **PASS**

- Amendment bumps `version: 0.1.1 → 0.1.2`.
- Change is purely additive (three optional JSON fields) and backward-compatible (gated, absent by default in production).
- No existing field types changed, no required fields added, no fields removed. A v0.2.0 bump is therefore NOT required.
- `updated: 2026-05-11` matches the commit author date of `9d896fcf` (`2026-05-11 22:28:02 +0000`).

### 2.6 Cross-reference accuracy — **PASS**

- New § 15 entry: `` `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` v0.1.1 § 4 AC-2 + AC-4 `` — version string and section numbers are correct.
- All pre-existing § 15 entries are preserved unchanged.

### 2.7 Per-role example consistency — **PASS**

The § 11 JSON example uses:
- `prompt_path: "docs/prompts/runtime-hermes-orchestrator.md"` — matches `MULTI-HERMES-CONTRACT.md` § 2 table (Orchestrator → `docs/prompts/runtime-hermes-orchestrator.md`).
- `loaded_skills` list of 7 entries (`telegram-gateway`, `cronjob`, `memory`, `dev-assist-classifier`, `dev-assist-progress-report`, `dev-assist-escalation-surface`, `dev-assist-work-queue-write`) — exactly matches the union of Hermes built-in skills (3) + custom dev-assist skills (4) listed in `MULTI-HERMES-CONTRACT.md` § 5.1.

### 2.8 Secret/PII surface — **PASS**

- `build_commit`: placeholder `abcdef0` — not a real commit SHA.
- `prompt_sha256`: placeholder `0123abcd… (64 hex chars) …` — contains ellipsis, clearly synthetic.
- No `smoke-fixture-token-[a-z0-9]{8}` shape appears in the contract (correctly confined to TKT-041 itself).
- Manual `grep` for `ghp_`, `fw_`, `sk-`, `[0-9]+:[A-Za-z0-9_-]{35,}` on the diff returned zero matches.

### 2.9 CI artefacts — **PARTIALLY VERIFIED**

- Local `validate_docs.py` run: **PASS**.
- `validate-identities` and `Run PR Agent` on HEAD `9d896fcf`: **Not verifiable** in this session due to unauthenticated `gh` CLI. Commit identity (`OpenClown-bot <bot@openclown-bot.dev>`) is whitelisted. No CI configuration changes in the diff.

## 3. Findings

| ID | Severity | Cite | Recommendation |
|---|---|---|---|
| 2.1 | Informational | `docs/architecture/OBSERVABILITY-CONTRACT.md` § 11.1 residual-risk sentence: "mitigated at the VPS firewall layer per `SELF-DEPLOYMENT-CONTRACT.md` § 7" | `SELF-DEPLOYMENT-CONTRACT.md` § 7 is "State Preservation Across Rollback And Upgrade"; it does not cover firewalls or network exposure. Replace the cross-reference with `§ 5.2` (systemd sandboxing / bind-address posture) or `§ 5.4` (web surface port-bind note), or add an explicit firewall subsection to `SELF-DEPLOYMENT-CONTRACT.md` and cite that. Alternatively, since the same erroneous citation already exists in v0.1.1 § 11 line 341, fix both occurrences in the same clerical pass. |

## 4. Security Notes

- No new credentials, tokens, or PII introduced.
- No real `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, or `FIREWORKS_API_KEY` shapes present.
- Placeholder tokens (`abcdef0`, `0123abcd…`) are clearly synthetic.
- The production-posture gate (marker file + query param) correctly prevents architecture-detail leakage on the default `/health` surface.

## 5. Acceptance Criteria Assessment

This is a spec-amendment PR; there are no implementation ACs. The amendment's own internal quality criteria (from the substantive checks above) are all satisfied except the one Informational cross-reference inaccuracy documented in Finding 2.1.

## 6. Final Verdict

**`pass_with_changes`**

- **High:** 0
- **Medium:** 0
- **Informational:** 1 (Finding 2.1 — `SELF-DEPLOYMENT-CONTRACT.md` § 7 firewall cross-reference mismatch)

The sole finding is a pre-existing cross-reference error that the amendment perpetuates rather than introduces. It does not affect the correctness of the three new `/health` fields, the gate semantics, or the backward-compatibility claim. Fixing it is a one-line clerical correction. Once corrected, the amendment is merge-safe.

## 7. Hand-Back

Branch: `rv/rv-arch-003-observability-loaded-skills`
HEAD SHA: `<to-be-pushed>`
Verdict: `pass_with_changes`
Finding count: 1 (Informational)

Awaiting SO dispatch of Architect amendment NUDGE for iter-2 closure of Finding 2.1, followed by re-verify.
