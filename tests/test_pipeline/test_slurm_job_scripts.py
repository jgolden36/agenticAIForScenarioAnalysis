"""Syntax and sourcing checks for the SLURM job scripts (no SLURM needed)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
JOBS = REPO / "slurm" / "jobs"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _scripts() -> list[Path]:
    return sorted(list(JOBS.glob("*.job")) + list(JOBS.glob("*.sbatch")) + list(JOBS.glob("_*.sh")))


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_bash_syntax(script: Path):
    proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_revision_include_sources_and_defines_functions(tmp_path):
    env_prefix = (
        f"export SLURM_SUBMIT_DIR={REPO} HORMUZ_STATE_DIR={tmp_path / 'state'} HORMUZ_LOG_DIR={tmp_path / 'logs'}; "
    )
    script = (
        env_prefix
        + "source slurm/jobs/_common.sh && source slurm/jobs/_revision_stage.sh && "
        + "declare -F hormuz_stage_validation hormuz_stage_export hormuz_stage_visualize hormuz_stage_postprocess "
        + "hormuz_stage_recover hormuz_capture_pip_freeze hormuz_stage_revision hormuz_revision_summary >/dev/null && "
        + 'test "$HORMUZ_STATE_DIR" = "' + str(tmp_path / "state") + '" && '
        + "safe_python t 1 -- false; test \"$HORMUZ_SAFE_PYTHON_RC\" = 1 && echo RC_OK"
    )
    proc = subprocess.run(["bash", "-c", script], cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "RC_OK" in proc.stdout
    # The pre-set directories were honoured and the failure record went to the tmp state dir.
    assert (tmp_path / "state").exists() and any((tmp_path / "state").glob("*_t_bash_failure_*.json"))


def test_revision_job_requires_run_id():
    proc = subprocess.run(
        ["bash", "-c", "unset HORMUZ_RUN_ID; HORMUZ_STDBUF_REEXEC=1 bash slurm/jobs/stonybrook_ai_cluster-revision.job"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "HORMUZ_RUN_ID" in proc.stderr
