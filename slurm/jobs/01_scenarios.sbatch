#!/bin/bash
#SBATCH --job-name=hormuz-scenarios
#SBATCH --output=slurm/logs/01_scenarios-%j.out
#SBATCH --error=slurm/logs/01_scenarios-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00

# ------------------------------------------------------------------
# Module 1: Scenario Generation
#
# Generates 4 scenario narratives via LLM. The LLM call is an HTTP
# request to a remote endpoint (cloud API or the 00_vllm sidecar on
# a separate GPU node), so this job needs no local GPU -- a small CPU
# slot is sufficient.
#
# Environment variables (set by submit_pipeline.sh):
#   HORMUZ_RUN_ID       - Unique pipeline run identifier
#   HORMUZ_CONFIG       - Path to pipeline config YAML
#   HORMUZ_AUTO_APPROVE - Set to "1" for fully automated runs
#   HORMUZ_CONDA_ENV    - Conda environment name (default: hormuz)
#
# Error handling: this stage is a hard dependency for everything
# downstream (no scenarios -> no parameters -> no model runs), so
# safe_python is called with continue_on_failure=0: bash failures
# are recorded but the SLURM exit code is propagated so the
# afterok dependency correctly halts the pipeline.
# ------------------------------------------------------------------

set -uo pipefail

# shellcheck source=./_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

STAGE="01_scenarios"

echo "============================================="
echo "  Module 1: Scenario Generation"
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
    echo "[fatal] cannot activate conda env; aborting Module 1"
    exit 1
fi

record_runtime_inventory "$STAGE"

# continue_on_failure=0: there is no useful pipeline state without
# scenarios, so we propagate the failure to SLURM. The bash_failure
# record is still written for diagnostics.
safe_python "$STAGE" 0 -- python slurm/scripts/run_scenarios.py
rc=$?

echo "Module 1 complete at $(date) (exit=${rc})"
exit "$rc"
