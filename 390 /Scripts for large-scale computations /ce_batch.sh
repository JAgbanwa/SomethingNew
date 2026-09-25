#!/usr/bin/env bash
# =============================================================================
# ce_batch.sh — Master orchestration script for the entire Charity Engine
#                search pipeline for Thue equations / elliptic curves.
#
# This script runs all phases sequentially:
#   1. Setup      — verify environment, build Docker image, generate tasks
#   2. Sieve      — submit modular sieve jobs (~1000 work units)
#   3. Thue       — submit Thue parameterization jobs (~500 work units)
#   4. Factor     — submit factorization search jobs (~2000 work units)
#   5. MW         — submit Mordell-Weil sieve jobs (~100 work units)
#   6. Collect    — download and merge all results
#
# Usage:
#   ./ce_batch.sh --auth KEY [--no-docker] [--skip-setup] [--collect-only]
#                [--phases "sieve thue factor mw"]
#
# Options:
#   --auth KEY          Charity Engine authentication key (required)
#   --no-docker         Skip Docker image build; run Python directly on host
#   --skip-setup        Skip the setup phase (if already done)
#   --collect-only      Only collect results from already-completed jobs
#   --phases LIST       Space-separated list of phases to submit (default: all)
#   --wait SECONDS      Poll interval for checking job completion (default: 300)
#   --timeout SECONDS   Maximum wait time for all jobs (default: 3600*48)
#   --help, -h          Show this help message
#
# Requirements:
#   - ce-cli installed and in PATH
#   - Charity Engine account with valid auth key
#   - Docker (unless --no-docker)
#   - Python 3.8+ with: numpy, sympy, gmpy2 (optional)
# =============================================================================

set -euo pipefail

# --- Defaults ---------------------------------------------------------------
AUTH_KEY="${CE_AUTH_KEY:-}"
USE_DOCKER=true
SKIP_SETUP=false
COLLECT_ONLY=false
WAIT_INTERVAL=300       # 5 minutes between polls
MAX_TIMEOUT=172800      # 48 hours
PHASES="sieve thue factor mw"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Color codes for output (disabled if not a terminal)
if [[ -t 1 ]]; then
    C_RED='\033[0;31m'
    C_GREEN='\033[0;32m'
    C_YELLOW='\033[1;33m'
    C_BLUE='\033[0;34m'
    C_NC='\033[0m'
else
    C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_NC=''
fi

log() {
    echo -e "${C_BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${C_NC} $*"
}

log_ok() {
    echo -e "${C_GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${C_NC} $*"
}

log_warn() {
    echo -e "${C_YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${C_NC} $*"
}

log_err() {
    echo -e "${C_RED}[$(date '+%Y-%m-%d %H:%M:%S')]${C_NC} $*" >&2
}

# --- Parse arguments --------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --auth)         AUTH_KEY="$2";        shift 2 ;;
        --no-docker)    USE_DOCKER=false;     shift ;;
        --skip-setup)   SKIP_SETUP=true;      shift ;;
        --collect-only) COLLECT_ONLY=true;    shift ;;
        --phases)       PHASES="$2";          shift 2 ;;
        --wait)         WAIT_INTERVAL="$2";   shift 2 ;;
        --timeout)      MAX_TIMEOUT="$2";     shift 2 ;;
        --help|-h)
            head -40 "$0"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$AUTH_KEY" ]]; then
    log_err "ERROR: Charity Engine auth key is required."
    echo "  Set CE_AUTH_KEY env var or use: --auth KEY"
    exit 1
fi

export CE_AUTH_KEY="$AUTH_KEY"

# --- Docker flag for sub-scripts --------------------------------------------
DOCKER_FLAG=""
if [[ "$USE_DOCKER" == true ]]; then
    DOCKER_FLAG="--docker"
else
    DOCKER_FLAG="--no-docker"
fi

# --- Phase 1: Setup ---------------------------------------------------------
if [[ "$SKIP_SETUP" == false ]] && [[ "$COLLECT_ONLY" == false ]]; then
    log "=== PHASE 1: SETUP ==="
    bash "${SCRIPT_DIR}/ce_setup.sh" \
        --auth "$AUTH_KEY" \
        $DOCKER_FLAG
    if [[ $? -ne 0 ]]; then
        log_err "Setup failed. Aborting."
        exit 1
    fi
    log_ok "Setup complete."
    echo ""
fi

# --- Submit scripts mapping -------------------------------------------------
declare -A SUBMIT_SCRIPTS=(
    [sieve]="ce_submit_sieve.sh"
    [thue]="ce_submit_thue.sh"
    [factor]="ce_submit_factor.sh"
    [mw]="ce_submit_mw.sh"
)

# --- Phase 2-5: Submit jobs -------------------------------------------------
if [[ "$COLLECT_ONLY" == false ]]; then
    for phase in $PHASES; do
        script="${SUBMIT_SCRIPTS[$phase]:-}"
        if [[ -z "$script" ]]; then
            log_warn "Unknown phase '${phase}', skipping."
            continue
        fi
        script_path="${SCRIPT_DIR}/${script}"
        if [[ ! -f "$script_path" ]]; then
            log_warn "Submit script not found: ${script_path}, skipping."
            continue
        fi

        log "=== PHASE: ${phase^^} ==="
        log "Submitting jobs via ${script}..."
        bash "$script_path" --auth "$AUTH_KEY"
        if [[ $? -ne 0 ]]; then
            log_warn "Phase ${phase} submission had issues. Continuing anyway."
        fi
        log_ok "Phase ${phase} submitted."
        echo ""
    done
fi

# --- Wait for completion (optional polling) ---------------------------------
if [[ "$COLLECT_ONLY" == false ]]; then
    log "=== WAITING FOR JOB COMPLETION ==="
    log "Polling interval: ${WAIT_INTERVAL}s, max timeout: ${MAX_TIMEOUT}s"

    elapsed=0
    all_done=false
    while [[ $elapsed -lt $MAX_TIMEOUT ]]; do
        # Check if all submitted jobs are completed
        pending=0
        for phase in $PHASES; do
            case "$phase" in
                sieve)  job="thue_sieve"  ;;
                thue)   job="thue_param"  ;;
                factor) job="thue_factor" ;;
                mw)     job="thue_mw"     ;;
                *)      continue ;;
            esac
            running=$(ce-cli --auth "$AUTH_KEY" \
                --action list \
                --app "$job" \
                --state running \
                2>/dev/null | wc -l || echo 0)
            pending=$((pending + running))
        done

        if [[ $pending -eq 0 ]]; then
            all_done=true
            log_ok "All jobs completed."
            break
        fi

        log "Still ${pending} job(s) running... (${elapsed}s elapsed)"
        sleep "$WAIT_INTERVAL"
        elapsed=$((elapsed + WAIT_INTERVAL))
    done

    if [[ "$all_done" == false ]]; then
        log_warn "Timeout reached. Some jobs may still be running."
        log_warn "Proceeding to collect whatever is available."
    fi
    echo ""
fi

# --- Phase 6: Collect results ------------------------------------------------
log "=== PHASE 6: COLLECT RESULTS ==="
bash "${SCRIPT_DIR}/ce_collect.sh" \
    --auth "$AUTH_KEY" \
    --mode all
if [[ $? -ne 0 ]]; then
    log_warn "Collection had issues. Check results/ and merged/ directories manually."
fi

# --- Final summary ----------------------------------------------------------
log "=============================================="
log "  PIPELINE COMPLETE"
log "=============================================="
log "  Results:  ${SCRIPT_DIR}/results/"
log "  Merged:   ${SCRIPT_DIR}/merged/"
log "  Solutions: ${SCRIPT_DIR}/merged/valid_solutions.csv"
log ""
log "  Next: verify any candidate with:"
log "    python verify.py --n <N> --x <X> --d-num <P> --d-den <Q>"
log "=============================================="
