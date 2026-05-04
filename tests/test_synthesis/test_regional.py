"""Tests for the regional / sectoral distributional extractor.

Covers:
- ``extract_regional_records`` against fixture outputs that mirror the
  shapes produced by MIRAGRODEP, PyCGE, SahysMod, and TEMOA.
- ``aggregate_to_unified`` mapping native ids to the unified taxonomy
  (with the wildcard fallback and the once-per-pair warning behaviour).
- ``_format_synthesis_inputs`` wires the new prompt fields without
  breaking the existing prompt vars.
- An integration test that runs ``slurm/scripts/export_results.main()``
  end-to-end against a synthetic state directory containing one
  MIRAGRODEP-shaped result and one SahysMod-shaped result, and asserts
  the new CSVs are produced with the expected rows.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------
# Helper: write the per-test crosswalk + spec files into a tmp configs/
# dir and rebind the loader cache to point at them.
# --------------------------------------------------------------------


def _patch_yaml_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    crosswalk: dict,
    spec: dict,
) -> tuple[Path, Path]:
    import yaml

    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cw_path = cfg_dir / "region_crosswalk.yaml"
    spec_path = cfg_dir / "distributional_outputs.yaml"
    cw_path.write_text(yaml.safe_dump(crosswalk), encoding="utf-8")
    spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")

    from src.synthesis import regional

    regional.reset_caches()
    monkeypatch.setattr(regional, "_DEFAULT_CROSSWALK_PATH", cw_path)
    monkeypatch.setattr(regional, "_DEFAULT_DISTRIBUTIONAL_PATH", spec_path)
    return cw_path, spec_path


# --------------------------------------------------------------------
# extract_regional_records
# --------------------------------------------------------------------


def test_extract_regional_list_miragrodep(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={
            "miragrodep": {
                "USA": "US",
                "SAU": "MENA_GCC",
                "QAT": "MENA_GCC",
                "CHN": "CHN",
                "*": "ROW",
            }
        },
        spec={
            "miragrodep": {
                "regional_vars": {
                    "kind": "regional",
                    "region_col": "region",
                    "value_cols": ["welfare_pct", "gdp_pct"],
                }
            }
        },
    )
    from src.synthesis.regional import extract_regional_records

    outputs = {
        "regional_vars": [
            {"region": "USA", "welfare_pct": -1.2, "gdp_pct": -0.4},
            {"region": "SAU", "welfare_pct": -3.1, "gdp_pct": -1.2},
            {"region": "QAT", "welfare_pct": -2.5, "gdp_pct": -0.9},
            {"region": "CHN", "welfare_pct": 0.4, "gdp_pct": 0.1},
            {"region": "ZZZ", "welfare_pct": 0.0, "gdp_pct": 0.0},
        ],
    }
    records = extract_regional_records("miragrodep", outputs)
    assert len(records) == 5 * 2
    by_region = {(r.native_region, r.value_label): r for r in records}
    assert by_region[("USA", "welfare_pct")].unified_region == "US"
    assert by_region[("SAU", "welfare_pct")].unified_region == "MENA_GCC"
    assert by_region[("ZZZ", "gdp_pct")].unified_region == "ROW"


def test_extract_sectoral_dict_pycge(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"pycge": {"*": "US"}},
        spec={
            "pycge": {
                "sectoral_output_pct_change": {
                    "kind": "sectoral_dict",
                    "value_label": "output_pct_change",
                }
            }
        },
    )
    from src.synthesis.regional import extract_regional_records

    outputs = {
        "sectoral_output_pct_change": {
            "agriculture": -0.7,
            "manufacturing": -1.4,
            "services": -0.3,
        }
    }
    records = extract_regional_records("pycge", outputs)
    assert {r.sector for r in records} == {"agriculture", "manufacturing", "services"}
    for r in records:
        assert r.unified_region == "US"
        assert r.value_label == "output_pct_change"


def test_extract_polygon_dict_sahysmod_picks_latest(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"sahysmod": {"*": "MENA_GCC"}},
        spec={
            "sahysmod": {
                "soil_salinity_dS_m": {
                    "kind": "regional_polygon_dict",
                    "value_label": "soil_salinity_dS_m",
                }
            }
        },
    )
    from src.synthesis.regional import extract_regional_records

    outputs = {
        "soil_salinity_dS_m": {
            "1": {"y0": 1.5, "y1": 2.0, "y2": 4.5},
            "2": {"y0": 1.0, "y2": 1.2},
        }
    }
    records = extract_regional_records("sahysmod", outputs)
    assert {r.native_region: r.value for r in records} == {"1": 4.5, "2": 1.2}
    assert all(r.unified_region == "MENA_GCC" for r in records)


def test_extract_regional_temoa_with_value_col(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"temoa": {"R1": "US", "R2": "US", "*": "ROW"}},
        spec={
            "temoa": {
                "Output_VFlow_Out": {
                    "kind": "regional",
                    "region_col": "regions",
                    "value_cols": ["vflow_out"],
                }
            }
        },
    )
    from src.synthesis.regional import extract_regional_records

    records = extract_regional_records(
        "temoa",
        {
            "Output_VFlow_Out": [
                {"regions": "R1", "vflow_out": 100.0},
                {"regions": "R2", "vflow_out": 80.0},
            ]
        },
    )
    assert len(records) == 2
    assert all(r.unified_region == "US" for r in records)


# --------------------------------------------------------------------
# aggregate_to_unified
# --------------------------------------------------------------------


def test_aggregate_to_unified_uses_mean_for_pct_and_sum_otherwise(
    monkeypatch, tmp_path, caplog,
):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"miragrodep": {"SAU": "MENA_GCC", "QAT": "MENA_GCC"}},
        spec={
            "miragrodep": {
                "regional_vars": {
                    "kind": "regional",
                    "region_col": "region",
                    "value_cols": ["welfare_pct", "exports_volume"],
                }
            }
        },
    )
    from src.synthesis.regional import aggregate_to_unified, extract_regional_records

    records = extract_regional_records(
        "miragrodep",
        {
            "regional_vars": [
                {"region": "SAU", "welfare_pct": -3.0, "exports_volume": 100.0},
                {"region": "QAT", "welfare_pct": -1.0, "exports_volume": 50.0},
            ]
        },
    )
    unified = aggregate_to_unified(records)
    welfare = unified[("miragrodep", "regional_vars", "welfare_pct")]
    exports = unified[("miragrodep", "regional_vars", "exports_volume")]
    assert welfare["MENA_GCC"] == pytest.approx(-2.0)
    assert exports["MENA_GCC"] == pytest.approx(150.0)


def test_unmapped_native_falls_through_to_row(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"miragrodep": {}},
        spec={
            "miragrodep": {
                "regional_vars": {
                    "kind": "regional",
                    "region_col": "region",
                    "value_cols": ["v"],
                }
            }
        },
    )
    from src.synthesis.regional import extract_regional_records

    records = extract_regional_records(
        "miragrodep", {"regional_vars": [{"region": "ATLANTIS", "v": 1.0}]},
    )
    assert records[0].unified_region == "ROW"


def test_dispersion_metrics_sorted_by_range(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"miragrodep": {
            "USA": "US", "CHN": "CHN", "EU27": "EU", "SAU": "MENA_GCC",
        }},
        spec={
            "miragrodep": {
                "regional_vars": {
                    "kind": "regional",
                    "region_col": "region",
                    "value_cols": ["welfare_pct"],
                }
            }
        },
    )
    from src.synthesis.regional import dispersion_metrics, extract_regional_records

    records = extract_regional_records(
        "miragrodep",
        {
            "regional_vars": [
                {"region": "USA", "welfare_pct": -0.5},
                {"region": "CHN", "welfare_pct": 0.5},
                {"region": "EU27", "welfare_pct": -2.0},
                {"region": "SAU", "welfare_pct": -8.0},
            ]
        },
    )
    metrics = dispersion_metrics(records)
    assert metrics
    m = metrics[0]
    assert m.bottom_region == "MENA_GCC"
    assert m.bottom_value == pytest.approx(-8.0)
    assert m.top_region == "CHN"
    assert m.top_value == pytest.approx(0.5)


# --------------------------------------------------------------------
# Synthesizer prompt wiring (region/sectoral keys flow through)
# --------------------------------------------------------------------


def test_format_synthesis_inputs_includes_distributional_keys(
    monkeypatch, tmp_path,
):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={"miragrodep": {"USA": "US", "SAU": "MENA_GCC"}},
        spec={
            "miragrodep": {
                "regional_vars": {
                    "kind": "regional",
                    "region_col": "region",
                    "value_cols": ["welfare_pct"],
                }
            }
        },
    )
    from src.common.types import ModelExecutionStatus, Scenario
    from src.pipeline.state import ModelExecutionResult, ScenarioNarrativeState
    from src.synthesis.synthesizer import _format_synthesis_inputs

    narrative = ScenarioNarrativeState(
        scenario_id=Scenario.A,
        label="Swift Contained",
        narrative="A short test narrative.",
        quantitative_assumptions={},
    )
    result = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="miragrodep",
        status=ModelExecutionStatus.COMPLETED,
        outputs={
            "regional_vars": [
                {"region": "USA", "welfare_pct": -0.5},
                {"region": "SAU", "welfare_pct": -3.0},
            ]
        },
    )
    out = _format_synthesis_inputs({
        "narrative": narrative,
        "results": [result],
        "consistency_flags": [],
    })
    assert "regional_breakdowns" in out
    assert "sectoral_breakdowns" in out
    assert "MENA_GCC" in out["regional_breakdowns"]
    assert "US" in out["regional_breakdowns"]


# --------------------------------------------------------------------
# End-to-end: export_results.main produces the new CSVs.
# --------------------------------------------------------------------


def _write_state(state_dir: Path, run_id: str, results: list[dict]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(results):
        (state_dir / f"{run_id}_model_{i:03d}.json").write_text(
            json.dumps(r), encoding="utf-8",
        )


def test_export_results_writes_distributional_csvs(monkeypatch, tmp_path):
    _patch_yaml_paths(
        monkeypatch, tmp_path,
        crosswalk={
            "miragrodep": {"USA": "US", "SAU": "MENA_GCC", "QAT": "MENA_GCC", "CHN": "CHN"},
            "sahysmod": {"*": "MENA_GCC"},
        },
        spec={
            "miragrodep": {
                "regional_vars": {
                    "kind": "regional",
                    "region_col": "region",
                    "value_cols": ["welfare_pct"],
                }
            },
            "sahysmod": {
                "soil_salinity_dS_m": {
                    "kind": "regional_polygon_dict",
                    "value_label": "soil_salinity_dS_m",
                }
            },
            "_aggregation_overrides": {
                "sahysmod.soil_salinity_dS_m": "mean",
            },
        },
    )

    from slurm.scripts import export_results, stage_utils

    monkeypatch.setattr(stage_utils, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(export_results, "get_project_root", lambda: tmp_path)
    state_dir = tmp_path / "data" / "pipeline_state"
    reports_dir = tmp_path / "data" / "reports"

    run_id = "test_run"
    monkeypatch.setenv("HORMUZ_RUN_ID", run_id)

    results: list[dict[str, Any]] = [
        {
            "scenario_id": "swift_contained",
            "model_id": "miragrodep",
            "status": "completed",
            "outputs": {
                "regional_vars": [
                    {"region": "USA", "welfare_pct": -0.5},
                    {"region": "SAU", "welfare_pct": -3.0},
                    {"region": "QAT", "welfare_pct": -2.5},
                    {"region": "CHN", "welfare_pct": 0.4},
                ],
            },
        },
        {
            "scenario_id": "swift_contained",
            "model_id": "sahysmod",
            "status": "completed",
            "outputs": {
                "soil_salinity_dS_m": {
                    "1": {"y0": 1.0, "y1": 2.5},
                    "2": {"y0": 1.2, "y1": 3.5},
                },
            },
        },
    ]
    _write_state(state_dir, run_id, results)

    rc = export_results.main(["--run-id", run_id, "--no-llm"])
    assert rc == 0

    csv_dir = reports_dir / run_id / "csv"
    assert csv_dir.exists(), f"expected csv dir at {csv_dir}"

    native_path = csv_dir / "regional_outcomes_native.csv"
    unified_path = csv_dir / "regional_outcomes_unified.csv"
    assert native_path.exists()
    assert unified_path.exists()

    with open(unified_path, newline="", encoding="utf-8") as f:
        unified_rows = list(csv.DictReader(f))
    by_region = {
        (row["model_id"], row["unified_region"], row["value_label"]): float(row["value"])
        for row in unified_rows
    }
    assert by_region[("miragrodep", "MENA_GCC", "welfare_pct")] == pytest.approx(-2.75)
    assert by_region[("miragrodep", "US", "welfare_pct")] == pytest.approx(-0.5)
    assert by_region[("miragrodep", "CHN", "welfare_pct")] == pytest.approx(0.4)
    assert by_region[("sahysmod", "MENA_GCC", "soil_salinity_dS_m")] == pytest.approx(3.0)

    with open(native_path, newline="", encoding="utf-8") as f:
        native_rows = list(csv.DictReader(f))
    miragrodep_natives = {
        row["native_region"] for row in native_rows if row["model_id"] == "miragrodep"
    }
    assert miragrodep_natives == {"USA", "SAU", "QAT", "CHN"}
