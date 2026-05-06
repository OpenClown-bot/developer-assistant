---
id: RV-SPEC-009
version: 0.1.0
status: complete
verdict: pass
review_target: PR-83
review_type: spec
reviewer_model: kimi-k2.6
created: 2026-05-06
---

# RV-SPEC-009: SPEC Review of PR #83 — PRD-001 v0.2.1 (Self-Deployment + High Autonomy + Multi-Hermes + Upstream Composability)

## 1. PR Reviewed

- **PR**: [#83](https://github.com/OpenClown-bot/developer-assistant/pull/83) (`devin/1778030342-prd-001-v0.2.0-self-deployment`)
- **Title**: PRD-001 v0.2.1: self-deployment + high autonomy + multi-Hermes + upstream composability
- **Author**: `OpenClown-bot`
- **Head SHA**: `ade83d6f1c8bc3e0c4350195b6aed444e348f8b5`
- **Base SHA**: `d09dba2565677d1b21be1c11139a68a00a46a878` (`main`)
- **Mergeable state**: `clean`
- **Commits**: two on the same branch
  - `fe4e8cb` — PRD-001 v0.2.0: add self-deployment operational target (new § 12)
  - `ade83d6` — PRD-001 v0.2.1: high autonomy, multi-Hermes team, upstream composability (new § 13 + threading through §§ 3, 4, 6, 7, 9, 10, 11)
- **Files changed** (cumulative across both commits):
  - `docs/prd/PRD-001.md` — revised, +180 / −6
  - `docs/questions/QUESTIONS-002-autonomy-team-composition.md` — added, +72 / −0
  - Net: 246 insertions, 6 deletions, 2 files

## 2. Spec Reviewed

- **Spec**: `docs/prd/PRD-001.md` @ `0.2.1` (revised from baseline `0.1.0` on `main`)
- **Companion Q&A record**: `docs/questions/QUESTIONS-002-autonomy-team-composition.md` @ `0.1.0` (new file, status: `resolved`)
- **Status at review time**: PRD frontmatter `status: draft`; QUESTIONS-002 frontmatter `status: resolved`
- **Scope alignment**: The PR stays strictly within the Business Planner write zone (`docs/prd/`, `docs/questions/`). It revises the PRD and adds a durable Q&A record. No code, tests, architecture, ADRs, tickets, prompts, reviews, CI, or session-state files are touched.

## 3. Architecture / ADR References Consumed by This Review

- **Architecture**: `docs/architecture/ARCH-001.md` @ `0.2.0` (the v0.1 baseline architecture; PRD § 11 hands off to it).
- **Contract documents**:
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md` @ `0.2.0`
  - `docs/architecture/HERMES-SKILL-ALLOWLIST.md` @ `0.1.0`
  - `docs/architecture/OPERATIONAL-STATE-STORE.md` @ `0.2.0`
  - `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` @ `0.1.0`
- **ADRs**:
  - `ADR-001-platform-foundation.md` @ `0.2.0` — Hermes-first hybrid foundation; PRD § 13 lives within this.
  - `ADR-002-repository-state.md` @ `0.2.0` — split state model; PRD § 12 references state-store backup.
  - `ADR-003-plugin-supply-chain.md` @ `0.2.0` — skill governance; PRD § 12.6 / § 8 secret handling.
- **Backlog / sequencing**:
  - `docs/backlog/TKT-NEW-self-deployment-architect-pass.md` — gap analysis discharged by this PRD revision.
  - `docs/session-log/2026-05-05-session-1.md` — cross-repo audit that produced the directive.
- **Tickets gated downstream**:
  - `docs/tickets/TKT-011.md` @ `0.2.0` — Telegram-to-PR trial; gated behind the upcoming Architect self-deployment pass.
  - `docs/tickets/TKT-017.md` @ `0.1.0` — readiness harness; preserved unchanged.
- **Other Q&A**: `docs/questions/QUESTIONS-001-bootstrap.md` @ `0.1.0` (the Founder rule "always ask after CI and Reviewer pass in v0.1" frames the merge gate this review sits in).
- **Stylistic calibration**: `docs/reviews/RV-SPEC-007.md`, `docs/reviews/RV-SPEC-008.md`, `docs/reviews/REVIEW-TEMPLATE.md`.
- **Validator**: `scripts/validate_docs.py` @ HEAD.

## 4. CI Status

GitHub API response for `commits/ade83d6f1c8bc3e0c4350195b6aed444e348f8b5/check-runs`:

```
{"conclusion":"success","name":"validate-docs","status":"completed"}
{"conclusion":"success","name":"Run PR Agent on every pull request","status":"completed"}
```

| Check | Status | Conclusion |
|---|---|---|
| `validate-docs` | completed | success |
| `Run PR Agent on every pull request` | completed | success |

Both required checks on the PR HEAD are green.

## 5. Findings

No `major` findings. Four `observation`-level findings are recorded; none individually or collectively block verdict `pass`. Each is mechanical to address in a later PRD revision (v0.2.2 or v0.3.0) or by the Architect during the upcoming self-deployment pass; none prevents the Architect from beginning that pass with the artifacts in this PR.

### 5.1 observation — § 10 open questions Q10–Q18 lack explicit `impact` and `urgency` fields

- **Location**: `docs/prd/PRD-001.md` @ `0.2.1` lines 217–228 (questions 10–18).
- **Description**: Each new open question (Q10 through Q18) provides (a) the question text, (b) two implicit options for non-trivial choices, and (c) a recommended default. None of the nine new questions provides (d) explicit "impact-of-getting-it-wrong" or (e) urgency, which are part of the founder-question shape recorded in `HERMES-RUNTIME-CONTRACT.md` § 5 (`founder_questions` sub-fields: context, options, recommended_default, impact, urgency, durable_artifact_target).
- **Pre-existing repo style note**: Baseline PRD-001 v0.1.0 questions Q1–Q8 also lack impact and urgency (they have only question text). The new questions are a strict improvement over baseline because they add recommended defaults; they remain below the HERMES-RUNTIME-CONTRACT shape. This is a pre-existing PRD style gap, not a regression introduced by v0.2.1.
- **Why this is not a blocker**: The recommended defaults are the most operationally important field for the upcoming Architect pass; the Architect can begin work knowing the Founder's leaning. Impact and urgency can be inferred from § 11 handoff narrative and the § 13 narrative for Q16–Q18.
- **Recommendation**: In a future PRD revision, restructure § 10 entries (both legacy Q1–Q8 and new Q10–Q18) to follow the HERMES-RUNTIME-CONTRACT § 5 founder-question shape with explicit impact and urgency. This is a Business Planner stylistic improvement, not a v0.2.1 blocker.

### 5.2 observation — § 10 Q9 resolution does not cross-reference QUESTIONS-002 by file path

- **Location**: `docs/prd/PRD-001.md` @ `0.2.1` line 213 (Q9 resolution).
- **Description**: Q9 is correctly marked `(Resolved in v0.2.1)`, the resolution text reproduces the substance of the Founder's selection, and it points to "Sections 6, 7, and 13.1" for the operative product wording. It does not link by file path to `docs/questions/QUESTIONS-002-autonomy-team-composition.md`, which is the durable Q&A record for this resolution and is added in the same PR.
- **Why this is not a blocker**: The PR description references QUESTIONS-002 explicitly; both files are in the same PR; QUESTIONS-002 itself states `PRD-001 § 10 question 9 is now resolved` in its own pointers section, making the bidirectional linkage discoverable. A reasonable reader (or Architect) looking for provenance will find the Q&A trail.
- **Recommendation**: Append `Full Q&A trail: docs/questions/QUESTIONS-002-autonomy-team-composition.md` to the Q9 resolution sentence. Mechanical change for a future PRD revision.

### 5.3 observation — § 11 Section-13 handoff acknowledges scope expansion but does not record the Founder's accepted ~1.5x–2x sequencing penalty

- **Location**: `docs/prd/PRD-001.md` @ `0.2.1` lines 251 and 255 (Section-13 handoff subsection).
- **Description**: The handoff acknowledges that absorbing the multi-Hermes mandate, upstream abstraction, and escalation policy may require revising ARCH-001 (likely to v0.3.0) and possibly extending HERMES-RUNTIME-CONTRACT and OPERATIONAL-STATE-STORE before the SELF-DEPLOYMENT-CONTRACT can be finalized. It does not state that the Founder explicitly accepted, during the QUESTIONS-002 Q1 selection, the ~1.5x–2x lengthening of the path to TKT-011 because of IPC, memory isolation, and orchestration. That acceptance is recorded in `QUESTIONS-002` Q1 ("Founder selection: A") and in the QUESTIONS-002 `Resolved` table ("The Founder accepts that this lengthens the path to TKT-011 by roughly 1.5x–2x").
- **Why this is not a blocker**: The product substance — multi-Hermes is a v0.1 hard requirement; each role its own Hermes runtime — is faithfully reflected in PRD § 13.2, § 6, § 7 (memory isolation), and § 11. The cost acceptance is process / scheduling context rather than product substance, and it is durably recorded in QUESTIONS-002 in this same PR.
- **Recommendation**: Optionally add one sentence to PRD § 11 Section-13 handoff acknowledging the Founder's accepted sequencing penalty (per QUESTIONS-002 Q1), so the Architect dispatch session reads the full provenance directly from PRD without needing to consult QUESTIONS-002. Stylistic improvement, not a blocker.

### 5.4 observation — Vendor name "OmniRoute" appears in PRD product-language sections

- **Location**: `docs/prd/PRD-001.md` @ `0.2.1` lines 267, 277 (in § 12 self-deployment narrative); the PR description also refers to it.
- **Description**: PRD § 12.1 states the Founder is "registered against ... the Founder's OmniRoute LLM access" and § 12.2 lists "an OmniRoute API key for LLM access" as one of the values the Founder writes into the deployment environment file. OmniRoute is a specific external service / vendor identifier. Strict reading of criterion A ("Names of specific tools, packages, libraries, services") would flag any vendor name in the PRD as implementation language.
- **Why this is not a blocker**: OmniRoute is the Founder's existing pre-approved LLM-routing layer per `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions, `docs/session-log/2026-05-05-session-1.md` § 0, and per all role prompts (`docs/prompts/executor.md`, `docs/prompts/reviewer.md`, etc.). It is a Founder-fixed external vendor identity, in the same product-language category as "Telegram bot identity" or "GitHub identity"; the Founder must supply a credential for it. The PRD does NOT name specific models, does not pick an LLM vendor (only identifies the Founder's LLM-access service), and does NOT commit to an internal implementation choice. This is therefore a Founder-credential identification, not an internal implementation pick.
- **Why it is still worth noting**: A future Founder could conceivably switch from OmniRoute to a different multi-LLM proxy. The PRD wording would then need to abstract one level higher (e.g., "the Founder's LLM access provider"). Today the wording is fine because OmniRoute is the canonical name in the project's repo conventions.
- **Recommendation**: Leave as-is for v0.2.1. If, during the Architect pass, OmniRoute itself becomes one of the variables under design (e.g., the Architect proposes a fallback when OmniRoute is unreachable), abstract the PRD wording in v0.2.2.

## 6. Product-Language Discipline (Criterion A)

PRD-001 v0.2.1 is in product language. § 12 and § 13, both new in v0.2.x, repeatedly and explicitly disclaim implementation choices and hand them to the Architect.

| Implementation-detail probe | PRD treatment | Verdict |
|---|---|---|
| Specific tools / packages / libraries / services | § 12.2 names container / service-manager candidates ("Docker, Docker Compose, systemd, bare-metal install, etc.") only as examples in a paragraph that explicitly disclaims commitment ("The PRD does not commit to the command name, the script language, or the underlying packaging mechanism ... The Architect chooses these and records the choice in an ADR"). § 13.2 same pattern: "The PRD does not commit to the IPC mechanism, supervision strategy, memory backend, model assignment per role, or self-learning persistence format". | PASS |
| File paths / mode bits / exact command names / config keys | § 12.2 names a placeholder file (`SELF-DEPLOY.env`) but explicitly labels it "referred to here as `SELF-DEPLOY.env`" and disclaims commitment to "command name, the script language, or the underlying packaging mechanism". § 12.6 same: "The PRD does not commit to a specific file mode, path convention, or secret-handling library". | PASS |
| Specific IPC mechanisms / queue technologies / supervision strategies | § 13.2 names categories (queue, event bus, direct call, repository-mediated) only as examples in a sentence that hands the choice to the Architect. § 11 same. | PASS |
| Specific model names from any specific vendor | § 10 Q17 introduces the concept of a Founder-pre-approved model catalog without naming any model. § 13.2 references "the agreed catalog (Section 10 question 17)" without naming models. | PASS |
| Schemas / message formats / API surfaces | § 13.3 names "upstream entry-point abstraction" only at the level of what it covers (incoming user messages, outgoing user messages, approval prompts, identity binding, session continuity). § 13.3 disclaims explicitly: "The PRD does not commit to the abstraction's exact API surface, the message schema, the identity-binding format, or the queue or bus that connects adapters to the main Hermes". | PASS |

The only edge case is the appearance of "OmniRoute" as a Founder-credential identifier in § 12.1 / § 12.2 (Finding 5.4), classified as a Founder-fixed external vendor identity rather than an internal implementation choice.

References to "Hermes" / "Hermes runtime" / "Telegram" in the PRD are not implementation-language violations because both are Founder-fixed and ARCH-001 v0.2.0–approved baseline identities (Hermes is the v0.1 platform foundation per ADR-001; Telegram is the required v0.1 founder-facing surface per QUESTIONS-001 and ARCH-001 § 7). Naming them is identifying the agreed product surface, not picking an implementation.

## 7. Internal Consistency of New § 13 (Criterion B)

| Required content | Present in PRD | Verdict |
|---|---|---|
| § 13.1 high autonomy reconciles with § 12 self-deployment approval gates | Last paragraph of § 13.1 (line 341): "The self-deployment approval gates in Section 12.5 (`install` without approval, `start` with explicit approval, `upgrade` with explicit approval and a state-store backup) are a separate, narrower regime ... Those gates remain in force regardless of the Section 13.1 day-to-day autonomy model." | PASS |
| § 13.2 explicitly says "the Founder talks to one entity" | Line 345: "From the Founder's view there is exactly one assistant, addressed through the Telegram adapter (Section 13.3)." Line 349: "The Founder sees one assistant." | PASS |
| § 13.2 explicitly says "internally the assistant is a team" | Line 345: "The assistant in v0.1 is internally a **team of full Hermes runtimes**, not a single runtime that switches roles." | PASS |
| § 13.2 names role list (Business Planner, Architect, Executor, Reviewer, Orchestrator) | Line 348: "Each **specialist role** (Business Planner, Architect, Executor, Reviewer, Orchestrator) runs as its **own full Hermes runtime**". | PASS |
| § 13.3 explicitly says "v0.1 does NOT implement OpenClaw" | Line 357: "v0.1 does not implement OpenClaw integration." | PASS |
| § 13.3 explicitly says Architect must abstract upstream entry-point | Line 361: "The architecture must define a single **upstream entry-point abstraction** covering incoming user messages, outgoing user messages, approval prompts, identity binding, and session continuity." | PASS |
| § 13.3 explicitly says v0.2 adds adapters, does not rewrite core | Lines 359, 363: "is an **adapter-level** addition, not a core rewrite"; "intended to be added as a parallel implementation later". Line 365: "'swap or add an upstream entry-point' never requires touching specialist Hermes runtimes, Founder-facing intake logic, or the orchestrator core." | PASS |

**Cross-consistency check across the three subsections**:

- § 13.1 (autonomy of the assistant as a whole) operates at the level of the main Hermes described in § 13.2: § 13.2 line 347 places escalation-prompt ownership on the main Hermes ("It owns Founder-facing conversation, identity binding, intake state, escalation prompts (per Section 13.1), and progress reports"). Consistent.
- § 13.3 (upstream abstraction) composes cleanly with § 13.2 (main-Hermes-as-Founder-facing): § 13.3 line 365 places the abstraction explicitly between the upstream adapter and the main Hermes ("never requires touching specialist Hermes runtimes, Founder-facing intake logic, or the orchestrator core"). Adapters connect to main Hermes, not specialist runtimes. Consistent.
- § 13.2 line 353 ("multi-Hermes composition has consequences for self-deployment (Section 12) that the Architect must absorb: install must bring up the orchestrator plus N specialist runtimes; health check must verify each runtime, not just one process; rollback must preserve each runtime's memory and self-learning state") explicitly threads Section 13 mandates back into Section 12, ensuring the two sections compose as one coherent product position.

§ 13's three subsections are individually well-formed and cross-consistent.

## 8. Faithful Reflection of QUESTIONS-002 (Criterion C)

QUESTIONS-002 records three resolved Founder positions. Each position must appear in the PRD locations called out by criterion C.

| QUESTIONS-002 Q | Founder selection | Required PRD locations | Found in | Verdict |
|---|---|---|---|---|
| Q1 — Multi-Hermes scope in v0.1 | Option A: hard requirement; each role its own Hermes runtime; ~1.5x–2x time penalty accepted | § 13.2 + § 6 + § 11 | § 13.2 (lines 343–353); § 6 line 116 ("must run each specialist role ... as its own full Hermes runtime instance with its own memory and self-learning state"), line 117 ("must expose one Founder-facing entity"); § 11 lines 232 (handoff opener), 251 ("Multi-Hermes mandate ..."), 254 ("Self-deployment scope expansion ..."), 255 (sequencing implication) | PASS (substance); see Finding 5.3 for the time-penalty observation |
| Q2 — OpenClaw upstream | Option B: v0.1 does not implement; Architect must abstract upstream entry-point; v0.2 adapter | § 13.3 + § 6 + § 11 | § 13.3 (lines 355–365); § 6 line 118 ("must abstract the upstream entry-point so that adding a new upstream adapter (e.g., OpenClaw) is an adapter-level change ... v0.1 ships only the Telegram adapter"); § 11 line 252 ("Upstream entry-point abstraction: define a single 'upstream entry-point' abstraction ... v0.1 ships only the Telegram adapter; the abstraction must allow adding the OpenClaw adapter in v0.2 as a parallel implementation, not as a core rewrite") | PASS |
| Q3 — Approval criterion | Option A: single trigger ("deviates from concept" OR "breaks something"); library / merge / model-from-catalog / agreed external API are autonomous; § 10 Q9 marked resolved | § 13.1 + § 6 + § 9 + § 10 (Q9 resolved) | § 13.1 (lines 330–341); § 6 line 127 ("must escalate decisions to the Founder ONLY when the decision deviates from the original product concept agreed during intake OR risks breaking already-committed scope or operational state; all other decisions during day-to-day project work proceed autonomously"); § 9 line 190 ("A v0.1 project run from intake to merged PR can complete with no approval prompts to the Founder unless the assistant identifies a deviation-from-concept or break-something condition"); § 10 line 213 (Q9 marked `(Resolved in v0.2.1)` with full resolution text) | PASS (substance); see Finding 5.2 for the QUESTIONS-002 cross-reference observation |

The three Founder positions are faithfully reflected in PRD product substance at every required location. The two minor gaps (5.2 and 5.3) are stylistic / provenance-link issues, not substance issues.

## 9. § 10 Open Questions Completeness and Quality (Criterion D)

| # | Question topic | (a) text | (b) ≥2 options | (c) recommended default | (d) impact | (e) urgency |
|---|---|---|---|---|---|---|
| 9 | Resolved | n/a | n/a | n/a | n/a | n/a |
| 10 | Non-Ubuntu install targets | yes | yes (non-Ubuntu vs Ubuntu-only) | yes | no | no |
| 11 | 15-minute install upper bound | yes | yes (faster vs accept 15 min) | yes | no | no |
| 12 | Health check depth (LLM dispatch vs connectivity-only) | yes | yes (end-to-end vs connectivity-only) | yes | no | no |
| 13 | Auto-start on VPS reboot | yes | yes (auto-start vs manual) | yes | no | no |
| 14 | Rollback as v0.1 hard requirement | yes | yes (hard requirement vs clean-install fallback) | yes | no | no |
| 15 | Secret rotation flow | yes | yes (documented rotate-and-restart vs informal edit-and-restart) | yes | no | no |
| 16 | Memory isolation between role Hermes runtimes | yes | yes (strict isolation vs shared "project pulse") | yes | no | no |
| 17 | Pre-approved model catalog | yes | yes (catalog in ARCH-001 vs dedicated MODEL-CATALOG.md) | yes | no | no |
| 18 | Simultaneous vs switchable upstream adapters in v0.2 | yes | yes (simultaneous vs switchable) | yes | no | no |

Q9 is correctly marked as resolved with the resolution text; the gap is the missing explicit cross-reference to QUESTIONS-002 (Finding 5.2). Q10–Q18 are well-formed at the (a)/(b)/(c) level and uniformly miss (d) and (e) (Finding 5.1). Q16, Q17, Q18 — the three new questions seeded by § 13 — are well-formed at (a)/(b)/(c) and tightly linked to § 13 subsection contents:

- Q16 references the strict per-role isolation default (§ 7 Memory isolation: "specialist role Hermes runtimes must not have implicit access to one another's memory; cross-role durable state lives in repository artifacts and the operational state store, not in shared agent memory"); consistent with § 13.2.
- Q17 names the model-catalog concept that § 13.2 line 348 and § 11 line 254 (model catalog as versioned/backupable upgrade item) both reference.
- Q18 names the simultaneous-vs-switchable choice that § 13.3 line 363 hands to Q18; § 11 line 252 echoes "Decide whether v0.2 should support simultaneous active adapters per Section 10 question 18".

§ 10 is **substantively complete enough** for the Architect to begin the self-deployment pass; it is **stylistically below** the HERMES-RUNTIME-CONTRACT § 5 founder-question shape on the (d)/(e) axis. This is a pre-existing PRD-001 style gap (baseline v0.1.0 Q1–Q8 are at the same level), not a v0.2.1 regression.

## 10. Architect Handoff Completeness (Criterion E)

| Required handoff content | PRD location | Verdict |
|---|---|---|
| Sequencing constraint: PRD v0.2.1 → Architect pass → TKT-011 | Line 244: "Sequencing constraint: this PRD revision -> Architect pass -> TKT-011 trial." Line 255: "The PRD-001 v0.2.1 -> Architect pass -> TKT-011 sequencing constraint stands". | PASS |
| Obligation to absorb § 12 (self-deployment) mandates | § 11 dedicated subsection (lines 242–247) opening "The following handoff notes apply specifically to self-deployment of the assistant itself (Section 12)". | PASS |
| Obligation to absorb § 13 (autonomy + multi-Hermes + upstream) mandates | § 11 dedicated subsection (lines 249–255) opening "The following handoff notes apply specifically to operating mode, team composition, and upstream composability (Section 13)". | PASS |
| Obligation to produce SELF-DEPLOYMENT-CONTRACT (or architecture section equivalent) | Line 245: "an architecture section (or new contract document such as `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md`) that specifies the install entry point, environment-variable contract, pre-flight validation, health-check checklist, rollback mechanism, upgrade procedure, and Founder-approval gates". | PASS |
| Obligation to produce escalation-policy artifact | Line 253: "Escalation policy artifact: produce an architecture document (or contract) that operationalizes the product-level rule ..." with explicit minimum coverage list. | PASS |
| Obligation to produce ADR on deployment mechanism | Line 245: "a new ADR recording the deployment-mechanism choice (container vs systemd vs bare-metal install, secrets storage, logging destination, operational state store backend)". | PASS |
| Obligation to produce ≥3 implementation tickets | Line 245: "and at least three implementation tickets covering install, health check, and rollback/upgrade with state-store backup". | PASS |
| Explicit warning that ARCH-001 may need v0.3.0 bump | Line 255: "The Architect should expect that absorbing the Section 13 mandates may require revising ARCH-001 (likely to v0.3.0)". | PASS |
| Explicit warning that HERMES-RUNTIME-CONTRACT and OPERATIONAL-STATE-STORE may need extension | Line 255: "and possibly extending HERMES-RUNTIME-CONTRACT and OPERATIONAL-STATE-STORE before the SELF-DEPLOYMENT-CONTRACT can be finalized". | PASS |

§ 11 also retains all baseline (v0.1.0) handoff bullets and discharges the original platform-selection bullet (line 232: "ARCH-001 v0.2.0 selected the Hermes-first hybrid baseline"). § 11 separates self-deployment handoff (§ 12) from operating-mode/team/upstream handoff (§ 13) into two clearly-bounded subsections, which keeps the Architect briefing actionable. The handoff is complete.

## 11. Write-Zone Compliance (Criterion F)

- **Files changed**: `docs/prd/PRD-001.md`, `docs/questions/QUESTIONS-002-autonomy-team-composition.md` (2 files).
- **Business Planner write zone** (per `CONTRIBUTING.md` and `AGENTS.md`): `docs/prd/`, `docs/questions/`. Both changed files are within the Business Planner allowed write zone.
- **No production code changed**: confirmed (`src/`, `tests/` untouched).
- **No architecture / ADRs / tickets / reviews / prompts / orchestration / session-state / CI / config files changed**: confirmed.
- **No secrets exposed**: confirmed (see § 12).

**Verdict**: PASS.

## 12. Secret Hygiene (Criterion G)

PRD-001 v0.2.1 and QUESTIONS-002 v0.1.0 contain no secret values, tokens, raw IDs, credential paths, token-bearing remotes, private runtime config, or VPS-specific identifiers.

- Secret **categories** are named at the product-language level (Telegram bot token, GitHub PAT for project repositories, OmniRoute API key, VPS-local paths) without any concrete value, repository URL, hostname, IP address, mode bit, or path prefix.
- The PRD repeatedly states secrets must live only in the Founder's environment file and never in repository artifacts (§ 6 lines 139–146; § 8; § 9 line 200; § 12.6).
- QUESTIONS-002 contains no secrets.

**Verdict**: PASS.

## 13. Cross-Reference Integrity (Criterion H)

`scripts/validate_docs.py` was run against the PR-83 working tree (PRD-001 v0.2.1 frontmatter intact, QUESTIONS-002 v0.1.0 frontmatter intact, all required directories present, all ticket sections in unrelated tickets unchanged) — `Docs validation passed.`

Manual spot checks of every internal reference in the revised PRD:

| Reference in PRD-001 v0.2.1 | Target | Resolves? |
|---|---|---|
| Section 5 (line 266) | § 5 in PRD itself | yes |
| Section 6 (lines 137, 213, 332) | § 6 in PRD itself | yes |
| Section 7 (line 213, 155) | § 7 in PRD itself | yes |
| Section 9 (line 213) | § 9 in PRD itself | yes |
| Section 10 (lines 213, 224, 332) | § 10 in PRD itself | yes |
| Section 11 (lines 244, 245, 253, 339, 351, 365 etc.) | § 11 in PRD itself | yes |
| Section 12 (lines 137, 257) | § 12 in PRD itself | yes |
| Section 12.5 (lines 311, 341) | § 12.5 in PRD itself | yes |
| Section 12.2 (line 317) | § 12.2 in PRD itself | yes |
| Section 13 (line 29) | § 13 in PRD itself | yes |
| Section 13.1 (lines 127, 155, 213, 332, 341) | § 13.1 in PRD itself | yes |
| Section 13.2 (lines 116, 117, 345) | § 13.2 in PRD itself | yes |
| Section 13.3 (lines 118, 357) | § 13.3 in PRD itself | yes |
| Section 10 question 9 | Q9 in PRD § 10 | yes |
| Section 10 question 17 (lines 226, 332, 348) | Q17 in PRD § 10 | yes |
| Section 10 question 18 (lines 224, 252, 363) | Q18 in PRD § 10 | yes |
| ARCH-001 v0.2.0 (lines 232, 255) | `docs/architecture/ARCH-001.md` v0.2.0 | yes |
| HERMES-RUNTIME-CONTRACT (lines 232, 255) | `docs/architecture/HERMES-RUNTIME-CONTRACT.md` v0.2.0 | yes |
| OPERATIONAL-STATE-STORE (lines 232, 255) | `docs/architecture/OPERATIONAL-STATE-STORE.md` v0.2.0 | yes |
| GENERATED-PROJECT-DEPLOYMENT-CONTRACT (line 257) | `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` v0.1.0 | yes |
| ADR (line 245, 280, 351) | `docs/architecture/adr/` (location/family reference) | yes |
| TKT-011 (lines 244, 255) | `docs/tickets/TKT-011.md` v0.2.0 | yes |
| `docs/backlog/TKT-NEW-self-deployment-architect-pass.md` (line 246) | exists | yes |
| `docs/session-log/2026-05-05-session-1.md` (line 246) | exists | yes |
| Section-13 handoff subsection in § 11 (line 232) | exists at lines 249–255 | yes |
| `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (line 245) | future Architect output (acknowledged as candidate path) | acceptable as handoff target |
| `docs/architecture/MODEL-CATALOG.md` (line 227) | future Architect output (acknowledged as candidate path) | acceptable as handoff target |

QUESTIONS-002 references checked similarly; all internal targets exist.

The revised PRD references QUESTIONS-002 indirectly through context (resolution text, PR description) but does not link by file path from § 10 Q9; Finding 5.2 records this as an observation.

**Verdict**: PASS.

## 14. Out-of-Scope Boundary Notes

The following were explicitly excluded from this RV-SPEC review per the invocation, and the Reviewer notes the boundary:

- **Architecture, ADR, ticket, code, or test work**: none has been produced for self-deployment yet. The Architect self-deployment pass (per `TKT-NEW-self-deployment-architect-pass.md`) is the next pass and is downstream of this PRD revision merging.
- **Whether the Founder's product positions are "correct"**: out of scope; the Founder has decided. This review verifies faithful reflection only.
- **Whether multi-Hermes overhead is "worth it"**: out of scope; the Founder explicitly accepted the sequencing penalty in QUESTIONS-002 Q1.
- **Implementation feasibility of any § 12 / § 13 commitment**: out of scope; that is the Architect's job in the next pass. § 11 lists the exact Architect deliverables (SELF-DEPLOYMENT-CONTRACT or equivalent, escalation-policy artifact, deployment-mechanism ADR, ≥3 implementation tickets, possible ARCH-001 v0.3.0 bump, possible HERMES-RUNTIME-CONTRACT / OPERATIONAL-STATE-STORE extensions).

## 15. Verdict

**pass**

PR #83 revises PRD-001 from v0.1.0 to v0.2.1 by adding § 12 (self-deployment operational target, in v0.2.0) and § 13 (operating mode, multi-Hermes team composition, upstream composability, in v0.2.1), and threads three resolved Founder positions through §§ 3, 6, 7, 9, 10, and 11. The companion file `docs/questions/QUESTIONS-002-autonomy-team-composition.md` records the Founder Q&A trail as a durable artifact.

Against the nine in-scope criteria (A–I):

- **A. Product-language discipline**: PASS. § 12 and § 13 repeatedly disclaim implementation choices (command names, packaging mechanism, IPC, supervision, memory backend, model assignment, classifier mechanism, adapter API surface) and hand them to the Architect. The single edge case (vendor name "OmniRoute") is a Founder-credential identification consistent with established repo conventions.
- **B. Internal consistency of § 13**: PASS. Each subsection contains every required element; the three subsections are cross-consistent (autonomy in 13.1 applies through main Hermes in 13.2; adapter abstraction in 13.3 sits in front of main Hermes; multi-Hermes scope is threaded explicitly back into § 12 self-deployment via § 13.2 last paragraph).
- **C. Faithful reflection of QUESTIONS-002**: PASS in substance. Two minor stylistic gaps recorded as Findings 5.2 (Q9 cross-reference to QUESTIONS-002) and 5.3 (sequencing-penalty acceptance note); neither blocks Architect dispatch.
- **D. § 10 open questions completeness and quality**: PASS at the substance level. New Q10–Q18 are well-formed with explicit recommended defaults; all nine miss explicit `impact` and `urgency` per the HERMES-RUNTIME-CONTRACT § 5 shape (Finding 5.1). Pre-existing PRD style; not a regression.
- **E. § 11 Architect handoff completeness**: PASS. All required handoff content (sequencing, § 12 absorption, § 13 absorption, SELF-DEPLOYMENT-CONTRACT obligation, escalation-policy obligation, deployment-mechanism ADR, ≥3 tickets, ARCH-001 v0.3.0 warning, HERMES-RUNTIME-CONTRACT / OPERATIONAL-STATE-STORE extension warning) is present and substantive.
- **F. Write-zone compliance**: PASS. Only Business Planner files touched.
- **G. Secret hygiene**: PASS. No secret values, raw IDs, credential paths, or VPS-specific identifiers appear in either changed file.
- **H. Cross-reference integrity**: PASS. `validate_docs.py` passes; every internal cross-reference resolves to an existing target at the cited version (or to a future Architect output explicitly handed off in § 11).
- **I. CI status**: PASS. Both `validate-docs` and `Run PR Agent on every pull request` on commit `ade83d6` returned `conclusion: success`.

The four observation-level findings are mechanical / stylistic and individually safe to address in a follow-up PRD revision (v0.2.2 or v0.3.0) or to leave to the Architect dispatch session. None of them prevents the next pass from beginning. No `major` or `minor` findings were produced; no Founder decision is required to conclude this review.

The PRD reflects the Founder's three positions (high autonomy, multi-Hermes team, upstream composability) faithfully, stays in product language, hands the Architect a complete and bounded brief, and preserves the v0.1 sequencing constraint (this PRD revision → Architect self-deployment pass → TKT-011).

## 16. Residual Risks

- **Stylistic gap in § 10 founder-question shape (Finding 5.1)**: future Architect or future Reviewer may need to manually resolve "impact" and "urgency" per Q10–Q18 when prioritizing. Mitigation: § 11 narrative makes the urgency of Section 12 / Section 13 mandates clear at the section level (the Architect pass is the immediate next step and is sequencing-blocked on this PRD merging); Q10–Q18 details are subordinate to that.
- **Q&A provenance link gap (Finding 5.2)**: a reader of PRD § 10 alone does not see a direct file-path link to QUESTIONS-002. Mitigation: QUESTIONS-002 is in the same PR, the PR description references it, and QUESTIONS-002 itself contains a back-pointer to PRD § 10 Q9.
- **Sequencing-penalty acceptance not on PRD face (Finding 5.3)**: an Architect dispatch session reading only PRD may not see the Founder's explicit acceptance of ~1.5x–2x time cost. Mitigation: QUESTIONS-002 is a required-reading file alongside the PRD for the Architect dispatch.
- **Vendor-name appearance "OmniRoute" (Finding 5.4)**: future Founder vendor change would require a PRD wording update. Mitigation: vendor change is out of v0.1 scope; Architect can handle when it occurs.
- **Future PRD revision likely**: § 11 line 255 explicitly anticipates that the Architect pass may discover ARCH-001 needs to bump to v0.3.0 and that HERMES-RUNTIME-CONTRACT / OPERATIONAL-STATE-STORE may need extension before SELF-DEPLOYMENT-CONTRACT can be finalized. If those discoveries reveal product-level questions (rather than purely architectural ones), a PRD-001 v0.3.0 may be required after the Architect pass. This is anticipated and is not a v0.2.1 risk.

## 17. Founder Approval

- **Founder approval required**: yes (per `docs/questions/QUESTIONS-001-bootstrap.md`: "Always ask founder after CI and Reviewer pass in v0.1").
- **Founder approval status**: pending. PR #83 cannot be merged until this review (RV-SPEC-009) is itself merged into `main` and the Founder approves PR #83.
- **Next step per the documented pipeline (verdict pass)**: Founder merges RV-SPEC-009, then Founder merges PR #83 (PRD-001 v0.2.1 + QUESTIONS-002), then the Architect self-deployment pass starts per `docs/backlog/TKT-NEW-self-deployment-architect-pass.md` with the expanded scope (multi-Hermes + upstream abstraction + escalation policy) recorded in PRD § 11. TKT-011 remains gated behind the Architect pass.
