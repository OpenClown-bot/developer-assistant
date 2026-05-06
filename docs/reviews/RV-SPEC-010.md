---
id: RV-SPEC-010
version: 0.1.0
status: complete
verdict: pass_with_changes
review_target: PR-86
review_type: spec
reviewer_model: kimi-k2.6
created: 2026-05-06
---

# RV-SPEC-010: SPEC Review of PR #86 — ARCH-001 v0.3.0 (PR-A/4): research + top-level decisions

## 1. PR Reviewed

- **PR**: [#86](https://github.com/OpenClown-bot/developer-assistant/pull/86) (`devin/1778037997-arch-001-pr-a-research-and-decisions`)
- **Title**: ARCH-001 v0.3.0 (PR-A/4): research + top-level decisions
- **Author**: `OpenClown-bot`
- **Head SHA**: `a3ac94c6a29f44618d6df66ca1751cd06ac2d84b`
- **Base SHA**: `d09dba2565677d1b21be1c11139a68a00a46a878` (`main`)
- **Mergeable state**: `clean`
- **Files changed**:
  - `docs/architecture/ARCH-001.md` — revised from v0.2.0 → v0.3.0, +241 / −89
  - `docs/architecture/RESEARCH-001-hermes-and-openclaw-ecosystems.md` — added, +386 / −0
  - `docs/architecture/adr/ADR-004-deployment-mechanism.md` — added, +138 / −0
  - `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` — added, +149 / −0
- **Net**: 914 insertions, 89 deletions, 4 files

## 2. Spec Reviewed

| Document | Version in PR | Baseline | Status |
|---|---|---|---|
| `docs/architecture/ARCH-001.md` | v0.3.0 | v0.2.0 (approved) | draft |
| `docs/architecture/RESEARCH-001-hermes-and-openclaw-ecosystems.md` | v0.1.0 | new | draft |
| `docs/architecture/adr/ADR-004-deployment-mechanism.md` | v0.1.0 | new | draft |
| `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` | v0.1.0 | new | draft |

## 3. Architecture / ADR / PRD References

Documents read in full for this review:

- `docs/prompts/reviewer.md` v0.3.0 (role prompt)
- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `docs/orchestration/SESSION-STATE.md`
- `docs/prd/PRD-001.md` v0.2.1
- `docs/questions/QUESTIONS-002-autonomy-team-composition.md`
- `docs/architecture/ARCH-001.md` v0.2.0 (baseline)
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` v0.2.0
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` v0.1.0
- `docs/architecture/OPERATIONAL-STATE-STORE.md` v0.2.0
- `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` v0.1.0
- `docs/architecture/adr/ADR-001-platform-foundation.md` v0.2.0
- `docs/architecture/adr/ADR-002-repository-state.md` v0.2.0
- `docs/architecture/adr/ADR-003-plugin-supply-chain.md` v0.2.0
- `docs/backlog/TKT-NEW-self-deployment-architect-pass.md`
- `docs/reviews/RV-SPEC-009.md` v0.1.0 (format reference)

## 4. Review Findings

### Critical

#### CRIT-1: `state.db` filename collision between Hermes native sessions DB and shared operational store

**Location**: `ADR-005 § Decision`, `ARCH-001 § 11.1` / `§ 11.2`, `RESEARCH-001 § 3.5`.

**Finding**: The design literally places two different SQLite databases at the same filesystem path inside every `HERMES_HOME`:

- Hermes native sessions database: `~/.hermes/state.db` (SQLite with FTS5, per `RESEARCH-001 § 3.5`).
- Shared operational store: `/srv/devassist/state/state.db` symlinked into each runtime's `HERMES_HOME` (per `ADR-005 § Decision`).

Both cannot be named `state.db` and live in the same directory. One will overwrite the other, destroying either session history or operational IPC data.

**Impact**: This invalidates the IPC model (work queue, escalations) and corrupts per-runtime memory/session isolation as documented.

**Required fix**: Rename the shared operational database (e.g., `operational.db`, `devassist.db`, or place it in a subdirectory such as `HERMES_HOME/operational/state.db`). Update all references in `ADR-005`, `ARCH-001 § 11.1`, and any contract documents (`MULTI-HERMES-CONTRACT.md`, `SELF-DEPLOYMENT-CONTRACT.md`) so that the symlink target and the Hermes native DB do not collide.

### Major

#### MAJ-1: PRD §12 "15-minute" deployment time constraint is not addressed in ADR-004 or ARCH-001

**Location**: `PRD-001 § 12` / Q11; `ADR-004` (all sections); `ARCH-001 § 14`.

**Finding**: PRD-001 mandates that "after explicit start approval the assistant responds to a Telegram message within 15 minutes of starting the install." Neither `ADR-004` nor `ARCH-001 § 14` analyzes whether the chosen systemd + bash bootstrap mechanism can satisfy this bound. There is no timing estimate for Hermes download, dependency installation, five `HERMES_HOME` initializations, or preflight checks.

**Impact**: Without a feasibility check or a timing budget, the chosen mechanism risks failing a hard product requirement.

**Required fix**: Add a timing analysis to `ADR-004` (or `SELF-DEPLOYMENT-CONTRACT.md`) that breaks down the 15-minute budget into install steps, lists worst-case assumptions (network speed, VPS size), and flags any step that threatens the bound.

#### MAJ-2: "Fully autonomous production deployment" still listed as deferred scope, creating ambiguity with PRD §12

**Location**: `ARCH-001 § 3` (Deferred Scope, bullet 3); `PRD-001 § 12`.

**Finding**: ARCH-001 v0.3.0 §3 still lists "Fully autonomous production deployment to a Founder VPS" as deferred. However, PRD-001 v0.2.1 §12 now makes *self-deployment with explicit approval gates* a v0.1 prerequisite. The deferred bullet was carried over from v0.2.0 without revision, creating the impression that the architecture does not fully accept the PRD mandate.

**Required fix**: Either remove the bullet (because the PRD-approved scope is self-deployment with gates, not fully autonomous deployment), or rewrite it to clarify that *ungated* fully autonomous deployment remains deferred while *gated* self-deployment is now in-scope.

#### MAJ-3: "Physical" memory isolation claim overstates separation given shared Linux uid

**Location**: `ADR-005 § Decision` / `Consequences`; `ARCH-001 § 11.1`.

**Finding**: The documents repeatedly claim per-runtime memory isolation is "physical" because each runtime has a separate `HERMES_HOME`. However, `ADR-005 § Consequences` states that all five runtimes share a single Linux uid (`devassist`). With a shared uid, filesystem-level separation depends entirely on systemd `ProtectHome=`, `ReadWritePaths=`, and `PrivateTmp=`. If a systemd unit is misconfigured, bypassed, or if a runtime escapes its sandbox, it can read or write another runtime's `MEMORY.md`, `USER.md`, and sessions database. This is process-level sandboxing, not physical isolation.

**Required fix**: Downgrade the claim from "physical" to "filesystem-level separation enforced by distinct `HERMES_HOME` paths plus systemd sandbox directives." Add a note that a hostile intra-runtime actor is out of the v0.1 threat model, but that the isolation is conditional on correct systemd unit configuration.

#### MAJ-4: RESEARCH-001 lacks timing and resource-footprint data needed for feasibility claims

**Location**: `RESEARCH-001` (all sections); `ADR-005 § Considered Options / Option A`.

**Finding**: `RESEARCH-001` provides no measurements or citations for:
- Hermes Agent installation time on a clean Ubuntu 22.04 VPS (relevant to PRD §12 15-minute bound).
- Steady-state memory footprint of one Hermes process, let alone five (ADR-005 cites "~1.5–3 GB under steady state per `MULTI-HERMES-CONTRACT.md` § 11", but that contract is not in this PR and the figure is unsupported by the research record).

**Required fix**: Add a research note documenting either observed/cited installation times and memory usage, or explicitly flag these as unverified assumptions with a validation task in TKT-020 or TKT-021.

### Minor

#### MIN-1: ADR-004 does not warn about `docker` group privilege escalation for Executor/Reviewer runtimes

**Location**: `ADR-004 § Decision` / `Consequences`.

**Finding**: ADR-004 assigns `SupplementaryGroups=docker` to the Executor and Reviewer systemd units so they can use the Docker terminal backend. Membership in the `docker` group is effectively root-equivalent on most Linux systems. The ADR lists this as a neutral implementation detail without a security warning or mitigation (e.g., rootless Docker, dedicated Docker user, or AppArmor/SELinux profile).

**Suggested fix**: Add a security note in `ADR-004 § Consequences` warning that `docker` group membership is a high-privilege boundary, and list mitigations or acceptance rationale.

#### MIN-2: Symlink path for shared operational store is not specified in ADR-005

**Location**: `ADR-005 § Decision`.

**Finding**: ADR-005 says the shared operational store is "symlinked into each runtime's `HERMES_HOME`" but does not state the symlink name or subdirectory. Combined with CRIT-1, this ambiguity makes implementation impossible without guessing.

**Suggested fix**: Specify the exact symlink path (e.g., `ln -s /srv/devassist/state/operational.db /srv/devassist/runtimes/<role>/.hermes/operational.db`) after resolving CRIT-1.

#### MIN-3: Minor encoding artifacts in markdown

**Location**: `ARCH-001 v0.3.0`, `ADR-004`, `ADR-005`, `RESEARCH-001`.

**Finding**: Several `§` symbols are rendered as `┬º` (UTF-8 BOM/encoding artifact from model output). This does not affect correctness but degrades readability.

**Suggested fix**: Run a cleanup pass replacing `┬º` with `§` before merge.

### Observations

- **ADR option counts**: ADR-004 evaluates 5 options (A–E), ADR-005 evaluates 6 options (A–F). Both exceed the ≥3 minimum.
- **Cross-reference health**: ARCH-001 v0.3.0 correctly references ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, and ADR-009 in the relevant sections. ADR-004 and ADR-005 both include Cross-References sections.
- **Research bibliography**: The bibliography records URLs but does not include retrieval dates or archived snapshots for web sources (e.g., OpenClaw docs, A2A protocol). This is acceptable for v0.1 but may be hardened in a future refresh.
- **Write zone compliance**: All 4 changed files are inside the Architect write zone (`docs/architecture/`, `docs/architecture/adr/`). No write-zone violation.

## 5. Security Notes

1. **Docker-group privilege escalation** (Executor/Reviewer): see MIN-1. The current design accepts this risk for sandbox functionality; a future hardening pass should evaluate rootless Docker or a dedicated low-privilege container runtime.
2. **Shared operational store as lateral-movement surface**: Because all five runtimes share one SQLite operational store, a compromise in one runtime can alter the `work_items` or `escalations` tables affecting other runtimes. The design mitigates this by keeping per-runtime memory separate, but the shared database is a single point of integrity failure. Backup and rollback scripts should treat `state.db` (or its renamed equivalent) as a critical asset.
3. **Single shared Linux uid (`devassist`)**: If systemd sandbox directives are ever disabled or misconfigured during debugging, all runtime directories become mutually readable/writable. Operational runbooks should warn against running Hermes as a non-sandboxed process in production.

## 6. Final Verdict

**`pass_with_changes`**

The research record is thorough and well-cited, the ADRs cover ≥3 options each with clear trade-off matrices, and the architecture correctly absorbs the PRD v0.2.1 mandates (self-deployment, high autonomy, multi-Hermes team, upstream composability). However, one **critical** design contradiction (`state.db` collision) and two **major** gaps (15-minute timing constraint unaddressed; deferred-scope ambiguity) must be resolved before this PR can be merged. The required changes are textual and analytical, not structural rewrites.

**Required before merge:**
1. Fix CRIT-1: rename the shared operational database and update all path references.
2. Fix MAJ-1: add timing feasibility analysis to `ADR-004` or the self-deployment contract.
3. Fix MAJ-2: revise `ARCH-001 § 3` deferred scope bullet to reflect the gated self-deployment mandate.
4. Fix MAJ-3: soften "physical isolation" language to "filesystem-level separation with systemd sandboxing".

**Recommended before merge:**
- Fix MIN-1 (Docker group security warning).
- Fix MIN-2 (specify exact symlink path).
- Fix MIN-3 (encoding cleanup).
