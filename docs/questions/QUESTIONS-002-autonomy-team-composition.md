---
id: QUESTIONS-002
version: 0.1.0
status: resolved
---

# Autonomy, Team Composition, and Upstream Composability — Founder Q&A

This document captures the three product questions raised by the Business Planner during the PRD-001 v0.2.1 revision and the Founder's recorded answers. The answers are reflected in PRD-001 v0.2.1 §§ 3, 6, 7, 9, 10, 11, and 13. This file is the durable Q&A record; PRD-001 is the durable product specification.

## Context

PRD-001 v0.2.0 added a self-deployment operational target (§ 12). While reviewing v0.2.0 the Founder raised three additional product positions that needed to be captured in PRD before the Architect could begin the self-deployment design pass:

1. The assistant must be operationally **autonomous** during day-to-day project work; approval prompts must be the exception, not the rule.
2. Internally the assistant should be a **team of full Hermes runtimes** — one main Hermes facing the Founder, plus one specialist Hermes per role behind it (each with its own memory and self-learning state, each on the model best suited to that role). Externally the Founder still talks to one entity.
3. In a future iteration the Founder will address the assistant through **OpenClaw** rather than Telegram; OpenClaw will delegate project-creation tasks to this assistant on the Founder's behalf. v0.1 does not implement this but must not preclude it.

The Business Planner translated each into an explicit product question with options, recommended default, and trade-offs, and presented them to the Founder. The Founder's selections are recorded below verbatim.

## Resolved

| Topic | Decision |
| --- | --- |
| Operating mode | High autonomy with exception-based escalation. The assistant escalates to the Founder ONLY when a candidate decision deviates from the original concept agreed at intake OR risks breaking already-committed scope or operational state. All other day-to-day decisions are autonomous. The operational definition of "deviates" and "breaks" is the Architect's escalation-policy artifact. |
| Team composition | Multi-Hermes is a v0.1 hard requirement. Each specialist role (Business Planner, Architect, Executor, Reviewer, Orchestrator) runs as its own full Hermes runtime with its own memory and self-learning state. The main Hermes is the only one the Founder talks to. The Founder accepts that this lengthens the path to TKT-011 by roughly 1.5x–2x because of IPC, memory isolation, and orchestration. |
| Upstream composability | v0.1 does not implement OpenClaw integration, but the architecture must abstract the upstream entry-point so that adding an OpenClaw adapter (or any future adapter) in v0.2 is an adapter-level addition, not a core rewrite. Whether v0.2 supports simultaneous Telegram + OpenClaw adapters or only one at a time remains an open question (PRD-001 § 10 question 18). |
| Self-deployment approval gates (clarification) | The three approval gates in PRD-001 § 12.5 (`install` without approval, `start` with approval, `upgrade` with approval and state-store backup) govern the moment the assistant gains operational control of the Founder's VPS and the moment a running assistant is replaced by a new version. They are a separate, narrower regime from the day-to-day autonomy model and remain in force regardless. |

## Question Trail

### Q1 — Multi-Hermes scope in v0.1

> Multi-Hermes (one main + a team of full subagents with memory and self-learning, each on its own model) — is this a v0.1 hard requirement or a direction?

Options presented:

- **A. v0.1 hard requirement**: multi-Hermes is mandatory in v0.1; each role is its own Hermes runtime. Trade-off: time to TKT-011 grows by ~1.5x–2x because of IPC, memory synchronization, and orchestration.
- **B (recommended at the time)**: v0.1 single runtime with roles, but the Architect must design so that a v0.2 transition to multi-Hermes does not require rewriting (roles isolated, communicating through clear contracts).
- **C**: future direction only; v0.1 PRD does not commit, Architect chooses freely.

**Founder selection: A.**

### Q2 — OpenClaw upstream integration

> Future plan: the Founder talks to OpenClaw, OpenClaw dispatches project creation to this assistant's main Hermes.

Options presented:

- **A**: v0.1 must already accept OpenClaw upstream calls. (Strongly expands scope, delays v0.1.)
- **B (recommended at the time)**: v0.1 does not implement, but the Architect must surface "upstream entry-point" as an explicit abstraction so that replacing or adding OpenClaw in v0.2 is a question of a new adapter, not a rewrite.
- **C**: v0.1 strictly Telegram-only; OpenClaw question deferred and risks rewriting in v0.2.

**Founder selection: B.**

### Q3 — Approval criterion during day-to-day project work

> When MUST the assistant ask the Founder during day-to-day project work (not self-deployment).

Options presented:

- **A (recommended at the time)**: single trigger — "deviates from the original concept or breaks something." All other decisions (library choice, routine PR merges, already-agreed external APIs, CI configuration, etc.) are autonomous. Operational definition of "deviates" and "breaks" is the Architect's escalation-policy artifact.
- **B**: trigger plus hard categories — money above a threshold, exposing public endpoints, attaching new external services always require approval even within concept.
- **C**: leave PRD-001 § 10 question 9 open; let the Architect or a separate security policy resolve it.

**Founder selection: A.**

## Pointers

- The product positions resolved here are reflected in PRD-001 v0.2.1: § 3 (v0.1 goal), § 6 (functional requirements), § 7 (non-functional requirements: autonomy, memory isolation), § 9 (success criteria), § 10 (question 9 marked resolved; new questions 16–18 added), § 11 (handoff notes for the Architect, including the new Section 13 handoff subsection), and § 13 (operating mode, team composition, upstream composability).
- The Architect must produce, during the self-deployment design pass referenced in `docs/backlog/TKT-NEW-self-deployment-architect-pass.md`, an "escalation policy" artifact that operationalizes the Q3 trigger ("deviates" or "breaks") into rules a running assistant can apply without per-decision Founder consultation. PRD-001 § 11 lists this as a required handoff artifact.
- The Architect should expect that absorbing the Q1 and Q2 mandates may require revising ARCH-001 (likely to v0.3.0) and possibly extending HERMES-RUNTIME-CONTRACT and OPERATIONAL-STATE-STORE before the SELF-DEPLOYMENT-CONTRACT can be finalized. The PRD-001 v0.2.1 → Architect pass → TKT-011 sequencing constraint stands.
