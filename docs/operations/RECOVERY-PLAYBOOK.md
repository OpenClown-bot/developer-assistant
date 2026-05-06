---
id: RECOVERY-PLAYBOOK
version: 0.1.0
status: draft
---

# Recovery Playbook

## 1. Purpose And Audience

This is a **Founder-facing runbook** for diagnosing and recovering the `developer-assistant` system on its Ubuntu 22.04 LTS VPS. It pairs with `OBSERVABILITY-CONTRACT.md` (FR-OBS-10) and operationalizes the rollback surface defined in `SELF-DEPLOYMENT-CONTRACT.md` § 9.

The intended reader is the Founder (or any single human operator) with `ssh` access to the VPS, no required prior context beyond having read `PRD-001.md` § 12. Each section answers a specific operational question, gives the diagnostic command to run, interprets the result, and prescribes the action. No section requires architectural reading to execute.

This playbook is the **first stop** when something feels wrong. It is intentionally short — when in doubt, run `dev-assist-cli status` and follow the matching section below.

## 2. Quick Reference Card

| Question | Command | Section |
| --- | --- | --- |
| Is the system alive? | `dev-assist-cli status --format human` | § 3 |
| Did anything just go wrong? | `dev-assist-cli errors --since 1h` | § 4 |
| What is this work item doing? | `dev-assist-cli logs --work-item <id> --recursive` | § 5 |
| How much have I spent today? | `dev-assist-cli costs --since today` | § 6 |
| One runtime is wedged. | § 7 | |
| Multiple runtimes are wedged. | § 8 | |
| Daily digest never arrived. | § 9 | |
| OmniRoute is unreachable. | § 10 | |
| State store complaint. | § 11 | |
| I want to roll the entire system back. | `scripts/rollback-self.sh` (see `SELF-DEPLOYMENT-CONTRACT.md` § 9) | § 12 |
| I want to upgrade. | `scripts/upgrade-self.sh` (see `SELF-DEPLOYMENT-CONTRACT.md` § 6.3) | § 13 |

All commands run as the `devassist` user unless noted. Use `sudo -u devassist <command>` if you ssh in as a different user. `sudo` is required for `systemctl`, `journalctl -u <unit>` (in some distros), and access under `/var/log/dev-assist/` (mode 0750).

## 3. State Triage (Not Yet Running, Running But Quiet, Partially Failing, Fully Wedged)

Run `dev-assist-cli status --format human` first. Match the output to one of the four states below.

### 3.1 State: Not Yet Running (after install)

**Symptom**: All six rows show `state: down`. `systemctl is-active devassist.target` returns `inactive`.

**Cause**: `scripts/install-self.sh` finished, but the Founder has not yet approved `start` (the second of the three approval gates in `SELF-DEPLOYMENT-CONTRACT.md` § 6).

**Action**: Run `sudo systemctl start devassist.target`. Re-run `dev-assist-cli status --format human` after ~30 seconds to confirm all six runtimes report `state: running`.

If a runtime fails to come up: `sudo journalctl -u devassist-<role>.service -n 200 --no-pager` will show the bootstrap error. Common causes: missing env var (see `SELF-DEPLOYMENT-CONTRACT.md` § 10), schema version mismatch (see § 11 below), invalid `auth.json` (see `MULTI-HERMES-CONTRACT.md` § 4).

### 3.2 State: Running But Quiet

**Symptom**: All six rows show `state: running`. `queue.pending = 0`, `queue.in_progress = 0`. `today_token_totals` is empty or near-empty. The Founder hasn't seen any Telegram activity recently.

**Cause**: The system is healthy and idle. No work has been dispatched.

**Action**: This is a normal state. If the Founder expected work to be in flight (e.g., they sent a Telegram message and got no reply):

1. Confirm the Orchestrator received the message: `sudo journalctl -u devassist-orchestrator.service --since "5 minutes ago" --grep telegram_message_id`. The Telegram `update.message_id` will appear in the structured log if the message was received.
2. If the message did not appear: confirm Telegram is reachable: `dev-assist-cli status --format human` shows `telegram` row, OR run `scripts/verify-self.sh` to check the connectivity invariant.
3. If the Orchestrator received the message but did not act on it: the message may have been rejected by the allowlist. Check `DEVASSIST_FOUNDER_TELEGRAM_USER_ID` and `TELEGRAM_ALLOWED_USERS` against the sender's Telegram user ID.

### 3.3 State: Partially Failing (One Runtime Degraded Or Down)

**Symptom**: Five of six rows show `state: running`. One row shows `state: degraded` or `state: down`. The `last_error` field on the affected row is populated.

**Cause**: One runtime crashed, hit a heartbeat-age threshold, or returned a non-200 health response.

**Action**: Go to § 7 (One Runtime Wedged).

### 3.4 State: Fully Wedged (Multiple Runtimes Down Or Whole Target Down)

**Symptom**: Multiple `state: down` rows, OR `systemctl is-active devassist.target` returns `inactive`/`failed`.

**Cause**: A systemic failure — operational state store unreadable, OmniRoute crashed taking dependent runtimes with it, VPS resource exhaustion, or a recent upgrade activated a broken release.

**Action**: Go to § 8 (Multiple Runtimes Wedged).

## 4. Reading Recent Errors

```
dev-assist-cli errors --since 1h
```

Returns rows from the `errors` SQLite table (`OPERATIONAL-STATE-STORE.md` § 3.5). Each row carries a `kind` field that indicates what to do next:

| `kind` | Meaning | Recovery |
| --- | --- | --- |
| `unhandled_exception` | A runtime caught an exception it did not classify. | Read `message` and `stack`; if recurring, file a ticket per `OBSERVABILITY-CONTRACT.md` § 13. |
| `work_item_failed` | A specialist runtime exhausted its retries on a work item. | Read `context_json.work_item_id` and trace its lifecycle: `dev-assist-cli logs --work-item <id> --recursive`. The Orchestrator will re-queue or escalate per the work-queue lease semantics in `MULTI-HERMES-CONTRACT.md` § 6.2. |
| `llm_chain_exhausted` | All catalog fallbacks for a role failed. | Run `scripts/verify-self.sh` to confirm OmniRoute reachability; check `dev-assist-cli costs` for an unexpected spike that may indicate provider rate limits. If persistent, escalate per `ESCALATION-POLICY.md` § 4.6. |
| `escalation_expired` | An escalation surfaced to Telegram but was not approved within the 7-day window (`MULTI-HERMES-CONTRACT.md` § 6.3). | The escalation is closed; the originating work item is set to `failed`. Read the new escalation that was raised; decide whether to re-dispatch the work or accept the failure. |
| `schema_mismatch` | A runtime started against a `operational.db` whose schema version it does not understand. | Likely cause: a partial upgrade. Run `scripts/rollback-self.sh` (`SELF-DEPLOYMENT-CONTRACT.md` § 9). |
| `health_check_failed` | A runtime's localhost health endpoint returned non-200 or did not respond within the timeout. | The runtime is degraded; go to § 7. |

## 5. Tracing A Single Work Item

```
dev-assist-cli logs --work-item <id> --recursive
```

Streams every JSON-line log entry that carries `work_item_id=<id>` across all six units, in chronological order. The `--recursive` flag follows `parent_work_item_id` to surface sub-tasks (`MULTI-HERMES-CONTRACT.md` § 5.1).

Reading the timeline:

1. `work_item.dequeue` from the target runtime indicates pickup.
2. `llm.call.start` / `llm.call.complete` pairs mark each LLM call (token counts, latency, cost in the `complete` line).
3. `escalation.raised` indicates the runtime hit a deterministic rule or LLM-classifier threshold; pair with `escalation.resolved` after Telegram approval.
4. `work_item.complete` is the success terminus; `work_item.fail` is the failure terminus (with `error_class` set).

If the timeline ends in `work_item.dequeue` with no subsequent line, the runtime is currently working on the item. Compare `dequeue` ts to `now`; if older than 30 minutes (default lease), the lease will reclaim and the item will return to `pending`.

## 6. Cost Visibility

```
dev-assist-cli costs --since today
```

Returns aggregated `tokens_in`, `tokens_out`, `estimated_usd` by `(runtime_role, model_id)`. The `estimated_usd` column comes from the rate snapshot at call time, not from the catalog at view time, so it remains accurate even if the catalog rates change (`OPERATIONAL-STATE-STORE.md` § 3.6).

Reading the output:

- A spike in `tokens_in` for one runtime (e.g., Architect) usually reflects a long-context analysis — verify by inspecting the recent work items.
- A spike in `tokens_out` from one model usually reflects a long generation — typical for `deepseek-v4-pro` (1M context) under reasoning loads.
- A spike in `estimated_usd` is informational only per the Founder's 2026-05-06 directive (cost-optimization waived within the catalog). Per-runtime / per-day USD ceilings are out of scope for v0.1.

For per-day trends, use `dev-assist-cli costs --since 7d` which queries the `llm_calls_daily` aggregate (`OPERATIONAL-STATE-STORE.md` § 3.7).

## 7. Recovery: One Runtime Wedged

**Diagnose**:

1. Confirm which runtime: `dev-assist-cli status --format human` shows the affected `role` and `last_error`.
2. Check the systemd unit: `sudo systemctl status devassist-<role>.service`. The status line will indicate `active (running)`, `activating`, `failed`, or `inactive (dead)`.
3. Read the last 200 log lines: `sudo journalctl -u devassist-<role>.service -n 200 --no-pager`. Filter for level=error: `... --grep '"level":"error"'`.
4. Check the health endpoint directly: `curl -fsS http://127.0.0.1:818<n>/health` (n: orchestrator=1, planner=2, architect=3, executor=4, reviewer=5). A non-200 return confirms the runtime is degraded.

**Act**:

| Diagnosis | Action |
| --- | --- |
| Unit `failed` with a clear exception | Read `message` and `stack` in the journal. Fix the root cause (env var, file permission, network). Restart: `sudo systemctl restart devassist-<role>.service`. Re-run `dev-assist-cli status` to confirm. |
| Unit `active` but health endpoint not 200 | The runtime is wedged in user code, not crashed. Restart: `sudo systemctl restart devassist-<role>.service`. The lease-reclaim sweep (every 5 minutes) will return any in-flight work items to `pending` so they get retried. |
| Unit `failed` with `Restart=on-failure` exhausted (StartLimitBurst=5 hit) | Reset the failure counter and try again: `sudo systemctl reset-failed devassist-<role>.service && sudo systemctl restart devassist-<role>.service`. If it fails again immediately, the cause is structural — go to § 8. |
| Unit `active` but log shows `llm_chain_exhausted` | The catalog fallback chain for that role is exhausted. Confirm OmniRoute is up (§ 10). If OmniRoute is up but every catalog model is failing, escalate to the Founder for catalog change approval per `ESCALATION-POLICY.md` § 4.6. |

After every restart, confirm:

1. `dev-assist-cli status --format human` shows the runtime back at `state: running`.
2. The health endpoint returns 200.
3. The runtime is processing work: a fresh `work_item.dequeue` line appears in the journal within ~60 seconds (the default poll cadence).

## 8. Recovery: Multiple Runtimes Wedged

When multiple `state: down` rows appear, the cause is usually systemic, not per-runtime. Check the four most likely systemic causes in order:

### 8.1 Operational state store inaccessible

`scripts/verify-self.sh` includes a `operational.db` quick-check invariant. Run it: `scripts/verify-self.sh`. If `operational.db check failed` appears, the operational store is corrupt or unreadable.

Actions in order:
- Check ownership: `ls -l /srv/devassist/state/operational.db` should show `devassist:devassist 0640`.
- If permissions are wrong: `sudo chown devassist:devassist /srv/devassist/state/operational.db && sudo chmod 0640 /srv/devassist/state/operational.db`.
- Run quick-check: `sudo -u devassist sqlite3 /srv/devassist/state/operational.db 'PRAGMA quick_check;'`. If it returns anything other than `ok`, the database is corrupt — go to § 12 (full rollback).

### 8.2 OmniRoute is down, taking dependent runtimes with it

`devassist-omniroute.service` is ordered before all five Hermes runtimes (`SELF-DEPLOYMENT-CONTRACT.md` § 5.3). If OmniRoute is in `failed` state, runtimes will fail their LLM calls and may saturate their fallback chains.

Actions: go to § 10 (OmniRoute Unreachable).

### 8.3 VPS resource exhaustion

Memory, disk, or CPU exhaustion can cascade.

Actions:
- Memory: `free -m`. If `available` is below 200 MB, kill Docker terminal sandboxes or restart the host: `sudo systemctl stop devassist.target && sudo systemctl start devassist.target`. The 1.5-3 GB steady-state estimate in `MULTI-HERMES-CONTRACT.md` § 11 should be re-evaluated against actual measurements; append the measurement to that section.
- Disk: `df -h /srv /var`. If either is above 90% full: rotate session JSONL with `find /srv/devassist/runtimes/*/.hermes/sessions -name '*.jsonl' -mtime +90 -delete`; rotate `operational.db` backups by keeping only the last 7 (the install script does this automatically per `SELF-DEPLOYMENT-CONTRACT.md` § 9.7); rotate journald with `sudo journalctl --vacuum-size=500M`.
- CPU: `top` for steady-state high. Bursty CPU during LLM calls is normal. Persistent saturation indicates a runtime is in a tight loop — restart that runtime per § 7.

### 8.4 Recent upgrade activated a broken release

If the last `state: down` event coincides with an `upgrade-self.sh --activate` run, the new release is broken.

Actions: roll back. See `SELF-DEPLOYMENT-CONTRACT.md` § 9 and § 12 below.

## 9. Recovery: Daily Digest Never Arrived

The daily digest is produced at 08:00 VPS time by a Hermes cron entry on the Orchestrator (`OBSERVABILITY-CONTRACT.md` FR-OBS-05). If it doesn't arrive:

1. Check the Hermes cron: `sudo journalctl -u devassist-orchestrator.service --since "today 08:00" --grep daily_digest`. Look for `daily_digest.start` and `daily_digest.complete` events.
2. Check the on-disk file: `ls -l /var/log/dev-assist/daily-digest-$(date -u +%Y%m%d).md`. If present, the digest was generated; the Telegram delivery failed.
3. If the digest was generated but delivery failed: the file is queued for re-delivery on the next successful run. The Founder can read it directly from disk in the meantime.
4. If the digest was not generated: confirm the Orchestrator's Hermes cron is running by listing scheduled entries: `sudo -u devassist hermes cron list --home /srv/devassist/runtimes/orchestrator/.hermes`. If `daily_digest` is missing, re-run the install script (`scripts/install-self.sh`) which is idempotent.
5. If the cron is registered but didn't fire: check VPS timezone (`timedatectl`); the cron uses the VPS local time, not UTC. If the timezone changed, re-run install to refresh the cron entry.

## 10. Recovery: OmniRoute Unreachable

OmniRoute is the routing layer per `ADR-011` Option B. All specialist-runtime LLM calls go through it; without it, every Hermes runtime degrades to its OpenRouter backup which can also fail if the runtime's adapter does not have direct OpenRouter credentials.

**Diagnose**:

1. `sudo systemctl status devassist-omniroute.service`. Confirm `active (running)`.
2. `curl -fsS http://127.0.0.1:20128/health`. Should return `200 OK`.
3. Run the verify gate: `scripts/verify-self.sh`. If `OmniRoute does not support catalog model <id>` appears, the upstream OmniRoute regressed — this is a `paid:third_party_external_service_not_yet_supported` escalation per `ADR-011` Verification Gate.

**Act**:

| Diagnosis | Action |
| --- | --- |
| Unit `failed` | `sudo systemctl restart devassist-omniroute.service`. Watch its journal: `sudo journalctl -u devassist-omniroute.service -n 100 --no-pager`. |
| Unit `active` but `/health` does not return 200 | Restart: `sudo systemctl restart devassist-omniroute.service`. |
| Unit `active` and `/health` returns 200 but `verify-self.sh` says a catalog model is no longer supported | Hard-gate escalation. Do NOT silently fall back to direct-Fireworks (`ADR-011` Consequences). Notify the Founder via Telegram: include the failing model id, the OmniRoute version, the timestamp. The Founder approves the next step (catalog change, OmniRoute pin downgrade, or temporary direct-provider fallback under explicit deviation approval). |
| Unit `active` but slow / timing out | `dev-assist-cli logs --since 10m --role omniroute --grep '"level":"error"'`. Read the recent error pattern. If it's an upstream Fireworks rate-limit, the OpenRouter backup will engage automatically; verify by checking `dev-assist-cli costs --since 10m` for `routing_path: openrouter` rows. |

## 11. Recovery: State Store Schema Or Quick-Check Failure

If a runtime startup fails with `kind: schema_mismatch` in the `errors` table, the runtime is running against an operational.db whose schema version it does not understand. This is almost always the consequence of a partial upgrade.

Actions:
1. Read the schema version: `sqlite3 /srv/devassist/state/operational.db 'SELECT value FROM _schema_meta WHERE key = "schema_version";'`.
2. Read what the runtime expected: `sudo journalctl -u devassist-<role>.service --since "1h ago" --grep schema_mismatch`. The expected version is in the log line.
3. If expected > actual (runtime is newer): a migration didn't run. Re-running `scripts/install-self.sh` is safe (idempotent) and will apply pending migrations.
4. If expected < actual (runtime is older): a downgrade is needed. Run `scripts/rollback-self.sh` to restore the previous release (`SELF-DEPLOYMENT-CONTRACT.md` § 9) — this also restores the `operational.db` backup taken before the upgrade.

If `PRAGMA quick_check` returns anything other than `ok`, the database file is corrupt. Restoration via `scripts/rollback-self.sh` is the only safe recovery.

## 12. Full System Rollback

When § 8 systemic recovery fails, or when the schema is unreadable, run:

```
sudo /srv/devassist/repo/scripts/rollback-self.sh
```

This executes the rollback flow defined in `SELF-DEPLOYMENT-CONTRACT.md` § 9: stop `devassist.target` gracefully, restore the most recent `operational.db` backup, restore per-runtime `memories/`/`sessions/`/`cron/` from the matching tarball, flip the `releases/current` symlink back to `releases/previous`, run `verify-self.sh`, and restart `devassist.target` only if verify passes.

After rollback:

1. Confirm `dev-assist-cli status --format human` shows all six runtimes back at `state: running`.
2. Confirm the work queue is consistent: `sqlite3 /srv/devassist/state/operational.db 'SELECT status, COUNT(*) FROM work_items GROUP BY status;'`. Expect the counts that existed at the backup timestamp; any work that was in-flight during the failed window is now `pending` (lease-reclaim) and will be re-attempted.
3. Notify the Founder via Telegram (the Orchestrator surfaces a `system.recovered` event automatically; you may also send a manual note explaining the cause).

If verify fails after rollback, the script does NOT auto-retry. It stops with a non-zero exit and a list of failing invariants. Read the invariants and follow the pertinent section of this playbook (typically § 8 or § 11).

## 13. Upgrade Procedure

The upgrade procedure is in `SELF-DEPLOYMENT-CONTRACT.md` § 6.3. Summary:

1. `scripts/upgrade-self.sh` records the current release, takes a `operational.db` backup, fetches the new release, runs install in-place, runs verify, and **stops** at the activation gate.
2. The Founder reviews the staged release and the verify result. If acceptable, run `scripts/upgrade-self.sh --activate`.
3. The script flips `releases/current` to the new release, restarts `devassist.target`, and runs verify against the new release.
4. If post-activation verify fails, the staged release is rolled back automatically and the previous release resumes.

## 14. When To Escalate To The Founder Directly (Not Via Telegram Bot)

The Telegram bot is the standard escalation surface (`ESCALATION-POLICY.md` § 8). However, when the Telegram bot itself is unreachable or the Orchestrator is down, the Founder can be notified through the alternative channel they have pre-arranged (out-of-scope for this playbook). In that case the playbook's role is to give the Founder the diagnostic context to share:

- Output of `dev-assist-cli status --format human`.
- Last 200 lines of `journalctl -u devassist.target --no-pager`.
- Output of `scripts/verify-self.sh` (whether it passed or failed and which invariants).
- Output of `dev-assist-cli errors --since 1h`.
- Hash of the current `releases/current` symlink target.

Compose the four outputs into a single Telegram message (or attach as a `.txt` if size exceeds 4096 chars). This is the irreducible diagnostic packet for any escalation that bypasses the standard surface.

## 15. Cross-References

- `OBSERVABILITY-CONTRACT.md` v0.1.0 § 13 (RECOVERY-PLAYBOOK integration; defines FR-OBS-10)
- `SELF-DEPLOYMENT-CONTRACT.md` v0.2.0 § 6 (approval gates), § 8 (verify invariants), § 9 (rollback)
- `MULTI-HERMES-CONTRACT.md` v0.1.0 § 6 (work-queue and escalations schemas), § 9 (failure semantics)
- `OPERATIONAL-STATE-STORE.md` v0.3.0 § 3.5 (`errors`), § 3.6 (`llm_calls`), § 3.7 (`llm_calls_daily`)
- `ESCALATION-POLICY.md` § 4.6 (catalog and routing-layer change escalation)
- `MODEL-CATALOG.md` v0.2.0 § 4 (catalog and fallback chains), § 5 (routing layer)
- `ADR-010` (observability shape), `ADR-011` (routing layer Option B)
- `docs/tickets/TKT-027.md` (CLI implementation), `TKT-028.md` (structured logging), `TKT-029.md` (daily digest), `TKT-030.md` (this playbook execution discipline), `TKT-031.md` (state-store tables and health endpoints)
