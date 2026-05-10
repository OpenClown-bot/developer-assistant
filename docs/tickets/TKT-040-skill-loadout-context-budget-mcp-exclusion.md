---
id: TKT-040
version: 0.1.0
status: draft
arch_ref: ARCH-002@0.1.0
updated: 2026-05-10
---

# TKT-040: Skill Loadout Context Budget Documentation + MCP Exclusion

## 1. Scope

Two small, related documentation-and-validation changes from ARCH-002 § 6.3:

(A) Add a single "Context budget" line per role table in `MULTI-HERMES-CONTRACT.md` § 5 (five role tables: Orchestrator, Business Planner, Architect, Executor, Reviewer) stating the prompt + skills + plugins context cap (e.g., "Context budget: prompt (~3.5k tokens) + skills loadout (~2k tokens) + plugins (~0.5k tokens) ≈ 6k tokens of static context per dispatch"). Per OpenCastle's context-budget vocabulary (`opencastle@18c6f2cf4e5c:README.md:L110-L114`).

(B) Add a one-paragraph subsection at `MULTI-HERMES-CONTRACT.md` § 5.0 stating that skill names matching `mcp:*` or `mcp/*` (or any path under `/srv/devassist/shared-skills/mcp/`) are excluded at load time. Implement the exclusion in the `dev-assist-work-queue` plugin's skill-loader path (defensive boundary aligned with the existing `ARCH-001.md` § 21 exclusion of MCP HTTP servers from v0.1). Per ORCH's MCP exclusion (`ORCH@0c0694896b3a:CLAUDE.md:L86-L93`).

This ticket has no dedicated ADR — it's a documentation amendment plus a one-line plugin-loader defensive check, supported directly by ARCH-002 § 6.3 amendment proposal. No new mechanism, no new schema.


## 2. Non-scope

- OpenCastle-style on-demand skill loading (loaded only when a tool call actually triggers the skill) — Future Possibility per ARCH-002 § 10; v0.1 keeps eager-load-on-init.
- Context-budget enforcement (refuse to load if prompt + skills + plugins exceed cap) — out of scope; v0.1 documents the cap, doesn't enforce.
- Skill-name versioning at the loader level — out of scope; ALLOWLIST § 4 already enforces version pinning.


## 3. Required Context

- ARCH-002 v0.1.0 § 3.5 (App-5), § 6.3 (amendment proposal).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.0 (custom skill allowlist), § 5.1-5.5 (per-role tables).
- `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 2 (deny-by-default), § 4 (allowlist).
- `ARCH-001.md` v0.3.0 § 21 (MCP HTTP servers exclusion baseline).
- `dev-assist-work-queue` plugin (skill loader path baseline).


## 4. Acceptance Criteria

**AC-1.** `MULTI-HERMES-CONTRACT.md` § 5.1 (Orchestrator), § 5.2 (Business Planner), § 5.3 (Architect), § 5.4 (Executor), § 5.5 (Reviewer) each receive a one-line "Context budget" footer below the existing skills tables, with role-specific token estimates derived from the actual prompt + skills + plugins token counts (measured during this ticket's implementation against the v0.1 prompt set).

**AC-2.** Token estimates are derived empirically: `python3 scripts/measure_role_context.py` (NEW helper script) computes prompt + skills + plugins token counts per role using the project's existing tokenizer (whichever Hermes uses; default cl100k_base or equivalent). Output committed as `docs/architecture/role-context-budgets.md` (NEW reference table).

**AC-3.** `MULTI-HERMES-CONTRACT.md` § 5.0 receives a new subsection § 5.0.1 "MCP exclusion at load time": a one-paragraph statement that skill names matching the `mcp:*`, `mcp/*` pattern, or paths under `/srv/devassist/shared-skills/mcp/`, are excluded at skill-loader init time. Cross-references `ARCH-001.md` § 21.

**AC-4.** `dev-assist-work-queue` plugin's skill-loader path implements the exclusion: at init time, iterate registered skills; reject any whose name matches the pattern with a structured journald log entry. The exclusion happens BEFORE skill-content load; rejected skills do not count against context budget.

**AC-5.** `tests/test_skill_loader_mcp_exclusion.py` covers: skill named `mcp:foo` rejected; skill named `mcp/bar/SKILL.md` rejected; skill at path `shared-skills/mcp/baz/SKILL.md` rejected; skill named `dev-assist-mcp-not-actually` *accepted* (must not match too greedily — the pattern is `mcp:*` or `mcp/*` or path-segment `/mcp/`, NOT substring `mcp`).

**AC-6.** `python3 scripts/validate_docs.py` passes.

**AC-7.** Backward compatibility: no skill currently in `MULTI-HERMES-CONTRACT.md` § 5 matches the exclusion pattern (verified by grepping the contract). Pre-existing `dev-assist-*` skills remain loaded normally.


## 5. Allowed Files

- `docs/architecture/MULTI-HERMES-CONTRACT.md` (§ 5.0 new subsection + § 5.1-5.5 context-budget footers)
- `docs/architecture/role-context-budgets.md` (NEW reference table)
- `scripts/measure_role_context.py` (NEW helper script)
- `src/work_queue/skill_loader.py` (extend — single-line exclusion check at init)
- OR `docs/architecture/shared-skills/dev-assist-work-queue/SKILL.md` (if the loader path is plugin-side rather than `src/`-side; Architect's call at implementation time)
- `tests/test_skill_loader_mcp_exclusion.py` (NEW)


## 6. Test Strategy

Test pyramid for this ticket:

- **Unit (`tests/test_skill_loader_mcp_exclusion.py`):** exclusion patterns: `mcp:foo` rejected, `mcp/bar` rejected, path `shared-skills/mcp/baz/SKILL.md` rejected; non-matches: `dev-assist-mcp-bridge` accepted, `dev-assist-classifier` accepted, `mcphelper` accepted (substring match must NOT trigger exclusion).
- **Integration:** start a runtime with the loader extension active; verify that no MCP-named skills load (none currently exist); verify that the structured journald log entry is emitted when an MCP-named skill would have been loaded (using a test fixture skill).
- **Tokenizer measurement:** `scripts/measure_role_context.py` runs against each role's prompt+skills+plugins set; output is a deterministic JSON report; numbers committed to `docs/architecture/role-context-budgets.md`.
- **Self-validation:** the new context-budget footers in MULTI-HERMES-CONTRACT.md § 5.1-5.5 carry numbers consistent with the empirical measurement (validate_docs.py optionally extends with a sanity check, gated behind an env flag).


## 7. Risk Notes

Primary risk: the MCP exclusion pattern over-matches and rejects legitimate skills with `mcp` substring (e.g., a future `dev-assist-mcp-bridge` for v0.2+ MCP bridge surface). Mitigation: pattern is path-segment / prefix strict (`mcp:*`, `mcp/*`, segment `/mcp/`), NOT substring. Secondary risk: tokenizer used for context-budget measurement may not match Hermes' actual tokenizer, producing misleading numbers. Mitigation: measurement methodology documented in `docs/architecture/role-context-budgets.md` with note on tokenizer choice; if Hermes uses a different tokenizer, the numbers are still informative as a relative comparison across roles.


## 8. Spec Amendment Notes

Hard rules for this ticket (governance constraints inherited from ARCH-002 + the source ADR; Executor MUST observe):


- Do NOT add new external pip dependencies for the tokenizer; use whatever Hermes uses (verify at implementation time and adapt).
- Do NOT enable any MCP-named skill — the exclusion is forward-only defensive; existing skills are unchanged.
- Context-budget numbers MUST be empirically measured, not estimated from prompt-line-count or character-count.
- Exclusion pattern MUST NOT be a substring match on `mcp` (false positive risk: `dev-assist-mcp-bridge` future-name); it MUST be path-segment / prefix-pattern strict.


## 9. Cross-references

- ARCH-002 v0.1.0 § 3.5 (App-5), § 6.3 (amendment proposal).
- RESEARCH-002 § 6.5 (OpenCastle context-management), § 6.2 (ORCH skill loader MCP exclusion).
- `opencastle@18c6f2cf4e5c:README.md:L110-L114` (context-budget source).
- `ORCH@0c0694896b3a:CLAUDE.md:L86-L93` (MCP exclusion source).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 5.
- `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 2 + § 4.
- `ARCH-001.md` v0.3.0 § 21.


## 10. Execution Log

(Reserved for Executor cycle.)
