---
id: ARCH-001
version: 0.2.0
status: approved
---

# ARCH-001: Telegram-First Hermes-Centered v0.1 Architecture

## 1. Context

`developer-assistant` is a docs-as-code project for building an AI developer assistant that can orchestrate software delivery through separated roles, durable repository artifacts, pull requests, CI, and review gates.

The previous draft architecture recommended a custom thin docs-as-code orchestrator and deferred Telegram, Hermes Agent, and OpenClaw. That recommendation is not approved. The current user decisions require a Telegram-first v0.1 and prefer building around Hermes Agent instead of building a custom runtime from scratch.

This revision makes Hermes Agent the v0.1 runtime foundation unless implementation discovery finds a hard blocker. No hard blocker is currently identified. The architecture preserves repository docs-as-code governance as the source of truth for product, architecture, tickets, reviews, and durable decisions.

## 2. v0.1 Scope

v0.1 must prove an end-to-end founder-driven project orchestration loop through Telegram:

1. Telegram founder intake through Hermes Agent.
2. Hermes-based orchestration of role-separated Business Planner, Architect, Executor, and Reviewer sessions.
3. Repository docs-as-code governance for PRD, architecture, ADRs, tickets, questions, reviews, CI results, and handoff state.
4. GitHub repository creation and PR-based delivery under a least-privilege assistant account or token.
5. CI validation, Reviewer LLM artifacts, and explicit founder approval gates for sensitive actions and final merge/deployment decisions.
6. Progress reports in Russian after ticket completion and during long-running work.
7. A documented one-command VPS deployment contract for generated projects, without automatic live deployment in v0.1.

## 3. Deferred Scope

The following remain out of v0.1 unless later approved by the user:

- Public SaaS or hostile multi-tenant operation.
- OpenClaw as the primary runtime or default gateway.
- Rich web dashboard beyond optional read-only status.
- Fully autonomous production deployment to a founder VPS.
- Unreviewed marketplace plugin or skill installation.
- Autonomous merge policy that bypasses user acknowledgement.

## 4. Architecture Principles

- Telegram is the primary founder interface for v0.1.
- Hermes Agent is the primary runtime foundation for Telegram gateway, orchestration loop, scheduled updates, and specialist-agent delegation.
- Repository artifacts remain the governance source of truth.
- Hermes memory, Telegram chat history, and operational databases are operational state, not authoritative product or engineering decisions.
- Role separation is preserved through prompts, tickets, write zones, PRs, CI, and review gates.
- GitHub PRs are the unit of implementation delivery.
- Secrets never live in repository artifacts.
- Hermes skills/plugins are accepted only through an allowlist, pinning, source review, scoped credentials, sandboxing, and rollback procedures.
- OpenClaw may be reconsidered later as a gateway/control UI layer, not as the immediate default.

## 5. System Components

| Component | v0.1 Responsibility | State or Artifacts |
| --- | --- | --- |
| Hermes Agent gateway | Receive Telegram messages, authenticate allowed founder chats, send questions and progress reports | Operational Telegram session state outside repository |
| Hermes Orchestrator runtime | Route work to role agents, schedule updates, call GitHub tools, resume interrupted runs | Operational run metadata outside repository plus durable summaries in repository |
| Role prompts | Define Orchestrator, Business Planner, Architect, Executor, and Reviewer behavior, required reading, write zones, stop conditions, and outputs | `docs/prompts/` |
| Repository state store | Authoritative PRD, architecture, ADRs, tickets, questions, review artifacts, handoff notes, and current durable project state | `docs/` artifacts |
| Operational state store | Telegram chat bindings, project registry, scheduled progress timers, Hermes run IDs, agent-run metadata, and idempotency keys | Local/VPS database or Hermes-supported persistence outside repository |
| GitHub integration | Create repositories, branches, PRs, observe checks, collect CI status, and link review artifacts | GitHub plus repository artifacts |
| CI and validation | Validate docs, tests, lint/typecheck, and security/static checks as configured | GitHub Actions and local commands |
| Security policy | Constrain plugins, tools, credentials, sandboxes, approvals, and rollback | ADRs, architecture docs, runtime config outside repository |

## 6. Platform Foundation

Hermes Agent is the v0.1 foundation. The product should use Hermes for:

- Telegram gateway and founder pairing/allowlisting.
- Long-running server/VPS operation.
- Scheduled progress reports.
- Delegation to coding/review agents where supported.
- GitHub-related automation through reviewed built-in or pinned skills.
- Sandboxed execution for risky commands and generated-code work.

`developer-assistant` still owns the governance model. The repository is the source of truth for decisions and engineering state. Hermes is the runtime that executes and routes work, not the canonical record of product scope, architecture, or ticket status.

The implementation should be a Hermes-first hybrid rather than a pure Hermes application: use Hermes capabilities where they reduce custom runtime work, and add only the minimal project-specific glue needed to enforce repository governance, prompts, tickets, CI, review gates, Telegram decision capture, and project registry behavior.

## 7. Telegram Founder Interaction

Telegram interaction is required in v0.1 and should work as a hybrid command/free-form chat model:

- `/new_project` starts guided intake and creates or selects a project workspace after required approvals.
- `/status` returns current phase, active ticket, active PR, blockers, and pending decisions.
- `/decisions` lists open decisions requiring founder input.
- `/pause` and `/resume` control autonomous work for the current project.
- Free-form founder messages are routed to the Orchestrator for classification as intake, answer, clarification, approval, rejection, or general question.

Question routing:

- Specialist agents must emit founder questions with context, decision options, recommended default, impact, and urgency.
- Hermes Orchestrator sends the question in Russian through Telegram.
- Founder answers are normalized into an English durable decision note when relevant.
- Product decisions are written to PRD or `docs/questions/`; architecture decisions are written to architecture docs or ADRs; implementation clarifications are written to the relevant ticket or review artifact.

Progress reports:

- Send a report after each ticket changes phase or a PR/review gate completes.
- Send time-based updates every 30 to 60 minutes during long-running work.
- Reports should include completed work, current action, blocker state, decisions needed, and notable risks.
- Reports should avoid deep technical detail unless requested or required for a decision.

Decision capture:

- Telegram chat history is not enough for durable decisions.
- Decisions that affect product scope, architecture, security, credentials, merge policy, deployment, external services, or cost must be summarized into repository artifacts.
- Operational acknowledgements may remain in operational state when they do not affect durable engineering behavior.

## 8. State Model

Repository artifacts remain authoritative for durable engineering state:

- `docs/prd/` for product requirements.
- `docs/architecture/` and `docs/architecture/adr/` for system decisions.
- `docs/tickets/` for implementation contracts and status.
- `docs/questions/` for unresolved or resolved founder questions.
- `docs/reviews/` for Reviewer LLM artifacts.
- `docs/orchestration/SESSION-STATE.md` for human-readable phase, blockers, active tickets, active PRs, and next action.

External operational state is required in v0.1 because Telegram-first orchestration needs information that should not be stored only in repository files:

- Telegram user/chat allowlist and project chat binding.
- Project registry mapping Telegram conversations to GitHub repositories and local workspaces.
- Scheduled progress update timers and last-report timestamps.
- Hermes agent-run IDs, retry/idempotency keys, and in-flight task metadata.
- Non-secret credential metadata such as which secret names must exist in the runtime environment.

External state must not store canonical product or architecture decisions without writing a durable repository summary. Secrets must live in environment variables, Hermes-supported secret mechanisms, GitHub Actions secrets, VPS secret storage, or a later approved secret manager, never in repository artifacts.

## 9. GitHub and Review Flow

The Orchestrator must use GitHub through least-privilege credentials and repository-scoped permissions where practical.

Implementation flow:

1. User approves architecture and a ticket sequence.
2. A ticket is moved to `ready` only when no unresolved blocker remains for that ticket.
3. Executor works on one ticket in a branch.
4. Executor opens a PR linked to the ticket.
5. CI runs docs validation and relevant project checks.
6. `pr-agent` or equivalent automated review may provide supplemental feedback.
7. Reviewer LLM writes an artifact under `docs/reviews/` using the allowed verdicts.
8. Founder acknowledgement is required before merge in v0.1.

Autonomous merges are not the default for v0.1. They may be reconsidered after at least one successful Telegram-to-PR-to-review-to-merge cycle.

## 10. Security Model

v0.1 assumes one trusted founder/operator and assistant-owned or founder-approved repositories. It does not support hostile multi-tenant operation.

Accepted risks:

- Hermes Agent is a large runtime with broad tool, memory, gateway, and plugin capabilities.
- Skills/plugins can execute code, alter behavior, and access credentials if allowed.
- Telegram, GitHub, LLM providers, VPS runtime, and coding sandboxes form a broad trust boundary.
- Some ecosystem components may be beta, experimental, or community-maintained.

Required mitigations:

- Use a Telegram allowlist and explicit founder chat pairing.
- Use least-privilege GitHub tokens scoped to required repositories and operations.
- Scope LLM, GitHub, Telegram, and VPS credentials separately; do not share a broad all-purpose token.
- Prefer sandboxed execution for generated-code work and dangerous commands.
- Disable unreviewed project-local plugins and marketplace auto-installation.
- Maintain an allowlist of enabled Hermes skills/plugins with source, version/commit, purpose, required credentials, review result, and rollback method.
- Pin Hermes runtime and all enabled skills/plugins to versions or commits for v0.1 deployments.
- Source-review any optional/community skill before it receives credentials or write access.
- Require approval for dangerous commands, credential changes, public endpoint exposure, spending money, or deployment actions.
- Keep a rollback path: disable the skill/plugin, revoke credentials, stop Hermes service, restore the last known-good runtime config, and continue from repository state.
- Do not commit `.env`, PATs, API keys, SSH keys, Telegram tokens, or VPS credentials.

## 11. OpenClaw Assessment

OpenClaw remains a valid later candidate for gateway/control UI capabilities because it offers a broad multi-channel gateway and Control UI. It should not displace Hermes in v0.1 unless implementation finds a documented Hermes blocker such as inability to operate the required Telegram workflow, unacceptable security limitations that cannot be mitigated, or missing GitHub/agent orchestration capabilities that cannot be reasonably bridged.

If revisited, OpenClaw should be evaluated as:

- A founder-facing gateway/control UI alongside or in front of Hermes.
- A read-only project status UI.
- A multi-channel expansion after Telegram is stable.

OpenClaw plugins run in-process and its large skill ecosystem remains a supply-chain risk. Any OpenClaw adoption requires a separate ADR.

## 12. CI and Validation

The v0.1 CI baseline should run:

- `python scripts/validate_docs.py`.
- Project tests when production code exists.
- Lint/typecheck when configured by implementation tickets.
- Static/security checks selected by architecture or security tickets.

Docs validation should check frontmatter, required ticket sections, ADR structure, and gradually add cross-link and status validation.

## 13. Generated Project Contract

Generated projects should include:

- `README.md` with purpose, status, and local run instructions.
- `CONTRIBUTING.md` with role/write-zone rules.
- `AGENTS.md` for agent operating rules.
- `docs/prd/`, `docs/architecture/`, `docs/tickets/`, `docs/reviews/`, `docs/questions/`, and `docs/orchestration/`.
- CI workflow running docs validation and relevant application checks.
- PR and review templates.
- Handoff notes and known risks.
- A documented one-command VPS deployment entry point, such as `make deploy` or an equivalent script, with final live execution requiring founder approval.

## 14. Implementation Ticket Strategy

Tickets remain `draft` until the user approves this revised architecture and resolves ticket-specific blockers. The first Executor sequence should establish validation and governance, then Hermes/Telegram runtime, then GitHub and security hardening.

## 15. Remaining User Decisions

The following decisions block some implementation tickets but do not block approval of this architecture:

1. Exact Telegram command set and whether free-form chat is allowed beyond the hybrid model proposed here.
2. Whether the lightweight web interface is deferred, read-only, or still required in v0.1 after Telegram is working.
3. Preferred operational state store for Hermes v0.1: Hermes native persistence if sufficient, SQLite on VPS, or another minimal database.
4. Initial Hermes skill/plugin allowlist, especially GitHub and coding-agent skills.
5. GitHub credential strategy: assistant-owned account token, GitHub App, or founder-provided repository access.
6. Merge policy after CI and Reviewer pass: always ask founder in v0.1 is recommended.
7. Exact one-command VPS deployment contract generated projects should expose.
