---
id: TKT-NEW-self-deployment-architect-pass
version: 0.1.0
status: backlog
source: Founder cross-repo audit directive 2026-05-05
created: 2026-05-05
---

# TKT-NEW-self-deployment-architect-pass: Architect-pass for `developer-assistant` self-deployment readiness

## Context

`developer-assistant` v0.1 is a Telegram-first AI engineering assistant that orchestrates docs-as-code projects on a founder-owned VPS via Hermes Agent. The architecture (`docs/architecture/ARCH-001.md` v0.2.0, `docs/architecture/HERMES-RUNTIME-CONTRACT.md`, `docs/architecture/HERMES-SKILL-ALLOWLIST.md`, `docs/architecture/OPERATIONAL-STATE-STORE.md`, ADR-001 / ADR-002 / ADR-003) describes:

- **What the assistant is for.** Hermes-based runtime that orchestrates per-project Business Planner / Architect / Executor / Reviewer sessions through Telegram intake.
- **Deployment readiness for *generated* projects.** `docs/architecture/GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` v0.1.0 specifies a one-command `make deploy` (or `./scripts/deploy.sh`) entry point that *generated* projects (the products `developer-assistant` builds for its users) must expose, including `DEPLOY.env.example`, idempotency, pre-flight validation, and founder-approval gates.

What the architecture does NOT specify, as of 2026-05-05:

- **Deployment readiness for `developer-assistant` ITSELF.** No Dockerfile, no `docker-compose.yml`, no `Procfile`, no `fly.toml`, no `systemd` unit file, no `Makefile` with a `deploy-self` target, no `scripts/install.sh` or equivalent. ARCH-001 v0.2.0 § 2 v0.1 Scope item 7 says "A documented one-command VPS deployment contract for generated projects, without automatic live deployment in v0.1" — explicitly scoping out automatic live deployment of the assistant. ARCH-001 § 3 Deferred Scope item "Fully autonomous production deployment to a founder VPS" reinforces this.
- **Hermes runtime install/operate contract.** `HERMES-RUNTIME-CONTRACT.md` defines the *boundary* between Hermes runtime and repository governance state, but does not specify *how* the Founder gets a fresh Hermes Agent installed on a fresh Ubuntu VPS, what env-var contract the assistant itself requires (Telegram bot token, GitHub PAT for project repos, OmniRoute API key, VPS SSH key access, SQLite or other operational state store path), how to bootstrap the project registry, how to upgrade Hermes Agent in place, how to roll back, or how to verify health.
- **Pre-deployment readiness gate.** TKT-017 added a *gated live-smoke readiness harness* (GitHub lane + Telegram lane) that fails closed without explicit gates and credentials. This is necessary but not sufficient: it tests connectivity and credential plumbing, not whether the Hermes runtime itself is installed, configured, healthy, and reachable from the Founder's intake channel.

## Why this matters now

The sister repo `OpenClown-bot/openclown-assistant` hit a "the project cannot be deployed" blocker during TKT-016 (boot/entrypoint integration layer fix). The blocker surfaced because the architecture had described *what* the boot path should do but had not described *how* the deployed bundle would be assembled, installed, and operated end-to-end. The fix consumed a full TKT cycle.

`developer-assistant` is at risk of the same class of blocker: TKT-001 through TKT-018 cover docs governance, runtime contract, allowlist, GitHub PR integration, Telegram transport binding, GitHub executor binding, smoke readiness harness, and a minimal trial vehicle — but no ticket and no architecture section defines how the assistant itself is deployed. The first time the Founder tries to actually run `developer-assistant` on the Ubuntu VPS, this gap will block the trial.

The Founder's directive on 2026-05-05 is explicit: "обязательно проверить, не будет ли там такой же проблемы, что невозможно проект задеплоить. если там это так же не учтено, как и у нас, то пропиши прогон архитекторов и тд тщательный."

## Proposed scope of the Architect pass

Architect must produce, in this order, before any TKT-011 first end-to-end Telegram-to-PR orchestration trial is dispatched:

1. **PRD revision (Business Planner first, then Architect).** PRD-001 must explicitly describe the operational target: Founder runs one command on a clean Ubuntu VPS, after which the assistant is reachable from Telegram, registered against the Founder's GitHub identity, and ready to accept project intake. The PRD revision should NOT specify implementation; that is Architect's job. PRD revision goes through Reviewer LLM RV-SPEC.
2. **Architecture section / new contract document.** Either a new ARCH-001 § "Self-deployment of `developer-assistant`" subsection or a new `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` file. Must specify:
   - **Bundle composition.** What artefacts ship with the assistant (Hermes Agent version pin, project repository clone, role prompts, validate_docs script, operational state store schema, env-var contract, PR-Agent action pin, etc.).
   - **Install entry point.** One command (e.g. `make install-self` or `./scripts/install-self.sh`) that, given a `SELF-DEPLOY.env` file, bootstraps Hermes Agent + the assistant + the operational state store + Telegram registration + GitHub PAT validation on a clean Ubuntu VPS.
   - **Env-var contract.** A `SELF-DEPLOY.env.example` placeholder file at the repo root, with categories: Hermes Agent runtime config, Telegram bot identity (`TELEGRAM_BOT_TOKEN` redaction-guarded), GitHub identity for project repos (`PROJECT_GITHUB_PAT` per TKT-014/TKT-016 path; the Founder's per-project PATs go through the project registry), OmniRoute API key (`OMNIROUTE_API_KEY` for PR-Agent + role LLMs), VPS-local paths (operational state store, log directory, secrets directory, repo workspace).
   - **Pre-flight validation.** Same idempotency / pre-flight rules as the GENERATED-PROJECT-DEPLOYMENT-CONTRACT, applied to the assistant itself: validate env vars, verify Telegram bot is reachable, verify GitHub PAT works against a sandbox repo, verify OmniRoute API key returns from a known model, verify SQLite path is writable, verify Hermes Agent version pin is installable.
   - **Health check.** One command (e.g. `make health-self`) that returns 0 if the deployed assistant can answer a Telegram message, write a project entry, dispatch one Executor session, and read it back.
   - **Rollback.** How to roll back to a known-good install (versioned Hermes Agent pin + versioned bundle).
   - **Founder approval gates.** Same explicit-approval pattern as the generated-project contract: install-self runs without approval but does NOT auto-start; start-self requires explicit approval; upgrade-self requires explicit approval and a backup of the operational state store.
3. **ADR.** A new ADR (e.g. `ADR-004-self-deployment-foundation.md`) recording the Founder + Architect decision on:
   - Container vs systemd vs bare-metal install (Docker Compose with a single `developer-assistant` service is the likely default given Hermes Agent's runtime, but Architect must evaluate and record).
   - Operational state store backend (SQLite default per existing decision; ADR formalises).
   - Secrets management (filesystem-only with strict mode 0600 vs. system keyring vs. external KMS — for v0.1 the filesystem default is most likely).
   - Logging destination (stderr + rotated log file vs. journald vs. centralised remote — for v0.1 stderr + local rotation is most likely).
4. **Tickets.** Architect breaks the new architecture section into at least three implementation tickets:
   - **TKT-NEW-self-deploy-bundle-and-script.** Implements the install entry point, env-var contract, pre-flight validation, and `SELF-DEPLOY.env.example`.
   - **TKT-NEW-self-deploy-health-check.** Implements the health check command + an integration test that runs end-to-end against a sandbox Hermes deploy.
   - **TKT-NEW-self-deploy-rollback-and-upgrade.** Implements rollback + upgrade with operational state store backup. Lower priority; can be deferred to v0.2 if Founder accepts no-rollback risk for v0.1.
5. **Reviewer LLM RV-SPEC.** Each architecture section / ADR / ticket goes through the standard Kimi K2.6 RV-SPEC pipeline before promotion to `ready`.

## Sequencing constraint

The Architect pass should run BEFORE any TKT-011 first end-to-end Telegram-to-PR orchestration trial. Reasoning: the trial requires `developer-assistant` to actually be running on a VPS, accepting Telegram messages, and dispatching role sessions. If the self-deployment contract is unspecified, the trial cannot start; if it is specified but the implementation tickets are not done, the trial cannot start. The current `docs/orchestration/SESSION-STATE.md` § Next Recommended Action says the next step is "re-run a fresh `TKT-011@0.2.0` Ticket Orchestrator session with `TKT-018@0.1.0` as the selected trial vehicle" — but TKT-011's `## 1. Scope` requires the trial to begin "from an authenticated Telegram founder interaction through the TKT-015 Hermes Telegram transport boundary" which implicitly requires a deployed Hermes runtime. The self-deployment contract must therefore precede TKT-011.

## Acceptance criteria for the eventual implementation tickets

- A clean Ubuntu 22.04 LTS VPS, given a `SELF-DEPLOY.env` file with all required values populated, can run `make install-self` (or equivalent) and reach a Telegram-reachable, GitHub-PAT-validated, OmniRoute-validated state in under 15 minutes without manual intervention beyond the env file.
- `make health-self` returns 0 only when all six health invariants pass (Telegram reachability, GitHub PAT validity, OmniRoute reachability, SQLite write, Hermes Agent process alive, project registry queryable).
- All secrets are read from `SELF-DEPLOY.env` (not committed, not logged, not echoed). The install script enforces 0600 mode on the env file before reading.
- The install script is idempotent: re-running on an already-installed VPS does not corrupt state or duplicate Hermes processes.
- Rollback (if implemented in v0.1) restores the operational state store to the pre-upgrade snapshot and downgrades the Hermes Agent pin to the previous version.

## Reviewer

Kimi K2.6 RV-SPEC + RV-CODE for each ticket; PR-Agent (DeepSeek V4 Pro) advisory; Founder ratification before merge.

## Notes

- This entry was filed by the Strategic Orchestrator on 2026-05-05 after a cross-repo audit directive from the Founder. The audit was triggered by the same class of blocker hit on `OpenClown-bot/openclown-assistant` TKT-016 boot/entrypoint integration layer fix.
- This is an Architect-scope deferral, NOT an SO clerical task. The SO must NOT begin writing PRD/architecture/ADR/ticket bodies — those go through Business Planner / Architect / Reviewer per `CONTRIBUTING.md` Roles.
- The next strategic step after this BACKLOG entry merges is to dispatch Business Planner for a PRD revision covering the operational target, then Architect for the architecture section, ADR, and tickets.
