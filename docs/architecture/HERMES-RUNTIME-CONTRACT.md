---
id: HERMES-RUNTIME-CONTRACT
version: 0.1.0
status: draft
---

# Hermes Runtime Integration Contract

## 1. Purpose

This document defines the v0.1 contract between Hermes Agent runtime behavior and `developer-assistant` repository governance artifacts. It specifies what the Hermes runtime receives as input, what it must produce as output, what state is authoritative, what state lives outside the repository, and what security constraints apply.

This contract is a boundary specification. It does not implement a runtime adapter, install or run Hermes Agent, enable marketplace skills/plugins, or add credentials.

## 2. Runtime Boundary

The Hermes runtime is the execution layer. It receives structured inputs, performs orchestrated work, and produces structured outputs. Repository artifacts are the governance layer. The runtime does not override, replace, or circumvent repository-governed decisions.

The boundary rule: if a piece of state affects product scope, architecture, tickets, reviews, approvals, security policy, merge decisions, or deployment decisions, it must exist as a repository artifact. Operational state that supports execution without governing product decisions may live outside the repository.

## 3. Authoritative Governance State

Repository artifacts remain the authoritative governance state for the following domains:

| Domain | Repository Path | Authority |
| --- | --- | --- |
| Product requirements | `docs/prd/` | Authoritative |
| Architecture specifications | `docs/architecture/` | Authoritative |
| Architecture decision records | `docs/architecture/adr/` | Authoritative |
| Implementation tickets and status | `docs/tickets/` | Authoritative |
| Founder questions and decisions | `docs/questions/` | Authoritative |
| Reviewer LLM artifacts and verdicts | `docs/reviews/` | Authoritative |
| Session state, phase, blockers, handoff | `docs/orchestration/` | Authoritative |
| Role prompts | `docs/prompts/` | Authoritative |

Hermes memory, Telegram chat history, and operational database records are not authoritative for product, architecture, tickets, reviews, or approvals. If Hermes memory or operational state contradicts repository artifacts, repository artifacts take precedence.

When the runtime makes a durable decision, it must write or update the corresponding repository artifact before considering the decision final.

## 4. Runtime Input Contract

Each Hermes runtime invocation for a role-based task must receive the following inputs:

| Input Field | Description | Required |
| --- | --- | --- |
| `telegram_event` | Incoming Telegram message or command that triggered the invocation, including chat ID, user ID, message text, timestamp, and reply-to context | Yes |
| `project_binding` | Telegram chat ID to GitHub repository and local workspace mapping from the project registry | Yes |
| `role` | The assigned role for this invocation: `orchestrator`, `business_planner`, `architect`, `executor`, or `reviewer` | Yes |
| `required_context_paths` | List of repository artifact paths the role must read before acting, as defined in `AGENTS.md` and the relevant ticket | Yes |
| `task_prompt` | The specific task instruction derived from a ticket, question, or orchestration decision | Yes |
| `allowed_files` | Write zones the role is permitted to modify, per `CONTRIBUTING.md` role write zones | Yes |
| `expected_outputs` | The output types the role must produce, from the set defined in Section 5 | Yes |

Additional input constraints:

- `telegram_event` must be authenticated against the Telegram allowlist before any role action.
- `required_context_paths` must be read in full before the role begins its primary task.
- `allowed_files` must be enforced by the runtime. If the role attempts to write outside its zone, the runtime must block the write and report the violation.
- `task_prompt` must reference a specific ticket ID when the invocation serves ticket implementation.

## 5. Runtime Output Contract

Each Hermes runtime invocation for a role-based task must produce the following outputs:

| Output Field | Description | Required |
| --- | --- | --- |
| `status` | Final status of the invocation: `completed`, `blocked`, `failed`, or `needs_approval` | Yes |
| `files_changed` | List of repository file paths created or modified, with change summary per file | Yes |
| `validation_commands` | List of commands that should be run to validate the changes (e.g., `python scripts/validate_docs.py`) | Yes |
| `founder_questions` | Zero or more questions requiring founder input (see sub-fields below) | Conditional: when the role encounters a decision it cannot make |
| `blockers` | Zero or more blockers preventing progress, with description and resolution path | Conditional: when progress is blocked |
| `progress_report_text` | Human-readable progress summary in Russian for Telegram delivery | Yes |
| `handoff_summary` | Structured summary of what was accomplished, what remains, and recommended next action, suitable for writing to `docs/orchestration/SESSION-STATE.md` | Yes |

### Founder Question Sub-Fields

Each entry in `founder_questions` must include:

| Sub-Field | Description | Required |
| --- | --- | --- |
| `context` | What situation produced the question | Yes |
| `options` | Available decision options | Yes |
| `recommended_default` | The option the role recommends if no response is given | Yes |
| `impact` | What is affected by this decision | Yes |
| `urgency` | `low`, `medium`, or `high` indicating time-sensitivity | Yes |
| `durable_artifact_target` | Repository path where the decision will be recorded once resolved (e.g., `docs/prd/`, `docs/architecture/adr/`, `docs/questions/`) | Yes |

### Blocker Sub-Fields

Each entry in `blockers` must include:

| Sub-Field | Description | Required |
| --- | --- | --- |
| `description` | What is blocking progress | Yes |
| `resolution_path` | What must happen to resolve the blocker | Yes |
| `owner` | Who or what role can resolve it | Yes |

### Handoff Summary Sub-Fields

The `handoff_summary` must include:

| Sub-Field | Description | Required |
| --- | --- | --- |
| `accomplished` | What was completed in this invocation | Yes |
| `remaining` | What is still outstanding for the current ticket or task | Yes |
| `next_action` | Recommended next step, including role and ticket ID if applicable | Yes |
| `artifacts_updated` | Repository artifacts modified during this invocation | Yes |

## 6. Operational State Outside Repository

The following operational state is stored outside the repository because it supports runtime execution without governing product or engineering decisions:

| External State | Description | Persistence |
| --- | --- | --- |
| Telegram user/chat allowlist | Allowed founder chat IDs and user IDs | Operational store |
| Telegram-to-project binding | Mapping of chat IDs to GitHub repository and workspace paths | Operational store |
| Project registry | Active projects, their repositories, workspaces, and current phase metadata | Operational store |
| Scheduled progress timers | Timestamps and intervals for periodic progress reports | Operational store |
| Hermes run IDs and idempotency keys | In-flight agent-run metadata, retry keys, and deduplication data | Operational store |
| Last-report timestamps | When the last progress report was sent per project | Operational store |
| Non-secret credential metadata | Which secret names must exist in the runtime environment (not the secret values) | Operational store |
| Telegram chat history | Raw message log for context (not authoritative for decisions) | Hermes memory or operational store |

The preferred implementation should use the smallest operational store that satisfies Hermes integration needs: Hermes native persistence if sufficient, or a local SQLite database on the VPS. The final choice is an implementation decision documented before the runtime ticket is marked ready.

External state must not store canonical product, architecture, security, merge, or deployment decisions without writing a corresponding durable repository artifact. Secrets must not live in operational tables; they must use environment variables, Hermes-supported secret mechanisms, GitHub Actions secrets, or VPS secret storage.

## 7. Role Execution Contract

Each role invocation follows this execution sequence:

1. Authenticate the `telegram_event` against the Telegram allowlist.
2. Resolve `project_binding` from the project registry.
3. Read all `required_context_paths` from the repository.
4. Execute the `task_prompt` within `allowed_files` constraints.
5. Produce all `expected_outputs` defined in Section 5.
6. Write any repository artifact updates before reporting completion.
7. Return structured output to the Orchestrator.

The Orchestrator role has additional responsibilities:

- Route `telegram_event` to the correct role based on classification (intake, answer, clarification, approval, rejection, question).
- Send `founder_questions` to Telegram in Russian.
- Capture founder responses and normalize them into English durable decision notes.
- Write decision notes to the `durable_artifact_target` specified in the question.
- Deliver `progress_report_text` to Telegram.
- Update `docs/orchestration/SESSION-STATE.md` with the `handoff_summary`.
- Schedule periodic progress reports every 30 to 60 minutes during long-running work.

## 8. Telegram Interaction Contract

Telegram is the primary founder interface for v0.1. The contract covers commands and free-form interaction.

### Commands

| Command | Action |
| --- | --- |
| `/new_project` | Start guided intake; create or select a project workspace after required approvals |
| `/status` | Return current phase, active ticket, active PR, blockers, and pending decisions |
| `/decisions` | List open decisions requiring founder input |
| `/pause` | Stop autonomous work for the current project |
| `/resume` | Resume autonomous work for the current project |

### Free-Form Messages

Free-form founder messages are routed to the Orchestrator for classification as: intake, answer, clarification, approval, rejection, or general question.

### Decision Capture

- Telegram chat history is not sufficient for durable decisions.
- Decisions affecting product scope, architecture, security, credentials, merge policy, deployment, external services, or cost must be summarized into repository artifacts.
- Operational acknowledgements that do not affect durable engineering behavior may remain in operational state.

### Progress Reports

- Sent after each ticket phase change or PR/review gate completion.
- Sent on a 30-to-60-minute interval during long-running work.
- Content: completed work, current action, blocker state, decisions needed, notable risks.
- Avoid deep technical detail unless requested or required for a decision.
- Language: Russian.

## 9. GitHub and PR Interaction Contract

The runtime interacts with GitHub through least-privilege credentials and repository-scoped permissions.

### Implementation Flow

1. Founder approves architecture and ticket sequence.
2. Ticket moves to `ready` only when no unresolved blocker remains.
3. Executor works on one ticket in a branch.
4. Executor opens a PR linked to the ticket.
5. CI runs docs validation and relevant checks.
6. `pr-agent` or equivalent automated review provides supplemental feedback.
7. Reviewer LLM writes artifact under `docs/reviews/` using allowed verdicts (`pass`, `pass_with_changes`, `fail`).
8. Founder acknowledgement is required before merge in v0.1.

### Constraints

- Autonomous merges are not the default for v0.1.
- GitHub tokens must be scoped to required repositories and operations only.
- LLM, GitHub, Telegram, and VPS credentials must be scoped separately; no shared all-purpose token.

## 10. Validation and Reporting Contract

### Validation

The runtime must trigger or confirm the following validation after producing file changes:

| Validation | Command | When |
| --- | --- | --- |
| Docs validation | `python scripts/validate_docs.py` | After every artifact change |
| Project tests | Project-specific test command | When production code exists |
| Lint/typecheck | Project-specific lint/typecheck command | When configured |
| Static/security checks | Project-specific security command | When configured |

The `validation_commands` output field must list the specific commands relevant to the changes made.

### Reporting

After each invocation:

1. Runtime produces `progress_report_text` in Russian.
2. Orchestrator delivers it to Telegram.
3. Orchestrator updates `docs/orchestration/SESSION-STATE.md` with the `handoff_summary`.

After each ticket phase change or PR gate:

1. Runtime sends a phase-change report to Telegram.

During long-running work:

1. Orchestrator sends time-based progress updates every 30 to 60 minutes.

## 11. Security Requirements

### Secrets

- Secrets must never appear in repository artifacts, logs, or runtime output.
- Prohibited in repository: `.env` files, GitHub PATs, LLM API keys, VPS SSH keys, Telegram tokens, service credentials.
- Secrets must live in environment variables, Hermes-supported secret mechanisms, GitHub Actions secrets, or VPS secret storage.
- Non-secret credential metadata (which secret names are required) may appear in operational state and architecture docs.

### Skill and Plugin Use

- Marketplace auto-installation is not allowed.
- Enabled skills/plugins must be allowlisted with the following fields per ADR-003: name, source URL, version/commit, purpose, built-in/optional/community classification, required credentials and scope, source review result and reviewer/date, sandbox or isolation mode, dangerous operations, rollback procedure.
- Community or optional skills/plugins must not receive credentials or write access until source-reviewed and explicitly added to the allowlist.
- Hermes runtime and all enabled skills/plugins must be pinned to versions or commits for v0.1 deployments.

### Sandboxing

- Prefer sandboxed execution for generated-code work, shell commands, and repository-modifying tools.
- Unreviewed project-local plugins are disabled by default.

### Dangerous Command Approval

The following actions require explicit founder approval before execution:

- Credential changes (creation, rotation, revocation, scope changes).
- Public endpoint exposure (opening ports, deploying to public URLs).
- Spending money (paid API calls, cloud resource allocation).
- Deployment actions (VPS deployment, live execution).
- Irreversible Git operations (force push, hard reset, branch deletion).
- Merge operations in v0.1 (founder acknowledgement required before merge).

### Rollback

When a skill/plugin causes harm or behaves unexpectedly:

1. Disable the skill/plugin.
2. Revoke its scoped credentials.
3. Stop the Hermes service.
4. Restore the last known-good runtime config.
5. Resume from repository state (repository artifacts remain authoritative).

## 12. OpenClaw Position

OpenClaw is not part of v0.1. It is named here only as a later possible gateway/control UI addition. If revisited, OpenClaw should be evaluated as:

- A founder-facing gateway/control UI alongside or in front of Hermes.
- A read-only project status UI.
- A multi-channel expansion after Telegram is stable.

OpenClaw plugins run in-process and its large skill ecosystem remains a supply-chain risk. Any OpenClaw adoption requires a separate ADR with equivalent or stricter controls than ADR-003.

## 13. Known Limitations

- This contract defines boundary specifications, not a runtime adapter implementation.
- Concrete Hermes API calls, message formats, and configuration are implementation details for a follow-up ticket.
- The operational state store choice (Hermes native persistence vs. SQLite) is not finalized in this document.
- The Telegram command set may evolve beyond the initial commands listed here.
- Sandbox capabilities depend on Hermes runtime features not yet evaluated in practice.
- The contract assumes one trusted founder/operator and does not address hostile multi-tenant scenarios.

## 14. Follow-Up Tickets

- TKT for Hermes runtime adapter implementation: binding this contract to actual Hermes Agent APIs and configuration.
- TKT for operational state store selection: deciding between Hermes native persistence and SQLite, implementing the chosen store.
- TKT for Hermes skill/plugin allowlist: defining the initial concrete allowlist entries per ADR-003.
- TKT for Telegram command handler implementation: wiring the command set to Hermes gateway behavior.
- TKT for end-to-end integration test: validating a complete Telegram-to-PR-to-review-to-merge cycle.
