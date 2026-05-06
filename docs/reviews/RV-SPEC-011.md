---
id: RV-SPEC-011
version: 0.1.0
status: complete
verdict: pass_with_changes
review_target: PR-87
review_type: spec
reviewer_model: kimi-k2.6
created: 2026-05-06
---

# RV-SPEC-011: SPEC Review of PR #87 — Self-Deployment + Multi-Hermes + IPC

## 1. PR Reviewed

- **PR**: [#87](https://github.com/OpenClown-bot/developer-assistant/pull/87) (`devin/1778037997-arch-001-pr-b-internals`)
- **Title**: ARCH-001 v0.3.0 (PR-B/4): internals — SELF-DEPLOYMENT-CONTRACT + MULTI-HERMES-CONTRACT + ADR-006
- **Author**: `devin-ai-integration[bot]` (committed by `OpenClown-bot`)
- **Head SHA**: `6cc96f28849bf65a10fdc45b5e5dd89222d04fda`
- **Base SHA**: `a3ac94c6a29f44618d6df66ca1751cd06ac2d84b` (PR-A branch `devin/1778037997-arch-001-pr-a-research-and-decisions`)
- **Mergeable state**: `clean` (against PR-A, not `main`)
- **Commits**: 2 (includes PR-A base)
  - `a3ac94c` — PR-A: research + top-level decisions
  - `6cc96f2` — PR-B: internals — self-deployment + multi-Hermes + IPC
- **Files changed** (PR-B delta only):
  - `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` — added, +357 / −0
  - `docs/architecture/MULTI-HERMES-CONTRACT.md` — added, +319 / −0
  - `docs/architecture/adr/ADR-006-ipc-and-state-mediation.md` — added, +149 / −0
  - Net: 825 insertions, 0 deletions, 3 files

## 2. Spec Reviewed

| Document | Version | Status in PR | Note |
| --- | --- | --- | --- |
| `SELF-DEPLOYMENT-CONTRACT.md` | v0.1.0 | draft | New file |
| `MULTI-HERMES-CONTRACT.md` | v0.1.0 | draft | New file |
| `ADR-006-ipc-and-state-mediation.md` | v0.1.0 | draft | New file |

## 3. Architecture / ADR / PRD References

Baselines reviewed against:

- `README.md` @ `main`
- `CONTRIBUTING.md` @ `main`
- `AGENTS.md` @ `main`
- `docs/orchestration/SESSION-STATE.md` @ `main`
- `docs/prd/PRD-001.md` @ `v0.2.1` (main baseline)
- `docs/questions/QUESTIONS-002-autonomy-team-composition.md` @ `v0.1.0`
- `docs/architecture/ARCH-001.md` @ `v0.2.0` (main baseline; PR-A proposes `v0.3.0` which is not yet merged)
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` @ `v0.2.0`
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` @ `v0.1.0`
- `docs/architecture/OPERATIONAL-STATE-STORE.md` @ `v0.2.0`
- `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` @ `v0.1.0`
- `docs/architecture/adr/ADR-001-platform-foundation.md` @ `v0.2.0`
- `docs/architecture/adr/ADR-002-repository-state.md` @ `v0.2.0`
- `docs/architecture/adr/ADR-003-plugin-supply-chain.md` @ `v0.2.0`
- `docs/backlog/TKT-NEW-self-deployment-architect-pass.md` @ `v0.1.0`
- `docs/reviews/RV-SPEC-009.md` @ `v0.1.0` (pattern reference)

## 4. Review Findings

### 4.1 MAJOR — Missing OPERATIONAL-STATE-STORE schema update

**Finding**: `MULTI-HERMES-CONTRACT.md` §6 defines two new SQLite tables (`work_items` and `escalations`) that are the IPC substrate for the multi-Hermes design. However, `OPERATIONAL-STATE-STORE.md` — the authoritative schema document on `main` at `v0.2.0` — is **not modified** in this PR. The new tables are only described in `MULTI-HERMES-CONTRACT.md`.

**Impact**: Schema authority is split. An Executor implementing TKT-022 (queue schema) will have to read two documents to reconstruct the full schema. Future reviewers of the state store will not see the new tables in the authoritative schema spec. This breaks the pattern established in `OPERATIONAL-STATE-STORE.md` §3, which is the single source of truth for operational tables.

**Required change**: Update `OPERATIONAL-STATE-STORE.md` to `v0.2.1` (or `v0.3.0`) and add Sections 3.4 (`work_items`) and 3.5 (`escalations`) with the same column/type/constraint detail already present in `MULTI-HERMES-STORE.md` §6.2 and §6.3, plus the indexes and migration discipline notes from §6.4. Alternatively, move the full table specs into `OPERATIONAL-STATE-STORE.md` and have `MULTI-HERMES-CONTRACT.md` reference them.

### 4.2 MAJOR — Ambiguous Hermes entry point for specialist runtimes

**Finding**: `SELF-DEPLOYMENT-CONTRACT.md` §5.2 shows a single systemd unit template with `ExecStart=/usr/local/bin/hermes gateway run` for **all five** runtimes. `MULTI-HERMES-CONTRACT.md` §4 sets `gateway.enabled: false` for the four specialist runtimes and `true` only for the Orchestrator.

The contract does not state whether `hermes gateway run` is the correct binary invocation when the config disables the gateway, or whether specialists should use a different command (e.g., `hermes agent run` or `hermes worker run`). If Hermes does not support a gateway-disabled `gateway run` mode, the specialist units will fail to start.

**Impact**: An Executor cannot implement the systemd units without asking the Architect this question. The contract is therefore not fully executable.

**Required change**: Explicitly state the expected `ExecStart` command per runtime in `MULTI-HERMES-CONTRACT.md` §4 or `SELF-DEPLOYMENT-CONTRACT.md` §5.2, or add a sentence confirming that Hermes `gateway run` gracefully becomes a non-gateway worker when `gateway.enabled: false`.

### 4.3 MAJOR — Custom skills not yet allowlisted or reviewed

**Finding**: `MULTI-HERMES-CONTRACT.md` §5 introduces 14 custom `dev-assist-*` skills. `HERMES-SKILL-ALLOWLIST.md` v0.1.0 (main baseline) does not list any of them, and the contract provides no source URL, version pin, or source-review result for any custom skill.

**Impact**: Per `ADR-003` §2 and §4, no skill may be loaded until it appears in the allowlist with all required fields documented. The contract effectively mandates skills that are not yet approved.

**Required change**: Add a dedicated subsection in `MULTI-HERMES-CONTRACT.md` (or in `HERMES-SKILL-ALLOWLIST.md` via a companion PR) that lists every custom skill with:
- Name and source URL (can be `https://github.com/OpenClown-bot/developer-assistant/tree/main/shared-skills/<name>` if project-local).
- Version / commit hash.
- Purpose in v0.1.
- Whether it is built-in, optional official, or project-local community.
- Required credentials and permission scope.
- Source review result: `pending` with a target ticket (e.g., TKT-023) is acceptable at this stage, but the field must exist.

### 4.4 MINOR — "No secrets in journal" verification is underspecified

**Finding**: `SELF-DEPLOYMENT-CONTRACT.md` §8 lists a seventh invariant: "No secrets in journal" (`journalctl -u devassist-*` scanned for known secret env-var values). The contract says the verify script scans for these values but does not explain the mechanism. To detect a leak, the script must either (a) read the secrets file itself, (b) embed the values, or (c) hash them and compare hashes — all of which have trade-offs. The contract also says "only the env-var name is logged, never the value" in failure paths, which is correct, but does not resolve how the detection itself works.

**Impact**: The Executor will need to design the scan heuristic. This is not a blocker, but it is an open design detail.

**Recommended change**: Add one sentence in §8 describing the detection heuristic (e.g., "The verify script reads `SELF-DEPLOY.env` into a sanitized regex set and scans journal output for matches; on match it logs the env-var name and exits non-zero without emitting the matched value.").

### 4.5 MINOR — Memory isolation deferred to implementation ticket

**Finding**: `MULTI-HERMES-CONTRACT.md` §7 correctly acknowledges that the shared `devassist` uid means `ProtectSystem=full` + `ReadWritePaths=` alone does **not** prevent one runtime from reading another's `memories/` directory via normal DAC (same uid). The contract states that `BindReadOnlyPaths=` must be added by TKT-021 to close this gap.

**Impact**: The contract is honest about the gap, but the guarantee of "physical isolation" is not fully met by the contract itself.

**Recommended change**: Move the `BindReadOnlyPaths=` mitigation from the TKT-021 implementation note into the `SELF-DEPLOYMENT-CONTRACT.md` §5.2 unit template (as an explicit parameter with a comment), so the isolation promise is part of the deployment contract, not an implementation afterthought.

### 4.6 OBSERVATION — Stacked-PR reference fragility

The PR references `ARCH-001.md` v0.3.0, `ADR-005-multi-hermes-runtime-isolation.md`, `RESEARCH-001-hermes-and-openclaw-ecosystems.md`, `MODEL-CATALOG.md`, and `ESCALATION-POLICY.md`. None of these exist on `main` at review time; they are introduced by PR-A and subsequent PRs (PR-C, PR-D, PR-E). PR-B is stacked on PR-A and cannot merge to `main` independently. This is structurally sound for a design pass, but the review verdict should be conditioned on PR-A merging first. If PR-A is rejected or significantly revised, this PR will require re-review.

### 4.7 OBSERVATION — Seven invariants vs. "six-check invariant" framing

The review prompt's Focus Area #1 asks whether the contract covers "the six-check invariant." `SELF-DEPLOYMENT-CONTRACT.md` §8 actually defines **seven** connectivity-only invariants (Telegram, GitHub PAT, OmniRoute, state store writable, schema version, each unit active, no secrets in journal). The PRD-001 §12.3 leaves the exact count to the Architect, so seven is acceptable. The prompt's "six" appears to be a shorthand; the PR exceeds it.

### 4.8 OBSERVATION — SELF-DEPLOYMENT-CONTRACT §10 contains contradictory phrasing

The text states: "The systemd unit for the Orchestrator includes the secret env var via `EnvironmentFile=`; the other four units' unit files do not reference the Telegram bot token." However, the template in §5.2 shows `EnvironmentFile=/srv/devassist/secrets/SELF-DEPLOY.env` for **all** units, and the note immediately following clarifies: "All five units load the same `SELF-DEPLOY.env` for convenience; the secret-segregation guarantee comes from each runtime's config not asking for it."

This is technically consistent (the file is loaded into all environments, but the config prevents usage), but the first sentence is misleading. A reader might think the other four units do not load the env file at all. This should be rephrased for clarity.

### 4.9 OBSERVATION — ADR-006 quality is high

`ADR-006` presents **six** considered options (A-F), evaluates each with explicit trade-offs, maps them against a decision-criteria table, and justifies the SQLite-mediated queue choice with v0.1-scale reasoning. It correctly addresses the runtime-crash mid-operation case through lease expiry + reclaim sweep (§6.2). This exceeds the "≥3 options" quality bar.

### 4.10 OBSERVATION — No breaking changes to existing code

The PR adds three new documents and touches no existing implementation files. `OPERATIONAL-STATE-STORE.md` is unchanged, so `state_store.py`, `progress_scheduling.py`, and `smoke_readiness.py` on `main` are unaffected. The new tables are additive and will be introduced via migration in a future ticket (TKT-022).

## 5. Security Notes

| Concern | Severity | Detail |
| --- | --- | --- |
| Shared secrets env file across all units | medium | All five systemd units load `SELF-DEPLOY.env`, so the Telegram bot token is present in every runtime's environment. The defense is config-level (non-Orchestrator runtimes do not load the `telegram-gateway` skill), not environment-level. A runtime compromise or a Hermes config injection bug could expose the token. **Mitigation**: note this in the contract and recommend a future hardening pass (e.g., per-unit env files with variable subsetting). |
| `ProtectSystem=full`, `ProtectHome=true`, `NoNewPrivileges=true` | good | Standard systemd hardening is applied consistently. |
| `PrivateTmp=true` | good | Prevents temp-file leakage between runtimes and host. |
| Docker group for Executor/Reviewer | medium | `SupplementaryGroups=docker` grants access to the Docker socket. The contract limits this to Executor and Reviewer, which is correct per their skill loadout. |
| Rollback preserves secrets | good | `SELF-DEPLOY.env` lives outside the release tree (`/srv/devassist/secrets/`), so release symlinking never touches it. |
| Secret leak detection in journal | good | The seventh invariant is a proactive security control. The implementation detail (how the script reads secrets to scan) should be documented per §4.4. |

## 6. Final Verdict

**Verdict**: `pass_with_changes`

**Justification**: The three new documents form a coherent, specific, and largely executable design for self-deployment and multi-Hermes composition. The PRD coverage is broad: one-command install, verify, rollback, upgrade, three approval gates, secrets handling, per-runtime skills loadout, SQLite-mediated IPC with lease semantics, and memory isolation boundaries are all addressed.

The design is **not quite ready to hand to an Executor without questions** for two reasons:
1. The `OPERATIONAL-STATE-STORE.md` authoritative schema is not updated with the new tables, creating a two-source-of-truth problem.
2. The Hermes binary entry point for gateway-disabled specialist runtimes is not explicitly confirmed.

Both are fixable with targeted text edits. Once those edits land (and PR-A is merged), this PR is approvable.

**Recommended follow-up actions**:
1. Update `OPERATIONAL-STATE-STORE.md` to include `work_items` and `escalations` tables (or move the table specs there and reference them from `MULTI-HERMES-CONTRACT.md`).
2. Clarify the `ExecStart` command for specialist runtimes in `MULTI-HERMES-CONTRACT.md` §4 or `SELF-DEPLOYMENT-CONTRACT.md` §5.2.
3. Add a custom-skill allowlist stub (with `pending` review status) to `MULTI-HERMES-CONTRACT.md` §5 or to `HERMES-SKILL-ALLOWLIST.md`.
4. Rephrase `SELF-DEPLOYMENT-CONTRACT.md` §10 to remove the misleading "other four units do not reference the Telegram bot token" sentence.
5. Move the `BindReadOnlyPaths=` isolation mitigation from the TKT-021 note into the systemd unit template in `SELF-DEPLOYMENT-CONTRACT.md` §5.2.
