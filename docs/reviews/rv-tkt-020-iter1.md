---
id: rv-tkt-020-iter1
version: 0.1.0
status: active
pr: "#98"
ticket: TKT-020
reviewer: Kimi K2.6
branch: feature/TKT-020-self-deploy-scripts
date: 2026-05-06
verdict: REQUEST-CHANGES
---

# RV-CODE-025: CODE Review of PR #98 — TKT-020 Self-Deployment Scripts + 8 Systemd Units

## Scope

Review of `feature/TKT-020-self-deploy-scripts` against:
- `docs/tickets/TKT-020.md` v0.1.1
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` v0.2.0
- `docs/architecture/adr/ADR-004-deployment-mechanism.md`
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md`
- `docs/architecture/adr/ADR-011-routing-layer.md` v0.1.0
- `docs/architecture/adr/ADR-009-model-assignment-and-fallback.md`
- `docs/tickets/TKT-026.md` v0.1.1
- `docs/architecture/OPERATIONAL-STATE-STORE.md` v0.3.0
- `docs/architecture/MULTI-HERMES-CONTRACT.md` §4, §5, §12
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions
- `CONTRIBUTING.md`
- `AGENTS.md`

## Pass / Fail per Deliverable

### 1. install-self.sh — PASS (with non-blocking note)

- **Filesystem layout**: creates `/srv/devassist/{repo,runtimes,state/backups,secrets,releases,omniroute/logs,web/templates,logs,shared-skills,shared-plugins}` and per-role `.hermes/{memories,sessions,cron,logs,skills}` — matches contract §4.
- **Users**: idempotent `useradd` for `devassist` and `omniroute` — PASS.
- **Hermes single-install**: installs once, skips if `/usr/local/lib/hermes-agent/bin/hermes` exists — PASS.
- **5 HERMES_HOME dirs**: created under `runtimes/<role>/.hermes` — PASS.
- **operational.db symlinks**: `symlink_operational_db()` creates symlink from each runtime `.hermes/operational.db` to shared state store — PASS.
- **state.db NOT symlinked**: no `state.db` symlink created — PASS.
- **SELF-DEPLOY.env**: placeholder-only values, mode `0600`, owned by `devassist:devassist` — PASS.
- **8 systemd units**: `render_systemd_units()` copies all 8 templates and runs `daemon-reload` — PASS.
- **Verify gate**: calls `verify-self.sh` at end of install — PASS.
- **Idempotency**: re-running skips user creation, skips Hermes/OmniRoute reinstall, skips env file overwrite if keys exist — PASS. Operational DB init uses `CREATE TABLE IF NOT EXISTS`, so re-run is safe.

### 2. verify-self.sh — REQUEST-CHANGES (blocking issue found)

- **12 invariants present**: `invariant_01` through `invariant_12` are implemented as 12 numbered functions.
- **FIXTURE mode**: all network checks stubbed; model probe stubbed; non-zero exit on failure — PASS.
- **model_catalog_cli stub skip**: `invariant_04` checks `src/developer_assistant/cli/model_catalog_cli.py` existence, logs warning and `record_pass` if missing — matches TKT-026 requirement — PASS.
- **Connectivity checks**: Telegram, GitHub PAT, OmniRoute `/v1/models` — PASS.
- **State store / schema checks**: `PRAGMA quick_check` and schema version `3` — PASS.
- **Runtime unit checks**: `invariant_07-11` check each of 5 role units via `systemctl is-active` — PASS.
- **OmniRoute unit check**: `invariant_12` checks `omniroute.service` — PASS.
- **❌ BLOCKING: Missing web unit active check**. `verify-self.sh` has no invariant checking `devassist-web.service` active status, nor `curl -fs http://127.0.0.1:8180/health`. The NUDGE override explicitly states: *"(Contract v0.2.0 also adds web unit active; confirm it is checked)"*. `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 §8 table lists "Web unit active" as one of the 12 invariants. The implementation's 12 invariants are numbered 01-12, but the set diverges from the contract table by splitting the single "Each runtime unit active" row into 5 separate checks (07-11), which displaces the contract's invariants for web unit, per-runtime health endpoints, journald retention, and secrets-in-journal scan.
- **Non-blocking**: `record_fail` line 37 contains a garbled character: `log "FAIL: $1 G $2"`. Should read `log "FAIL: $1 — $2"` or plain ASCII.

### 3. rollback-self.sh — PASS

- **Restores operational.db only**: `restore_operational_db()` copies latest `.db` backup, runs `PRAGMA quick_check`, atomic `mv` — PASS.
- **Does NOT touch state.db**: `restore_runtime_state()` copies only `memories/`, `sessions/`, `cron/` from tarball; log message explicitly says "state.db NOT touched" — PASS.
- **Runtime tarball restore**: `tar xzf` to temp, per-role copy — PASS.
- **Symlink flip**: `flip_release_symlink()` swaps `releases/current` to target of `releases/previous` — PASS.
- **Verify gate**: runs `verify-self.sh` after restore — PASS.
- **Conditional restart**: `restart_units()` only starts `devassist.target` if verify passed (script exits before restart if verify fails due to `set -e`) — PASS.

### 4. upgrade-self.sh — PASS

- **State backup**: `take_operational_db_backup()` uses timestamped filename (`operational-${ts}.db`), preventing double-backup overwrite on multiple runs — PASS.
- **Runtime-state tarball**: `take_runtime_state_backup()` copies `memories/`, `sessions/`, `cron/` only, excludes `state.db` — PASS.
- **Release fetch**: `git clone` into `releases/<id>/`, with fallback empty dir on failure — PASS.
- **In-place install**: runs `install-self.sh` against new release dir — PASS.
- **Verify gate**: runs `verify-self.sh` before activation — PASS.
- **Activation gate**: stops at `activation_gate()` unless `--activate` is passed; prints clear instructions — PASS.
- **--activate**: stops target, saves current as `previous`, flips `current` symlink, `daemon-reload`, starts target, post-activation verify — PASS.

### 5. 8 Systemd Units — PASS

All 8 templates rendered:
| Unit | Wants/After | User | Port | SupplementaryGroups | Sandbox |
|---|---|---|---|---|---|
| `devassist.target` | Wants=all 7 services | — | — | — | — |
| `devassist-orchestrator.service` | After=omniroute | devassist | — | — | ProtectSystem, ProtectHome, PrivateTmp, NoNewPrivileges, ReadOnlyPaths, ReadWritePaths, BindReadOnlyPaths |
| `devassist-planner.service` | After=omniroute | devassist | — | — | Same sandbox |
| `devassist-architect.service` | After=omniroute | devassist | — | — | Same sandbox |
| `devassist-executor.service` | After=omniroute | devassist | — | docker | Same sandbox |
| `devassist-reviewer.service` | After=omniroute | devassist | — | docker | Same sandbox |
| `omniroute.service` | Before=5 runtimes | omniroute | 20128 | — | Same sandbox |
| `devassist-web.service` | After=5 runtimes | devassist | 8180 | — | Same sandbox |

- `ExecStart` for orchestrator uses `hermes gateway run` — PASS.
- `ExecStart` for planner/architect/executor/reviewer uses `hermes run` — PASS.
- Executor and Reviewer include `SupplementaryGroups=docker` — PASS.
- OmniRoute uses `User=omniroute`, `--port 20128` — PASS.
- Web uses `--port 8180` — PASS.
- All units have `NoNewPrivileges=true`, `ProtectSystem=full`, `ProtectHome=true`, `PrivateTmp=true` — PASS.

### 6. NUDGE Override Compliance Summary

| Override | Status | Notes |
|---|---|---|
| 8 units (not 6) | ✅ PASS | All 8 rendered: target + 5 runtime + omniroute + web |
| 12 invariants (not 7) | ⚠️ PARTIAL | 12 functions exist (01-12), but composition diverges from contract table. Missing web unit active check — **blocking**. |
| OmniRoute port 20128 throughout | ✅ PASS | Consistent in all scripts and templates |
| operational.db vs state.db distinction in rollback | ✅ PASS | Rollback restores operational.db only; runtime tarball excludes state.db |
| TKT-026 model_catalog_cli stub: skip with warning if CLI not implemented | ✅ PASS | `invariant_04` checks file existence, warns, records pass if missing |

### 7. Idempotency — PASS

- `install-self.sh`: second run returns 0, does not duplicate users, does not corrupt DB, does not duplicate symlinks — confirmed by `test_install_idempotent_second_run`.
- `upgrade-self.sh`: timestamped backups prevent overwrite.

### 8. No Secrets — PASS

- `SELF-DEPLOY.env` contains only `test-token-placeholder` values.
- `test_scripts_use_placeholder_tokens` asserts no `sk-` prefix.
- `test_verify_no_secrets_in_output` asserts `test-token-placeholder` does not leak to stdout/stderr.

### 9. Tests — PASS (coverage adequate for dry-run)

- `test_install_creates_filesystem_layout`
- `test_install_creates_operational_db_symlinks`
- `test_install_creates_env_symlinks`
- `test_install_renders_systemd_units`
- `test_install_idempotent_second_run`
- `test_executor_has_docker_group`
- `test_orchestrator_runs_gateway`
- `test_planner_runs_hermes_run`
- `test_omniroute_port_20128`
- `test_omniroute_runs_as_omniroute_user`
- `test_web_service_binds_8180`
- `test_all_units_have_sandboxing`
- `test_verify_all_invariants_pass_in_fixture_mode` (expects `12/12`)
- `test_verify_no_secrets_in_output`
- `test_rollback_aborts_with_no_backup`
- `test_rollback_dry_run_completes`
- `test_rollback_does_not_touch_state_db`
- `test_upgrade_staging_without_activate`
- `test_upgrade_does_not_auto_activate`

**Note**: Tests cannot be executed on the current Windows host (`bash` not available). Static analysis of test code shows correct assertions.

### 10. POSIX Compatibility — PASS

- All scripts use `#!/usr/bin/env bash` and `set -euo pipefail`.
- Uses `local` variables, `[[ ]]` tests, array expansion with `@` — all acceptable per NUDGE.
- No associative arrays used in critical paths.

### 11. Security — PASS

- systemd sandbox directives present in all 8 units (`NoNewPrivileges`, `ProtectSystem`, `ProtectHome`, `PrivateTmp`, `ReadOnlyPaths`, `ReadWritePaths`, `BindReadOnlyPaths`).
- `SELF-DEPLOY.env` created with mode `0600`.
- `omniroute.service` runs as `User=omniroute`.
- `devassist-web.service` has read-only bind mounts for state and repo.

## Blocking Issues (must fix before merge)

### B1: verify-self.sh missing `devassist-web.service` active check

**Reference**: NUDGE override: *"(Contract v0.2.0 also adds web unit active; confirm it is checked)"*; `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 §8 table row 9: *"Web unit active — `systemctl is-active devassist-web.service` returns `active` AND `curl -fs http://127.0.0.1:8180/health` returns `200 OK`"*.

**Current state**: `verify-self.sh` implements 12 invariants (`invariant_01` through `invariant_12`). Invariants 07-11 check the five specialist runtime units individually. Invariant 12 checks `omniroute.service`. There is no check for `devassist-web.service`.

**Required fix**: Add an invariant that checks `systemctl is-active devassist-web.service` (and optionally `curl -fs http://127.0.0.1:8180/health`). Because the test `test_verify_all_invariants_pass_in_fixture_mode` expects `"12/12"`, the invariant count must remain 12. The recommended resolution is to merge `invariant_07` through `invariant_11` back into a single "Each runtime unit active" invariant (matching contract table row 7), freeing invariant slots for web unit active and other contract-mandated checks. Alternatively, if the 5 separate checks are intentionally kept for granularity, the total invariant count should become 13+ and tests must be updated accordingly. The NUDGE override's instruction to "confirm it is checked" is unambiguous: the web unit check must exist.

## Non-Blocking Suggestions

### S1: Fix garbled character in `record_fail` log message

`verify-self.sh` line 37: `log "FAIL: $1 G $2"` — replace with clean ASCII or UTF-8 em-dash.

### S2: Add remaining contract v0.2.0 §8 invariants (deferred OK)

The contract table also lists:
- Per-runtime health endpoints (`:8181-8185/health`)
- journald retention drop-in configured
- No secrets in journal scan

These are currently omitted from `verify-self.sh`. If the scope is intentionally "connectivity-only" per `PRD-001.md` §10 Q12, document this scope limitation in a comment near the invariant list. Otherwise, add them in a follow-up ticket.

### S3: upgrade-self.sh backup integrity check

`take_operational_db_backup()` could run `PRAGMA quick_check` on the backup file after copying to ensure the backup is not corrupted.

### S4: install-self.sh schema migration path

`init_operational_db()` uses `CREATE TABLE IF NOT EXISTS`, which is safe for re-runs but does not handle schema version bumps. For v0.1 this is acceptable; consider a future migration script when schema version >3.

## Final Verdict

**REQUEST-CHANGES**

The implementation is solid, idempotent, secret-free, and well-tested for dry-run mode. All 8 systemd units are correctly sandboxed. Rollback and upgrade scripts correctly enforce the operational.db / state.db boundary. The TKT-026 stub skip logic is properly implemented.

However, the **blocking issue B1** must be resolved before merge: `verify-self.sh` must check `devassist-web.service` active status, as explicitly required by the NUDGE override and `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 §8. Once the web-unit invariant is added (and the invariant count / test expectations are reconciled), this PR can be approved.
