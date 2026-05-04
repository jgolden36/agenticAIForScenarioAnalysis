#!/bin/bash
# ==================================================================
# Shared helpers for Hormuz pipeline SLURM jobs.
#
# Every per-stage sbatch script sources this file. It provides:
#
#   record_runtime_inventory <stage>
#       Probe the compute node for available runtimes (python, conda,
#       gams, julia, R, java, cuda, ...) and persist a JSON inventory
#       to slurm/logs/runtime-<stage>-<job>-<task>.json. The same
#       record is appended to data/pipeline_state/<run_id>_runtime.jsonl
#       so the synthesis stage can document *why* a model could not
#       run when a required runtime was unavailable.
#
#   record_bash_failure <stage> <exit_code> [message]
#       Persist a structured JSON record describing a bash-layer
#       failure (e.g. the python interpreter crashed before it could
#       write its own status file). Written to
#       data/pipeline_state/<run_id>_<stage>_bash_failure_<task>.json
#       and merged by run_synthesis.py alongside model-level results.
#
#   safe_python <stage> <continue_on_failure: 0|1> -- <python args...>
#       Run `python <args>` while:
#         - never killing the surrounding sbatch task on a Python crash
#           when continue_on_failure=1 (used by array jobs so the rest
#           of the array still runs and `--dependency=afterok` fires);
#         - recording any non-zero exit via record_bash_failure;
#         - re-raising the exit code when continue_on_failure=0
#           (used by single-job stages where there is no useful work
#           to continue with).
#
# Design note: this layer is intentionally orthogonal to the per-model
# error handling already implemented in slurm/scripts/run_model.py.
# That script catches NotImplementedError / missing adapter / generic
# exceptions per (scenario, model) pair and writes a status JSON. The
# helpers here are the *outer* safety net: they catch failures that
# happen before run_model.py can write its own record (interpreter
# crash, missing manifest, OOM, runtime not installed on this node).
# ==================================================================

# Resolve the project root (sbatch sets SLURM_SUBMIT_DIR; fall back to
# the common.sh location otherwise so the helper still works locally).
HORMUZ_PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
HORMUZ_STATE_DIR="${HORMUZ_PROJECT_ROOT}/data/pipeline_state"
HORMUZ_LOG_DIR="${HORMUZ_PROJECT_ROOT}/slurm/logs"

mkdir -p "$HORMUZ_STATE_DIR" "$HORMUZ_LOG_DIR"

# Best-effort UTC timestamp in ISO-8601.
_hormuz_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Compose a stable id for the current task. For non-array jobs the
# array-task fields are absent; we substitute "single".
_hormuz_task_tag() {
    local job="${SLURM_JOB_ID:-local}"
    local arr="${SLURM_ARRAY_TASK_ID:-single}"
    echo "${job}-${arr}"
}

# Probe whether a command is available on PATH.
_hormuz_have() {
    command -v "$1" >/dev/null 2>&1
}

# Capture the version line of a tool, or "missing".
#
# Safety notes:
#   * stdin is redirected from /dev/null so tools that drop into an
#     interactive REPL when stdin is a tty (e.g. `gams` with no args,
#     `R` without `--no-save`, some java agents) never block waiting
#     for input.
#   * A hard 10-second wall-clock timeout wraps every probe so a
#     hung vendor binary (e.g. GAMS checking a dead license server,
#     nvidia-smi on a driver that's mid-reset) cannot stall the whole
#     job. The timeout is best-effort: if `timeout` itself is missing
#     we fall back to unwrapped execution.
_hormuz_version() {
    local tool="$1"
    shift
    if _hormuz_have "$tool"; then
        local runner=()
        if command -v timeout >/dev/null 2>&1; then
            runner=(timeout --preserve-status 10s)
        fi
        # Run the version command, grab the first non-empty line, trim.
        ( "${runner[@]}" "$tool" "$@" </dev/null 2>&1 \
              | head -n 1 | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' ) \
            || echo "present (version probe failed/timeout)"
    else
        echo "missing"
    fi
}

# ------------------------------------------------------------------
# record_runtime_inventory <stage>
# ------------------------------------------------------------------
record_runtime_inventory() {
    local stage="${1:-unknown}"
    local tag
    tag="$(_hormuz_task_tag)"
    local out_per_task="${HORMUZ_LOG_DIR}/runtime-${stage}-${tag}.json"
    local out_run="${HORMUZ_STATE_DIR}/${HORMUZ_RUN_ID:-no_run_id}_runtime.jsonl"

    # Probe each runtime. None of these are required to succeed; the
    # whole point is to *document* what is and isn't available.
    local python_v conda_v gams_v julia_v r_v java_v cuda_v
    python_v=$(_hormuz_version python --version)
    conda_v=$(_hormuz_version conda --version)
    gams_v=$(_hormuz_version gams)            # `gams` with no args prints banner
    julia_v=$(_hormuz_version julia --version)
    r_v=$(_hormuz_version R --version)
    java_v=$(_hormuz_version java -version)
    cuda_v=$(_hormuz_version nvcc --version)

    local gpu_present="no"
    if _hormuz_have nvidia-smi && nvidia-smi -L >/dev/null 2>&1; then
        gpu_present="yes"
    fi

    local conda_env="${HORMUZ_CONDA_ENV:-unset}"
    local conda_active="${CONDA_DEFAULT_ENV:-none}"
    local hostname_v
    hostname_v=$(hostname 2>/dev/null || echo "unknown")

    # Note: we write JSON by hand to avoid a python dependency just for
    # logging. Strings are pre-escaped only for the few characters that
    # commonly appear in version banners (backslashes and double quotes).
    _hormuz_json_escape() {
        printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
    }

    {
        printf '{\n'
        printf '  "stage": "%s",\n'              "$(_hormuz_json_escape "$stage")"
        printf '  "run_id": "%s",\n'             "$(_hormuz_json_escape "${HORMUZ_RUN_ID:-}")"
        printf '  "timestamp": "%s",\n'          "$(_hormuz_timestamp)"
        printf '  "hostname": "%s",\n'           "$(_hormuz_json_escape "$hostname_v")"
        printf '  "slurm_job_id": "%s",\n'       "${SLURM_JOB_ID:-local}"
        printf '  "slurm_array_task_id": "%s",\n' "${SLURM_ARRAY_TASK_ID:-single}"
        printf '  "conda_env_requested": "%s",\n' "$(_hormuz_json_escape "$conda_env")"
        printf '  "conda_env_active": "%s",\n'    "$(_hormuz_json_escape "$conda_active")"
        printf '  "gpu_visible": "%s",\n'         "$gpu_present"
        printf '  "runtimes": {\n'
        printf '    "python": "%s",\n' "$(_hormuz_json_escape "$python_v")"
        printf '    "conda": "%s",\n'  "$(_hormuz_json_escape "$conda_v")"
        printf '    "gams": "%s",\n'   "$(_hormuz_json_escape "$gams_v")"
        printf '    "julia": "%s",\n'  "$(_hormuz_json_escape "$julia_v")"
        printf '    "R": "%s",\n'      "$(_hormuz_json_escape "$r_v")"
        printf '    "java": "%s",\n'   "$(_hormuz_json_escape "$java_v")"
        printf '    "cuda": "%s"\n'    "$(_hormuz_json_escape "$cuda_v")"
        printf '  }\n'
        printf '}\n'
    } > "$out_per_task"

    # Append a one-line JSON record for run-wide aggregation.
    # The synthesis stage reads this file to flag models whose required
    # runtime was unavailable.
    {
        printf '{"stage":"%s","tag":"%s","timestamp":"%s","hostname":"%s","gpu":"%s",' \
            "$stage" "$tag" "$(_hormuz_timestamp)" "$hostname_v" "$gpu_present"
        printf '"runtimes":{"python":"%s","conda":"%s","gams":"%s","julia":"%s","R":"%s","java":"%s","cuda":"%s"}}\n' \
            "$(_hormuz_json_escape "$python_v")" \
            "$(_hormuz_json_escape "$conda_v")" \
            "$(_hormuz_json_escape "$gams_v")" \
            "$(_hormuz_json_escape "$julia_v")" \
            "$(_hormuz_json_escape "$r_v")" \
            "$(_hormuz_json_escape "$java_v")" \
            "$(_hormuz_json_escape "$cuda_v")"
    } >> "$out_run"

    echo "[runtime] Inventory written to $out_per_task"
    echo "[runtime] gpu=${gpu_present} python=${python_v} gams=${gams_v} julia=${julia_v} R=${r_v} java=${java_v} cuda=${cuda_v}"
}

# ------------------------------------------------------------------
# record_bash_failure <stage> <exit_code> [message]
# ------------------------------------------------------------------
record_bash_failure() {
    local stage="${1:-unknown}"
    local exit_code="${2:-1}"
    local message="${3:-bash-layer failure (no message)}"
    local tag
    tag="$(_hormuz_task_tag)"
    local out="${HORMUZ_STATE_DIR}/${HORMUZ_RUN_ID:-no_run_id}_${stage}_bash_failure_${tag}.json"

    _hormuz_json_escape() {
        printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
    }

    {
        printf '{\n'
        printf '  "stage": "%s",\n'             "$(_hormuz_json_escape "$stage")"
        printf '  "run_id": "%s",\n'            "$(_hormuz_json_escape "${HORMUZ_RUN_ID:-}")"
        printf '  "slurm_job_id": "%s",\n'      "${SLURM_JOB_ID:-local}"
        printf '  "slurm_array_task_id": "%s",\n' "${SLURM_ARRAY_TASK_ID:-single}"
        printf '  "hostname": "%s",\n'          "$(_hormuz_json_escape "$(hostname 2>/dev/null || echo unknown)")"
        printf '  "timestamp": "%s",\n'         "$(_hormuz_timestamp)"
        printf '  "status": "bash_failure",\n'
        printf '  "exit_code": %s,\n'           "$exit_code"
        printf '  "error_message": "%s"\n'      "$(_hormuz_json_escape "$message")"
        printf '}\n'
    } > "$out"

    echo "[failure] Recorded bash failure for stage=${stage} task=${tag} exit=${exit_code}: ${message}"
    echo "[failure] $out"
}

# ------------------------------------------------------------------
# safe_python <stage> <continue_on_failure: 0|1> -- python <args...>
# ------------------------------------------------------------------
# Runs the given command. On non-zero exit, records a bash failure and
# either swallows the exit (continue_on_failure=1) or re-raises it
# (continue_on_failure=0). Designed so array jobs never abort the whole
# `--dependency=afterok` chain because of one task's interpreter crash.
safe_python() {
    local stage="${1:-unknown}"
    local cont="${2:-0}"
    shift 2
    if [[ "${1:-}" == "--" ]]; then
        shift
    fi

    echo "[safe_python] stage=${stage} continue_on_failure=${cont} cmd: $*"

    # Remember whether the caller had `set -e` enabled so we can
    # restore it; we must not short-circuit on the python exit code.
    local _had_errexit=0
    case $- in *e*) _had_errexit=1 ;; esac
    set +e
    "$@"
    local rc=$?
    if [[ "$_had_errexit" == "1" ]]; then
        set -e
    fi

    if [[ $rc -ne 0 ]]; then
        record_bash_failure "$stage" "$rc" "Python invocation exited with code $rc: $*"
        if [[ "$cont" == "1" ]]; then
            echo "[safe_python] continue_on_failure=1 -> sbatch task will exit 0 to preserve dependency chain."
            return 0
        else
            echo "[safe_python] continue_on_failure=0 -> propagating exit code $rc."
            return "$rc"
        fi
    fi

    echo "[safe_python] stage=${stage} completed successfully."
    return 0
}

# ------------------------------------------------------------------
# hormuz_activate_conda [env_name]
# ------------------------------------------------------------------
# Sources the conda shell hook (conda init) and activates the requested
# environment. Bare `conda activate` does NOT work in non-interactive
# sbatch scripts because `conda activate` is a shell function defined
# only after `etc/profile.d/conda.sh` is sourced -- without this the
# script either errors immediately or silently runs a system python
# that doesn't have the pipeline dependencies installed.
#
# Returns 0 on success, non-zero on failure. The caller is expected to
# decide whether to record a bash failure and abort.
# ------------------------------------------------------------------
hormuz_activate_conda() {
    local env="${1:-${HORMUZ_CONDA_ENV:-hormuz}}"

    # Locate the conda binary if CONDA_EXE isn't already set by the
    # environment module system.
    if [[ -z "${CONDA_EXE:-}" ]] && command -v conda >/dev/null 2>&1; then
        CONDA_EXE="$(command -v conda)"
        export CONDA_EXE
    fi

    if [[ -z "${CONDA_EXE:-}" ]]; then
        echo "[conda] no conda binary on PATH; cannot activate env '${env}'"
        return 1
    fi
    echo "[conda] using CONDA_EXE=${CONDA_EXE}"

    # Source the conda shell hook so `conda activate` becomes available.
    # `conda info --base` can stall on a cold network filesystem; wrap
    # it in a 60-second timeout so a misbehaving mount shows up as an
    # error rather than a silent hang.
    local conda_base
    local base_runner=()
    if command -v timeout >/dev/null 2>&1; then
        base_runner=(timeout --preserve-status 60s)
    fi
    conda_base="$("${base_runner[@]}" "$CONDA_EXE" info --base </dev/null 2>/dev/null)" || {
        echo "[conda] 'conda info --base' failed or timed out (exit=$?)"
        return 1
    }
    echo "[conda] conda base: ${conda_base}"

    if [[ -f "${conda_base}/etc/profile.d/conda.sh" ]]; then
        # shellcheck source=/dev/null
        source "${conda_base}/etc/profile.d/conda.sh"
    else
        echo "[conda] ${conda_base}/etc/profile.d/conda.sh not found"
        return 1
    fi

    # Validate that the requested env actually exists before calling
    # `conda activate`. On some conda builds, activating a missing env
    # prints the error to stderr but exits 0, which the surrounding
    # `if ! ...` cannot detect. An explicit pre-check avoids that.
    if ! "$CONDA_EXE" env list 2>/dev/null \
            | awk 'NF && $1 !~ /^#/ { print $1 }' \
            | grep -qx -- "$env"; then
        echo "[conda] env '${env}' does not exist on $(hostname)."
        echo "[conda]   available envs on this node:"
        "$CONDA_EXE" env list 2>/dev/null | sed 's/^/[conda]     /' || true
        echo "[conda]   Create it with:  sbatch slurm/jobs/setup_env.sbatch"
        echo "[conda]   or manually:     conda create -y -n ${env} python=3.11 && \\"
        echo "[conda]                    conda activate ${env} && \\"
        echo "[conda]                    pip install -e \".[dev,adapters]\""
        return 1
    fi

    echo "[conda] activating '${env}'..."
    # Capture conda's exit code explicitly and preserve its stderr so
    # the user sees the actual error (e.g. EnvironmentNameNotFound,
    # CondaEnvException) rather than a misleading "rc=0" line.
    local _conda_rc
    conda activate "$env"
    _conda_rc=$?
    if [[ $_conda_rc -ne 0 ]]; then
        echo "[conda] activate ${env} failed (conda exit=${_conda_rc})"
        echo "[conda]   See the conda error above. Common fixes:"
        echo "[conda]     - env corrupted: conda env remove -n ${env} && resubmit setup_env.sbatch"
        echo "[conda]     - pip/perm issue: check ${CONDA_PREFIX:-$HOME/miniconda3/envs/${env}} is writable"
        return 1
    fi

    echo "[conda] activated env '${env}' (CONDA_PREFIX=${CONDA_PREFIX:-unset})"
    return 0
}
