---
id: RV-CODE-019
version: 0.1.0
status: approved
verdict: pass
reviewer_model: kimi-k2.6
created: 2026-05-04
approved_at: 2026-05-04
approved_by: Strategic Orchestrator
approved_note: SO audit confirmed PR #47 and PR #48 were already merged with green Docs CI, green PR-Agent, Reviewer verdict pass, and merged-main validation passing.
---

# RV-CODE-019: Review of PR #47 — TKT-015 Wire Telegram adapter to Hermes gateway transport

## 1. PR Reviewed

- **PR**: [#47](https://github.com/OpenClown-bot/developer-assistant/pull/47) (`tkt-015/telegram-gateway-transport`)
- **Title**: TKT-015: Wire Telegram adapter to Hermes gateway transport
- **Author**: `OpenClown-bot`
- **Head SHA**: `65ea130af3d4d548786b694b3cf2160e490f3ce6`
- **Base SHA**: `e0cb258c883c7b91d10b54ff78f64d4cffda4ff9`
- **Merge state**: `CLEAN`
- **Files changed**:
  - `src/developer_assistant/hermes_telegram_transport.py` (new, 267 lines)
  - `tests/test_hermes_telegram_transport.py` (new, 838 lines, 81 test methods)
  - `docs/tickets/TKT-015.md` (Section 10 Execution Log only, 56 additions / 1 removal)

## 2. Ticket Reviewed

- **Ticket**: `docs/tickets/TKT-015.md` @ `0.1.0`
- **Status at review time**: `ready`
- **Scope alignment**: The PR stays strictly within TKT-015 scope. It wires the completed TKT-006 Telegram founder interaction adapter to a Hermes Telegram gateway transport boundary without modifying the adapter, without implementing GitHub executor binding, without implementing the full Telegram-to-PR trial, and without enabling any blocked capabilities.

## 3. Architecture / ADR References

- **Architecture**: `docs/architecture/ARCH-001.md` @ `0.2.0`
- **Relevant contracts**:
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md` @ `0.2.0`
  - `docs/architecture/HERMES-SKILL-ALLOWLIST.md` @ `0.1.0`
  - `docs/architecture/OPERATIONAL-STATE-STORE.md` @ `0.2.0`
- **Relevant ADRs**:
  - `ADR-001-platform-foundation.md` @ `0.2.0`
  - `ADR-002-repository-state.md` @ `0.2.0`
  - `ADR-003-plugin-supply-chain.md` @ `0.2.0`
- **Dependencies reviewed**:
  - `TKT-006.md` @ `0.3.0` (done)
  - `TKT-008.md` @ `0.3.0` (done)
  - `TKT-011.md` @ `0.1.0` (draft, correctly not implemented)
  - `TKT-014.md` @ `0.1.0` (done)
  - `TKT-NEW-008-D.md` @ `0.1.0` (backlog, correctly not implemented)

## 4. CI Status

| Check | Conclusion |
| --- | --- |
| Docs validation (`python scripts/validate_docs.py`) | **pass** |
| Unit tests (`python -m unittest discover -s tests -p "test_*.py" -v`) | **pass** — 387 tests, 0 failures, 1 skipped |

## 5. Findings

### minor — `deliver()` and `deliver_as_sender()` duplicate message-delivery logic

- **Location**: `src/developer_assistant/hermes_telegram_transport.py:202-207` and `:220-221`
- **Description**: Both methods repeat the same `isinstance(result, CommandResult)` check, `text` extraction, factory fallback, and callback invocation. `deliver_as_sender()` could delegate to `self.deliver(result, callback=None)` to avoid drift.
- **Recommendation**: Refactor `deliver_as_sender` to call `self.deliver(result)` so that outbound text extraction and fallback logic live in a single place.

### minor — `_outbound_sender` attribute is declared but never initialized or used

- **Location**: `src/developer_assistant/hermes_telegram_transport.py:12` (inside `__init__`)
- **Description**: `self._outbound_sender: TelegramSender` is declared without assignment or subsequent use. `create_sender()` returns a fresh instance each time instead of caching it in this attribute.
- **Recommendation**: Either remove the unused declaration, or initialize it (e.g., `self._outbound_sender = self.create_sender()`) and reuse it if the intent is to keep a single sender reference.

### minor — `test_config_stores_no_token_values` is vacuously true

- **Location**: `tests/test_hermes_telegram_transport.py` (TransportConfig validation test class)
- **Description**: `TransportConfig` has no `str`-typed fields (all fields are `bool`, `List[str]`, or `Dict[str,str]`). The `for v in as_dict.values(): if isinstance(v, str) and v:` loop therefore never exercises `assertNotIn`, making the test trivially pass without verifying anything.
- **Recommendation**: If the intent is to guard against accidental token fields, assert that no field named `bot_token`, `token`, or similar exists on the dataclass, or test `validate_transport_config_env` instead.

### observation — `sanitize_gateway_payload` discards raw identifiers by design

- **Location**: `src/developer_assistant/hermes_telegram_transport.py:224-234`
- **Description**: The function accepts `raw_chat_id` and `raw_user_id` but returns a payload using the caller-provided `chat_label` and `user_label`. This is the correct sanitization contract, but the parameter naming could be misread as using the raw values.
- **Recommendation**: Keep as-is; the signature documents that raw inputs are expected at the boundary and must be mapped by the caller.

### praise — Transport uses existing TKT-006 public API without adapter modifications

- **Location**: `src/developer_assistant/hermes_telegram_transport.py`
- **Description**: The transport layer imports only public types from `telegram_adapter.py` and does not modify the adapter. This confirms the adapter API designed in TKT-006 is sufficient for a clean transport boundary.

### praise — Strong security-hygiene enforcement at the transport boundary

- **Location**: `HermesGatewayPayload.validate()`, `TransportConfig.validate()`, `validate_transport_config_env()`
- **Description**: Raw numeric chat/user IDs are rejected, allow-all modes are treated as violations that disable authorization, bot token presence is checked via a boolean flag (never the value), and no secrets appear in committed code.

### praise — Comprehensive test coverage for all 9 acceptance criteria

- **Location**: `tests/test_hermes_telegram_transport.py`
- **Description**: 81 new tests cover payload validation, config validation, authorization, inbound wiring, all five Telegram commands, free-form classification, specialist-question delivery, founder-answer capture, progress-report delivery, outbound sender behavior, token/ID leak prevention, and adapter behavior preservation.

## 6. Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Inbound Hermes gateway messages converted to `TelegramEvent` without raw private IDs in artifacts, fixtures, logs, or errors | **pass** | `HermesGatewayPayload.validate()` rejects numeric chat/user IDs; `sanitize_gateway_payload()` maps raw IDs to sanitized labels; no raw IDs appear in code or tests |
| 2 | Inbound transport enforces founder allowlist or DM pairing; allow-all modes remain disabled | **pass** | `TransportConfig.is_authorized()` requires allowlist/DM pairing and returns `False` when allow-all flags are set; tests cover all paths |
| 3 | Outbound `TelegramSender.send()` delivered through reviewed Hermes gateway path; Russian text preserved | **pass** | `HermesTelegramSender` implements `TelegramSender` via injectable `OutboundCallback`; `deliver()` preserves `message_ru` from `CommandResult`; Russian smoke tests verify `/status`, `/pause`, `/resume`, etc. |
| 4 | Runtime config validation enforces TKT-012 / `HERMES-SKILL-ALLOWLIST.md` constraints | **pass** | `validate_transport_config_env()` and `TransportConfig.validate()` reject allow-all flags, require allowlist or DM pairing, require bot token presence, prefer polling, and require webhook secret in webhook mode |
| 5 | Smoke coverage demonstrates commands through transport boundary | **pass** | Tests for `/new_project`, `/status`, `/decisions`, `/pause`, `/resume`, free-form classification, specialist-question delivery, founder-answer capture, and progress-report delivery |
| 6 | Smoke-test documentation records sanitized info without tokens/IDs | **pass** | TKT-015 Section 10 Execution Log documents sanitized keys, no token values, no raw IDs, and states live smoke test was not run due to credential unavailability |
| 7 | Implementation does not enable Hermes bundled GitHub skills, marketplace skills, project-local plugins, OpenClaw plugins, autonomous merge, or live deployment | **pass** | No such capabilities are imported, configured, or referenced in the PR; Security Confirmation in Execution Log explicitly denies all |
| 8 | Existing TKT-006 adapter behavior remains covered by unit tests; new transport tests use mocked inputs | **pass** | `TestExistingAdapterBehaviorPreserved` (5 tests) verifies adapter commands, classification, and rejection remain intact; all transport tests use `_make_payload`, `_RecordingOutboundCallback`, and lambda factories with no live credentials |
| 9 | `python scripts/validate_docs.py` and `python -m unittest discover -s tests -p "test_*.py" -v` pass | **pass** | Both ran successfully: docs validation passed; 387 tests passed, 0 failures, 1 skipped |

## 7. Security / Process Notes

- **Secrets exposure**: None. No Telegram bot tokens, raw chat IDs, raw user IDs, PATs, API keys, or VPS credentials appear in committed artifacts.
- **Write zone compliance**: Confirmed. Only files within TKT-015 allowed zone were modified (new transport source, new transport tests, TKT-015 Section 10 Execution Log). `telegram_adapter.py` and all other source files are untouched.
- **Scope compliance**: TKT-NEW-008-D (live GitHub REST/git executor binding) is not implemented. TKT-011 (full Telegram-to-PR trial) is not implemented. OpenClaw, marketplace skills, project-local plugins, autonomous merge, and live deployment are not enabled.
- **Allow-all modes**: `GATEWAY_ALLOW_ALL_USERS` and `TELEGRAM_ALLOW_ALL_USERS` are treated as violations that disable authorization. No allow-all mode is enabled by default.
- **Hermes bundled GitHub skills**: Not enabled. No `github-pr-workflow`, `github-issues`, or `github-auth` references appear.

## 8. Verdict

**pass**

The PR fully satisfies all 9 TKT-015 acceptance criteria, passes CI, introduces no security violations, preserves existing TKT-006 adapter behavior, and stays strictly within the allowed write zone. The minor findings (method-level duplication, unused attribute, and a vacuous test) are non-blocking code-quality observations that can be addressed in a follow-up or accepted as-is for v0.1. No hard-stop conditions are triggered.

## 9. Residual Risks

- Live Hermes Telegram gateway payload shape may differ from the mocked format used in tests; a small shim or follow-up adjustment may be needed when credentials are available.
- Progress scheduling remains in-memory only (not persisted through SQLite). A follow-up ticket is suggested if Hermes deployment requires durable scheduling.
- The transport boundary is tested with mocks; a live smoke test is still required before TKT-011.

## 10. Founder Approval

- **Founder approval required:** yes
- **Founder approval status:** approved by merge of PR #47 and PR #48 on 2026-05-04
