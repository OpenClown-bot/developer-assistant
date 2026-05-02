---
id: SESSION-LOG-TEMPLATE-cold
version: 0.1.0
status: template
---

# Cold Handoff Template — Strategic Orchestrator

This template is filled in by the outgoing Strategic Orchestrator (SO) at the end of every closed TKT cycle, OR ad-hoc when the Founder triggers a routine session switch. Save the filled-in copy as `docs/session-log/<YYYY-MM-DD>-session-N.md`.

Cold = formal state only, no texture. Use the **warm** template instead when a planned session switch is imminent and conversational texture matters.

---

## 0. Self-checks (the new SO runs these autonomously, no Founder interaction)

```
gh auth status
git -C ~/repos/developer-assistant fetch origin
git -C ~/repos/developer-assistant log --oneline -5
cd ~/repos/developer-assistant && python3 scripts/validate_docs.py
cd ~/repos/developer-assistant && pytest tests/
```

Expected: `gh` authenticated; `main` clean; validator says "Docs validation passed."; pytest all green.

If anything fails, stop and report to the Founder before proceeding.

## 1. Required reading (in order, in full)

1. `docs/meta/strategic-orchestrator.md` — your portable System Prompt.
2. `README.md`
3. `CONTRIBUTING.md`
4. `AGENTS.md`
5. `docs/prompts/business-planner.md`
6. `docs/prompts/architect.md`
7. `docs/prompts/executor.md`
8. `docs/prompts/reviewer.md`
9. `docs/prompts/ticket-orchestrator.md`
10. `docs/prompts/runtime-hermes-orchestrator.md` (runtime persona, NOT a dev-time pipeline role — read so you don't confuse it with the Ticket Orchestrator role)
11. `docs/prd/PRD-001.md`
12. `docs/architecture/ARCH-001.md` and any cited ADRs
13. All `docs/tickets/TKT-*.md`
14. `docs/orchestration/SESSION-STATE.md`
15. This file (the snapshot)

## 2. Project context

(Copy verbatim from `docs/meta/strategic-orchestrator.md` § 2.)

## 3. Pipeline diagram

(Copy verbatim from `docs/meta/strategic-orchestrator.md` § 3.)

## 4. Roles and write zones

(Copy verbatim from `CONTRIBUTING.md` § Roles and write zones.)

## 5. Current state — fill in at snapshot time

### 5.1 Last closed TKT cycle

- TKT id: `TKT-NNN@vX.Y.Z`
- Closed at: `<ISO timestamp>`
- Final Executor PR: `#<NN>` (`<final-tkt-SHA>`)
- Final Reviewer PR: `#<NN>` (`<final-rv-SHA>`)
- Closure PR: `#<NN>` (`<closure-SHA>`)
- Final Reviewer verdict: `<pass | pass_with_changes>`
- Iters: 1 → ... → final
- BACKLOG entries created: `<list>`
- Lessons (if any): `<short bullet list>`

### 5.2 Open PRs (none expected at cold-handoff time after auto-cold rule fires)

| PR # | Branch | Wait on | CI status |
|---|---|---|---|
| `<N>` | `<branch>` | `<role / Founder>` | `<green / red / pending>` |

### 5.3 Active / next TKT candidates

| TKT id | Status | Notes |
|---|---|---|
| `TKT-NNN` | `ready` | Default next-up if Founder agrees. |
| `TKT-NNN` | `draft` | Architect work pending. |

### 5.4 Outstanding Q-Founder items

| Topic | Asked at | Why it matters |
|---|---|---|
| `<topic>` | `<ISO timestamp>` | `<one-line>` |

### 5.5 Tooling assumptions (verified at snapshot time)

- opencode + GPT-5.5 high reachable via OmniRoute → Fireworks.
- `gh` CLI authenticated with PAT (env var name documented in `docs/orchestration/SESSION-STATE.md` Tooling Decisions).
- Validator + pytest green on `origin/main`.
- PR-Agent workflow live and recent runs `conclusion: success`.

## 6. First-reply protocol (the new SO MUST send this back to the Founder before doing any work)

Send a 5-line reply containing exactly:

1. Role confirmation: "I'm the Strategic Orchestrator for developer-assistant on this opencode session, GPT-5.5 high."
2. State acknowledgement: "Last closed TKT was TKT-NNN. No open PRs. Default next-up: TKT-NNN ready, awaiting your go."
3. Validator/pytest result: "validator: 0 failed; pytest: NN passed."
4. Concrete next-action proposal: "Want me to dispatch a TO session for TKT-NNN, or pick a different TKT first?"
5. Question or pause: "Confirm direction before I draft the TO bootstrap."

Do **not** start drafting NUDGEs, opening PRs, or taking other action until the Founder responds to the first-reply.
