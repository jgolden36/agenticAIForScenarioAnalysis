"""Tests for scripts/revision/software_versions.py and model_licenses.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.revision.model_licenses import render_markdown as render_licenses, rows as license_rows
from scripts.revision.software_versions import build, llm_backends, local_environment, parse_pip_freeze, runtime_inventories

REPO = Path(__file__).resolve().parents[2]


def test_local_environment_and_pip_freeze(tmp_path):
    env = local_environment(REPO)
    assert env["python"] and env["packages"]["pydantic"] and env["packages"]["langgraph"]
    pf = tmp_path / "freeze.txt"
    pf.write_text("langgraph==1.2.18\nPyYAML==6.0.3\n# comment\n-e git+https://x#egg=y\ntorch @ file:///wheel\n")
    parsed = parse_pip_freeze(pf)
    assert parsed["langgraph"] == "1.2.18" and parsed["pyyaml"] == "6.0.3" and parsed["torch"].startswith("file://")


def test_runtime_inventories_and_backends(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "runtime-01_scenarios-1-0.json").write_text(json.dumps({
        "stage": "01_scenarios", "run_id": "r", "hostname": "tesla1", "gpu_visible": "yes",
        "conda_env_active": "hormuz", "runtimes": {"python": "Python 3.11.9", "gams": "", "julia": "", "R": "", "java": "", "cuda": "12.4", "conda": "23.1"}}))
    state = tmp_path / "state"
    state.mkdir()
    (state / "r_runtime.jsonl").write_text(
        json.dumps({"stage": "03_models", "tag": "2-5", "hostname": "tesla1", "gpu": "yes",
                    "runtimes": {"python": "Python 3.11.9", "gams": "", "julia": "", "R": "", "java": "", "cuda": "12.4", "conda": "23.1"}}) + "\n"
        + json.dumps({"stage": "03_models", "tag": "2-6", "hostname": "tesla2", "gpu": "no",
                      "runtimes": {"python": "Python 3.11.9", "gams": "GAMS 45.1", "julia": "", "R": "", "java": "", "cuda": "", "conda": "23.1"}}) + "\n")
    (state / "r_scenarios.json").write_text(json.dumps({"config": {"llm": {"provider": "vllm", "model": "gpt-oss-120b"}}}))
    inv = runtime_inventories(logs, state, ["r"])
    assert len(inv) == 2 and {r["hostname"] for r in inv} == {"tesla1", "tesla2"}
    assert next(r for r in inv if r["hostname"] == "tesla2")["gams"] == "GAMS 45.1"
    backends = llm_backends(state, ["r", "missing"])
    assert backends[0]["model"] == "gpt-oss-120b" and backends[1]["state_available"] is False
    d = build(REPO, run_ids=["r"], state_dir=state, runtime_dir=logs, pip_freeze=None)
    assert d["llm_backends"][0]["model"] == "gpt-oss-120b" and any(p["package"] == "langgraph" for p in d["packages"])


def test_model_licenses_cover_registry():
    data = license_rows()
    assert len(data) >= 34 and all(r["license_notes"] for r in data)
    md = render_licenses(data)
    assert "Every registered model carries license notes" in md and "| `poles_jrc` |" in md
