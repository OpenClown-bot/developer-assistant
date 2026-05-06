---
id: RV-SPEC-012
version: 0.1.0
status: complete
verdict: pass_with_changes
review_target: PR-88
review_type: spec
reviewer_model: kimi-k2.6
created: 2026-05-06
---

# 1. PR Identification

| Attribute | Value |
|-----------|-------|
| PR Number | #88 |
| PR Title | ARCH-001 v0.3.0 boundary surfaces (PR-C/4) |
| Author | architect |
| Review Date | 2026-05-06 |
| Review Branch | `rv/spec-012-pr-88` |

# 2. Review Scope

**Declared scope (review brief):** 6 files for PR-C/4 — ARCH-001.md v0.3.0, ESCALATION-POLICY.md, MODEL-CATALOG.md, UPSTREAM-ADAPTER-CONTRACT.md, ADR-007, ADR-008.

**Actual scope inspected:** 13 changed files (+2,913 / −89):
- `docs/architecture/ARCH-001.md` v0.3.0 (modified)
- `docs/architecture/ESCALATION-POLICY.md` v0.1.0 (new)
- `docs/architecture/MODEL-CATALOG.md` v0.1.0 (new)
- `docs/architecture/UPSTREAM-ADAPTER-CONTRACT.md` v0.1.0 (new)
- `docs/architecture/MULTI-HERMES-CONTRACT.md` v0.1.0 (new)
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` v0.1.0 (new)
- `docs/architecture/RESEARCH-001-hermes-and-openclaw-ecosystems.md` (new)
- `docs/architecture/adr/ADR-004-deployment-mechanism.md` v0.1.0 (new)
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` v0.1.0 (new)
- `docs/architecture/adr/ADR-006-ipc-and-state-mediation.md` v0.1.0 (new)
- `docs/architecture/adr/ADR-007-upstream-adapter-shape.md` v0.1.0 (new)
- `docs/architecture/adr/ADR-008-escalation-classifier.md` v0.1.0 (new)
- `docs/architecture/adr/ADR-009-model-assignment-and-fallback.md` v0.1.0 (new)

**Baselines used for comparison:**
- PRD-001 v0.2.1 §6, §9, §12, §13
- AGENTS.md (role-model mapping)
- `docs/orchestration/SESSION-STATE.md` (2026-05-05 model assignments)
- ARCH-001.md v0.2.0 on `main`
- HERMES-RUNTIME-CONTRACT.md, HERMES-SKILL-ALLOWLIST.md, OPERATIONAL-STATE-STORE.md, GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md on `main`
- ADR-001, ADR-002, ADR-003 on `main`

# 3. Findings

## Finding 1 — Scope bundling (process)
**Severity:** Medium  
**Status:** Not blocking, but requires documentation  
**Description:** The review brief declares PR #88 as "PR-C/4" with 6 files focused on boundary surfaces (escalation policy, model catalog, upstream adapter). The actual diff contains 13 files, bundling content from PR-A (self-deployment — SELF-DEPLOYMENT-CONTRACT, ADR-004) and PR-B (multi-Hermes runtime — MULTI-HERMES-CONTRACT, ADR-005, ADR-006) together with PR-C.  
**Impact:** Bundling multiple PRs into one review makes it harder to assess whether each individual PR meets its own acceptance criteria. The content itself is correct, but the process traceability is degraded.  
**Recommendation:** Accept for this review, but note in project state that PR #88 is effectively a consolidated "Architect pass" covering PR-A, PR-B, and PR-C together, consistent with PRD-001 §11 sequencing implication.

## Finding 2 — MODEL-CATALOG.md uses placeholder identifiers inconsistent with approved Founder assignments
**Severity:** High (required change)  
**Status:** Must fix before Executor pass  
**Description:** MODEL-CATALOG.md §3 states it "adopts the Founder-set 2026-05-05 model assignment as the default v0.1 catalog." However, the identifiers in Table 1 are placeholder names (`gpt-5.1`, `claude-sonnet-4.5`, `claude-opus-4.5`, `gemini-2.5-pro`, `deepseek-v3.5`) that do **not** match the Founder-approved assignments recorded in SESSION-STATE.md and AGENTS.md (`GPT-5.5 High`, `DeepSeek V4 Pro`, `Kimi K2.6`, `Qwen 3.6 Plus`, `GLM 5.1`).  
**Impact:** An Executor implementing against this catalog will use wrong model identifiers at runtime, causing API call failures or routing to non-existent models.  
**Recommendation:** Update MODEL-CATALOG.md Table 1 to use the exact identifiers from SESSION-STATE.md / AGENTS.md, or add an explicit mapping column showing "Catalog ID → Runtime ID". Ensure the catalog stays in sync with any future Founder reassignments via a documented maintenance hook.

## Finding 3 — ESCALATION-POLICY.md §5 delegates concept-deviation classification to an auxiliary LLM without deterministic specification
**Severity:** High (required change)  
**Status:** Must fix before Executor pass  
**Description:** PRD-001 §13.1 requires an escalation policy that "operationalizes" the rule: escalate when a decision deviates from the original concept OR risks breaking committed scope/state. ESCALATION-POLICY.md §5 implements the "breaking something" limb with clear, deterministic thresholds (force-push, data loss, token revocation). However, the "deviation from concept" limb is delegated to an **auxiliary LLM classifier** (§5.1: "an auxiliary LLM classifier evaluates the deviation limb"). The policy does not specify: (a) the exact location/format of the "static block of text" representing the intake-fixed concept, (b) how that block is kept in sync with intake, (c) deterministic fallback rules when the classifier is ambiguous, or (d) prompt structure that would allow an Executor to implement this as code without itself invoking an LLM at runtime.  
**Impact:** The review instructions explicitly flag "the LLM decides" as a gap: PRD requires a specification an Executor can implement as deterministic code or as a bounded, testable algorithm. Relying on an opaque auxiliary LLM call for a safety-critical policy creates an untestable, non-reproducible gate.  
**Recommendation:** Either (1) replace the auxiliary-LLM limb with a deterministic rules engine (e.g., a deny-list of disallowed actions + an allow-list of pre-approved patterns, with a deterministic scoring function), or (2) if an LLM classifier is architecturally required, fully specify its prompt template, input schema, output schema, confidence threshold, fallback behavior, and model assignment from the catalog, so the Executor can implement it as a bounded, versioned component.

## Finding 4 — ESCALATION-POLICY.md lacks concept-block location and sync specification
**Severity:** Medium (required change)  
**Status:** Must fix alongside Finding 3  
**Description:** ESCALATION-POLICY.md §5.1 states the classifier receives "the PRD's intake-time concept summary (a static block of text)" but does not specify where that block lives in the repository or operational state store, what format it uses, who writes it during intake, or how it is versioned and synchronized when the Founder updates the concept.  
**Recommendation:** Add a subsection specifying: (a) the file path or state-store key for the concept block, (b) the schema (e.g., a structured YAML frontmatter with fields for target user, success criteria, tech-stack constraints, budget constraints), (c) the writer (Orchestrator during Journey 1/2 intake), and (d) the versioning rule (versioned alongside MODEL-CATALOG.md).

## Finding 5 — Positive: UPSTREAM-ADAPTER-CONTRACT.md fully covers PRD §13.3 requirements
**Severity:** Informational  
**Description:** UPSTREAM-ADAPTER-CONTRACT.md addresses all five required operations (inbound message, outbound message, approval prompt, identity binding, session continuity) and explicitly preserves forward compatibility for the OpenClaw v0.2 adapter as a parallel implementation. The abstraction is clean and does not require a core rewrite to add a second adapter.

## Finding 6 — Positive: ADR-007, ADR-008, ADR-009 meet quality standards
**Severity:** Informational  
**Description:** All three ADRs present three or more options, include decision-criteria mapping tables, and provide clear rationale with consequences. ADR-009 correctly maps model roles to the catalog and includes fallback rules.

## Finding 7 — Positive: MULTI-HERMES-CONTRACT.md addresses PRD §13.2 composition requirements
**Severity:** Informational  
**Description:** The contract covers IPC mechanism (repository-mediated state store + event bus), memory isolation (strict per-role with bounded context), supervisor strategy, and restart/recovery for per-runtime memory and self-learning state. It is consistent with PRD §13.2 and §11 multi-Hermes mandate.

## Finding 8 — Positive: ARCH-001 v0.3.0 successfully absorbs Section 13 mandates
**Severity:** Informational  
**Description:** ARCH-001 v0.3.0 revises the v0.2.0 baseline to incorporate multi-Hermes composition, upstream entry-point abstraction, escalation policy artifact, and expanded self-deployment scope (install/health/rollback/upgrade for N runtimes). The version bump and changelog are correctly documented.

# 4. Verdict

**Recommended Verdict:** `pass_with_changes`

The PR delivers a coherent, consolidated "Architect pass" that successfully absorbs all PRD-001 v0.2.1 §13 mandates (multi-Hermes, upstream composability, escalation policy, model catalog, expanded self-deployment). The architecture is sound and the ADRs meet quality standards. However, two high-severity findings (MODEL-CATALOG placeholder identifiers; ESCALATION-POLICY auxiliary-LLM classifier without deterministic specification) and one medium-severity finding (concept-block location/sync) must be resolved before the Executor pass. The scope-bundling process issue is noted but does not block approval.

**Conditions for pass:**
1. Fix MODEL-CATALOG.md to use Founder-approved model identifiers or add an explicit mapping.
2. Replace or fully specify the auxiliary-LLM classifier in ESCALATION-POLICY.md §5 so it is implementable as deterministic/testable code.
3. Add concept-block location, format, writer, and sync specification to ESCALATION-POLICY.md §5.1.

# 5. Additional Notes

- The PR title says "PR-C/4" but the diff is effectively a full Architect pass covering PR-A + PR-B + PR-C. This is acceptable per PRD-001 §11 sequencing implication ("the Architect pass simply has more in scope than v0.2.0 implied"), but future PRs should aim for smaller, independently reviewable units.
- ADR-004, ADR-005, ADR-006 were not declared in the review brief but are present in the diff. They are reviewed as part of the bundled scope and found adequate.
- No secrets, credentials, or `.env` files were introduced in the diff.
- All new files are within the architecture write zone (`docs/architecture/` and `docs/architecture/adr/`).

# 6. Sign-off

| Field | Value |
|-------|-------|
| Reviewer | Reviewer (Kimi K2.6) |
| Date | 2026-05-06 |
| Verdict | `pass_with_changes` |
| Blocking findings | 2 High + 1 Medium (Findings 2, 3, 4) |
