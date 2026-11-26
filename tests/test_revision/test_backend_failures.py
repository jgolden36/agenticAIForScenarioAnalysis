"""The failure report must attribute each failed run to the error that ended it."""

from __future__ import annotations

import pytest

from scripts.revision.backend_failures import classify, pair, parse_errors, parse_failures, still_failing


def test_parse_failures_reads_every_log_form() -> None:
    out = (
        "[groq-a/20260215] brief build failed (rc=1).\n"
        "x | [anthropic-b/20260222] brief failed again (rc=1).\n"
        "x | [groq-c/20260301] pipeline status=failed (51s)\n"
        "x | [groq-d/20260308] pipeline status=ok (51s)\n"
    )
    assert parse_failures(out) == [("groq-a", "20260215", "brief"), ("anthropic-b", "20260222", "brief"), ("groq-c", "20260301", "scenarios")]


def test_parse_errors_keeps_the_last_exception_of_a_chain() -> None:
    err = """Traceback (most recent call last):
pydantic_core._pydantic_core.ValidationError: 1 validation error for ScenarioSet
  Input should be a valid dictionary

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
langchain_core.exceptions.OutputParserException: Failed to parse ScenarioSet from completion [{}]
"""
    errors = parse_errors(err)
    assert len(errors) == 1
    assert errors[0][0].endswith("OutputParserException")


def test_parse_errors_names_the_offending_field() -> None:
    err = """Traceback (most recent call last):
pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief
observed_indicators
  Input should be a valid list [type=list_type]
Traceback (most recent call last):
ValueError: Scenario generation returned 4 of 5 scenarios; see log.
ValueError: some unrelated problem
"""
    errors = parse_errors(err)
    assert [cls for cls, _ in errors] == ["pydantic_core._pydantic_core.ValidationError", "ValueError"]
    assert errors[0][1].endswith("observed_indicators")


@pytest.mark.parametrize(("message", "label"), [
    ("ValueError: Scenario generation returned 4 of 5 scenarios", "scenario_count_short"),
    ("x.ValidationError: 1 validation error for ScenarioSet", "scenario_schema_validation"),
    ("x.OutputParserException: Failed to parse ScenarioSet from completion", "scenario_schema_validation"),
    ("x.ValidationError: 1 validation error for WeeklyBrief: observed_indicators", "brief_schema_validation"),
    ("x.OutputParserException: Failed to parse WeeklyBrief from completion", "brief_schema_validation"),
    ("groq.BadRequestError: does not support response format `json_schema`", "json_schema_unsupported"),
    ("something else", "other"),
])
def test_classify(message: str, label: str) -> None:
    assert classify(message) == label


def test_pair_refuses_a_count_mismatch() -> None:
    with pytest.raises(ValueError, match="refusing to pair"):
        pair([("groq-a", "20260215", "brief")], [])


def test_pair_refuses_another_providers_error() -> None:
    with pytest.raises(ValueError, match="log order mismatch"):
        pair([("anthropic-a", "20260215", "brief")], [("groq.BadRequestError", "x")])


def test_still_failing_keeps_the_latest_error_and_drops_recovered_weeks() -> None:
    runs = [
        {"tag": "opus", "week_start": "2026-02-22", "status": "failed"},
        {"tag": "opus", "week_start": "2026-03-01", "status": "ok"},
    ]
    rows = [
        {"tag": "opus", "week": "20260222", "stage": "brief", "error_class": "brief_schema_validation", "error": "first"},
        {"tag": "opus", "week": "20260301", "stage": "brief", "error_class": "brief_schema_validation", "error": "fixed later"},
        {"tag": "opus", "week": "20260222", "stage": "scenarios", "error_class": "scenario_schema_validation", "error": "second"},
    ]
    kept = still_failing(runs, rows)
    assert [(r["week"], r["error"]) for r in kept] == [("20260222", "second")]
