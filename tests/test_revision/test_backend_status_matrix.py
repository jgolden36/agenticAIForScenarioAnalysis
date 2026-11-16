"""A backend's status must reflect model work done, not the recorded run status."""

from __future__ import annotations

from typing import Any

from scripts.revision.backend_status_matrix import build_matrix, render


def _run(tag: str, week: str, run_id: str, status: str = "ok") -> dict[str, Any]:
    return {"tag": tag, "week_start": week, "run_id": run_id, "status": status}


def _row(completed: int, clean: bool) -> dict[str, Any]:
    return {"completed": str(completed), "clean_synthesis": str(clean), "sections_failed": "0" if clean else "3", "sections_total": "30"}


def _result() -> dict[str, Any]:
    source = [_run("sonnet", "2026-02-15", "j1"), _run("sonnet", "2026-02-22", "j2"),
              _run("old", "2026-02-15", "j3", "brief_failed"), _run("old", "2026-02-22", "j4", "brief_failed")]
    reruns = [_run("sonnet", "2026-02-22", "r2")]
    added = [_run("new", "2026-02-15", "a1"), _run("new", "2026-02-22", "a2", "failed")]
    comparison = {"j1": _row(48, True), "j2": _row(0, False), "r2": _row(47, False), "a1": _row(48, True)}
    return build_matrix(source, reruns, added, comparison, {"old"})


def test_zero_scenario_run_recorded_ok_is_not_model_work() -> None:
    sonnet = next(s for s in _result()["summary"] if s["backend"] == "sonnet")
    assert sonnet["first_batch_recorded_ok"] == 2
    assert sonnet["first_batch_did_model_work"] == 1
    assert sonnet["first_batch_clean"] == 1


def test_rerun_updates_current_but_keeps_the_original() -> None:
    result = _result()
    sonnet = next(s for s in result["summary"] if s["backend"] == "sonnet")
    assert (sonnet["weeks_rerun"], sonnet["current_did_model_work"], sonnet["current_clean"]) == (1, 2, 1)
    assert sonnet["completed_models_per_working_week"] == [47, 48]
    week = next(r for r in result["rows"] if r["backend"] == "sonnet" and r["week"] == "2026-02-22")
    assert (week["original"]["run_id"], week["current"]["run_id"]) == ("j2", "r2")


def test_retired_backend_stays_failed_and_marked() -> None:
    old = next(s for s in _result()["summary"] if s["backend"] == "old")
    assert old["retired"] is True
    assert (old["first_batch_recorded_ok"], old["current_did_model_work"]) == (0, 0)


def test_added_backend_is_never_merged_into_an_original_row() -> None:
    result = _result()
    new = next(s for s in result["summary"] if s["backend"] == "new")
    assert new["group"] == "added"
    assert (new["first_batch_recorded_ok"], new["current_did_model_work"], new["current_clean"]) == (1, 1, 1)
    assert all(r["added"] is None for r in result["rows"] if r["backend"] == "old")


def test_render_marks_each_week() -> None:
    text = render(_result())
    assert "old (retired)" in text
    assert "| sonnet | W | w |" in text
    assert "| old | - | - |" in text
