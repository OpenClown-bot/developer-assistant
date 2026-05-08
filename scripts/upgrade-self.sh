#!/usr/bin/env bash
set -euo pipefail

SELF_DEPLOY_VERSION="0.2.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLES="orchestrator planner architect executor reviewer"
DRY_RUN="${UPGRADE_DRY_RUN:-0}"
ACTIVATE="${1:-}"
PREFIX=""
if [ "$DRY_RUN" = "1" ]; then
    PREFIX="${INSTALL_DRY_RUN_PREFIX:-/tmp/devassist-dry-run}"
fi
BASE="${PREFIX}/srv/devassist"
BACKUP_DIR="${BASE}/state/backups"
LOG_FILE="${BASE}/logs/self-deploy.log"

log() {
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[${ts}] upgrade-self: $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[${ts}] upgrade-self: $*"
}

current_release_id() {
    local current="${BASE}/releases/current"
    if [ -L "$current" ]; then
        readlink -f "$current" 2>/dev/null | xargs basename 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}

take_operational_db_backup() {
    local db="${BASE}/state/operational.db"
    if [ ! -f "$db" ]; then
        log "FATAL: operational.db not found at ${db}"
        exit 1
    fi
    local ts
    ts=$(date -u '+%Y%m%d-%H%M%S')
    local backup="${BACKUP_DIR}/operational-${ts}.db"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would backup ${db} to ${backup}"
        mkdir -p "$BACKUP_DIR"
        return 0
    fi
    mkdir -p "$BACKUP_DIR"
    sqlite3 "$db" ".backup '${backup}'" || {
        log "FATAL: operational.db backup failed"
        exit 1
    }
    log "operational.db backed up to ${backup}"
}

take_runtime_state_backup() {
    local ts
    ts=$(date -u '+%Y%m%d-%H%M%S')
    local tarball="${BACKUP_DIR}/runtime-state-${ts}.tar.gz"
    local staging
    staging=$(mktemp -d)
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would create runtime-state tarball at ${tarball}"
        rm -rf "$staging"
        return 0
    fi
    log "Creating runtime-state tarball at ${tarball}"
    for role in $ROLES; do
        local rd="${BASE}/runtimes/${role}/.hermes"
        mkdir -p "${staging}/${role}"
        [ -d "${rd}/memories" ] && cp -a "${rd}/memories" "${staging}/${role}/" 2>/dev/null || true
        [ -d "${rd}/sessions" ] && cp -a "${rd}/sessions" "${staging}/${role}/" 2>/dev/null || true
        [ -d "${rd}/cron" ]    && cp -a "${rd}/cron"    "${staging}/${role}/" 2>/dev/null || true
    done
    mkdir -p "$BACKUP_DIR"
    tar czf "$tarball" -C "$staging" . 2>/dev/null || {
        log "WARN: runtime-state tarball creation had issues"
    }
    rm -rf "$staging"
    log "Runtime-state tarball created at ${tarball}"
}

fetch_new_release() {
    local new_id="${NEW_RELEASE_ID:-pending-$(date -u '+%Y%m%d-%H%M%S')}"
    local release_dir="${BASE}/releases/${new_id}"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would fetch new release ${new_id} into ${release_dir}"
        mkdir -p "$release_dir"
        return 0
    fi
    log "Fetching new release ${new_id} into ${release_dir}"
    mkdir -p "$release_dir"
    git clone --depth 1 "${HERMES_DEVASSIST_REPO_URL:-https://github.com/example/developer-assistant}" \
        --branch "${HERMES_DEVASSIST_REPO_BRANCH:-main}" "$release_dir" 2>/dev/null || {
        log "WARN: git clone into release dir failed; using empty dir"
    }
    log "New release fetched at ${release_dir}"
    NEW_RELEASE_DIR="$release_dir"
}

run_install_in_place() {
    log "Running install-self.sh against new release"
    INSTALL_DRY_RUN="${DRY_RUN}" \
    INSTALL_DRY_RUN_PREFIX="${PREFIX}" \
        "${SCRIPT_DIR}/install-self.sh" || {
        log "FATAL: install-self.sh against new release failed"
        exit 1
    }
    log "Install in-place completed"
}

run_verify() {
    log "Running verify-self.sh (pre-start phase)"
    VERIFY_PHASE=pre-start \
        bash "${SCRIPT_DIR}/verify-self.sh"
    return $?
}

activation_gate() {
    local old_id
    old_id=$(current_release_id)
    local new_id="${NEW_RELEASE_ID:-pending-$(date -u '+%Y%m%d-%H%M%S')}"
    log "Upgrade staged at release ${new_id}"
    log "Previous release: ${old_id}"
    log "Verify passed; awaiting activation"
    echo ""
    echo "Upgrade staged at release ${new_id}."
    echo "Previous release: ${old_id}."
    echo "Verify: passed."
    echo ""
    echo "To activate, run: scripts/upgrade-self.sh --activate"
    echo "To abort and rollback, run: scripts/rollback-self.sh"
    echo ""
}

do_activate() {
    local new_id="${NEW_RELEASE_ID:-pending-$(date -u '+%Y%m%d-%H%M%S')}"
    local new_release_dir="${BASE}/releases/${new_id}"
    local current="${BASE}/releases/current"
    local previous="${BASE}/releases/previous"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would stop devassist.target, flip symlink, start devassist.target"
        return 0
    fi
    log "Activation: stopping devassist.target"
    systemctl stop devassist.target || true
    sleep 2
    log "Saving current symlink target as previous"
    local cur_target
    cur_target=$(readlink -f "$current" 2>/dev/null) || cur_target=""
    if [ -n "$cur_target" ]; then
        ln -sfn "$cur_target" "$previous"
    fi
    log "Flipping releases/current to ${new_release_dir}"
    ln -sfn "$new_release_dir" "$current"
    systemctl daemon-reload 2>/dev/null || true
    log "Starting devassist.target"
    systemctl start devassist.target
    sleep 2
    log "Running post-activation verify"
    if ! run_verify; then
        log "WARN: post-activation verify failed; units are running with new release"
        echo "WARNING: post-activation verify failed. Units are running."
        echo "Inspect failures and consider rollback: scripts/rollback-self.sh"
    else
        log "Post-activation verify passed"
        echo "Activation complete. Verify passed."
    fi
}

main() {
    log "upgrade-self.sh v${SELF_DEPLOY_VERSION} starting (DRY_RUN=${DRY_RUN}, ACTIVATE=${ACTIVATE})"

    if [ "$ACTIVATE" = "--activate" ]; then
        do_activate
        log "upgrade-self.sh --activate finished"
        return 0
    fi

    local old_id
    old_id=$(current_release_id)
    log "Current release: ${old_id}"

    take_operational_db_backup
    take_runtime_state_backup
    fetch_new_release
    run_install_in_place

    if run_verify; then
        activation_gate
    else
        log "FATAL: verify failed after staging new release"
        echo "Upgrade verify failed. Do NOT activate."
        echo "To rollback, run: scripts/rollback-self.sh"
        exit 1
    fi

    log "upgrade-self.sh finished (awaiting --activate)"
}

main "$@"
