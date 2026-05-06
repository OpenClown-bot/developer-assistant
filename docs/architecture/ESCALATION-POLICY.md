---
id: ESCALATION-POLICY
version: 0.1.0
status: draft
---

# Escalation Policy

## 1. Purpose

This document operationalizes the autonomy/escalation rule defined in `PRD-001.md` § 13.1:

> The assistant escalates to the Founder only when a candidate decision either (a) **strongly deviates from the original concept** captured at intake, or (b) **risks breaking already-committed scope or operational state**. All other engineering decisions proceed autonomously.

The PRD intentionally does not commit to a classifier mechanism; it requires the Architect to produce this artifact. This document is that artifact. It states the deterministic rule set, the LLM-classifier contract, where the enforcement runs, and how the Founder's response is captured. Implementation lives in TKT-023.

## 2. Where This Policy Runs

The policy runs as a Hermes plugin (`dev-assist-escalation-policy`) loaded into **every** specialist runtime, not just the Orchestrator. The plugin registers a Hermes `pre_tool_call` hook (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.8) that intercepts tool calls before they execute.

This placement matters:

- The hook fires inside the runtime that wants to take the action, so the action is blocked at its source.
- The hook fires before Hermes' own approval prompt (per `HERMES-SKILL-ALLOWLIST.md` § 3 the runtimes use `approvals.mode: manual`), so the project's policy is the **first** safety net and Hermes' approval prompt remains as a **second** safety net.
- The hook does not depend on the Orchestrator being available; even if the Orchestrator is restarting, a specialist runtime can still pause itself and write an `escalation` row.

## 3. Decision Tree

For every tool call a specialist runtime is about to make, the plugin walks this tree:

```
┌─────────────────────────────────────────────────────────────────────┐
│ A. Read-only or trivially-safe tool call?                           │
│    (read_file, list_files, session_search, memory tool actions      │
│    add/replace/remove on this runtime's own MEMORY.md, etc.)        │
│  ────────────► PROCEED, no further checks                           │
└──────────┬──────────────────────────────────────────────────────────┘
           ▼ (action is not read-only)
┌─────────────────────────────────────────────────────────────────────┐
│ B. Match against the deterministic rule set (§ 4)?                  │
│  ────────────► ESCALATE with trigger_kind=deterministic_rule:<id>   │
└──────────┬──────────────────────────────────────────────────────────┘
           ▼ (no deterministic rule matched)
┌─────────────────────────────────────────────────────────────────────┐
│ C. Within-catalog model pick? (§ 6 of MODEL-CATALOG.md)              │
│  ────────────► PROCEED, no LLM consultation                         │
└──────────┬──────────────────────────────────────────────────────────┘
           ▼ (action might affect scope)
┌─────────────────────────────────────────────────────────────────────┐
│ D. Run the LLM classifier (§ 5)                                     │
│   verdict = ASK_FOUNDER | PROCEED                                   │
└──────────┬──────────────────────────────────────────────────────────┘
           ▼
        if ASK_FOUNDER → ESCALATE with trigger_kind=llm_classifier
        if PROCEED     → PROCEED
```

**Fail-closed default**: if the deterministic rule engine errors, OR the LLM classifier is unreachable AND the action is in a category the deterministic rules cover (state-modifying, credential-touching, network-touching, repository-write), the plugin escalates rather than proceeds. The rationale: an unenforceable policy is worse than slow.

## 4. Deterministic Rule Set

These rules MUST escalate without LLM consultation. The rule id format is `<category>:<short-name>` so that escalations can be grouped and audited.

### 4.1 Repository governance (`gov:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `gov:write_outside_zone` | Any file write to a path outside the current ticket's `allowed_files` (per `CONTRIBUTING.md`) | The role's write zone is the contract; zone violation requires Founder decision |
| `gov:delete_governance_artifact` | Deletion of any file under `docs/prd/`, `docs/architecture/`, `docs/architecture/adr/`, `docs/tickets/`, `docs/questions/`, `docs/reviews/`, `docs/orchestration/` | Governance artifacts are durable engineering history |
| `gov:overwrite_approved_artifact` | Modification of an artifact whose `status: approved` frontmatter is not changed in the same edit, when the modification adds/removes content rather than fixes typos | Approved artifacts are committed scope; edits should be "draft" of a new version, not silent overwrite |
| `gov:rename_artifact` | Rename or move of any artifact under `docs/` | Cross-references break silently; rename requires Founder ack |

### 4.2 Git operations (`git:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `git:force_push` | `git push --force` or `git push -f` (any branch) | Destroys committed history |
| `git:force_with_lease_main_master` | `git push --force-with-lease` against `main` or `master` | Even with lease, main/master force-push is out of scope |
| `git:hard_reset` | `git reset --hard <ref>` | Destroys local committed history |
| `git:branch_delete` | `git branch -D <ref>` or remote branch delete | Could remove an in-flight PR's branch |
| `git:rebase_main_master` | Rebase against an already-pushed `main` or `master` | Rewrites shared history |
| `git:no_verify_commit_or_push` | `--no-verify` flag on commit or push | Skips pre-commit/pre-push hooks, including secret scans |

### 4.3 State store and persistence (`state:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `state:drop_table` | SQL `DROP TABLE` against `state.db` | Schema-destructive |
| `state:drop_database` | SQL `DROP DATABASE` against any database | Schema-destructive |
| `state:truncate_or_delete_unbounded` | `DELETE FROM <table>` without a `WHERE` clause OR `TRUNCATE` | Wipes operational data |
| `state:alter_table_drop_column` | SQL `ALTER TABLE ... DROP COLUMN` | Loses operational data |
| `state:downgrade_schema` | Migration that targets a schema version lower than current | Backward migrations are out of scope in v0.1 |

### 4.4 Credentials and secrets (`secret:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `secret:rotate` | Any tool call that updates `SELF-DEPLOY.env` or any env-var with names matching `*TOKEN*`, `*KEY*`, `*PASSWORD*`, `*SECRET*` | Credential rotation is a Founder action |
| `secret:revoke` | API call to revoke a token (Telegram `revokeBotToken`, GitHub `delete-pat`, etc.) | Same |
| `secret:write_to_repo` | File write whose content matches a secret-like pattern (regexes for known token shapes) into a tracked repo file | Prevents `.env` leakage; matches CI's pre-commit secret scan |
| `secret:expose_in_log` | Tool call producing output that contains a known secret env-var value | Prevents leak via journalctl |

### 4.5 Network exposure (`net:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `net:open_inbound_port` | Any operation that opens an inbound TCP/UDP port on the VPS (ufw allow, systemd socket, etc.) | Public exposure is out of v0.1 scope |
| `net:webhook_mode_telegram` | Switching Telegram gateway from polling to webhook | Same; default is polling per `HERMES-SKILL-ALLOWLIST.md` § 4.1 |
| `net:expose_endpoint` | `ngrok`, Cloudflare Tunnel, reverse-proxy config that publicly exposes a local service | Same |

### 4.6 Paid third-party introduction (`paid:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `paid:new_recurring_service` | Configuration change that introduces a paid third-party as a hard dependency: Modal, Daytona, Vercel sandbox, hosted Postgres / Qdrant / Pinecone / Weaviate / Letta, managed Redis, etc. | v0.1 budget envelope is one VPS + already-approved LLM API spend |
| `paid:llm_provider_outside_catalog` | LLM API call to a provider not in `MODEL-CATALOG.md` | Catalog is the Founder-pre-approved set |
| `paid:cloud_resource_provision` | Provisioning a paid cloud resource (EC2, GCE, Lambda, etc.) | Out of v0.1 scope |

### 4.7 Deployment and approval gates (`deploy:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `deploy:start_units_unprompted` | `systemctl start devassist.target` from inside any specialist runtime | The `start` gate per `PRD-001.md` § 12.5 is Founder-driven; specialist runtimes never auto-start |
| `deploy:upgrade_activate_unprompted` | `upgrade-self.sh --activate` from inside any specialist runtime | The `upgrade` gate is Founder-driven |
| `deploy:generated_project_live_run` | Final live run of a generated project's deploy entry point on a Founder-targeted host | `GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` requires Founder approval before live execution |
| `deploy:merge_pr` | API call that merges a PR | Founder ack is required for v0.1 (`ARCH-001.md` § 9 step 8) |

### 4.8 Plugin and skill changes (`plugin:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `plugin:install_unallowed` | Installation of a Hermes skill or plugin not in `HERMES-SKILL-ALLOWLIST.md` § 4 | Allowlist is the trust surface |
| `plugin:enable_project_local` | Setting `HERMES_ENABLE_PROJECT_PLUGINS=true` | Disabled by ADR-003 in v0.1 |
| `plugin:enable_marketplace_autoinstall` | Setting Hermes config that enables hub auto-install | Disabled by ADR-003 |
| `plugin:agent_managed_skill_create` | Use of `skill_manage` tool to create or modify a runtime skill | Disabled in v0.1 production per `MULTI-HERMES-CONTRACT.md` § 4 |

### 4.9 PRD/ADR/architecture changes (`scope:*`)

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `scope:prd_status_to_approved` | Any edit that flips a PRD frontmatter from `draft` to `approved` | Founder-only |
| `scope:adr_status_to_approved` | Any edit that flips an ADR frontmatter from `draft` to `approved` or `proposed` to `accepted` | Founder-only |
| `scope:add_v01_commitment` | Any edit that adds a new bullet under `PRD-001.md` § 12 (v0.1 in-scope), § 13 (autonomy/team/upstream), or § 7 (NFR) | Founder-only scope decision |

### 4.10 Concept-level red flags (`concept:*`)

These rules catch the obvious shape of "I am about to redefine the project." They overlap with the LLM classifier in § 5 but exist as deterministic backstops so the LLM is not single-pointed.

| Rule id | Trigger condition | Why escalate |
| --- | --- | --- |
| `concept:replace_target_user` | Edit to PRD § 2 (Vision) or § 3 (Goals) | Concept-level |
| `concept:replace_tech_stack` | Edit that switches the project off Hermes Agent or off Telegram | Concept-level |
| `concept:replace_runtime_target` | Edit that switches the deployment target from VPS to anything else | Concept-level |
| `concept:expose_private_endpoint` | Same as `net:expose_endpoint`; included here to be visible in concept-review escalations | Concept-level |

The deterministic rule set is exhaustive for `pre_tool_call` interception: any tool call matching a rule above MUST escalate, regardless of LLM verdict. The LLM is not consulted on these.

## 5. LLM Classifier

When no deterministic rule matches but the action is not trivially read-only, the plugin asks an auxiliary LLM whether the action triggers either limb of the PRD § 13.1 rule.

### 5.1 Classifier prompt (English; immutable to LLM)

The classifier prompt is hard-coded in the plugin source (not editable by any runtime's MEMORY.md). It looks like:

```
You are an escalation classifier for the developer-assistant project.

You receive:
1. The PRD's intake-time concept summary (a static block of text).
2. The PRD § 12 (v0.1 commitments) as a static block.
3. The PRD § 13 (autonomy/team/upstream) as a static block.
4. The current candidate action: tool name, tool arguments, and a short
   plain-English description of what the action will do.

Classify the candidate action against this rule:

  Escalate to the Founder if and only if the candidate action:
   (a) deviates from the concept, target user, success criteria, or
       constraints captured in the intake / PRD § 12 / PRD § 13;
   OR
   (b) risks breaking already-committed scope, durable engineering state,
       or external commitments (force-push, schema-destructive ops,
       credential rotation, public endpoint exposure, paid third-party
       introduction, etc.).

You return EXACTLY one line of JSON:
  {"verdict":"ASK_FOUNDER","reason":"<one sentence>"}
or
  {"verdict":"PROCEED","reason":"<one sentence>"}

You do NOT add any other text. You do NOT execute the candidate action.
You do NOT have access to tools. You only classify.
```

The plugin parses the JSON, and treats anything other than a parseable response or any other verdict value as ASK_FOUNDER (fail-closed).

### 5.2 Classifier model

Per `MODEL-CATALOG.md` § 6 the classifier model is one of the Founder-pre-approved entries explicitly tagged `auxiliary_classifier`. v0.1 default: `gpt-5.1-mini` via OmniRoute (independent of any specialist runtime's primary model so the audit is independent). The classifier model can be overridden per runtime in config, but only to another `auxiliary_classifier`-tagged entry.

### 5.3 Classifier latency budget

- Hard timeout: 10 seconds. On timeout: fail-closed (ASK_FOUNDER).
- Hard cost ceiling per classification: <0.001 USD (per `MODEL-CATALOG.md` § 4 estimate).
- Cache: identical (action_kind, action_args_hash) within a 5-minute window reuses the previous verdict (within the same runtime; not shared across runtimes).

### 5.4 Classifier inputs scope

The classifier receives a redacted version of the candidate action's arguments. Specifically: paths and tool names are passed through verbatim; secret-like values are replaced with `<REDACTED>`; LLM API keys are never sent. The redaction list is the same as the deterministic `secret:*` rule set.

## 6. Escalation Lifecycle

When the plugin decides to escalate (deterministic rule match OR LLM verdict ASK_FOUNDER), it:

1. Inserts a row into `escalations` (`MULTI-HERMES-CONTRACT.md` § 6.3) with:
   - `originating_runtime` = the calling runtime's `HERMES_DEVASSIST_ROLE`.
   - `originating_work_item_id` = the current work item if any.
   - `trigger_kind` = `deterministic_rule:<rule_id>` or `llm_classifier`.
   - `context` = a one-paragraph plain-English description of the situation.
   - `proposed_action` = the tool name plus a one-sentence summary of what was about to happen.
   - `options_json` = the response options the runtime expects ("approve", "deny", or freeform answers depending on the rule).
   - `recommended_default` = what the runtime would have done if no escalation existed (per `HERMES-RUNTIME-CONTRACT.md` § 5 founder_questions sub-fields).
   - `impact` = what is affected.
   - `urgency` = `low`, `medium`, or `high`.
   - `durable_artifact_target` = where the decision will be recorded (PRD, `docs/questions/`, ADR, or ticket path).
2. Returns a "blocked" response to the Hermes tool-call dispatcher; the runtime sees the tool call refused with a structured reason.
3. The runtime's role-prompt instructs it to: (a) `release` the current work item back to `pending` (so it doesn't time out the lease), and (b) write a short note in its own session memory recording the escalation id it is waiting on.
4. The runtime exits the work-item iteration. Its cron poller picks up another item or sleeps.
5. The Orchestrator's `dev-assist-escalation-surface` skill polls `escalations` for `status='pending'` and surfaces them to the Founder per `UPSTREAM-ADAPTER-CONTRACT.md` § 4.3.
6. The Founder responds. The Orchestrator updates `escalations.status` to `approved` or `denied`, writes the Founder's English-normalized decision note into the `durable_artifact_target`, and writes a follow-up `work_item` re-dispatching the originating work to the originating runtime with `payload_json.previous_escalation_id` set.
7. The originating runtime reclaims the work item, sees the previous escalation was approved, and proceeds (or sees it was denied and writes a `blocker` artifact instead).

## 7. Founder Approval Surface

The Founder sees escalations in Telegram per `UPSTREAM-ADAPTER-CONTRACT.md` § 4.3. v0.1 supports three response modes:

- `/approve <id>` — approves the escalation.
- `/deny <id>` — denies it.
- Free-text reply to the escalation message — captured as a free-form answer; the Orchestrator's classifier extracts a yes/no decision plus a normalized rationale.

For high-urgency escalations the Orchestrator may additionally use a Telegram inline keyboard with "Approve" / "Deny" / "Other" buttons; this is a UI affordance, not a separate response mode.

The escalation surface MUST include in every prompt:

- The originating runtime (so the Founder knows which role asked).
- The proposed action.
- The trigger kind (deterministic rule id or LLM classifier).
- The recommended default.
- The impact statement.
- The urgency.
- The escalation id (so the Founder can use `/approve <id>` precisely).

Russian wording is the responsibility of `dev-assist-escalation-surface`; the underlying record is English to keep the durable artifact trail consistent with the rest of `docs/`.

## 8. Auditability

Every escalation row is durable. Every resolved escalation produces:

- An updated `escalations` row with `founder_response` and timestamps.
- A repository artifact at `durable_artifact_target` recording the decision in English (per `HERMES-RUNTIME-CONTRACT.md` § 8 Decision Capture).
- A follow-up `work_items` row re-dispatching the originating work.

Aggregate audit queries (read-only):

- `SELECT trigger_kind, COUNT(*) FROM escalations GROUP BY trigger_kind` — frequency by rule.
- `SELECT originating_runtime, AVG(julianday(resolved_at) - julianday(created_at)) FROM escalations WHERE status IN ('approved','denied') GROUP BY originating_runtime` — average resolution latency by runtime.
- `SELECT * FROM escalations WHERE status='expired'` — escalations the Founder did not respond to within 7 days.

These queries inform whether the policy is too noisy (too many escalations), too quiet (the Founder is being surprised by un-escalated changes), or imbalanced (one runtime escalates 10× more than the others).

## 9. Tuning Process

Tuning is itself a Founder-approved decision. To change a rule:

- Adding a new deterministic rule, removing one, or weakening one all require Founder approval — they are governance changes to `ESCALATION-POLICY.md`. The change goes through the normal Architect → RV-SPEC → Founder loop.
- Changing the LLM classifier's prompt requires the same loop.
- Changing which model is used as the auxiliary classifier requires Founder approval per `MODEL-CATALOG.md` § 7 (catalog change escalates).
- Changing the latency budget or cache window does NOT require Founder approval; the Architect documents the change in this file's frontmatter version and ships.

## 10. Failure Modes

| Failure | Detection | Recovery |
| --- | --- | --- |
| Plugin crashes inside the hook | Hermes `pre_tool_call` raises | The runtime treats this as fail-closed (ESCALATE) and writes an escalation with `trigger_kind='plugin_crash'`; restarts via systemd `Restart=on-failure` |
| LLM classifier unreachable | Network timeout on the classifier call | Fail-closed: escalate with `trigger_kind='llm_classifier_unreachable'` |
| Classifier returns malformed JSON | Plugin's parser raises | Fail-closed: escalate with `trigger_kind='llm_classifier_malformed'` |
| Deterministic rule false positive | Founder sees an escalation that should not have triggered | Founder approves it; tunes the rule via the § 9 process |
| Deterministic rule false negative | A scope-changing action proceeds without escalation | This is the worst-case failure mode; mitigated by (a) the LLM classifier as a second layer, (b) the Hermes approval prompt as a third layer (still active in `manual` mode), and (c) the audit query in § 8 reviewed regularly |
| Escalation surfaces to Founder but Founder is offline | Escalation stays `surfaced`; the 7-day expiration sweep eventually marks it `expired` and re-escalates | |

## 11. Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy/escalation rule)
- `ARCH-001.md` v0.3.0 § 15
- `MULTI-HERMES-CONTRACT.md` § 5.6, § 6.3, § 8.2
- `UPSTREAM-ADAPTER-CONTRACT.md` § 4.3
- `MODEL-CATALOG.md` § 6 (auxiliary classifier model)
- `HERMES-RUNTIME-CONTRACT.md` v0.2.0 § 5 founder_questions sub-fields
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.8, § 3.9, § 6.4
- `docs/architecture/adr/ADR-008-escalation-classifier.md`
- Implementation: TKT-023 (escalation policy enforcement plugin)
