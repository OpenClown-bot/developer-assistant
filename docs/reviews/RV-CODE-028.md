---
id: RV-CODE-028
version: 0.1.0
status: draft
verdict: pass_with_changes
---

# RV-CODE-028: Review of PR #107 — TKT-028 Structured Per-Runtime Logging And `work_item_id` Propagation

## 1. PR Reviewed

- **PR**: #107 (`tkt/028-structured-logging-work-item-id`)
- **Scope**: Structured JSON-line logging, `work_item_id` contextvar propagation, LLM-call decorator, OmniRoute header injector, and Hermes plugin adapter.
- **Files changed** (7 files, ~996 additions):
  - `src/developer_assistant/observability/__init__.py`
  - `src/developer_assistant/observability/omniroute_header.py`
  - `src/developer_assistant/observability/structured_logger.py`
  - `src/developer_assistant/plugins/__init__.py`
  - `src/developer_assistant/plugins/structured_logging_plugin.py`
  - `tests/test_structured_logger.py`
  - `tests/test_work_item_id_propagation.py`

## 2. Ticket Reviewed

- **Ticket**: `docs/tickets/TKT-028.md`
- **Status at review time**: `in_review`
- **Scope alignment**: The PR implements the core structured logger, `work_item_id` propagation primitives, the LLM-call decorator, the OmniRoute header injector, and the Hermes plugin adapter. It does **not** include an Orchestrator code path that binds `work_item_id` to Telegram-message-driven requests (§4 acceptance criterion #7). This is consistent with the PR description, which limits itself to the logger/decorator/plugin/header stack and explicitly states it does not modify the CLI, schema, or systemd units. The Orchestrator binding is a runtime-integration gap that should be addressed in a follow-up PR or a downstream ticket (e.g., TKT-021 runtime renderer).

## 3. Architecture / ADR References

- **Architecture**: `docs/architecture/OBSERVABILITY-CONTRACT.md` v0.1.1 § 4 (FR-OBS-01) and § 5 (FR-OBS-02)
- **Relevant ADRs**: ADR-010-observability-shape.md, ADR-011-routing-layer.md
- **Other contracts referenced**:
  - `docs/architecture/HERMES-RUNTIME-CONTRACT.md` v0.2.0 (plugin loader reference; note: § 11.3 in the checked-in version covers "Dangerous Command Approval" rather than plugin loading; the plugin contract is inferred from the ticket scope and common Hermes plugin conventions)
  - `docs/architecture/OPERATIONAL-STATE-STORE.md` v0.3.0 (work_items schema and propagation semantics)

## 4. CI Status

| Check | Conclusion |
| --- | --- |
| validate-docs | **pass** (SUCCESS on PR) |
| PR Agent | **pass** (SUCCESS on PR) |
| Targeted tests (`test_structured_logger.py`, `test_work_item_id_propagation.py`) | **pass** (24/24 passed) |
| Full suite (`pytest tests/`) | **pass** (959 passed, 36 skipped) |

## 5. Findings

### minor — `_JsonFormatter` calls `datetime.now()` twice per log line

- **Location**: `src/developer_assistant/observability/structured_logger.py` (`_JsonFormatter.format`, `ts_iso` construction)
- **Description**: The timestamp is built by concatenating `strftime` from one `datetime.datetime.now(datetime.timezone.utc)` call with milliseconds from a second `now()` call. If the wall clock crosses a second boundary between the two calls, `ts_iso` may contain a seconds component from the first call and a millisecond component from the second, producing an inconsistent timestamp.
- **Recommendation**: Capture `now = datetime.datetime.now(datetime.timezone.utc)` once, then format `ts_iso` from that single object.

### info — `_extra_payload` convention is undocumented

- **Location**: `src/developer_assistant/observability/structured_logger.py` (module-level)
- **Description**: Callers are expected to pass `extra={"event": "...", "_extra_payload": {...}}` so that additional fields are unpacked into the JSON log line. This convention is not explained in any docstring or module-level comment.
- **Recommendation**: Add a short module docstring paragraph or a comment block describing the `_extra_payload` unpacking convention.

### minor — `dequeue_wrapper` is synchronous and may prematurely clear context for async `fn`

- **Location**: `src/developer_assistant/plugins/structured_logging_plugin.py` (`dequeue_wrapper`)
- **Description**: `dequeue_wrapper` is a sync function. If `fn` is an async coroutine function, `fn(*args, **kwargs)` returns a coroutine object; the `finally` block (which calls `_manager.clear_work_item_context()`) executes before the coroutine is awaited, meaning the `work_item_id` context is cleared too early for async work-item handlers.
- **Recommendation**: Provide an `async_dequeue_wrapper` variant, or add a docstring explicitly documenting that this wrapper is intended for synchronous dequeue handlers only.

### info — `inject_work_item_header` is a sync hook used with async `httpx`

- **Location**: `src/developer_assistant/observability/omniroute_header.py`
- **Description**: `httpx.AsyncClient` does invoke sync `request` event hooks, so the hook works in practice. A brief docstring confirming this is intentional would prevent future refactor attempts to "asyncify" it unnecessarily.
- **Recommendation**: Add a one-line docstring or comment noting that sync event hooks are valid for async httpx clients.

### info — `omniroute_header.py` has no unit-test coverage

- **Location**: `src/developer_assistant/observability/omniroute_header.py`
- **Description**: The module is small (two functions, ~12 lines of logic) and relies on a contextvar read plus a header mutation. No dedicated tests verify that the header is injected when the contextvar is set and omitted when it is `None`.
- **Recommendation**: Add a lightweight test file (e.g., `tests/test_omniroute_header.py`) covering `inject_work_item_header` with a mock request object and `build_headers_with_work_item` with/without a set contextvar.

### info — `set_manager()` is a module-level global setter

- **Location**: `src/developer_assistant/observability/structured_logger.py`
- **Description**: `_MANAGER` is a module global mutated by `set_manager()`. This is the simplest v0.1 integration path between the logger and `ObservabilityManager`, and it is only written once at plugin startup. Acceptable for v0.1.
- **Recommendation**: Record a TODO or architecture note for a future DI refactor; not blocking.

## 6. Acceptance Criteria Assessment

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `structured_logger.py` exists, imports cleanly, exposes required API (`get_logger`, `work_item`, `instrument_llm_call`, `init_runtime_logger`) | **pass** | Module present; public API exported in `__init__.py` |
| 2 | `get_logger(...).info(...)` emits JSON-line with all mandatory fields | **pass** | `TestMandatoryFields` asserts presence of `ts_iso`, `level`, `runtime_role`, `work_item_id`, `model`, `tokens_in`, `tokens_out`, `latency_ms`, `event`, `message` |
| 3 | `runtime_role` from env var; defaults to `"unknown"` with one-time warning | **pass** | `TestMandatoryFields::test_runtime_role_defaults_to_unknown` |
| 4 | `work_item(...)` context manager propagates `work_item_id` across `asyncio.create_task` and `threading.Thread` | **pass** | `TestWorkItemIdContextVar` covers asyncio, `dispatch_in_thread`, raw thread isolation, and null-outside-block |
| 5 | `@instrument_llm_call(model_id=...)` wraps sync and async LLM calls, emits `.start`, `.complete`, `.fail` with metadata | **pass** | `TestInstrumentLLMCallDecorator` covers sync, async, exception, plain dict, object response |
| 6 | Decorator never logs prompt/completion content | **pass** | `test_decorator_no_prompt_content_in_log` asserts `"SENSITIVE"`, `"secret prompt"`, and `"xyz789"` are absent from log output |
| 7 | Orchestrator code path binds `work_item_id` to Telegram-driven dispatch | **deferred** | Not present in this PR; out of PR scope per PR description; should be wired in runtime-integration follow-up |
| 8 | Specialist runtime claims `work_items` row and pushes `id` onto contextvar | **pass** | `dequeue_wrapper` in `structured_logging_plugin.py` performs this; also covered by synthetic pipeline test |
| 9 | Downstream runtime inherits same `work_item_id` | **pass** | `work_item()` contextvar propagates across awaited coroutines; synthetic four-step pipeline test validates |
| 10 | Child work items carry distinct `work_item_id`; parent recoverable via `parent_id` | **pass** | `test_parent_child_distinct_work_item_ids` validates nested scopes and distinct IDs |
| 11 | `omniroute_header.py` injects `X-DEVASSIST-Work-Item-Id` header | **pass** | Module implements `inject_work_item_header` and `build_headers_with_work_item` using `_WORK_ITEM_ID` contextvar |
| 12 | Tests cover JSON shape, contextvar, decorator, no-secrets, missing-role | **pass** | 24 targeted tests pass |
| 13 | Plugin integrates as Hermes plugin | **pass** | `structured_logging_plugin.py` exposes `load()`, `startup()`, `shutdown()`, `dequeue_wrapper()` |
| 14 | No real secrets or provider keys in tests | **pass** | Manually inspected diff; all fixtures use synthetic values |
| 15 | Docs validation passes | **pass** | `python scripts/validate_docs.py` passed locally and in CI |
| 16 | Full unittest discovery passes | **pass** | `pytest tests/` passes (959 passed, 36 skipped) |

## 7. Security / Process Notes

- **Secrets exposure**: None found. No `.env`, tokens, API keys, or hostnames committed.
- **Write zone compliance**: **confirmed**. All changed files are within the Executor write zone (`src/`, `tests/`).
- **Integration with TKT-031**: The `@instrument_llm_call` decorator emits JSON log lines to stderr; the `InstrumentedLLMClient` (pre-existing from TKT-031) writes SQLite rows via `ObservabilityManager.record_llm_call()`. They target different sinks and do not double-write or conflict when used at their intended layers. If both are applied to the same call path, the decorator produces a JSON log event while the client produces a SQLite row—acceptable parallel observability.
- **OBSERVABILITY-CONTRACT §4 compliance**: Every JSON log line emitted by `_JsonFormatter` contains all ten mandatory fields.

## 8. Verdict

**pass_with_changes**

The PR successfully implements the core structured logging infrastructure, `work_item_id` contextvar propagation, the LLM-call decorator, the OmniRoute header injector, and the Hermes plugin adapter. All 24 targeted tests pass, the full suite passes, CI is green, mandatory fields are present in every JSON line, and prompt/completion content is never logged. Write zones are respected and no secrets are introduced.

The recommended changes are minor and do not block merge:
1. Capture `datetime.now()` once in `_JsonFormatter`.
2. Document the `_extra_payload` convention.
3. Add an async variant or a sync-only constraint note for `dequeue_wrapper`.
4. Confirm sync-event-hook usage in a docstring for `inject_work_item_header`.
5. Add lightweight unit tests for `omniroute_header.py`.

One acceptance criterion (Orchestrator code path binding `work_item_id` to Telegram dispatch) is not satisfied in this PR, but it is acknowledged as out of the PR's stated scope and should be wired in a downstream runtime-integration ticket.

## 9. Residual Risks

- The `dequeue_wrapper` sync/async mismatch may cause premature context clearing if a future runtime adapter passes an async handler into the sync wrapper without first awaiting the coroutine.
- `_extra_payload` is an internal convention; without documentation, future contributors may incorrectly place extra fields directly in `extra={}` and find they are silently dropped or collide with `logging` reserved attributes.
- The `ObservabilityManager.from_env()` default for `DEVASSIST_RUNTIME_ROLE` is `"executor"` (TKT-031), while the structured logger defaults to `"unknown"`. If the env var is missing, SQLite rows and JSON log lines will disagree on the runtime role.

## 10. Founder Approval

- **Founder approval required:** yes
- **Founder approval status:** pending
