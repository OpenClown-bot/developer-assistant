---
id: TKT-037
version: 0.1.0
status: draft
arch_ref: ARCH-002@0.1.0
adr_ref: ADR-017@0.1.0
updated: 2026-05-10
---

# TKT-037: Escalation Modality Split — Mail/Nudge/Peek surface formatter

## 1. Scope

Implement ADR-017 (Escalation Modalities). Add a `modality` column to the `escalations` table with values `nudge | mail | peek`. Update the `dev-assist-escalation-surface` skill to branch on modality. Implement the daily-digest cron task for `mail`-modality entries. Wire the `paused_on_founder` work-item state transitions for `nudge`-modality escalations (the column itself was added in TKT-036; TKT-037 wires the surface behaviour and resume logic).

This ticket also amends `ESCALATION-POLICY.md` v0.1.1 → v0.1.2 to add a `modality` field on each rule in § 4 and on each verdict in § 5, plus introduces the new `AMEND_OR_ESCALATE` verdict variant for low-priority deviations that route to `mail`.


## 2. Non-scope

- AgentsMesh-style N:M Channels — Future Possibility per ARCH-002 § 10, triggered by second human added to project.
- Web-status surface enhancement showing modality-filtered escalations — TKT-040 or follow-up (web-status is the dev-assist-cli surface; v0.1 ships with `--modality nudge|mail|peek` flag).
- Response analytics (which modalities the Founder responds to fastest) — out of scope.


## 3. Required Context

- ADR-017 v0.1.0 § Decision (final spec).
- ADR-016 v0.1.0 § Decision G-COMPLETE-2 (attempt-exhaustion → nudge).
- ARCH-002 v0.1.0 § 3.8 (App-8), § 5.4 (Q-RESEARCH-002-04), § 6.2 (amendment).
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.3 (escalations table baseline).
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.6 (escalations schema).
- `ESCALATION-POLICY.md` v0.1.1 § 4 + § 5 + § 5.5 (deterministic rules + classifier + advisory narrative).
- TKT-023 (escalation plugin base — reference for plugin architecture).
- TKT-036 (work_items.status enum extended with `paused_on_founder`).


## 4. Acceptance Criteria

**AC-1.** Schema migration: `ALTER TABLE escalations ADD COLUMN modality TEXT NOT NULL DEFAULT 'nudge' CHECK (modality IN ('nudge','mail','peek'))`. Backward-compatible: all existing rows get `nudge`. Migration recorded under `docs/architecture/migrations/op-store-v0.3.x.md`.

**AC-2.** `dev-assist-escalation-surface` skill branches on modality:
- `nudge` → priority Telegram message via existing surface formatter (current behaviour) AND set originating runtime's `work_items.status` to `paused_on_founder`.
- `mail` → no immediate Telegram push; entry added to daily-digest queue.
- `peek` → no Telegram push, no daily-digest entry; only surfaces in `dev-assist-cli status` and web-status.

**AC-3.** Daily digest cron task: every day at a configurable local time (default 09:00 Founder TZ), scans for unread `mail`-modality entries since previous digest, batches them into a single Telegram message (Russian), marks them as `digested_at = now()` (new column added by this migration). If no unread mail entries exist, no digest is sent.

**AC-4.** Resume logic: when Founder responds to a `nudge`-modality escalation (via Telegram callback, `/approve <id>`, `/deny <id>`, or free-form), Orchestrator:
  - writes `responded_at`, `response_text`, `resolution_artifact_path` to escalations table;
  - transitions originating `work_items.status` from `paused_on_founder` back to `claimed`;
  - delivers the response to originating runtime via existing escalation-resume mechanism.

**AC-5.** Mapping rules implemented per ADR-017 § Decision "Mapping rules" — every existing trigger defaults to `nudge` (backward-compatible). New `AMEND_OR_ESCALATE` verdict in `ESCALATION-POLICY.md` § 5 routes to `mail`.

**AC-6.** `ESCALATION-POLICY.md` v0.1.2 amendment: each rule in § 4 and each verdict in § 5 has a `modality` field; new `AMEND_OR_ESCALATE` verdict variant added; § 5.5 advisory narrative call unchanged but documented as fired for nudge + mail (skipped for peek).

**AC-7.** `MULTI-HERMES-CONTRACT.md` § 6.3 amended with `modality` column. `OPERATIONAL-STATE-STORE.md` § 3.6 schema migration documented.

**AC-8.** `tests/test_escalation_modality.py` covers: schema migration backward compatibility (existing rows = nudge); each modality's surface behaviour (nudge → Telegram + work_item pause; mail → digest queue; peek → no push); daily-digest batching; resume logic for nudge; AMEND_OR_ESCALATE verdict routing.

**AC-9.** `python3 scripts/validate_docs.py` passes.

**AC-10.** `paused_on_founder_stuck` failure mode (per ARCH-002 § 6.4): cron task scans for work_items in `paused_on_founder` for > 24h; emits a mail-modality reminder. Test covers the 24h-stuck path.


## 5. Allowed Files

- `src/escalation/surface.py` (extend)
- `src/escalation/digest.py` (NEW — daily-digest cron task)
- `src/escalation/resume.py` (NEW or extend — Founder-response → resume logic)
- `tests/test_escalation_modality.py` (NEW)
- `docs/architecture/shared-skills/dev-assist-escalation-surface/SKILL.md` (extend per branching logic; Architect-zone authorship justified by ADR-017 § Decision explicit pointer to TKT-037)
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (§ 6.3 amendment only)
- `docs/architecture/OPERATIONAL-STATE-STORE.md` (§ 3.6 amendment only)
- `docs/architecture/ESCALATION-POLICY.md` (v0.1.1 → v0.1.2 amendment, modality fields + AMEND_OR_ESCALATE)
- `docs/architecture/migrations/op-store-v0.3.x.md` (extend with escalations.modality migration)


## 6. Test Strategy

Test pyramid for this ticket:

- **Unit (`tests/test_escalation_modality.py`):** schema migration backward compatibility (existing rows = nudge); each modality's surface-formatter branch (nudge → Telegram + work_item pause; mail → digest queue; peek → no push); daily-digest batching (no entries → no send; multiple entries → single batch); resume logic for nudge (responded_at write + work_items.status transition).
- **AMEND_OR_ESCALATE verdict:** `ESCALATION-POLICY.md` § 5 classifier tested with new verdict variant routing to `mail`.
- **Stuck-paused detection:** work_item in `paused_on_founder` for > 24h triggers reminder (mocked clock).
- **Integration:** end-to-end escalation lifecycle — runtime emits nudge, Telegram delivered, work_item paused, Founder responds, work_item resumed, escalation row resolution_artifact_path written.


## 7. Risk Notes

Primary risk: backward-compatibility default-to-nudge could create false-positive Telegram fatigue if a future rule author forgets to opt-in to mail/peek for low-priority signals. Mitigation: ESCALATION-POLICY.md v0.1.2 documents the modality-defaulting rule explicitly and the Reviewer rubric (TKT-038 gate-tagging) catches misclassified findings at PR review time. Secondary risk: daily-digest cron timing in Founder TZ — TZ misconfiguration could cause 23-hour or 25-hour gaps; mitigation: configurable via env var with sensible default and explicit error on missing/invalid TZ.


## 8. Spec Amendment Notes

Hard rules for this ticket (governance constraints inherited from ARCH-002 + the source ADR; Executor MUST observe):


- Do NOT modify `dev-assist-escalation-policy` plugin (the deterministic classifier in `ESCALATION-POLICY.md` § 5) — only adapt how its verdicts map to modality. The classifier algorithm itself stays pure and deterministic per ADR-008.
- Do NOT modify `work_queue/dispatcher.py` or `work_queue/complete.py` — TKT-036's write zone (TKT-037 receives the `paused_on_founder` enum extension as input).
- Daily-digest local time MUST be configurable via env var (default 09:00 Founder TZ); DO NOT hardcode.
- Schema migration must be additive (no DROP / no destructive ALTER on existing escalation rows).
- All Telegram surface behaviour preserves existing Russian narrative quality; advisory-narrative LLM call (per `ESCALATION-POLICY.md` § 5.5) MUST stay outside decision path.


## 9. Cross-references

- ADR-017 v0.1.0 (Escalation modalities).
- ADR-016 v0.1.0 § Decision G-COMPLETE-2 (attempt-exhaustion → nudge).
- ADR-008 v0.1.1 (deterministic classifier).
- ARCH-002 v0.1.0 § 3.8, § 5.4, § 6.2.
- RESEARCH-002 § 6.1 (Gas Town), § 6.8 (Ralph), § 7.4.
- `MULTI-HERMES-CONTRACT.md` v0.2.1 § 6.3.
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.6.
- `ESCALATION-POLICY.md` v0.1.1 § 4 + § 5 + § 5.5.


## 10. Execution Log

(Reserved for Executor cycle.)
