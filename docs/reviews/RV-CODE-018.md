---
id: RV-CODE-018
version: 0.1.0
status: complete
verdict: pass_with_changes
---

# RV-CODE-018: Review of PR #35 — TKT-006 Telegram founder interaction

## 1. PR Reviewed

- **PR**: [#35](https://github.com/OpenClown-bot/developer-assistant/pull/35) (`tkt-006/telegram-founder-interaction`)
- **Title**: TKT-006: Implement Telegram founder interaction through Hermes
- **Author**: `OpenClown-bot`
- **Merge state**: `CLEAN`
- **Final reviewed HEAD**: `394968a30aee29d0bd7efd0f69b71d7a15e164df`
- **Files changed**:
  - `src/developer_assistant/telegram_adapter.py` — new runtime adapter module (517 lines)
  - `tests/test_telegram_adapter.py` — new unit tests (675 lines, 53 test methods)
  - `docs/tickets/TKT-006.md` — Section 10 Execution Log only (43 additions)

## 2. Ticket Reviewed

- **Ticket**: `docs/tickets/TKT-006.md` @ `0.3.0`
- **Status in PR**: `ready`
- **Scope alignment**: The PR stays within ticket scope. It implements the logic-layer Telegram founder interaction adapter for one trusted founder and one active project. It does not implement OpenClaw, web dashboard, autonomous merge, live VPS deployment, or marketplace skills. It does not wire into the actual Hermes Agent runtime or Telegram Bot API — this is acknowledged as a known limitation acceptable for a minimal v0.1 iter-1 stepping stone.

## 3. Architecture / ADR References

- **Architecture**: `docs/architecture/ARCH-001.md` @ `0.2.0`
- **Relevant architecture contracts**:
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md` @ `0.2.0`
  - `docs/architecture/HERMES-SKILL-ALLOWLIST.md` @ `0.1.0`
  - `docs/architecture/OPERATIONAL-STATE-STORE.md` @ `0.2.0`
- **Relevant ADRs**:
  - `ADR-001-platform-foundation.md` @ `0.2.0`
  - `ADR-002-repository-state.md` @ `0.2.0`
  - `ADR-003-plugin-supply-chain.md` @ `0.2.0`

## 4. CI Status

| Check | Conclusion | Notes |
|---|---|---|
| Docs CI (`validate-docs`) | **pass** | Completed 2026-05-02T22:03:11Z |
| PR-Agent (`Run PR Agent on every pull request`) | **pass** | Completed 2026-05-02T22:05:31Z; advisory findings recorded in Section 5 |
| Local docs validation | **pass** | `python scripts/validate_docs.py` — Docs validation passed. |
| Local unit tests | **1 failure** | 213 tests ran, 212 passed, 1 failed, 1 skipped. Failure: `test_durable_rejection_writes_artifact`. Executor PR body claimed 185 tests OK, 0 failed — this claim is inaccurate for the exact HEAD. |
| `pytest` availability | **unavailable** | Unittest fallback used, consistent with prior tickets. |

## 5. Findings (ordered by severity)

### High — Durable rejection and answer decisions are not written to artifacts

- **Location**: `src/developer_assistant/telegram_adapter.py:399–402`
- **Description**: In `_handle_freeform`, `artifact_target` is set for durable messages in categories `APPROVAL`, `REJECTION`, `ANSWER`, and other durable messages, but `self._artifact_writer.write()` is only called when `category == MessageCategory.APPROVAL`. Consequently, a founder’s durable rejection (e.g., “Отклоняю change в продакшн”) or a durable answer is classified correctly and marked `durable_decision=True`, yet it is never persisted to a repository artifact. This violates `HERMES-RUNTIME-CONTRACT.md` Section 8 (Decision Capture): “Decisions affecting product scope, architecture, security, credentials, merge policy, deployment … must be summarized into repository artifacts.” It also causes the included test `test_durable_rejection_writes_artifact` to fail on the exact Executor HEAD.
- **Recommendation** (required before merge): Change the write guard to include `REJECTION` and `ANSWER`:
  ```python
  if durable and artifact_target and category in (
      MessageCategory.APPROVAL,
      MessageCategory.REJECTION,
      MessageCategory.ANSWER,
  ):
      self._artifact_writer.write(artifact_target, f"Decision from {event.chat_key}: {event.text}")
  ```
  Then re-run the full test suite (`python -m unittest discover -s tests -p "test_*.py" -v`) and confirm zero failures.

### Medium — Executor-reported test count is inaccurate

- **Location**: PR #35 body and `docs/tickets/TKT-006.md` Section 10
- **Description**: The Executor reported “185 tests OK, 0 failed.” A fresh checkout of the exact Executor HEAD `394968a30aee29d0bd7efd0f69b71d7a15e164df` and full unittest discovery yields 213 tests with 1 failure (`test_durable_rejection_writes_artifact`). The reported count does not match reality.
- **Recommendation**: Update the Execution Log and PR body with the accurate test count and failure after applying the High finding fix.

### Medium — Logic-layer adapter only; no Hermes runtime or Telegram Bot API wiring

- **Location**: `src/developer_assistant/telegram_adapter.py` module-level docstring and `handle_event`
- **Description**: The adapter implements event handling, command routing, classification, and decision capture as a pure Python logic layer. It is not bound to Hermes Agent gateway APIs, Telegram Bot API polling/webhook handlers, or the SQLite operational state store from TKT-007. TKT-006 AC #1 states “Hermes can receive Telegram messages from an allowlisted founder chat.” This is structurally satisfied by `handle_event(TelegramEvent)`, but no actual Hermes or Telegram transport integration exists.
- **Recommendation**: Acceptable for v0.1 iter-1 minimal implementation. A follow-up ticket must bind this adapter to Hermes gateway behavior per `HERMES-RUNTIME-CONTRACT.md` Section 14 (“TKT for Hermes runtime adapter implementation”).

### Low — `validate_telegram_config_env` strict false-like casing

- **Location**: `src/developer_assistant/telegram_adapter.py:474–476`
- **Description**: The function accepts only `None`, `""`, `"false"`, `"False"`, `"0"` as safe false-like values for `GATEWAY_ALLOW_ALL_USERS` and `TELEGRAM_ALLOW_ALL_USERS`. Values such as `"FALSE"`, `"no"`, or `"No"` are treated as violations. This is a fail-closed posture (safe), but may surprise operators using common alternative casings.
- **Recommendation**: Document the exact allowed false-like strings in runtime setup docs, or optionally expand the accepted set to `("false", "False", "FALSE", "0", "no", "No", "NO", "off", "Off", "OFF")`. Not blocking for v0.1.

### Info — Authorization accepts chat OR user, not paired binding

- **Location**: `src/developer_assistant/telegram_adapter.py:263`
- **Description**: `FounderAuthorizer.is_allowed` returns `chat_ok or user_ok`. For the v0.1 threat model (one trusted founder, one active project), this is acceptable under `HERMES-SKILL-ALLOWLIST.md` Section 7.1, which allows DM pairing or user allowlist as alternatives.
- **Recommendation**: No change required for v0.1. If multi-tenant or multi-project scenarios are introduced later, require both chat AND user pairing.

### Info — Tests inspect private adapter attributes

- **Location**: `tests/test_telegram_adapter.py` (multiple lines, e.g., `adapter._projects`, `adapter._pending_questions`, `adapter._report_intervals`, `adapter._telegram_sender`)
- **Description**: Unit tests reach into underscored attributes to assert state changes. This is common for stateful adapters, but it couples tests to internal representation.
- **Recommendation**: Acceptable for v0.1. Ensure public API surface (`handle_event`, `route_specialist_question`, `send_progress_report`, `is_report_due`, `update_project_state`) remains the primary integration contract for the future Hermes runtime adapter.

### Info — Redundant conditional logic in `_handle_freeform`

- **Location**: `src/developer_assistant/telegram_adapter.py:393–398`
- **Description**: The `if` and `elif` branches both assign `artifact_target = "docs/questions/"` under different durable-category conditions, but the subsequent write guard only matches `APPROVAL`. The `elif` branch is reachable for durable `INTAKE`, `CLARIFICATION`, or `GENERAL_QUESTION`, yet no write occurs for those categories, leaving `artifact_target` set without a corresponding write.
- **Recommendation**: Simplify to a single `if durable and category in (APPROVAL, REJECTION, ANSWER):` block that both sets the target and performs the write, or document why non-decision durable categories still need an `artifact_target`. Not blocking.

## 6. Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Hermes can receive Telegram messages from an allowlisted founder chat. | **Partial** | `TelegramFounderAdapter.handle_event()` receives `TelegramEvent` and enforces allowlist via `FounderAuthorizer`. No actual Hermes runtime or Telegram Bot API wiring; acknowledged as v0.1 iter-1 minimal implementation. Follow-up ticket required for gateway binding. |
| 2 | `/new_project`, `/status`, `/decisions`, `/pause`, `/resume` behavior implemented. | **Pass** | All five commands dispatched in `_dispatch_command` with Russian responses, state mutation, and `/decisions` pending-question resolution. Tests cover each command plus bot-name suffix parsing. |
| 3 | Free-form founder messages classified into required categories. | **Pass** | `classify_message` returns exactly one of `intake`, `answer`, `clarification`, `approval`, `rejection`, `general_question`. Tests cover all categories in Russian and English, plus pending-question context. |
| 4 | Specialist-agent questions routed with context, options, recommendation, impact, urgency. | **Pass** | `SpecialistQuestion` enforces all fields, validates `urgency` values, and `to_russian_text()` renders Russian output. `route_specialist_question` stores the question and sends via `TelegramSender`. |
| 5 | Founder answers that affect durable decisions are written to repository artifacts. | **Partial** | Durable `APPROVAL` correctly triggers `artifact_writer.write()`. Durable `REJECTION` and `ANSWER` set `artifact_target` but do **not** trigger a write, causing a failing test and violating the decision-capture contract. Fix required before merge (see High finding). |
| 6 | Progress reports after milestones and on 30–60 minute schedule. | **Pass** | `is_report_due` enforces 30–60 min interval with clamping, milestone override, and first-report logic. `ProgressReport.to_russian_text()` produces Russian text with all required fields. |
| 7 | Telegram token and chat identifiers not committed. | **Pass** | No tokens, raw chat IDs, raw user IDs, `.env` files, or credential values in committed code. Fixtures use sanitized keys (`chat:founder`, `user:founder`, `chat:proj-alpha`). |
| 8 | Production `TELEGRAM_BOT_TOKEN` use follows `HERMES-SKILL-ALLOWLIST` constraints. | **Pass** | `validate_telegram_config_env` denies allow-all flags, requires `TELEGRAM_ALLOWED_USERS` or DM pairing, requires token presence, and enforces webhook secret in webhook mode. Polling is default. |
| 9 | `python scripts/validate_docs.py` passes. | **Pass** | Confirmed locally and in CI. |
| 10 | Relevant unit tests pass. | **Partial** | 212/213 tests pass. One failure (`test_durable_rejection_writes_artifact`) due to the durable-rejection write gap. Fix required before merge. |

## 7. Security / Process Notes

- **Secrets exposure**: None. No Telegram tokens, chat IDs, user IDs, `.env` files, PATs, API keys, or credential values were committed. All test fixtures use sanitized placeholder keys.
- **Telegram credential path**: The implementation does not broaden the reviewed Telegram credential-bearing path from TKT-012. It remains a logic-layer adapter with no actual Bot API calls. The security constraints (`validate_telegram_config_env`, `FounderAuthorizer`) align with `HERMES-SKILL-ALLOWLIST.md` Section 4.1 and Section 7.1.
- **Skill/plugin marketplace**: No marketplace skills, project-local plugins, OpenClaw plugins, or Hermes bundled GitHub credential-bearing skills are enabled or referenced in the code.
- **Autonomous merge / live deployment**: Not implemented. `/new_project` only sets an `artifact_intent` of `docs/prd/`; it does not create repositories, deploy, or merge.
- **Operational state vs repository authority**: Progress scheduling uses in-memory timestamps rather than the SQLite store from TKT-007. The adapter does not treat Telegram chat history or in-memory state as authoritative for durable decisions. The only gap is the missing write for durable rejections/answers (High finding).
- **Write zone compliance**: Confirmed. Only `src/developer_assistant/telegram_adapter.py`, `tests/test_telegram_adapter.py`, and `docs/tickets/TKT-006.md` Section 10 were modified. No changes to architecture, prompts, workflows, or PR metadata.
- **Import style**: Tests use `from src.developer_assistant.telegram_adapter import ...`, consistent with existing `test_state_store.py` and `test_github_workflow.py`.

## 8. Verdict

**`pass_with_changes`**

The PR satisfies the majority of TKT-006 acceptance criteria and aligns with ARCH-001, HERMES-RUNTIME-CONTRACT, HERMES-SKILL-ALLOWLIST, OPERATIONAL-STATE-STORE, and ADR-001/002/003. The command routing, classification, specialist question formatting, progress report scheduling, and secret hygiene are well-implemented and tested.

The blocking issue is a one-line logic gap in `_handle_freeform` that prevents durable `REJECTION` and `ANSWER` messages from being written to repository artifacts, which both fails an existing test and violates the durable-decision contract. The required fix is low-risk and localized: broaden the artifact-write guard to cover `REJECTION` and `ANSWER`, re-run the full test suite, and update the test count claim in the Execution Log. These changes can be made by the Executor before merge without another full review cycle.

The logic-layer-only nature of the adapter (no Hermes/Telegram API wiring) is an accepted v0.1 iter-1 limitation and must be tracked as a follow-up ticket.

## 9. Residual Risks

1. **No Hermes/Telegram Bot API integration**: The adapter is not wired to a real gateway. A follow-up ticket must implement the runtime adapter that binds `TelegramEvent` creation and `TelegramSender.send()` to actual Hermes/Telegram transport.
2. **In-memory progress timestamps**: `send_progress_report` and `is_report_due` use in-memory dicts. Process restart loses scheduling state. Production should migrate to the SQLite `scheduled_progress` table from TKT-007.
3. **Keyword-based classification**: `classify_message` uses regex heuristics. Ambiguous or sarcastic founder messages may be misclassified. An LLM-based classifier should be evaluated in a future iteration.
4. **All durable decisions routed to `docs/questions/`**: The adapter does not distinguish product decisions (`docs/prd/`), architecture decisions (`docs/architecture/adr/`), or ticket-level clarifications. This is acceptable for v0.1 but should be refined when the runtime adapter understands decision topics.
5. **Pending question overwrite**: `route_specialist_question` overwrites any existing pending question for the same chat without queueing. For v0.1 with one founder and one project, this is acceptable.

## 10. Founder Approval

- **Founder approval required:** yes
- **Founder approval status:** pending
- **Required before merge:**
  1. Executor applies the High finding fix (durable rejection/answer artifact write).
  2. Executor re-runs the full test suite and confirms zero failures.
  3. Executor updates `docs/tickets/TKT-006.md` Section 10 with corrected test counts.
  4. Founder acknowledges the residual risks (logic-layer only, in-memory timestamps, keyword heuristics).
