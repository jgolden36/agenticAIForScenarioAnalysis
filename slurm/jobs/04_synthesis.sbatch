#!/bin/bash
#SBATCH --job-name=hormuz-synthesis
#SBATCH --output=slurm/logs/04_synthesis-%j.out
#SBATCH --error=slurm/logs/04_synthesis-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00

# ------------------------------------------------------------------
# Module 4: Output Synthesis
#
# Collects results from all model execution array jobs, runs
# cross-model consistency checks, and synthesizes a structured
# analysis report via LLM.
#
# This is a single job (not an array) that runs after all Module 3
# jobs complete. It is designed to handle partial inputs: if some
# models failed, were skipped (NotImplementedError), or hit a
# bash-layer crash, run_synthesis.py will read the corresponding
# {run_id}_model_*.json and {run_id}_03_*_bash_failure_*.json
# records and document the gaps in the report.
#
# Error handling: continue_on_failure=0 because synthesis is the
# leaf of the dependency DAG; a crash here should be visible to the
# user via the SLURM exit code.
# ------------------------------------------------------------------

set -uo pipefail

# shellcheck source=./_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

STAGE="04_synthesis"

echo "============================================="
echo "  Module 4: Output Synthesis"
echo "  Job ID:   ${SLURM_JOB_ID:-N/A}"
echo "  Node:     $(hostname)"
echo "  Run ID:   ${HORMUZ_RUN_ID:-not set}"
echo "  LLM URL:  ${PIPELINE_LLM_BASE_URL:-<provider default>}"
echo "  Date:     $(date)"
echo "============================================="

cd "${SLURM_SUBMIT_DIR}"

module purge 2>/dev/null || true
module load anaconda3 2>/dev/null || true

if ! hormuz_activate_conda "${HORMUZ_CONDA_ENV:-hormuz}"; then
    record_bash_failure "$STAGE" 1 "hormuz_activate_conda failed for env '${HORMUZ_CONDA_ENV:-hormuz}' on $(hostname)"
    echo "[fatal] cannot activate conda env; aborting Module 4"
    exit 1
fi

record_runtime_inventory "$STAGE"

# Inform the synthesis script how many bash-layer failures were
# recorded earlier in the pipeline so they can be incorporated into
# the report. The Python side is free to ignore it.
BASH_FAILURE_COUNT=$(ls -1 \
    "${HORMUZ_PROJECT_ROOT}/data/pipeline_state/${HORMUZ_RUN_ID:-no_run_id}_"*"_bash_failure_"*.json \
    2>/dev/null | wc -l | tr -d ' ')
export HORMUZ_BASH_FAILURE_COUNT="${BASH_FAILURE_COUNT:-0}"
echo "[synthesis] Detected ${HORMUZ_BASH_FAILURE_COUNT} bash-layer failure record(s) from upstream stages."

# continue_on_failure=0: synthesis is the leaf job; surface failures
# to the user via the SLURM exit code.
safe_python "$STAGE" 0 -- python slurm/scripts/run_synthesis.py
rc=$?

echo "Module 4 complete at $(date) (exit=${rc})"
exit "$rc"
