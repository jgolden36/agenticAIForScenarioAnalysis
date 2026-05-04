"""Tests for src/pipeline/upstream_forwarding.py.

Covers transforms (identity, to_percent, level_to_pct, mean_of_keys),
fallback ordering, structured ``commodity_price_shocks`` merge,
override-record content, no-upstream-output fallback to LLM values,
FAILED/SKIPPED upstream runs treated as missing, per-rule scenario
filters, the per-tier ``target_models`` filter, and the helium ->
semiconductor forwarding the merge mechanism powers today
(world_helium_model -> simrlfab / argonne_abm).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.state import ModelExecutionResult
from src.pipeline.upstream_forwarding import (
    ComputedShock,
    OverrideRecord,
    ParamMapping,
    SourceSpec,
    UpstreamMapping,
    clear_mapping_cache,
    compute_downstream_inputs,
    is_downstream_model_id,
    load_mapping,
    merge_into_params,
    register_overrides_in_outputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _result(
    scenario: Scenario | str,
    model_id: str,
    outputs: dict | None,
    status: ModelExecutionStatus = ModelExecutionStatus.COMPLETED,
) -> ModelExecutionResult:
    return ModelExecutionResult(
        scenario_id=scenario if isinstance(scenario, Scenario) else Scenario(scenario),
        model_id=model_id,
        status=status,
        outputs=outputs or {},
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_mapping_cache()
    yield
    clear_mapping_cache()


def _write_mapping(tmp_path: Path, body: dict) -> Path:
    p = tmp_path / "mapping.yaml"
    p.write_text(yaml.safe_dump(body), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Mapping loader
# ---------------------------------------------------------------------------


def test_load_mapping_missing_file_returns_empty_no_op(tmp_path: Path):
    mapping = load_mapping(tmp_path / "does_not_exist.yaml")
    assert isinstance(mapping, UpstreamMapping)
    assert mapping.by_model == {}
    assert mapping.warn_threshold_pct == 50.0


def test_load_mapping_parses_threshold_and_models(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "defaults": {"llm_vs_upstream_warn_threshold_pct": 75.0},
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                }
            },
        },
    )
    m = load_mapping(p)
    assert m.warn_threshold_pct == 75.0
    assert "opencge" in m.by_model
    rules = m.by_model["opencge"]
    assert len(rules) == 1
    assert rules[0].target_param == "oil_price_shock_pct"
    assert rules[0].sources[0].source_model == "poles_jrc"


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


def test_identity_transform_passes_value_through(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [_result(Scenario.A, "poles_jrc", {"peak_price_change_pct": 42.5})]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert "opencge" in out
    shock = out["opencge"][0]
    assert shock.value == 42.5
    assert shock.source_model_id == "poles_jrc"


def test_to_percent_transform_multiplies_by_100(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "fractional_change",
                                "transform": "to_percent",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [_result(Scenario.A, "poles_jrc", {"fractional_change": 0.42})]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out["opencge"][0].value == pytest.approx(42.0)


def test_level_to_pct_transform_uses_baseline(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "bornstein_krusell_rebelo",
                                "source_field": "oil_price_usd",
                                "transform": "level_to_pct",
                                "baseline": 80.0,
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(Scenario.A, "bornstein_krusell_rebelo", {"oil_price_usd": 120.0})
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out["opencge"][0].value == pytest.approx(50.0)


def test_level_to_pct_zero_baseline_returns_no_shock(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "bornstein_krusell_rebelo",
                                "source_field": "oil_price_usd",
                                "transform": "level_to_pct",
                                "baseline": 0.0,
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(Scenario.A, "bornstein_krusell_rebelo", {"oil_price_usd": 100.0})
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out == {}


def test_mean_of_keys_index_kind_converts_to_pct(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "miragrodep": {
                    "fertilizer_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "futures",
                                "source_field": "peak_price_index_per_commodity",
                                "transform": "mean_of_keys",
                                "keys": ["urea", "dap", "potash"],
                                "value_kind": "index",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(
            Scenario.A,
            "futures",
            {
                "peak_price_index_per_commodity": {
                    "urea": 1.4,
                    "dap": 1.6,
                    "potash": 1.8,
                    "wheat": 1.05,
                }
            },
        )
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out["miragrodep"][0].value == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# Fallback ordering and missing/SKIPPED/FAILED handling
# ---------------------------------------------------------------------------


def test_fallback_uses_second_source_when_first_missing(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            },
                            {
                                "source_model": "bornstein_krusell_rebelo",
                                "source_field": "oil_price_peak_pct_eps_u_no",
                                "transform": "identity",
                            },
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(Scenario.A, "poles_jrc", {"some_other_field": 99.0}),
        _result(
            Scenario.A,
            "bornstein_krusell_rebelo",
            {"oil_price_peak_pct_eps_u_no": 35.5},
        ),
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out["opencge"][0].source_model_id == "bornstein_krusell_rebelo"


def test_failed_source_treated_as_missing(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            },
                            {
                                "source_model": "bornstein_krusell_rebelo",
                                "source_field": "oil_price_peak_pct_eps_u_no",
                                "transform": "identity",
                            },
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(
            Scenario.A,
            "poles_jrc",
            {"peak_price_change_pct": 99.0},
            status=ModelExecutionStatus.FAILED,
        ),
        _result(
            Scenario.A,
            "bornstein_krusell_rebelo",
            {"oil_price_peak_pct_eps_u_no": 22.0},
        ),
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out["opencge"][0].source_model_id == "bornstein_krusell_rebelo"


def test_skipped_source_treated_as_missing(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(
            Scenario.A,
            "poles_jrc",
            {"peak_price_change_pct": 99.0},
            status=ModelExecutionStatus.SKIPPED,
        )
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out == {}


def test_no_upstream_output_yields_no_shocks_for_model(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    out = compute_downstream_inputs(Scenario.A.value, [], mapping)
    assert out == {}


def test_other_scenario_results_are_ignored(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [_result(Scenario.B, "poles_jrc", {"peak_price_change_pct": 50.0})]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out == {}


# ---------------------------------------------------------------------------
# merge_into_params: Replace-with-metadata + structured target_key
# ---------------------------------------------------------------------------


def test_merge_replaces_scalar_param_and_records_override():
    llm_params = {"oil_price_shock_pct": 100.0, "disruption_duration_months": 3}
    computed = [
        ComputedShock(
            target_param="oil_price_shock_pct",
            target_key=None,
            value=42.5,
            source_model_id="poles_jrc",
            source_field="peak_price_change_pct",
            transform="identity",
        )
    ]
    merged, records = merge_into_params("opencge", llm_params, computed)

    assert merged["oil_price_shock_pct"] == 42.5
    assert merged["disruption_duration_months"] == 3
    assert llm_params["oil_price_shock_pct"] == 100.0
    assert len(records) == 1
    rec = records[0]
    assert rec.name == "oil_price_shock_pct"
    assert rec.target_key is None
    assert rec.llm_value == 100.0
    assert rec.computed_value == 42.5
    assert rec.source_model_id == "poles_jrc"
    assert rec.source_field == "peak_price_change_pct"
    assert rec.transform == "identity"
    assert rec.deviation_pct == pytest.approx(80.7, abs=0.5)


def test_merge_handles_structured_commodity_price_shocks():
    llm_params = {
        "oil_price_shock_pct": 50.0,
        "commodity_price_shocks": {"lng": 30.0, "fertilizer": 20.0},
    }
    computed = [
        ComputedShock(
            target_param="commodity_price_shocks",
            target_key="lng",
            value=80.0,
            source_model_id="energy_flux_lng_profits",
            source_field="average_ttf_netback",
            transform="level_to_pct",
        ),
        ComputedShock(
            target_param="commodity_price_shocks",
            target_key="helium",
            value=200.0,
            source_model_id="world_helium_model",
            source_field="price_change_pct",
            transform="identity",
        ),
    ]
    merged, records = merge_into_params("opencge", llm_params, computed)

    cs = merged["commodity_price_shocks"]
    assert cs["lng"] == 80.0
    assert cs["fertilizer"] == 20.0
    assert cs["helium"] == 200.0
    assert llm_params["commodity_price_shocks"] == {"lng": 30.0, "fertilizer": 20.0}
    assert len(records) == 2
    by_key = {r.target_key: r for r in records}
    assert by_key["lng"].llm_value == 30.0
    assert by_key["lng"].computed_value == 80.0
    assert by_key["helium"].llm_value is None
    assert by_key["helium"].computed_value == 200.0


def test_merge_with_no_llm_param_records_none_for_llm_value():
    llm_params: dict = {}
    computed = [
        ComputedShock(
            target_param="oil_price_shock_pct",
            target_key=None,
            value=12.0,
            source_model_id="poles_jrc",
            source_field="peak_price_change_pct",
            transform="identity",
        )
    ]
    merged, records = merge_into_params("opencge", llm_params, computed)
    assert merged["oil_price_shock_pct"] == 12.0
    assert records[0].llm_value is None
    assert records[0].deviation_pct is None


def test_merge_no_computed_shocks_is_noop():
    llm_params = {"oil_price_shock_pct": 25.0}
    merged, records = merge_into_params("opencge", llm_params, [])
    assert merged == llm_params
    assert merged is not llm_params
    assert records == []


# ---------------------------------------------------------------------------
# register_overrides_in_outputs + helpers
# ---------------------------------------------------------------------------


def test_register_overrides_attaches_serialised_records():
    rec = OverrideRecord(
        name="oil_price_shock_pct",
        target_key=None,
        llm_value=10.0,
        computed_value=15.0,
        source_model_id="poles_jrc",
        source_field="peak_price_change_pct",
        transform="identity",
        deviation_pct=40.0,
    )
    out = register_overrides_in_outputs({"foo": 1}, [rec])
    assert "_upstream_overrides" in out
    assert out["_upstream_overrides"][0]["name"] == "oil_price_shock_pct"
    assert out["_upstream_overrides"][0]["computed_value"] == 15.0
    assert out["foo"] == 1


def test_register_overrides_accepts_dicts_too():
    out = register_overrides_in_outputs(
        {},
        [{"name": "oil_price_shock_pct", "llm_value": 1, "computed_value": 2}],
    )
    assert out["_upstream_overrides"][0]["name"] == "oil_price_shock_pct"


def test_register_overrides_empty_list_is_noop():
    original = {"a": 1}
    out = register_overrides_in_outputs(original, [])
    assert out == original


def test_is_downstream_model_id_uses_loaded_mapping():
    mapping = UpstreamMapping(
        by_model={
            "opencge": [
                ParamMapping(
                    target_param="oil_price_shock_pct",
                    target_key=None,
                    sources=(
                        SourceSpec(
                            source_model="poles_jrc",
                            source_field="peak_price_change_pct",
                            transform="identity",
                        ),
                    ),
                )
            ]
        }
    )
    assert is_downstream_model_id("opencge", mapping)
    assert not is_downstream_model_id("poles_jrc", mapping)


# ---------------------------------------------------------------------------
# End-to-end: compute_downstream_inputs -> merge_into_params for one scenario
# ---------------------------------------------------------------------------


def test_end_to_end_compute_then_merge(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    },
                    "commodity_price_shocks__helium": {
                        "target_param": "commodity_price_shocks",
                        "target_key": "helium",
                        "sources": [
                            {
                                "source_model": "world_helium_model",
                                "source_field": "price_change_pct",
                                "transform": "identity",
                            }
                        ],
                    },
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(Scenario.A, "poles_jrc", {"peak_price_change_pct": 35.0}),
        _result(Scenario.A, "world_helium_model", {"price_change_pct": 250.0}),
    ]
    computed_by_model = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert "opencge" in computed_by_model
    assert len(computed_by_model["opencge"]) == 2

    llm_params = {
        "oil_price_shock_pct": 80.0,
        "commodity_price_shocks": {"helium": 100.0, "lng": 40.0},
    }
    merged, records = merge_into_params(
        "opencge", llm_params, computed_by_model["opencge"]
    )
    assert merged["oil_price_shock_pct"] == 35.0
    assert merged["commodity_price_shocks"]["helium"] == 250.0
    assert merged["commodity_price_shocks"]["lng"] == 40.0
    assert len(records) == 2


# ---------------------------------------------------------------------------
# Per-rule scenarios filter
# ---------------------------------------------------------------------------


def test_scenarios_filter_skips_other_scenarios(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "commodity_price_shocks__water": {
                        "target_param": "commodity_price_shocks",
                        "target_key": "water",
                        "scenarios": ["infrastructure_collapse"],
                        "sources": [
                            {
                                "source_model": "cwatm",
                                "source_field": "unmet_demand_pct",
                                "transform": "identity",
                            }
                        ],
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [_result(Scenario.D, "cwatm", {"unmet_demand_pct": 70.0})]
    out = compute_downstream_inputs(Scenario.D.value, results, mapping)
    assert "opencge" not in out


def test_scenarios_filter_fires_for_listed_scenario(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "commodity_price_shocks__water": {
                        "target_param": "commodity_price_shocks",
                        "target_key": "water",
                        "scenarios": ["infrastructure_collapse"],
                        "sources": [
                            {
                                "source_model": "cwatm",
                                "source_field": "unmet_demand_pct",
                                "transform": "identity",
                            }
                        ],
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    results = [_result(Scenario.E, "cwatm", {"unmet_demand_pct": 70.0})]
    out = compute_downstream_inputs(Scenario.E.value, results, mapping)
    assert "opencge" in out
    shock = out["opencge"][0]
    assert shock.target_param == "commodity_price_shocks"
    assert shock.target_key == "water"
    assert shock.value == pytest.approx(70.0)
    assert shock.source_model_id == "cwatm"


def test_empty_scenarios_filter_applies_everywhere(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    for sid in (Scenario.A, Scenario.D, Scenario.E):
        out = compute_downstream_inputs(
            sid.value,
            [_result(sid, "poles_jrc", {"peak_price_change_pct": 12.0})],
            mapping,
        )
        assert "opencge" in out, f"rule should fire for {sid.value}"


def test_scenarios_filter_accepts_string_value(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "commodity_price_shocks__water": {
                        "target_param": "commodity_price_shocks",
                        "target_key": "water",
                        "scenarios": "infrastructure_collapse",
                        "sources": [
                            {
                                "source_model": "cwatm",
                                "source_field": "unmet_demand_pct",
                                "transform": "identity",
                            }
                        ],
                    }
                }
            }
        },
    )
    mapping = load_mapping(p)
    rule = mapping.by_model["opencge"][0]
    assert rule.scenarios == ("infrastructure_collapse",)


def test_shipped_water_rule_only_fires_for_infrastructure_collapse():
    """The water -> macro rule in the shipped configs/upstream_forwarding_mapping.yaml
    must fire ONLY for the infrastructure_collapse scenario."""
    mapping = load_mapping()
    cwatm_results_template = {"unmet_demand_pct": 70.0, "desalination_capacity_factor": 0.2}

    for sid in (Scenario.A, Scenario.B, Scenario.C, Scenario.D):
        results = [_result(sid, "cwatm", dict(cwatm_results_template))]
        out = compute_downstream_inputs(sid.value, results, mapping)
        for downstream_id, shocks in out.items():
            water_shocks = [
                s for s in shocks
                if s.target_param == "commodity_price_shocks"
                and s.target_key == "water"
            ]
            assert not water_shocks, (
                f"water shock must NOT propagate to {downstream_id} under {sid.value}"
            )

    results = [_result(Scenario.E, "cwatm", dict(cwatm_results_template))]
    out = compute_downstream_inputs(Scenario.E.value, results, mapping)
    macro_models_with_water_rule = {
        downstream_id
        for downstream_id, rules in mapping.by_model.items()
        if any(
            r.target_param == "commodity_price_shocks"
            and r.target_key == "water"
            and "infrastructure_collapse" in r.scenarios
            for r in rules
        )
    }
    assert macro_models_with_water_rule
    for downstream_id in macro_models_with_water_rule:
        assert downstream_id in out
        water_shocks = [
            s for s in out[downstream_id]
            if s.target_param == "commodity_price_shocks"
            and s.target_key == "water"
        ]
        assert len(water_shocks) == 1
        assert water_shocks[0].source_model_id == "cwatm"
        assert water_shocks[0].value == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# target_models filter (used by the orchestrator and SLURM dispatcher to
# scope the merge to one tier per barrier).
# ---------------------------------------------------------------------------


def test_target_models_filter_restricts_returned_models(tmp_path: Path):
    p = _write_mapping(
        tmp_path,
        {
            "models": {
                "opencge": {
                    "oil_price_shock_pct": {
                        "sources": [
                            {
                                "source_model": "poles_jrc",
                                "source_field": "peak_price_change_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                },
                "simrlfab": {
                    "helium_supply_reduction_pct": {
                        "sources": [
                            {
                                "source_model": "world_helium_model",
                                "source_field": "effective_supply_gap_pct",
                                "transform": "identity",
                            }
                        ]
                    }
                },
            }
        },
    )
    mapping = load_mapping(p)
    results = [
        _result(Scenario.A, "poles_jrc", {"peak_price_change_pct": 30.0}),
        _result(Scenario.A, "world_helium_model", {"effective_supply_gap_pct": 45.0}),
    ]

    # No filter: both models surface.
    everyone = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert set(everyone) == {"opencge", "simrlfab"}

    # Filter to just SimRLFab (commodity_downstream barrier).
    only_simrlfab = compute_downstream_inputs(
        Scenario.A.value, results, mapping, target_models={"simrlfab"}
    )
    assert set(only_simrlfab) == {"simrlfab"}
    assert only_simrlfab["simrlfab"][0].value == pytest.approx(45.0)

    # Filter to just OpenCGE (macro barrier).
    only_opencge = compute_downstream_inputs(
        Scenario.A.value, results, mapping, target_models={"opencge"}
    )
    assert set(only_opencge) == {"opencge"}


# ---------------------------------------------------------------------------
# Helium -> semiconductor forwarding (the new commodity_downstream tier)
# ---------------------------------------------------------------------------


def test_world_helium_model_forwards_into_simrlfab(tmp_path: Path):
    """Acceptance test: world_helium_model.effective_supply_gap_pct must
    flow into simrlfab.helium_supply_reduction_pct under the shipped
    configs/upstream_forwarding_mapping.yaml."""
    mapping = load_mapping()
    helium_outputs = {
        "effective_supply_gap_pct": 32.5,
        "price_change_pct": 410.0,
        "disruption_duration_months": 6.0,
    }
    results = [_result(Scenario.D, "world_helium_model", helium_outputs)]

    per_downstream = compute_downstream_inputs(
        Scenario.D.value,
        results,
        mapping,
        target_models={"simrlfab"},
    )
    assert "simrlfab" in per_downstream
    by_param = {
        s.target_param: s for s in per_downstream["simrlfab"]
    }
    assert "helium_supply_reduction_pct" in by_param
    assert by_param["helium_supply_reduction_pct"].value == pytest.approx(32.5)
    assert by_param["helium_supply_reduction_pct"].source_model_id == "world_helium_model"
    assert by_param["helium_supply_reduction_pct"].source_field == "effective_supply_gap_pct"
    assert "disruption_duration_months" in by_param
    assert by_param["disruption_duration_months"].value == pytest.approx(6.0)


def test_world_helium_model_forwards_into_argonne_abm():
    """Same shipped-mapping acceptance test for Argonne ABM."""
    mapping = load_mapping()
    helium_outputs = {
        "effective_supply_gap_pct": 27.0,
        "disruption_duration_months": 4.0,
    }
    results = [_result(Scenario.B, "world_helium_model", helium_outputs)]

    per_downstream = compute_downstream_inputs(
        Scenario.B.value,
        results,
        mapping,
        target_models={"argonne_abm"},
    )
    assert "argonne_abm" in per_downstream
    by_param = {s.target_param: s for s in per_downstream["argonne_abm"]}
    assert by_param["supply_shock_pct"].value == pytest.approx(27.0)
    assert by_param["supply_shock_pct"].source_model_id == "world_helium_model"
    assert by_param["disruption_duration_months"].value == pytest.approx(4.0)


def test_helium_merge_preserves_llm_extracted_calibration_params():
    """Categorical (neon_supply_status) and calibration
    (fab_utilization_baseline, demand_response_elasticity) parameters
    have no upstream source -- they must remain on the LLM-extracted
    value after merge_into_params."""
    mapping = load_mapping()
    helium_outputs = {
        "effective_supply_gap_pct": 18.0,
        "disruption_duration_months": 3.0,
    }
    results = [_result(Scenario.A, "world_helium_model", helium_outputs)]

    # SimRLFab
    per_simrlfab = compute_downstream_inputs(
        Scenario.A.value, results, mapping, target_models={"simrlfab"}
    )
    llm_simrlfab = {
        "helium_supply_reduction_pct": 5.0,
        "neon_supply_status": "constrained",
        "fab_utilization_baseline": 0.92,
        "disruption_duration_months": 1.0,
    }
    merged, records = merge_into_params(
        "simrlfab", llm_simrlfab, per_simrlfab["simrlfab"]
    )
    assert merged["helium_supply_reduction_pct"] == pytest.approx(18.0)
    assert merged["disruption_duration_months"] == pytest.approx(3.0)
    # LLM-only fields preserved exactly
    assert merged["neon_supply_status"] == "constrained"
    assert merged["fab_utilization_baseline"] == pytest.approx(0.92)
    # Override records cover only the two replaced params
    replaced = {(r.name, r.target_key) for r in records}
    assert replaced == {
        ("helium_supply_reduction_pct", None),
        ("disruption_duration_months", None),
    }

    # Argonne ABM
    per_abm = compute_downstream_inputs(
        Scenario.A.value, results, mapping, target_models={"argonne_abm"}
    )
    llm_abm = {
        "supply_shock_pct": 4.0,
        "demand_response_elasticity": -0.4,
        "disruption_duration_months": 1.0,
    }
    merged_abm, records_abm = merge_into_params(
        "argonne_abm", llm_abm, per_abm["argonne_abm"]
    )
    assert merged_abm["supply_shock_pct"] == pytest.approx(18.0)
    assert merged_abm["demand_response_elasticity"] == pytest.approx(-0.4)
    assert merged_abm["disruption_duration_months"] == pytest.approx(3.0)


def test_skipped_world_helium_model_falls_through_to_llm_values():
    """When world_helium_model is SKIPPED, merge_into_params receives no
    computed shocks for SimRLFab/Argonne ABM, so the LLM-extracted
    parameters survive untouched."""
    mapping = load_mapping()
    results = [
        _result(
            Scenario.A,
            "world_helium_model",
            {"effective_supply_gap_pct": 99.0},
            status=ModelExecutionStatus.SKIPPED,
        )
    ]
    per_downstream = compute_downstream_inputs(
        Scenario.A.value,
        results,
        mapping,
        target_models={"simrlfab", "argonne_abm"},
    )
    assert per_downstream == {}

    llm_simrlfab = {
        "helium_supply_reduction_pct": 12.5,
        "neon_supply_status": "normal",
        "fab_utilization_baseline": 0.85,
        "disruption_duration_months": 2.0,
    }
    merged, records = merge_into_params("simrlfab", llm_simrlfab, [])
    assert merged == llm_simrlfab
    assert records == []


def test_world_helium_model_falls_back_to_price_change_pct(tmp_path: Path):
    """When effective_supply_gap_pct is missing, the second-source
    fallback (price_change_pct) supplies the SimRLFab input."""
    mapping = load_mapping()
    # Only price_change_pct present; no effective_supply_gap_pct.
    results = [
        _result(
            Scenario.D,
            "world_helium_model",
            {"price_change_pct": 88.0, "disruption_duration_months": 6.0},
        )
    ]
    per = compute_downstream_inputs(
        Scenario.D.value, results, mapping, target_models={"simrlfab"}
    )
    by_param = {s.target_param: s for s in per["simrlfab"]}
    assert by_param["helium_supply_reduction_pct"].value == pytest.approx(88.0)
    assert by_param["helium_supply_reduction_pct"].source_field == "price_change_pct"


# ---------------------------------------------------------------------------
# Dict-shaped results (SLURM dispatcher path)
# ---------------------------------------------------------------------------


def test_dict_shaped_results_supported():
    mapping = UpstreamMapping(
        by_model={
            "opencge": [
                ParamMapping(
                    target_param="oil_price_shock_pct",
                    target_key=None,
                    sources=(
                        SourceSpec(
                            source_model="poles_jrc",
                            source_field="peak_price_change_pct",
                            transform="identity",
                        ),
                    ),
                )
            ]
        }
    )
    results = [
        {
            "scenario_id": "swift_contained",
            "model_id": "poles_jrc",
            "status": "completed",
            "outputs": {"peak_price_change_pct": 17.0},
        }
    ]
    out = compute_downstream_inputs(Scenario.A.value, results, mapping)
    assert out["opencge"][0].value == 17.0


# ---------------------------------------------------------------------------
# Backwards-compat shim
# ---------------------------------------------------------------------------


def test_backwards_compat_shim_re_exports_public_symbols():
    """The src.pipeline.upstream_to_macro shim must keep working so
    legacy imports don't break."""
    from src.pipeline import upstream_to_macro as legacy

    assert legacy.compute_macro_inputs is compute_downstream_inputs
    assert legacy.is_macro_model_id is is_downstream_model_id
    assert legacy.merge_into_params is merge_into_params
    assert legacy.UpstreamMapping is UpstreamMapping
    assert legacy.ParamMapping is ParamMapping
    assert legacy.SourceSpec is SourceSpec
    assert legacy.ComputedShock is ComputedShock
    assert legacy.OverrideRecord is OverrideRecord
