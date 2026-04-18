#!/bin/bash
# ==================================================================
# Hormuz Crisis Analysis Pipeline — SLURM Submission Orchestrator
#
# Submits the full pipeline as a chain of dependent SLURM jobs:
#
#   01_scenarios  →  dispatch_params  →  02_parameters (array)
#                                          ↓
#                                    dispatch_models
#                                     ↙          ↘
#                          03_models_cpu     03_models_gpu  (arrays)
#                                     ↘          ↙
#                                    04_synthesis
#
# Each arrow represents a --dependency=afterok constraint, ensuring
# stages run in sequence while exploiting parallelism within stages.
#
# Usage:
#   ./slurm/submit_pipeline.sh                # Submit full pipeline (auto-approved)
#   ./slurm/submit_pipeline.sh --dry-run      # Show sbatch commands without submitting
#   ./slurm/submit_pipeline.sh --partition gpu # Override GPU partition name
#
# NOTE: cluster runs are non-interactive. The pipeline always auto-
# approves the three HITL checkpoints because SLURM cannot pause for
# analyst input. For interactive HITL, run the LangGraph orchestrator
# locally instead: `python -m src.pipeline.graph`.
#
# Environment variables (optional):
#   HORMUZ_CONDA_ENV   - Conda environment name (default: hormuz)
#   HORMUZ_CONFIG      - Pipeline config YAML override
#   HORMUZ_ACCOUNT     - SLURM account to charge
# ==================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---- Parse arguments ------------------------------------------------

# Cluster runs are always auto-approved; --auto is retained as a no-op
# for backward compatibility and emits a deprecation notice.
AUTO_APPROVE=1
DRY_RUN=0
GPU_PARTITION="gpu"
CPU_PARTITION="batch"
ACCOUNT=""
MAX_ARRAY_CONCURRENT=16  # Max simultaneous array tasks

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto)
            echo "[notice] --auto is now the default for cluster runs; flag is a no-op."
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --partition)
            GPU_PARTITION="$2"
            shift 2
            ;;
        --cpu-partition)
            CPU_PARTITION="$2"
            shift 2
            ;;
        --account)
            ACCOUNT="$2"
            shift 2
            ;;
        --max-concurrent)
            MAX_ARRAY_CONCURRENT="$2"
            shift 2
            ;;
        -h|--help)
            head -30 "$0" | tail -25
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# ---- Setup ----------------------------------------------------------

RUN_ID="$(date -u +%Y%m%d_%H%M%S)"
CONDA_ENV="${HORMUZ_CONDA_ENV:-hormuz}"
ACCOUNT="${ACCOUNT:-${HORMUZ_ACCOUNT:-}}"
CONFIG="${HORMUZ_CONFIG:-${PROJECT_ROOT}/slurm/config/pipeline_cluster.yaml}"

# ---- LLM precondition check ----------------------------------------
# Cluster default is local vLLM. If the user hasn't switched providers,
# they must point the pipeline at the running vLLM endpoint via
# PIPELINE_LLM_BASE_URL. The submitter checks here so we fail fast on
# the login node rather than ~140 LLM calls into the run.
LLM_PROVIDER="${PIPELINE_LLM_PROVIDER:-vllm}"
if [[ "$LLM_PROVIDER" == "vllm" || "$LLM_PROVIDER" == "ollama" ]]; then
    # Try to auto-pick from sidecar URL file written by 00_vllm.sbatch.
    VLLM_URL_FILE="${PROJECT_ROOT}/slurm/state/vllm_url.txt"
    if [[ -z "${PIPELINE_LLM_BASE_URL:-}" && -f "$VLLM_URL_FILE" ]]; then
        PIPELINE_LLM_BASE_URL="$(cat "$VLLM_URL_FILE")"
        export PIPELINE_LLM_BASE_URL
        echo "[llm] picked PIPELINE_LLM_BASE_URL=${PIPELINE_LLM_BASE_URL} from ${VLLM_URL_FILE}"
    fi
    if [[ -z "${PIPELINE_LLM_BASE_URL:-}" ]]; then
        echo "ERROR: PIPELINE_LLM_BASE_URL is not set and ${VLLM_URL_FILE} does not exist." >&2
        echo "       Either submit 00_vllm.sbatch first, or set the URL manually:" >&2
        echo "         export PIPELINE_LLM_BASE_URL=http://gpu03:8000/v1" >&2
        echo "       To use a cloud LLM instead, set PIPELINE_LLM_PROVIDER=anthropic (or openai)" >&2
        echo "       and export the relevant API key (ANTHROPIC_API_KEY / OPENAI_API_KEY)." >&2
        exit 1
    fi
elif [[ "$LLM_PROVIDER" == "anthropic" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "ERROR: PIPELINE_LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not exported." >&2
    exit 1
elif [[ "$LLM_PROVIDER" == "openai" && -z "${OPENAI_API_KEY:-}" ]]; then
    echo "ERROR: PIPELINE_LLM_PROVIDER=openai but OPENAI_API_KEY is not exported." >&2
    exit 1
fi
export PIPELINE_LLM_PROVIDER="$LLM_PROVIDER"

# Ensure log and state directories exist
mkdir -p "${PROJECT_ROOT}/slurm/logs"
mkdir -p "${PROJECT_ROOT}/data/pipeline_state/manifests"

# Common sbatch arguments
SBATCH_COMMON=""
if [[ -n "$ACCOUNT" ]]; then
    SBATCH_COMMON="--account=${ACCOUNT}"
fi

# Export variables for all jobs
export HORMUZ_RUN_ID="$RUN_ID"
export HORMUZ_CONDA_ENV="$CONDA_ENV"
export HORMUZ_CONFIG="$CONFIG"
export HORMUZ_AUTO_APPROVE="1"

# Build the explicit --export list so the variables survive the
# `--wrap=` shells used for the dispatch jobs (some clusters strip
# environment variables that aren't named explicitly even with ALL).
EXPORT_VARS="ALL,HORMUZ_RUN_ID=${RUN_ID},HORMUZ_CONDA_ENV=${CONDA_ENV},HORMUZ_CONFIG=${CONFIG}"
if [[ -n "${HORMUZ_AUTO_APPROVE:-}" ]]; then
    EXPORT_VARS="${EXPORT_VARS},HORMUZ_AUTO_APPROVE=${HORMUZ_AUTO_APPROVE}"
fi
EXPORT_VARS="${EXPORT_VARS},PIPELINE_LLM_PROVIDER=${PIPELINE_LLM_PROVIDER}"
if [[ -n "${PIPELINE_LLM_BASE_URL:-}" ]]; then
    EXPORT_VARS="${EXPORT_VARS},PIPELINE_LLM_BASE_URL=${PIPELINE_LLM_BASE_URL}"
fi
if [[ -n "${PIPELINE_LLM_MODEL:-}" ]]; then
    EXPORT_VARS="${EXPORT_VARS},PIPELINE_LLM_MODEL=${PIPELINE_LLM_MODEL}"
fi
if [[ -n "${VLLM_API_KEY:-}" ]]; then
    EXPORT_VARS="${EXPORT_VARS},VLLM_API_KEY=${VLLM_API_KEY}"
fi
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    EXPORT_VARS="${EXPORT_VARS},ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
fi
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    EXPORT_VARS="${EXPORT_VARS},OPENAI_API_KEY=${OPENAI_API_KEY}"
fi

echo "============================================="
echo "  Hormuz Pipeline — SLURM Submission"
echo "============================================="
echo "  Run ID:          $RUN_ID"
echo "  Project root:    $PROJECT_ROOT"
echo "  Conda env:       $CONDA_ENV"
echo "  GPU partition:   $GPU_PARTITION"
echo "  CPU partition:   $CPU_PARTITION"
echo "  Auto-approve:    $( [[ $AUTO_APPROVE -eq 1 ]] && echo YES || echo NO )"
echo "  Max concurrent:  $MAX_ARRAY_CONCURRENT"
echo "  Config:          $CONFIG"
echo "  LLM provider:    ${PIPELINE_LLM_PROVIDER}"
echo "  LLM base URL:    ${PIPELINE_LLM_BASE_URL:-<provider default>}"
echo "  Dry run:         $( [[ $DRY_RUN -eq 1 ]] && echo YES || echo NO )"
echo "============================================="
echo ""

# Helper: submit a job and capture the job ID
submit_job() {
    local description="$1"
    shift
    local cmd="sbatch $SBATCH_COMMON $*"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[DRY RUN] $description"
        echo "  $cmd"
        echo "  (would return JOBID)"
        echo ""
        echo "DRY_RUN_JOBID"
        return
    fi

    echo "Submitting: $description"
    echo "  $cmd"

    local output
    output=$($cmd)
    local job_id
    job_id=$(echo "$output" | grep -oP '\d+' | tail -1)
    echo "  → Job ID: $job_id"
    echo ""
    echo "$job_id"
}

# ---- Stage 1: Scenario Generation -----------------------------------

echo "──── Stage 1: Scenario Generation ────"
JOB1=$(submit_job "Module 1: Scenario Generation" \
    --partition="$CPU_PARTITION" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    "${PROJECT_ROOT}/slurm/jobs/01_scenarios.sbatch" \
    | tail -1)

# ---- Between stages: Generate parameter manifest --------------------

# This runs as a small job that produces the manifest, then the array
# job depends on it.
echo "──── Dispatch: Parameter Manifest ────"
JOB_DISPATCH_P=$(submit_job "Generate parameter extraction manifest" \
    --partition="$CPU_PARTITION" \
    --dependency="afterok:${JOB1}" \
    --cpus-per-task=1 \
    --mem=4G \
    --time=00:10:00 \
    --job-name=hormuz-dispatch-params \
    --output="${PROJECT_ROOT}/slurm/logs/dispatch_params-%j.out" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    --wrap="module load anaconda3 2>/dev/null || true; source ${PROJECT_ROOT}/slurm/jobs/_common.sh; hormuz_activate_conda ${CONDA_ENV} || { record_bash_failure dispatch_params 1 'conda activate failed'; exit 1; }; python slurm/scripts/dispatch_models.py parameters --run-id ${RUN_ID}" \
    | tail -1)

# ---- Stage 2: Parameter Extraction (Array Job) ----------------------

# We can't know the exact array size until the dispatch job runs and
# materialises the manifest, but the upper bound is well-defined:
#   N_scenarios (=4) * N_model_specs (=34 in this repo) = 136.
# We use 149 (headroom for 1-2 future specs) by default. Out-of-range
# tasks in run_parameters.py exit cleanly and write nothing, so the
# only cost is wasted scheduler slots at the tail. dispatch_models.py
# also writes data/pipeline_state/manifests/<run_id>_parameters_count.txt
# for follow-up improvements that want to size the array exactly.
PARAM_ARRAY_MAX="${HORMUZ_PARAM_ARRAY_MAX:-149}"

echo "──── Stage 2: Parameter Extraction (Array) ────"
JOB2=$(submit_job "Module 2: Parameter Extraction (array 0-${PARAM_ARRAY_MAX})" \
    --partition="$CPU_PARTITION" \
    --dependency="afterok:${JOB_DISPATCH_P}" \
    --array="0-${PARAM_ARRAY_MAX}%${MAX_ARRAY_CONCURRENT}" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    "${PROJECT_ROOT}/slurm/jobs/02_parameters.sbatch" \
    | tail -1)

# ---- Between stages: Generate model execution manifests --------------

echo "──── Dispatch: Model Execution Manifest ────"
JOB_DISPATCH_M=$(submit_job "Generate model execution manifests" \
    --partition="$CPU_PARTITION" \
    --dependency="afterok:${JOB2}" \
    --cpus-per-task=1 \
    --mem=4G \
    --time=00:10:00 \
    --job-name=hormuz-dispatch-models \
    --output="${PROJECT_ROOT}/slurm/logs/dispatch_models-%j.out" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    --wrap="module load anaconda3 2>/dev/null || true; source ${PROJECT_ROOT}/slurm/jobs/_common.sh; hormuz_activate_conda ${CONDA_ENV} || { record_bash_failure dispatch_models 1 'conda activate failed'; exit 1; }; python slurm/scripts/dispatch_models.py models --run-id ${RUN_ID}" \
    | tail -1)

# ---- Stage 3: Model Execution (CPU + GPU Arrays) --------------------

# Upper bounds. CPU array hosts almost all models (~30 stub + real
# adapters). GPU array currently hosts only adapters whose
# ResourceRequirements.requires_gpu is True (today: SimRLFab) -> 4
# entries. Override via env when adding more GPU models.
MODEL_CPU_ARRAY_MAX="${HORMUZ_MODEL_CPU_ARRAY_MAX:-149}"
MODEL_GPU_ARRAY_MAX="${HORMUZ_MODEL_GPU_ARRAY_MAX:-15}"

echo "──── Stage 3a: CPU Model Execution (Array) ────"
JOB3_CPU=$(submit_job "Module 3: CPU Models (array 0-${MODEL_CPU_ARRAY_MAX})" \
    --partition="$CPU_PARTITION" \
    --dependency="afterok:${JOB_DISPATCH_M}" \
    --array="0-${MODEL_CPU_ARRAY_MAX}%${MAX_ARRAY_CONCURRENT}" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    "${PROJECT_ROOT}/slurm/jobs/03_models_cpu.sbatch" \
    | tail -1)

echo "──── Stage 3b: GPU Model Execution (Array) ────"
JOB3_GPU=$(submit_job "Module 3: GPU Models (array 0-${MODEL_GPU_ARRAY_MAX})" \
    --partition="$GPU_PARTITION" \
    --dependency="afterok:${JOB_DISPATCH_M}" \
    --array="0-${MODEL_GPU_ARRAY_MAX}%${MAX_ARRAY_CONCURRENT}" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    "${PROJECT_ROOT}/slurm/jobs/03_models_gpu.sbatch" \
    | tail -1)

# ---- Stage 4: Synthesis (after all models complete) ------------------

echo "──── Stage 4: Output Synthesis ────"
JOB4=$(submit_job "Module 4: Output Synthesis" \
    --partition="$CPU_PARTITION" \
    --dependency="afterok:${JOB3_CPU}:${JOB3_GPU}" \
    --export="$EXPORT_VARS" \
    --chdir="$PROJECT_ROOT" \
    "${PROJECT_ROOT}/slurm/jobs/04_synthesis.sbatch" \
    | tail -1)

# ---- Summary ---------------------------------------------------------

echo ""
echo "============================================="
echo "  Pipeline Submitted Successfully"
echo "============================================="
echo ""
echo "  Run ID:     $RUN_ID"
echo ""
echo "  Job Chain:"
echo "    Stage 1 (Scenarios):        $JOB1"
echo "    Dispatch (Params):          $JOB_DISPATCH_P"
echo "    Stage 2 (Parameters):       $JOB2"
echo "    Dispatch (Models):          $JOB_DISPATCH_M"
echo "    Stage 3a (CPU Models):      $JOB3_CPU"
echo "    Stage 3b (GPU Models):      $JOB3_GPU"
echo "    Stage 4 (Synthesis):        $JOB4"
echo ""
echo "  Monitor with:"
echo "    squeue -u \$USER"
echo "    sacct -j ${JOB1},${JOB2},${JOB3_CPU},${JOB3_GPU},${JOB4}"
echo ""
echo "  Logs in:    ${PROJECT_ROOT}/slurm/logs/"
echo "  State in:   ${PROJECT_ROOT}/data/pipeline_state/"
echo ""

echo "  NOTE: cluster runs are non-interactive."
echo "        validation_status fields will be marked 'approved' automatically."
echo "        For interactive HITL review between modules, run the local"
echo "        LangGraph orchestrator instead:"
echo "          python -m src.pipeline.graph"
echo ""
