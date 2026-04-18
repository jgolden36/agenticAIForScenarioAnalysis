#!/bin/bash
#SBATCH --job-name=hormuz-model-cpu
#SBATCH --output=slurm/logs/03_model_cpu-%A_%a.out
#SBATCH --error=slurm/logs/03_model_cpu-%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --partition=batch
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
# Array size set dynamically by submit_pipeline.sh via --array=0-N

# ------------------------------------------------------------------
# Module 3: CPU Model Execution (SLURM Array Job)
#
# Runs domain models that need CPU only: GAMS solvers (GGM, World
# Fertilizer Model, POLES-JRC), Julia CGE (MPSGE.jl), R models,
# Excel/spreadsheet models (LNGST, MarketSim), AnyLogic ABM.
#
# Each array task executes one (scenario, model) pair. The manifest
# file determines which model and parameters to use.
#
# Error handling (see slurm/jobs/_common.sh):
#   * record_runtime_inventory documents which runtimes (gams, julia,
#     R, java) were actually loadable on this node. Synthesis can use
#     this to explain why a model could not run.
#   * safe_python wraps run_model.py and tolerates per-task failures
#     so that one model crashing (or its runtime being absent) does
#     not abort the rest of the array nor the afterok dependency to
#     Module 4.
# ------------------------------------------------------------------

# NOTE: we drop `set -e` deliberately. The bash layer must keep going
# even when individual probes / module loads / model adapters fail,
# so that we can record the failure and continue with available models.
set -uo pipefail

# Source shared helpers (record_runtime_inventory, safe_python, ...).
# shellcheck source=./_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

STAGE="03_models_cpu"

echo "============================================="
echo "  Module 3: CPU Model Execution"
echo "  Array Job: ${SLURM_ARRAY_JOB_ID:-N/A} Task: ${SLURM_ARRAY_TASK_ID:-N/A}"
echo "  Node:      $(hostname)"
echo "  CPUs:      ${SLURM_CPUS_PER_TASK:-N/A}"
echo "  Run ID:    ${HORMUZ_RUN_ID:-not set}"
echo "  Date:      $(date)"
echo "============================================="

cd "${SLURM_SUBMIT_DIR}"

# Module loading is best-effort. Failures here are EXPECTED on nodes
# that don't ship a given runtime: we record them via the runtime
# inventory below rather than aborting the task.
module purge 2>/dev/null || true
module load anaconda3 2>/dev/null || true

# Load all potentially needed runtime modules; record availability.
module load gams/53    2>/dev/null || echo "[module] gams/53 not available on this node"
module load julia/1.11 2>/dev/null || echo "[module] julia/1.11 not available on this node"
module load R/4.4      2>/dev/null || echo "[module] R/4.4 not available on this node"
module load java/17    2>/dev/null || echo "[module] java/17 not available on this node"

# Activating conda is also best-effort: if it fails the python call
# below will fail and be recorded; we don't want to silently abort.
if ! hormuz_activate_conda "${HORMUZ_CONDA_ENV:-hormuz}"; then
    record_bash_failure "$STAGE" 1 "hormuz_activate_conda failed for env '${HORMUZ_CONDA_ENV:-hormuz}' on $(hostname)"
    echo "[task ${SLURM_ARRAY_TASK_ID:-N/A}] cannot activate conda env; skipping (continue_on_failure=1)"
    exit 0
fi

# Document what's actually available on this compute node so the
# synthesis stage can attribute model-availability problems correctly.
record_runtime_inventory "$STAGE"

# Override manifest name to use CPU-only manifest.
export HORMUZ_MANIFEST_NAME="models_cpu"

# Run the model executor under safe_python. continue_on_failure=1 so
# that an interpreter-level crash in one array task does not break
# the afterok dependency for Module 4 — the synthesis stage will see
# the bash_failure record and report it alongside model-level
# failed/skipped entries from run_model.py.
safe_python "$STAGE" 1 -- python slurm/scripts/run_model.py

echo "Task ${SLURM_ARRAY_TASK_ID:-N/A} complete at $(date)"
exit 0
