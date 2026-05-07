---
id: RV-CODE-032
version: 0.1.0
ticket: TKT-032 v0.1.0
branch: rv/rv-code-032
reviewer_model: Kimi K2.6 via OmniRoute
date: 2026-05-08
---

# RV-CODE-032: Review of PR #119 (TKT-032 — VPS Deployment Smoke Test)

## Verdict: pass-with-notes

PR #119 is approved with minor notes. No blockers. The PR satisfies TKT-032 acceptance criteria, passes CI, passes local unittest (1083 tests OK), and correctly removes scope-creep artifacts (local OmniRoute unit, devassist-web.service). Two low-severity documentation gaps in the PR body and one minor template-scope deviation are noted below.

---

## Findings

| # | Severity | Category | Finding | Status |
|---|----------|----------|---------|--------|
| 1 | Low | Scope | `etc/runtime-templates/*/config.yaml.tmpl` (5 files) changed `{{omniroute_port}}` → `{{omniroute_base_url}}`. These files are **not** explicitly listed in TKT-032 §5 Allowed Files, but the change is a justified cascading template update driven by the in-scope `runtime_layout.py` / `install-self.sh` fix. No functional concern. | Noted |
| 2 | Low | Scope | `.gitignore` (new, `*.pyc`) is not in TKT-032 §5 Allowed Files. Trivial hygiene addition; no functional impact. | Noted |
| 3 | Low | PR Body | Credential injection confirmation omits `FIREWORKS_API_KEY`. TKT-032 §1.1 requires the env file to contain `TELEGRAM_BOT_TOKEN`, `PROJECT_GITHUB_PAT`, and `FIREWORKS_API_KEY`. The PR body only confirms the first two. The SELF-DEPLOY.env template does include `FIREWORKS_API_KEY=test-token-placeholder`, so the code path is present; this is a documentation gap only. | Noted |
| 4 | Low | PR Body | TKT-032 §1.2 recommends reporting credential presence as `"key <name> is set (length N)"`. The PR body reports presence but omits length. Minor hygiene. | Noted |
| 5 | Medium | Architecture | ADR-011 v0.1.0 states "OmniRoute as a sixth systemd-supervised service on the same VPS." PR #119 removes the local `omniroute.service` unit and user, treating OmniRoute as Founder-managed (remote or pre-installed). The env-var pattern (`OMNIROUTE_BASE_URL` with localhost default) preserves the ADR-011 default deployment shape while allowing a remote override. This is acceptable for v0.1 because TKT-032 §1.3 explicitly places OmniRoute configuration out of scope ("Founder performs"). However, ADR-011 should be reconciled in a follow-up revision to reflect the remote-local dual-mode posture. | Noted |
| 6 | Low | Architecture | `devassist-worker-runner` (inline bash+Python) and `devassist-orchestrator-runner` are pragmatic v0.1 worker patterns. Health endpoints bind to `127.0.0.1` only. The orchestrator runner invokes `hermes gateway run`; this subcommand's existence in the pinned Hermes version (`v2026.4.30`) has not been independently verified in this review, but the PR body confirms live VPS testing. Acceptable as a tested assumption. | Noted |
| 7 | Low | Tests | `test_self_deployment_scripts.py` updated expected invariant count from `12/12` to `11/11` (web service removed, omniroute split into two invariants). All 1083 unit tests pass locally; 37 skipped. | Resolved |

---

## Scope Compliance Assessment

**Within scope:**
- `scripts/install-self.sh`, `scripts/verify-self.sh`, `scripts/rollback-self.sh`, `scripts/upgrade-self.sh` — all modified per TKT-032 §5.
- `src/developer_assistant/cli/dev_assist_cli.py` — removal of `cmd_serve_web` (scope-creep cleanup, allowed).
- `src/developer_assistant/cli/runtime_layout_cli.py` — OmniRoute URL argument fix.
- `src/developer_assistant/observability/llm_client_instrumentation.py` — env-var pattern.
- `src/developer_assistant/observability/status_query.py` — removed omniroute from `_ROLE_ORDER`.
- `src/developer_assistant/runtime_layout.py` — env-var pattern for OmniRoute base URL.
- `tests/test_self_deployment_scripts.py` — updated expectations.
- `docs/tickets/TKT-032.md` — not modified in diff (execution log remains empty, acceptable for PR stage; Executor may append post-merge).

**Borderline / out-of-scope but justified:**
- `etc/runtime-templates/*/config.yaml.tmpl` — cascading template rename required by runtime_layout.py change.
- `.gitignore` — trivial hygiene.

**No unauthorized files modified.**

---

## Architecture Compliance Assessment

| Requirement | Assessment |
|---|---|
| OmniRoute routing (ADR-011) | The `OMNIROUTE_BASE_URL` env-var pattern with default `http://127.0.0.1:20128/v1` satisfies the ADR-011 localhost default. Remote override is confirmed by the PR body. The removal of the local `omniroute.service` unit is acceptable because OmniRoute is Founder-managed (TKT-032 §1.3), but ADR-011 text should be updated in a follow-up to reflect this dual-mode posture. |
| Model IDs (MODEL-CATALOG.md v0.2.0) | `deepseek-v4-pro` is a valid catalog identifier (Architect main + fallback). The PR body claims a revert from `deepseek-v3p2`; `main` already contained `deepseek-v4-pro`, so the effective diff is a no-op on model IDs. No concern. |
| Multi-Hermes runtime layout (MULTI-HERMES-CONTRACT.md) | Five runtimes preserved. `omniroute` removed from `_ROLE_ORDER` and systemd target. `devassist-web.service` removed. Health endpoints moved to per-runtime worker runners. Acceptable v0.1 simplification. |
| Observability (OBSERVABILITY-CONTRACT.md, ADR-010) | Per-runtime localhost-only health endpoints on ports 8181–8185 are present. `dev-assist-cli status` remains available. Journald drop-in and retention invariant retained. No paid services introduced. |
| Install gate (SELF-DEPLOYMENT-CONTRACT §3) | Install script does **not** invoke `systemctl start`. Unit tests enforce this. PR body confirms Founder approval was requested before start. Compliant. |
| Credential path (SELF-DEPLOYMENT-CONTRACT §4) | `/srv/devassist/secrets/SELF-DEPLOY.env` rendered with placeholder values, mode `0600`, owner `devassist:devassist`. Secrets sourced from Executor env vars, not committed. Compliant. |

---

## Security Assessment

| Control | Status | Evidence |
|---|---|---|
| No credential values in git | **Pass** | Diff shows only placeholder values (`test-token-placeholder`) in `SELF-DEPLOY.env` template. No raw tokens, PATs, or API keys in any changed file. |
| SELF-DEPLOY.env permissions | **Pass** | `install-self.sh` sets `chmod 0600` and `chown devassist:devassist` on the env file. |
| verify-self.sh secret handling | **Pass** | `verify-self.sh` sources `SELF-DEPLOY.env` selectively (whitelist of key names) and does not log values. `invariant_11_no_secrets_in_journal` scans journald for actual secret values and reports only leak presence, never the value. |
| Health endpoint binding | **Pass** | Worker runner embeds `http.server.HTTPServer(('127.0.0.1', ...))` — localhost only. |
| Public endpoints / webhook mode | **Pass** | No public IP binding. No webhook configuration added. Telegram gateway remains in polling mode (implied by `hermes gateway run`). |
| Systemd sandbox | **Pass** | Existing `ProtectSystem=full`, `ProtectHome=true`, `PrivateTmp=true`, `NoNewPrivileges=true` directives remain in unit templates. |

---

## PR Body vs TKT-032 §7 Checklist

| TKT-032 §7 Requirement | PR #119 Status |
|---|---|
| Link this ticket | ✅ Summary references TKT-032 |
| List all install script fixes with before/after rationale | ✅ Table present with 11 rows |
| State credentials injected from env, not committed | ✅ Confirmed |
| State runtimes NOT started autonomously — Founder approval requested | ✅ Confirmed |
| Include post-start verification output (sanitized) | ✅ Sanitized summary present |
| Include readiness decision for TKT-011 | ✅ "Ready for TKT-011 live orchestration trial" with two caveats |
| Include PR-Agent status and Reviewer artifact path/verdict | ✅ PR-Agent passed; Reviewer artifact noted as pending |
| State founder acknowledgement before merge required | ✅ "Founder acknowledgement before merge remains required" |
| Explicitly state "This PR unblocks TKT-011" | ✅ Present |

**Minor gaps:** `FIREWORKS_API_KEY` not explicitly listed in credential confirmation (see Finding #3); key lengths not reported (Finding #4).

---

## CI & Local Test Results

- **CI `validate-docs`**: Pass (6s).
- **CI `Run PR Agent on every pull request`**: Pass (2m4s).
- **Local `python scripts/validate_docs.py`**: Pass.
- **Local `python -m unittest discover -s tests -p "test_*.py" -v`**: 1083 tests, OK (skipped=37).

---

## Merge Recommendation

**Approve with notes.** The two low-severity documentation gaps (FIREWORKS_API_KEY omission in PR body, key-length reporting) do not block merge because the code paths are correct and the PR body already commits to "no credential values appear in any git commit." The medium architecture note (ADR-011 reconciliation) is deferred to a future ADR revision and does not block v0.1 deployment.

**Required before merge:** Founder acknowledgement per SELF-DEPLOYMENT-CONTRACT §3 and PR body statement.

**Post-merge follow-ups:**
1. Append execution log to `docs/tickets/TKT-032.md` §10.
2. Reconcile ADR-011 v0.1.0 text with remote-OmniRoute deployment posture.
3. Update PR body or ticket to confirm `FIREWORKS_API_KEY` injection if not already done in a subsequent commit.
