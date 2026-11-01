#!/bin/bash
# ==================================================================
# slurm/jobs/_revision_stage.sh
#
# Shared post-processing and revision-stage helpers for the SLURM
# drivers. Source this file AFTER slurm/jobs/_common.sh (it relies on
# safe_python, record_bash_failure, HORMUZ_PROJECT_ROOT, HORMUZ_LOG_DIR
# and HORMUZ_SAFE_PYTHON_RC from there).
#
# Functions
#   hormuz_stage_validation  <run_id> <stage_prefix>   Stage 4b: run_validation.py
#   hormuz_stage_export      <run_id> <stage_prefix>   Stage 5:  export_results.py
#   hormuz_stage_visualize   <run_id> <stage_prefix>   Stage 6:  visualize_results.py
#   hormuz_stage_postprocess <run_id> <stage_prefix>   4b + 5 + 6 in order
#   hormuz_stage_recover     <run_id> <stage_prefix> <recovery_report_dir>
#                                                      Rebuild per-cell records from data/outputs
#   hormuz_capture_pip_freeze <dest_file>              Snapshot the Python environment
#   hormuz_stage_revision    <run_id> <stage_prefix>   Stage 7: scripts/revision/build_all.py
#                                                      (+ optional backend_comparison.py)
#   hormuz_revision_summary  <run_id>                  Artefact listing for job summaries
#
# Every function is bash-best-effort: failures are recorded through
# safe_python / record_bash_failure and surfaced in the HORMUZ_*_RC
# variables below, but only hormuz_stage_recover propagates a non-zero
# return (nothing downstream is meaningful when recovery fails).
#
#   HORMUZ_VALIDATION_RC, HORMUZ_EXPORT_RC, HORMUZ_VIZ_RC,
#   HORMUZ_RECOVER_RC, HORMUZ_REVISION_RC, HORMUZ_BACKEND_RC
#
# Environment toggles (defaults in parentheses)
#   Stage 4b/5/6
#     HORMUZ_VALIDATION_FAIL_ON_ERROR (0)   run_validation.py --fail-on-error
#     HORMUZ_EXPORT_USE_LLM (1)             0 -> export_results.py --no-llm
#     HORMUZ_EXPORT_EXEC_SUMMARY_LLM (1)    0 -> export_results.py --no-exec-summary
#     HORMUZ_VIZ_NO_TIMESERIES (0)          1 -> visualize_results.py --no-timeseries
#   Recovery
#     HORMUZ_OUTPUTS_ROOT (<root>/data/outputs)
#     HORMUZ_RECOVER_OVERWRITE (0)          1 -> --overwrite-existing
#   Stage 7
#     HORMUZ_RUN_BASELINE (1)               run the deterministic analyst baseline + comparison
#     HORMUZ_BASELINE_FILE (<root>/configs/baselines/hormuz_2026_analyst.yaml)
#     HORMUZ_BASELINE_RUN_ID (baseline_analyst)
#     HORMUZ_BASELINE_OUTPUT_ROOT (<root>)  baseline state/report land under <root>/data/
#     HORMUZ_REPORT_DIR (<root>/data/reports/<run_id>)
#     HORMUZ_REVISION_OUT_DIR (<root>/docs/revision/runs/<run_id>)
#     HORMUZ_REVISION_SKIP ()               comma list forwarded to build_all.py --skip
#     HORMUZ_PIP_FREEZE_FILE (${HORMUZ_LOG_DIR}/pip_freeze.txt)
#     HORMUZ_BACKEND_REPORTS_ROOT / HORMUZ_BACKEND_STATE_ROOT (unset)
#                                           when set, also run backend_comparison.py
# ==================================================================

_hormuz_rev_root() {
    echo "${HORMUZ_PROJECT_ROOT:-$(pwd)}"
}

_hormuz_rev_log_dir() {
    echo "${HORMUZ_LOG_DIR:-$(_hormuz_rev_root)/slurm/logs}"
}

# ------------------------------------------------------------------
# Stage 4b: per-output validation (configs/validation_rules.yaml).
# ------------------------------------------------------------------
hormuz_stage_validation() {
    local run_id="${1:?run_id}" prefix="${2:?stage_prefix}"
    local root
    root="$(_hormuz_rev_root)"
    echo ""
    echo "════════════ Stage 4b: Output Validation ════════════"
    local args=( --run-id "$run_id" )
    if [[ "${HORMUZ_VALIDATION_FAIL_ON_ERROR:-0}" == "1" ]]; then
        args+=( --fail-on-error )
        echo "[validation] HORMUZ_VALIDATION_FAIL_ON_ERROR=1: the script exits 2 on any error finding."
    fi
    safe_python "${prefix}_04b_validation" 1 -- \
        python "${root}/slurm/scripts/run_validation.py" "${args[@]}"
    HORMUZ_VALIDATION_RC="${HORMUZ_SAFE_PYTHON_RC:-0}"
    if [[ "$HORMUZ_VALIDATION_RC" -ne 0 ]]; then
        echo "[validation] WARNING: validation exited ${HORMUZ_VALIDATION_RC}; see data/reports/${run_id}/validation.md."
    fi
    return 0
}

# ------------------------------------------------------------------
# Stage 5: quantitative CSV + qualitative narrative export.
# ------------------------------------------------------------------
hormuz_stage_export() {
    local run_id="${1:?run_id}" prefix="${2:?stage_prefix}"
    local root
    root="$(_hormuz_rev_root)"
    echo ""
    echo "════════════ Stage 5: Results Export (CSV + Qualitative) ════════════"
    local args=( --run-id "$run_id" )
    if [[ "${HORMUZ_EXPORT_USE_LLM:-1}" != "1" ]]; then
        args+=( --no-llm )
        echo "[export] HORMUZ_EXPORT_USE_LLM=0: qualitative narratives use deterministic templates."
    fi
    if [[ "${HORMUZ_EXPORT_EXEC_SUMMARY_LLM:-1}" != "1" ]]; then
        args+=( --no-exec-summary )
        echo "[export] HORMUZ_EXPORT_EXEC_SUMMARY_LLM=0: skipping the executive-summary LLM pass."
    fi
    safe_python "${prefix}_05_export" 1 -- \
        python "${root}/slurm/scripts/export_results.py" "${args[@]}"
    HORMUZ_EXPORT_RC="${HORMUZ_SAFE_PYTHON_RC:-0}"
    if [[ "$HORMUZ_EXPORT_RC" -ne 0 ]]; then
        echo "[export] WARNING: export exited ${HORMUZ_EXPORT_RC}; CSVs or qualitative reports may be incomplete."
    fi
    return 0
}

# ------------------------------------------------------------------
# Stage 6: figures + index.html dashboard.
# ------------------------------------------------------------------
hormuz_stage_visualize() {
    local run_id="${1:?run_id}" prefix="${2:?stage_prefix}"
    local root
    root="$(_hormuz_rev_root)"
    echo ""
    echo "════════════ Stage 6: Visualization (figures + dashboard) ════════════"
    if ! python -c "import matplotlib" >/dev/null 2>&1; then
        echo "[viz] matplotlib is not importable in this environment; figures will be skipped."
        echo "[viz] Install the plotting extras with: pip install -e \".[viz]\""
    fi
    local args=( --run-id "$run_id" )
    if [[ "${HORMUZ_VIZ_NO_TIMESERIES:-0}" == "1" ]]; then
        args+=( --no-timeseries )
        echo "[viz] HORMUZ_VIZ_NO_TIMESERIES=1: skipping per-CSV time-series PNGs."
    fi
    safe_python "${prefix}_06_visualize" 1 -- \
        python "${root}/slurm/scripts/visualize_results.py" "${args[@]}"
    HORMUZ_VIZ_RC="${HORMUZ_SAFE_PYTHON_RC:-0}"
    if [[ "$HORMUZ_VIZ_RC" -ne 0 ]]; then
        echo "[viz] WARNING: visualization exited ${HORMUZ_VIZ_RC}; figures may be incomplete."
    fi
    return 0
}

hormuz_stage_postprocess() {
    local run_id="${1:?run_id}" prefix="${2:?stage_prefix}"
    hormuz_stage_validation "$run_id" "$prefix"
    hormuz_stage_export "$run_id" "$prefix"
    hormuz_stage_visualize "$run_id" "$prefix"
    return 0
}

# ------------------------------------------------------------------
# Recovery: rebuild the per-cell record set of an earlier run from
# data/outputs/<scenario>/<model>/metadata.json (filtered by run_id).
# A dry run first puts the present / recovered / stale / missing totals
# in the job log; the real pass then writes
# <run_id>_model_recovered_<tier>_<scenario>_<model>.json records.
# The state dir is always the real data/pipeline_state, even when the
# caller redirected HORMUZ_STATE_DIR for its own failure records.
# ------------------------------------------------------------------
hormuz_stage_recover() {
    local run_id="${1:?run_id}" prefix="${2:?stage_prefix}" report_dir="${3:?recovery_report_dir}"
    local root
    root="$(_hormuz_rev_root)"
    local outputs_root="${HORMUZ_OUTPUTS_ROOT:-${root}/data/outputs}"
    local state_dir="${root}/data/pipeline_state"
    echo ""
    echo "════════════ Recovery: per-cell records from ${outputs_root} ════════════"
    if [[ ! -d "$outputs_root" ]]; then
        record_bash_failure "${prefix}_00_recover" 1 "data/outputs root not found: ${outputs_root}"
        echo "[recover] ERROR: ${outputs_root} does not exist; nothing to recover from."
        HORMUZ_RECOVER_RC=1
        return 1
    fi
    mkdir -p "$report_dir"
    local args=( --run-id "$run_id" --outputs-root "$outputs_root" --state-dir "$state_dir" --report-dir "$report_dir" )
    if [[ "${HORMUZ_RECOVER_OVERWRITE:-0}" == "1" ]]; then
        args+=( --overwrite-existing )
        echo "[recover] HORMUZ_RECOVER_OVERWRITE=1: existing records are replaced by the data/outputs copy."
    fi
    safe_python "${prefix}_00_recover_dry_run" 1 -- \
        python "${root}/scripts/revision/recover_run_from_outputs.py" "${args[@]}" --dry-run
    safe_python "${prefix}_00_recover" 0 -- \
        python "${root}/scripts/revision/recover_run_from_outputs.py" "${args[@]}"
    HORMUZ_RECOVER_RC=$?
    if [[ "$HORMUZ_RECOVER_RC" -ne 0 ]]; then
        echo "[recover] ERROR: recovery exited ${HORMUZ_RECOVER_RC}."
    else
        echo "[recover] Recovery report: ${report_dir}/recovery_${run_id}.md"
        echo "[recover] NOTE: synthesis.json is not rerun here; synthesis_outcomes.csv still reflects the"
        echo "[recover]       record set the LLM synthesis saw, while model_status.csv, quantitative_results.csv"
        echo "[recover]       and the coverage ledger reflect the recovered set."
    fi
    return "$HORMUZ_RECOVER_RC"
}

# ------------------------------------------------------------------
# Environment snapshot consumed by scripts/revision/software_versions.py.
# ------------------------------------------------------------------
hormuz_capture_pip_freeze() {
    local dest="${1:?dest_file}"
    mkdir -p "$(dirname "$dest")"
    if python -m pip freeze > "$dest" 2>/dev/null && [[ -s "$dest" ]]; then
        echo "[revision] pip freeze written to ${dest} ($(wc -l < "$dest" | tr -d ' ') packages)"
        return 0
    fi
    echo "[revision] pip freeze failed (non-fatal); the cluster column of software_versions.md stays empty."
    rm -f "$dest"
    return 0
}

# ------------------------------------------------------------------
# Stage 7: every revision artefact for one run via build_all.py.
# ------------------------------------------------------------------
hormuz_stage_revision() {
    local run_id="${1:?run_id}" prefix="${2:?stage_prefix}"
    local root log_dir
    root="$(_hormuz_rev_root)"
    log_dir="$(_hormuz_rev_log_dir)"

    : "${HORMUZ_RUN_BASELINE:=1}"
    : "${HORMUZ_BASELINE_FILE:=${root}/configs/baselines/hormuz_2026_analyst.yaml}"
    : "${HORMUZ_BASELINE_RUN_ID:=baseline_analyst}"
    : "${HORMUZ_BASELINE_OUTPUT_ROOT:=${root}}"
    : "${HORMUZ_REPORT_DIR:=${root}/data/reports/${run_id}}"
    : "${HORMUZ_REVISION_OUT_DIR:=${root}/docs/revision/runs/${run_id}}"
    : "${HORMUZ_REVISION_SKIP:=}"
    : "${HORMUZ_PIP_FREEZE_FILE:=${log_dir}/pip_freeze.txt}"
    export HORMUZ_RUN_BASELINE HORMUZ_BASELINE_FILE HORMUZ_BASELINE_RUN_ID HORMUZ_BASELINE_OUTPUT_ROOT
    export HORMUZ_REPORT_DIR HORMUZ_REVISION_OUT_DIR HORMUZ_REVISION_SKIP HORMUZ_PIP_FREEZE_FILE

    echo ""
    echo "════════════ Stage 7: Revision Artefacts ════════════"
    echo "[revision] run id:       ${run_id}"
    echo "[revision] report dir:   ${HORMUZ_REPORT_DIR}"
    echo "[revision] out dir:      ${HORMUZ_REVISION_OUT_DIR}"
    echo "[revision] runtime dir:  ${log_dir}"
    echo "[revision] baseline:     ${HORMUZ_RUN_BASELINE} (run id ${HORMUZ_BASELINE_RUN_ID}, output root ${HORMUZ_BASELINE_OUTPUT_ROOT})"
    if [[ -n "$HORMUZ_REVISION_SKIP" ]]; then
        echo "[revision] skipping:     ${HORMUZ_REVISION_SKIP}"
    fi
    if [[ ! -d "$HORMUZ_REPORT_DIR" ]]; then
        echo "[revision] WARNING: report dir ${HORMUZ_REPORT_DIR} does not exist; steps that need csv/ or synthesis.json will fail."
    fi
    mkdir -p "$HORMUZ_REVISION_OUT_DIR"

    hormuz_capture_pip_freeze "$HORMUZ_PIP_FREEZE_FILE"

    local args=(
        --run-id "$run_id"
        --report-dir "$HORMUZ_REPORT_DIR"
        --state-dir "${root}/data/pipeline_state"
        --out-dir "$HORMUZ_REVISION_OUT_DIR"
        --runtime-dir "$log_dir"
    )
    if [[ -s "$HORMUZ_PIP_FREEZE_FILE" ]]; then
        args+=( --pip-freeze "$HORMUZ_PIP_FREEZE_FILE" )
    fi
    if [[ "$HORMUZ_RUN_BASELINE" == "1" ]]; then
        args+=( --baseline "$HORMUZ_BASELINE_FILE"
                --baseline-run-id "$HORMUZ_BASELINE_RUN_ID"
                --baseline-output-root "$HORMUZ_BASELINE_OUTPUT_ROOT" )
    fi
    if [[ -n "$HORMUZ_REVISION_SKIP" ]]; then
        args+=( --skip "$HORMUZ_REVISION_SKIP" )
    fi

    # The revision scripts resolve relative defaults against the cwd and
    # effort_metrics / the pycge replay shell out to git in the repo, so
    # run from the project root.
    pushd "$root" >/dev/null || return 0
    safe_python "${prefix}_07_revision" 1 -- \
        python scripts/revision/build_all.py "${args[@]}"
    HORMUZ_REVISION_RC="${HORMUZ_SAFE_PYTHON_RC:-0}"

    HORMUZ_BACKEND_RC=0
    if [[ -n "${HORMUZ_BACKEND_REPORTS_ROOT:-}" ]]; then
        echo "[revision] backend comparison over ${HORMUZ_BACKEND_REPORTS_ROOT}"
        local bargs=( --reports-root "$HORMUZ_BACKEND_REPORTS_ROOT" --out-dir "$HORMUZ_REVISION_OUT_DIR" )
        if [[ -n "${HORMUZ_BACKEND_STATE_ROOT:-}" ]]; then
            bargs+=( --state-root "$HORMUZ_BACKEND_STATE_ROOT" )
        fi
        safe_python "${prefix}_07_backend_comparison" 1 -- \
            python scripts/revision/backend_comparison.py "${bargs[@]}"
        HORMUZ_BACKEND_RC="${HORMUZ_SAFE_PYTHON_RC:-0}"
    fi
    popd >/dev/null || true

    if [[ "$HORMUZ_REVISION_RC" -ne 0 ]]; then
        echo "[revision] WARNING: build_all.py exited ${HORMUZ_REVISION_RC}; see ${HORMUZ_REVISION_OUT_DIR}/build_all_report.json for the failing step(s)."
    else
        echo "[revision] all steps ok; report at ${HORMUZ_REVISION_OUT_DIR}/build_all_report.json"
    fi
    return 0
}

# ------------------------------------------------------------------
# Human-readable listing for the job summary block.
# ------------------------------------------------------------------
hormuz_revision_summary() {
    local run_id="${1:?run_id}"
    local root
    root="$(_hormuz_rev_root)"
    local out_dir="${HORMUZ_REVISION_OUT_DIR:-${root}/docs/revision/runs/${run_id}}"
    echo "  Revision rc:  ${HORMUZ_REVISION_RC:-skipped}"
    echo "  Revision out: ${out_dir}"
    if [[ -d "$out_dir" ]]; then
        local entry
        for entry in "$out_dir"/*; do
            [[ -e "$entry" ]] && echo "                  $(basename "$entry")"
        done
    fi
    if [[ "${HORMUZ_RUN_BASELINE:-1}" == "1" ]]; then
        echo "  Baseline:     ${HORMUZ_BASELINE_RUN_ID:-baseline_analyst} -> ${HORMUZ_BASELINE_OUTPUT_ROOT:-${root}}/data/reports/${HORMUZ_BASELINE_RUN_ID:-baseline_analyst}"
    fi
    if [[ -n "${HORMUZ_PIP_FREEZE_FILE:-}" && -f "${HORMUZ_PIP_FREEZE_FILE}" ]]; then
        echo "  pip freeze:   ${HORMUZ_PIP_FREEZE_FILE}"
    fi
    if [[ -n "${HORMUZ_BACKEND_REPORTS_ROOT:-}" ]]; then
        echo "  Backends rc:  ${HORMUZ_BACKEND_RC:-skipped}"
    fi
}
