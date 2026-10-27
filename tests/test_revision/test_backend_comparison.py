"""Tests for scripts/revision/backend_comparison.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.revision.backend_comparison import compare, main, render_markdown


def _write_run(root: Path, state: Path, backend_dir: str, week: str, model: str, completed: int, failed_sections: int, clean: bool = True):
    run_id = f"weekly_{week}"
    report = root / backend_dir / run_id
    (report / "csv").mkdir(parents=True)
    sdir = state / backend_dir
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{run_id}_scenarios.json").write_text(json.dumps({
        "scenarios_validated": True, "config": {"llm": {"provider": "vllm", "model": model}},
        "scenario_narratives": [{"scenario_id": "swift_contained"}]}))
    for i in range(completed):
        (sdir / f"{run_id}_model_macro_{i}.json").write_text(json.dumps({
            "scenario_id": "swift_contained", "model_id": f"m{i}", "status": "completed", "runtime_seconds": 1.0,
            "started_at": f"2026-03-01T00:00:{i:02d}+00:00", "completed_at": f"2026-03-01T00:01:{i:02d}+00:00", "manifest_name": "models_macro"}))
    for i in range(3):
        (sdir / f"{run_id}_params_{i}.json").write_text(json.dumps({"validation_status": "approved", "runtime_seconds": 4.0}))
    synthesis = {
        "synthesis_results": [{"scenario_id": "swift_contained", "outcome_variable": "x", "value": "1"}] if clean or failed_sections < 6 else [],
        "context_budget_summary": {"section_calls": 6, "sections_failed": failed_sections},
        "context_budget_events": [{"status": "failed", "error": "LengthFinishReasonError"}] * failed_sections,
        "synthesis_validated": True,
    }
    (sdir / f"{run_id}_synthesis.json").write_text(json.dumps(synthesis))
    (report / "synthesis.json").write_text(json.dumps(synthesis))


def test_compare_groups_by_backend_and_flags_failed_backends(tmp_path):
    reports = tmp_path / "reports"
    state = tmp_path / "state"
    _write_run(reports, state, "backend_a", "20260301", "gpt-oss-120b", completed=5, failed_sections=0)
    _write_run(reports, state, "backend_a", "20260308", "gpt-oss-120b", completed=3, failed_sections=2)
    _write_run(reports, state, "backend_b", "20260301", "sonnet-4.6", completed=0, failed_sections=6, clean=False)

    result = compare(reports, state)
    assert set(result["summary"]) == {"gpt-oss-120b", "sonnet-4.6"}
    a = result["summary"]["gpt-oss-120b"]
    assert a["n_runs"] == 2 and a["clean_weeks"] == ["20260301"] and a["completed_per_week"] == [5, 3]
    assert a["clean_rate"] == 0.5 and a["completed_mean"] == 4.0
    assert "sonnet-4.6" in result["failed_backends"]
    row = next(r for r in result["rows"] if r["week"] == "20260301" and r["backend"] == "gpt-oss-120b")
    assert row["cells_attempted"] == 3 and row["denominator_basis"] == "parameter_sets"
    assert row["model_span_s"] == 64.0 and row["s_per_completed_model"] == 1.0
    # The same week exists under both backend directories; each run must resolve its own state.
    row_b = next(r for r in result["rows"] if r["backend"] == "sonnet-4.6")
    assert row_b["completed"] == 0 and row_b["week"] == "20260301"
    assert row["review_mode"] == "auto_approved"
    md = render_markdown(result)
    assert "## Backends with no clean week" in md and "sonnet-4.6" in md


def test_main_writes_artifacts_and_backend_map(tmp_path):
    reports = tmp_path / "reports"
    state = tmp_path / "state"
    _write_run(reports, state, "dirA", "20260301", "", completed=2, failed_sections=0)
    bm = tmp_path / "map.json"
    bm.write_text(json.dumps({"dirA": "mapped-backend"}))
    out = tmp_path / "docs"
    assert main(["--reports-root", str(reports), "--state-root", str(state), "--backend-map", str(bm), "--out-dir", str(out)]) == 0
    rows = list(csv.DictReader(open(out / "backend_comparison.csv")))
    assert rows[0]["backend"] == "mapped-backend"
    assert (out / "backend_comparison.md").exists() and (out / "backend_comparison.json").exists()
