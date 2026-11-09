"""Tier 1 adjudication: run the analytical-MVP adapters for one crisis round.

``Adjudicator.adjudicate`` takes a :class:`RoundRequest`, maps the world state onto adapter
parameters (``configs/game/game_state_to_parameters.yaml``), and runs three stages:

1. shipping (``aisdb``, ``ais_project``),
2. commodity (``poles_jrc``, ``lngst``, ``world_helium_model``, ``world_fertilizer``, ``futures``),
3. downstream (``marketsim``, ``fed_oil``) and the macro kernel per team region.

Between stages it applies the pipeline's own forwarding rules (``src/pipeline/upstream_forwarding``),
so POLES-JRC sees the mean of the two shipping models' rerouting multipliers and the fertilizer
model sees LNGST's gas impulse, exactly as Algorithm 1 step 11 would, but across models that share
an analytical level and so never meet in ``ModelExecutor``. Every replaced value is kept as an
override record; cross-source disagreement is flagged with the pipeline's consistency check.

The adjudicator never raises for a model failure. A failed, timed-out or invalid run becomes a
``Fallback`` entry and the response is still complete; the game then keeps its last multiplier
for that commodity and shows a badge. No LLM is called anywhere in this module.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from src.common.types import ModelExecutionStatus, Scenario
from src.models.base import ModelAdapter, ModelOutput, resolve_implementation_mode
from src.models.macro.macro_kernel import compute_regional_macro_outcomes
from src.models.registry import ModelRegistry, build_default_registry
from src.pipeline.state import ModelExecutionResult
from src.pipeline.upstream_forwarding import (
    ParamMapping,
    UpstreamMapping,
    _parse_mapping_dict,
    compute_downstream_inputs,
    load_mapping as load_forwarding_mapping,
    merge_into_params,
    register_overrides_in_outputs,
)
from src.synthesis.consistency import check_cross_source_disagreement

from . import baseline as baseline_mod
from . import mapping as mapping_mod
from .schemas import (
    Fallback,
    LaneState,
    MacroRow,
    ModelProvenance,
    ModelRun,
    RoundRequest,
    RoundResponse,
)

logger = logging.getLogger(__name__)

STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("shipping", ("aisdb", "ais_project")),
    ("commodity", ("poles_jrc", "lngst", "world_helium_model", "world_fertilizer", "futures")),
    ("downstream", ("marketsim", "fed_oil")),
)

MACRO_SHOCK_SOURCES = {
    "oil": ("poles_jrc", "peak_price_change_pct"),
    "lng": ("lngst", "implied_price_impulse_pct"),
    "fertilizer": ("world_fertilizer", "fertilizer_price_index_pct"),
    "helium": ("world_helium_model", "price_change_pct"),
}


class Adjudicator:
    """Runs the Tier 1 adapters for a round. Construct once, call many times."""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        *,
        baseline_path: Path | str | None = None,
        mapping_path: Path | str | None = None,
        forwarding_path: Path | str | None = None,
        per_model_timeout_s: float = 5.0,
        total_budget_s: float = 30.0,
    ) -> None:
        self.registry = registry if registry is not None else build_default_registry(None)
        self.baseline_path = baseline_path
        self.baseline = baseline_mod.load_baseline(baseline_path)
        self.baseline_values = baseline_mod.collapse(self.baseline)
        self.mapping = mapping_mod.load_mapping(mapping_path)
        self.forwarding = self._merged_forwarding(forwarding_path)
        self.per_model_timeout_s = per_model_timeout_s
        self.total_budget_s = total_budget_s
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="adjudicator")

    # --- configuration -----------------------------------------------------------------------

    def _merged_forwarding(self, forwarding_path: Path | str | None) -> UpstreamMapping:
        """The pipeline forwarding mapping plus the game's ``forwarding_extra`` rules.

        An extra rule replaces any pipeline rule with the same target so the game file states
        every substitution the adjudicator can make.
        """
        base = load_forwarding_mapping(forwarding_path)
        extra = _parse_mapping_dict({"models": self.mapping.forwarding_extra})
        disabled = set()
        for item in self.mapping.forwarding_disable:
            mid, _, param = str(item).partition(".")
            disabled.add((mid, param))
        by_model: dict[str, list[ParamMapping]] = {
            k: [r for r in v if (k, r.target_param) not in disabled] for k, v in base.by_model.items()
        }
        for mid, rules in extra.by_model.items():
            keep = [r for r in by_model.get(mid, [])
                    if (r.target_param, r.target_key) not in {(x.target_param, x.target_key) for x in rules}]
            by_model[mid] = keep + list(rules)
        return UpstreamMapping(by_model=by_model, warn_threshold_pct=base.warn_threshold_pct,
                               cross_source_warn_threshold_pct=base.cross_source_warn_threshold_pct)

    def models(self) -> list[dict[str, Any]]:
        """Which adapters the adjudicator uses and the mode each runs in with no config."""
        rows = []
        for _stage, mids in STAGES:
            for mid in mids:
                a = self.registry.get(mid)
                info = a.implementation_info if a is not None else None
                rows.append({
                    "model_id": mid,
                    "stage": _stage,
                    "registered": a is not None,
                    "mode_when_executed": getattr(getattr(info, "mode_when_executed", None), "value", "unknown"),
                    "analytical_level": getattr(getattr(a, "analytical_level", None), "value", None),
                })
        rows.append({"model_id": "macro_kernel", "stage": "macro", "registered": True,
                     "mode_when_executed": "analytical_reduction", "analytical_level": "short_run_macro"})
        return rows

    # --- the round -------------------------------------------------------------------------

    def scenario_label(self, world: dict[str, Any], derived: dict[str, Any]) -> str:
        rule = self.baseline_values.get("scenario_label_rule") or {}
        if world.get("qatar_damaged_share", 0.0) >= float(rule.get("infrastructure_collapse_if_damaged_share_at_least", 0.3)):
            return Scenario.E.value
        escalated = int(world.get("escalation_rung", 0)) >= int(rule.get("escalated_if_rung_at_least", 5))
        swift = float(derived.get("total_weeks", 8)) <= float(rule.get("swift_if_expected_total_weeks_at_most", 6))
        if swift and not escalated:
            return Scenario.A.value
        if not swift and not escalated:
            return Scenario.B.value
        if swift and escalated:
            return Scenario.C.value
        return Scenario.D.value

    def adjudicate(self, req: RoundRequest) -> RoundResponse:
        t0 = time.perf_counter()
        world = req.world.model_dump()
        ctx = mapping_mod.build_context(world, self.baseline_values, self.mapping)
        derived = ctx["derived"]
        label = self.scenario_label(world, derived)

        results: list[ModelExecutionResult] = []
        outputs: dict[str, dict[str, Any]] = {}
        runs: list[ModelRun] = []
        fallbacks: list[Fallback] = []
        provenance: list[ModelProvenance] = []
        overrides: list[dict[str, Any]] = []

        for _stage, model_ids in STAGES:
            for mid in model_ids:
                if time.perf_counter() - t0 > self.total_budget_s:
                    fallbacks.append(Fallback(model_id=mid, reason="round budget exhausted"))
                    runs.append(ModelRun(model_id=mid, status="skipped", error="round budget exhausted"))
                    continue
                # Forwarding is resolved per model, from every completed run so far, so a model
                # can consume another's output even when both sit in the same stage (LNGST feeds
                # the fertilizer model; the fertilizer model feeds the futures curves).
                shocks = compute_downstream_inputs(label, results, self.forwarding, target_models=[mid])
                run, result = self._run_one(mid, ctx, shocks.get(mid, []), label)
                runs.append(run)
                if result is None:
                    fallbacks.append(Fallback(model_id=mid, reason=run.error or "failed"))
                    continue
                results.append(result)
                outputs[mid] = result.outputs
                overrides.extend(result.outputs.get("_upstream_overrides") or [])
                for key, value in result.outputs.items():
                    if key.startswith("_") or not isinstance(value, (int, float)) or isinstance(value, bool):
                        continue
                    provenance.append(ModelProvenance(model_id=mid, output_key=key, value=value,
                                                      implementation_mode=run.implementation_mode,
                                                      runtime_ms=run.runtime_ms))

        multipliers, peaks, shocks_out = self._multipliers(outputs, world, fallbacks)
        lane = self._lane(outputs)
        macro, macro_run = self._macro(outputs, derived, req, provenance)
        runs.append(macro_run)

        flags: list[dict[str, Any]] = []
        try:
            for f in check_cross_source_disagreement(Scenario(label), results,
                                                     threshold_pct=self.forwarding.cross_source_warn_threshold_pct):
                flags.append(f.model_dump(mode="json"))
        except Exception as e:  # noqa: BLE001  -- a flag failure must not fail the round
            logger.warning("cross-source check failed: %s", e)

        return RoundResponse(
            status="ok",
            game_id=req.game_id,
            turn=req.turn,
            scenario_label=label,
            as_of=str(self.baseline.get("as_of")),
            multipliers=multipliers,
            peak_multipliers=peaks,
            lane=lane,
            shocks=shocks_out,
            macro_by_team=macro,
            provenance=provenance,
            runs=runs,
            overrides=overrides,
            flags=flags,
            fallbacks=fallbacks,
            derived={k: v for k, v in derived.items()},
            elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )

    # --- one adapter ----------------------------------------------------------------------

    def _run_one(self, mid: str, ctx: dict[str, Any], shocks: list, label: str
                 ) -> tuple[ModelRun, ModelExecutionResult | None]:
        adapter = self.registry.get(mid)
        if adapter is None:
            return ModelRun(model_id=mid, status="skipped", error="not in registry"), None
        try:
            params = mapping_mod.parameters_for(mid, ctx, self.mapping)
        except mapping_mod.MappingError as e:
            return ModelRun(model_id=mid, status="failed", error=f"mapping: {e}"), None
        params, records = merge_into_params(mid, params, shocks)

        t = time.perf_counter()
        try:
            v = adapter.validate_inputs(params)
            if not v.valid:
                return ModelRun(model_id=mid, status="failed", inputs=params,
                                error="validation: " + "; ".join(v.errors)), None
            fut = self._pool.submit(_execute, adapter, params)
            out: ModelOutput = fut.result(timeout=self.per_model_timeout_s)
        except FutureTimeout:
            return ModelRun(model_id=mid, status="failed", inputs=params,
                            runtime_ms=round((time.perf_counter() - t) * 1000, 2),
                            error=f"timed out after {self.per_model_timeout_s}s"), None
        except NotImplementedError as e:
            return ModelRun(model_id=mid, status="skipped", inputs=params, error=f"stub: {e}"), None
        except Exception as e:  # noqa: BLE001  -- isolate every model failure
            return ModelRun(model_id=mid, status="failed", inputs=params,
                            runtime_ms=round((time.perf_counter() - t) * 1000, 2),
                            error=f"{type(e).__name__}: {e}"), None
        runtime_ms = round((time.perf_counter() - t) * 1000, 2)
        mode = resolve_implementation_mode(out, adapter).value
        outputs = register_overrides_in_outputs(dict(out.outputs), records)
        result = ModelExecutionResult(scenario_id=Scenario(label), model_id=mid,
                                      status=ModelExecutionStatus.COMPLETED, outputs=outputs,
                                      runtime_seconds=runtime_ms / 1000.0, implementation_mode=mode)
        return ModelRun(model_id=mid, status="completed", implementation_mode=mode,
                        runtime_ms=runtime_ms, inputs=params), result

    # --- turning outputs into game numbers ----------------------------------------------------

    def _designer(self, key: str, default: float) -> float:
        try:
            return float(self.baseline_values["designer_parameters"][key])
        except (KeyError, TypeError, ValueError):
            return default

    def _ramp(self, weeks_elapsed: int, ramp_weeks: float) -> float:
        return min(1.0, (int(weeks_elapsed) + 1) / max(1.0, ramp_weeks))

    def _multipliers(self, outputs: dict[str, dict[str, Any]], world: dict[str, Any],
                     fallbacks: list[Fallback]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        multipliers: dict[str, float] = {}
        peaks: dict[str, float] = {}
        for good, spec in self.mapping.outputs.items():
            mid, key = spec["source_model"], spec["source_field"]
            value = (outputs.get(mid) or {}).get(key)
            if not isinstance(value, (int, float)):
                if mid in outputs:
                    fallbacks.append(Fallback(model_id=mid, reason=f"{key} missing for {good}"))
                continue
            scale = self._designer(spec["scale_key"], 1.0) if spec.get("scale_key") else 1.0
            peak = 1.0 + scale * float(value) / 100.0
            ramp = self._ramp(world.get("weeks_elapsed", 0), self._designer(spec.get("ramp_weeks_key", ""), 4.0))
            peaks[good] = round(peak, 4)
            multipliers[good] = round(1.0 + (peak - 1.0) * ramp, 4)
        shocks: dict[str, float] = {}
        for name, (mid, key) in MACRO_SHOCK_SOURCES.items():
            value = (outputs.get(mid) or {}).get(key)
            if isinstance(value, (int, float)):
                shocks[f"{name}_price_shock_pct"] = round(float(value), 3)
        gap = (outputs.get("world_helium_model") or {}).get("effective_supply_gap_pct")
        if isinstance(gap, (int, float)):
            shocks["helium_effective_supply_gap_pct"] = round(float(gap), 3)
        return multipliers, peaks, shocks

    def _lane(self, outputs: dict[str, dict[str, Any]]) -> LaneState:
        lane = LaneState()
        rc = [o.get("rerouting_cost_multiplier") for o in (outputs.get("aisdb"), outputs.get("ais_project")) if o]
        rc = [float(x) for x in rc if isinstance(x, (int, float))]
        if rc:
            lane.rerouting_cost_multiplier = round(sum(rc) / len(rc), 4)
        fl = [o.get("effective_fleet_capacity_loss_pct") for o in (outputs.get("aisdb"), outputs.get("ais_project")) if o]
        fl = [float(x) for x in fl if isinstance(x, (int, float))]
        if fl:
            lane.effective_fleet_capacity_loss_pct = round(sum(fl) / len(fl), 3)
        prem = (outputs.get("aisdb") or {}).get("war_risk_insurance_premium_pct")
        if isinstance(prem, (int, float)):
            lane.war_risk_insurance_premium_pct = float(prem)
        return lane

    def _macro(self, outputs: dict[str, dict[str, Any]], derived: dict[str, Any], req: RoundRequest,
               provenance: list[ModelProvenance]) -> tuple[dict[str, MacroRow], ModelRun]:
        shocks: dict[str, float] = {}
        for name, (mid, key) in MACRO_SHOCK_SOURCES.items():
            value = (outputs.get(mid) or {}).get(key)
            if isinstance(value, (int, float)):
                shocks[name] = float(value)
        ramp = self._ramp(req.world.weeks_elapsed, self._designer("price_ramp_weeks_energy", 4.0))
        shocks = {k: v * ramp for k, v in shocks.items()}
        regions = {seat: spec.region for seat, spec in req.teams.items()} or baseline_mod.team_regions(self.baseline_path)
        t = time.perf_counter()
        try:
            rows = compute_regional_macro_outcomes(shocks, float(derived.get("duration_months", 2.0)),
                                                  regime="short_run")
        except Exception as e:  # noqa: BLE001
            return {}, ModelRun(model_id="macro_kernel", status="failed", inputs=shocks,
                                error=f"{type(e).__name__}: {e}")
        runtime_ms = round((time.perf_counter() - t) * 1000, 2)
        by_region = {r["region"]: r for r in rows}
        out: dict[str, MacroRow] = {}
        for seat, region in regions.items():
            row = by_region.get(region) or by_region.get("ROW")
            if row is None:
                continue
            out[seat] = MacroRow(region=region, gdp_impact_pct=float(row["gdp_impact_pct"]),
                                 cpi_inflation_pct=float(row["cpi_inflation_pct"]),
                                 consumption_impact_pct=float(row["consumption_impact_pct"]))
            for key in ("gdp_impact_pct", "cpi_inflation_pct", "consumption_impact_pct"):
                provenance.append(ModelProvenance(model_id="macro_kernel", output_key=f"{region}.{key}",
                                                  value=float(row[key]), implementation_mode="analytical_reduction",
                                                  runtime_ms=runtime_ms))
        return out, ModelRun(model_id="macro_kernel", status="completed", implementation_mode="analytical_reduction",
                             runtime_ms=runtime_ms, inputs={"commodity_shocks": shocks,
                                                            "duration_months": derived.get("duration_months")})


def _execute(adapter: ModelAdapter, params: dict[str, Any]) -> ModelOutput:
    return adapter.execute(adapter.translate_inputs(params))
