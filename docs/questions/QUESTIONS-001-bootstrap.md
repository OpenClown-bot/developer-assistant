---
id: QUESTIONS-001
version: 0.1.0
status: open
---

# Bootstrap Questions

## Resolved

| Topic | Decision |
| --- | --- |
| Project name | `developer-assistant` |
| User-facing language | Russian |
| Repo artifact language | English prompts and durable docs, Russian discussion |
| Git host | GitHub |
| Deployment target | User-owned VPS |
| Process strictness | Lightweight PRD -> ArchSpec -> Tickets |
| Review approach | Automated PR review plus Reviewer LLM |
| Reference process | Use `OpenClown-bot/openclown-assistant` as inspiration, not as a direct template copy |
| Role model mapping | Business Planner: Codex GPT-5.5 High; Architect: Codex GPT-5.5 XHigh; Executor: GLM 5.1; Reviewer: Kimi 2.6 |
| Architecture approval | Current custom-thin-orchestrator architecture is not approved and must be revised before implementation |
| Telegram priority | Telegram interaction is required in v0.1, not deferred |
| Platform preference | User prefers building around Hermes Agent for v0.1, with OpenClaw possibly added later |
| Platform risk posture | User accepts some Hermes/OpenClaw platform, plugin, and security risks if documented and mitigated |
| v0.1 foundation recommendation | Revised architecture recommends a Hermes-first hybrid foundation with repository docs-as-code governance preserved |
| OpenClaw position | OpenClaw is deferred as a possible later gateway/control UI unless a Hermes blocker is documented |
| State model | Repository artifacts remain governance source of truth; external operational state is required for Telegram/Hermes runtime metadata |
| Architecture baseline | User approved `ARCH-001` version `0.2.0` as the v0.1 baseline |
| Telegram model | Hybrid commands plus free-form classification |
| Web interface | Deferred until Telegram works |
| Operational state default | SQLite on VPS unless Hermes native persistence is proven sufficient |
| Hermes allowlist | Minimal Telegram, GitHub, coding-agent delegation, and sandbox/runtime capabilities only |
| GitHub credential direction | Fine-grained PAT first, GitHub App later |
| Static/security tools | Docs validation first, Semgrep/CodeQL later |
| Merge policy | Always ask founder after CI and Reviewer pass in v0.1 |
| VPS deployment contract | One-command `make deploy` or equivalent; final live deployment requires founder approval |

## Open

1. Which first tickets should be marked `ready` for Executor work after architecture approval?
2. Should this local folder be initialized as a git repository and connected to `https://github.com/OpenClown-bot/assistant-developer`?
3. Should GitHub CLI `gh` be installed for PR operations, or should v0.1 proceed with plain `git` plus GitHub UI/API until `gh` is available?
