---
id: GENERATED-PROJECT-DEPLOYMENT-CONTRACT
version: 0.1.0
status: draft
---

# Generated Project VPS Deployment Contract

## 1. Purpose

This document defines the v0.1 contract that every generated project must satisfy for one-command deployment readiness to a user-owned VPS. It specifies the deployment entry point, required environment variables and secret categories, founder approval requirements, logging, rollback, health checks, handoff notes, and how generated-project tickets should adapt this contract to their application stack.

This contract does not implement deployment code, deploy anything live, run VPS commands, or store credentials.

## 2. One-Command Deployment Entry Point

Every generated project must expose a single deployment entry point:

```
make deploy
```

Or, if the project does not use Make, an equivalent script:

```
./scripts/deploy.sh
```

The entry point must:

- Be documented in the project `README.md` under a "Deployment" section.
- Be idempotent: running it again should not break a working deployment.
- Accept all deployment parameters through environment variables, never through interactive prompts or hardcoded values.
- Perform a pre-deployment validation check (environment variables present, connectivity test) before making any changes to the VPS.
- Exit with a non-zero code on failure and a zero code on success.

The entry point is the only command a founder needs to run to go from a cloned repository to a running application on the VPS, after environment variables and VPS access are configured.

## 3. Required Environment Variables and Secret Categories

Generated projects must declare their required environment variables in a `DEPLOY.env.example` file at the repository root. This file must contain placeholder names and descriptions but must never contain secret values.

### Minimum Required Categories

| Category | Example Variable Names | Description |
| --- | --- | --- |
| VPS access | `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY_PATH` | Target VPS connection parameters |
| Application secrets | `APP_SECRET_KEY`, `APP_DATABASE_URL` | Application-level secret configuration |
| External service credentials | `LLM_API_KEY`, `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN` | Third-party service credentials needed by the application |
| Application configuration | `APP_PORT`, `APP_ENV`, `APP_LOG_LEVEL` | Non-secret runtime configuration |

### Rules

- Variable names must follow the pattern `<CATEGORY>_<NAME>` for clarity and grouping.
- `DEPLOY.env.example` must include a comment for each variable describing its purpose and whether it is required or optional.
- Secret values must never appear in `DEPLOY.env.example`, repository artifacts, logs, or CI output.
- The deployment entry point must validate that all required variables are set before proceeding and must print a clear error listing missing variables if validation fails.

### Founder Responsibility

In v0.1, the founder is responsible for:

- Creating and populating the actual `.env` or environment configuration on the VPS.
- Securing SSH key material and service credentials outside the repository.
- Rotating credentials when needed.

The deployment contract documents what is required but does not automate secret provisioning.

## 4. Founder Approval Requirement

In v0.1, live deployment to a VPS requires explicit founder approval before execution. This applies regardless of whether the deployment is triggered by the founder manually or by the Hermes runtime on behalf of the founder.

The approval flow:

1. The deployment entry point is documented and tested in a dry-run or staging mode where available.
2. Before any live deployment, the founder must explicitly acknowledge readiness through Telegram or an equivalent channel.
3. The founder's approval must be captured as a durable decision note in `docs/orchestration/` or the relevant ticket.
4. Only after approval is recorded may the deployment entry point be executed against the live VPS.

This requirement exists because v0.1 does not support fully autonomous production deployment (per PRD-001 Section 4, ARCH-001 Section 3, and HERMES-RUNTIME-CONTRACT Section 11).

## 5. Logs

Generated projects must produce structured deployment logs:

| Requirement | Detail |
| --- | --- |
| Log destination | Standard output and a deploy log file at `deploy.log` in the project root or a configured path |
| Log format | One line per event, ISO 8601 timestamp, severity level, message |
| Secret scrubbing | Logs must not contain secret values. If a command might leak secrets, redirect its output or wrap it to mask sensitive patterns. |
| Retention | `deploy.log` is overwritten on each deployment by default. The founder may configure log rotation. |
| Failure detail | On failure, logs must include the step that failed, the error message, and any remediation hints. |

## 6. Rollback Expectation

The deployment entry point must support rollback to the previously known-good state:

| Requirement | Detail |
| --- | --- |
| Rollback entry point | `make rollback` or `./scripts/rollback.sh` |
| Rollback scope | Revert the application to the state before the last successful deployment, not to an arbitrary historical version |
| Mechanism | The deployment entry point must create a backup marker (such as a git tag, container image tag, or snapshot identifier) before making changes. The rollback entry point uses this marker to restore. |
| Rollback safety | Rollback must not delete persistent data (databases, uploaded files) unless the founder explicitly requests it. |
| Rollback testing | Rollback must be documented and should be tested at least once per generated project before the project is considered deployment-ready. |
| Failure of rollback | If rollback fails, the entry point must log the failure, leave the system in the current state, and report the incident to the founder for manual intervention. |

## 7. Health Check Expectation

After deployment, the application must expose a health check:

| Requirement | Detail |
| --- | --- |
| Health check command | `make healthcheck` or `./scripts/healthcheck.sh` |
| Health check endpoint | An HTTP endpoint at `/health` (or a configured path) returning HTTP 200 when healthy |
| Check scope | Application is reachable, core dependencies (database, external services) are connected, configuration is valid |
| Deployment integration | The deployment entry point must run the health check after completing deployment steps and report the result |
| Failure handling | If the health check fails after deployment, the entry point must log the failure, attempt automatic rollback, and report to the founder |

## 8. Handoff Notes

Every generated project must include a handoff document at `docs/orchestration/HANDOFF.md` that covers:

| Section | Content |
| --- | --- |
| Project overview | What the project does, its current status, and its deployment target |
| Deployment instructions | Step-by-step guide from clone to running application, including environment variable setup |
| Architecture summary | High-level architecture, key dependencies, and integration points |
| Known risks | Security risks, operational risks, and limitations documented during development |
| Rollback procedure | How to roll back, where backups are stored, and what data is preserved |
| Monitoring and logs | Where to find logs, how to check health, and what to monitor in production |
| Contact and ownership | Who built the project, when it was last updated, and where to find the PRD and architecture docs |
| Follow-up work | Known technical debt, deferred features, and recommended next steps |

Handoff notes must be written so a human engineer unfamiliar with the project can understand, deploy, and maintain the application without access to agent chat history.

## 9. Adapting Deployment Details to Application Stack

This contract defines a generic deployment pattern. Generated-project tickets must adapt it to their specific application stack. The adaptation process:

1. **Identify the deployment target.** Determine whether the application runs as a Docker container, a systemd service, a Node.js process, a Python application, or another runtime. The deployment entry point and rollback mechanism must match the chosen runtime.

2. **Define stack-specific environment variables.** Extend the `DEPLOY.env.example` with variables specific to the application's framework, database, and external services. Follow the naming convention in Section 3.

3. **Choose a deployment mechanism.** The `make deploy` entry point may internally use Docker Compose, Ansible, SSH-based scripts, or another deployment tool appropriate to the stack. The mechanism must still satisfy the contract requirements: idempotent, environment-variable-driven, pre-validation, structured logging, backup marker, health check, and rollback support.

4. **Adapt health checks.** The health check must verify the dependencies and behaviors specific to the application stack. For example, a web application must verify HTTP response; a Telegram bot must verify Telegram API connectivity.

5. **Document stack-specific rollback.** Rollback procedures vary by deployment mechanism. Container-based deployments may roll back by switching image tags. Systemd deployments may roll back by switching symlink targets and restarting. The generated-project ticket must document the chosen approach.

6. **Record deviations.** If a generated project cannot satisfy a contract requirement (for example, a static site that has no persistent state to protect during rollback), the ticket must document the deviation and the rationale. Undocumented deviations are not allowed.

Each generated-project ticket that involves deployment must reference this contract and include a "Deployment Adaptation" section describing how the above six steps apply.

## 10. Relationship to Existing Architecture

This contract is consistent with and references the following existing artifacts:

- **PRD-001 Section 6**: The system must produce a one-command deployment path for a user-owned VPS without requiring v0.1 to perform the final live deployment automatically.
- **PRD-001 Section 8**: Repository artifacts may document which secret categories are needed but must not include secret values. Final deployment should require a separate founder action.
- **ARCH-001 Section 13**: Generated projects must include a documented one-command VPS deployment entry point with final live execution requiring founder approval.
- **ARCH-001 Section 10**: Security model requires approval for deployment actions and credentials; secrets must not be committed.
- **HERMES-RUNTIME-CONTRACT Section 11**: Deployment actions require explicit founder approval. Secrets must never appear in repository artifacts or logs. Rollback procedure is defined.
- **ADR-001**: Hermes Agent is the runtime foundation; deployment tooling should be compatible with Hermes VPS deployment patterns.
- **ADR-002**: Repository artifacts are authoritative governance state; deployment contract and handoff notes are repository artifacts. Operational VPS state is outside repository scope.
- **ADR-003**: Hermes skills/plugins used for deployment must be allowlisted, pinned, source-reviewed, and reversible per supply-chain controls.

## 11. Known Limitations

- This contract defines expectations, not deployment code. Implementation is the responsibility of generated-project tickets.
- The contract assumes a single VPS target. Multi-host, container-orchestration, or cloud-provider deployments are out of v0.1 scope.
- The `make deploy` convention may not fit every stack; the contract allows equivalent scripts.
- Dry-run or staging deployment is recommended but not required by this contract; generated-project tickets may add that requirement.
- Health check depth is intentionally minimal for v0.1. Richer observability is a later concern.
- The contract does not specify a particular deployment tool (Docker, Ansible, etc.) to preserve stack flexibility.
