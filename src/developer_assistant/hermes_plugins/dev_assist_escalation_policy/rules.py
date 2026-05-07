from __future__ import annotations

import re
from typing import Optional

from developer_assistant.hermes_plugins.dev_assist_escalation_policy.redaction import redact_string

_GOV_DOCS_PREFIXES = (
    "docs/prd/",
    "docs/architecture/",
    "docs/architecture/adr/",
    "docs/tickets/",
    "docs/questions/",
    "docs/reviews/",
    "docs/orchestration/",
)

_GOVERNANCE_PATH_RE = re.compile(
    r"^docs/(prd|architecture|architecture/adr|tickets|questions|reviews|orchestration)/"
)

_CATALOG_MODELS = frozenset({
    "accounts/fireworks/models/minimax-m2p7",
    "accounts/fireworks/models/kimi-k2p6",
    "accounts/fireworks/models/qwen3p6-plus",
    "accounts/fireworks/models/deepseek-v4-pro",
    "accounts/fireworks/models/glm-5p1",
})

_CATALOG_MODEL_SLUGS = frozenset({
    "minimax-m2p7",
    "kimi-k2p6",
    "qwen3p6-plus",
    "deepseek-v4-pro",
    "glm-5p1",
})

_SECRET_NAME_RE = re.compile(r"(?i).*(TOKEN|API_KEY|SECRET|PASSWORD)")

_KNOWN_SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|[0-9]{8,10}:AA[A-Za-z0-9_-]{33}|sk-or-[A-Za-z0-9\-]{30,})"
)

_PAID_SERVICES = frozenset({
    "modal.com", "daytona", "e2b.dev", "vercel", "fly.io",
    "qdrant.cloud", "pinecone", "weaviate.cloud",
    "managed_redis", "managed_postgres", "letta_cloud",
})

_ALLOWED_ROLES = frozenset({"orchestrator", "planner", "architect", "executor", "reviewer"})

_APPROVED_FRONTMATTER_RE = re.compile(r"^status:\s*approved\s*$", re.MULTILINE)


def gov_write_outside_zone(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command"):
        return None
    path = action_args.get("path", "")
    allowed = action_args.get("allowed_files", [])
    if not allowed:
        return None
    if path and path not in allowed:
        return "gov:write_outside_zone"
    return None


def gov_delete_governance_artifact(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_delete", "shell_command"):
        return None
    path = action_args.get("path", "")
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if action_kind == "file_delete" and path and _GOVERNANCE_PATH_RE.match(path):
        return "gov:delete_governance_artifact"
    if action_kind == "shell_command" and re.search(r"rm\s+", cmd) and _GOVERNANCE_PATH_RE.search(cmd):
        return "gov:delete_governance_artifact"
    return None


def gov_overwrite_approved_artifact(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "file_write":
        return None
    old_content = action_args.get("old_content", "")
    new_content = action_args.get("content", "")
    if not old_content:
        return None
    if not _APPROVED_FRONTMATTER_RE.search(old_content):
        return None
    if new_content and old_content != new_content:
        return "gov:overwrite_approved_artifact"
    return None


def gov_rename_artifact(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_rename", "file_move", "shell_command"):
        return None
    path = action_args.get("path", "") or action_args.get("old_path", "")
    dest = action_args.get("new_path", "") or action_args.get("destination", "")
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if path and _GOVERNANCE_PATH_RE.match(path):
        return "gov:rename_artifact"
    if dest and _GOVERNANCE_PATH_RE.match(dest):
        return "gov:rename_artifact"
    if action_kind == "shell_command" and re.search(r"git\s+mv\s+", cmd) and _GOVERNANCE_PATH_RE.search(cmd):
        return "gov:rename_artifact"
    return None


def git_force_push(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"git\s+push\s+.*(--force\b|-f\b)", cmd) and "--force-with-lease" not in cmd:
        return "git:force_push"
    return None


def git_force_with_lease_main_master(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if "--force-with-lease" in cmd and re.search(r"(main|master)", cmd):
        return "git:force_with_lease_main_master"
    return None


def git_hard_reset(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"git\s+reset\s+.*--hard", cmd):
        return "git:hard_reset"
    return None


def git_branch_delete(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"git\s+branch\s+(-D|--delete|--force-delete)", cmd):
        return "git:branch_delete"
    if re.search(r"git\s+push\s+.*--delete", cmd):
        return "git:branch_delete"
    return None


def git_rebase_main_master(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"git\s+rebase", cmd) and re.search(r"(origin/)?(main|master)", cmd):
        return "git:rebase_main_master"
    return None


def git_no_verify_commit_or_push(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"git\s+(commit|push)\s+.*--no-verify", cmd):
        return "git:no_verify_commit_or_push"
    return None


def state_drop_table(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    sql = action_args.get("command", "") or action_args.get("sql", "") or action_args.get("content", "")
    if re.search(r"(?i)DROP\s+TABLE", sql):
        return "state:drop_table"
    return None


def state_drop_database(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    sql = action_args.get("command", "") or action_args.get("sql", "") or action_args.get("content", "")
    if re.search(r"(?i)DROP\s+DATABASE", sql):
        return "state:drop_database"
    return None


def state_truncate_or_delete_unbounded(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    sql = action_args.get("command", "") or action_args.get("sql", "") or action_args.get("content", "")
    if re.search(r"(?i)TRUNCATE\s", sql):
        return "state:truncate_or_delete_unbounded"
    if re.search(r"(?i)DELETE\s+FROM\s+\w+\s*;?\s*$", sql.strip()):
        return "state:truncate_or_delete_unbounded"
    if re.search(r"(?i)DELETE\s+FROM\s+\w+\s*$", sql.strip()):
        return "state:truncate_or_delete_unbounded"
    return None


def state_alter_table_drop_column(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    sql = action_args.get("command", "") or action_args.get("sql", "") or action_args.get("content", "")
    if re.search(r"(?i)ALTER\s+TABLE\s+.*DROP\s+COLUMN", sql):
        return "state:alter_table_drop_column"
    return None


def state_downgrade_schema(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call", "file_write"):
        return None
    content = action_args.get("command", "") or action_args.get("content", "") or action_args.get("sql", "")
    if "downgrade" in content.lower() and "schema" in content.lower():
        return "state:downgrade_schema"
    target = action_args.get("target_version", "")
    current = action_args.get("current_version", "")
    if target and current and str(target) < str(current):
        return "state:downgrade_schema"
    return None


def secret_rotate(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    path = action_args.get("path", "")
    if path and ("SELF-DEPLOY.env" in path or ".env" in path):
        content = action_args.get("content", "") or action_args.get("command", "")
        if _SECRET_NAME_RE.search(content):
            return "secret:rotate"
    env_name = action_args.get("env_var", "") or action_args.get("variable_name", "")
    if env_name and _SECRET_NAME_RE.match(env_name):
        return "secret:rotate"
    return None


def secret_revoke(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "") or action_args.get("action", "")
    if re.search(r"(?i)(revokeBotToken|delete-pat|revoke.*token|revoke.*key)", cmd):
        return "secret:revoke"
    return None


def secret_write_to_repo(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "file_write":
        return None
    content = action_args.get("content", "")
    if content and _KNOWN_SECRET_VALUE_RE.search(content):
        return "secret:write_to_repo"
    return None


def secret_expose_in_log(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    output = action_args.get("output", "") or action_args.get("content", "") or action_args.get("command", "")
    if output and _KNOWN_SECRET_VALUE_RE.search(output):
        return "secret:expose_in_log"
    return None


def net_open_inbound_port(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"(?i)(ufw\s+allow|firewall-cmd\s+.*--add-port|iptables\s+-A\s+INPUT.*ACCEPT)", cmd):
        return "net:open_inbound_port"
    if re.search(r"ListenStream\s*=\s*\d+", cmd):
        return "net:open_inbound_port"
    return None


def net_webhook_mode_telegram(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    content = action_args.get("content", "") or action_args.get("command", "")
    if re.search(r"(?i)setWebhook|telegram_webhook_url|telegram\.update_mode.*webhook", content):
        return "net:webhook_mode_telegram"
    return None


def net_expose_endpoint(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if re.search(r"(?i)(ngrok|cloudflare\s+tunnel|cf\s+tunnel)", cmd):
        return "net:expose_endpoint"
    if re.search(r"(?i)reverse.?proxy", cmd):
        return "net:expose_endpoint"
    return None


def paid_new_recurring_service(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    content = action_args.get("content", "") or action_args.get("command", "")
    for svc in _PAID_SERVICES:
        if svc.lower() in content.lower():
            return "paid:new_recurring_service"
    return None


def paid_llm_provider_outside_catalog(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("tool_call", "shell_command"):
        return None
    model = action_args.get("model", "")
    if model and model not in _CATALOG_MODELS and model not in _CATALOG_MODEL_SLUGS:
        return "paid:llm_provider_outside_catalog"
    return None


def paid_cloud_resource_provision(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if re.search(r"(?i)(aws\s+ec2|gcloud\s+compute|aws\s+lambda|az\s+vm|terraform\s+apply)", cmd):
        return "paid:cloud_resource_provision"
    return None


def deploy_start_units_unprompted(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"systemctl\s+start\s+devassist", cmd):
        return "deploy:start_units_unprompted"
    return None


def deploy_upgrade_activate_unprompted(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "shell_command":
        return None
    cmd = action_args.get("command", "")
    if re.search(r"upgrade-self\.sh\s+.*--activate", cmd):
        return "deploy:upgrade_activate_unprompted"
    return None


def deploy_generated_project_live_run(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if re.search(r"(?i)(live.?run|deploy.*live|production.*run|prod.*deploy)", cmd):
        return "deploy:generated_project_live_run"
    return None


def deploy_merge_pr(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "") or action_args.get("action", "")
    if re.search(r"(?i)(merge.*PR|gh\s+pr\s+merge|pull.*request.*merge)", cmd):
        return "deploy:merge_pr"
    return None


def plugin_install_unallowed(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if re.search(r"(?i)(hermes\s+plugin\s+install|hermes\s+skill\s+install|pip\s+install.*hermes)", cmd):
        return "plugin:install_unallowed"
    return None


def plugin_enable_project_local(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    content = action_args.get("content", "") or action_args.get("command", "")
    if "HERMES_ENABLE_PROJECT_PLUGINS" in content:
        val = action_args.get("value", "")
        if str(val).lower() in ("true", "1", "yes") or "true" in content.lower():
            return "plugin:enable_project_local"
    return None


def plugin_enable_marketplace_autoinstall(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    content = action_args.get("content", "") or action_args.get("command", "")
    if re.search(r"(?i)(hub.*auto.?install|marketplace.*auto|auto.*install.*skill)", content):
        return "plugin:enable_marketplace_autoinstall"
    return None


def plugin_agent_managed_skill_create(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("tool_call", "shell_command"):
        return None
    tool = action_args.get("tool", "") or action_args.get("tool_name", "")
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if tool == "skill_manage" or re.search(r"(?i)skill_manage", cmd):
        action = action_args.get("action", "")
        if action in ("create", "modify") or re.search(r"(?i)(create|modify)", cmd):
            return "plugin:agent_managed_skill_create"
    return None


def scope_prd_status_to_approved(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "file_write":
        return None
    path = action_args.get("path", "")
    content = action_args.get("content", "")
    old_content = action_args.get("old_content", "")
    if path and re.search(r"docs/prd/PRD-.*\.md", path):
        if "status: approved" in content and "status: approved" not in (old_content or ""):
            return "scope:prd_status_to_approved"
    return None


def scope_adr_status_to_approved(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "file_write":
        return None
    path = action_args.get("path", "")
    content = action_args.get("content", "")
    old_content = action_args.get("old_content", "")
    if path and re.search(r"docs/architecture/adr/ADR-.*\.md", path):
        if re.search(r"status:\s*(approved|accepted)", content) and not re.search(r"status:\s*(approved|accepted)", old_content or ""):
            return "scope:adr_status_to_approved"
    return None


def scope_add_v01_commitment(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind != "file_write":
        return None
    path = action_args.get("path", "")
    if path and re.search(r"docs/prd/PRD-.*\.md", path):
        content = action_args.get("content", "")
        old_content = action_args.get("old_content", "")
        if content and old_content and len(content) > len(old_content):
            return "scope:add_v01_commitment"
    return None


def concept_replace_target_user(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write",):
        return None
    path = action_args.get("path", "")
    if path and re.search(r"docs/prd/PRD-.*\.md", path):
        content = action_args.get("content", "")
        if re.search(r"(§\s*2|Vision)", content or ""):
            return "concept:replace_target_user"
    return None


def concept_replace_tech_stack(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    content = action_args.get("content", "") or action_args.get("command", "")
    for kw in ("replace_hermes", "swap_telegram", "remove_openclaw"):
        if kw in content:
            return "concept:replace_tech_stack"
    return None


def concept_replace_runtime_target(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("file_write", "shell_command", "tool_call"):
        return None
    content = action_args.get("content", "") or action_args.get("command", "")
    for kw in ("k8s", "kubernetes", "ecs", "lambda", "cloud_run", "fargate", "deploy_to_aws", "deploy_to_gcp", "deploy_to_azure"):
        if kw in content:
            return "concept:replace_runtime_target"
    return None


def concept_expose_private_endpoint(action_kind: str, action_args: dict) -> Optional[str]:
    if action_kind not in ("shell_command", "tool_call"):
        return None
    cmd = action_args.get("command", "") or action_args.get("content", "")
    if re.search(r"(?i)(ngrok|cloudflare\s+tunnel|cf\s+tunnel)", cmd):
        return "concept:expose_private_endpoint"
    if re.search(r"(?i)reverse.?proxy", cmd):
        return "concept:expose_private_endpoint"
    return None


ALL_RULES = [
    gov_write_outside_zone,
    gov_delete_governance_artifact,
    gov_overwrite_approved_artifact,
    gov_rename_artifact,
    git_force_push,
    git_force_with_lease_main_master,
    git_hard_reset,
    git_branch_delete,
    git_rebase_main_master,
    git_no_verify_commit_or_push,
    state_drop_table,
    state_drop_database,
    state_truncate_or_delete_unbounded,
    state_alter_table_drop_column,
    state_downgrade_schema,
    secret_rotate,
    secret_revoke,
    secret_write_to_repo,
    secret_expose_in_log,
    net_open_inbound_port,
    net_webhook_mode_telegram,
    net_expose_endpoint,
    paid_new_recurring_service,
    paid_llm_provider_outside_catalog,
    paid_cloud_resource_provision,
    deploy_start_units_unprompted,
    deploy_upgrade_activate_unprompted,
    deploy_generated_project_live_run,
    deploy_merge_pr,
    plugin_install_unallowed,
    plugin_enable_project_local,
    plugin_enable_marketplace_autoinstall,
    plugin_agent_managed_skill_create,
    scope_prd_status_to_approved,
    scope_adr_status_to_approved,
    scope_add_v01_commitment,
    concept_replace_target_user,
    concept_replace_tech_stack,
    concept_replace_runtime_target,
    concept_expose_private_endpoint,
]


def evaluate_rules(action_kind: str, action_args: dict) -> Optional[str]:
    for rule_fn in ALL_RULES:
        result = rule_fn(action_kind, action_args)
        if result is not None:
            return result
    return None
