#!/bin/bash
#SBATCH --job-name=hormuz-model-gpu
#SBATCH --output=slurm/logs/03_model_gpu-%A_%a.out
#SBATCH --error=slurm/logs/03_model_gpu-%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
# Array size set dynamically by submit_pipeline.sh via --array=0-N

# ------------------------------------------------------------------
# Module 3: GPU Model Execution (SLURM Array Job)
#
# Runs domain models that require GPU acceleration:
# - ML-based forecasting models (TimeSeriesTransformer, LoRA fine-tuned)
# - SimRLFab (RL-based semiconductor fab simulation)
# - Futures forecasting models with deep learning
#
# Each array task gets one GPU and runs one (scenario, model) pair.
#
# Error handling (see slurm/jobs/_common.sh):
#   * record_runtime_inventory documents whether CUDA / nvidia-smi are
#     present and whether PyTorch can see the GPU. Synthesis can use
#     this to flag GPU-unavailability vs. model-level failures.
#   * safe_python wraps run_model.py and tolerates per-task failures
#     so that one model crashing (or its runtime being absent) does
#     not abort the rest of the array nor the afterok dependency to
#     Module 4.
# ------------------------------------------------------------------

set -uo pipefail

# shellcheck source=./_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

STAGE="03_models_gpu"

echo "============================================="
echo "  Module 3: GPU Model Execution"
echo "  Array Job: ${SLURM_ARRAY_JOB_ID:-N/A} Task: ${SLURM_ARRAY_TASK_ID:-N/A}"
echo "  Node:      $(hostname)"
echo "  GPUs:      ${SLURM_GPUS_ON_NODE:-none}"
echo "  Run ID:    ${HORMUZ_RUN_ID:-not set}"
echo "  Date:      $(date)"
echo "============================================="

cd "${SLURM_SUBMIT_DIR}"

# Module loading is best-effort: missing modules are recorded by the
# runtime inventory rather than crashing the whole task.
module purge 2>/dev/null || true
module load anaconda3 2>/dev/null || true
module load cuda/12.4 2>/dev/null || echo "[module] cuda/12.4 not available on this node"
module load cudnn/9.0 2>/dev/null || echo "[module] cudnn/9.0 not available on this node"

if ! hormuz_activate_conda "${HORMUZ_CONDA_ENV:-hormuz}"; then
    record_bash_failure "$STAGE" 1 "hormuz_activate_conda failed for env '${HORMUZ_CONDA_ENV:-hormuz}' on $(hostname)"
    echo "[task ${SLURM_ARRAY_TASK_ID:-N/A}] cannot activate conda env; skipping (continue_on_failure=1)"
    exit 0
fi

# Document compute-node capabilities (CUDA, nvidia-smi, etc.).
record_runtime_inventory "$STAGE"

# Best-effort PyTorch GPU probe. If torch isn't installed or the GPU
# isn't visible, we record the situation but still let safe_python try
# to run the script — some GPU-tagged models can fall back to CPU.
if ! python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}, GPUs: {torch.cuda.device_count()}')" 2>/dev/null; then
    echo "[gpu] PyTorch GPU probe failed (torch missing or CUDA unavailable)"
    record_bash_failure "$STAGE" 0 "PyTorch GPU probe failed on $(hostname); models requiring CUDA may be skipped"
fi

# Override manifest name to use GPU-only manifest.
export HORMUZ_MANIFEST_NAME="models_gpu"

# continue_on_failure=1: one task's interpreter crash must not break
# the afterok dependency to Module 4 (synthesis).
safe_python "$STAGE" 1 -- python slurm/scripts/run_model.py

echo "Task ${SLURM_ARRAY_TASK_ID:-N/A} complete at $(date)"
exit 0
