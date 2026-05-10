#!/usr/bin/env bash
set -euo pipefail

SELF_DEPLOY_VERSION="0.3.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNIROUTE_PORT=20128
OMNIROUTE_BASE_URL="${OMNIROUTE_BASE_URL:-http://127.0.0.1:20128/v1}"
OMNIROUTE_API_KEY="${OMNIROUTE_API_KEY:-test-token-placeholder}"
EXPECTED_SCHEMA_VERSION="3"
ROLES="orchestrator planner architect executor reviewer"

# TKT-034 § 1.A.iv: 15 custom dev-assist-* skills enumerated in
# MULTI-HERMES-CONTRACT.md § 5.0 (the prose says "14"; the table lists 15 rows).
# This list is the install-time pin; the verify-self.sh
# `check_shared_skills_manifest_match` invariant enforces parity with the
# rendered manifest and with on-disk content. Any addition/removal MUST be
# a sibling Architect amendment to MULTI-HERMES-CONTRACT.md § 5.0 first.
SHARED_SKILLS="dev-assist-classifier dev-assist-progress-report dev-assist-escalation-surface dev-assist-work-queue-write dev-assist-work-queue-poll dev-assist-prd-writer dev-assist-questions-writer dev-assist-arch-writer dev-assist-adr-writer dev-assist-tickets-writer dev-assist-executor-discipline dev-assist-write-zone-enforcer dev-assist-github-workflow dev-assist-reviewer-rubric dev-assist-review-writer"

# TKT-034 § 1.B.ii default-fill values for the visible-prompt set.
DEFAULT_OMNIROUTE_BASE_URL="https://omniroute.infinitycore.space:8443/v1"
DEFAULT_HERMES_DEVASSIST_REPO_URL="https://github.com/OpenClown-bot/developer-assistant.git"
DEFAULT_HERMES_DEVASSIST_REPO_BRANCH="main"
DEFAULT_OPERATOR_GIT_USER_NAME="developer-assistant operator"

# TKT-034 § 1.B.ii: retry-N exhaustion default (configurable via env).
INSTALL_PROMPT_RETRIES="${INSTALL_PROMPT_RETRIES:-3}"
# TKT-034 § 7 SSH-key flow: timeout for "Press ENTER once added" prompt.
INSTALL_SSH_KEY_TIMEOUT_SECONDS="${INSTALL_SSH_KEY_TIMEOUT_SECONDS:-300}"

# TKT-034 § 1.B.iii flag state. Defaults assigned by parse_flags();
# detect_install_mode() resolves the final INSTALL_MODE.
INTERACTIVE_FLAG=""
GH_AUTH_MODE="pat"
FORCE_REINSTALL=0
REPROMPT_SECRETS=0
ROTATE_SECRETS=0
INSTALL_MODE=""

MODEL_MAIN_ORCHESTRATOR="accounts/fireworks/models/minimax-m2p7"
MODEL_MAIN_PLANNER="accounts/fireworks/models/qwen3p6-plus"
MODEL_MAIN_ARCHITECT="accounts/fireworks/models/deepseek-v3p2"
MODEL_MAIN_EXECUTOR="accounts/fireworks/models/glm-5p1"
MODEL_MAIN_REVIEWER="accounts/fireworks/models/kimi-k2p6"

FALLBACK_ORCHESTRATOR="accounts/fireworks/models/kimi-k2p6,accounts/fireworks/models/qwen3p6-plus,accounts/fireworks/models/deepseek-v3p2"
FALLBACK_PLANNER="accounts/fireworks/models/kimi-k2p6,accounts/fireworks/models/minimax-m2p7,accounts/fireworks/models/deepseek-v3p2"
FALLBACK_ARCHITECT="accounts/fireworks/models/kimi-k2p6,accounts/fireworks/models/glm-5p1,accounts/fireworks/models/qwen3p6-plus"
FALLBACK_EXECUTOR="accounts/fireworks/models/deepseek-v3p2,accounts/fireworks/models/kimi-k2p6,accounts/fireworks/models/qwen3p6-plus"
FALLBACK_REVIEWER="accounts/fireworks/models/deepseek-v3p2,accounts/fireworks/models/glm-5p1,accounts/fireworks/models/qwen3p6-plus"
DRY_RUN="${INSTALL_DRY_RUN:-0}"
PREFIX=""
if [ "$DRY_RUN" = "1" ]; then
    PREFIX="${INSTALL_DRY_RUN_PREFIX:-/tmp/devassist-dry-run}"
fi
BASE="${PREFIX}/srv/devassist"
SYSTEMD_DIR="${PREFIX}/etc/systemd/system"
LOG_FILE="${BASE}/logs/self-deploy.log"

log() {
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[${ts}] install-self: $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[${ts}] install-self: $*"
}

check_deps() {
    # TKT-034 § 1.B.viii required-CLIs: extended to the full canonical list.
    # verify_prereqs() runs the strict B.viii preflight; this lightweight
    # check guards the script's own helper steps (mkdir, chown, etc.) before
    # verify_prereqs() is even reachable.
    local missing=""
    for cmd in bash systemctl sqlite3 curl tar git python3 sudo lsb_release stat sha256sum useradd usermod chmod chown ln mkdir; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing="${missing} ${cmd}"
        fi
    done
    if [ -n "$missing" ]; then
        log "FATAL: missing dependencies:${missing}"
        exit 1
    fi
}

create_users() {
    # TKT-034 § 1.A.ii / AC-2 (b): drop --no-create-home so devassist has a
    # real HOME for git config + gh auth (per ADR-014 Correction 5). The
    # systemd unit templates (TKT-033 frozen surface) override HOME with
    # Environment=HOME=/srv/devassist/runtimes/<role>/.hermes; /home/devassist
    # is for the install-time gh auth + git config flow only.
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would create system user devassist with home /home/devassist"
        # Fixture: create a stub home dir under PREFIX so tests can read
        # ~devassist/.gitconfig from the dry-run prefix.
        local fixture_home="${PREFIX}/home/devassist"
        mkdir -p "$fixture_home"
        return 0
    fi
    if ! id -u devassist >/dev/null 2>&1; then
        log "Creating system user: devassist (with home /home/devassist)"
        useradd --system --create-home --home-dir /home/devassist --shell /usr/sbin/nologin devassist
        chmod 0700 /home/devassist
    else
        log "User devassist already exists (idempotent)"
        if [ ! -d /home/devassist ]; then
            mkdir -p /home/devassist
            chown devassist:devassist /home/devassist
            chmod 0700 /home/devassist
        fi
    fi
}

create_filesystem() {
    log "Creating /srv/devassist/ filesystem layout under ${BASE}"
    mkdir -p "${BASE}"/{repo,runtimes,state/backups,secrets,releases,web/templates,logs,shared-skills,shared-plugins}
    for role in $ROLES; do
        mkdir -p "${BASE}/runtimes/${role}/.hermes"/{memories,sessions,cron,logs,skills}
    done
    if [ "$DRY_RUN" = "0" ]; then
        chown -R devassist:devassist "${BASE}"
        chmod 0700 "${BASE}/state/backups"
        chmod 0640 "${BASE}/state" 2>/dev/null || true
    fi
    log "Filesystem layout created"
}

init_operational_db() {
    local db="${BASE}/state/operational.db"
    if [ ! -f "$db" ]; then
        log "Initializing operational.db at ${db}"
        sqlite3 "$db" "PRAGMA journal_mode=WAL;" || true
        sqlite3 "$db" "PRAGMA foreign_keys=ON;" || true
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
        sqlite3 "$db" "INSERT OR IGNORE INTO _schema_meta (key, value) VALUES ('schema_version', '${EXPECTED_SCHEMA_VERSION}');"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS project_bindings (chat_key TEXT PRIMARY KEY, repo_url TEXT NOT NULL, repo_owner_name TEXT, workspace_path TEXT, phase TEXT, updated_at TEXT NOT NULL);"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS scheduled_progress (project_key TEXT PRIMARY KEY, last_report_at TEXT, next_report_at TEXT, interval_minutes INTEGER, updated_at TEXT NOT NULL, FOREIGN KEY (project_key) REFERENCES project_bindings(chat_key));"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS hermes_runs (run_id TEXT PRIMARY KEY, project_key TEXT NOT NULL, role TEXT, task_type TEXT, status TEXT NOT NULL, idempotency_key TEXT UNIQUE, in_flight_meta TEXT, updated_at TEXT NOT NULL, FOREIGN KEY (project_key) REFERENCES project_bindings(chat_key));"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS work_items (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL, target_role TEXT NOT NULL CHECK(target_role IN ('planner','architect','executor','reviewer')), kind TEXT NOT NULL, payload_json TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 50, status TEXT NOT NULL CHECK(status IN ('pending','claimed','completed','failed','released')), claimed_by_runtime TEXT, claimed_at TEXT, claim_lease_until TEXT, completed_at TEXT, result_json TEXT, attempt_count INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3, originating_run_id TEXT);"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS escalations (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, originating_runtime TEXT NOT NULL CHECK(originating_runtime IN ('orchestrator','planner','architect','executor','reviewer')), originating_work_item_id INTEGER, trigger_kind TEXT NOT NULL, context TEXT NOT NULL, proposed_action TEXT NOT NULL, options_json TEXT NOT NULL, recommended_default TEXT NOT NULL, impact TEXT NOT NULL, urgency TEXT NOT NULL CHECK(urgency IN ('low','medium','high')), durable_artifact_target TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','surfaced','approved','denied','expired')), surfaced_at TEXT, resolved_at TEXT, founder_response TEXT, telegram_message_id TEXT);"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS errors (err_id TEXT PRIMARY KEY, ts TEXT NOT NULL, runtime TEXT NOT NULL, work_item_id INTEGER, error_class TEXT NOT NULL, message TEXT NOT NULL, context_json TEXT NOT NULL DEFAULT '{}');"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS llm_calls (call_id TEXT PRIMARY KEY, ts TEXT NOT NULL, runtime TEXT NOT NULL, work_item_id INTEGER, model TEXT NOT NULL, routing_path TEXT NOT NULL CHECK(routing_path IN ('omniroute_endpoint','openrouter_endpoint')), tokens_in INTEGER NOT NULL, tokens_out INTEGER NOT NULL, latency_ms INTEGER NOT NULL, rate_in_per_1m_usd REAL NOT NULL, rate_out_per_1m_usd REAL NOT NULL, cost_usd REAL NOT NULL, status TEXT NOT NULL CHECK(status IN ('success','fail')), error_class TEXT);"
        sqlite3 "$db" "CREATE TABLE IF NOT EXISTS llm_calls_daily (day TEXT NOT NULL, runtime TEXT NOT NULL, model TEXT NOT NULL, routing_path TEXT NOT NULL, call_count INTEGER NOT NULL, call_count_success INTEGER NOT NULL, call_count_fail INTEGER NOT NULL, tokens_in_total INTEGER NOT NULL, tokens_out_total INTEGER NOT NULL, cost_usd_total REAL NOT NULL, latency_ms_p50 INTEGER, latency_ms_p95 INTEGER, PRIMARY KEY (day, runtime, model, routing_path));"
        sqlite3 "$db" "PRAGMA quick_check;" | grep -q "ok" && log "operational.db initialized and verified" || { log "FATAL: operational.db quick_check failed"; exit 1; }
    else
        log "operational.db already exists (idempotent)"
    fi
}

symlink_operational_db() {
    for role in $ROLES; do
        local target="${BASE}/runtimes/${role}/.hermes/operational.db"
        local source="${BASE}/state/operational.db"
        if [ -L "$target" ]; then
            log "Symlink ${target} already exists (idempotent)"
        else
            if [ -e "$target" ]; then
                log "WARNING: ${target} exists and is not a symlink; replacing"
                rm -f "$target"
            fi
            ln -sfn "$source" "$target"
            log "Symlinked ${target} -> ${source}"
        fi
    done
}

symlink_env_file() {
    for role in $ROLES; do
        local target="${BASE}/runtimes/${role}/.hermes/.env"
        local source="${BASE}/secrets/SELF-DEPLOY.env"
        if [ -L "$target" ]; then
            log "Symlink ${target} already exists (idempotent)"
        else
            if [ -e "$target" ]; then
                log "WARNING: ${target} exists and is not a symlink; replacing"
                rm -f "$target"
            fi
            ln -sfn "$source" "$target"
            log "Symlinked ${target} -> ${source}"
        fi
    done
}

render_runtime_configs() {
    local template_dir="${SCRIPT_DIR}/../etc/runtime-templates"
    for role in $ROLES; do
        local tmpl="${template_dir}/${role}/config.yaml.tmpl"
        local dst="${BASE}/runtimes/${role}/.hermes/config.yaml"
        if [ ! -f "$tmpl" ]; then
            log "FATAL: runtime config template ${tmpl} not found"
            exit 1
        fi

        local model_main=""
        local fallbacks=""
        local gateway_enabled="false"
        local repo_path="${BASE}/repo"
        local built_in_skills="    - chat\n    - file\n    - code"
        local prompt_file=""
        local terminal_block=""

        case "$role" in
            orchestrator)
                model_main="$MODEL_MAIN_ORCHESTRATOR"
                fallbacks="$FALLBACK_ORCHESTRATOR"
                gateway_enabled="true"
                built_in_skills="    - chat\n    - file\n    - code\n    - telegram_gateway"
                prompt_file="orchestrator.md"
                ;;
            planner)
                model_main="$MODEL_MAIN_PLANNER"
                fallbacks="$FALLBACK_PLANNER"
                prompt_file="business_planner.md"
                ;;
            architect)
                model_main="$MODEL_MAIN_ARCHITECT"
                fallbacks="$FALLBACK_ARCHITECT"
                prompt_file="architect.md"
                ;;
            executor)
                model_main="$MODEL_MAIN_EXECUTOR"
                fallbacks="$FALLBACK_EXECUTOR"
                prompt_file="executor.md"
                terminal_block="\nterminal:\n  backend: docker"
                ;;
            reviewer)
                model_main="$MODEL_MAIN_REVIEWER"
                fallbacks="$FALLBACK_REVIEWER"
                prompt_file="reviewer.md"
                terminal_block="\nterminal:\n  backend: docker"
                ;;
        esac

        local fb_1
        fb_1=$(echo "$fallbacks" | cut -d',' -f1)

        local content
        content=$(cat "$tmpl")
        content=$(echo "$content" | sed "s|{{model_main}}|${model_main}|g")
        content=$(echo "$content" | sed "s|{{fallback_1}}|${fb_1}|g")
        content=$(echo "$content" | sed "s|{{omniroute_base_url}}|${OMNIROUTE_BASE_URL}|g")
        content=$(echo "$content" | sed "s|{{omniroute_api_key}}|${OMNIROUTE_API_KEY}|g")
        content=$(echo "$content" | sed "s|{{gateway_enabled}}|${gateway_enabled}|g")
        content=$(echo "$content" | sed "s|{{role}}|${role}|g")
        content=$(echo "$content" | sed "s|{{repo_path}}|${repo_path}|g")
        content=$(echo "$content" | sed "s|{{prompt_file}}|${prompt_file}|g")
        content=$(echo "$content" | sed "s|{{built_in_skills}}|${built_in_skills}|g")
        content=$(echo "$content" | sed "s|{{terminal_block}}|${terminal_block}|g")

        echo "$content" > "$dst"
        if [ "$DRY_RUN" = "0" ]; then
            chown devassist:devassist "$dst"
        fi
        log "Rendered config.yaml for ${role}"
    done

    # TKT-033 § 1 component C: render the install-time prompt-manifest atomically.
    # Folded INSIDE render_runtime_configs() so the manifest is part of the same
    # rendering phase as the per-role config.yaml; main() already calls this
    # function before render_systemd_units(), so the manifest is guaranteed to
    # exist before any ExecStart/ExecStartPre can run. Per-role <role> -->
    # docs/prompts/<file>.md mapping mirrors AGENTS.md Roles table; keep this
    # in sync with src/developer_assistant/runtime_check.py PROMPT_FILE_BY_ROLE.
    local repo_root="${SCRIPT_DIR}/.."
    local manifest_dir="${BASE}/state"
    local manifest="${manifest_dir}/prompt-manifest.json"
    local manifest_tmp="${manifest}.tmp.$$"
    local rendered_at
    rendered_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    mkdir -p "$manifest_dir"
    {
        printf '{\n'
        printf '  "schema_version": "1.0",\n'
        printf '  "rendered_at": "%s",\n' "$rendered_at"
        printf '  "prompts": {\n'
        local first=1
        for role in $ROLES; do
            local prompt_rel
            case "$role" in
                orchestrator) prompt_rel="docs/prompts/runtime-hermes-orchestrator.md" ;;
                planner)      prompt_rel="docs/prompts/business-planner.md" ;;
                architect)    prompt_rel="docs/prompts/architect.md" ;;
                executor)     prompt_rel="docs/prompts/executor.md" ;;
                reviewer)     prompt_rel="docs/prompts/reviewer.md" ;;
                *) log "FATAL: unknown role '${role}' in prompt-manifest renderer"; exit 1 ;;
            esac
            local prompt_path="${repo_root}/${prompt_rel}"
            if [ ! -f "$prompt_path" ]; then
                log "FATAL: prompt file not found at ${prompt_path}; cannot render manifest"
                exit 1
            fi
            local sha
            sha=$(sha256sum "$prompt_path" | awk '{print $1}')
            if [ "$first" = "1" ]; then
                first=0
            else
                printf ',\n'
            fi
            printf '    "%s": "%s"' "$role" "$sha"
        done
        printf '\n  }\n}\n'
    } > "$manifest_tmp"
    mv -f "$manifest_tmp" "$manifest"
    if [ "$DRY_RUN" = "0" ]; then
        chown devassist:devassist "$manifest" 2>/dev/null || true
        chmod 0644 "$manifest"
    fi
    log "Rendered prompt-manifest.json with SHA-256 of 5 per-role prompt files (atomic mv)"
}

render_self_deploy_env() {
    local secrets_dir="${BASE}/secrets"
    local env_file="${secrets_dir}/SELF-DEPLOY.env"
    # TKT-034 § 1.B.iv (Option ψ): dir 0710 root:devassist; file 0400
    # devassist:devassist. The directory is created here (with the strict
    # ACL) before the env file is written so the ACL transition is atomic
    # from the operator's perspective.
    mkdir -p "$secrets_dir"
    # In DRY_RUN we apply chmod (no privileges required) so verify-self
    # can confirm the ACL policy in fixture; chown requires root and is
    # only applied on a real install.
    chmod 0710 "$secrets_dir" 2>/dev/null || true
    if [ "$DRY_RUN" = "0" ]; then
        chown root:devassist "$secrets_dir" 2>/dev/null || true
    fi
    if [ -f "$env_file" ] && grep -q "TELEGRAM_BOT_TOKEN" "$env_file" 2>/dev/null; then
        log "SELF-DEPLOY.env already exists with required keys (idempotent)"
        # Re-tighten the ACL on every run so a re-install picks up the
        # 0400/0710 invariant even if the file pre-existed at 0600.
        chmod 0600 "$env_file" 2>/dev/null || true
        if [ "$DRY_RUN" = "0" ]; then
            chmod 0400 "$env_file" 2>/dev/null || true
            chown devassist:devassist "$env_file" 2>/dev/null || true
        fi
        return 0
    fi
    log "Rendering ${env_file} with values from environment (or placeholders)"

    local tbt="${TELEGRAM_BOT_TOKEN:-test-token-placeholder}"
    local tau="${TELEGRAM_ALLOWED_USERS:-test-user-placeholder}"
    local gt="${GITHUB_TOKEN:-test-token-placeholder}"
    local oak="${OMNIROUTE_API_KEY:-test-token-placeholder}"
    local obu="${OMNIROUTE_BASE_URL:-http://127.0.0.1:20128/v1}"
    local ork="${OPENROUTER_API_KEY:-}"
    local fak="${FIREWORKS_API_KEY:-test-token-placeholder}"
    local hru="${HERMES_DEVASSIST_REPO_URL:-https://github.com/example/developer-assistant}"
    local hrb="${HERMES_DEVASSIST_REPO_BRANCH:-main}"
    local dfuid="${DEVASSIST_FOUNDER_TELEGRAM_USER_ID:-test-user-placeholder}"
    local ogun="${OPERATOR_GIT_USER_NAME:-developer-assistant operator}"
    local ogue="${OPERATOR_GIT_USER_EMAIL:-devassist@localhost}"

    cat > "$env_file" <<EOF
TELEGRAM_BOT_TOKEN=${tbt}
TELEGRAM_ALLOWED_USERS=${tau}
GITHUB_TOKEN=${gt}
OMNIROUTE_API_KEY=${oak}
OMNIROUTE_BASE_URL=${obu}
CUSTOM_BASE_URL=${obu}
CUSTOM_API_KEY=${oak}
OPENROUTER_API_KEY=${ork}
FIREWORKS_API_KEY=${fak}
ANTHROPIC_API_KEY=
GLM_API_KEY=
KIMI_API_KEY=
HERMES_DEVASSIST_REPO_URL=${hru}
HERMES_DEVASSIST_REPO_BRANCH=${hrb}
DEVASSIST_FOUNDER_TELEGRAM_USER_ID=${dfuid}
OPERATOR_GIT_USER_NAME=${ogun}
OPERATOR_GIT_USER_EMAIL=${ogue}
EOF
    # Always apply chmod 0600 (no privileges); verify-self accepts 0400
    # or 0600 in fixture mode.
    chmod 0600 "$env_file" 2>/dev/null || true
    if [ "$DRY_RUN" = "0" ]; then
        # TKT-034 § 1.B.iv: tighten file ACL from 0600 to 0400.
        chmod 0400 "$env_file"
        chown devassist:devassist "$env_file"
    fi
}

install_hermes_agent() {
    local hermes_dir="${PREFIX}/usr/local/lib/hermes-agent"
    local hermes_repo="${hermes_dir}/src"
    local hermes_venv="${hermes_dir}/venv"
    if [ -x "${hermes_venv}/bin/hermes" ]; then
        log "Hermes Agent already installed at ${hermes_dir} (idempotent)"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would install Hermes Agent at ${hermes_dir}"
        mkdir -p "$hermes_dir"/bin
        echo "#!/bin/sh" > "${hermes_dir}/bin/hermes"
        echo "echo 'hermes stub (dry-run)'" >> "${hermes_dir}/bin/hermes"
        chmod +x "${hermes_dir}/bin/hermes"
        return 0
    fi
    log "Installing Hermes Agent at ${hermes_dir}"
    mkdir -p "$hermes_dir"
    git clone --depth 1 --branch v2026.4.30 https://github.com/NousResearch/hermes-agent.git "$hermes_repo" || {
        log "FATAL: Hermes Agent git clone failed"
        exit 1
    }
    python3 -m venv "$hermes_venv"
    "${hermes_venv}/bin/pip" install --quiet "$hermes_repo" || {
        log "FATAL: Hermes Agent pip install failed"
        exit 1
    }
    ln -sfn "${hermes_venv}/bin/hermes" /usr/local/bin/hermes
    ln -sfn "${hermes_venv}/bin/hermes" "${hermes_dir}/bin/hermes" 2>/dev/null || true
    "${hermes_venv}/bin/pip" install --quiet python-telegram-bot 2>/dev/null || log "WARN: python-telegram-bot install failed (Telegram gateway may not work)"
    log "Hermes Agent installed"
}

install_dev_assist_cli() {
    local cli_dir="${PREFIX}/opt/dev-assist"
    local cli_bin="${cli_dir}/bin"
    if [ -x "${cli_bin}/dev-assist-cli" ]; then
        log "dev-assist-cli already installed at ${cli_bin} (idempotent)"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would install dev-assist-cli at ${cli_dir}"
        mkdir -p "$cli_bin"
        echo "#!/bin/sh" > "${cli_bin}/dev-assist-cli"
        echo "echo 'dev-assist-cli stub (dry-run)'" >> "${cli_bin}/dev-assist-cli"
        chmod +x "${cli_bin}/dev-assist-cli"
        return 0
    fi
    log "Installing dev-assist-cli at ${cli_dir}"
    mkdir -p "$cli_dir" "$cli_bin"
    cat > "${cli_bin}/dev-assist-cli" <<'CLIWrapper'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, "/srv/devassist/repo/src")
from developer_assistant.cli.dev_assist_cli import main
sys.exit(main())
CLIWrapper
    chmod +x "${cli_bin}/dev-assist-cli"
    chown -R devassist:devassist "$cli_dir"
    log "dev-assist-cli installed"
}

install_worker_runner() {
    local worker_path="${PREFIX}/usr/local/bin/devassist-worker-runner"
    local orch_path="${PREFIX}/usr/local/bin/devassist-orchestrator-runner"
    if [ -x "$worker_path" ] && [ -x "$orch_path" ]; then
        log "worker/orchestrator runners already installed (idempotent)"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would install worker and orchestrator runners"
        return 0
    fi
    log "Installing devassist-worker-runner and devassist-orchestrator-runner"
    cat > "$worker_path" <<'WORKERRUNNER'
#!/usr/bin/env bash
set -euo pipefail
ROLE="${HERMES_DEVASSIST_ROLE:-unknown}"
HEALTH_PORT="${DEVASSIST_HEALTH_PORT:-0}"
POLL_INTERVAL="${DEVASSIST_WORKER_POLL_INTERVAL:-30}"
HERMES_BIN="/usr/local/bin/hermes"
export HOME="${HOME:-/srv/devassist/runtimes/${ROLE}}"
if [ "${HEALTH_PORT:-0}" -gt 0 ]; then
    python3 -c "
import http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            import os; self.wfile.write(('{\"status\":\"ok\",\"role\":\"'+os.environ.get('HERMES_DEVASSIST_ROLE','unknown')+'\"}').encode())
        else: self.send_response(404); self.end_headers()
    def log_message(self,*a): pass
http.server.HTTPServer(('127.0.0.1',int('${HEALTH_PORT}')),H).serve_forever()
" &
fi
trap "kill 0 2>/dev/null" EXIT
while true; do
    ${HERMES_BIN} chat -q "Process next work item for role ${ROLE}" --yolo --accept-hooks --quiet 2>/dev/null || true
    sleep "$POLL_INTERVAL"
done
WORKERRUNNER
    chmod +x "$worker_path"

    cat > "$orch_path" <<'ORCHRUNNER'
#!/usr/bin/env bash
set -euo pipefail
HEALTH_PORT="${DEVASSIST_HEALTH_PORT:-0}"
HERMES_BIN="/usr/local/bin/hermes"
export HOME="${HOME:-/srv/devassist/runtimes/orchestrator}"
python3 -c "
import http.server
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(b'{\"status\":\"ok\",\"role\":\"orchestrator\"}')
        else: self.send_response(404); self.end_headers()
    def log_message(self,*a): pass
http.server.HTTPServer(('127.0.0.1',int('${HEALTH_PORT}')),H).serve_forever()
" &
trap "kill 0 2>/dev/null" EXIT
exec ${HERMES_BIN} gateway run --accept-hooks
ORCHRUNNER
    chmod +x "$orch_path"
    log "worker/orchestrator runners installed"
}

render_systemd_units() {
    mkdir -p "$SYSTEMD_DIR"
    local template_dir="${SCRIPT_DIR}/templates"
    local units="devassist.target devassist-orchestrator.service devassist-planner.service devassist-architect.service devassist-executor.service devassist-reviewer.service "

    for unit in $units; do
        local src="${template_dir}/${unit}.j2"
        local dst="${SYSTEMD_DIR}/${unit}"
        if [ ! -f "$src" ]; then
            log "FATAL: template ${src} not found"
            exit 1
        fi
        cp "$src" "$dst"
        log "Rendered ${dst}"
    done

    if [ "$DRY_RUN" = "0" ]; then
        systemctl daemon-reload 2>/dev/null || log "WARN: systemctl daemon-reload skipped (not running systemd?)"
    else
        log "DRY_RUN: would run systemctl daemon-reload"
    fi
}

write_journald_dropin() {
    local dropin_dir="${PREFIX}/etc/systemd/journald.conf.d"
    local dropin_file="${dropin_dir}/dev-assist.conf"
    mkdir -p "$dropin_dir"
    cat > "$dropin_file" <<'JOURNALD'
[Journal]
Storage=persistent
SystemMaxUse=1G
SystemMaxFileSize=128M
MaxRetentionSec=30d
ForwardToSyslog=no
JOURNALD
    log "Wrote journald drop-in at ${dropin_file}"
    if [ "$DRY_RUN" = "0" ]; then
        systemctl restart systemd-journald 2>/dev/null || log "WARN: journald restart skipped"
    fi
}

run_verify() {
    log "Running verify-self.sh (pre-start mode)"
    VERIFY_PHASE=pre-start \
        bash "${SCRIPT_DIR}/verify-self.sh"
    local rc=$?
    if [ $rc -ne 0 ]; then
        log "FATAL: verify-self.sh failed (exit ${rc}); install aborted"
        exit $rc
    fi
    log "verify-self.sh passed"
}

# ----------------------------------------------------------------------
# TKT-034 § 1.B additions: flag parsing, install-mode detection,
# prereq verification, prior-deploy detection, gh CLI install + auth,
# devassist git identity, shared-skills manifest renderer, and the
# 11 interactive prompt functions.
# ----------------------------------------------------------------------

usage() {
    # TKT-034 § 4 AC-3: in-script usage block documenting the new flags.
    cat <<USAGE
Usage: install-self.sh [OPTIONS]

Bring a freshly provisioned Ubuntu 22.04 LTS VPS to the post-install state
defined by SELF-DEPLOYMENT-CONTRACT.md v0.3.0 § 4-§ 8 and
MULTI-HERMES-CONTRACT.md v0.2.0 § 5.

Options:
  --interactive             Force interactive credential-prompt mode.
  --non-interactive         Force non-interactive mode (read all required
                            env vars from the calling environment).
  --gh-auth=pat             Use a fine-grained GitHub PAT (default).
  --gh-auth=ssh             Use the SSH-key alternative path. A PAT is
                            still required for the runtime REST API.
  --force-reinstall         Skip the prior-deploy detection abort. Does
                            NOT perform destructive cleanup; the operator
                            is responsible for running the cleanup runbook
                            first. Combining with --rotate-secrets aborts
                            with a "Not implemented in v0.2.0" message.
  --reprompt-secrets        RESERVED. Aborts with "Not implemented in
                            v0.2.0; deferred to a future ticket".
  --rotate-secrets          RESERVED. Aborts with "Not implemented in
                            v0.2.0; deferred to a future ticket".
  --help, -h                Print this usage block and exit.

Environment overrides:
  INSTALL_DRY_RUN=1                      Render under INSTALL_DRY_RUN_PREFIX.
  INSTALL_DRY_RUN_PREFIX=<path>          Default: /tmp/devassist-dry-run.
  INSTALL_NONINTERACTIVE=1               Equivalent to --non-interactive.
  INSTALL_PROMPT_RETRIES=<N>             Default: 3.
  INSTALL_SSH_KEY_TIMEOUT_SECONDS=<N>    Default: 300.

See docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md
for the full architectural choices behind each flag.
USAGE
}

parse_flags() {
    # TKT-034 § 1.B.iii: explicit CLI flags. Conflicts (--interactive AND
    # --non-interactive) abort with non-zero exit; reserved flags abort
    # with a deferral message; --gh-auth=pat is the default.
    local seen_interactive=0
    local seen_non_interactive=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --interactive)
                INTERACTIVE_FLAG="yes"
                seen_interactive=1
                ;;
            --non-interactive)
                INTERACTIVE_FLAG="no"
                seen_non_interactive=1
                ;;
            --gh-auth=pat)
                GH_AUTH_MODE="pat"
                ;;
            --gh-auth=ssh)
                GH_AUTH_MODE="ssh"
                ;;
            --gh-auth=*)
                log "FATAL: unknown --gh-auth value '${1#--gh-auth=}'; expected pat or ssh"
                exit 2
                ;;
            --force-reinstall)
                FORCE_REINSTALL=1
                ;;
            --reprompt-secrets)
                REPROMPT_SECRETS=1
                ;;
            --rotate-secrets)
                ROTATE_SECRETS=1
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                log "FATAL: unknown flag '$1'"
                usage >&2
                exit 2
                ;;
        esac
        shift
    done
    if [ "$seen_interactive" = "1" ] && [ "$seen_non_interactive" = "1" ]; then
        log "FATAL: --interactive and --non-interactive are mutually exclusive"
        exit 2
    fi
    # TKT-034 § 4 AC-9 (b): --rotate-secrets (alone or combined) aborts.
    if [ "$ROTATE_SECRETS" = "1" ]; then
        log "FATAL: --rotate-secrets is RESERVED; not implemented in v0.2.0; deferred to a future v0.3.0+ ticket"
        exit 2
    fi
    if [ "$REPROMPT_SECRETS" = "1" ]; then
        log "FATAL: --reprompt-secrets is RESERVED; not implemented in v0.2.0; deferred to a future v0.3.0+ ticket"
        exit 2
    fi
}

detect_install_mode() {
    # TKT-034 § 1.B.iii: TTY detection rule. Explicit flag wins; then env
    # var; then [-t 0] && [-t 1]; default non-interactive.
    if [ "$INTERACTIVE_FLAG" = "yes" ]; then
        INSTALL_MODE="interactive"
    elif [ "$INTERACTIVE_FLAG" = "no" ] || [ "${INSTALL_NONINTERACTIVE:-0}" = "1" ]; then
        INSTALL_MODE="non-interactive"
    elif [ -t 0 ] && [ -t 1 ]; then
        INSTALL_MODE="interactive"
    else
        INSTALL_MODE="non-interactive"
    fi
}

# --- Validation helpers -----------------------------------------------

# TKT-034 § 1.B.ii placeholder-pattern rejection (per ADR-014 Correction 7).
PLACEHOLDER_REGEX='^(YOUR_|CHANGE_ME|TEST_)'

is_placeholder_value() {
    local val="$1"
    if [ -z "$val" ]; then
        return 0
    fi
    if [[ "$val" =~ $PLACEHOLDER_REGEX ]]; then
        return 0
    fi
    if [ "$val" = "test-token-placeholder" ] || [ "$val" = "test-user-placeholder" ]; then
        return 0
    fi
    return 1
}

validate_telegram_allowed_users() {
    local val="$1"
    if [[ "$val" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
        return 0
    fi
    return 1
}

validate_telegram_user_id() {
    local val="$1"
    if [[ "$val" =~ ^[0-9]+$ ]]; then
        return 0
    fi
    return 1
}

validate_repo_url() {
    # TKT-034 § 1.A.iii / B.ii: token-bearing URL rejected; bare HTTPS only.
    local val="$1"
    if [[ "$val" =~ ^https://[^@/]+@ ]]; then
        return 1
    fi
    if [[ "$val" =~ ^https://github\.com/[^/]+/[^/]+(\.git)?$ ]]; then
        return 0
    fi
    return 1
}

validate_omniroute_base_url() {
    local val="$1"
    if [[ "$val" =~ ^https:// ]]; then
        return 0
    fi
    if [[ "$val" =~ ^http://127\.0\.0\.1: ]] || [[ "$val" =~ ^http://localhost: ]]; then
        return 0
    fi
    return 1
}

# --- Network probe stubs ----------------------------------------------
# TKT-034 § 4 AC-11: all probes are stubbed via INSTALL_FIXTURE_PROBES=1
# (used by tests). Real network calls only when neither DRY_RUN nor
# fixture-probes are set.

probe_telegram_get_me() {
    local token="$1"
    if [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE: probe_telegram_get_me stubbed PASS"
        return 0
    fi
    local code
    code=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 10 "https://api.telegram.org/bot${token}/getMe" 2>/dev/null) || code="000"
    [ "$code" = "200" ]
}

probe_github_user() {
    local token="$1"
    if [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE: probe_github_user stubbed PASS"
        return 0
    fi
    local code
    code=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 10 -H "Authorization: token ${token}" "https://api.github.com/user" 2>/dev/null) || code="000"
    [ "$code" = "200" ]
}

probe_omniroute_models() {
    local base_url="$1"
    local key="$2"
    if [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE: probe_omniroute_models stubbed PASS"
        return 0
    fi
    local code
    code=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 10 -H "Authorization: Bearer ${key}" "${base_url}/models" 2>/dev/null) || code="000"
    [ "$code" = "200" ]
}

probe_openrouter_key() {
    local key="$1"
    if [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE: probe_openrouter_key stubbed PASS"
        return 0
    fi
    local code
    code=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 10 -H "Authorization: Bearer ${key}" "https://openrouter.ai/api/v1/auth/key" 2>/dev/null) || code="000"
    [ "$code" = "200" ]
}

probe_repo_reachable() {
    local url="$1"
    if [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE: probe_repo_reachable stubbed PASS"
        return 0
    fi
    git ls-remote --heads "$url" >/dev/null 2>&1
}

# --- Generic prompt helpers -------------------------------------------

abort_install() {
    # TKT-034 § 4 AC-4 (c): error message names the env-var only, never the
    # rejected value.
    local env_var="$1"
    local reason="$2"
    log "FATAL: prompt aborted for ${env_var}: ${reason}"
    log "Re-run with --non-interactive and pre-set ${env_var} in the environment to bypass."
    exit 1
}

prompt_visible() {
    # $1 = env-var name; $2 = purpose; $3 = default (or empty); $4 = validator
    # function name; sets PROMPT_VALUE on success; aborts on retry exhaustion.
    local env_var="$1"
    local purpose="$2"
    local default_val="$3"
    local validator="$4"
    local prompt_text
    if [ -n "$default_val" ]; then
        prompt_text="${env_var} (${purpose}) [default: ${default_val}]: "
    else
        prompt_text="${env_var} (${purpose}): "
    fi
    local attempts=0
    local val
    while [ "$attempts" -lt "$INSTALL_PROMPT_RETRIES" ]; do
        attempts=$((attempts + 1))
        printf '%s' "$prompt_text"
        IFS= read -r val || val=""
        if [ -z "$val" ] && [ -n "$default_val" ]; then
            val="$default_val"
        fi
        if "$validator" "$val"; then
            PROMPT_VALUE="$val"
            return 0
        fi
        echo "  Validation failed for ${env_var} (attempt ${attempts}/${INSTALL_PROMPT_RETRIES})"
    done
    abort_install "$env_var" "validation failed after ${INSTALL_PROMPT_RETRIES} attempts"
}

prompt_secret() {
    # Like prompt_visible but with terminal echo disabled.
    local env_var="$1"
    local purpose="$2"
    local validator="$3"
    local prompt_text="${env_var} (${purpose}, hidden): "
    local attempts=0
    local val
    while [ "$attempts" -lt "$INSTALL_PROMPT_RETRIES" ]; do
        attempts=$((attempts + 1))
        printf '%s' "$prompt_text"
        IFS= read -rs val || val=""
        printf '\n'
        if "$validator" "$val"; then
            PROMPT_VALUE="$val"
            return 0
        fi
        echo "  Validation failed for ${env_var} (attempt ${attempts}/${INSTALL_PROMPT_RETRIES})"
    done
    abort_install "$env_var" "validation failed after ${INSTALL_PROMPT_RETRIES} attempts"
}

# --- 11 prompt functions per TKT-034 § 1.B.ii -------------------------

prompt_telegram_bot_token() {
    eval 'v_telegram() { local val="$1"; if is_placeholder_value "$val"; then return 1; fi; probe_telegram_get_me "$val"; }'
    prompt_secret "TELEGRAM_BOT_TOKEN" "Telegram bot token from @BotFather" v_telegram
    TELEGRAM_BOT_TOKEN="$PROMPT_VALUE"
    export TELEGRAM_BOT_TOKEN
}

prompt_telegram_allowed_users() {
    eval 'v_tau() { local val="$1"; if is_placeholder_value "$val"; then return 1; fi; validate_telegram_allowed_users "$val"; }'
    prompt_visible "TELEGRAM_ALLOWED_USERS" "Comma-separated numeric Telegram user IDs" "" v_tau
    TELEGRAM_ALLOWED_USERS="$PROMPT_VALUE"
    export TELEGRAM_ALLOWED_USERS
}

prompt_devassist_founder_telegram_user_id() {
    # AC: Founder ID MUST appear in TELEGRAM_ALLOWED_USERS.
    eval 'v_dfuid() {
        local val="$1"
        if is_placeholder_value "$val"; then return 1; fi
        if ! validate_telegram_user_id "$val"; then return 1; fi
        case ",${TELEGRAM_ALLOWED_USERS}," in
            *",${val},"*) return 0 ;;
            *) return 1 ;;
        esac
    }'
    prompt_visible "DEVASSIST_FOUNDER_TELEGRAM_USER_ID" "Numeric Telegram user ID (must be in TELEGRAM_ALLOWED_USERS)" "" v_dfuid
    DEVASSIST_FOUNDER_TELEGRAM_USER_ID="$PROMPT_VALUE"
    export DEVASSIST_FOUNDER_TELEGRAM_USER_ID
}

prompt_github_token_pat() {
    eval 'v_gt() { local val="$1"; if is_placeholder_value "$val"; then return 1; fi; probe_github_user "$val"; }'
    prompt_secret "GITHUB_TOKEN" "Fine-grained GitHub PAT (Contents:write, Pull requests:write)" v_gt
    GITHUB_TOKEN="$PROMPT_VALUE"
    export GITHUB_TOKEN
}

prompt_github_token_ssh() {
    # TKT-034 § 1.B.ii GH-auth=ssh alternative path. Generate an ED25519
    # keypair under /home/devassist/.ssh, instruct the operator to add it
    # to GitHub at https://github.com/settings/keys, then prompt with a
    # bounded read until ssh -T succeeds (or timeout).
    log "Generating ED25519 keypair for devassist@github SSH transport..."
    if [ "$DRY_RUN" = "0" ]; then
        local ssh_dir="/home/devassist/.ssh"
        mkdir -p "$ssh_dir"
        chown devassist:devassist "$ssh_dir"
        chmod 0700 "$ssh_dir"
        if [ ! -f "${ssh_dir}/id_ed25519" ]; then
            sudo -u devassist ssh-keygen -t ed25519 -N "" -f "${ssh_dir}/id_ed25519" -C "devassist@$(hostname)"
        fi
        echo "Public key (paste into https://github.com/settings/keys with read/write scope):"
        cat "${ssh_dir}/id_ed25519.pub"
    else
        log "DRY_RUN: would generate ED25519 keypair for devassist"
    fi
    if [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE: skipping interactive 'Press ENTER once added' prompt for SSH-key flow"
    else
        printf 'Press ENTER once the SSH key is added on GitHub (timeout %ss): ' "$INSTALL_SSH_KEY_TIMEOUT_SECONDS"
        # shellcheck disable=SC2034 # _ is the conventional unused read target
        read -t "$INSTALL_SSH_KEY_TIMEOUT_SECONDS" -r _ || abort_install "GITHUB_SSH_KEY" "operator did not confirm SSH key add within ${INSTALL_SSH_KEY_TIMEOUT_SECONDS}s"
        if ! sudo -u devassist ssh -T -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 git@github.com 2>&1 | grep -q "successfully authenticated"; then
            abort_install "GITHUB_SSH_KEY" "SSH key not yet active on GitHub"
        fi
    fi
    # Even with SSH, the runtime REST API path still needs a PAT.
    prompt_github_token_pat
}

prompt_fireworks_api_key() {
    eval 'v_fak() { local val="$1"; if is_placeholder_value "$val"; then return 1; fi; probe_omniroute_models "${OMNIROUTE_BASE_URL:-'"$DEFAULT_OMNIROUTE_BASE_URL"'}" "$val"; }'
    prompt_secret "FIREWORKS_API_KEY" "OmniRoute auth key (per ADR-014 Correction 3)" v_fak
    FIREWORKS_API_KEY="$PROMPT_VALUE"
    OMNIROUTE_API_KEY="$FIREWORKS_API_KEY"
    export FIREWORKS_API_KEY OMNIROUTE_API_KEY
}

prompt_omniroute_base_url() {
    eval 'v_obu() { local val="$1"; validate_omniroute_base_url "$val"; }'
    prompt_visible "OMNIROUTE_BASE_URL" "OmniRoute base URL" "$DEFAULT_OMNIROUTE_BASE_URL" v_obu
    OMNIROUTE_BASE_URL="$PROMPT_VALUE"
    export OMNIROUTE_BASE_URL
}

prompt_openrouter_api_key() {
    # OPTIONAL: empty input accepted; non-empty validated by probe.
    eval 'v_ork() { local val="$1"; if [ -z "$val" ]; then return 0; fi; if is_placeholder_value "$val"; then return 1; fi; probe_openrouter_key "$val"; }'
    prompt_secret "OPENROUTER_API_KEY" "OpenRouter API key (OPTIONAL, press ENTER to skip)" v_ork
    OPENROUTER_API_KEY="$PROMPT_VALUE"
    export OPENROUTER_API_KEY
}

prompt_hermes_devassist_repo_url() {
    eval 'v_hru() { local val="$1"; if ! validate_repo_url "$val"; then return 1; fi; probe_repo_reachable "$val"; }'
    prompt_visible "HERMES_DEVASSIST_REPO_URL" "developer-assistant repo HTTPS URL" "$DEFAULT_HERMES_DEVASSIST_REPO_URL" v_hru
    HERMES_DEVASSIST_REPO_URL="$PROMPT_VALUE"
    export HERMES_DEVASSIST_REPO_URL
}

prompt_hermes_devassist_repo_branch() {
    eval 'v_hrb() { local val="$1"; if [ -z "$val" ]; then return 1; fi; if is_placeholder_value "$val"; then return 1; fi; return 0; }'
    prompt_visible "HERMES_DEVASSIST_REPO_BRANCH" "Branch to track (e.g. main)" "$DEFAULT_HERMES_DEVASSIST_REPO_BRANCH" v_hrb
    HERMES_DEVASSIST_REPO_BRANCH="$PROMPT_VALUE"
    export HERMES_DEVASSIST_REPO_BRANCH
}

prompt_operator_git_user_name() {
    eval 'v_ogun() { local val="$1"; if [ -z "$val" ]; then return 1; fi; if is_placeholder_value "$val"; then return 1; fi; return 0; }'
    prompt_visible "OPERATOR_GIT_USER_NAME" "git user.name for devassist" "$DEFAULT_OPERATOR_GIT_USER_NAME" v_ogun
    OPERATOR_GIT_USER_NAME="$PROMPT_VALUE"
    export OPERATOR_GIT_USER_NAME
}

prompt_operator_git_user_email() {
    local hostname_val default_email
    hostname_val="$(hostname 2>/dev/null || echo localhost)"
    default_email="devassist@${hostname_val}"
    eval 'v_ogue() { local val="$1"; if [ -z "$val" ]; then return 1; fi; if is_placeholder_value "$val"; then return 1; fi; if [[ "$val" =~ ^[^[:space:]@]+@[^[:space:]@]+$ ]]; then return 0; fi; return 1; }'
    prompt_visible "OPERATOR_GIT_USER_EMAIL" "git user.email for devassist" "$default_email" v_ogue
    OPERATOR_GIT_USER_EMAIL="$PROMPT_VALUE"
    export OPERATOR_GIT_USER_EMAIL
}

# --- Prompt-phase orchestration ---------------------------------------

prompt_phase_idempotent_skip() {
    # TKT-034 § 1.B.v / AC-7 (a): skip the prompt phase when the env file
    # exists, has TELEGRAM_BOT_TOKEN with a non-empty non-placeholder value,
    # AND every required env var is non-empty + non-placeholder.
    local env_file="${BASE}/secrets/SELF-DEPLOY.env"
    if [ ! -f "$env_file" ]; then
        return 1
    fi
    local v
    for var in TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS DEVASSIST_FOUNDER_TELEGRAM_USER_ID GITHUB_TOKEN FIREWORKS_API_KEY OMNIROUTE_BASE_URL HERMES_DEVASSIST_REPO_URL HERMES_DEVASSIST_REPO_BRANCH OPERATOR_GIT_USER_NAME OPERATOR_GIT_USER_EMAIL; do
        v=$(grep -E "^${var}=" "$env_file" 2>/dev/null | head -1 | cut -d= -f2-)
        if [ -z "$v" ] || is_placeholder_value "$v"; then
            return 1
        fi
    done
    log "Prompt phase short-circuited: ${env_file} already has all required env vars (idempotent)"
    return 0
}

run_interactive_prompts() {
    if prompt_phase_idempotent_skip; then
        return 0
    fi
    log "Entering interactive prompt phase (${INSTALL_PROMPT_RETRIES} retries per prompt)"
    prompt_telegram_bot_token
    prompt_telegram_allowed_users
    prompt_devassist_founder_telegram_user_id
    if [ "$GH_AUTH_MODE" = "ssh" ]; then
        prompt_github_token_ssh
    else
        prompt_github_token_pat
    fi
    prompt_omniroute_base_url
    prompt_fireworks_api_key
    prompt_openrouter_api_key
    prompt_hermes_devassist_repo_url
    prompt_hermes_devassist_repo_branch
    prompt_operator_git_user_name
    prompt_operator_git_user_email
}

validate_required_env_vars() {
    # TKT-034 § 1.B.iii non-interactive contract: all required env vars
    # MUST be set in the calling environment; missing aborts BEFORE any
    # filesystem write (defense against half-rendered env files).
    # In DRY_RUN mode the existing render_self_deploy_env placeholder
    # fallback fills missing vars (test-fixture compatibility); the
    # verify-self.sh `check_required_env_vars_present` invariant then
    # detects the placeholders and fails the post-install verify, which
    # is the right phase for that signal.
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: validate_required_env_vars skipped (placeholders allowed in fixture)"
        return 0
    fi
    if prompt_phase_idempotent_skip; then
        return 0
    fi
    local missing=""
    for var in TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS DEVASSIST_FOUNDER_TELEGRAM_USER_ID GITHUB_TOKEN FIREWORKS_API_KEY OMNIROUTE_BASE_URL HERMES_DEVASSIST_REPO_URL HERMES_DEVASSIST_REPO_BRANCH OPERATOR_GIT_USER_NAME OPERATOR_GIT_USER_EMAIL; do
        local v
        v="$(printenv "$var" 2>/dev/null || echo "")"
        if [ -z "$v" ]; then
            missing="${missing} ${var}"
        fi
    done
    if [ -n "$missing" ]; then
        log "FATAL: non-interactive mode requires all required env vars to be set; missing:${missing}"
        log "Re-run with --interactive to be prompted for each value."
        exit 1
    fi
}

# --- Prior-deploy detection (TKT-034 § 1.B.vii) -----------------------

detect_prior_deploy() {
    if [ "$FORCE_REINSTALL" = "1" ]; then
        log "Prior-deploy detection skipped (--force-reinstall)"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: prior-deploy detection skipped"
        return 0
    fi
    local found=""
    if [ -d /srv/devassist ]; then found="${found} /srv/devassist directory;"; fi
    if id devassist >/dev/null 2>&1; then found="${found} devassist system user;"; fi
    if [ -f /etc/systemd/system/devassist.target ]; then found="${found} devassist.target unit;"; fi
    if compgen -G "/etc/systemd/system/devassist-*.service" >/dev/null 2>&1; then
        found="${found} devassist-*.service unit(s);"
    fi
    if [ -n "$found" ]; then
        log "FATAL: Existing deploy detected:${found}"
        log "Run the cleanup runbook first; see docs/operations/cleanup-runbook.md (forthcoming) or the SO-relayed runbook from session-log § 5.2."
        log "To skip detection without cleanup (idempotent re-run only), invoke with --force-reinstall."
        exit 1
    fi
}

# --- VPS prereq verification (TKT-034 § 1.B.viii) ---------------------

verify_prereqs() {
    # 8 checks in fixed order; first failure short-circuits.
    if [ "$DRY_RUN" = "1" ] || [ "${INSTALL_FIXTURE_PROBES:-0}" = "1" ]; then
        log "FIXTURE/DRY_RUN: verify_prereqs (8 checks) skipped"
        return 0
    fi
    log "verify_prereqs: 8 checks in order OS/sudo/network/disk/CLIs/Docker/Python/gh"
    # 1. OS
    local os_id os_rel
    os_id=$(lsb_release -is 2>/dev/null || echo "unknown")
    os_rel=$(lsb_release -rs 2>/dev/null || echo "unknown")
    if [ "$os_id" != "Ubuntu" ] || [ "$os_rel" != "22.04" ]; then
        log "FATAL: prereq OS: expected Ubuntu 22.04, got ${os_id} ${os_rel}"
        exit 1
    fi
    log "  PASS prereq OS: Ubuntu 22.04"
    # 2. Sudo posture
    if [ "$(id -u)" != "0" ]; then
        log "FATAL: prereq sudo: must run under sudo (id -u != 0)"
        exit 1
    fi
    log "  PASS prereq sudo: id -u == 0"
    # 3. Network
    local code
    code=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 10 https://api.github.com 2>/dev/null) || code="000"
    if [ "$code" != "200" ]; then
        log "FATAL: prereq network: api.github.com unreachable (HTTP ${code})"
        exit 1
    fi
    log "  PASS prereq network: api.github.com reachable"
    # 4. Disk
    local avail_kb
    avail_kb=$(df --output=avail /srv 2>/dev/null | tail -1 | tr -d ' ')
    if [ -z "$avail_kb" ] || [ "$avail_kb" -lt 5000000 ]; then
        log "FATAL: prereq disk: /srv has ${avail_kb:-0} KB available, need ≥ 5_000_000"
        exit 1
    fi
    log "  PASS prereq disk: /srv has ${avail_kb} KB available"
    # 5. Required CLIs
    local missing=""
    for cli in bash systemctl sqlite3 curl tar git python3 sudo lsb_release stat sha256sum useradd usermod chmod chown ln mkdir; do
        if ! command -v "$cli" >/dev/null 2>&1; then
            missing="${missing} ${cli}"
        fi
    done
    if [ -n "$missing" ]; then
        log "FATAL: prereq required-CLIs: missing:${missing}"
        exit 1
    fi
    log "  PASS prereq required-CLIs: all present"
    # 6. Docker
    if ! command -v docker >/dev/null 2>&1; then
        log "FATAL: prereq docker: command -v docker failed (apt-get install docker.io)"
        exit 1
    fi
    if ! systemctl is-active docker >/dev/null 2>&1; then
        log "FATAL: prereq docker: daemon inactive (systemctl start docker)"
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        log "FATAL: prereq docker: 'docker info' failed (check daemon socket)"
        exit 1
    fi
    if ! getent group docker >/dev/null 2>&1; then
        log "FATAL: prereq docker: docker group missing (groupadd docker)"
        exit 1
    fi
    if id devassist >/dev/null 2>&1; then
        if ! getent group docker | grep -qw devassist; then
            log "FATAL: prereq docker: devassist not in docker supplementary group (usermod -aG docker devassist)"
            exit 1
        fi
    fi
    log "  PASS prereq docker: daemon active, group present"
    # 7. Python
    local pyver
    pyver=$(python3 --version 2>&1 | awk '{print $2}')
    local pymaj pymin
    pymaj=$(echo "$pyver" | cut -d. -f1)
    pymin=$(echo "$pyver" | cut -d. -f2)
    if [ "$pymaj" -lt 3 ] || { [ "$pymaj" = "3" ] && [ "$pymin" -lt 11 ]; }; then
        log "FATAL: prereq python: ${pyver} below 3.11"
        exit 1
    fi
    log "  PASS prereq python: ${pyver}"
    # 8. gh CLI
    if ! command -v gh >/dev/null 2>&1; then
        log "FATAL: prereq gh: gh CLI missing (apt-get install gh after adding GitHub CLI APT repo)"
        exit 1
    fi
    local ghver
    ghver=$(gh --version 2>/dev/null | head -1 | awk '{print $3}')
    local ghmaj ghmin
    ghmaj=$(echo "$ghver" | cut -d. -f1)
    ghmin=$(echo "$ghver" | cut -d. -f2)
    if [ "$ghmaj" -lt 2 ] || { [ "$ghmaj" = "2" ] && [ "$ghmin" -lt 40 ]; }; then
        log "FATAL: prereq gh: ${ghver} below 2.40.0"
        exit 1
    fi
    log "  PASS prereq gh: ${ghver}"
    log "verify_prereqs: all 8 checks passed"
}

# --- gh CLI install + auth (TKT-034 § 1.A.i) --------------------------

install_gh_cli() {
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would install gh CLI via APT"
        return 0
    fi
    if command -v gh >/dev/null 2>&1; then
        log "gh CLI already installed: $(gh --version 2>/dev/null | head -1)"
        return 0
    fi
    log "Installing gh CLI via APT..."
    type -p curl >/dev/null || apt-get install -y curl
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
    local arch
    arch=$(dpkg --print-architecture)
    echo "deb [arch=${arch} signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list
    apt-get update
    apt-get install -y gh
    log "gh CLI installed: $(gh --version | head -1)"
}

authenticate_gh_for_devassist() {
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would authenticate gh as devassist via stdin token"
        # Fixture: write a stub auth-state marker so verify-self can check
        # the dry-run prefix as if gh were authenticated.
        local fixture_marker="${PREFIX}/home/devassist/.config/gh/hosts.yml"
        mkdir -p "$(dirname "$fixture_marker")"
        cat > "$fixture_marker" <<'GH'
github.com:
    git_protocol: https
    user: devassist-fixture
    oauth_token: redacted-by-fixture
GH
        return 0
    fi
    local token="${GITHUB_TOKEN:-}"
    if [ -z "$token" ]; then
        log "FATAL: GITHUB_TOKEN not set; cannot authenticate gh"
        exit 1
    fi
    # TKT-034 § 4 AC-2 (a): token via stdin redirection, NOT --token <val>.
    log "Authenticating gh as devassist (token via stdin)"
    sudo -u devassist env HOME=/home/devassist gh auth login \
        --hostname github.com --git-protocol https --with-token <<<"$token"
    sudo -u devassist env HOME=/home/devassist gh auth setup-git
    sudo -u devassist env HOME=/home/devassist git config --global \
        credential.helper '!gh auth git-credential'
}

configure_devassist_git_identity() {
    local user_name="${OPERATOR_GIT_USER_NAME:-${DEFAULT_OPERATOR_GIT_USER_NAME}}"
    local user_email
    user_email="${OPERATOR_GIT_USER_EMAIL:-devassist@$(hostname 2>/dev/null || echo localhost)}"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would configure devassist git identity (name=${user_name}, email=${user_email})"
        # Fixture: write ~devassist/.gitconfig under PREFIX so verify-self
        # tests can read it via the fixture check_devassist_git_identity.
        local fixture_home="${PREFIX}/home/devassist"
        mkdir -p "$fixture_home"
        cat > "${fixture_home}/.gitconfig" <<EOF
[user]
	name = ${user_name}
	email = ${user_email}
[credential]
	helper = !gh auth git-credential
EOF
        return 0
    fi
    sudo -u devassist env HOME=/home/devassist git config --global user.name "$user_name"
    sudo -u devassist env HOME=/home/devassist git config --global user.email "$user_email"
}

# --- Shared-skills manifest renderer (TKT-034 § 1.A.iv) ---------------

render_shared_skills_manifest() {
    local repo_root
    repo_root="$(cd "${SCRIPT_DIR}/.." && pwd)"
    local skills_dst="${BASE}/shared-skills"
    local manifest_dir="${BASE}/state"
    local manifest="${manifest_dir}/shared-skills-manifest.json"
    local manifest_tmp="${manifest}.tmp.$$"
    local rendered_at
    rendered_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    local release_commit
    release_commit=$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || echo "unknown")
    mkdir -p "$manifest_dir" "$skills_dst"
    # TKT-034 v0.3.1 § 1.A.iv enforcement: silent fallback (e.g. recording
    # a sentinel SHA value like "absent_at_install_time" and continuing) is
    # explicitly disallowed. The on-disk source tree at
    # shared-skills/<skill>/SKILL.md is the single source of truth; absence
    # is a hard error, not a degradation path. Pre-validate the full set
    # before opening the manifest_tmp redirect so the FATAL log line lands
    # on stdout/journald rather than inside the staged JSON.
    local skill src_md
    for skill in $SHARED_SKILLS; do
        src_md="${repo_root}/shared-skills/${skill}/SKILL.md"
        if [ ! -f "$src_md" ]; then
            log "FATAL: shared-skills source missing: shared-skills/${skill}/SKILL.md"
            exit 1
        fi
    done
    {
        printf '{\n'
        printf '  "schema_version": "1.0",\n'
        printf '  "rendered_at": "%s",\n' "$rendered_at"
        printf '  "release_commit": "%s",\n' "$release_commit"
        printf '  "skills": {\n'
        local first=1
        local src_dir sha
        for skill in $SHARED_SKILLS; do
            src_dir="${repo_root}/shared-skills/${skill}"
            src_md="${src_dir}/SKILL.md"
            mkdir -p "${skills_dst}/${skill}"
            cp -r "${src_dir}/." "${skills_dst}/${skill}/" 2>/dev/null || true
            sha=$(sha256sum "$src_md" | awk '{print $1}')
            if [ "$first" = "1" ]; then
                first=0
            else
                printf ',\n'
            fi
            printf '    "%s": {"path": "shared-skills/%s/SKILL.md", "sha256_of_skill_md": "%s", "pinned_commit": "%s"}' \
                "$skill" "$skill" "$sha" "$release_commit"
        done
        printf '\n  }\n}\n'
    } > "$manifest_tmp"
    mv -f "$manifest_tmp" "$manifest"
    if [ "$DRY_RUN" = "0" ]; then
        chown -R devassist:devassist "$skills_dst" 2>/dev/null || true
        chown devassist:devassist "$manifest" 2>/dev/null || true
        chmod 0644 "$manifest"
    fi
    local count
    count=$(echo "$SHARED_SKILLS" | wc -w | tr -d ' ')
    log "Rendered shared-skills-manifest.json with ${count} custom skill entries (atomic mv)"
}

main() {
    parse_flags "$@"
    detect_install_mode

    log "install-self.sh v${SELF_DEPLOY_VERSION} starting (DRY_RUN=${DRY_RUN}, PREFIX=${PREFIX}, MODE=${INSTALL_MODE}, GH_AUTH=${GH_AUTH_MODE})"

    detect_prior_deploy
    verify_prereqs
    check_deps
    install_gh_cli
    if [ "$INSTALL_MODE" = "interactive" ]; then
        run_interactive_prompts
    else
        validate_required_env_vars
    fi
    create_users
    create_filesystem
    init_operational_db
    symlink_operational_db
    symlink_env_file
    render_self_deploy_env
    render_runtime_configs
    render_shared_skills_manifest
    authenticate_gh_for_devassist
    configure_devassist_git_identity
    install_hermes_agent
    install_dev_assist_cli
    install_worker_runner
    render_systemd_units
    write_journald_dropin
    run_verify

    log "Install complete. Runtimes are NOT started."
    echo ""
    echo "Install complete. Runtimes are NOT started."
    echo "To start, run: systemctl start devassist.target"
    echo "To verify, run: scripts/verify-self.sh"
    echo ""
    log "install-self.sh finished successfully"
}

# Only auto-run main when invoked directly, not when sourced (e.g. for
# unit-testing individual prompt functions per TKT-034 § 6).
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
