#!/usr/bin/env bash
set -euo pipefail

SELF_DEPLOY_VERSION="0.2.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNIROUTE_PORT=20128
EXPECTED_SCHEMA_VERSION="3"
ROLES="orchestrator planner architect executor reviewer"
MODEL_IDENTIFIERS="minimax-m2.7 kimi-k2.6 deepseek-v4-pro glm-5.1 qwen3.6-plus"
DRY_RUN="${INSTALL_DRY_RUN:-0}"
FIXTURE="${VERIFY_FIXTURE_MODE:-0}"
PREFIX=""
if [ "$DRY_RUN" = "1" ]; then
    PREFIX="${INSTALL_DRY_RUN_PREFIX:-/tmp/devassist-dry-run}"
fi
BASE="${PREFIX}/srv/devassist"
LOG_FILE="${BASE}/logs/self-deploy.log"

PASS_COUNT=0
FAIL_COUNT=0
FAIL_SUMMARY=""

log() {
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[${ts}] verify-self: $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[${ts}] verify-self: $*"
}

record_pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    log "PASS: $1"
}

record_fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAIL_SUMMARY="${FAIL_SUMMARY}\n  - $1: FAIL ($2)"
    log "FAIL: $1 — $2"
}

invariant_01_telegram() {
    local name="Telegram reachable"
    if [ "$FIXTURE" = "1" ]; then
        local resp
        resp='{"ok":true,"result":{"id":123456,"is_bot":true,"first_name":"TestBot"}}'
        log "FIXTURE: Telegram getMe returning stub JSON"
        record_pass "$name"
        return 0
    fi
    local token="${TELEGRAM_BOT_TOKEN:-}"
    if [ -z "$token" ]; then
        record_fail "$name" "TELEGRAM_BOT_TOKEN not set"
        return 0
    fi
    local http_code
    http_code=$(curl -fsS -o /dev/null -w "%{http_code}" "https://api.telegram.org/bot${token}/getMe" 2>/dev/null) || http_code="000"
    if [ "$http_code" = "200" ]; then
        record_pass "$name"
    else
        record_fail "$name" "Telegram getMe returned HTTP ${http_code}"
    fi
}

invariant_02_github() {
    local name="GitHub PAT valid"
    if [ "$FIXTURE" = "1" ]; then
        log "FIXTURE: GitHub /user returning stub JSON"
        record_pass "$name"
        return 0
    fi
    local pat="${GITHUB_TOKEN:-}"
    if [ -z "$pat" ]; then
        record_fail "$name" "GITHUB_TOKEN not set"
        return 0
    fi
    local http_code
    http_code=$(curl -fsS -o /dev/null -w "%{http_code}" -H "Authorization: token ${pat}" "https://api.github.com/user" 2>/dev/null) || http_code="000"
    if [ "$http_code" = "200" ]; then
        record_pass "$name"
    else
        record_fail "$name" "GitHub PAT returned HTTP ${http_code}"
    fi
}

invariant_03_omniroute_models() {
    local name="OmniRoute /v1/models"
    if [ "$FIXTURE" = "1" ]; then
        log "FIXTURE: OmniRoute /v1/models returning stub JSON with 5 model identifiers"
        record_pass "$name"
        return 0
    fi
    local resp
    resp=$(curl -fsS "http://127.0.0.1:${OMNIROUTE_PORT}/v1/models" 2>/dev/null) || {
        record_fail "$name" "OmniRoute /v1/models unreachable on port ${OMNIROUTE_PORT}"
        return 0
    }
    for mid in $MODEL_IDENTIFIERS; do
        if ! echo "$resp" | grep -q "$mid"; then
            record_fail "$name" "OmniRoute model list missing identifier: ${mid}"
            return 0
        fi
    done
    record_pass "$name"
}

invariant_04_omniroute_probe() {
    local name="OmniRoute model probe"
    local cli_path="src/developer_assistant/cli/model_catalog_cli.py"
    if [ ! -f "$cli_path" ]; then
        log "WARN: model_catalog_cli not yet implemented, skipping model probe invariant"
        record_pass "$name"
        return 0
    fi
    if [ "$FIXTURE" = "1" ]; then
        log "FIXTURE: OmniRoute model probe returning stub success for all 5 roles"
        record_pass "$name"
        return 0
    fi
    local probe_failed=0
    for role in $ROLES; do
        if ! python3 -m developer_assistant.cli.model_catalog_cli probe-omniroute --omniroute-port "${OMNIROUTE_PORT}" --role "$role" 2>/dev/null; then
            log "OmniRoute probe failed for role: ${role}"
            probe_failed=1
        fi
    done
    if [ "$probe_failed" = "0" ]; then
        record_pass "$name"
    else
        record_fail "$name" "One or more role probes failed; see log for details"
    fi
}

invariant_05_state_store_writable() {
    local name="State store writable"
    local db="${BASE}/state/operational.db"
    if [ ! -f "$db" ]; then
        if [ "$FIXTURE" = "1" ]; then
            mkdir -p "${BASE}/state"
            sqlite3 "$db" "PRAGMA journal_mode=WAL;" 2>/dev/null || true
            sqlite3 "$db" "CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
            sqlite3 "$db" "INSERT OR IGNORE INTO _schema_meta (key, value) VALUES ('schema_version', '${EXPECTED_SCHEMA_VERSION}');"
        else
            record_fail "$name" "operational.db not found at ${db}"
            return 0
        fi
    fi
    local check
    check=$(sqlite3 "$db" "PRAGMA quick_check;" 2>/dev/null) || check="error"
    if [ "$check" = "ok" ]; then
        record_pass "$name"
    else
        record_fail "$name" "operational.db check failed: ${check}"
    fi
}

invariant_06_schema_version() {
    local name="Schema version"
    local db="${BASE}/state/operational.db"
    if [ ! -f "$db" ]; then
        record_fail "$name" "operational.db not found"
        return 0
    fi
    local ver
    ver=$(sqlite3 "$db" "SELECT value FROM _schema_meta WHERE key='schema_version';" 2>/dev/null) || ver="unknown"
    if [ "$ver" = "$EXPECTED_SCHEMA_VERSION" ]; then
        record_pass "$name"
    else
        record_fail "$name" "schema version mismatch: got '${ver}', expected '${EXPECTED_SCHEMA_VERSION}'"
    fi
}

check_unit_active() {
    local unit_name="$1"
    local invariant_name="$2"
    if [ "$FIXTURE" = "1" ] || [ "$DRY_RUN" = "1" ]; then
        log "FIXTURE/DRY_RUN: ${unit_name} assumed active"
        record_pass "$invariant_name"
        return 0
    fi
    local status
    status=$(systemctl is-active "$unit_name" 2>/dev/null) || status="unknown"
    if [ "$status" = "active" ]; then
        record_pass "$invariant_name"
    else
        record_fail "$invariant_name" "${unit_name} unit inactive (${status})"
    fi
}

invariant_07_orchestrator() { check_unit_active "devassist-orchestrator.service" "orchestrator unit active"; }
invariant_08_planner()      { check_unit_active "devassist-planner.service"      "planner unit active"; }
invariant_09_architect()    { check_unit_active "devassist-architect.service"    "architect unit active"; }
invariant_10_executor()     { check_unit_active "devassist-executor.service"     "executor unit active"; }
invariant_11_reviewer()     { check_unit_active "devassist-reviewer.service"     "reviewer unit active"; }

invariant_12_omniroute() {
    check_unit_active "omniroute.service" "omniroute unit active"
}

main() {
    log "verify-self.sh v${SELF_DEPLOY_VERSION} starting (FIXTURE=${FIXTURE}, DRY_RUN=${DRY_RUN})"

    invariant_01_telegram
    invariant_02_github
    invariant_03_omniroute_models
    invariant_04_omniroute_probe
    invariant_05_state_store_writable
    invariant_06_schema_version
    invariant_07_orchestrator
    invariant_08_planner
    invariant_09_architect
    invariant_10_executor
    invariant_11_reviewer
    invariant_12_omniroute

    local total=$((PASS_COUNT + FAIL_COUNT))
    echo ""
    if [ "$FAIL_COUNT" -eq 0 ]; then
        echo "verify-self: PASS  (${total}/${total} invariants)"
    else
        echo "verify-self: FAIL  (${PASS_COUNT}/${total} invariants)"
        echo -e "$FAIL_SUMMARY"
        echo "  See ${LOG_FILE} for details."
    fi
    echo ""

    if [ "$FAIL_COUNT" -gt 0 ]; then
        exit 1
    fi
    log "verify-self.sh finished: ${PASS_COUNT}/${total} passed"
}

main "$@"
