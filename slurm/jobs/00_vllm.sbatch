#!/bin/bash
#SBATCH --job-name=hormuz-vllm
#SBATCH --output=slurm/logs/00_vllm-%j.out
#SBATCH --error=slurm/logs/00_vllm-%j.err
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=24:00:00

# ------------------------------------------------------------------
# Optional vLLM sidecar for the Hormuz pipeline.
#
# Launches a vLLM OpenAI-compatible server on a GPU node and writes
# the resolved URL (http://<node>:<port>/v1) to
#   slurm/state/vllm_url.txt
#
# submit_pipeline.sh auto-picks the URL from that file when
# PIPELINE_LLM_BASE_URL is not already exported, so the typical flow
# is:
#
#   sbatch slurm/jobs/00_vllm.sbatch
#   # wait for the URL file to appear (squeue / cat slurm/logs/00_vllm-*.out)
#   ./slurm/submit_pipeline.sh
#
# Variables (override via --export or environment):
#   HORMUZ_VLLM_MODEL       - HF model id (default: meta-llama/Llama-3.1-70B-Instruct)
#   HORMUZ_VLLM_PORT        - TCP port (default: 8000)
#   HORMUZ_VLLM_TP_SIZE     - tensor-parallel size (default: 1)
#   HORMUZ_VLLM_DTYPE       - dtype (default: auto)
#   HORMUZ_VLLM_MAX_LEN     - max model len (default: 8192)
#   HORMUZ_VLLM_EXTRA_ARGS  - extra flags appended verbatim
#
# This is the "hot-swap" sidecar: it stays up for 24 hours unless
# cancelled. Re-submit before the wall time expires for long campaigns.
# ------------------------------------------------------------------

set -uo pipefail

# shellcheck source=./_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

STAGE="00_vllm"

VLLM_MODEL="${HORMUZ_VLLM_MODEL:-meta-llama/Llama-3.1-70B-Instruct}"
VLLM_PORT="${HORMUZ_VLLM_PORT:-8000}"
VLLM_TP_SIZE="${HORMUZ_VLLM_TP_SIZE:-1}"
VLLM_DTYPE="${HORMUZ_VLLM_DTYPE:-auto}"
VLLM_MAX_LEN="${HORMUZ_VLLM_MAX_LEN:-8192}"
VLLM_EXTRA_ARGS="${HORMUZ_VLLM_EXTRA_ARGS:-}"

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
URL_FILE="${PROJECT_ROOT}/slurm/state/vllm_url.txt"
mkdir -p "$(dirname "$URL_FILE")"

NODE_HOST="$(hostname -f 2>/dev/null || hostname)"
URL="http://${NODE_HOST}:${VLLM_PORT}/v1"

echo "============================================="
echo "  vLLM sidecar"
echo "  Job ID:   ${SLURM_JOB_ID:-N/A}"
echo "  Node:     ${NODE_HOST}"
echo "  GPUs:     ${SLURM_GPUS_ON_NODE:-none}"
echo "  Model:    ${VLLM_MODEL}"
echo "  Port:     ${VLLM_PORT}"
echo "  TP size:  ${VLLM_TP_SIZE}"
echo "  URL:      ${URL}"
echo "  URL file: ${URL_FILE}"
echo "============================================="

cd "$PROJECT_ROOT"

module purge 2>/dev/null || true
module load anaconda3 2>/dev/null || true
module load cuda/12.4 2>/dev/null || echo "[module] cuda/12.4 not available on this node"

if ! hormuz_activate_conda "${HORMUZ_CONDA_ENV:-hormuz}"; then
    record_bash_failure "$STAGE" 1 "hormuz_activate_conda failed for env '${HORMUZ_CONDA_ENV:-hormuz}' on $(hostname)"
    echo "[fatal] cannot activate conda env; aborting vLLM sidecar"
    exit 1
fi

record_runtime_inventory "$STAGE"

if ! python -c "import vllm" 2>/dev/null; then
    record_bash_failure "$STAGE" 1 "vllm package not installed in conda env '${HORMUZ_CONDA_ENV:-hormuz}'"
    echo "[fatal] vllm is not installed. Try: pip install vllm"
    exit 1
fi

# Publish the URL so submit_pipeline.sh can pick it up.
echo "$URL" > "$URL_FILE"
echo "[vllm] published URL ${URL} to ${URL_FILE}"

# Cleanup hook: when SLURM kills us (timeout or scancel), remove the
# URL file so subsequent submit_pipeline.sh calls fail fast rather
# than pointing at a dead server.
cleanup() {
    rm -f "$URL_FILE"
    echo "[vllm] removed ${URL_FILE} on shutdown"
}
trap cleanup EXIT TERM INT

# Block on vLLM. The server runs until the SLURM job is killed.
# shellcheck disable=SC2086
exec python -m vllm.entrypoints.openai.api_server \
    --model "${VLLM_MODEL}" \
    --port "${VLLM_PORT}" \
    --host 0.0.0.0 \
    --tensor-parallel-size "${VLLM_TP_SIZE}" \
    --dtype "${VLLM_DTYPE}" \
    --max-model-len "${VLLM_MAX_LEN}" \
    ${VLLM_EXTRA_ARGS}
