#!/bin/bash
#SBATCH --job-name=hormuz-setup
#SBATCH --output=slurm/logs/setup-%j.out
#SBATCH --error=slurm/logs/setup-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00

# ------------------------------------------------------------------
# One-time environment setup for the Hormuz pipeline on the cluster.
#
# Creates a conda environment with all required dependencies,
# installs the pipeline package, and pre-compiles Julia packages.
#
# Error handling: every optional install step is wrapped so that a
# missing system library or unavailable wheel does NOT abort setup.
# Failures are surfaced as warnings and recorded in the runtime
# inventory so downstream jobs can detect missing capabilities.
# ------------------------------------------------------------------

# Note: no `set -e`. We intentionally let optional installs fail
# without taking down the whole setup job.
set -uo pipefail

# Source shared helpers if available; tolerate the case where this
# job is run before the rest of the repo is checked out.
if [[ -f "$(dirname "${BASH_SOURCE[0]}")/_common.sh" ]]; then
    # shellcheck source=./_common.sh
    source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
else
    record_bash_failure() { echo "[setup] (no _common.sh) $*"; }
    record_runtime_inventory() { echo "[setup] (no _common.sh) inventory skipped"; }
    hormuz_activate_conda() {
        local env="${1:-${HORMUZ_CONDA_ENV:-hormuz}}"
        if command -v conda >/dev/null 2>&1; then
            local base
            base="$(conda info --base 2>/dev/null)" || return 1
            if [[ -f "${base}/etc/profile.d/conda.sh" ]]; then
                # shellcheck source=/dev/null
                source "${base}/etc/profile.d/conda.sh"
                conda activate "$env"
                return $?
            fi
        fi
        return 1
    }
fi

STAGE="setup_env"
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-.}"
cd "$PROJECT_ROOT"

echo "============================================="
echo "  Hormuz Pipeline — Environment Setup"
echo "  Node: $(hostname)"
echo "  Date: $(date)"
echo "============================================="

# Track per-step success/failure so we can report a summary at the end.
SETUP_WARNINGS=()

run_step() {
    # run_step <label> <command...>
    local label="$1"
    shift
    echo ""
    echo "--- ${label} ---"
    if "$@"; then
        echo "[ok] ${label}"
        return 0
    else
        local rc=$?
        echo "[warn] ${label} failed with exit ${rc}"
        SETUP_WARNINGS+=("${label} (exit ${rc})")
        record_bash_failure "$STAGE" "$rc" "Setup step failed: ${label}"
        return 0   # keep going
    fi
}

module purge 2>/dev/null || true
module load anaconda3 2>/dev/null || echo "[module] anaconda3 not available"

CONDA_ENV="${HORMUZ_CONDA_ENV:-hormuz}"

# Create conda environment if it doesn't exist.
if ! conda env list | grep -q "^${CONDA_ENV} "; then
    run_step "[1/5] Create conda env '${CONDA_ENV}'" \
        conda create -y -n "$CONDA_ENV" python=3.11
else
    echo "[1/5] Conda environment '${CONDA_ENV}' already exists."
fi

if ! hormuz_activate_conda "$CONDA_ENV"; then
    echo "[fatal] cannot activate conda env '${CONDA_ENV}'"
    record_bash_failure "$STAGE" 1 "hormuz_activate_conda failed for env '${CONDA_ENV}' on $(hostname)"
    exit 1
fi

# Core install — this is the only step that should be considered
# fatal: without the pipeline package itself, nothing else makes
# sense. Even so we report a clean error rather than crashing.
run_step "[2/5] Install hormuz-pipeline (editable + dev + adapters)" \
    pip install -e ".[dev,adapters]" --quiet

# Optional adapter dependencies — each tied to a runtime that may or
# may not be present on the cluster. Failures are recorded but do not
# halt setup; the corresponding model adapters will simply raise
# NotImplementedError / ImportError at run time, which run_model.py
# already converts into a SKIPPED / FAILED status.
echo ""
echo "--- [3/5] Optional adapter dependencies ---"

if module avail gams 2>&1 | grep -q gams; then
    run_step "  - gamsapi" \
        pip install "gamsapi[transfer]>=52.0" --quiet
else
    echo "  - gamsapi: skipped (no gams module on this cluster)"
fi

if module avail julia 2>&1 | grep -q julia; then
    run_step "  - juliacall" \
        pip install "juliacall>=0.9.20" --quiet
else
    echo "  - juliacall: skipped (no julia module on this cluster)"
fi

if module avail R 2>&1 | grep -q "R/"; then
    run_step "  - rpy2" \
        pip install "rpy2>=3.5" --quiet
else
    echo "  - rpy2: skipped (no R module on this cluster)"
fi

run_step "  - openpyxl + pandas" \
    pip install "openpyxl>=3.1" "pandas>=2.0" --quiet

# GPU/ML dependencies — also optional; missing wheels are common on
# CPU-only login nodes and should not abort setup.
echo ""
echo "--- [4/5] ML / GPU dependencies (optional) ---"
run_step "  - torch" \
    pip install torch --quiet
run_step "  - transformers + accelerate + peft" \
    pip install transformers accelerate peft --quiet

# Data directory layout.
run_step "[5/5] Create data directories" \
    mkdir -p data/inputs data/outputs data/reports data/pipeline_state/manifests

# Document what landed on this node so the user can see exactly what
# capabilities the pipeline will have at run time.
record_runtime_inventory "$STAGE"

echo ""
echo "============================================="
echo "  Setup complete."
echo "  Activate with: conda activate ${CONDA_ENV}"
if [[ ${#SETUP_WARNINGS[@]} -gt 0 ]]; then
    echo ""
    echo "  WARNINGS — ${#SETUP_WARNINGS[@]} step(s) did not complete:"
    for w in "${SETUP_WARNINGS[@]}"; do
        echo "    * $w"
    done
    echo "  Models that depend on the missing components will be"
    echo "  reported as SKIPPED in the synthesis stage."
fi
echo "============================================="
