---
id: RV-SPEC-015
version: 0.1.0
status: complete
verdict: pass
review_target: PR-91
review_type: spec
reviewer_model: kimi-k2.6
created: 2026-05-06
---

# RV-SPEC-015: SPEC Review of PR #91 — Raise PR-Agent timeout from 18 to 30 minutes

## 1. PR Reviewed

- **PR**: #91
- **Title**: Raise PR-Agent timeout from 18 to 30 minutes
- **Files changed**: `.github/workflows/pr_agent.yml`
- **Change summary**: `timeout-minutes: 18` → `timeout-minutes: 30`, with updated inline comment documenting observed workloads and the rationale for the new cap.

## 2. Review Findings

### 2.1 Scope correctness — Severity: none
The diff touches exactly one parameter (`timeout-minutes`) and the single inline comment block that explains it. No other workflow keys, permissions, secrets, or job structure were modified. Scope is minimal and correct.

### 2.2 Timeout value reasonableness — Severity: none
The updated comment states observed workloads:
- typical runs: 3–9 min
- large docs PRs: ~12–15 min
- architecture pass PRs: ~18–25 min

A 30-minute hard cap provides a 5–12 minute headroom above the current known long tail (architecture pass PRs). This is a reasonable safety margin: it prevents legitimate, compute-heavy reviews from being killed prematurely, while still bounding runaway runs tightly enough to avoid indefinite resource consumption.

### 2.3 Comment accuracy and consistency — Severity: none
The comment cites PR-C (#88) and PR-E (#90) as concrete examples that hit the old 18-minute cap at ~18 min on large diffs. This is consistent with the repo’s practice of documenting observed workload data in workflow comments. The wording is clear and the arithmetic (30 min covering 18–25 min observed architecture passes) is internally consistent.

### 2.4 Adjacent workflow parameters — Severity: none
No other parameters need to change alongside the timeout:
- **Concurrency**: `cancel-in-progress: true` is already in place and mitigates the primary risk of multiple long-running jobs piling up on successive pushes.
- **Permissions**: remain minimal (`issues: write`, `pull-requests: write`).
- **Secrets / model config**: unchanged.
- **Auto-review flags**: unchanged.

## 3. Security Notes

- **Longer exposure window**: raising the timeout from 18 to 30 minutes extends the maximum lifetime of a compromised or runaway PR-Agent job by 12 minutes. This is a marginal increase against a hard cap that is still relatively short.
- **Mitigating controls**: `concurrency.cancel-in-progress: true` limits stale runs; minimal job permissions reduce blast radius; no new secrets or elevated privileges were introduced.
- **Verdict**: the security posture is unchanged; the risk increase is negligible and acceptable for the operational benefit.

## 4. Final Verdict

**pass**

The change is minimal, well-documented, and correctly scoped. The 30-minute timeout is calibrated against observed data, leaves an appropriate buffer for the long tail, and does not weaken security or workflow hygiene. No changes requested.
