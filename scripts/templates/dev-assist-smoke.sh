#!/usr/bin/env bash
# TKT-041 v0.1.1 AUDIT-003 — operator-facing smoke runner.
#
# Wraps dev-assist-cli smoke inject-message, polls AC-5..AC-6 completion,
# and emits a structured PASS/FAIL summary on stdout. Designed to run on
# a smoke-mode-marked VPS as the devassist system user. The marker file
# at /srv/devassist/state/smoke-mode.flag MUST exist (the CLI itself
# refuses smoke subcommands when absent).
#
# Usage:
#   dev-assist-smoke.sh [--timeout-claim-s N] [--timeout-result-s N]
#
# Exit codes:
#   0  smoke PASS (work_item claimed within N1 and completed within N2)
#   1  smoke FAIL (claim or result timeout, or DB / endpoint error)
#   2  smoke refused (marker file absent — environmental)

set -euo pipefail

SCRIPT_NAME="dev-assist-smoke"
MARKER_FILE_PATH="${DEVASSIST_SMOKE_MODE_MARKER_PATH:-/srv/devassist/state/smoke-mode.flag}"
DB_PATH="${DEV_ASSIST_DB_PATH:-/srv/devassist/state/operational.db}"
TIMEOUT_CLAIM_S=90       # AC-6 N1 default
TIMEOUT_RESULT_S=300     # AC-6 N2 default (Q-TKT-041-01 calibration TBD)
CLI="${DEV_ASSIST_CLI:-dev-assist-cli}"

while [ $# -gt 0 ]; do
    case "$1" in
        --timeout-claim-s) TIMEOUT_CLAIM_S="$2"; shift 2 ;;
        --timeout-result-s) TIMEOUT_RESULT_S="$2"; shift 2 ;;
        --cli) CLI="$2"; shift 2 ;;
        --marker-file) MARKER_FILE_PATH="$2"; shift 2 ;;
        --db-path) DB_PATH="$2"; shift 2 ;;
        -h|--help)
            cat <<USAGE
Usage: ${SCRIPT_NAME} [options]

Options:
  --timeout-claim-s N    AC-6 N1 timeout in seconds (default: 90)
  --timeout-result-s N   AC-6 N2 timeout in seconds (default: 300; pending
                         empirical N2 calibration via Q-TKT-041-01)
  --cli PATH             dev-assist-cli executable (default: dev-assist-cli)
  --marker-file PATH     Smoke-mode marker file (default: ${MARKER_FILE_PATH})
  --db-path PATH         operational.db (default: ${DB_PATH})
USAGE
            exit 0
            ;;
        *) echo "${SCRIPT_NAME}: FATAL: unknown flag '$1'" >&2; exit 2 ;;
    esac
done

emit() {
    # Emit one structured line. Sorted JSON keys for deterministic output.
    python3 -c "import json,sys; print(json.dumps(json.loads(sys.stdin.read()), sort_keys=True))" <<<"$1"
}

if [ ! -f "$MARKER_FILE_PATH" ]; then
    emit "{\"summary\":\"REFUSED\",\"error\":\"smoke_mode_not_enabled\",\"marker_file_path\":\"${MARKER_FILE_PATH}\"}"
    exit 2
fi

CORRELATION_ID="$(date -u +%s)-$$"
SYNTHETIC_TEXT="smoke-fixture-message-${CORRELATION_ID}"

# Step 1: inject.
INJECT_OUT="$("$CLI" --db-path "$DB_PATH" smoke --marker-file "$MARKER_FILE_PATH" inject-message --text "$SYNTHETIC_TEXT")"
WORK_ITEM_ID="$(python3 -c "import json,sys
try:
    print(json.loads(sys.stdin.read()).get('work_item_id') or '')
except Exception:
    print('')
" <<<"$INJECT_OUT")"

if [ -z "$WORK_ITEM_ID" ]; then
    emit "{\"summary\":\"FAIL\",\"stage\":\"inject\",\"raw\":${INJECT_OUT:-null}}"
    exit 1
fi

# Step 2: wait for claim (AC-6 N1).
CLAIM_OUT="$("$CLI" --db-path "$DB_PATH" smoke --marker-file "$MARKER_FILE_PATH" wait --work-item-id "$WORK_ITEM_ID" --until claimed --timeout-s "$TIMEOUT_CLAIM_S" || true)"
CLAIM_STATUS="$(python3 -c "import json,sys
try:
    print(json.loads(sys.stdin.read()).get('status') or '')
except Exception:
    print('')
" <<<"$CLAIM_OUT")"

if [ "$CLAIM_STATUS" != "ok" ]; then
    emit "{\"summary\":\"FAIL\",\"stage\":\"claim\",\"work_item_id\":${WORK_ITEM_ID},\"raw\":${CLAIM_OUT:-null}}"
    exit 1
fi

# Step 3: wait for result (AC-6 N2).
RESULT_OUT="$("$CLI" --db-path "$DB_PATH" smoke --marker-file "$MARKER_FILE_PATH" wait --work-item-id "$WORK_ITEM_ID" --until completed --timeout-s "$TIMEOUT_RESULT_S" || true)"
RESULT_STATUS="$(python3 -c "import json,sys
try:
    print(json.loads(sys.stdin.read()).get('status') or '')
except Exception:
    print('')
" <<<"$RESULT_OUT")"

if [ "$RESULT_STATUS" != "ok" ]; then
    emit "{\"summary\":\"FAIL\",\"stage\":\"result\",\"work_item_id\":${WORK_ITEM_ID},\"raw\":${RESULT_OUT:-null}}"
    exit 1
fi

emit "{\"summary\":\"PASS\",\"work_item_id\":${WORK_ITEM_ID},\"correlation_id\":\"${CORRELATION_ID}\",\"claim\":${CLAIM_OUT},\"result\":${RESULT_OUT}}"
exit 0
