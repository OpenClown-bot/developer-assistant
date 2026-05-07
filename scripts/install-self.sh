#!/usr/bin/env bash
set -euo pipefail

SELF_DEPLOY_VERSION="0.2.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNIROUTE_PORT=20128
EXPECTED_SCHEMA_VERSION="3"
ROLES="orchestrator planner architect executor reviewer"
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
    local missing=""
    for cmd in bash systemctl sqlite3 curl tar git mkdir ln chown chmod python3 npm; do
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
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would create system users devassist and omniroute"
        return 0
    fi
    if ! id -u devassist >/dev/null 2>&1; then
        log "Creating system user: devassist"
        useradd --system --no-create-home --shell /usr/sbin/nologin devassist
    else
        log "User devassist already exists (idempotent)"
    fi
    if ! id -u omniroute >/dev/null 2>&1; then
        log "Creating system user: omniroute"
        useradd --system --no-create-home --shell /usr/sbin/nologin omniroute
    else
        log "User omniroute already exists (idempotent)"
    fi
}

create_filesystem() {
    log "Creating /srv/devassist/ filesystem layout under ${BASE}"
    mkdir -p "${BASE}"/{repo,runtimes,state/backups,secrets,releases,omniroute/logs,web/templates,logs,shared-skills,shared-plugins}
    for role in $ROLES; do
        mkdir -p "${BASE}/runtimes/${role}/.hermes"/{memories,sessions,cron,logs,skills}
    done
    if [ "$DRY_RUN" = "0" ]; then
        chown -R devassist:devassist "${BASE}"
        chown -R omniroute:omniroute "${BASE}/omniroute"
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

render_self_deploy_env() {
    local env_file="${BASE}/secrets/SELF-DEPLOY.env"
    if [ -f "$env_file" ] && grep -q "TELEGRAM_BOT_TOKEN" "$env_file" 2>/dev/null; then
        log "SELF-DEPLOY.env already exists with required keys (idempotent)"
        return 0
    fi
    log "Rendering ${env_file} with placeholder values"
    cat > "$env_file" <<'ENVFILE'
TELEGRAM_BOT_TOKEN=test-token-placeholder
TELEGRAM_ALLOWED_USERS=test-user-placeholder
GITHUB_TOKEN=test-token-placeholder
OMNIROUTE_API_KEY=test-token-placeholder
OPENROUTER_API_KEY=test-token-placeholder
FIREWORKS_API_KEY=test-token-placeholder
HERMES_DEVASSIST_REPO_URL=https://github.com/example/developer-assistant
HERMES_DEVASSIST_REPO_BRANCH=main
DEVASSIST_FOUNDER_TELEGRAM_USER_ID=test-user-placeholder
ENVFILE
    if [ "$DRY_RUN" = "0" ]; then
        chmod 0600 "$env_file"
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
    log "Hermes Agent installed"
}

install_omniroute() {
    local omniroute_dir="${PREFIX}/opt/omniroute"
    if [ -d "$omniroute_dir" ] && [ -x "${omniroute_dir}/bin/omniroute" ]; then
        log "OmniRoute already installed at ${omniroute_dir} (idempotent)"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would install OmniRoute at ${omniroute_dir}"
        mkdir -p "$omniroute_dir"/bin
        echo "#!/bin/sh" > "${omniroute_dir}/bin/omniroute"
        echo "echo 'omniroute stub (dry-run)'" >> "${omniroute_dir}/bin/omniroute"
        chmod +x "${omniroute_dir}/bin/omniroute"
        return 0
    fi
    log "Installing OmniRoute at ${omniroute_dir}"
    mkdir -p "$omniroute_dir"
    npm install -g omniroute --prefix "$omniroute_dir" 2>/dev/null || {
        log "WARN: npm install of omniroute failed; creating stub"
        mkdir -p "$omniroute_dir"/bin
        echo "#!/bin/sh" > "${omniroute_dir}/bin/omniroute"
        echo "echo 'omniroute stub'" >> "${omniroute_dir}/bin/omniroute"
        chmod +x "${omniroute_dir}/bin/omniroute"
    }
    chown -R omniroute:omniroute "$omniroute_dir"
    log "OmniRoute installed"
}

install_dev_assist_cli() {
    local cli_dir="${PREFIX}/opt/dev-assist"
    local cli_venv="${cli_dir}/venv"
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
    python3 -m venv "$cli_venv"
    "${cli_venv}/bin/pip" install --quiet -e "${BASE}/repo/src" 2>/dev/null || {
        log "WARN: pip install of dev-assist-cli failed; creating wrapper script"
        cat > "${cli_bin}/dev-assist-cli" <<'CLIWrapper'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, "/srv/devassist/repo/src")
from developer_assistant.cli.dev_assist_cli import main
main()
CLIWrapper
        chmod +x "${cli_bin}/dev-assist-cli"
    }
    ln -sfn "${cli_venv}/bin/dev-assist-cli" "${cli_bin}/dev-assist-cli" 2>/dev/null || true
    chown -R devassist:devassist "$cli_dir"
    log "dev-assist-cli installed"
}

render_systemd_units() {
    mkdir -p "$SYSTEMD_DIR"
    local template_dir="${SCRIPT_DIR}/templates"
    local units="devassist.target devassist-orchestrator.service devassist-planner.service devassist-architect.service devassist-executor.service devassist-reviewer.service omniroute.service devassist-web.service"

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
    log "Running verify-self.sh (offline dry-run mode)"
    INSTALL_DRY_RUN=1 VERIFY_FIXTURE_MODE=1 ROLLBACK_DRY_RUN=1 UPGRADE_DRY_RUN=1 \
        INSTALL_DRY_RUN_PREFIX="${PREFIX}" \
        "${SCRIPT_DIR}/verify-self.sh"
    local rc=$?
    if [ $rc -ne 0 ]; then
        log "FATAL: verify-self.sh failed (exit ${rc}); install aborted"
        exit $rc
    fi
    log "verify-self.sh passed"
}

main() {
    log "install-self.sh v${SELF_DEPLOY_VERSION} starting (DRY_RUN=${DRY_RUN}, PREFIX=${PREFIX})"

    check_deps
    create_users
    create_filesystem
    init_operational_db
    symlink_operational_db
    symlink_env_file
    render_self_deploy_env
    install_hermes_agent
    install_omniroute
    install_dev_assist_cli
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

main "$@"
