"""Tier 1 adjudication for the agricultural module: fertilizer, yields, forward curves, macro.

``AgriAdjudicator.adjudicate`` takes an :class:`AgriRoundRequest` from the game's ``agri``
ruleset and runs the analytical-MVP adapters directly through the ``ModelAdapter`` contract:

1. ``world_fertilizer``, only when the round carries a Hormuz shock (gas price change or a
   Middle East production loss). Its nitrogen price change replaces the Hormuz part of the
   game's own fertilizer change; the export-ban and control-cell parts stay the game's.
2. Per team, the farm-gate rule and the pipeline's ``price_to_demand_reduction`` bridge
   (elasticity and cap read from ``configs/upstream_forwarding_mapping.yaml``), then APSIM:
   one nitrogen-only run per team and one water-only run per (team, crop) under a drought.
3. ``futures`` once per priced crop and once for urea.
4. The macro kernel per team region, on the world nitrogen change.

Every parameter comes from ``configs/game/agri_state_to_parameters.yaml``. Every number in the
answer names its model, output key and implementation mode. A failed, invalid or timed-out
run becomes a ``Fallback`` and the answer is still complete. No LLM is called anywhere here.

Crop prices are not computed here: the game clears them with its own Tier 0 rule. The Tier 2
path for prices and bilateral trade is MAgPIE, MIRAGRODEP or GTAP (``docs/game/AGRI.md``).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from src.models.base import ModelAdapter, ModelOutput, resolve_implementation_mode
from src.models.macro.macro_kernel import compute_regional_macro_outcomes
from src.models.registry import ModelRegistry, build_default_registry
from src.pipeline.upstream_forwarding import load_mapping as load_forwarding_mapping

from . import baseline as baseline_mod
from . import mapping as mapping_mod
from .agri_schemas import (
    GAME_CROPS,
    AgriRoundRequest,
    AgriRoundResponse,
    FertilizerResult,
    YieldPair,
)
from .schemas import Fallback, MacroRow, ModelProvenance, ModelRun

logger = logging.getLogger(__name__)

AGRI_MODELS: tuple[tuple[str, str], ...] = (
    ("fertilizer", "world_fertilizer"),
    ("yields", "apsim"),
    ("forward", "futures"),
)


def default_agri_baseline_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "game" / "agri_2027_baseline.yaml"


def default_agri_mapping_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "game" / "agri_state_to_parameters.yaml"


def _resolve(rule: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(rule, dict) and set(rule) == {"expr"}:
        return mapping_mod.evaluate(str(rule["expr"]), ctx)
    return rule


def _block(block: dict[str, Any] | None, ctx: dict[str, Any], where: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, rule in (block or {}).items():
        try:
            out[name] = _resolve(rule, ctx)
        except mapping_mod.MappingError as e:
            raise mapping_mod.MappingError(f"{where}.{name}: {e}") from e
    return out


def _num(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    return float(x)


class AgriAdjudicator:
    """Runs the Tier 1 agricultural adapters for a round. Construct once, call many times."""

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
        self.baseline_path = str(baseline_path or default_agri_baseline_path())
        self.baseline = baseline_mod.load_baseline(self.baseline_path)
        self.baseline_values = baseline_mod.collapse(self.baseline)
        self.mapping = mapping_mod.load_mapping(mapping_path or default_agri_mapping_path())
        self.raw = self.mapping.raw
        self.forwarding = load_forwarding_mapping(forwarding_path)
        self.bridge = self._bridge()
        self.per_model_timeout_s = per_model_timeout_s
        self.total_budget_s = total_budget_s
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agri-adjudicator")

    # --- configuration -----------------------------------------------------------------------

    def _designer(self, key: str, default: float) -> float:
        try:
            return float(self.baseline_values["designer_parameters"][key])
        except (KeyError, TypeError, ValueError):
            return default

    def _bridge(self) -> dict[str, Any]:
        """The fertilizer price -> application cut bridge, from the forwarding rule when present."""
        for rule in self.forwarding.by_model.get("apsim", []):
            if rule.target_param != "fertilizer_application_reduction_pct":
                continue
            for src in rule.sources:
                if src.transform == "price_to_demand_reduction" and src.elasticity is not None:
                    return {"elasticity": float(src.elasticity), "cap_pct": float(src.clip_max),
                            "source": "configs/upstream_forwarding_mapping.yaml",
                            "rule": f"apsim.fertilizer_application_reduction_pct <- {src.source_model}.{src.source_field}"}
        return {"elasticity": self._designer("fertilizer_application_elasticity", 0.35),
                "cap_pct": self._designer("application_cut_cap_pct", 95.0),
                "source": "configs/game/agri_2027_baseline.yaml",
                "rule": "designer_parameters.fertilizer_application_elasticity (forwarding rule absent)"}

    def crop_names(self, adapter: str) -> dict[str, str]:
        names = (self.baseline_values.get("crop_names") or {}).get(adapter) or {}
        return {c: str(names.get(c, c)) for c in GAME_CROPS}

    def models(self) -> list[dict[str, Any]]:
        rows = []
        for stage, mid in AGRI_MODELS:
            a = self.registry.get(mid)
            info = a.implementation_info if a is not None else None
            rows.append({"model_id": mid, "stage": stage, "registered": a is not None,
                         "mode_when_executed": getattr(getattr(info, "mode_when_executed", None), "value", "unknown"),
                         "analytical_level": getattr(getattr(a, "analytical_level", None), "value", None)})
        rows.append({"model_id": "macro_kernel", "stage": "macro", "registered": True,
                     "mode_when_executed": "analytical_reduction", "analytical_level": "short_run_macro"})
        return rows

    # --- the round -------------------------------------------------------------------------

    def adjudicate(self, req: AgriRoundRequest) -> AgriRoundResponse:
        t0 = time.perf_counter()
        world = req.world.model_dump()
        ctx = mapping_mod.build_context(world, self.baseline_values, self.mapping)
        derived = ctx["derived"]
        runs: list[ModelRun] = []
        fallbacks: list[Fallback] = []
        provenance: list[ModelProvenance] = []
        overrides: list[dict[str, Any]] = []
        flags: list[dict[str, Any]] = []

        def keep(mid: str, key: str, value: Any, run: ModelRun) -> None:
            if _num(value) is not None:
                provenance.append(ModelProvenance(model_id=mid, output_key=key, value=float(value),
                                                  implementation_mode=run.implementation_mode, runtime_ms=run.runtime_ms))

        # 1. world fertilizer (Hormuz link only)
        fert = FertilizerResult(world_change_pct=float(world["fertilizer_price_change_pct"]))
        wf_out: dict[str, Any] | None = None
        if derived.get("hormuz_active"):
            run, out = self._run(t0, "world_fertilizer", lambda: _block(self.mapping.models.get("world_fertilizer"), ctx,
                                                                    "world_fertilizer"))
            runs.append(run)
            if out is None:
                fallbacks.append(Fallback(model_id="world_fertilizer", reason=run.error or "failed"))
            else:
                wf_out = out
                for key in ("nitrogen_price_pct", "phosphate_price_pct", "potash_price_pct", "fertilizer_price_index_pct"):
                    setattr(fert, key, _num(out.get(key)))
                    keep("world_fertilizer", key, out.get(key), run)
                fert.source_model = "world_fertilizer"
                fert.implementation_mode = run.implementation_mode
        upstream = {"ran_world_fertilizer": wf_out is not None, "world_fertilizer": wf_out or {}}
        try:
            derived.update(_block(self.raw.get("after_fertilizer"), {**ctx, "upstream": upstream}, "after_fertilizer"))
        except mapping_mod.MappingError as e:
            fallbacks.append(Fallback(model_id="world_fertilizer", reason=f"mapping: {e}"))
            derived["n_world_pct"] = float(world["fertilizer_price_change_pct"])
        n_world = float(derived["n_world_pct"])
        fert.world_change_pct = round(n_world, 4)
        if wf_out is not None and _num(wf_out.get("nitrogen_price_pct")) is not None:
            tier1 = float(wf_out["nitrogen_price_pct"])
            tier0 = float(world["hormuz_component_pct"])
            overrides.append({"name": "hormuz_component_pct", "target_key": None, "llm_value": None,
                              "game_value": tier0, "computed_value": round(tier1, 4),
                              "source_model_id": "world_fertilizer", "source_field": "nitrogen_price_pct",
                              "transform": "identity", "deviation_pct": _deviation(tier0, tier1),
                              "note": "Tier 1 nitrogen replaces the game's Tier 0 Hormuz component; "
                                      "the export-ban and control-cell parts stay the game's"})
            dev = _deviation(tier0, tier1)
            warn = self._designer("tier_disagreement_warn_pct", 50.0)
            if dev is not None and dev > warn:
                flags.append({"kind": "tier0_vs_tier1", "field": "hormuz_component_pct", "tier0": tier0,
                              "tier1": round(tier1, 4), "deviation_pct": dev, "threshold_pct": warn,
                              "message": f"world_fertilizer nitrogen {tier1:.1f} pct vs the game's Tier 0 {tier0:.1f} pct"})

        # 2. per team: farm gate, application cut, APSIM
        derived["elasticity"] = self.bridge["elasticity"]
        derived["application_cut_cap_pct"] = self.bridge["cap_pct"]
        apsim_names = self.crop_names("apsim")
        per_team = self.raw.get("per_team") or {}
        farmgate: dict[str, float] = {}
        cuts: dict[str, float] = {}
        yields: dict[str, dict[str, YieldPair]] = {}
        for team_id, spec in req.teams.items():
            team = spec.model_dump()
            tctx = {**ctx, "team": team}
            try:
                for name, rule in (per_team.get("derived") or {}).items():
                    team[name] = _resolve(rule, tctx)
            except mapping_mod.MappingError as e:
                fallbacks.append(Fallback(model_id="apsim", reason=f"{team_id}: mapping: {e}"))
                continue
            farmgate[team_id] = round(float(team["farmgate_change_pct"]), 4)
            cuts[team_id] = round(float(team["application_reduction_pct"]), 4)
            overrides.append({"name": "fertilizer_application_reduction_pct", "target_key": team_id, "llm_value": None,
                              "computed_value": cuts[team_id],
                              "source_model_id": "world_fertilizer" if wf_out is not None else "game",
                              "source_field": "nitrogen_price_pct" if wf_out is not None else "fertilizer_price_change_pct",
                              "transform": "price_to_demand_reduction", "elasticity": self.bridge["elasticity"],
                              "clip_max": self.bridge["cap_pct"], "farmgate_change_pct": farmgate[team_id],
                              "bridge_source": self.bridge["source"], "deviation_pct": None})
            pairs = {c: YieldPair(water_pct=0.0) for c in GAME_CROPS}
            run, out = self._run(t0, "apsim", lambda: _block(per_team.get("apsim_nitrogen"), tctx, "apsim_nitrogen"),
                                 label=f"{team_id}:nitrogen")
            runs.append(run)
            if out is None:
                fallbacks.append(Fallback(model_id="apsim", reason=f"{team_id} nitrogen: {run.error or 'failed'}"))
            else:
                by_crop = out.get("yield_pct_change_by_crop") or {}
                for crop in GAME_CROPS:
                    v = _num(by_crop.get(apsim_names[crop]))
                    pairs[crop].n_pct = round(v, 4) if v is not None else None
                    keep("apsim", f"{team_id}.{crop}.n_pct", v, run)
            for crop, deficit in team.get("water_deficit_pct_by_crop", {}).items():
                cctx = {**tctx, "crop": {"game": crop, "apsim": apsim_names[crop], "deficit_pct": float(deficit)}}
                run, out = self._run(t0, "apsim", lambda: _block(per_team.get("apsim_water"), cctx, "apsim_water"),
                                     label=f"{team_id}:water:{crop}")
                runs.append(run)
                if out is None:
                    pairs[crop].water_pct = None
                    fallbacks.append(Fallback(model_id="apsim", reason=f"{team_id} water {crop}: {run.error or 'failed'}"))
                    continue
                v = _num((out.get("yield_pct_change_by_crop") or {}).get(apsim_names[crop]))
                pairs[crop].water_pct = round(v, 4) if v is not None else None
                keep("apsim", f"{team_id}.{crop}.water_pct", v, run)
            yields[team_id] = pairs

        # 3. forward curves
        curves: dict[str, list[float]] = {}
        ttn: dict[str, int | None] = {}
        fut_cfg = self.raw.get("futures") or {}
        fut_names = self.crop_names("futures")
        jobs: list[tuple[str, str, dict[str, Any], str]] = []
        for crop in GAME_CROPS:
            if crop in world["crop_price_change_pct"]:
                cctx = {**ctx, "crop": {"game": crop, "futures": fut_names[crop],
                                        "price_change_pct": float(world["crop_price_change_pct"][crop])}}
                jobs.append((crop, fut_names[crop], cctx, "per_crop"))
        jobs.append(("urea", "urea", ctx, "urea"))
        for game_name, fut_name, cctx, block in jobs:
            run, out = self._run(t0, "futures", lambda: _block(fut_cfg.get(block), cctx, f"futures.{block}"), label=game_name)
            runs.append(run)
            if out is None:
                fallbacks.append(Fallback(model_id="futures", reason=f"{game_name}: {run.error or 'failed'}"))
                continue
            curve = (out.get("forward_price_curves") or {}).get(fut_name)
            if isinstance(curve, list):
                curves[game_name] = [float(x) for x in curve]
            t = (out.get("time_to_normalization_months_per_commodity") or {}).get(fut_name)
            ttn[game_name] = int(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else None
            peak = (out.get("peak_price_index_per_commodity") or {}).get(fut_name)
            keep("futures", f"{game_name}.peak_price_index", peak, run)
            if ttn[game_name] is not None:
                keep("futures", f"{game_name}.time_to_normalization_months", ttn[game_name], run)

        # 4. macro kernel per team region
        macro, macro_run = self._macro(req, ctx, provenance)
        runs.append(macro_run)

        derived_out = {k: v for k, v in derived.items() if isinstance(v, (int, float, str, bool)) or v is None}
        derived_out["bridge"] = dict(self.bridge)
        return AgriRoundResponse(
            status="ok", game_id=req.game_id, turn=req.turn, as_of=str(self.baseline.get("as_of")),
            baseline_id=str(self.baseline.get("baseline_id", "")), fertilizer=fert,
            farmgate_fertilizer_price_change_pct=farmgate, application_reduction_pct=cuts, yields=yields,
            forward_curves=curves, time_to_normalization_months=ttn, macro_by_team=macro,
            provenance=provenance, runs=runs, overrides=overrides, flags=flags, fallbacks=fallbacks,
            derived=derived_out, elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 2))

    # --- one adapter call -------------------------------------------------------------------

    def _run(self, t0: float, mid: str, params_fn, label: str | None = None) -> tuple[ModelRun, dict[str, Any] | None]:
        """Build the parameters, validate, execute with a timeout. Never raises."""
        if time.perf_counter() - t0 > self.total_budget_s:
            return ModelRun(model_id=mid, label=label, status="skipped", error="round budget exhausted"), None
        adapter = self.registry.get(mid)
        if adapter is None:
            return ModelRun(model_id=mid, label=label, status="skipped", error="not in registry"), None
        try:
            params = params_fn()
        except mapping_mod.MappingError as e:
            return ModelRun(model_id=mid, label=label, status="failed", error=f"mapping: {e}"), None
        t = time.perf_counter()
        try:
            v = adapter.validate_inputs(params)
            if not v.valid:
                return ModelRun(model_id=mid, label=label, status="failed", inputs=params,
                                error="validation: " + "; ".join(v.errors)), None
            fut = self._pool.submit(_execute, adapter, params)
            out: ModelOutput = fut.result(timeout=self.per_model_timeout_s)
        except FutureTimeout:
            return ModelRun(model_id=mid, label=label, status="failed", inputs=params,
                            runtime_ms=round((time.perf_counter() - t) * 1000, 2),
                            error=f"timed out after {self.per_model_timeout_s}s"), None
        except NotImplementedError as e:
            return ModelRun(model_id=mid, label=label, status="skipped", inputs=params, error=f"stub: {e}"), None
        except Exception as e:  # noqa: BLE001  -- isolate every model failure
            return ModelRun(model_id=mid, label=label, status="failed", inputs=params,
                            runtime_ms=round((time.perf_counter() - t) * 1000, 2),
                            error=f"{type(e).__name__}: {e}"), None
        runtime_ms = round((time.perf_counter() - t) * 1000, 2)
        mode = resolve_implementation_mode(out, adapter).value
        return ModelRun(model_id=mid, label=label, status="completed", implementation_mode=mode,
                        runtime_ms=runtime_ms, inputs=params), dict(out.outputs)

    def _macro(self, req: AgriRoundRequest, ctx: dict[str, Any], provenance: list[ModelProvenance]
               ) -> tuple[dict[str, MacroRow], ModelRun]:
        cfg = self.raw.get("macro") or {}
        try:
            shocks = {k: float(v) for k, v in _block(cfg.get("shocks"), ctx, "macro.shocks").items()}
            duration = float(_resolve(cfg.get("duration_months", 6.0), ctx))
        except (mapping_mod.MappingError, TypeError, ValueError) as e:
            return {}, ModelRun(model_id="macro_kernel", status="failed", error=f"mapping: {e}")
        default_regions = baseline_mod.team_regions(self.baseline_path)
        regions = {tid: (spec.region or default_regions.get(tid, "ROW")) for tid, spec in req.teams.items()}
        t = time.perf_counter()
        try:
            rows = compute_regional_macro_outcomes(shocks, duration, regime="short_run")
        except Exception as e:  # noqa: BLE001
            return {}, ModelRun(model_id="macro_kernel", status="failed", inputs=shocks, error=f"{type(e).__name__}: {e}")
        runtime_ms = round((time.perf_counter() - t) * 1000, 2)
        by_region = {r["region"]: r for r in rows}
        out: dict[str, MacroRow] = {}
        for tid, region in regions.items():
            row = by_region.get(region) or by_region.get("ROW")
            if row is None:
                continue
            out[tid] = MacroRow(region=region, gdp_impact_pct=float(row["gdp_impact_pct"]),
                                cpi_inflation_pct=float(row["cpi_inflation_pct"]),
                                consumption_impact_pct=float(row["consumption_impact_pct"]))
            for key in ("gdp_impact_pct", "cpi_inflation_pct", "consumption_impact_pct"):
                provenance.append(ModelProvenance(model_id="macro_kernel", output_key=f"{tid}.{key}", value=float(row[key]),
                                                  implementation_mode="analytical_reduction", runtime_ms=runtime_ms))
        return out, ModelRun(model_id="macro_kernel", status="completed", implementation_mode="analytical_reduction",
                             runtime_ms=runtime_ms, inputs={"commodity_shocks": shocks, "duration_months": duration})


def _deviation(a: float, b: float) -> float | None:
    """Symmetric percent deviation, as the pipeline's override records use it."""
    denom = (abs(a) + abs(b)) / 2.0
    if denom < 1e-9:
        return None
    return round(100.0 * abs(a - b) / denom, 2)


def _execute(adapter: ModelAdapter, params: dict[str, Any]) -> ModelOutput:
    return adapter.execute(adapter.translate_inputs(params))
