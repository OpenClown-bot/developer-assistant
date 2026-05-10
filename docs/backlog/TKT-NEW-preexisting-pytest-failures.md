---
id: TKT-NEW-preexisting-pytest-failures
version: 0.1.0
status: backlog
source_tkt: TKT-034
created: 2026-05-10
---

# TKT-NEW: Pre-existing pytest failures on `origin/main` — environment-dependent triage

## Context

Across the TKT-034 / TKT-035 implementation cycles, three different SO / Executor / Reviewer environments observed **three different absolute pytest-failure counts** on identical `origin/main` HEADs:

| Environment | Measured baseline on `origin/main` | Provisioning notes |
|---|---|---|
| Devin SO snapshot box (2026-05-10, session 1 cold handoff) | `60 failed, 1139 passed, 2 skipped, 84 subtests passed` | No `/srv/devassist/` filesystem provisioned; partial fixture availability |
| Founder VPS (this snapshot box, post-`/srv/devassist/` setup) | `12 failed, 1187 passed, 2 skipped, 84 subtests passed` | `/srv/devassist/` filesystem provisioned per `SELF-DEPLOYMENT-CONTRACT.md` § 4 |
| TKT-035 Executor containerized env (opencode + VPS) | `62 failed, 1187 passed, 2 skipped` | `/srv/devassist/` not provisioned in containerized Executor session |
| TKT-035 Reviewer env (opencode + Founder PC, Windows-style filesystem) | `7 failed, 1127 passed, 112 skipped, 84 subtests passed` | Windows-style filesystem; large skip surface on Linux-only tests; smaller failure surface |
| TKT-034 iter-2 SO ratify (2026-05-10) | `12 failed, 1201 passed, 2 skipped, 84 subtests passed` | Same VPS box, post-iter-2 implementation |

The failures are concentrated in three test modules:

- `tests/test_self_deployment_scripts.py` (filesystem-fixture dependent; expects `/srv/devassist/` layout)
- `tests/test_health_endpoint.py` (environment-dependent HTTP fixture; expects local port binding)
- `tests/test_runtime_check.py` (environment-dependent fixture setup; expects template files in known location)
- `tests/test_runtime_layout_catalog_round_trip.py` (added later; fixture-dependent)

All four modules are **outside the active TKT-035 / TKT-034 / TKT-040 write zones**, so failures here have never been the responsibility of a TKT-cycle Executor to fix.

## Why this matters

- The **delta-based verification invariant** (`+N net-passing, 0 new failures, 0 new skips`) holds across all environments and is the load-bearing measurement for SO pass-2 ratify.
- The **absolute baseline count** is *not* reliable as a stop-the-world canary because it varies with environment provisioning.
- The current session-log § 0 self-check (`docs/session-log/2026-05-10-session-1.md` line 27) states "Failure count must equal 60 exactly; any other count means a regression" — this is **environment-specific**, true only on the Devin SO snapshot box without `/srv/devassist/`. On the actual VPS post-provisioning, the count is 12. This contributed to a NUDGE-level baseline mismatch on TKT-034 iter-2 (cited as F2 surfaceable in SESSION-STATE.md AUDIT-002 closure paragraph).

## Proposed scope

1. **Bucket the pre-existing failures by root cause** (fixture-availability vs assertion-staleness vs platform-portability) and triage each bucket:
   - Fixture-availability failures: introduce a conftest skip marker `pytest.mark.requires_devassist_layout` that skips when `/srv/devassist/` is absent. Same for HTTP-port fixtures.
   - Assertion-staleness failures: pin to a tag or remove if obsolete.
   - Platform-portability failures: gate behind `pytest.mark.linux_only` or similar.
2. **Replace the absolute-count self-check** in `docs/session-log/2026-05-10-session-1.md` § 0 with a delta-from-empty-clone protocol: `pytest --collect-only` count + a deterministic skip-fixture report instead of a flaky failure count.
3. **Document the environment-dependence** in `docs/orchestration/SESSION-STATE.md` Tooling Decisions section.
4. **De-flake or remove** any tests that fail purely due to mock/fixture drift unrelated to product code.

## Priority

Medium. Not blocking any active TKT cycle (delta-based verification works around the absolute-count variance), but causes recurring NUDGE-mismatch surfacing (Q-TKT-034-02, F-PA2-2/F-PA2-3 in TKT-035 closure) and operator-time-costly per-session sanity-check confusion. Should land before the next major-cycle TKT dispatch.

## References

- `docs/orchestration/SESSION-STATE.md` § Current Phase → AUDIT-002 closure (Q-TKT-034-02 carry-over)
- `docs/orchestration/SESSION-STATE.md` § Current Phase → TKT-035 closure (F-PA2-2 + F-PA2-3 surfaceable)
- `docs/session-log/2026-05-10-session-1.md` § 0 (baseline reconcile amendment, this hygiene pass)
- `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` § 10 iter-2 baseline correction subsection (existing reconcile attempt)
