#!/usr/bin/env bash
set -euo pipefail

SELF_DEPLOY_VERSION="0.2.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLES="orchestrator planner architect executor reviewer"
DRY_RUN="${ROLLBACK_DRY_RUN:-0}"
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
    echo "[${ts}] rollback-self: $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[${ts}] rollback-self: $*"
}

detect_running_units() {
    log "Detecting currently running units"
    RUNNING_UNITS=""
    for role in $ROLES; do
        local unit="devassist-${role}.service"
        local status
        if [ "$DRY_RUN" = "1" ]; then
            status="active"
        else
            status=$(systemctl is-active "$unit" 2>/dev/null) || status="inactive"
        fi
        if [ "$status" = "active" ]; then
            RUNNING_UNITS="${RUNNING_UNITS} ${unit}"
            log "  ${unit}: ${status}"
        else
            log "  ${unit}: ${status}"
        fi
    done
}

stop_target() {
    log "Stopping devassist.target"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would run systemctl stop devassist.target"
        return 0
    fi
    systemctl stop devassist.target || {
        log "WARN: systemctl stop devassist.target returned error; forcing"
        systemctl kill devassist.target 2>/dev/null || true
    }
    sleep 2
}

find_latest_backup() {
    LATEST_DB_BACKUP=""
    LATEST_TARBALL=""
    LATEST_DB_BACKUP=$(ls -1t "${BACKUP_DIR}"/operational-*.db 2>/dev/null | head -1)
    LATEST_TARBALL=$(ls -1t "${BACKUP_DIR}"/runtime-state-*.tar.gz 2>/dev/null | head -1) || LATEST_TARBALL=""
    if [ -z "$LATEST_DB_BACKUP" ]; then
        log "FATAL: no operational.db backup found in ${BACKUP_DIR}"
        echo "FATAL: no operational.db backup found. Rollback aborted."
        exit 1
    fi
    log "Latest DB backup: ${LATEST_DB_BACKUP}"
    log "Latest tarball: ${LATEST_TARBALL:-none}"
}

restore_operational_db() {
    local db="${BASE}/state/operational.db"
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would restore ${LATEST_DB_BACKUP} to ${db}"
        return 0
    fi
    log "Restoring operational.db from ${LATEST_DB_BACKUP}"
    local tmp="${db}.new"
    cp "$LATEST_DB_BACKUP" "$tmp"
    sqlite3 "$tmp" "PRAGMA quick_check;" | grep -q "ok" || {
        log "FATAL: backup operational.db quick_check failed; aborting restore"
        rm -f "$tmp"
        exit 1
    }
    fsync_file "$tmp"
    mv "$tmp" "$db"
    log "operational.db restored (atomic rename)"
}

fsync_file() {
    if command -v fsync >/dev/null 2>&1; then
        fsync "$1" 2>/dev/null || true
    elif command -v sync >/dev/null 2>&1; then
        sync 2>/dev/null || true
    fi
}

restore_runtime_state() {
    if [ -z "$LATEST_TARBALL" ]; then
        log "No runtime-state tarball found; skipping runtime state restore"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would restore runtime state from ${LATEST_TARBALL}"
        return 0
    fi
    log "Restoring runtime state from ${LATEST_TARBALL}"
    local tmp_dir
    tmp_dir=$(mktemp -d)
    tar xzf "$LATEST_TARBALL" -C "$tmp_dir"
    for role in $ROLES; do
        local runtime_dir="${BASE}/runtimes/${role}/.hermes"
        if [ -d "${tmp_dir}/${role}/memories" ]; then
            cp -a "${tmp_dir}/${role}/memories/." "${runtime_dir}/memories/" 2>/dev/null || true
            log "  Restored memories for ${role}"
        fi
        if [ -d "${tmp_dir}/${role}/sessions" ]; then
            cp -a "${tmp_dir}/${role}/sessions/." "${runtime_dir}/sessions/" 2>/dev/null || true
            log "  Restored sessions for ${role}"
        fi
        if [ -d "${tmp_dir}/${role}/cron" ]; then
            cp -a "${tmp_dir}/${role}/cron/." "${runtime_dir}/cron/" 2>/dev/null || true
            log "  Restored cron for ${role}"
        fi
    done
    rm -rf "$tmp_dir"
    log "Runtime state restored (memories, sessions, cron only; state.db NOT touched)"
}

flip_release_symlink() {
    local current="${BASE}/releases/current"
    local previous="${BASE}/releases/previous"
    if [ ! -L "$current" ]; then
        log "WARN: releases/current is not a symlink; cannot flip"
        return 0
    fi
    if [ ! -L "$previous" ] && [ ! -e "$previous" ]; then
        log "WARN: releases/previous does not exist; cannot flip"
        return 0
    fi
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would flip releases/current -> target of releases/previous"
        return 0
    fi
    local prev_target
    if ! prev_target=$(readlink -f "$previous" 2>/dev/null); then
        log "WARN: cannot read releases/previous target"
        return 0
    fi
    log "Flipping releases/current from $(readlink -f "$current") to ${prev_target}"
    ln -sfn "$prev_target" "$current"
    log "Release symlink flipped"
}

run_verify() {
    log "Running verify-self.sh against restored release"
    VERIFY_PHASE=pre-start \
        bash "${SCRIPT_DIR}/verify-self.sh"
    return $?
}

restart_units() {
    if [ "$DRY_RUN" = "1" ]; then
        log "DRY_RUN: would start devassist.target"
        return 0
    fi
    log "Restarting devassist.target"
    systemctl start devassist.target
    sleep 2
    log "devassist.target started"
}

main() {
    log "rollback-self.sh v${SELF_DEPLOY_VERSION} starting (DRY_RUN=${DRY_RUN})"

    detect_running_units
    stop_target
    find_latest_backup
    restore_operational_db
    restore_runtime_state
    flip_release_symlink

    if [ "$DRY_RUN" = "0" ]; then
        systemctl daemon-reload 2>/dev/null || true
    fi

    if run_verify; then
        log "Verify passed after rollback"
        restart_units
        log "Rollback complete. Units restarted."
        echo "Rollback complete. Units restarted after verify passed."
    else
        log "FATAL: verify failed after rollback; units NOT restarted"
        echo "Rollback restore completed but verify failed."
        echo "Units are NOT restarted. Inspect failures above and run verify-self.sh manually."
        exit 1
    fi

    log "rollback-self.sh finished"
}

main "$@"
