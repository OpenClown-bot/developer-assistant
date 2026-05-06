---
id: ESCALATION-POLICY
version: 0.1.1
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

For every tool call a specialist runtime is about to make, the plugin walks this tree. Every step is **deterministic**: the entire decision is a pure function of the candidate action, the structured concept anchor (`PROJECT-CONCEPT.md`), and this file's § 4 rule set. There is **no LLM call inside the decision path** (RV-SPEC-012 F3 fix; ADR-008 v0.1.1).

```
A. Read-only or trivially-safe tool call?
   (read_file, list_files, session_search, memory tool actions
   add/replace/remove on this runtime's own MEMORY.md, etc.)
   ─► PROCEED, no further checks
   │ (action is not read-only)
   ▼
B. Match against the deterministic rule set (§ 4)?
   ─► ESCALATE with trigger_kind=deterministic_rule:<id>
   │ (no deterministic rule matched)
   ▼
C. Within-catalog model pick? (§ 6 of MODEL-CATALOG.md)
   ─► PROCEED
   │ (action is not within-catalog and not read-only)
   ▼
D. Deterministic concept-deviation classifier (§ 5)
   Compares the candidate action against PROJECT-CONCEPT.md § 2
   using a fully-specified pure-function predicate set (§ 5.1).
   ─► ESCALATE with trigger_kind=concept_deviation:<rule_id>
   ─► PROCEED
```

**Fail-closed defaults**:

- If the deterministic rule engine errors (parser failure, malformed `PROJECT-CONCEPT.md`, file unreadable), the plugin escalates rather than proceeds with `trigger_kind='classifier_error'`.
- If the action passes all four steps (read-only, no § 4 rule, within-catalog, no concept-deviation rule) but the action is in a category the deterministic rules cover (state-modifying, credential-touching, network-touching, repository-write) AND a structural defect prevents § 4 from being evaluated, the plugin treats step B as not-yet-decided and escalates with `trigger_kind='rule_engine_unavailable'`.

The rationale: an unenforceable policy is worse than slow. Both fail-closed paths are reachable only on engineering bugs (the rule engine cannot legitimately be unavailable in production); they exist so that misconfiguration cannot silently degrade enforcement to fail-open.

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
| `state:drop_table` | SQL `DROP TABLE` against `operational.db` | Schema-destructive |
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

## 5. Deterministic Concept-Deviation Classifier

When no deterministic rule from § 4 matches and the action is not trivially read-only or within-catalog, the plugin runs the concept-deviation classifier. The classifier is a **pure function** — same inputs always yield the same verdict — with **no LLM call inside the decision path** (RV-SPEC-012 F3 fix; ADR-008 v0.1.1).

### 5.1 Algorithm

The algorithm is the one specified in `PROJECT-CONCEPT.md` v0.1.0 § 3, repeated here for completeness:

```python
def classify_concept_deviation(action: CandidateAction, anchor: ConceptAnchor) -> Verdict:
    """
    Pure function. No I/O. No LLM. No randomness.
    Postcondition: same (action, anchor) ALWAYS yields the same Verdict.
    """
    for rule in anchor.deviation_rules:
        if matches(action, rule.match):
            if rule.verdict == "ESCALATE":
                return Verdict.ESCALATE(rule_id=rule.id, cite=rule.cite)
            elif rule.verdict == "PROCEED_OR_RULE_4_DECIDES":
                if any_section_4_rule_matches(action):
                    return Verdict.ESCALATE(rule_id="<§ 4 match>", cite="§ 4")
                return Verdict.PROCEED
            else:
                return Verdict.PROCEED
    return Verdict.ESCALATE(rule_id="classifier_safety_default", cite="§ 5 fail-closed")
```

The `matches(action, rule.match)` predicate is composed exclusively from Python primitives — string equality, regex (`re.search`), Unix glob (`fnmatch.fnmatch`), and list membership. The full predicate language is enumerated in `PROJECT-CONCEPT.md` § 3 (`kind`, `path_glob`, `argument_keyword_set`, `argument_regex`, `content_regex`, `content_diff_touches`).

Every `deviation_rules` entry that fires comes with a stable `id` and a back-reference (`cite`) to the deterministic-rule line in § 4 or to the concept clause in `PROJECT-CONCEPT.md` § 2. Both go into the `escalations.trigger_kind` column as `concept_deviation:<rule_id>` so audits in § 8 can group by rule.

### 5.2 Concept anchor location

The anchor block consumed by the classifier is the YAML in `PROJECT-CONCEPT.md` § 2 — file path: **`docs/architecture/PROJECT-CONCEPT.md`** in the developer-assistant repository (RV-SPEC-012 F4 fix). The plugin loads the file at startup with these guarantees:

- The file MUST exist and parse as valid YAML; otherwise the plugin fails to start (systemd `ExecStart` exits non-zero, `Restart=on-failure` retries but the runtime never reaches `agent run`). This prevents a missing/corrupted anchor from silently degrading enforcement.
- The `version` field in the file's frontmatter MUST match a hard-coded minimum version in the plugin source. Mismatch is a fatal-startup error. Bumping the file version triggers a coordinated plugin update.
- The plugin re-reads the file on `SIGHUP` so that an in-place anchor update can roll out without a full systemd restart of every runtime.

The anchor file is itself protected by a deterministic rule — `concept:edit_concept_anchor` in § 4.10 — so the file cannot be modified by any specialist runtime without escalation.

### 5.3 Performance bounds

Because the classifier is pure-Python with no I/O, the bounds are tight:

- Hard wall-clock timeout: 100 ms per classification (vs the prior 10 s LLM budget). The previous “hard cost ceiling per classification: <0.001 USD” clause is obsolete — the deterministic classifier has zero per-call cost.
- Cache: identical `(action_kind, action_args_hash)` within a 5-minute window reuses the previous verdict (within the same runtime; not shared across runtimes). The cache exists to avoid re-walking the rule list for repeated identical Hermes tool calls; correctness does not depend on it.
- The previous ADDENDUM-001 reference to a 10-second auxiliary-classifier latency budget in `MODEL-CATALOG.md` § 5.3 is preserved as the bound for the **advisory narrative call** in § 5.5 below — NOT for the escalate/proceed decision.

### 5.4 Argument scope and redaction

The classifier receives a redacted version of the candidate action's arguments. Specifically: paths and tool names are passed through verbatim; secret-like values are replaced with `<REDACTED>`; LLM API keys are never read into the classifier's input. The redaction list is the same as the deterministic `secret:*` rule set in § 4.4.

Redaction is part of `matches(action, rule.match)`'s contract (the predicate operates on the redacted argument string only) so that adding a new secret-detection regex to § 4.4 also strengthens the concept-deviation classifier's input hygiene. TKT-023 § 1 covers this with a unit test that asserts no environment-variable value listed in `SELF-DEPLOY.env`'s required set ever appears in the classifier's input string.

### 5.5 Optional advisory narrative (NOT in the decision path)

When § 5.1 returns `ESCALATE`, the plugin MAY invoke the runtime's catalog main model (`MODEL-CATALOG.md` § 4.1) to generate a short Russian-language narrative for the Founder explaining what was about to happen and why the deterministic classifier matched. This narrative is **advisory text on the escalation surface only**; it has no effect on the verdict, and the deterministic classifier never waits on it.

Bounds for the advisory call:

- Hard wall-clock timeout: 10 seconds (matches the legacy `MODEL-CATALOG.md` § 5.3 budget).
- Hard cost ceiling: <0.001 USD per call (same as legacy).
- If the call times out or fails, the plugin attaches a fallback English-language narrative built deterministically from `rule_id` + `cite` and proceeds with the escalation. The fallback path is the default; the LLM call is best-effort.
- The advisory call uses the runtime's own catalog main model; no separate "auxiliary classifier" model entry is required (`MODEL-CATALOG.md` v0.1.1 § 4.2).

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
- Adding, removing, or modifying any line of the structured anchor in `PROJECT-CONCEPT.md` § 2 is itself caught by the deterministic rule `concept:edit_concept_anchor` (§ 4.10). It cannot land without Founder approval.
- Changing the deterministic classifier algorithm in § 5.1 (e.g., adding a new predicate type to the `match` schema) requires the same Architect → RV-SPEC → Founder loop.
- Changing the advisory-narrative call in § 5.5 (model, prompt, latency / cost bound, opt-out) does NOT require Founder approval because it does not affect the escalate/proceed decision; the Architect documents the change in this file's frontmatter version and ships. The advisory call is functionally optional.
- Changing the wall-clock timeout for the deterministic classifier (§ 5.3) or the cache window does NOT require Founder approval; same path.

## 10. Failure Modes

| Failure | Detection | Recovery |
| --- | --- | --- |
| Plugin crashes inside the hook | Hermes `pre_tool_call` raises | The runtime treats this as fail-closed (ESCALATE) and writes an escalation with `trigger_kind='plugin_crash'`; restarts via systemd `Restart=on-failure` |
| `PROJECT-CONCEPT.md` missing or malformed at startup | Plugin's YAML parser raises in `ExecStart` | systemd marks the unit `failed`; install verify catches before the start gate (`SELF-DEPLOYMENT-CONTRACT.md` § 8). At runtime: fail-closed escalate with `trigger_kind='classifier_error'` until restored |
| Concept-anchor version mismatch | Plugin's startup version-check raises | Same as above |
| Deterministic rule engine raises during `matches()` | Plugin's exception handler catches | Fail-closed: escalate with `trigger_kind='rule_engine_unavailable'` and log the rule id that raised; aggregate audit query in § 8 surfaces a recurring failure |
| Advisory narrative call (§ 5.5) times out or fails | LLM call exceeds 10 s | Drop the LLM narrative; attach the deterministic English fallback narrative built from `rule_id` + `cite`. The escalation is unaffected |
| Deterministic rule false positive | Founder sees an escalation that should not have triggered | Founder approves it; tunes the rule via the § 9 process |
| Deterministic rule false negative | A scope-changing action proceeds without escalation | This is the worst-case failure mode; mitigated by (a) the structured concept anchor catching concept-level deviations the § 4 list misses, (b) the Hermes approval prompt as a second layer (still active in `manual` mode), and (c) the audit query in § 8 reviewed regularly |
| Escalation surfaces to Founder but Founder is offline | Escalation stays `surfaced`; the 7-day expiration sweep eventually marks it `expired` and re-escalates | |

## 11. Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy/escalation rule)
- `ARCH-001.md` v0.3.0 § 15
- `PROJECT-CONCEPT.md` v0.1.0 (structured anchor consumed by § 5)
- `MULTI-HERMES-CONTRACT.md` § 5.6, § 6.3, § 8.2
- `UPSTREAM-ADAPTER-CONTRACT.md` § 4.3
- `MODEL-CATALOG.md` v0.1.1 § 4.1 (catalog main models, used for advisory narrative in § 5.5), § 4.2 (no separate auxiliary classifier in v0.1)
- `HERMES-RUNTIME-CONTRACT.md` v0.2.0 § 5 founder_questions sub-fields
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.8, § 3.9, § 6.4
- `docs/architecture/adr/ADR-008-escalation-classifier.md` v0.1.1 (deterministic + structured anchor)
- Implementation: TKT-023 (escalation policy enforcement plugin)
