---
id: TKT-039
version: 0.1.0
status: draft
arch_ref: ARCH-002@0.1.0
adr_ref: ADR-018@0.1.0
updated: 2026-05-10
---

# TKT-039: Concept-Anchor Freshness Ledger + validate_docs check + Reviewer context injection

## 1. Scope

Implement ADR-018 (Anti-Drift Concept-Anchor Freshness Ledger). Three coupled components:

(1) Author the new ledger artifact `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` (Architect-zone authorship; this Executor ticket is permitted to author Architect-zone documents whose content is fully specified by ADR-018 § Decision Component 1).
(2) Extend `scripts/validate_docs.py` with two new checks: anchor membership (Check 1, hard CI fail) and forward consistency (Check 2, soft CI warning per Q-ARCH-002-02 v0.1 default).
(3) Extend the `dev-assist-reviewer-rubric` skill with a context-injection branch that reads the ledger at Reviewer-dispatch time and includes relevant anchors in the Reviewer LLM's prompt.

Optionally (env-flag-gated) emit `peek`-modality escalation when Check 2 fires, per ADR-018 § Decision Component 4.

This ticket depends on TKT-038 because the Reviewer rubric extension layers on top of TKT-038's gate-tag work; the Reviewer rubric edit point is the same skill file.


## 2. Non-scope

- Strict (CI-fail) Check 2 — Q-ARCH-002-02 Founder decision required.
- Automated `Last reviewed` bumping — manual Architect process for v0.1; an automated bump on every Architect cycle PR is a v0.2+ enhancement.
- Anchor-evolution analytics (which anchors get edited most often) — out of scope.
- Bidirectional check (every `PROJECT-CONCEPT.md` § 2 anchor must be asserted by ≥1 contract) — would over-constrain; some anchors are operational-only.


## 3. Required Context

- ADR-018 v0.1.0 § Decision (final spec).
- ADR-017 v0.1.0 (for peek-modality emission path).
- ARCH-002 v0.1.0 § 5.6 (Q-RESEARCH-002-06 answer), § 6.5 (amendment).
- `PROJECT-CONCEPT.md` v0.1.0 § 2 (concept anchor block — anchor IDs source of truth).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.5 (Reviewer skill loadout).
- `scripts/validate_docs.py` (current implementation).
- TKT-038 (Reviewer rubric extension baseline — gate-tag work merged first).


## 4. Acceptance Criteria

**AC-1.** `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` v0.1.0 (status: draft, arch_ref: ARCH-002@0.1.0, adr_ref: ADR-018@0.1.0) authored with the schema from ADR-018 § Decision Component 1. Initial seeding covers the 13 long-lived contract documents in scope at deployment time:
  - ARCH-001 v0.3.0
  - MULTI-HERMES-CONTRACT v0.2.1
  - HERMES-RUNTIME-CONTRACT v0.2.0
  - HERMES-SKILL-ALLOWLIST v0.1.2
  - ESCALATION-POLICY (post-TKT-037: v0.1.2)
  - PROJECT-CONCEPT v0.1.0
  - OPERATIONAL-STATE-STORE (post-TKT-036/037/038: v0.3.x)
  - OBSERVABILITY-CONTRACT v0.1.x
  - MODEL-CATALOG v0.1.1
  - UPSTREAM-ADAPTER-CONTRACT v0.1.x
  - SELF-DEPLOYMENT-CONTRACT v0.2.0
  - SANDBOX-CONTRACT v0.1.0 (post-TKT-035)
  - PRD-001 v0.2.1

  Each entry lists: `Contract document`, `Asserted anchor IDs`, `Last reviewed` (date Architect last verified the asserted anchors). Initial `Last reviewed` = 2026-05-10 for all.

**AC-2.** Alias table at top of CONCEPT-ANCHOR-FRESHNESS.md maps human-readable synonyms to canonical anchor IDs (e.g., `multi_hermes` → `multi_hermes_runtime_topology`). Initially small (≤ 10 aliases).

**AC-3.** `validate_docs.py` Check 1 (anchor membership, hard fail): every asserted anchor ID in the ledger maps to a current entry in `PROJECT-CONCEPT.md` § 2 (parsed from YAML) OR to an entry in the alias table. Mismatches → CI fail with line-precise error message.

**AC-4.** `validate_docs.py` Check 2 (forward consistency, soft warning): when a contract document listed in CONCEPT-ANCHOR-FRESHNESS.md is *modified* in a PR diff (file appears in `git diff --name-only origin/main..HEAD`), the PR body must contain a `## Concept Anchors Asserted` section listing the anchor IDs of the changed file from the ledger. Mismatches → CI **annotation warning** (merge allowed). Per Q-ARCH-002-02 v0.1 default = soft.

**AC-5.** `dev-assist-reviewer-rubric` skill extension: at Reviewer-dispatch time, the skill loader reads CONCEPT-ANCHOR-FRESHNESS.md, identifies the contract documents touched in the PR diff, collects the relevant anchors, and includes them in the Reviewer LLM prompt under a "Concept Anchors Context" section.

**AC-6.** Optional peek-modality emit: when Check 2 fires, env-flag `CONCEPT_ANCHOR_PEEK_EMIT=1` (default `0` = disabled) causes the workflow to emit a `peek`-modality escalation per ADR-017 with `trigger_kind='concept_anchor_unlisted'`. v0.1 ships disabled-by-default to avoid premature instrumentation; enable later if drift compliance is poor.

**AC-7.** `dev-assist-cli concept-anchors` new command: lists ledger entries; `--stale` flag shows contracts whose `Last reviewed` is > 90 days old. Output: tabular by default, `--json` flag for machine-readable.

**AC-8.** `tests/test_concept_anchor_ledger.py` covers: ledger membership Check 1 happy/fail paths; forward-consistency Check 2 happy/warn paths; alias resolution; Reviewer skill context-injection (mocked PR diff → expected anchor list); CLI `--stale` flag.

**AC-9.** Failure modes wired per ARCH-002 § 6.4: `concept_anchor_unlisted` (Check 2 warning), `concept_anchor_orphan` (Check 1 fail), `concept_anchor_alias_collision` (alias table duplicate ID — schema-validation fail at ledger parse time).

**AC-10.** `python3 scripts/validate_docs.py` passes (Checks 1+2 self-apply to the ledger artifact itself).


## 5. Allowed Files

- `docs/architecture/CONCEPT-ANCHOR-FRESHNESS.md` (NEW; Architect-zone authorship justified per § 1)
- `scripts/validate_docs.py` (extend with two new checks)
- `docs/architecture/shared-skills/dev-assist-reviewer-rubric/SKILL.md` (extend with context-injection branch)
- `src/cli/concept_anchors.py` (NEW)
- `tests/test_concept_anchor_ledger.py` (NEW)


## 6. Test Strategy

Test pyramid for this ticket:

- **Unit (`tests/test_concept_anchor_ledger.py`):** Check 1 (anchor membership) happy path (all asserted IDs map to PROJECT-CONCEPT.md § 2 entries) and fail path (orphan ID); Check 2 (forward consistency) happy path (PR body has anchors-asserted section) and warn path (PR body missing); alias resolution (alias-table-mapped ID resolves correctly); duplicate-alias detection at ledger parse time.
- **Reviewer skill context-injection:** mocked PR diff with changed contract files → expected anchor list injected into Reviewer LLM prompt; truncation at 500 token cap tested.
- **CLI (`dev-assist-cli concept-anchors`):** lists ledger entries; `--stale` flag filters by `Last reviewed > 90 days`; tabular and JSON output.
- **Self-application:** validate_docs Check 1 + Check 2 self-apply to the ledger artifact (CONCEPT-ANCHOR-FRESHNESS.md is a contract document and lists itself).


## 7. Risk Notes

Primary risk: false positives on Check 2 (PR amends a contract document but the amendment doesn't actually change concept-anchor claims, e.g., a typo fix or formatting tweak). Mitigation: Check 2 is soft (CI warning, not fail) per Q-ARCH-002-02 v0.1 default. Secondary risk: ledger maintenance burden — if anchors evolve faster than the Architect updates the ledger, drift accumulates silently. Mitigation: `Last reviewed > 90 days` stale-flag in CLI surfaces neglected entries; Architect-cycle dispatch in TO can include a freshness check as a routine step. Tertiary risk: peek-modality emit env-flag accidentally enabled in prod without operator awareness. Mitigation: default OFF; documented in MULTI-HERMES-CONTRACT.md amendment with rationale.


## 8. Spec Amendment Notes

Hard rules for this ticket (governance constraints inherited from ARCH-002 + the source ADR; Executor MUST observe):


- Do NOT modify `PROJECT-CONCEPT.md` § 2 — that's the Architect's source of truth and outside this ticket's write zone (ADR-018 only consumes it).
- Do NOT modify ADR-018 — Architect-cycle authoritative.
- Check 2 MUST stay soft (warning-only) per Q-ARCH-002-02 v0.1 default; promotion to hard requires Founder decision and a follow-up Architect cycle.
- Reviewer prompt context-injection MUST be bounded: no more than 500 tokens of anchor content per dispatch (truncate with explicit "...truncated; see CONCEPT-ANCHOR-FRESHNESS.md" notice if exceeded).
- Peek-modality emission MUST be env-flag-gated and OFF by default in v0.1.


## 9. Cross-references

- ADR-018 v0.1.0 (Concept-anchor freshness ledger).
- ADR-017 v0.1.0 (for peek-modality emit path).
- ARCH-002 v0.1.0 § 5.6, § 6.5.
- RESEARCH-002 § 6.7 (CLITrigger wiki injection), § 6.10 (OpenHands governance), § 7.7 (failure modes).
- `PROJECT-CONCEPT.md` v0.1.0 § 2.
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.5.
- `scripts/validate_docs.py`.
- TKT-038 (Reviewer rubric baseline post gate-tag work).


## 10. Execution Log

(Reserved for Executor cycle.)
