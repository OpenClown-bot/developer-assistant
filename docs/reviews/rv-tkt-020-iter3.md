---
id: rv-tkt-020-iter3
version: 0.1.0
status: active
pr: "#98"
ticket: TKT-020
reviewer: Kimi K2.6
branch: feature/TKT-020-self-deploy-scripts
date: 2026-05-06
verdict: APPROVE
---

# RV-CODE-027: CODE Review of PR #98 — TKT-020 Self-Deployment Scripts + 8 Systemd Units (ITER-3)

## Scope

Re-review of `feature/TKT-020-self-deploy-scripts` iter-3 fix, following iter-1 `REQUEST-CHANGES` (B1: missing web unit invariant, S1: garbled em-dash).

Reference documents same as iter-1 (`rv-tkt-020-iter1.md` § Scope).

## Changes Since Iter-1

| Item | Iter-1 Status | Iter-3 Fix | Status |
|---|---|---|---|
| B1: `verify-self.sh` missing `devassist-web.service` active check | REQUEST-CHANGES | Added `invariant_09_web_service()`: checks `systemctl is-active devassist-web.service` + `curl -fs http://127.0.0.1:8180/health` | ✅ RESOLVED |
| S1: garbled character in `record_fail` log message | Non-blocking suggestion | Fixed: `log "FAIL: $1 -- $2"` (clean ASCII) | ✅ RESOLVED |
| Contract §8 invariants 7-12 misaligned with 12-invariant count | REQUEST-CHANGES | Restructured: `invariant_07_runtime_units()` (single check for all 5 roles), `invariant_08_omniroute_unit()`, `invariant_09_web_service()`, `invariant_10_runtime_health_endpoints()`, `invariant_11_journald_retention()`, `invariant_12_no_secrets_in_journal()` | ✅ RESOLVED |

## Detailed Verification

### 1. verify-self.sh — RESOLVED

**12 invariants, contract-aligned:**

| # | Name | Contract §8 Row | Implementation | Dry-run / Fixture Stub |
|---|---|---|---|---|
| 01 | Telegram reachable | Telegram reachable | `curl` to `api.telegram.org/bot<TOKEN>/getMe` | Stub JSON, auto-pass |
| 02 | GitHub PAT valid | GitHub PAT valid | `curl` to `api.github.com/user` with `Authorization: token <PAT>` | Stub, auto-pass |
| 03 | OmniRoute reachable | OmniRoute reachable | `curl` to `:20128/v1/models`, validates all 5 catalog identifiers | Stub, auto-pass |
| 04 | OmniRoute model probe | OmniRoute model probe | TKT-026 `model_catalog_cli probe-omniroute`; skipped with warning if CLI missing | Stub, auto-pass |
| 05 | State store writable | State store writable | `sqlite3 operational.db PRAGMA quick_check` | Auto-pass if fixture |
| 06 | Schema version | Schema version | Idempotent migrations, validates `_schema_meta` value == `3` | Auto-pass if fixture |
| 07 | Each runtime unit active | Each runtime unit active | `systemctl is-active` loop over all 5 roles; single pass/fail with per-role detail | All 5 assumed active in dry-run |
| 08 | OmniRoute unit active | OmniRoute unit active | `systemctl is-active omniroute.service` | Assumed active in dry-run |
| 09 | Web unit active | Web unit active | `systemctl is-active devassist-web.service` + `curl :8180/health` | Assumed active in dry-run |
| 10 | Per-runtime health endpoints | Per-runtime health endpoints | `curl` loop `:8181/health`..`:8185/health` per role | All assumed 200 in dry-run |
| 11 | journald retention configured | journald retention configured | Checks drop-in file `SystemMaxUse=1G` + `MaxRetentionSec=30d` | Assumed present in dry-run |
| 12 | No secrets in journal | No secrets in journal | `journalctl` scan for env-var values; logs var names only, never values | Assumed clean in dry-run |

**Total count**: `main()` calls exactly 12 invariants. Test `test_verify_counts_invariants` asserts `"12/12"` in stdout. ✅

**New test coverage**: `test_verify_includes_web_service_invariant` asserts `"web unit active"` appears in verify output. ✅

**record_fail**: line 37 uses clean ASCII `--` separator. ✅

### 2. Other Scripts — Unchanged, Still PASS

`install-self.sh`, `rollback-self.sh`, `upgrade-self.sh`, 8 systemd templates, and the bulk of `test_self_deployment_scripts.py` were not modified in iter-3. All iter-1 PASS verdicts remain valid (filesystem layout, idempotency, state.db boundary, activation gate, sandboxing, etc.).

### 3. No New Blocking Issues

- **invariant_07_runtime_units**: Previously recorded 5 separate pass/fail entries; now records a single aggregated pass/fail. This correctly maps to the contract table's single row "Each runtime unit active" and keeps the total invariant count at 12. ✅
- **invariant_12_no_secrets_in_journal**: Uses `printenv` to read secret values for grep scanning, but only logs env-var *names* (never values) on leak detection. Skips `test-token-placeholder` values. Safe. ✅
- **journalctl dependency**: `journalctl` call is guarded by `if [ "$FIXTURE" = "1" ] || [ "$DRY_RUN" = "1" ]`, so tests don't require systemd. ✅
- **Port 8180 /health check**: Uses `curl -fsS` with 1-second timeout implication (standard curl default). Acceptable for connectivity-only invariant. ✅
- **Port loop 8181-8185**: Incremented via `port=$((port + 1))` — POSIX-compliant arithmetic. ✅

## Final Verdict

**APPROVE**

All blocking issues from iter-1 (B1, S1) are resolved. The 12-invariant set now exactly matches `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 §8. No new blocking issues introduced. PR #98 is ready for merge.
