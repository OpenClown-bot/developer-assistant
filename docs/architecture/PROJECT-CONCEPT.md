---
id: PROJECT-CONCEPT
version: 0.1.0
status: draft
---

# Project Concept Anchor (structured)

## 1. Purpose

This artifact pins the durable concept anchor for the developer-assistant project as a structured (YAML) block. It is the deterministic comparison surface used by `ESCALATION-POLICY.md` § 5 to detect concept-level deviation without delegating the decision to an opaque LLM call. Per the Reviewer's RV-SPEC-012 F3 finding, the escalation classifier must be deterministic-or-fully-specified; this artifact is the "fully-specified" half — every limb of the comparison maps back to a clause in `PRD-001.md`, an ADR, or another contract artifact.

The artifact lives in `docs/architecture/` (the Architect's write zone) rather than `docs/orchestration/` because the concept anchor is part of the durable design surface, not a "current-session" working note. `SESSION-STATE.md` records the project's *operational* state at a point in time; this file records the *durable* concept the assistant must not silently drift from.

Adding, removing, or modifying any line of the YAML block below requires the standard Architect → RV-SPEC → Founder loop, the same as any other contract artifact (`ESCALATION-POLICY.md` § 9). Edits are caught by the deterministic rule `concept:edit_concept_anchor` in `ESCALATION-POLICY.md` § 4.10 (added by the F3 fix in this same PR).

## 2. Concept Anchor Block

```yaml
# Authoritative project-concept anchor. Loaded verbatim by
# dev-assist-escalation-policy at startup; the YAML below is the only
# input to the deterministic concept-deviation classifier.
#
# Every entry MUST cite the clause in PRD-001.md / an ADR / another
# contract artifact that introduces it. If a clause moves, this file
# moves with it.

project_identity:
  name: developer-assistant
  target_user: technical_founder_solo                      # PRD-001 § 2 (Vision)
  primary_interface: Telegram                              # PRD-001 § 6
  secondary_interface: lightweight_web_status_dashboard    # PRD-001 § 6
  deployment_target: single_vps_owned_by_founder           # PRD-001 § 12

in_scope_v0_1:
  - id: install_in_15_min
    citation: "PRD-001 § 12.1"
  - id: self_deployment_via_founder_action
    citation: "PRD-001 § 12.2, ADR-004"
  - id: high_autonomy_default
    citation: "PRD-001 § 13.1"
  - id: telegram_to_pr_trial
    citation: "PRD-001 § 13.2, TKT-011"
  - id: multi_hermes_runtime_topology
    citation: "PRD-001 § 13.3, ADR-005, MULTI-HERMES-CONTRACT.md"
  - id: upstream_composability_for_openclaw
    citation: "PRD-001 § 13.3, UPSTREAM-ADAPTER-CONTRACT.md, ADR-007"
  - id: founder_pre_approved_model_catalog
    citation: "PRD-001 § 13.1, MODEL-CATALOG.md, ADR-009"
  - id: deterministic_escalation_policy
    citation: "PRD-001 § 13.1, ESCALATION-POLICY.md, ADR-008"
  - id: centralized_observability_per_runtime
    citation: "PRD-001 § 12, OBSERVABILITY-CONTRACT.md, ADR-010"

budget_constraints:
  - id: single_ubuntu_vps_founder_owned
    citation: "PRD-001 § 12, RESEARCH-001 § 5.2"
  - id: already_approved_llm_api_spend
    citation: "PRD-001 § 12 (budget envelope), MODEL-CATALOG.md § 8"
  - id: no_paid_third_party_recurring_services_unless_approved
    citation: "ESCALATION-POLICY.md § 4.6 (paid:new_recurring_service)"
  - id: no_managed_vector_store_in_v0_1
    citation: "ARCH-001 § 21, MODEL-CATALOG.md § 2"

tech_anchors:
  - id: hermes_agent_runtime
    citation: "ARCH-001 § 11, ADR-005"
  - id: openclaw_skills_ecosystem
    citation: "RESEARCH-001 § 4"
  - id: omniroute_routing_primary
    citation: "ADR-011, MODEL-CATALOG.md § 5"
  - id: openrouter_routing_backup
    citation: "ADR-011, MODEL-CATALOG.md § 5"
  - id: telegram_bot_polling_mode
    citation: "HERMES-SKILL-ALLOWLIST.md § 4.1, ESCALATION-POLICY.md § 4.5 (net:webhook_mode_telegram)"
  - id: sqlite_state_store
    citation: "OPERATIONAL-STATE-STORE.md, ADR-002"
  - id: linux_vps_systemd
    citation: "ADR-005, SELF-DEPLOYMENT-CONTRACT.md § 5"
  - id: github_actions_ci_validate_docs_and_pr_agent
    citation: "ARCH-001 § 17"

risk_boundaries:
  - id: no_public_inbound_network_exposure
    citation: "ESCALATION-POLICY.md § 4.5 (net:open_inbound_port, net:expose_endpoint)"
  - id: no_auto_deploy_without_founder_start_gate
    citation: "PRD-001 § 12.5, ESCALATION-POLICY.md § 4.7 (deploy:start_units_unprompted)"
  - id: no_force_push_to_main_master
    citation: "ESCALATION-POLICY.md § 4.2 (git:force_with_lease_main_master, git:force_push)"
  - id: no_schema_destructive_ddl
    citation: "ESCALATION-POLICY.md § 4.3 (state:drop_table, state:truncate_or_delete_unbounded, state:alter_table_drop_column)"
  - id: no_credential_rotation_without_founder
    citation: "ESCALATION-POLICY.md § 4.4 (secret:rotate, secret:revoke)"
  - id: no_llm_provider_outside_model_catalog
    citation: "ESCALATION-POLICY.md § 4.6 (paid:llm_provider_outside_catalog)"
  - id: no_skill_outside_hermes_skill_allowlist
    citation: "ESCALATION-POLICY.md § 4.8 (plugin:install_unallowed)"
  - id: no_governance_artifact_deletion_or_silent_overwrite
    citation: "ESCALATION-POLICY.md § 4.1 (gov:delete_governance_artifact, gov:overwrite_approved_artifact)"
  - id: no_prd_status_flip_to_approved_without_founder
    citation: "ESCALATION-POLICY.md § 4.9 (scope:prd_status_to_approved)"

deviation_rules:
  # These rules drive the deterministic concept-deviation classifier in
  # ESCALATION-POLICY.md § 5. Each rule's `match` is a precise predicate
  # over the candidate-action structure; each rule's `verdict` is one of
  # {ESCALATE, PROCEED}. The classifier walks the rules in order; the
  # first matching rule wins. If no rule matches AND the action is not
  # trivially read-only AND no deterministic § 4 rule fired, the
  # classifier returns ESCALATE (fail-closed).

  - id: replace_target_user
    match:
      kind: file_write
      path_glob: "docs/prd/PRD-*.md"
      content_diff_touches: ["§ 2", "Vision"]
    verdict: ESCALATE
    cite: "concept:replace_target_user (ESCALATION-POLICY § 4.10)"

  - id: replace_tech_stack_anchor
    match:
      kind: any_action
      argument_keyword_set: ["replace_hermes", "swap_telegram", "remove_openclaw"]
      operator: OR
    verdict: ESCALATE
    cite: "concept:replace_tech_stack (ESCALATION-POLICY § 4.10)"

  - id: replace_runtime_target
    match:
      kind: any_action
      argument_keyword_set: ["k8s", "kubernetes", "ecs", "lambda", "cloud_run", "fargate", "deploy_to_aws", "deploy_to_gcp", "deploy_to_azure"]
      operator: OR
    verdict: ESCALATE
    cite: "concept:replace_runtime_target (ESCALATION-POLICY § 4.10)"

  - id: introduce_paid_recurring_service
    match:
      kind: any_action
      argument_keyword_set: ["modal.com", "daytona", "e2b.dev", "vercel", "fly.io paid", "qdrant.cloud", "pinecone", "weaviate.cloud", "managed_redis", "managed_postgres", "letta_cloud"]
      operator: OR
    verdict: ESCALATE
    cite: "paid:new_recurring_service (ESCALATION-POLICY § 4.6)"

  - id: edit_concept_anchor
    match:
      kind: file_write
      path_glob: "docs/architecture/PROJECT-CONCEPT.md"
    verdict: ESCALATE
    cite: "concept:edit_concept_anchor (ESCALATION-POLICY § 4.10)"

  - id: open_public_inbound_port
    match:
      kind: shell_command
      argument_regex: "(ufw allow|firewall-cmd --add-port|iptables -A INPUT.*ACCEPT|systemd .* ListenStream)"
    verdict: ESCALATE
    cite: "net:open_inbound_port (ESCALATION-POLICY § 4.5)"

  - id: introduce_webhook_mode_telegram
    match:
      kind: file_write
      argument_keyword_set: ["telegram_webhook_url", "setWebhook", "telegram.update_mode: webhook"]
      operator: OR
    verdict: ESCALATE
    cite: "net:webhook_mode_telegram (ESCALATION-POLICY § 4.5)"

  - id: hardcode_secret_in_repo
    match:
      kind: file_write
      content_regex: "(?i)(sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{36}|[0-9]{9,10}:AA[A-Za-z0-9_-]{33})"
    verdict: ESCALATE
    cite: "secret:write_to_repo (ESCALATION-POLICY § 4.4)"

  # Default rule: fall-through.
  - id: default_fall_through
    match:
      kind: any_action
    verdict: PROCEED_OR_RULE_4_DECIDES
    note: |
      If no deviation_rule above fires, control returns to the § 4
      deterministic rule set in ESCALATION-POLICY.md (gov:*, git:*,
      state:*, secret:*, net:*, paid:*, deploy:*, plugin:*, scope:*,
      concept:*). If none of those fire either, the action is treated
      as a routine within-concept action and proceeds without
      escalation. This is the autonomy-default per PRD § 13.1.
```

## 3. Classifier Algorithm (referenced from `ESCALATION-POLICY.md` § 5)

The deterministic concept-deviation classifier in `ESCALATION-POLICY.md` § 5 implements this exact algorithm. The algorithm is fully specified, pure-Python, and unit-testable; it does NOT call any LLM.

```python
def classify_concept_deviation(action: CandidateAction, anchor: ConceptAnchor) -> Verdict:
    """
    Pure function. No I/O. No LLM. No randomness.

    Args:
      action: the candidate action (tool name, args, redacted text).
      anchor: the parsed YAML block from PROJECT-CONCEPT.md § 2.
    Returns:
      Verdict.ESCALATE or Verdict.PROCEED.

    Postcondition: same (action, anchor) ALWAYS yields the same Verdict.
    """
    for rule in anchor.deviation_rules:
        if matches(action, rule.match):
            if rule.verdict == "ESCALATE":
                return Verdict.ESCALATE(rule_id=rule.id, cite=rule.cite)
            elif rule.verdict == "PROCEED_OR_RULE_4_DECIDES":
                # Defer to deterministic rule set § 4.
                if any_section_4_rule_matches(action):
                    return Verdict.ESCALATE(rule_id="<§ 4 match>", cite="ESCALATION-POLICY § 4")
                return Verdict.PROCEED
            else:
                return Verdict.PROCEED
    # Unreachable: default_fall_through always matches.
    return Verdict.ESCALATE(rule_id="classifier_safety_default", cite="ESCALATION-POLICY § 5 fail-closed")
```

The `matches(action, rule.match)` predicate is a pure decision over:

- **`kind`** — the action class (`file_write`, `shell_command`, `tool_call`, `any_action`).
- **`path_glob`** — Unix glob applied to the candidate file write's target path.
- **`argument_keyword_set` + `operator: OR|AND`** — set membership over the union of stringified action arguments after the secret-redaction pass (`ESCALATION-POLICY.md` § 5.4).
- **`argument_regex`** — Python `re.search` on the same redacted argument string.
- **`content_regex`** — Python `re.search` on the file-write's content (only valid when `kind=file_write`).
- **`content_diff_touches`** — list of structural anchors (markdown § id, table id, code-fence label) that the diff between old and new content modifies.

Every predicate is a Python primitive (string, regex, list membership). No LLM. No probabilistic component. Implementation is in TKT-023 (added in PR-D).

## 4. Maintenance

This file changes only when:

- The PRD changes a concept-level commitment (e.g., `PRD-001` § 2 Vision, § 12 v0.1 commitments, § 13 autonomy/upstream).
- A new ADR records a concept-level decision (e.g., adding a new tech anchor, deferring a v0.1 item to v0.2).
- A new deterministic rule is added to `ESCALATION-POLICY.md` § 4 that the classifier should reach by way of this anchor.

Changes to this file are themselves caught by the `edit_concept_anchor` deviation rule above; they cannot land without Founder approval.

## 5. Cross-References

- `PRD-001.md` v0.2.1 § 2, § 6, § 12, § 13.1, § 13.2, § 13.3
- `ESCALATION-POLICY.md` v0.1.1 § 4 (deterministic rules), § 5 (deterministic concept-deviation classifier)
- `ARCH-001.md` v0.3.0 § 15 (escalation policy summary), § 16 (model catalog summary)
- `MODEL-CATALOG.md` v0.1.1 § 4.1 (per-role assignment), § 5 (routing layer), § 6 (within-catalog autonomy)
- `MULTI-HERMES-CONTRACT.md` § 4 (runtime config), § 8.2 (escalation flow)
- `OPERATIONAL-STATE-STORE.md` v0.2.1 § 3.5, § 3.6 (work_items, escalations)
- `OBSERVABILITY-CONTRACT.md` (ADDENDUM-001 — landed in PR-E)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.8 (pre_tool_call hook)
- `docs/architecture/adr/ADR-008-escalation-classifier.md` v0.1.1
- `docs/architecture/adr/ADR-009-model-assignment-and-fallback.md` v0.1.1
- Implementation: TKT-023 (escalation policy plugin)
