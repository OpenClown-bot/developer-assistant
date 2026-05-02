---
id: SESSION-LOG-TEMPLATE-warm
version: 0.1.0
status: template
---

# Warm Handoff Template — Strategic Orchestrator

This template is filled in by the outgoing Strategic Orchestrator (SO) when the Founder triggers a planned session switch ("переезжаем в новую SO сессию" / "let's switch SO sessions"). Save the filled-in copy as `docs/session-log/<YYYY-MM-DD>-session-N.md`.

Warm = cold + texture. Texture is conversational context the new SO needs to feel continuous to the Founder: sticky moments, observations, open conversational threads, intentional omissions.

---

## 0. Self-checks (the new SO runs these autonomously, no Founder interaction)

```
gh auth status
git -C ~/repos/developer-assistant fetch origin
git -C ~/repos/developer-assistant log --oneline -10
cd ~/repos/developer-assistant && python3 scripts/validate_docs.py
cd ~/repos/developer-assistant && pytest tests/
gh pr list --repo OpenClown-bot/developer-assistant --state open
```

Expected: `gh` authenticated; `main` clean; validator says "Docs validation passed."; pytest all green; open PR list matches § 5.2 below.

If anything fails, stop and report to the Founder before proceeding.

## 1. Required reading (in order, in full)

(Same list as the cold template § 1, plus the warm-only § 6 of THIS file before answering anything.)

1. `docs/meta/strategic-orchestrator.md` — your portable System Prompt.
2. `README.md`
3. `CONTRIBUTING.md`
4. `AGENTS.md`
5. `docs/prompts/business-planner.md`
6. `docs/prompts/architect.md`
7. `docs/prompts/executor.md`
8. `docs/prompts/reviewer.md`
9. `docs/prompts/ticket-orchestrator.md`
10. `docs/prompts/runtime-hermes-orchestrator.md`
11. `docs/prd/PRD-001.md`
12. `docs/architecture/ARCH-001.md` and any cited ADRs
13. All `docs/tickets/TKT-*.md`
14. `docs/orchestration/SESSION-STATE.md`
15. The PRIOR session-log file referenced as "predecessor" in § 5.6 below.
16. This file (the snapshot).
17. **Warm-only:** § 6 (Texture) of this file BEFORE the first-reply protocol.

## 2. Project context

(Copy verbatim from `docs/meta/strategic-orchestrator.md` § 2.)

## 3. Pipeline diagram

(Copy verbatim from `docs/meta/strategic-orchestrator.md` § 3.)

## 4. Roles and write zones

(Copy verbatim from `CONTRIBUTING.md` § Roles and write zones.)

## 5. Current state — fill in at snapshot time

### 5.1 Active TKT cycles (in flight)

| TKT id | iter | Executor PR | Reviewer PR | Reviewer verdict | PR-Agent state |
|---|---|---|---|---|---|
| `TKT-NNN` | iter-N | `#<N>` `<SHA>` | `#<N>` `<SHA>` | `<pending / pass / fail>` | `<IN_PROGRESS / success / failure>` |

### 5.2 Open PRs

| PR # | Branch | Wait on | CI status | Notes |
|---|---|---|---|---|
| `<N>` | `<branch>` | `<role / Founder>` | `<green / red / pending>` | `<one-liner>` |

### 5.3 Recently closed TKT cycles (last 3)

| TKT id | Closed at | Final iters | Notable findings | BACKLOG entries |
|---|---|---|---|---|
| `TKT-NNN` | `<ISO>` | `<N>` | `<list>` | `<list>` |

### 5.4 Outstanding Q-Founder items

| Topic | Asked at | Why it matters | Proposed answer (if any) |
|---|---|---|---|

### 5.5 Tooling assumptions (verified at snapshot time)

(Same as cold template § 5.5.)

### 5.6 Predecessor session-log file

`docs/session-log/<YYYY-MM-DD>-session-(N-1).md` — read this for the prior context.

## 6. Texture (warm-only — read BEFORE first reply)

### 6.1 Sticky moments / open conversational threads

- `<one-paragraph summary>` of any thread that the Founder is likely to return to (e.g. "we discussed deferring TKT-NEW-7 because Founder wants to ship the Hermes skill allowlist first; revisit after TKT-012 closes").
- ...

### 6.2 Observations about the Founder

- `<one-line>` (e.g. "Founder prefers terse status updates; lengthy hand-holding annoys; teach via 1-2 sentence rationale per action, not multi-paragraph essays.").
- ...

### 6.3 Intentional omissions

- `<one-line>` (e.g. "Did NOT propose TKT-NEW-X yet; Founder explicitly deferred until ARCH-001@0.3.0.").
- ...

### 6.4 Communication-style cheatsheet

- Default Russian when talking to Founder; English in repo artifacts.
- Bias to brevity; if Founder asks "почему?" expand with concrete reasoning.
- When pushing back, cite the artifact and quote the line, never just "I think...".

## 7. First-reply protocol (the new SO MUST send this back to the Founder before doing any work)

Send a 6-line reply containing:

1. Role confirmation: "I'm the Strategic Orchestrator for developer-assistant on this opencode session, GPT-5.5 high — taking over via warm handoff."
2. State acknowledgement: "In flight: TKT-NNN iter-N (waiting on Reviewer / PR-Agent). Open PRs: #X #Y. Default next-up: TKT-NNN ready."
3. Validator/pytest result: "validator: 0 failed; pytest: NN passed."
4. **Texture quote** (warm-only): one verbatim observation from § 6 of this file (e.g. "Note: TKT-NEW-7 is deferred until TKT-012 closes per our prior conversation.") — proves the new SO actually read the warm material.
5. Concrete next-action proposal: "Want me to wait on TKT-NNN PR-Agent settle, or pick up the TKT-NNN iter-N+1 NUDGE the prior SO had drafted?"
6. Question or pause: "Confirm direction before I draft the next NUDGE."

Do **not** start drafting NUDGEs, opening PRs, or taking other action until the Founder responds to the first-reply.
