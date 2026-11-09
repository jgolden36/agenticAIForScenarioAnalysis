"""The expression evaluator and the game-state-to-parameters mapping."""
from __future__ import annotations

import pytest

from src.game import baseline as baseline_mod
from src.game import mapping as mapping_mod
from src.game.mapping import MappingError, evaluate
from src.game.schemas import WorldState

CLOSED = WorldState(transit_capacity_pct=20, mine_density=0.5, escalation_rung=6, qatar_damaged_share=0.17,
                    bypass_used_mbd=4.0, stock_release_mbd=2.0, demand_restraint_mbd=0.5,
                    war_risk_premium_pct=5.0, weeks_elapsed=2, expected_remaining_weeks=6).model_dump()


def test_evaluate_arithmetic_and_lookups():
    ctx = {"world": {"x": 20.0, "flag": True}, "baseline": {"a": {"b": 2.0, "lst": [1, 2, 3]}}, "derived": {}}
    assert evaluate("world.x / 2 + baseline.a.b", ctx) == 12.0
    assert evaluate("clamp(world.x, 0, 10)", ctx) == 10
    assert evaluate("baseline.a.lst[2]", ctx) == 3
    assert evaluate("'yes' if world.flag and world.x > 5 else 'no'", ctx) == "yes"
    assert evaluate("[1, 2] if not world.flag else ['cape_of_good_hope']", ctx) == ["cape_of_good_hope"]
    assert evaluate("world.x < 50", ctx) is True


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "world.x.__class__", "lambda: 1",
                                  "(1).__class__", "[x for x in [1]]", "world['x'] + unknown"])
def test_evaluate_refuses_everything_else(expr):
    ctx = {"world": {"x": 1.0}, "baseline": {}, "derived": {}}
    with pytest.raises((MappingError, Exception)):
        evaluate(expr, ctx)


def test_derived_block_and_floors():
    mapping = mapping_mod.load_mapping()
    ctx = mapping_mod.build_context(CLOSED, baseline_mod.baseline_values(), mapping)
    d = ctx["derived"]
    assert d["closure_fraction"] == pytest.approx(0.8)
    assert d["gross_oil_loss_mbd"] == pytest.approx(20.9 * 0.8)
    assert d["net_oil_loss_mbd"] == pytest.approx(20.9 * 0.8 - 6.5)
    assert d["strait_closed"] is True
    assert 0.5 <= d["duration_months"] <= 36
    # a fully supplied closure cannot go negative
    world = dict(CLOSED, bypass_used_mbd=30.0)
    ctx2 = mapping_mod.build_context(world, baseline_mod.baseline_values(), mapping)
    assert ctx2["derived"]["net_oil_loss_mbd"] == 0


def test_every_adapter_block_validates_against_its_adapter():
    from src.models.registry import build_default_registry

    registry = build_default_registry(None)
    mapping = mapping_mod.load_mapping()
    for world in (CLOSED, WorldState().model_dump()):
        ctx = mapping_mod.build_context(world, baseline_mod.baseline_values(), mapping)
        for mid in mapping.models:
            adapter = registry.get(mid)
            assert adapter is not None, mid
            params = mapping_mod.parameters_for(mid, ctx, mapping)
            v = adapter.validate_inputs(params)
            assert v.valid, (mid, v.errors)


def test_baseline_records_carry_sources_and_status():
    rows = baseline_mod.records(baseline_mod.load_baseline())
    assert len(rows) > 60
    statuses = {r["status"] for r in rows}
    assert statuses <= {"primary", "secondary", "designer"}
    assert all(r["source"] for r in rows)
    sources = baseline_mod.load_baseline()["sources"]
    assert all(r["source"] in sources for r in rows)
