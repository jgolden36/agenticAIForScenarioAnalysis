"""Tests for the parameter-extraction record shapes written by Stage 2."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.run_parameters import build_param_record, failed_param_record  # noqa: E402


def test_completed_record_is_approved_when_auto_approve():
    rec = build_param_record(
        "swift_contained", "poles_jrc",
        [{"name": "supply_loss_mbd", "value": 5.0}],
        runtime_seconds=1.5, auto_approve=True,
    )
    assert rec["status"] == "completed"
    assert rec["error_message"] is None
    assert rec["validation_status"] == "approved"
    assert rec["runtime_seconds"] == 1.5


def test_empty_extraction_with_warnings_is_failed():
    rec = build_param_record(
        "swift_contained", "cwatm", [],
        warnings=["Extraction failed after 3 attempts: ValidationError"],
        auto_approve=True,
    )
    assert rec["status"] == "failed"
    assert "3 attempts" in rec["error_message"]
    # A failed cell is never auto-approved.
    assert rec["validation_status"] == "pending"
    assert rec["parameters"] == []


def test_failed_record_from_exception():
    rec = failed_param_record("swift_contained", "nems", RuntimeError("boom"), runtime_seconds=0.2)
    assert rec["status"] == "failed"
    assert rec["error_message"] == "RuntimeError: boom"
    assert rec["parameters"] == []
