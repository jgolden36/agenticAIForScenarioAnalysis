"""prepare_supplementary_run.py copies only the target models and their upstream sources."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.revision.prepare_supplementary_run import model_closure, prepare  # noqa: E402


def _params(d: Path, run: str, i: int, scenario: str, model: str, status: str = "completed"):
    rec = {"scenario_id": scenario, "model_id": model, "status": status,
           "parameters": [{"name": "x", "value": 1.0}] if status != "failed" else None}
    (d / f"{run}_params_{i}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_closure_follows_forwarding_transitively():
    c = model_closure(["opencge"])
    # opencge <- poles_jrc <- aisdb / ais_project (rerouting cost). Since
    # 2026-11-14 opencge reads LNGST's TTF change directly, not Energy
    # Flux's netback, so energy_flux_lng_profits is no longer upstream.
    assert {"opencge", "lngst", "poles_jrc", "aisdb", "ais_project"} <= set(c)
    assert "energy_flux_lng_profits" not in c
    assert {"energy_flux_lng_profits", "lngst"} <= set(model_closure(["energy_flux_lng_profits"]))


def test_prepare_copies_subset_and_records_gaps(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    rows = [("A", "lngst"), ("A", "energy_flux_lng_profits"), ("A", "pycge"), ("B", "lngst")]
    for i, (s, m) in enumerate(rows):
        _params(src, "may", i, s, m)
    _params(src, "may", 9, "B", "energy_flux_lng_profits", status="failed")
    (src / "may_scenarios.json").write_text("[]", encoding="utf-8")

    m = prepare("may", "supp", src, dst, ["energy_flux_lng_profits"])
    assert m["model_closure"] == ["energy_flux_lng_profits", "lngst"]
    assert m["n_params_copied"] == 3  # pycge and the failed record are left out
    assert "B/energy_flux_lng_profits" in m["missing_or_failed_in_source"]
    assert (dst / "supp_scenarios.json").exists()
    rec = json.loads((dst / "supp_params_0.json").read_text())
    assert rec["supplementary_of"]["run_id"] == "may"
    # Source files untouched.
    assert "supplementary_of" not in json.loads((src / "may_params_0.json").read_text())

    with pytest.raises(FileExistsError):
        prepare("may", "supp", src, dst, ["energy_flux_lng_profits"])
    with pytest.raises(ValueError):
        prepare("may", "may", src, src, ["lngst"])


def test_default_exclusions_drop_unrunnable_fallbacks(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _params(src, "may", 0, "A", "sahysmod")
    m = prepare("may", "supp", src, tmp_path / "dst", ["opencge"])
    assert "sahysmod" not in m["model_closure"]
    assert "bornstein_krusell_rebelo" in m["excluded_fallback_sources"]
