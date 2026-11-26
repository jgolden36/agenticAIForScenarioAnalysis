"""Merging re-executed cells must add only lost cells and leave originals alone."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.revision.merge_refilled_cells import check_overrides, compare_outputs, merge


def _write(state: Path, name: str, scenario: str, model: str, status: str = "completed", outputs: dict | None = None) -> None:
    (state / name).write_text(json.dumps({"scenario_id": scenario, "model_id": model, "status": status, "outputs": outputs or {}}), encoding="utf-8")


def test_compare_outputs_flags_only_real_differences() -> None:
    result = compare_outputs({"a": 1.0, "b": 2.0, "_runtime": 5.0, "gone": 1.0}, {"a": 1.0, "b": 2.5, "_runtime": 9.0, "new": 1.0})
    assert [d["key"] for d in result["different"]] == ["b"]
    assert result["only_original"] == ["gone"]
    assert result["only_refilled"] == ["new"]


def test_check_overrides_classifies_each_record() -> None:
    fill = {("D", "poles"): {"status": "completed", "outputs": {"peak": 51.82}}, ("E", "poles"): {"status": "failed"}}
    overrides = {
        "D": {"fed": [
            {"name": "x", "transform": "identity", "computed_value": 51.82, "source_model_id": "poles", "source_field": "peak"},
            {"name": "y", "transform": "identity", "computed_value": 60.0, "source_model_id": "poles", "source_field": "peak"},
            {"name": "z", "transform": "to_percent", "computed_value": 1.0, "source_model_id": "poles", "source_field": "peak"},
        ]},
        "E": {"fed": [{"name": "x", "transform": "identity", "computed_value": 1.0, "source_model_id": "poles", "source_field": "peak"}]},
    }
    result = check_overrides(overrides, fill)
    assert result["counts"] == {"match": 1, "mismatch": 1, "not_checked_transform": 1, "not_checked_source_not_completed": 1}
    assert result["mismatches"][0]["name"] == "y"


def test_merge_adds_lost_cells_and_keeps_originals(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    _write(state, "may_model_0.json", "C", "poles", outputs={"peak": 58.25})
    _write(state, "fill_model_commodity_0.json", "C", "poles", outputs={"peak": 58.25})
    _write(state, "fill_model_commodity_1.json", "D", "poles", outputs={"peak": 51.82})
    before = (state / "may_model_0.json").read_bytes()

    out = tmp_path / "merged"
    result = merge("may", "fill", state, out)

    assert [(a["scenario"], a["model"]) for a in result["added"]] == [("D", "poles")]
    assert (state / "may_model_0.json").read_bytes() == before
    assert (out / "may_model_0.json").read_bytes() == before
    refilled = json.loads((out / "may_model_refilled_D_poles.json").read_text(encoding="utf-8"))
    assert refilled["refilled_from_run"] == "fill"
    assert result["reproducibility"][0]["different"] == []
    assert not list(state.glob("may_model_refilled_*"))
