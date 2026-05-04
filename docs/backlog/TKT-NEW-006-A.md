---
id: TKT-NEW-006-A
version: 0.1.0
status: completed
source_tkt: TKT-006
created: 2026-05-03
completed_by_tkt: TKT-015
completed_at: 2026-05-04
---

# TKT-NEW-006-A: Wire Telegram Adapter To Hermes Gateway Transport

## Context

TKT-006 delivered a tested logic-layer Telegram founder adapter. It does not yet create `TelegramEvent` instances from the live Hermes Telegram gateway or deliver `TelegramSender.send()` through the Telegram Bot API.

## Proposed Scope

- Bind inbound Hermes/Telegram messages to `TelegramEvent` with sanitized runtime chat/user keys.
- Bind `TelegramSender.send()` to the reviewed Hermes Telegram gateway path.
- Preserve TKT-012 constraints: allowlist or DM pairing configured, allow-all flags disabled, polling preferred for v0.1, webhook only with `TELEGRAM_WEBHOOK_SECRET`, and no token values in git-tracked config.
- Document sanitized manual smoke-test steps without printing tokens or raw chat identifiers.

## Priority

High for first live Telegram runtime use.

## Resolution

Implemented by `TKT-015` in PR #47 and reviewed by `RV-CODE-019` in PR #48. The backlog item is consumed; live Telegram smoke testing remains a separate deployment-readiness requirement because credentials and a live Hermes Telegram gateway were unavailable during the ticket.
