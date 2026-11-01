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


def _lock_root(tmp_path: Path, run_id: str, holder: str) -> Path:
    """A fake project root whose slurm/jobs is the real one, with a pre-existing lock."""
    root = tmp_path / "root"
    (root / "slurm").mkdir(parents=True)
    (root / "slurm" / "jobs").symlink_to(JOBS, target_is_directory=True)
    lock = root / "slurm" / "logs" / run_id / "revision.lock.d"
    lock.mkdir(parents=True)
    (lock / "job_id").write_text(holder + "\n")
    return root


def _stub_squeue(tmp_path: Path, running: bool) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "squeue"
    body = 'echo "999999 batch hormuz-revision user R 0:10 1 node"' if running else "exit 0"
    stub.write_text("#!/bin/bash\n" + body + "\n")
    stub.chmod(0o755)
    return bindir


def _run_revision_job(root: Path, bindir: Path, run_id: str) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, "PATH": f"{bindir}:{os.environ.get('PATH', '')}", "HORMUZ_STDBUF_REEXEC": "1",
           "SLURM_SUBMIT_DIR": str(root), "HORMUZ_RUN_ID": run_id, "HORMUZ_CONDA_ENV": "definitely_missing_env"}
    env.pop("SLURM_JOB_ID", None)
    return subprocess.run(["bash", str(JOBS / "stonybrook_ai_cluster-revision.job")], cwd=root,
                          capture_output=True, text=True, env=env, timeout=120)


def test_revision_job_refuses_to_start_when_holder_is_running(tmp_path):
    root = _lock_root(tmp_path, "locktest", "999999")
    proc = _run_revision_job(root, _stub_squeue(tmp_path, running=True), "locktest")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "999999" in proc.stderr and "scancel 999999" in proc.stderr
    # The other job's lock is left in place.
    assert (root / "slurm" / "logs" / "locktest" / "revision.lock.d" / "job_id").read_text().strip() == "999999"


def test_revision_job_removes_stale_lock_and_releases_its_own(tmp_path):
    root = _lock_root(tmp_path, "locktest", "999999")
    proc = _run_revision_job(root, _stub_squeue(tmp_path, running=False), "locktest")
    assert "stale lock from job 999999" in proc.stdout
    # The job continues past the lock (and fails later at conda activation in this
    # environment); the EXIT trap releases the lock it took.
    assert proc.returncode != 3
    assert not (root / "slurm" / "logs" / "locktest" / "revision.lock.d").exists()
