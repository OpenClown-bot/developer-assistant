---
id: UPSTREAM-ADAPTER-CONTRACT
version: 0.1.0
status: draft
---

# Upstream Adapter Contract

## 1. Purpose

This document defines the v0.1 contract for the **upstream entry-point abstraction** — the boundary between whatever conversational surface the Founder uses and the `developer-assistant` Orchestrator runtime. It satisfies `PRD-001.md` § 13.3 (upstream composability: Telegram is one adapter, OpenClaw is a future adapter) and operationalizes the architectural shape defined in `ARCH-001.md` v0.3.0 § 13.

The contract is a boundary specification: it states the five operations every upstream adapter must implement, the data shape that crosses the boundary, and how identity binding and session continuity work. It does not specify the OpenClaw v0.2 implementation in detail; that is a future Architect pass.

## 2. Why An Upstream Abstraction

`PRD-001.md` § 13.3 commits the project to "swap or add an upstream entry-point" without touching specialist Hermes runtimes, Founder-facing intake logic, or the orchestrator core. Without an explicit abstraction, the Telegram-specific code paths would gradually fuse into the Orchestrator runtime's classifier, escalation surface, and progress reporter, making the OpenClaw addition a partial rewrite rather than a parallel adapter slot.

The abstraction's job is to keep the Orchestrator runtime's internal behavior independent of the upstream channel. The Orchestrator should be able to produce a "send this message to the Founder" intent, hand it to whatever adapter is registered, and let the adapter handle the channel-specific delivery, formatting, and capture.

## 3. Where The Abstraction Lives

The upstream abstraction lives **inside the Orchestrator Hermes runtime** as a Hermes skill adapter (ADR-007). It does NOT live as:

- A separate gateway process. There is exactly one Founder-facing process — the Orchestrator — and the abstraction lives inside it.
- An OpenClaw plugin. v0.1 does not run OpenClaw at all per `ARCH-001.md` § 3 and ADR-001.
- An MCP server exposed by the Orchestrator. While MCP is a candidate for v0.2+ (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.11, § 6.5), v0.1 keeps the abstraction in-process for simplicity.

Concretely the abstraction is implemented as four artifacts in the Orchestrator runtime's loadout:

- **Telegram adapter binding**: the bundled Hermes `telegram-gateway` skill, configured per `HERMES-SKILL-ALLOWLIST.md` § 4.1, plus the custom `dev-assist-classifier` and `dev-assist-escalation-surface` skills that translate between Hermes-internal events and the abstraction's five operations.
- **Adapter registry plugin**: the `dev-assist-work-queue` plugin's "outbound delivery" extension point, which lets the Orchestrator send "ask the Founder" intents without knowing which adapter will handle them.
- **Identity binding table**: `founder_identity_bindings` table in the operational store mapping `(adapter_id, upstream_user_id)` to a single internal Founder identity.
- **Session continuity table**: `upstream_sessions` table tracking per-adapter session state.

v0.1 has exactly one row in the adapter registry: `adapter_id='telegram'`. v0.2+ adds `adapter_id='openclaw'` (or `adapter_id='a2a:<peer>'` for an A2A-speaking peer) without touching the four specialist runtimes.

## 4. The Five Operations

Every upstream adapter MUST implement these five operations. The operations are listed in the contract; the implementation lives inside skills/plugins that the Orchestrator runtime loads.

### 4.1 inbound

Deliver a Founder message into the Orchestrator runtime.

Inputs (from the upstream channel into the adapter):

| Field | Type | Description |
| --- | --- | --- |
| `adapter_id` | string | identifies which adapter received the message (e.g., `telegram`) |
| `upstream_user_id` | string | the channel-native user id (e.g., Telegram user id) |
| `upstream_chat_id` | string | the channel-native chat id |
| `message_text` | string | the raw user-typed text |
| `message_id` | string | channel-native message id, used for reply correlation |
| `received_at` | string | ISO 8601 UTC |
| `reply_to_message_id` | string \| null | if the user replied to a previous bot message, its id |
| `attachments` | list | optional attachments (v0.1 ignores; reserved for future) |

Outputs (from the adapter into the Orchestrator):

The adapter resolves `upstream_user_id` against `founder_identity_bindings` (§ 5). If no binding exists, the adapter rejects the message (Telegram allowlist enforcement; OpenClaw permission check; etc.). If a binding exists, the adapter produces a normalized `inbound_message` event:

```json
{
  "adapter_id": "telegram",
  "founder_id": "<internal id>",
  "session_id": "<continuity id, see §4.5>",
  "message_text": "...",
  "message_id_upstream": "...",
  "reply_to_message_id_upstream": null,
  "received_at": "..."
}
```

The Orchestrator's `dev-assist-classifier` skill classifies the event, then writes any required `work_items` or `escalation` resolutions per the multi-Hermes coordination patterns (`MULTI-HERMES-CONTRACT.md` § 8).

### 4.2 outbound

Deliver an Orchestrator-produced message back to the Founder.

Inputs (from the Orchestrator into the adapter):

| Field | Type | Description |
| --- | --- | --- |
| `adapter_id` | string | which adapter to use (defaults to the adapter that received the originating message) |
| `founder_id` | string | internal id; the adapter resolves to the `upstream_user_id` and `upstream_chat_id` |
| `session_id` | string | for continuity |
| `message_text` | string | Russian, per `PRD-001.md` § 11 |
| `purpose` | string enum | `progress_report`, `status_response`, `decision_response`, `general_message` |
| `parent_message_id_upstream` | string \| null | if this is a follow-up to a specific Founder message, for reply threading |

Outputs:

The adapter sends the message via the channel-specific API and returns the upstream `message_id` for future reply correlation. v0.1's Telegram adapter uses the bundled `telegram-gateway` skill's send action.

Formatting rules for v0.1 (Telegram-specific, but extensible):

- Plain text + Telegram-flavored markdown (bold, italic, inline code, code blocks).
- 4096 char limit; long messages are split at paragraph boundaries.
- No image attachments in v0.1 outbound.

### 4.3 approval prompt

A specialization of `outbound` that delivers an `escalations` row (`MULTI-HERMES-CONTRACT.md` § 6.3) to the Founder and captures a yes/no/answer response.

Inputs (from the Orchestrator into the adapter):

| Field | Type | Description |
| --- | --- | --- |
| `escalation_id` | integer | foreign key into `escalations.id` |
| `adapter_id`, `founder_id`, `session_id` | as above | |
| `prompt_text` | string | full Russian-language prompt with context, options, recommended default, impact, urgency |
| `response_modes` | list | which response modes the adapter should accept: `slash_command` (`/approve`, `/deny`), `inline_buttons` (Telegram inline keyboard), `free_text` |

Outputs:

- The adapter sends the prompt via the channel.
- The adapter writes back the upstream `message_id` to `escalations.telegram_message_id` (or per-adapter equivalent column) and updates `status='surfaced'` plus `surfaced_at`.
- Subsequent inbound Founder messages are matched against surfaced escalations by the classifier; the matched response (approve / deny / free-text answer) updates the escalation row to `approved` or `denied` per § 8.2 of `MULTI-HERMES-CONTRACT.md`.

The classifier MUST pre-empt ambiguity between an inbound message that addresses a specific escalation and an inbound message that is a separate command. v0.1 disambiguates by:

1. Checking for a `/approve <id>` or `/deny <id>` slash command (highest precedence).
2. Checking for an inline-keyboard callback referencing the escalation id (Telegram-specific; second precedence).
3. Checking for a Telegram reply (`reply_to_message_id_upstream`) pointing at the surfaced prompt's `message_id`; treat the reply text as the free-text answer (third precedence).
4. Otherwise: route the message to the general classifier and DO NOT auto-resolve any escalation.

### 4.4 identity binding

Map an upstream identity (Telegram user id, OpenClaw account, A2A peer cert) to a single internal `founder_id`. v0.1 has exactly one Founder; the table supports multiple rows only because a future v0.2 may bind one Founder to multiple upstream identities (Telegram + OpenClaw + email gateway) simultaneously.

`founder_identity_bindings` table:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `created_at` | TEXT NOT NULL | |
| `founder_id` | TEXT NOT NULL | the internal Founder id; v0.1 has one value |
| `adapter_id` | TEXT NOT NULL | e.g., `telegram` |
| `upstream_user_id` | TEXT NOT NULL | channel-native user id |
| `display_name` | TEXT | Founder-readable label |
| `bound_at` | TEXT NOT NULL | when this binding was created |
| `revoked_at` | TEXT | NULL while active |
| UNIQUE (`adapter_id`, `upstream_user_id`) | | one binding per upstream identity |

The Telegram adapter binds the Founder by either:

- Reading `DEVASSIST_FOUNDER_TELEGRAM_USER_ID` from `SELF-DEPLOY.env` and inserting the binding at install time. Lowest-friction path.
- DM pairing: Founder sends `/pair <token>` to the bot with a short-lived token displayed by `verify-self.sh` after install. Higher-friction but no need to know the Telegram user id at install time. v0.1 supports both; the Founder picks one in the install summary.

The OpenClaw adapter (v0.2+) reuses the same table by inserting a row with `adapter_id='openclaw'` and `upstream_user_id=<OpenClaw account id>`. The Founder is the same internal `founder_id` row.

### 4.5 session continuity

Track per-adapter session state so that a paused-and-resumed conversation does not lose context. v0.1's notion of "session" is intentionally light because Hermes already keeps full transcripts.

`upstream_sessions` table:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `session_id` | TEXT NOT NULL UNIQUE | the abstraction-level session id (e.g., `tg-<chat_id>`) |
| `adapter_id` | TEXT NOT NULL | |
| `founder_id` | TEXT NOT NULL | |
| `upstream_chat_id` | TEXT NOT NULL | |
| `created_at` | TEXT NOT NULL | |
| `last_message_at` | TEXT NOT NULL | |
| `paused` | INTEGER NOT NULL DEFAULT 0 | for `/pause` semantics |
| `current_project_id` | INTEGER | nullable; the project this session is currently bound to (for `/new_project`, `/status`, etc.) |

Session ids are derived deterministically per adapter:

- Telegram: `tg-<chat_id>`. The chat id is stable across messages, so the session is naturally continuous.
- OpenClaw (v0.2): `oc-<workspace_id>-<conversation_id>`.
- A2A: `a2a-<peer>-<task_id>`.

The Orchestrator's classifier reads `current_project_id` from the session row to resolve free-form messages against the right project. `/new_project` updates this column atomically with the project registry insert.

`/pause` sets `paused=1`; the Orchestrator skips delivering scheduled progress reports while paused. `/resume` clears it.

## 5. Adapter Registry

The set of installed upstream adapters lives in a small in-process registry inside the Orchestrator runtime. Each registered adapter is described by:

| Field | Type | Notes |
| --- | --- | --- |
| `adapter_id` | string | e.g., `telegram` |
| `display_name` | string | Founder-readable |
| `inbound_skill` | string | which skill provides `inbound` (e.g., `telegram-gateway`) |
| `outbound_skill` | string | which skill provides `outbound` |
| `approval_prompt_skill` | string | which skill provides `approval prompt`; may be the same as `outbound_skill` |
| `formatter` | string | which formatter to use for outbound messages (Telegram markdown, plain text, etc.) |
| `enabled` | bool | |

v0.1 ships the registry pre-populated with one entry: `telegram`. The registry is not configurable through the operational store in v0.1; it is set in the Orchestrator runtime's loadout. Configurability moves to a config-file or operational table in v0.2 when OpenClaw is added.

## 6. Outbound Routing

When the Orchestrator wants to send the Founder a message, it does NOT pick an adapter. It produces an outbound intent and the registry routes it.

Routing rules for v0.1:

- If the outbound intent has an explicit `adapter_id`, the registry uses that adapter.
- Otherwise the registry routes to the adapter that produced the originating inbound message (so a reply goes back through the same channel).
- If there is no originating inbound (e.g., a scheduled progress report), the registry uses the `default_adapter_id` config value, which v0.1 sets to `telegram`.

Routing rules for v0.2+ when both Telegram and OpenClaw are enabled:

- The Founder's last-active adapter is preferred for unsolicited messages.
- The Founder may issue an explicit `/route <adapter>` command (per `PRD-001.md` § 10 Q18 future decision) to switch the default for subsequent messages.

The v0.2 routing policy is open product scope per `PRD-001.md` § 10 Q18 and is not committed in this contract.

## 7. v0.1 Telegram Adapter Specifics

The v0.1 Telegram adapter uses the bundled Hermes `telegram-gateway` skill (`HERMES-SKILL-ALLOWLIST.md` § 4.1). Specifics:

- Mode: polling (no webhook); keeps the VPS outbound-only.
- Allowlist: `TELEGRAM_ALLOWED_USERS` env var is required.
- Bot identity: one `TELEGRAM_BOT_TOKEN` from @BotFather.
- Pairing: Founder runs `verify-self.sh` after install; if a Founder Telegram user id is not provisioned in `SELF-DEPLOY.env`, the verify script outputs a one-line `/pair <token>` instruction the Founder can DM the bot.
- Inbound: the gateway hands the message to the Orchestrator session; the Orchestrator's `dev-assist-classifier` skill produces the `inbound_message` event.
- Outbound: the Orchestrator's `dev-assist-progress-report` and `dev-assist-escalation-surface` skills call the registry's outbound action.

The Telegram bot token is loaded ONLY into the Orchestrator runtime's environment (`MULTI-HERMES-CONTRACT.md` § 12). Specialist runtimes do not have access to send Telegram messages directly even though they share the same `SELF-DEPLOY.env` file.

## 8. v0.2 OpenClaw Adapter (Forward-Looking Notes Only; NOT v0.1)

The v0.1 architecture must not preclude OpenClaw. The forward-looking design that this contract preserves space for:

- The OpenClaw side runs an OpenClaw workspace that uses an OpenClaw plugin to delegate project-creation work to `developer-assistant`'s Orchestrator runtime.
- The OpenClaw plugin talks to the Orchestrator over a single endpoint. Two candidate endpoints:
  - **MCP HTTP server** exposed by the Orchestrator (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.11): trivial to implement on the Hermes side; OpenClaw treats it as an external tool source.
  - **A2A-compliant HTTP server** (`https://a2a-protocol.org/`): more general; allows non-OpenClaw peers to call in too.
- The Orchestrator's adapter registry gains `adapter_id='openclaw'` (or `adapter_id='a2a:openclaw'`); the inbound/outbound/approval skills are added to the Orchestrator's loadout. No specialist runtime is touched.
- v0.2 escalation prompts produced inside `developer-assistant` are visible in OpenClaw rather than (or in addition to) Telegram, depending on the v0.2 routing policy decision.

This is a forward-looking sketch, not a v0.1 commitment. The v0.2 Architect pass refines and finalizes it.

## 9. Adapter-Agnostic Behavior

These behaviors are independent of which adapter is active and remain identical when v0.2 adds OpenClaw:

- All Founder-facing outbound text is in Russian (`PRD-001.md` § 11).
- Decision capture: free-form Founder responses that contain durable decisions are normalized to English and written to repository artifacts (`HERMES-RUNTIME-CONTRACT.md` § 8 Decision Capture).
- Escalation-policy enforcement runs on every specialist runtime regardless of adapter (`ESCALATION-POLICY.md`).
- The 30-60 minute progress-report cron lives on the Orchestrator and produces outbound messages through the registry (`MULTI-HERMES-CONTRACT.md` § 5.1).

## 10. Failure Modes

| Failure | Detection | Recovery |
| --- | --- | --- |
| Telegram API unreachable | Outbound returns network error | Retry with exponential backoff up to 5 minutes; if still failing, log and surface a state-store flag `outbound_degraded` that `/status` includes |
| Founder identity binding missing | Inbound message has no matching row in `founder_identity_bindings` | Reject inbound message; bot does not respond (allowlist semantics); log the rejected upstream id |
| Multiple inbound messages addressing the same surfaced escalation | The classifier resolves the first one; subsequent messages with the same matching pattern get a Russian response "this escalation was already resolved" | |
| Session row missing for a known Founder | Inbound creates the session row on first message | |
| Outbound message exceeds Telegram size limit | Adapter splits at paragraph boundaries; if a single paragraph exceeds the limit, splits at sentence boundaries | |
| Adapter registry has zero enabled adapters | Orchestrator startup detects this and exits with non-zero status; the install script's verify step fails | |
| Two adapters both claim the same inbound channel | Cannot happen in v0.1 (only one adapter exists); v0.2's registry enforces unique `(adapter_id)` and a separate routing key per channel | |

## 11. Cross-References

- `PRD-001.md` v0.2.1 § 13.3 (upstream composability mandate)
- `PRD-001.md` v0.2.1 § 10 Q18 (open: simultaneous vs switchable adapters in v0.2+)
- `ARCH-001.md` v0.3.0 § 13
- `MULTI-HERMES-CONTRACT.md` § 5.1, § 6.3, § 8.2 (Orchestrator skills, escalations table, escalation flow)
- `HERMES-SKILL-ALLOWLIST.md` v0.1.0 § 4.1 (Telegram gateway allowlist entry)
- `OPERATIONAL-STATE-STORE.md` v0.2.0 (table location)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.7, § 3.11, § 4, § 6.5
- `docs/architecture/adr/ADR-007-upstream-adapter-shape.md`
- Implementation: TKT-024 (upstream-adapter scaffolding)
