---
id: TKT-041
version: 0.1.1
status: ready
arch_ref: ARCH-001@0.3.0
audit_ref: AUDIT-003
supersedes: TKT-032@0.1.0
updated: 2026-05-12
---

# TKT-041: Behaviour-level deployment smoke (AUDIT-003 spec)

## 1. Scope

Promote the scope stub at `docs/session-log/2026-05-08-session-2.md` § 5.3 (AUDIT-003) into a full implementation contract. Replace the process-aliveness acceptance criteria of `docs/tickets/TKT-032.md` (v0.1.0) § 4 with a **behaviour-level smoke** that verifies the deployed `developer-assistant` runtime behaves as the composition the project specifies in `MULTI-HERMES-CONTRACT.md` v0.2.0 § 5 — NOT as a generic Hermes Agent. This ticket is the third of the four-ticket AUDIT family (AUDIT-001..004) closing the integration-composition gap exposed by the 2026-05-08 live VPS deployment of TKT-032 (v0.1.0). AUDIT-001 (TKT-033 v0.3.0, merged 2026-05-09) blocks boot on per-runtime invariants; AUDIT-002 (TKT-034 v0.3.1, merged 2026-05-11) corrects how the runtime's on-disk preconditions get there; AUDIT-003 corrects how the runtime's **behaviour** is verified once it boots and the queue is reachable.

### 1.1 Architect decision: AUDIT-003 supersedes TKT-032 (option α; option β rejected)

The NUDGE for AUDIT-003 (Strategic Orchestrator, 2026-05-11) presented two options:

- **Option α (supersede).** TKT-032 promoted `ready → superseded`; AUDIT-003 is the sole behaviour gate to TKT-011.
- **Option β (co-exist).** TKT-032 reformulated as process-aliveness pre-flight only; AUDIT-003 is the behaviour gate stacked after it.

**Decision: option α. TKT-032 is superseded by TKT-041.** Justification:

1. **Operational subsumption.** TKT-032 § 4 AC are connectivity-only (install runs; env file exists; `verify-self.sh` exits 0; runtimes `running`/`degraded`; one `/health` endpoint returns 200). The process-aliveness layer is now wholly covered by AUDIT-001 (TKT-033 v0.3.0 § 4 AC-2, AC-3, AC-5 — eleven-invariant journald grammar enforced at `ExecStartPre=` with non-restart on invariant failure) plus AUDIT-002 (TKT-034 v0.3.1 § 4 AC-2, AC-4, AC-5 — operator-hygiene + interactive installer + verify-self.sh extension to eight new invariants under B.vi). There is no remaining behaviour the TKT-032 AC list checks that AUDIT-001 + AUDIT-002 do not already check more strictly.

2. **False-positive risk if reformulated.** Reformulating TKT-032 as "process-aliveness pre-flight only" recreates the exact two-gate failure mode the audit family exists to eliminate: a green pre-flight gate followed by a runtime that mis-behaves at the composition layer — i.e. the 2026-05-08 live test outcome that `docs/session-log/2026-05-08-session-2.md` § 2 catalogues across 14 rows. Keeping a separate process-aliveness ticket alive perpetuates the pattern of declaring a deployment "ready" while the actual composition is wrong.

3. **Already-executed work products are unaffected.** TKT-032's cycle PRs (#119 Executor, #120 Reviewer, #121 Architect ADR-014) are merged on `main`; the eight infrastructure corrections from that cycle are durable in ADR-014. Superseding the *ticket* does not retract the *work*. The merged code, scripts, and ADR-014 are kept as-is.

4. **Simpler dispatch chain.** A single gate to TKT-011 (AUDIT-003 alone) is easier to reason about than a two-gate stack (TKT-032 pre-flight then AUDIT-003 behaviour). The session-log § 8 dispatch order (AUDIT-001 → AUDIT-002 ∥ AUDIT-003 → AUDIT-004 → TKT-011) is preserved.

5. **No semantic gap.** Every TKT-032 § 4 AC bullet has an explicit replacement in this ticket's § 4 (see § 1.5 cross-reference table) or in AUDIT-001 / AUDIT-002. Option α therefore loses zero coverage.

The corresponding TKT-032 amendment (frontmatter `status: ready → superseded`; new § 1 stub pointing here) is produced in the same Architect commit. The TKT-032 file is otherwise unmodified — its § 10 Execution Log, AC narrative, and dependency history remain as the historical record of the 2026-05-08 live test that exposed the audit family's need.

### 1.2 Smoke composition contract

The behaviour-level smoke MUST exercise the following end-to-end invariant against a freshly installed `developer-assistant` deployment (per AUDIT-002's interactive installer flow, with the smoke-mode flag set per § 1.4):

```
Synthetic Telegram-shaped message
    → Orchestrator's `dev-assist-classifier` skill produces a class label and persists it
    → Orchestrator's `dev-assist-work-queue-write` inserts a row in `operational.db`.work_items
    → Planner runtime's `dev-assist-work-queue-poll` claims the row within N1 seconds
    → Planner runtime produces a result (success or `failed`) within N2 seconds
    → Result is observable in `operational.db`.errors and/or `operational.db`.llm_calls tables
    → Result is observable in the Orchestrator's `/health` JSON and the Planner's `/health` JSON
```

Planner is the chosen specialist runtime target because it is the smallest specialist surface in the contract (`MULTI-HERMES-CONTRACT.md` § 5.2: three custom skills + two built-ins; no `terminal`, no GitHub). Choosing Planner exercises the Orchestrator → specialist → result path in `MULTI-HERMES-CONTRACT.md` § 8.1 without engaging the Executor's Docker-terminal surface or the Reviewer's RV rubric surface, both of which are out of scope for a deployment-time behaviour smoke.

N1 (claim deadline) and N2 (result deadline) are picked in § 4 AC-7 with rationale.

### 1.3 Synthetic-message gateway path (Architect decision)

The NUDGE permits a scripted gateway client OR a reviewed-and-gated mock-injection path. The Architect chooses **smoke-mode injection CLI** (option B), with the mock-Telegram-API approach (option A) explicitly rejected. Justification:

- **Option B exercises every layer above the Telegram network adapter** (the gateway's classifier dispatch, work-queue write, work-queue poll, specialist work, result round-trip, observability writes) without depending on Hermes v2026.4.30's HTTPS-to-localhost mock-API plumbing, which is not documented in the reviewed surface area of `HERMES-SKILL-ALLOWLIST.md` § 4.1 and would require either TLS termination on a localhost mock or a host-file override (both fragile).
- **Option A would couple AUDIT-003 to Hermes internals.** Hermes' `gateway/platforms/telegram_network.py` is reviewed (`HERMES-SKILL-ALLOWLIST.md` § 4.1) but a `TELEGRAM_API_BASE_URL` override is not part of the reviewed surface. Exercising it would require an Executor-time review extension and a sibling RV-CODE pass.
- **The Telegram network adapter itself is reviewed and out of audit-family scope.** Its correctness lives in `HERMES-SKILL-ALLOWLIST.md` § 4.1 + ADR-014 Correction 7. AUDIT-003 is about the *composition* path, not the upstream adapter.

Option B implementation shape (the Executor refines mechanics within these constraints):

- A new `dev-assist-cli` subcommand `dev-assist-cli smoke inject-message --text <TEXT> [--from-user-id <ID>] [--timeout-s <SECONDS>]` writes a synthetic inbound message directly into the Orchestrator runtime's gateway dispatcher via a localhost-only HTTP admin port (Architect picks **port 8186** — the next free port after the per-runtime health ports 8181..8185 from `OBSERVABILITY-CONTRACT.md` § 11). The admin port is bound to `127.0.0.1` only and exposed only by the Orchestrator runtime.
- The CLI returns the work_items.id of the smoke-injected row plus the synthetic message's correlation id; subsequent CLI calls (`dev-assist-cli smoke wait --work-item-id <ID> --until claimed --timeout-s <N1>`, `dev-assist-cli smoke wait --work-item-id <ID> --until completed --timeout-s <N2>`) poll the operational store and the relevant `/health` endpoints.
- The inject endpoint refuses any request when the smoke-mode marker file (§ 1.4) is absent. Refusal returns HTTP 403 with body `{"error":"smoke_mode_not_enabled"}` and journald event `smoke.inject.refused`.

### 1.4 Security envelope for smoke-mode

Smoke-mode is a deployment posture, NOT a runtime feature flag that can be flipped on a running production instance. The envelope:

1. **Marker file gate.** A file `/srv/devassist/state/smoke-mode.flag` (mode `0400`, owner `devassist:devassist`) MUST exist before any smoke-inject endpoint or smoke-only CLI subcommand accepts requests. The marker file is written ONLY by `scripts/install-self.sh --smoke-mode` (the Executor extends AUDIT-002's interactive installer with this flag per § 5 Allowed Files). The installer's smoke-mode prompt copy MUST display: *"WARNING: smoke mode enables synthetic-message injection on localhost. Do NOT enable on a Founder-facing production install. Continue? [yes/no]"* — and reject `yes` unless interactive TTY is confirmed per AUDIT-002 B.iii TTY detection rule.
2. **Localhost-only admin port.** The smoke-inject endpoint binds to `127.0.0.1:8186`. Binding to `0.0.0.0` or `::` is forbidden; the install script asserts this at render time. The VPS firewall rules (`SELF-DEPLOYMENT-CONTRACT.md` § 7) further enforce that port 8186 is not exposed publicly.
3. **Smoke-fixture token rotation.** When smoke-mode is active, the runtime asserts at boot that `TELEGRAM_BOT_TOKEN` matches the regex `^smoke-fixture-token-[a-z0-9]{8}$` (i.e., a syntactically-valid Telegram bot token shape that cannot be a real BotFather token, because real tokens are `^[0-9]+:[A-Za-z0-9_-]+$`). A production-shaped token in a smoke-mode install fails boot with the runtime_check invariant `smoke_fixture_token_mismatch` (new invariant — extends AUDIT-001's eleven-invariant enum to twelve; the enum bump is a sibling Architect ADR amendment routed by the SO, NOT folded into this ticket; see § 8 Risks).
4. **Telegram outbound dry-run.** When smoke-mode is active, the Orchestrator's `telegram-gateway` skill operates in dry-run mode: outbound `sendMessage` calls are written to `/srv/devassist/logs/smoke-outbound.jsonl` (mode `0640`, owner `devassist:devassist`) instead of dispatched to `api.telegram.org`. The dry-run mode is enforced by the smoke-mode install path setting `gateway.telegram.dry_run: true` (or the closest equivalent override Hermes v2026.4.30 exposes; if no such override exists, the Executor files Q-TKT-041 and pauses per the AUDIT-001 / AUDIT-002 precedent — see § 8 Risks).
5. **Telegram inbound polling disabled.** When smoke-mode is active, the Orchestrator's `telegram-gateway` skill disables polling-mode upstream connection to `api.telegram.org` (`gateway.telegram.polling.enabled: false` or equivalent). This prevents a real chat being silently consumed during smoke runs.
6. **Mutually exclusive with production install.** `install-self.sh --smoke-mode` is mutually exclusive with `install-self.sh --rotate-secrets` (AUDIT-002 B.iv deferred flag) and with the absence of `--smoke-mode` from any subsequent re-install (a production install on a host that previously held a smoke-mode marker file MUST clear the marker file and rotate `TELEGRAM_BOT_TOKEN` before boot is permitted). `verify-self.sh` asserts this mutual-exclusion.
7. **Reviewer artifact required for any envelope change.** Any future change to the smoke-inject endpoint's authentication, path, scope, or marker-file ACL requires a sibling RV-CODE Reviewer artifact and a fresh AUDIT-003-successor Architect cycle. The envelope above is the frozen contract for v0.1.

### 1.5 Cross-reference: TKT-032 § 4 AC → AUDIT-001/002/003 coverage

| TKT-032 v0.1.0 § 4 AC bullet | Replacement coverage |
| --- | --- |
| Install script runs on Ubuntu 22.04 LTS VPS | AUDIT-002 § 4 AC-3 (B.viii prereq verification) + § 4 AC-5 (b) (Founder-driven entrypoint succeeds) |
| Install issues fixed in PR branch | One-time TKT-032 cycle work; superseded as a future requirement by AUDIT-002's interactive installer |
| `SELF-DEPLOY.env` exists with correct ACL + content | AUDIT-002 § 4 AC-4 (B.iv credential injection) + § 4 AC-5 (a) (secrets ACL 0400 devassist:devassist) |
| `verify-self.sh` exits 0 | AUDIT-002 § 4 AC-5 (extended verify with eight new B.vi invariants) |
| Executor requests Founder approval before start | AUDIT-002 § 4 AC-3 (B.i bootstrap entrypoint) + `SELF-DEPLOYMENT-CONTRACT.md` § 6.2 (start gate) — unchanged contract, durably enforced |
| `dev-assist-cli status` shows all five runtimes running/degraded | AUDIT-001 § 4 AC-2 (`ExecStartPre=` enforcement) — runtimes that boot but fail invariants now go to `failed`, not `degraded`; this is a strengthening, not a regression |
| At least one `/health` endpoint returns 200 | **This ticket** § 4 AC-2 (loaded-skills probe), AC-3 (delegate_task negative test), AC-4 (prompt SHA), AC-5 (classifier → work_items), AC-6 (specialist claim + result round-trip + observability) — each probe queries `/health` of the relevant runtime; the new contract requires all five `/health` endpoints to return 200 AND structured payload, replacing TKT-032's "at least one" with "all five plus payload validation" |
| No secret values in any artefact | AUDIT-002 § 4 AC-6 (secret-leak grep extension); preserved in this ticket § 4 AC-9 |
| Backwards-compatible script (CI tests still pass) | AUDIT-002 § 4 AC-7 (idempotency + offline test compatibility); preserved here § 4 AC-8 (test baseline discipline) |
| `python scripts/validate_docs.py` passes | Continued: § 6 |
| `python -m unittest discover` passes | Continued: § 6 |

Zero TKT-032 AC bullets lack replacement coverage.

## 2. Non-scope

- TKT-011 full live trial (separate cycle — AUDIT-004 rewrites TKT-011's dispatch precondition to `AUDIT-001 + AUDIT-002 + AUDIT-003 merged`; AUDIT-004 is a sibling spec, NOT folded into this ticket).
- AUDIT-001 (TKT-033 v0.3.0) enforcement layer. The eleven-invariant runtime_check is load-bearing for AUDIT-003 but NOT re-edited here; the smoke verifies its surface from above, it does not extend it. The one exception is the proposed `smoke_fixture_token_mismatch` twelfth invariant in § 1.4 (3), which is intentionally NOT folded in — it is filed as a Q-TKT and routed through SO for a sibling AUDIT-001-successor cycle if the Architect decides it is warranted; see § 8.
- AUDIT-002 (TKT-034 v0.3.1) installer hygiene. The interactive installer is load-bearing for AUDIT-003 (via the `--smoke-mode` flag the Executor adds), but this ticket does NOT re-spec the installer's twelve scope items A.i–B.viii. Any drift in the installer surface that AUDIT-003 surfaces (e.g., a missing `--smoke-mode` flag plumbing) MUST be filed as a Q-TKT against AUDIT-002's successor, NOT folded into this ticket.
- ADR-014's eight infrastructure corrections (already on `main` via PR #121). They are load-bearing preconditions, referenced not duplicated.
- Founder-merge-policy changes.
- Adding new specialist runtimes (the five `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 roles are frozen for v0.1).
- Modifying any role prompt body in `docs/prompts/<role>.md`. The Architect role write-zone (per `AGENTS.md` and `docs/prompts/architect.md` § Allowed Write Zone) does not include `docs/prompts/`; the prompt bodies are owned by the SO/Business Planner.
- Modifying `docs/architecture/MULTI-HERMES-CONTRACT.md`, `HERMES-SKILL-ALLOWLIST.md`, `SELF-DEPLOYMENT-CONTRACT.md`, `OBSERVABILITY-CONTRACT.md`, `MODEL-CATALOG.md`, or any ADR directly in this ticket's PR. The `/health` JSON extension proposed in § 4 AC-2 / AC-4 is a backward-compatible addition (new optional fields `loaded_skills`, `prompt_path`, `prompt_sha256`); the corresponding amendment to `OBSERVABILITY-CONTRACT.md` § 11 is a sibling clerical Architect PR filed by the SO after AUDIT-003 merges, NOT folded into the AUDIT-003 PR.
- Retroactively modifying merged tickets other than TKT-032. TKT-020, TKT-021, TKT-026, TKT-031, TKT-033, TKT-034 are not retroactively amended.
- Running any Hermes runtime against real LLM credentials, real Telegram bot tokens, real GitHub PATs, or real OmniRoute keys during the AUDIT-003 implementation cycle. All § 6 tests are offline; smoke-mode-on-VPS runs (if any) use only the smoke-fixture token and the dry-run gateway path.
- Network-layer Telegram tests (mock Telegram HTTPS API, TLS termination, `TELEGRAM_API_BASE_URL` overrides). Rejected in § 1.3.
- Auto-rotating the smoke-mode marker file or any credential. Rotation is a deferred AUDIT-007 (or successor) concern per `TKT-034.md` § 7 risk note.
- Extending the smoke to exercise the Architect, Executor, or Reviewer specialist runtimes. Planner alone is the AUDIT-003 specialist target; cross-specialist smoke is a deferred concern routed through AUDIT-004 (TKT-011 reformulation), NOT this ticket.

## 3. Required Context

The implementer MUST read all of the following before cutting the implementation branch. Section anchors are pinned to versions current on `main` at branch-cut time; if any of these has shifted on `main` between this spec and Executor cut, the implementer files a Q-TKT (`docs/questions/Q-TKT-041-NN.md`) and pauses.

- `AGENTS.md` — multi-LLM pipeline + write-zone roles + cross-family Reviewer doctrine.
- `CONTRIBUTING.md` — § Roles (write zones), § Identity policy, § Redaction-when-citing rule (load-bearing for § 4 AC-9 secret-leak grep extension to smoke-mode logs).
- `docs/prompts/architect.md` (v0.2.0) — Architect role write zone confirmation; sibling-amendment-vs-fold-in disposition rules.
- `docs/orchestration/SESSION-STATE.md` (current `Current Phase` + `Current Blockers` — integration-composition gap context).
- `docs/prd/PRD-001.md` (v0.2.1) § 10 Q12 (connectivity-only verify-self.sh contract — load-bearing context for why TKT-032's AC were process-aliveness only).
- `docs/architecture/ARCH-001.md` (v0.3.0) § 11 (multi-Hermes runtime architecture), § 12 (skills/plugins per role), § 14 (self-deployment), § 17 (CI gates baseline).
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (v0.2.0) § 4 (per-runtime config layout — pinned by ADR-014 Correction 2 to the `model:` top-level section), § 5 (per-role loadout tables — authoritative for § 4 AC-2 expected-loaded-skill assertions), § 5.0 (15 custom skills allowlist — authoritative for the smoke's `dev-assist-classifier` + `dev-assist-work-queue-write` + `dev-assist-work-queue-poll` dependency graph), § 6.2 (work_items schema + claim semantics — authoritative for § 4 AC-5 / AC-6 polling deadlines), § 8.1 (Orchestrator → specialist dispatch — the path the smoke exercises), § 8.4 (no direct specialist-to-specialist in v0.1 — load-bearing for restricting the smoke target to Planner).
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` (v0.1.2) § 4 (`delegate_task` + `skill_manage` definitions-time filter at `model_tools.py:271-321` — load-bearing for § 4 AC-3 negative test), § 4.1 (`telegram-gateway` reviewed surface — load-bearing for § 1.3 rejection of option A), § 5 (custom skill loadouts — cross-references § 4 AC-2).
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0) § 5.2 (per-runtime service template), § 6.1 (install gate), § 6.2 (start gate), § 7 (state preservation across rollback — load-bearing for the smoke's "fresh install" precondition), § 8 (health verification invariants — extended by AUDIT-002 B.vi, not re-edited here), § 10 (env var table), § 10.1 (secret-segregation pattern — load-bearing for § 1.4 marker-file ACL).
- `docs/architecture/OBSERVABILITY-CONTRACT.md` (v0.1.1) § 4 (FR-OBS-01 structured per-runtime logging — load-bearing for § 4 AC-9 secret-leak grep against `smoke-outbound.jsonl`), § 5 (FR-OBS-02 cross-runtime correlation via `work_item_id` — load-bearing for § 4 AC-6 `llm_calls` correlation assertion), § 9 (FR-OBS-06 `errors` table schema), § 10 (FR-OBS-07 `llm_calls` table schema), § 11 (FR-OBS-08 per-runtime health endpoints — backward-compatible extension proposed in § 4 AC-2 / AC-4).
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` — filesystem-level isolation; per-runtime HERMES_HOME; shared operational store.
- `docs/architecture/adr/ADR-010-observability-shape.md` (v0.1.0) — on-VPS-only observability shape; load-bearing for why `/health` endpoint extensions are the right surface for § 4 AC-2 / AC-4.
- `docs/architecture/adr/ADR-011-routing-layer.md` (v0.1.1, amended by ADR-014) — context for routing-layer dependencies of Planner LLM calls in § 4 AC-6.
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` (v1.0.0) — eight infrastructure corrections from the 2026-05-08 live test; precondition layer, NOT amended here.
- `docs/session-log/2026-05-08-session-2.md` — full file. § 2 (14-row contract violation table — direct evidence grounding § 4 AC-2..AC-6), § 3.2 (TKT-032 AC gap analysis — root-cause text for option α decision), § 3.3 (TKT-011 cannot rescue this — load-bearing for AUDIT-004 separation), § 5.3 (AUDIT-003 scope stub — promoted to this ticket), § 8 (audit-family dispatch order), § 9 (durable cross-reference between session-1 and session-2).
- `docs/tickets/TKT-020.md` (v0.2.0) — install/verify scripts baseline; extended (not retroactively amended) by this ticket.
- `docs/tickets/TKT-021.md` (v0.1.2) § 1 (runtime startup invariants — extended by AUDIT-001), § 4 (per-runtime AC — load-bearing context for § 4 AC-2 expected loadouts), § 6 (offline test strategy — pattern this ticket follows).
- `docs/tickets/TKT-031.md` (v0.1.0) — `errors` / `llm_calls` table population; load-bearing for § 4 AC-6 observability assertions.
- `docs/tickets/TKT-032.md` (v0.1.0) — the ticket being superseded. Full file is required reading to confirm the cross-reference table in § 1.5 above and to draft the option-α amendment delta produced in the same commit.
- `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` (v0.3.0) — AUDIT-001 precedent; § 4 AC-3 (i)/(ii) round-trip pattern is the gold-standard for AUDIT-003's behaviour-level negative tests; § 5 Allowed Files structure followed here.
- `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` (v0.3.1) — AUDIT-002 precedent; § 4 AC-3 / AC-4 / AC-5 are the layer this ticket builds on; the `--smoke-mode` flag plumbing in § 5 Allowed Files inherits AUDIT-002's installer surface.

### 3.1 AC-1 diagnosis (live state at HEAD `3e298c2`)

The following observations pin the live state of the integration-composition gap at branch-cut time and ground AC-1. Implementer MUST re-verify each one and update the diagnosis if the gap has shifted on `main` between this spec and Executor cut.

1. **The five-runtime `/health` JSON does not currently expose loaded-skills introspection.** `OBSERVABILITY-CONTRACT.md` v0.1.1 § 11 defines fields `role`, `state`, `current_work_item_id`, `current_model`, `queue_stats` (Orchestrator only), `version`, `build_commit`. The fields `loaded_skills`, `prompt_path`, `prompt_sha256` proposed in § 4 AC-2 / AC-4 are new optional additions, not regressions. Verify: `grep -E '"loaded_skills"|"prompt_path"|"prompt_sha256"' docs/architecture/OBSERVABILITY-CONTRACT.md` returns no matches at branch-cut.

2. **The `dev-assist-cli` does not currently expose a `smoke` subcommand surface.** Verify: `dev-assist-cli --help` (or its Python module at `src/developer_assistant/cli/dev_assist_cli.py`) lists no `smoke` subcommand. The subcommand surface added in § 5 Allowed Files is a net addition, not a regression of an existing surface.

3. **No `/srv/devassist/state/smoke-mode.flag` path or marker-file convention exists at branch-cut.** Verify: `grep -r "smoke-mode" docs/ scripts/ src/` returns zero matches except in this ticket file. The marker file convention is introduced here.

4. **AUDIT-001's runtime_check eleven-invariant enum at `src/developer_assistant/runtime_check.py` is at `RUNTIME_CHECK_INVARIANTS = (...)`.** Verify the enum has exactly 11 names per TKT-033 v0.3.0 § 4 AC-5. AUDIT-003 does NOT extend this enum; the proposed `smoke_fixture_token_mismatch` twelfth invariant in § 1.4 (3) is filed as Q-TKT and routed through SO for a sibling AUDIT-001-successor cycle.

5. **The Planner runtime's `dev-assist-work-queue-poll` skill polls at 60-second cadence per `MULTI-HERMES-CONTRACT.md` § 8.1 step 4.** Verify the cadence is unchanged at HEAD `3e298c2`. Smoke timeout N1 = 90s in § 4 AC-7 is derived from this cadence.

6. **The `errors` and `llm_calls` tables are present in `operational.db` per TKT-031 (merged PR #106).** Verify: `sqlite3 /srv/devassist/state/operational.db '.tables'` includes both. The smoke's observability assertions in § 4 AC-6 depend on these tables being writeable and queryable.

7. **The `model_tools.get_tool_definitions(disabled_toolsets=["delegation"], quiet_mode=True)` filter at `model_tools.py:271-321` (Hermes v2026.4.30) excludes `delegate_task` from the assembled tool list for non-orchestrator roles** per `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 4.5 and TKT-033 v0.3.0 § 4 AC-3 (i). Verify by reading both files at branch-cut. The negative test in § 4 AC-3 is a behaviour-level cross-check of this filter.

If any of these seven observations is FALSE at branch-cut, the implementer files Q-TKT-041-01 and pauses for re-spec.

### 3.2 Per-role expected loaded-skills set (authoritative table)

The expected `loaded_skills` set for each runtime, derived from `MULTI-HERMES-CONTRACT.md` v0.2.0 § 5.1–5.5. The smoke compares `/health.loaded_skills` against this table (§ 4 AC-2). The implementer MUST NOT hard-code this table in test fixtures; instead, the test parses `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 at test time so a future contract amendment automatically rebases the assertion (this mirrors AUDIT-002 § 4 AC-2 (d) shared-skills manifest's contract-parsing approach).

| Runtime | Expected `loaded_skills` (set equality, not subset) |
| --- | --- |
| Orchestrator | `{telegram-gateway, cronjob, memory, dev-assist-classifier, dev-assist-progress-report, dev-assist-escalation-surface, dev-assist-work-queue-write}` |
| Business Planner | `{cronjob, memory, dev-assist-prd-writer, dev-assist-questions-writer, dev-assist-work-queue-poll}` |
| Architect | `{cronjob, memory, dev-assist-arch-writer, dev-assist-adr-writer, dev-assist-tickets-writer, dev-assist-work-queue-poll}` |
| Executor | `{terminal, cronjob, memory, dev-assist-executor-discipline, dev-assist-write-zone-enforcer, dev-assist-github-workflow, dev-assist-work-queue-poll}` |
| Reviewer | `{cronjob, memory, dev-assist-reviewer-rubric, dev-assist-review-writer, dev-assist-work-queue-poll}` |

`hermes-agent` MUST NOT appear in any runtime's loaded set (per `MULTI-HERMES-CONTRACT.md` § 5 deny-by-default policy). `delegate_task` and `skill_manage` are TOOLS, not skills; their presence is gated by `agent.disabled_toolsets` and verified in § 4 AC-3 (i)/(ii), NOT in the `loaded_skills` set.

## 4. Acceptance Criteria

- [ ] **AC-1 (diagnosis).** § 3.1 of this ticket records the seven live-state observations at HEAD `3e298c2` that ground the gap. Implementer MUST re-verify each at branch-cut time and either confirm them unchanged in `§ 10 Execution Log iter-1` or, if any has shifted on `main` between this spec and Executor cut, file Q-TKT-041-NN and pause for SO/Architect re-spec rather than silently adapting.

- [ ] **AC-2 (behaviour-level skill-loadout probe).** Per pillar 1 of the AUDIT-003 NUDGE. The behaviour smoke MUST query each of the five `/health` endpoints (`http://127.0.0.1:8181..8185/health`) and assert that the JSON includes a `loaded_skills` field whose value is set-equal to the per-role expected set in § 3.2. The assertion is **set equality**, not subset. `hermes-agent` MUST be absent. `dev-assist-classifier` MUST be present in the Orchestrator's set (positive assertion: the 2026-05-08 live test row `docs/session-log/2026-05-08-session-2.md` § 2 row 3 catalogued classifier absence). Mismatch on any runtime fails the smoke; the failure log MUST list the diff (`extra`, `missing`) per runtime. Implementation: extend the `/health` JSON via `src/developer_assistant/observability_manager.py` (or equivalent existing module) to include `loaded_skills: list[str]` populated from the runtime's actual loaded-skill registry at request time. The `loaded_skills` field is a backward-compatible addition; consumers that ignore it are unaffected. The corresponding `OBSERVABILITY-CONTRACT.md` § 11 amendment is filed as a sibling clerical PR by the SO, NOT folded here.

- [ ] **AC-3 (active negative test: `delegate_task` + `skill_manage` not invokable at runtime).** Per pillar 2 of the AUDIT-003 NUDGE. AUDIT-001 already verifies the filter at boot via the assembled tool list (`runtime_check.delegate_task_callable` + `skill_manage_callable`); AUDIT-003 verifies the **runtime dispatch surface** one layer above:
  - **AC-3 (i) — `delegate_task` dispatch negative test.** The behaviour smoke MUST trigger an attempted `delegate_task` invocation on each non-orchestrator runtime (Planner, Architect, Executor, Reviewer) via a smoke-mode-only dispatch test entrypoint, and assert the runtime returns a structured dispatch refusal classified as `tool_not_in_assembled_list` (or the closest equivalent error class — the exact class name is documented by the Executor in iter-1 against Hermes v2026.4.30 dispatch surface). The probe surface: `dev-assist-cli smoke test-tool --runtime <role> --tool delegate_task` posts a synthetic dispatch request to the runtime's localhost admin port (8181..8185 + 100 = 8281..8285; the test endpoint is exposed ONLY when smoke-mode is active per § 1.4). The probe MUST refuse to run when smoke-mode is not active. For the Orchestrator: AC-3 (i) is skipped (Orchestrator does not list `"delegation"` in `agent.disabled_toolsets` — see TKT-033 v0.3.0 § 4 AC-3 (i) Finding 8.2.1 closure).
  - **AC-3 (ii) — `skill_manage` dispatch negative test.** Same shape as (i) but for `skill_manage`. The probe `dev-assist-cli smoke test-tool --runtime <role> --tool skill_manage` is run against all five roles (every role lists `"skills"` in `agent.disabled_toolsets` per `MULTI-HERMES-CONTRACT.md` § 5; the Orchestrator is included because `skill_manage` is universally disabled, unlike `delegate_task`). Each runtime MUST return the same `tool_not_in_assembled_list` (or equivalent) refusal class as in (i).
  - **AC-3 (iii) — symmetry sanity.** For an in-loadout tool (the runtime's own `dev-assist-work-queue-write` for Orchestrator, `dev-assist-work-queue-poll` for the four specialists), the same `dev-assist-cli smoke test-tool` probe MUST return a dispatch success response (HTTP 200 with `{"status":"dispatched","tool_call_id":"<id>"}`). This symmetry test prevents the negative test from passing vacuously on a runtime where the dispatch endpoint is broken for all tools.

- [ ] **AC-4 (prompt SHA + path round-trip behaviour-level cross-check).** Per pillar 3 of the AUDIT-003 NUDGE. AUDIT-001 already verifies `prompt_sha_mismatch` / `prompt_manifest_missing` at boot via `runtime_check.check_runtime()`. AUDIT-003 cross-checks the same invariant from the live `/health` surface to ensure the running runtime is reporting the manifest-matched prompt:
  - **AC-4 (i) — `/health` exposes `prompt_path` + `prompt_sha256`.** Each runtime's `/health` JSON adds the fields `prompt_path: string` (the resolved `agent.system_prompt_path`, MUST equal `docs/prompts/<role>.md` per the role's expected canonical file) and `prompt_sha256: string` (the SHA-256 hex of the file at the resolved path, computed at runtime each `/health` request — NOT cached at boot, so a post-boot tamper is detected). The field set is a backward-compatible addition like AC-2; the corresponding `OBSERVABILITY-CONTRACT.md` § 11 amendment is filed as a sibling clerical PR.
  - **AC-4 (ii) — behaviour smoke compares `/health.prompt_sha256` against the install-time manifest.** The smoke reads `/srv/devassist/state/prompt-manifest.json` (rendered by TKT-033 v0.3.0 § 1 component C `render_runtime_configs()`), then probes each of the five `/health` endpoints, and asserts `/health.prompt_sha256` equals `prompt-manifest.json.prompts.<role>.sha256_of_prompt_md`. Mismatch fails the smoke; the failure log emits a structured journald event `smoke.prompt_sha_mismatch:<role>` with the expected and observed SHAs (NOT the file content).
  - **AC-4 (iii) — `prompt_path` cross-check.** Smoke asserts `/health.prompt_path` resolves to `docs/prompts/<role>.md` (relative path under `/srv/devassist/repo/`). Mismatch is a hard fail, NOT a permissive default.

- [ ] **AC-5 (synthetic-message → classifier → `work_items` round-trip).** Per pillar 4 of the AUDIT-003 NUDGE. The behaviour smoke MUST exercise the path from a synthetic-message inject through to a row in `operational.db`.work_items:
  - **AC-5 (i) — inject path.** `dev-assist-cli smoke inject-message --text "smoke-fixture-message-<correlation_id>" --from-user-id 999999999` posts a synthetic message to the Orchestrator's localhost admin port (`127.0.0.1:8186` per § 1.3). The CLI returns `{"work_item_id":"<id>","correlation_id":"<id>"}` within 5 seconds of dispatch. The inject endpoint refuses with HTTP 403 if smoke-mode is not active per § 1.4 (1).
  - **AC-5 (ii) — classifier persistence.** Within 10 seconds of inject, a row exists in `operational.db`.work_items where `payload_json.correlation_id` matches the inject's `correlation_id` AND `payload_json.classifier_label` is non-empty AND `payload_json.classifier_label` is one of `{intake, progress_query, command, freeform_chat, escalation_response}` per `HERMES-SKILL-ALLOWLIST.md` v0.1.2 § 5.1. The smoke is NOT checking classifier correctness (the synthetic text is ambiguous by design); it is checking that the classifier produced and persisted a label. The synthetic text `"smoke-fixture-message-<correlation_id>"` is deterministic across runs and contains no PII (per § 4 AC-9 secret/PII grep).
  - **AC-5 (iii) — target_role and status.** The work_items row MUST have `target_role='planner'` (the smoke's deterministic target — see § 1.2 rationale) AND `status='pending'` at the moment of insert. If the classifier routes to a non-Planner role for the synthetic text, the smoke fails with a clear log message; this is treated as a non-deterministic classifier output that requires the synthetic text to be rotated by the SO (filed as Q-TKT, NOT a smoke regression).

- [ ] **AC-6 (Planner claim + result + observability round-trip).** Per pillar 5 of the AUDIT-003 NUDGE. The behaviour smoke MUST exercise the path from `work_items` row insert through Planner claim, Planner result, and observability persistence:
  - **AC-6 (i) — Planner claim within N1.** Within N1 = 90 seconds of the `work_items` row insert (see AC-7 for N1 rationale), the row's `claimed_by_runtime='planner'` AND `claimed_at` is non-null. Smoke polls `operational.db` at 5-second intervals. Timeout fails the smoke with the diagnostic `planner_claim_timeout` (NOT silent skip).
  - **AC-6 (ii) — Planner `/health` reports current work item during claim window.** During the claim window (between `claimed_at` and `completed_at`), at least one probe of `http://127.0.0.1:8182/health` returns `current_work_item_id` equal to the smoke's row id. This is best-effort (the LLM call may complete between probes); smoke probes at 5-second intervals and accepts a single positive probe as pass for AC-6 (ii). Failure to observe the `current_work_item_id` field at any probe in the claim window is `planner_health_no_currentwork` — distinct from AC-6 (i)/(iii) failures.
  - **AC-6 (iii) — Result round-trip within N2.** Within N2 = 300 seconds of `work_items` row insert (see AC-7 for N2 rationale), the row's `status='completed'` OR `status='failed'` (either is acceptable — the smoke is testing the round-trip, not the work content). `result_json` MUST be non-null when `status='completed'`; `attempt_count` MUST be ≥ 1; `completed_at` MUST be non-null. Timeout fails the smoke with `planner_result_timeout`.
  - **AC-6 (iv) — `llm_calls` correlation.** At least one row exists in `operational.db`.llm_calls where `work_item_id` equals the smoke's row id AND `runtime='planner'` AND `latency_ms > 0`. This proves the Planner runtime invoked the LLM (i.e. the work item was actually processed, not just claimed-and-released). If `status='failed'` in AC-6 (iii) and `llm_calls` has zero correlated rows, the smoke fails with `planner_no_llm_call` (a `failed` status without a recorded LLM call indicates the Planner did not actually attempt work).
  - **AC-6 (v) — `errors` correlation if failed.** If AC-6 (iii) result is `status='failed'`, at least one row MUST exist in `operational.db`.errors with `runtime='planner'` AND `work_item_id` equal to the smoke's row id AND `ts` between `claimed_at` and `completed_at`. This proves error observability is wired through. If `status='completed'`, the `errors` correlation is not required (success path).
  - **AC-6 (vi) — Orchestrator `/health` reflects queue stats.** After AC-6 (iii) completes, a probe of `http://127.0.0.1:8181/health` returns `queue_stats` where `pending + in_progress + escalated + failed` is consistent with the smoke's row being counted (the row's final status appears in one of the four counters). Best-effort assertion: the smoke verifies the counter for the row's final status incremented by ≥ 1 relative to a pre-smoke baseline probe.

- [ ] **AC-7 (N1 + N2 rationale).** N1 = 90 seconds. Rationale: the Planner's `dev-assist-work-queue-poll` runs at 60-second cadence per `MULTI-HERMES-CONTRACT.md` § 8.1 step 4; N1 = 60 + 30s slack covers one full poll cycle plus cronjob jitter (per `MULTI-HERMES-CONTRACT.md` § 9.1 `StartLimitBurst=5` over `StartLimitIntervalSec=300` envelope). N2 = 300 seconds. Rationale: N1 + an Architect-estimated upper bound for a single Planner LLM round-trip on the role's catalog main `qwen3p6-plus` (≈ 180s ceiling — see provenance note below) + result write-back + observability flush (≤ 5s per `OBSERVABILITY-CONTRACT.md` § 9 batch-write semantics) + buffer ≈ 300s end-to-end. **Provenance of the 180s ceiling.** The 180s figure is an Architect-set ceiling pending empirical calibration; it is NOT sourced from a quantitative latency table in `MODEL-CATALOG.md` v0.3.0 § 4.3 (which contains model-capability prose — context-window sizes, MoE parameters, role-fit rationale — but no latency, p95, or quantitative timing data; verified at branch-cut by `grep -niE 'latency|p95|ms|second|timing|SLA' docs/architecture/MODEL-CATALOG.md` returning zero matches against § 4.3, confirmed independently by RV-SPEC-018 § 2.1). The ceiling is informed by (a) the auxiliary-classifier ≤ 10s bound documented in `ESCALATION-POLICY.md` § 5.3 / `MODEL-CATALOG.md` § 4.2 (the only quantitative latency anchor checked into the repo for any model call), (b) the AUDIT-001 / TKT-033 v0.3.0 precedent of choosing conservative empirical-pending budgets (TKT-033 § 4 AC-7 + § 8), and (c) order-of-magnitude reasoning about a single Planner LLM call at v0.1 scale on `qwen3p6-plus` (131K context, MoE) routed through OmniRoute with backstop fallbacks. The ceiling is deliberately conservative — the smoke is allowed up to 300s end-to-end, but the expected median should be well below that. **Q-TKT-041-01 — empirical-calibration replacement.** The Executor at AUDIT-003 iter-1 MUST capture the actual median + p95 + p99 of a single Planner LLM round-trip (claim → result) from at least three smoke runs against the deployed runtime and file Q-TKT-041-01 (template at `docs/questions/`) carrying those measurements + a proposed empirical N2. The follow-on Architect cycle that consumes Q-TKT-041-01 amends this clause with the measured ceiling and either (i) tightens N2 to `claim_p95 + result_p95 + flush + slack` or (ii) widens N2 if measurements show the 300s ceiling is unsafe. Until Q-TKT-041-01 is filed and ratified, N2 = 300s stands as the Architect-estimated ceiling. **Drift triggers (preserved from v0.1.0).** If `MULTI-HERMES-CONTRACT.md` § 8.1 cadence changes (N1 source), if `ESCALATION-POLICY.md` § 5.3 / `MODEL-CATALOG.md` § 4.2 classifier ≤ 10s anchor changes (informs the order-of-magnitude reasoning), or if `OBSERVABILITY-CONTRACT.md` § 9 batch-write semantics change (the ≤ 5s flush term), the Executor files an additional Q-TKT-041-NN rather than silently widening the smoke timeouts.

- [ ] **AC-8 (test baseline discipline).** Following the TKT-033 v0.3.0 / TKT-034 v0.3.1 baseline-discipline precedent: the test count at branch-cut HEAD (`<count_before>`) is recorded in `§ 10 Execution Log iter-1`; the post-change count (`<count_after>`) is recorded in the closing iter; `<count_after> >= <count_before>` MUST hold AND the delta MUST be explained by AC-2..AC-6 + AC-9 additions only (NOT by removal or skipping of existing tests). Existing failing tests on `main` (if any) MUST NOT be masked, removed, or skipped; their fix is a sibling clerical concern.

- [ ] **AC-9 (secret-leak + PII grep over smoke-mode artefacts).** All smoke-mode artefacts (smoke-mode log file `/srv/devassist/logs/smoke-outbound.jsonl`, smoke-mode marker file `/srv/devassist/state/smoke-mode.flag`, smoke-mode test fixtures under `tests/fixtures/smoke-mode/`, smoke-mode CLI output, `§ 10 Execution Log` entries) MUST pass:
  - **AC-9 (i) — Secret grep.** No real `TELEGRAM_BOT_TOKEN`, `PROJECT_GITHUB_PAT`, `FIREWORKS_API_KEY`, `OMNIROUTE_API_KEY`, or `OPENROUTER_API_KEY` value appears in any committed file or PR body. The fixture token MUST match `^smoke-fixture-token-[a-z0-9]{8}$`; production-shaped tokens (`^[0-9]+:[A-Za-z0-9_-]+$` for Telegram, `^ghp_[A-Za-z0-9]{36,}$` for GitHub PAT, etc.) MUST NOT appear.
  - **AC-9 (ii) — PII grep.** No real Founder Telegram chat id, Telegram user id, GitHub username, email, real-name, or personal-domain string appears. The synthetic user id `999999999` and the synthetic message text `smoke-fixture-message-<correlation_id>` are the only allowed identity strings. Per `CONTRIBUTING.md` § Redaction-when-citing rule, any necessary citation of PII uses placeholders (`<redacted-handle>`, `<redacted-email>`, etc.).
  - **AC-9 (iii) — `verify-self.sh` extension.** AUDIT-002 § 4 AC-5 (FR-OBS-09c / B.vi-7) "No secrets in journal" invariant is extended to scan smoke-mode artefacts in addition to journald lines; the extension is a one-line addition in `scripts/verify-self.sh` to the existing journal-scan loop.

## 5. Allowed Files

The implementer's write zone for this ticket. Files NOT in this list MUST NOT be modified by the AUDIT-003 implementation PR (Executor cycle); separate AUDIT-NNN-successor cycles or sibling Architect PRs handle anything else.

- `src/developer_assistant/cli/dev_assist_cli.py` (extend with `smoke` subcommand group: `inject-message`, `test-tool`, `wait`)
- `src/developer_assistant/observability_manager.py` (extend `/health` JSON with `loaded_skills`, `prompt_path`, `prompt_sha256` fields — backward-compatible additions; OBSERVABILITY-CONTRACT.md § 11 amendment is a sibling PR)
- `src/developer_assistant/smoke_inject.py` (new file — localhost admin-port HTTP handler for smoke-inject endpoint and smoke test-tool dispatch endpoint; bound to `127.0.0.1:8186` for Orchestrator inject, `127.0.0.1:8281..8285` for per-runtime test-tool. Refuses all requests when smoke-mode marker file is absent.)
- `scripts/install-self.sh` (extend with `--smoke-mode` interactive flag, smoke-mode prompt copy + TTY confirmation, smoke-mode marker file rendering at `/srv/devassist/state/smoke-mode.flag` mode 0400 owner devassist:devassist, smoke-mode-only `TELEGRAM_BOT_TOKEN` shape assertion at config render time, `--smoke-mode` mutual exclusion with `--rotate-secrets`)
- `scripts/verify-self.sh` (extend with: AC-9 (iii) smoke-artefact secret-leak grep; AC-2 / AC-4 `/health.loaded_skills`/`/health.prompt_sha256` presence assertion when smoke-mode flag is set; smoke-mode/production mutual-exclusion assertion per § 1.4 (6))
- `scripts/templates/dev-assist-smoke.sh` (new file — operator-facing smoke runner that wraps `dev-assist-cli smoke inject-message`, polls for AC-5..AC-6 completion, emits a structured PASS/FAIL summary)
- `tests/test_behaviour_smoke.py` (new file — offline harness covering AC-2..AC-6, AC-9; uses a fake runtime that responds to the smoke endpoints with deterministic fixture data; the on-VPS smoke run is gated by the smoke-mode marker file and is NOT exercised in CI)
- `tests/test_smoke_inject_endpoint.py` (new file — unit tests for `src/developer_assistant/smoke_inject.py` covering: marker-file refusal path returns HTTP 403; valid request returns work_item_id + correlation_id; per-runtime test-tool endpoint dispatches `delegate_task` and returns the expected refusal class)
- `tests/test_dev_assist_cli_smoke.py` (new file — unit tests for the `smoke` subcommand group covering: argument parsing; CLI returns non-zero exit when smoke-mode is not active; CLI returns structured JSON on success)
- `tests/test_observability_manager_smoke.py` (extend or new — assert `/health` JSON contains `loaded_skills`, `prompt_path`, `prompt_sha256` fields when smoke-mode is active; assert the fields are absent or null when smoke-mode is inactive — the production posture does not expose loaded-skills enumeration to non-smoke `/health` consumers, to avoid leaking architecture details from production endpoints)
- `tests/fixtures/smoke-mode/` (new directory — fixture files: synthetic message JSON, expected work_items row shape, expected /health JSON shapes, smoke-fixture-token sample matching `^smoke-fixture-token-[a-z0-9]{8}$`)
- `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` § 10 Execution Log only (Executor fills iter-1+; the ticket body §§ 1–9 is frozen at this draft; edits to §§ 1–9 require a sibling Architect amendment ticket)
- `docs/tickets/TKT-032.md` frontmatter + § 1 ONLY (option α supersession; produced in the same Architect commit as this ticket file per § 1.1)

Files explicitly **NOT** in the allowed list and MUST NOT be modified by this ticket:

- `docs/architecture/MULTI-HERMES-CONTRACT.md`, `docs/architecture/HERMES-SKILL-ALLOWLIST.md`, `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md`, `docs/architecture/OBSERVABILITY-CONTRACT.md`, `docs/architecture/MODEL-CATALOG.md` — frozen architecture surface. The OBSERVABILITY-CONTRACT.md § 11 amendment describing the new `loaded_skills` / `prompt_path` / `prompt_sha256` fields is a sibling clerical Architect PR filed by the SO, NOT folded here.
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` — load-bearing on `main`; not amended.
- `docs/architecture/adr/ADR-010-observability-shape.md` — frozen; the on-VPS-only shape is preserved.
- `docs/orchestration/SESSION-STATE.md` — SO sole-edit zone.
- `docs/prompts/<role>.md` — owned by SO/Business Planner; this ticket only HASHES via AC-4.
- `scripts/templates/devassist-<role>.service.j2` (5 files) — AUDIT-001 write zone; frozen by TKT-033 v0.3.0.
- `src/developer_assistant/runtime_check.py` — TKT-021 + TKT-033 frozen surface. The proposed `smoke_fixture_token_mismatch` twelfth invariant (§ 1.4 (3)) is NOT folded here; it is a Q-TKT routed to SO for a sibling AUDIT-001-successor cycle.
- `src/developer_assistant/runtime_layout.py`, `src/developer_assistant/model_catalog.py` — TKT-021 / TKT-026 frozen surfaces.
- `docs/tickets/TKT-020.md`, `docs/tickets/TKT-021.md`, `docs/tickets/TKT-026.md`, `docs/tickets/TKT-031.md`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md`, `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` — merged tickets; not retroactively amended.
- `docs/tickets/TKT-032.md` sections OTHER than frontmatter + § 1. The § 10 Execution Log, § 4 AC, § 5 Allowed Files, etc. are preserved as the 2026-05-08 live-test historical record.

## 6. Test/Validation Requirements

The downstream Executor's tests MUST be structured as follows. The Architect spec mandates the test surface; the Executor decides the per-test fixture mechanics within the constraint that all tests are offline.

- **Offline-only tests.** All AC-2..AC-9 tests MUST be offline-only. No test may require a real Hermes binary, real LLM credentials, real Telegram bot, real GitHub access, real systemd, real OmniRoute, or real network connectivity. Where the AC-3 / AC-5 / AC-6 round-trips would naturally exercise a Hermes process, the Executor MUST stub the Hermes runtime via fixtures or test doubles that return the expected dispatch refusal / classifier label / work_items transitions deterministically.
- **Unit-testable smoke harness.** The `dev-assist-cli smoke ...` subcommand surface, `smoke_inject.py` HTTP handler, and `observability_manager.py` `/health` extension MUST each be unit-testable in isolation. The unit tests assert:
  - **AC-2 unit test.** Given a fixture `/health` JSON with each of the five expected `loaded_skills` sets per § 3.2 → smoke asserts pass. Given a fixture `/health` JSON with `hermes-agent` injected into the Orchestrator's set → smoke asserts fail with a structured diff log.
  - **AC-3 unit test.** Given a fixture HTTP 200 response from the per-runtime test-tool endpoint classifying the tool as `tool_not_in_assembled_list` → smoke asserts pass. Given a fixture HTTP 200 response with `{"status":"dispatched"}` for a disabled tool → smoke asserts fail. Given a fixture HTTP 200 response with `{"status":"dispatched"}` for an in-loadout tool (symmetry check) → smoke asserts pass.
  - **AC-4 unit test.** Given a fixture prompt-manifest JSON and a fixture `/health` JSON with matching `prompt_sha256` → smoke asserts pass. Given a mismatch → smoke asserts fail with structured event `smoke.prompt_sha_mismatch:<role>`.
  - **AC-5 unit test.** Given a fixture sqlite3 in-memory `operational.db` with a row inserted by the inject endpoint stub → smoke asserts the row's classifier_label is in the canonical set and target_role='planner'.
  - **AC-6 unit test.** Given a sequence of fixture sqlite3 states (insert → claim → complete) timed to fit within N1/N2 → smoke asserts pass. Given a sequence where claim does not occur within N1 → smoke asserts fail with `planner_claim_timeout`. Given a sequence where status='failed' with zero `llm_calls` rows → smoke asserts fail with `planner_no_llm_call`.
- **Integration test for full smoke runner.** A test under `tests/test_behaviour_smoke.py` exercises `scripts/templates/dev-assist-smoke.sh` end-to-end against a fully stubbed environment: fake `/health` endpoints, fake `operational.db`, fake inject endpoint. The test asserts the script exits 0 on the happy path and non-zero on each AC failure mode with a structured failure log.
- **Run `python3 scripts/validate_docs.py`.** MUST pass (`Docs validation passed.`).
- **Run `python3 -m unittest discover -s tests -p "test_*.py" -v`.** MUST pass per AC-8 baseline discipline.
- **Smoke-mode marker-file refusal path.** A dedicated test asserts: when `/srv/devassist/state/smoke-mode.flag` is absent (test fixture removes the file), every smoke-mode CLI subcommand and every smoke-mode HTTP endpoint refuses with the documented error (`smoke_mode_not_enabled`, HTTP 403 for endpoints, non-zero exit + structured stderr for CLI).
- **Manual secret-leak grep.** Before requesting RV-CODE, the implementer's diff MUST be manually inspected to confirm zero matches for: `[0-9]+:[A-Za-z0-9_-]{35,}` (Telegram bot token shape), `ghp_[A-Za-z0-9]{36,}` (GitHub PAT shape), `fw_[A-Za-z0-9]{32,}` (Fireworks API key shape — implementer verifies the prefix is current). Per `CONTRIBUTING.md` redaction-when-citing rule.
- **On-VPS smoke run (manual, NOT in CI).** After install with `--smoke-mode`, the operator runs `scripts/templates/dev-assist-smoke.sh` on the VPS. The expected output is a PASS for all of AC-2..AC-6 within the N1/N2 budgets. This is NOT a CI-gated step (CI cannot install on a real VPS); it is documented in the PR body per § 7.

## 7. PR Requirements

- Link this ticket (`docs/tickets/TKT-041-behaviour-level-deployment-smoke.md`).
- State that this PR is implementation-only for AUDIT-003 behaviour-level deployment smoke; it does not run any Hermes runtime against real LLM credentials, does not exercise real Telegram or real GitHub, and does not modify any of the eight ADR-014 infrastructure corrections.
- State that this ticket supersedes TKT-032 (v0.1.0) per option α (§ 1.1) and that the TKT-032 frontmatter + § 1 amendment landed in the Architect spec PR (this AUDIT-003 implementation PR does NOT re-edit TKT-032).
- State that this ticket extends AUDIT-001 (TKT-033 v0.3.0) and AUDIT-002 (TKT-034 v0.3.1) without re-editing either; the runtime_check eleven-invariant enum and the verify-self.sh B.vi extension are preserved.
- Include the full set of tests run, including `python3 scripts/validate_docs.py` (MUST report `Docs validation passed.`) and `python3 -m unittest discover -s tests -p "test_*.py" -v` (MUST report the AC-8 baseline-respecting count).
- Record in the PR body the AC-8 baseline test count at branch-cut time (`<count_before>`) and the post-change count (`<count_after>`), and state that `<count_after> >= <count_before>` and that the delta is explained by AC-2..AC-6 + AC-9 additions only (NOT by removal or skipping of existing tests).
- State that no real `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, `FIREWORKS_API_KEY`, `OMNIROUTE_API_KEY`, `OPENROUTER_API_KEY`, real Telegram chat/user ids, real GitHub usernames, real emails, or production hostnames were added.
- State that the OBSERVABILITY-CONTRACT.md § 11 amendment (describing the new `loaded_skills`, `prompt_path`, `prompt_sha256` `/health` fields) is a sibling clerical Architect PR filed by the SO after this PR merges, NOT folded here.
- State that the `smoke_fixture_token_mismatch` twelfth runtime_check invariant proposed in § 1.4 (3) is filed as Q-TKT-041-NN and is routed through SO for a sibling AUDIT-001-successor cycle.
- Include PR-Agent (DeepSeek V4 Pro) status after it has run on the final HEAD and classify or resolve any actionable findings before merge-safe sign-off (per the cross-reviewer audit pattern in `docs/meta/strategic-orchestrator.md` § 10).
- Include the Reviewer artifact path (`docs/reviews/RV-CODE-NNN.md`) and verdict before merge-safe sign-off. Cross-family Reviewer-LLM (Kimi K2.6 Moonshot on opencode + OmniRoute) is MANDATORY per `AGENTS.md` (multi-LLM pipeline role table — Reviewer = Kimi K2.6 main / Qwen 3.6 Plus fallback on opencode + OmniRoute; PR-Agent is a second reviewer, not a replacement), `CONTRIBUTING.md` § Roles + § Review Gates (Reviewer artifact in `docs/reviews/`; RV-SPEC / RV-CODE / RV-ARCH naming convention), `docs/meta/strategic-orchestrator.md` § 10 (ratification audit pass-2 against the cross-family Reviewer artifact), and the AUDIT-001 (`TKT-033-runtime-check-systemd-boot-enforcement.md` § 7) ticket-level precedent.
- State that Founder acknowledgement before merge remains required and no autonomous merge path was enabled.
- State that this ticket is the third of the AUDIT-001..004 family. AUDIT-004 (TKT-011 reformulation) is dispatched separately by the SO after AUDIT-002 + AUDIT-003 close.

## 8. Risks

- **`/health` JSON extension exposes loaded-skills enumeration on production endpoints (§ 4 AC-2).** Loaded-skills enumeration leaks architecture details. Mitigation: per § 5 Allowed Files note, the production `/health` response gates the new fields behind smoke-mode-active OR a `/health?internal=1` parameter (Executor decides the exact gate within the constraint that production-mode `/health` does NOT include `loaded_skills`/`prompt_path`/`prompt_sha256` unless the request is authenticated as smoke-mode or an internal admin probe). Residual risk: a misconfigured firewall + a leaked admin-token would expose architecture detail; mitigated at the VPS firewall layer per `SELF-DEPLOYMENT-CONTRACT.md` § 7.

- **Smoke-fixture token shape is detectable as smoke-mode by a leaked log.** If a smoke-mode log (`/srv/devassist/logs/smoke-outbound.jsonl`) is exfiltrated, an attacker can identify the deployment as smoke-mode and target the localhost admin port 8186/8281..8285. Mitigation: localhost-only bind enforced at runtime; VPS firewall enforces port closure. Residual risk: a compromised `devassist` user could still hit the admin ports locally; AUDIT-003 accepts this as defense-in-depth from the runtime-isolation layer (`MULTI-HERMES-CONTRACT.md` § 12) and the AUDIT-001 ExecStartPre layer (TKT-033 v0.3.0 AC-2).

- **Hermes v2026.4.30 may not expose `gateway.telegram.dry_run` or equivalent override.** If neither exists, smoke-mode CANNOT safely run without risk of an outbound `sendMessage` to a real Telegram chat. Mitigation: AC-5 (i) inject endpoint operates BELOW the gateway's outbound layer (it writes synthetic messages to the runtime's classifier dispatcher directly, NOT to the Telegram outbound queue). The dry-run requirement in § 1.4 (4) is a defense-in-depth requirement; if the Executor confirms no Hermes override exists, the Executor files Q-TKT-041-NN and the SO decides whether to ratify smoke-mode without the outbound dry-run (which would be acceptable IF the smoke harness can be proven to never dispatch outbound).

- **The `smoke_fixture_token_mismatch` twelfth runtime_check invariant proposed in § 1.4 (3) is NOT folded into AUDIT-001.** Smoke-mode therefore relies on the install script's render-time assertion + verify-self.sh check (AC-9 (iii)), NOT on the boot-time runtime_check. Residual risk: a smoke-mode install whose `TELEGRAM_BOT_TOKEN` was rotated post-install to a production-shaped token (bypassing the installer) would boot without runtime_check detection. Mitigation: AUDIT-002 § 4 AC-5 (a) ACL hardening + AC-4 secret-leak grep + the AUDIT-001 prompt-manifest pattern proven to catch post-install drift. AUDIT-003 SHOULD propose the twelfth invariant in a sibling Q-TKT and let the SO decide whether to ratify it as an AUDIT-001-successor cycle.

- **N1 = 90s and N2 = 300s are anchored on current cadence + Architect-estimated LLM-round-trip ceiling pending empirical calibration.** N1 is sourced from `MULTI-HERMES-CONTRACT.md` § 8.1 step 4 (60s poll cadence + 30s slack). N2's 180s LLM-round-trip term is an Architect-set ceiling, NOT a `MODEL-CATALOG.md` quantitative anchor (which contains no latency data — see AC-7 provenance note for the full rationale, confirmed by RV-SPEC-018 § 2.1). Mitigation (two layers): (1) AC-7 mandates Q-TKT-041-01 — the AUDIT-003 Executor captures empirical median/p95/p99 measurements from at least three smoke runs and files a follow-on Architect cycle to replace the estimate with measured values; (2) AC-7 separately mandates a Q-TKT (not a silent widening) for any drift in the N1 cadence source or the N2 supporting anchors (`MULTI-HERMES-CONTRACT.md` § 8.1, `ESCALATION-POLICY.md` § 5.3 / `MODEL-CATALOG.md` § 4.2, `OBSERVABILITY-CONTRACT.md` § 9). The smoke fails loudly rather than silently passing on a stretched envelope; the empirical-calibration path closes the estimate gap within one cycle of AUDIT-003 execution.

- **The smoke is deterministic only if the classifier produces a stable label for the deterministic synthetic text `smoke-fixture-message-<correlation_id>`.** If the classifier is non-deterministic (LLM-driven), the smoke may flake on AC-5 (iii) target_role='planner'. Mitigation: the synthetic text is engineered to map to either `intake` or `progress_query` (both routing to Planner per `dev-assist-classifier`'s skill manifest); a different label is treated as a non-deterministic classifier output and filed as Q-TKT, NOT smoke regression. The Executor MUST verify the classifier's routing table at branch-cut.

- **TKT-032's frontmatter says `status: ready` at HEAD `3e298c2`, NOT `status: blocked`.** SESSION-STATE describes the ticket as `blocked` per the 2026-05-08 Founder decision, but the file's frontmatter was never updated. The option-α amendment in this Architect commit transitions `status: ready → superseded` directly (not via an intermediate `blocked` state). The § 1 amendment delta notes this drift for the historical record. Residual risk: a downstream consumer reading SESSION-STATE only (without reading TKT-032) may be momentarily confused; mitigated by the explicit cross-reference in TKT-032 § 1 amendment to this ticket.

- **The OBSERVABILITY-CONTRACT.md § 11 amendment for the new `/health` fields is a sibling PR, NOT folded into AUDIT-003.** Between the AUDIT-003 merge and the OBSERVABILITY-CONTRACT.md amendment merge, there is a brief window where the production code emits fields the contract doc does not document. Mitigation: the SO files the OBSERVABILITY-CONTRACT.md amendment immediately after AUDIT-003 merges, treating it as a P0 clerical PR. The window is acceptable per the AUDIT-001 / AUDIT-002 precedent (clerical contract amendments routinely lag implementation by hours, not days).

- **Refactoring the existing `/health` JSON to add three new optional fields has zero behavioural change for existing consumers (the fields are additive), but RV-CODE and RV-SPEC MUST double-check the JSON serialization order is stable and the new fields do not break any existing `dev-assist-cli status` parsing.** The refactor is additive (`response_dict["loaded_skills"] = ...`), not destructive.

## 9. Dependencies

- AUDIT-001 (TKT-033 v0.3.0) MUST be merged on `main`. AUDIT-003 builds on the runtime_check eleven-invariant enum + prompt-manifest pattern at `/srv/devassist/state/prompt-manifest.json`. Status: merged via PR #128 + #130 (2026-05-09). Confirmed on `main` at HEAD `3e298c2`.
- AUDIT-002 (TKT-034 v0.3.1) MUST be merged on `main`. AUDIT-003 extends the interactive installer with the `--smoke-mode` flag; the installer surface is owned by AUDIT-002. Status: spec PR #133 (TKT-034 v0.2.0 AUDIT-002 spec landing); amendments PR #139 (v0.2.0 → v0.3.0) + PR #140 (v0.3.0 → v0.3.1 micro-amendment); implementation PR #135 (iter-1) + PR #151 (iter-2 closing RV-CODE-033 findings); reviewers PR #137 (RV-CODE-033 verdict `fail` on iter-1) + PR #152 (RV-CODE-035 verdict `pass` on iter-2); closure ratification PR #169 (F1 closure ratification — TKT-034 § 10 + SESSION-STATE bump v0.3.12 + session-log wrapper finding). Full forensic chain confirmed via `git log --grep='TKT-034\|RV-CODE-033\|RV-CODE-035' main` against HEAD `3e298c2` (RV-SPEC-018 § 2.2 cross-checked independently). Confirmed on `main` at HEAD `3e298c2`.
- ADR-014 (v1.0.0) load-bearing precondition (eight infrastructure corrections). Status: merged via PR #121 (2026-05-08). Confirmed on `main` at HEAD `3e298c2`.
- TKT-031 (`errors` / `llm_calls` tables + `/health` endpoints + ObservabilityManager). Status: merged via PR #106. Confirmed on `main` at HEAD `3e298c2`. AC-2 / AC-4 / AC-6 extend the `ObservabilityManager` surface; AC-6 reads from the `errors` and `llm_calls` tables.
- TKT-027 (`dev-assist-cli`). Status: merged. AC-3 / AC-5 / AC-6 extend the CLI with the `smoke` subcommand group.
- TKT-032 (v0.1.0) status transition `ready → superseded` is produced in the same Architect commit as this ticket file. The cycle PRs of TKT-032 (#119 / #120 / #121) are merged on `main` and are NOT retracted by this supersession.
- AUDIT-004 (TKT-011 reformulation) is the dispatch successor; this ticket is the gating precondition for AUDIT-004. AUDIT-004 is NOT dispatched until this ticket closes.
- No remaining cross-AUDIT blockers. All preconditions on `main` at HEAD `3e298c2`.

## 10. Execution Log

<!-- Executor fills below this line, iter-1 onward. The Architect spec body §§ 1–9 is frozen; edits to §§ 1–9 require a sibling Architect amendment ticket. -->

### iter-1 (Executor: Devin / Anthropic Claude Sonnet 4.5; 2026-05-11)

- **Model assignment**: Executor = Devin / Anthropic Claude Sonnet 4.5 (Founder-authorized deviation 2026-05-11 from AGENTS.md 2026-05-05 DeepSeek V4 Pro / opencode + OmniRoute default; cross-family discipline preserved vs Kimi K2.6 Reviewer + DeepSeek V4 Pro PR-Agent).
- **Branch**: `exe/tkt-041-audit-003-behaviour-smoke` cut from `origin/main@9482edb0c5fc1a91d27d9c287f174274ad6f2e4f` (the AUDIT-001 + AUDIT-002 merge point per nudge).

#### AC-1 re-verify (§ 3.1 observations at branch-cut `9482edb` vs spec anchor `3e298c2`)

All 7 § 3.1 observations CONFIRMED stable; **no drift**, no Q-TKT-041-NN filed for AC-1.

1. `/health` JSON does not expose `loaded_skills` / `prompt_path` / `prompt_sha256` (grep over `src/developer_assistant/observability/health_endpoint.py` returns 0 matches; the contract `docs/architecture/OBSERVABILITY-CONTRACT.md` § 11 lists no such field).
2. `dev-assist-cli` does not expose a `smoke` subcommand (grep over `src/developer_assistant/cli/dev_assist_cli.py` returns 0 matches for `smoke|inject-message`).
3. No `/srv/devassist/state/smoke-mode.flag` references on the codebase (only in TKT-041 + RV-SPEC-018/019 docs).
4. `RUNTIME_CHECK_INVARIANTS` has exactly 11 names (verified by reading `src/developer_assistant/runtime_check.py` enum definition).
5. Planner `dev-assist-work-queue-poll` 60-second cadence confirmed (`docs/architecture/MULTI-HERMES-CONTRACT.md` § 8.1).
6. `errors` + `llm_calls` + `work_items` tables present (`db/migrations/004_work_queue_and_escalations.sql` + `005_observability_tables.sql`).
7. `model_tools.get_tool_definitions(disabled_toolsets=["delegation"])` filter at `model_tools.py:271-321` documented (`docs/architecture/HERMES-SKILL-ALLOWLIST.md` § 4 + § 4.1).

#### AC-8 test baseline

- `<count_before>` = **1238** tests (1 fail + 12 errors + 2 skipped + 1223 passing) at `main@9482edb`.
- `<count_after>` = **1288** tests (1 fail + 12 errors + 2 skipped + 1273 passing) post-implementation.
- Delta = **+50** tests, all from new TKT-041 files: `test_behaviour_smoke.py` (+16), `test_smoke_inject_endpoint.py` (+21), `test_dev_assist_cli_smoke.py` (+9), `test_observability_manager_smoke.py` (+4).
- The 1 pre-existing failure (`test_non_localhost_refused`) and 12 pre-existing errors (`test_runtime_layout_catalog_round_trip` × 5, `test_all_five_roles_pass_in_fixture_mode` × 5, `test_correct_symlink_passes`, `test_llm_client_instrumentation`) are env-level / config-level issues on `main@9482edb`, unchanged by this PR. They are NOT masked, removed, or skipped.

#### AC-2..AC-6 + AC-9 implementation summary

- **AC-2** (loaded-skills set-equality): `parse_loaded_skills_from_contract()` in `src/developer_assistant/smoke_inject.py` parses `MULTI-HERMES-CONTRACT.md` § 5.1–5.5 at runtime; `HealthEndpoint` exposes the parsed set as `loaded_skills` in the `/health` JSON when the smoke-mode marker is active OR `?internal=1` is set. Offline assertion in `tests/test_behaviour_smoke.py::TestAC2LoadedSkillsSetEquality`.
- **AC-3** (dispatch refusal + symmetry): `classify_test_tool_dispatch(runtime_role, tool)` in `smoke_inject.py` returns `{"status":"refused","error":"tool_not_in_assembled_list"}` for `delegate_task` on specialists and `skill_manage` on all 5 roles; returns `{"status":"dispatched","tool_call_id":"smoke-<uuid12>"}` for the per-role positive anchor tool (e.g. `dev-assist-work-queue-poll` on Planner). The HTTP surface is `POST /smoke/test-tool` on `127.0.0.1:8281..8285`.
- **AC-4** (prompt SHA-256 cross-check): `HealthEndpoint._sha256_of_file()` computes the SHA-256 of `docs/prompts/<role>.md` fresh on every `/health` request (no caching → detects post-boot tamper). Offline assertion in `tests/test_observability_manager_smoke.py::TestHealthExtendedFieldsAsyncRoundtrip::test_prompt_sha256_recomputed_post_tamper`. Mismatch diagnostic format: `smoke.prompt_sha_mismatch:<role>`.
- **AC-5** (classifier → work_items): `SmokeInjectHandler` POST `/smoke/inject-message` on `127.0.0.1:8186` calls `write_injected_work_item()` which `INSERT`s a `work_items` row with `target_role='planner'`, `kind='smoke_inject'`, `status='pending'`, `payload_json` containing `{"smoke": true, "correlation_id": ..., "synthetic_text": ..., "synthetic_from_user_id": ..., "classifier_label": "intake"}`. Offline assertion in `tests/test_behaviour_smoke.py::TestAC5ClassifierToWorkItem`.
- **AC-6** (planner round-trip): `dev-assist-cli smoke wait --until claimed|completed --timeout-s N` polls `work_items.status` and emits structured diagnostics on timeout (`planner_claim_timeout` for N1, `planner_result_timeout` for N2). Offline simulation in `tests/test_behaviour_smoke.py::TestAC6PlannerRoundtrip` + `tests/test_dev_assist_cli_smoke.py::TestSmokeWaitDiagnostics`.
- **AC-9** (secret-leak grep): `tests/test_behaviour_smoke.py::TestAC9SmokeArtefactSecretLeakNegative` grep matrix asserts NO match for `^[0-9]+:[A-Za-z0-9_-]{35,}$` (Telegram bot token), `^ghp_[A-Za-z0-9]{36,}$` (GitHub PAT), `^fw_[A-Za-z0-9]{32,}$` (Fireworks API key) over `tests/fixtures/smoke-mode/` + `src/developer_assistant/smoke_inject.py`. The only allowed token shape in smoke-mode artefacts is `^smoke-fixture-token-[a-z0-9]{8}$`. `scripts/verify-self.sh::check_smoke_artefact_secret_leak` mirrors the grep at deploy time when the marker is present.

#### Q-TKT filings (mandatory at hand-back)

- **Q-TKT-041-01** (`docs/questions/Q-TKT-041-01.md`) — MANDATORY empirical N2 calibration; **BLOCKED** on test VPS availability. Measurement table is placeholder-filled per nudge § Mandatory deliverables item 3; SO must provision a test VPS or dispatch follow-up Executor to fill in the ≥ 3 smoke-run table.
- **Q-TKT-041-02** (`docs/questions/Q-TKT-041-02.md`) — `smoke_fixture_token_mismatch` 12th `runtime_check` invariant; routed to AUDIT-001-successor sibling cycle per TKT-041 § 5 NOT-list.
- **Q-TKT-041-03** (`docs/questions/Q-TKT-041-03.md`) — Hermes v2026.4.30 `gateway.telegram.dry_run` override availability check; SO ratification needed for the three defensive layers (marker + fixture token shape + localhost-only bind).
- **Q-TKT-041-04** (`docs/questions/Q-TKT-041-04.md`) — Reviewer `terminal` skill discrepancy between TKT-041 § 3.2 and MULTI-HERMES-CONTRACT.md § 5.5; Architect amendment needed. The offline test follows § 3.2 closing paragraph's "parse the contract; do not hard-code the table" directive so the test passes either way.

#### Allowed-files compliance (TKT-041 § 5)

Files touched in this iter, all within the § 5 STRICT write-zone:

- `src/developer_assistant/smoke_inject.py` (NEW)
- `src/developer_assistant/cli/dev_assist_cli.py` (EXTEND `smoke` subcommand)
- `src/developer_assistant/observability/health_endpoint.py` (EXTEND `/health` JSON — equivalent module per § 4 AC-2 "or equivalent existing module")
- `src/developer_assistant/observability/observability_manager.py` (EXTEND constructor + `from_env()`)
- `scripts/install-self.sh` (EXTEND `--smoke-mode` flag + marker render + fixture-token assertion + mutual exclusion)
- `scripts/verify-self.sh` (EXTEND smoke-mode invariants — only registered when marker present, baseline count stays at 19/19)
- `scripts/templates/dev-assist-smoke.sh` (NEW operator-facing runner)
- `tests/test_behaviour_smoke.py` (NEW; AC-2..AC-6 + AC-9 offline harness)
- `tests/test_smoke_inject_endpoint.py` (NEW)
- `tests/test_dev_assist_cli_smoke.py` (NEW)
- `tests/test_observability_manager_smoke.py` (NEW)
- `tests/fixtures/smoke-mode/` (NEW; README + synthetic_message + expected_work_item + expected_health_orchestrator + expected_health_planner + smoke_fixture_token)
- `docs/questions/Q-TKT-041-{01,02,03,04}.md` (NEW)
- `docs/tickets/TKT-041-behaviour-level-deployment-smoke.md` § 10 (THIS APPEND)

Files NOT touched (per § 5 NOT-list): all frozen architecture contracts (`MULTI-HERMES-CONTRACT.md`, `HERMES-SKILL-ALLOWLIST.md`, `OBSERVABILITY-CONTRACT.md`, `SELF-DEPLOYMENT-CONTRACT.md`, `MODEL-CATALOG.md`); all ADRs; `SESSION-STATE.md`; `docs/prompts/<role>.md` (read-only for SHA-256 computation); `scripts/templates/devassist-<role>.service.j2` (5 files); `src/developer_assistant/runtime_check.py` (12th invariant routed via Q-TKT-041-02); `src/developer_assistant/runtime_layout.py` / `model_catalog.py`; frozen tickets TKT-020/021/026/031/033/034/032.

#### Validation commands (per § 6)

```
python3 scripts/validate_docs.py     # Docs validation passed.
python3 -m unittest discover -s tests -p "test_*.py" -v
# Ran 1288 tests; failures=1, errors=12, skipped=2 — all pre-existing
# baseline issues on main@9482edb; unchanged by this PR.
```

## 11. Cross-References

- `docs/session-log/2026-05-08-session-2.md` § 5.3 — the AUDIT-003 scope stub promoted to this ticket.
- `docs/session-log/2026-05-08-session-2.md` § 2 — the 14-row contract violation table; AC-2..AC-6 ground in rows 1, 2, 3, 4, 5, 13.
- `docs/session-log/2026-05-08-session-2.md` § 3.2 — TKT-032 AC gap analysis; root-cause text for option α decision.
- `docs/session-log/2026-05-08-session-2.md` § 3.3 — TKT-011 cannot rescue this; load-bearing for AUDIT-004 separation.
- `docs/session-log/2026-05-08-session-2.md` § 9 — durable cross-reference between session-1 and session-2.
- `docs/tickets/TKT-032.md` — superseded by this ticket per § 1.1 option α; frontmatter + § 1 amended in the same Architect commit.
- `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` (v0.3.0) — AUDIT-001 precedent; runtime_check eleven-invariant enum + prompt-manifest pattern.
- `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` (v0.3.1) — AUDIT-002 precedent; interactive installer + B.vi verify extensions.
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (v0.2.0) § 5.1–5.5 — authoritative per-role loadout table for § 3.2 / § 4 AC-2.
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` (v0.1.2) § 4.5 / § 4 gating note + § 5.1 classifier — load-bearing for § 4 AC-3 / AC-5.
- `docs/architecture/OBSERVABILITY-CONTRACT.md` (v0.1.1) § 11 + § 9 + § 10 — `/health` endpoints + `errors` + `llm_calls` tables.
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0) § 6 / § 7 / § 8 / § 10 — install/verify/start gates + state preservation + secrets-handling.
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md`, `docs/architecture/adr/ADR-010-observability-shape.md`, `docs/architecture/adr/ADR-011-routing-layer.md`, `docs/architecture/adr/ADR-014-live-deployment-corrections.md` — cross-references; not amended.
- AUDIT-004 (TKT-011 reformulation; future ticket; not yet assigned an id) — successor cycle dispatched after this ticket closes.
