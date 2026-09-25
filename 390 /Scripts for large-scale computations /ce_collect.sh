#!/usr/bin/env bash
# =============================================================================
# ce_collect.sh — Collect and merge results from all completed Charity Engine
#                  jobs for the Thue-equation / elliptic-curve search project.
#
# Usage:
#   ./ce_collect.sh --mode all          # collect from all phases
#   ./ce_collect.sh --mode sieve        # collect sieve results only
#   ./ce_collect.sh --mode thue         # collect Thue parameterization results
#   ./ce_collect.sh --mode factor      # collect factorization search results
#   ./ce_collect.sh --mode mw          # collect Mordell-Weil sieve results
#   ./ce_collect.sh --auth KEY          # Charity Engine auth key
#
# Requirements: ce-cli installed and authenticated.
# =============================================================================

set -euo pipefail

# --- Defaults ---------------------------------------------------------------
AUTH_KEY="${CE_AUTH_KEY:-}"
MODE="all"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${PROJECT_DIR}/results"
MERGED_DIR="${PROJECT_DIR}/merged"

# Phase job-name prefixes (must match the submit scripts)
SIEVE_JOB="thue_sieve"
THUE_JOB="thue_param"
FACTOR_JOB="thue_factor"
MW_JOB="thue_mw"

# --- Parse arguments -------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)  MODE="$2";  shift 2 ;;
        --auth)  AUTH_KEY="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 --mode {all|sieve|thue|factor|mw} [--auth KEY]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$AUTH_KEY" ]]; then
    echo "ERROR: Charity Engine auth key not provided."
    echo "Set CE_AUTH_KEY env var or use --auth KEY."
    exit 1
fi

mkdir -p "$RESULTS_DIR" "$MERGED_DIR"

# --- Helper: download results for a given job name -------------------------
collect_phase() {
    local job_name="$1"
    local phase_label="$2"
    local phase_dir="${RESULTS_DIR}/${phase_label}"
    mkdir -p "$phase_dir"

    echo "========================================================"
    echo "  Collecting results for phase: ${phase_label}"
    echo "  Job name: ${job_name}"
    echo "========================================================"

    # List all completed work units for this job
    # ce-cli returns one WU ID per line
    local wu_list
    wu_list=$(ce-cli --auth "$AUTH_KEY" \
        --action list \
        --app "${job_name}" \
        --state completed \
        2>/dev/null || true)

    if [[ -z "$wu_list" ]]; then
        echo "  No completed work units found for ${job_name}."
        echo ""
        return 0
    fi

    local count=0
    while IFS= read -r wu_id; do
        [[ -z "$wu_id" ]] && continue
        echo "  Downloading WU ${wu_id}..."
        ce-cli --auth "$AUTH_KEY" \
            --action download \
            --wu "${wu_id}" \
            --destdir "${phase_dir}/${wu_id}" \
            2>/dev/null || {
                echo "    WARNING: Failed to download WU ${wu_id}, skipping."
                continue
            }
        count=$((count + 1))
    done <<< "$wu_list"

    echo "  Downloaded ${count} work units for phase ${phase_label}."
    echo ""
}

# --- Helper: merge results from a phase into a single CSV ------------------
merge_phase() {
    local phase_label="$1"
    local phase_dir="${RESULTS_DIR}/${phase_label}"
    local merged_file="${MERGED_DIR}/${phase_label}_merged.csv"

    echo "--- Merging phase: ${phase_label} ---"

    # CSV header
    echo "phase,wu_id,n,x,d_num,d_den,status,timestamp" > "$merged_file"

    if [[ ! -d "$phase_dir" ]] || [[ -z "$(ls -A "$phase_dir" 2>/dev/null)" ]]; then
        echo "  No data to merge for ${phase_label}."
        echo ""
        return 0
    fi

    for wu_dir in "$phase_dir"/*/; do
        [[ -d "$wu_dir" ]] || continue
        local wu_id
        wu_id=$(basename "$wu_dir")

        # Look for result files produced by ce_worker.sh
        # Expected format: JSON or CSV lines in result.json or output.csv
        local result_file=""
        for candidate in "result.json" "output.csv" "solution.txt" "result.txt"; do
            if [[ -f "${wu_dir}/${candidate}" ]]; then
                result_file="${wu_dir}/${candidate}"
                break
            fi
        done

        if [[ -z "$result_file" ]]; then
            echo "  WU ${wu_id}: no result file found, skipping."
            continue
        fi

        # Append each data line to the merged CSV
        # The worker writes lines like: n,x,d_num,d_den,status
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            [[ "$line" == \#* ]] && continue
            [[ "$line" == "{"* ]] && continue  # skip JSON headers
            echo "${phase_label},${wu_id},${line}" >> "$merged_file"
        done < "$result_file"
    done

    local line_count
    line_count=$(wc -l < "$merged_file")
    echo "  Merged ${line_count} lines into ${merged_file}"
    echo ""
}

# --- Helper: extract valid solutions from merged CSV -----------------------
extract_solutions() {
    local merged_file="$1"
    local solutions_file="${MERGED_DIR}/valid_solutions.csv"

    echo "--- Extracting valid solutions ---"

    # Header
    echo "phase,wu_id,n,x,d_num,d_den,status,timestamp" > "$solutions_file"

    if [[ ! -f "$merged_file" ]]; then
        echo "  No merged file to extract from."
        return 0
    fi

    # Filter lines where status contains "VALID" or "FOUND" or "SOLUTION"
    grep -iE "(VALID|FOUND|SOLUTION)" "$merged_file" >> "$solutions_file" 2>/dev/null || true

    local sol_count
    sol_count=$(($(wc -l < "$solutions_file") - 1))
    echo "  Found ${sol_count} valid solution(s) across all phases."
    echo ""
}

# --- Main logic ------------------------------------------------------------

case "$MODE" in
    all)
        collect_phase "$SIEVE_JOB"  "sieve"
        collect_phase "$THUE_JOB"   "thue"
        collect_phase "$FACTOR_JOB" "factor"
        collect_phase "$MW_JOB"     "mw"

        merge_phase "sieve"
        merge_phase "thue"
        merge_phase "factor"
        merge_phase "mw"
        ;;
    sieve)
        collect_phase "$SIEVE_JOB" "sieve"
        merge_phase "sieve"
        ;;
    thue)
        collect_phase "$THUE_JOB" "thue"
        merge_phase "thue"
        ;;
    factor)
        collect_phase "$FACTOR_JOB" "factor"
        merge_phase "factor"
        ;;
    mw)
        collect_phase "$MW_JOB" "mw"
        merge_phase "mw"
        ;;
    *)
        echo "ERROR: Unknown mode '${MODE}'."
        echo "Use: all, sieve, thue, factor, or mw."
        exit 1
        ;;
esac

# --- Final extraction ------------------------------------------------------
if [[ "$MODE" == "all" ]]; then
    # Combine all merged files into one for solution extraction
    combined="${MERGED_DIR}/all_merged.csv"
    echo "phase,wu_id,n,x,d_num,d_den,status,timestamp" > "$combined"
    for phase in sieve thue factor mw; do
        if [[ -f "${MERGED_DIR}/${phase}_merged.csv" ]]; then
            tail -n +2 "${MERGED_DIR}/${phase}_merged.csv" >> "$combined"
        fi
    done
    extract_solutions "$combined"
else
    extract_solutions "${MERGED_DIR}/${MODE}_merged.csv"
fi

# --- Summary ---------------------------------------------------------------
echo "========================================================"
echo "  COLLECTION SUMMARY"
echo "========================================================"
echo "  Results directory:  ${RESULTS_DIR}"
echo "  Merged directory:   ${MERGED_DIR}"
echo ""
if [[ -f "${MERGED_DIR}/valid_solutions.csv" ]]; then
    valid_count=$(($(wc -l < "${MERGED_DIR}/valid_solutions.csv") - 1))
    echo "  Valid solutions:    ${valid_count}"
    if [[ $valid_count -gt 0 ]]; then
        echo ""
        echo "  --- Valid solutions ---"
        cat "${MERGED_DIR}/valid_solutions.csv"
    fi
else
    echo "  No solutions file generated."
fi
echo ""
echo "  Done. Next step: run verify.py on any candidate solution."
echo "  Example:"
echo "    python verify.py --n <N> --x <X> --d-num <P> --d-den <Q>"
echo "========================================================"
