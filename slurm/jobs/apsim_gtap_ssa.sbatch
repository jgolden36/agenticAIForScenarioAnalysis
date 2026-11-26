#!/bin/bash
# ==================================================================
# APSIM-GTAP Armington-elasticity Latin hypercube (AgResilience E9 design).
#
# Array job: each task solves a share of the draws (all five scenarios per
# draw, so each draw's GTAP re-calibration happens once per task). Then
# aggregate with a dependent job:
#
#   jid=$(sbatch --parsable --exclude=orion,tesla1,tesla2,h100 --array=0-9 slurm/jobs/apsim_gtap_ssa.sbatch)
#   sbatch --exclude=orion,tesla1,tesla2,h100 --dependency=afterany:${jid} \
#       --export=ALL,HORMUZ_SSA_AGGREGATE=1 slurm/jobs/apsim_gtap_ssa.sbatch
#
# Scenario inputs default to the analyst baseline; set HORMUZ_SSA_INPUTS to
# a fill's apsim_gtap_fill_inputs.json to perturb around a run's inputs.
# Toggles: HORMUZ_SSA_N (100), HORMUZ_SSA_WORK_DIR, HORMUZ_SSA_OUT_DIR.
# ==================================================================
#SBATCH --job-name=hormuz-apsim-gtap-ssa
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=slurm/logs/apsim_gtap_ssa-%A_%a.out
#SBATCH --error=slurm/logs/apsim_gtap_ssa-%A_%a.err
#SBATCH --mail-type=END,FAIL

set -uo pipefail
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$PROJECT_ROOT"

LOG_DIR="${PROJECT_ROOT}/slurm/logs/apsim_gtap_ssa"
mkdir -p "$LOG_DIR"
export HORMUZ_LOG_DIR="$LOG_DIR"
export HORMUZ_STATE_DIR="$LOG_DIR"
source "${PROJECT_ROOT}/slurm/jobs/_common.sh"
export HORMUZ_CONDA_ENV="${HORMUZ_CONDA_ENV:-hormuz}"
export WANDB_MODE=disabled
export CUDA_VISIBLE_DEVICES=""

if command -v module >/dev/null 2>&1; then
    timeout --preserve-status 60s bash -c "module load anaconda3 </dev/null" 2>/dev/null || true
fi
# Nodes without the anaconda module (e.g. orion): fall back to ~/miniconda3,
# where the hormuz env lives.
if ! command -v conda >/dev/null 2>&1 && [[ -z "${CONDA_EXE:-}" && -x "$HOME/miniconda3/bin/conda" ]]; then
    export CONDA_EXE="$HOME/miniconda3/bin/conda"
fi
hormuz_activate_conda "${HORMUZ_CONDA_ENV}" || { echo "conda env ${HORMUZ_CONDA_ENV} not available"; exit 1; }

WORK="${HORMUZ_SSA_WORK_DIR:-${PROJECT_ROOT}/data/robustness/apsim_gtap_ssa}"
OUT="${HORMUZ_SSA_OUT_DIR:-${PROJECT_ROOT}/docs/revision/robustness/apsim_gtap_ssa}"
N="${HORMUZ_SSA_N:-100}"
INPUT_ARGS=()
if [[ -n "${HORMUZ_SSA_INPUTS:-}" ]]; then
    INPUT_ARGS=( --inputs "$HORMUZ_SSA_INPUTS" )
fi

if [[ "${HORMUZ_SSA_AGGREGATE:-0}" == "1" ]]; then
    python scripts/revision/apsim_gtap_ssa.py --work-dir "$WORK" --aggregate --out-dir "$OUT" --n "$N" ${INPUT_ARGS[@]+"${INPUT_ARGS[@]}"}
    exit $?
fi

record_runtime_inventory "apsim_gtap_ssa_${SLURM_ARRAY_TASK_ID:-0}"
python scripts/revision/apsim_gtap_ssa.py --work-dir "$WORK" --n "$N" ${INPUT_ARGS[@]+"${INPUT_ARGS[@]}"} \
    --chunk "${SLURM_ARRAY_TASK_ID:-0}" --n-chunks "${SLURM_ARRAY_TASK_COUNT:-1}"
