---
id: SESSION-LOG-README
version: 0.1.0
status: active
---

# Session Log — Strategic Orchestrator handoff snapshots

This directory holds **session-handoff snapshots** for the Strategic Orchestrator (SO) role on `developer-assistant`. Each file captures the state needed for a fresh SO session (or any other agent inheriting strategic context) to bootstrap without losing project context, role identity, or pipeline discipline.

## File naming

`YYYY-MM-DD-session-N.md` where `N` increments across sessions on the same day.

Example: `2026-05-01-session-1.md`, `2026-05-01-session-2.md`, etc.

## File types

| Snapshot type | When to use | Approx size | Texture? |
|---|---|---|---|
| `handoff-cold-orchestrator.md` (template) | Routine — fresh opencode session, no prior planning. **Auto-generated after every closed TKT cycle.** | ~300–500 lines | Formal state only — no texture |
| `handoff-warm-orchestrator.md` (template) | Planned — Founder triggered with "switching to a new SO session". | ~600–1000 lines | Cold + texture, observations, open conversational threads, intentional omissions |

Templates live in `TEMPLATES/`.

## Auto-cold rule

After every **closed TKT cycle** — i.e. both the Code PR and its corresponding `RV-CODE-*` review file are merged into `main`, plus the closure-PR with status flips and BACKLOG entries — the SO MUST automatically generate a `handoff-cold-orchestrator` snapshot under `<YYYY-MM-DD>-session-N.md`, **without waiting for the Founder to ask**.

The auto-cold file is committed via the standard PR flow (a single small PR titled `session-log: auto-cold after <TKT-NNN> cycle close`).

Warm handoffs remain **on-demand only**. Texture is expensive to capture and only worth it when a planned switch is imminent.

## Founder-side how-to (when to switch sessions)

Signs the SO session is "drifting" and you should switch to a fresh one:
- SO starts repeating itself or contradicting itself across messages.
- SO asks a question whose answer is already in `SESSION-STATE.md` or a prior session-log snapshot.
- SO refuses to read a file you can clearly see in `git log` (context-window thrashing).
- SO claims it remembers something from "the start of the conversation" but the supposed earlier message does not exist in your scrollback.

When you see any of these: ask the SO to write a `handoff-warm-orchestrator.md` snapshot, then start a fresh opencode tab loading GPT-5.5 high and paste the bootstrap message from `docs/meta/strategic-orchestrator.md` § 7 followed by the snapshot body.

Routine session switches (e.g. closing your laptop, restarting opencode) do not require a warm snapshot — the auto-cold from the last closed TKT cycle is enough.
