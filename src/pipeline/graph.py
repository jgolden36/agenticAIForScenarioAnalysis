"""LangGraph-based pipeline orchestrator.

Implements Algorithm 1 using LangGraph's StateGraph with:
- interrupt() for mandatory HITL checkpoints
- Send for dynamic fan-out of parallel model execution
- Command for state updates and routing
- Reducer-based state accumulation for parallel outputs

This replaces the imperative orchestrator with a declarative graph
structure that supports persistence, partial reruns, and visualization.

NOTE: The interrupt() nodes (review_scenarios, review_parameters,
review_synthesis) require a long-lived process to be resumed via
Command(resume=...). They are therefore for LOCAL / DEVELOPMENT runs
only -- on the SLURM cluster the pipeline is split across separate
short-lived jobs (slurm/scripts/run_*.py) that auto-approve the
checkpoints. See slurm/submit_pipeline.sh for the cluster entry point.
"""

from __future__ import annotations

import asyncio
import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.types import Send
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from src.common.llm import get_llm
from src.common.logging import get_logger
from src.common.types import (
    ANALYTICAL_LEVEL_ORDER,
    AnalyticalLevel,
    ModelExecutionStatus,
    Scenario,
    ValidationStatus,
)
from src.interface.comparison import find_robust_outcomes
from src.interface.provenance import ProvenanceTracker
from src.models.executor import ModelExecutor
from src.models.uncertainty import maybe_run_with_uncertainty
from src.models.registry import (
    ModelRegistry,
    build_default_registry,
    default_config_dir,
)
from src.parameters.extractor import build_parameter_extractor
from src.parameters.model_specs import ALL_MODEL_SPECS
from src.pipeline.config import PipelineConfig
from src.pipeline.state import (
    ConsistencyFlag,
    ModelExecutionResult,
    ModelParameterSet,
    ParameterValue,
    PipelineState,
    ScenarioNarrativeState,
    SynthesisResult,
)
from src.pipeline.upstream_forwarding import (
    compute_downstream_inputs,
    load_mapping,
    merge_into_params,
    register_overrides_in_outputs,
)
from src.scenarios.framework import ScenarioFramework
from src.scenarios.generator import build_scenario_generator
from src.scenarios.schemas import QuantitativeAssumption, ScenarioNarrative
from src.synthesis.consistency import check_consistency
from src.synthesis.synthesizer import build_synthesizer

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LangGraph state schema (TypedDict with reducers)
# ---------------------------------------------------------------------------

class OverallSimulationState(TypedDict):
    """Top-level pipeline state for the LangGraph orchestrator.

    Uses TypedDict (recommended over Pydantic for LangGraph internal state)
    with reducer annotations for parallel output accumulation.

    Scalar fields use last-write-wins. List fields use operator.add
    to accumulate results from parallel fan-out executions.
    """

    # Immutable context (set once at graph start)
    run_id: str
    crisis_description: str
    framework: dict  # Serialized ScenarioFramework
    config: dict  # Serialized PipelineConfig

    # Module 1: Scenario narratives
    scenario_narratives: list[dict]
    scenarios_validated: bool

    # Module 2: Extracted parameters (accumulates via fan-out)
    parameter_sets: Annotated[list[dict], operator.add]
    parameters_validated: bool

    # Module 3: Model execution results (accumulates via fan-out)
    execution_results: Annotated[list[dict], operator.add]

    # Module 4: Consistency and synthesis
    consistency_flags: Annotated[list[dict], operator.add]
    synthesis_results: Annotated[list[dict], operator.add]
    synthesis_validated: bool

    # Error tracking (accumulates)
    errors: Annotated[list[str], operator.add]

    # Metadata
    completed_at: str | None

    # Transient per-node data (for fan-out workers)
    current_scenario_id: str | None
    current_model_id: str | None
    current_params: dict | None
    # Upstream-to-macro override records attached by the merge barrier
    # node and consumed by execute_macro_model so they survive into
    # ModelExecutionResult.outputs["_upstream_overrides"].
    current_upstream_overrides: list[dict] | None


# ---------------------------------------------------------------------------
# Graph node functions
# ---------------------------------------------------------------------------


def generate_scenarios(state: OverallSimulationState) -> dict:
    """Module 1: Generate scenario narratives via LLM."""
    logger.info("Node: generate_scenarios")

    config = PipelineConfig(**state["config"])
    llm = get_llm(
        provider=config.llm.provider,
        model=config.llm.model,
        temperature=config.llm.temperature,
        **config.llm.extra_kwargs,
    )

    generator = build_scenario_generator(llm)
    framework = ScenarioFramework(**state["framework"])

    scenario_set = generator.invoke({
        "crisis_description": state["crisis_description"],
        "framework": framework,
        "num_scenarios": config.num_scenarios,
    })

    narratives = [
        {
            "scenario_id": s.scenario_id.value,
            "label": s.label,
            "narrative": s.narrative_timeline,
            "quantitative_assumptions": {a.variable: a.value for a in s.quantitative_assumptions},
            "consistency_notes": s.consistency_notes,
            "validation_status": ValidationStatus.PENDING.value,
        }
        for s in scenario_set.scenarios
    ]

    logger.info(f"Generated {len(narratives)} scenario narratives")
    return {"scenario_narratives": narratives}


def review_scenarios(state: OverallSimulationState) -> dict:
    """HITL Checkpoint 1: Analyst review of scenario narratives.

    Uses interrupt() to pause execution and surface scenarios for review.
    Resume with Command(resume={"status": "approved"/"rejected", "comments": "..."}).
    """
    logger.info("Node: review_scenarios (HITL checkpoint)")

    narratives = state["scenario_narratives"]

    # Build review payload
    review_content = []
    for n in narratives:
        review_content.append({
            "scenario_id": n["scenario_id"],
            "label": n["label"],
            "narrative": n["narrative"],
            "assumptions": n["quantitative_assumptions"],
        })

    # Pause for analyst review
    decision = interrupt({
        "checkpoint": "scenario_review",
        "title": "Scenario Narratives",
        "content": review_content,
        "instruction": "Review the generated scenarios. Resume with {status: approved/rejected, comments: ...}",
    })

    if decision.get("status") == "approved":
        now = datetime.now(timezone.utc).isoformat()
        updated = []
        for n in narratives:
            n_copy = dict(n)
            n_copy["validation_status"] = ValidationStatus.APPROVED.value
            n_copy["validated_at"] = now
            updated.append(n_copy)
        logger.info("Scenarios approved by analyst")
        return {"scenario_narratives": updated, "scenarios_validated": True}
    else:
        comments = decision.get("comments", "No reason given")
        logger.warning(f"Scenarios rejected: {comments}")
        return {
            "scenarios_validated": False,
            "errors": [f"Scenarios rejected: {comments}"],
        }


def extract_parameters(state: OverallSimulationState) -> list[Send]:
    """Fan-out: dispatch parameter extraction for each (scenario, model) pair.

    Returns a list of Send objects, each launching an independent
    extract_single_parameters node.
    """
    logger.info("Node: extract_parameters (fan-out)")

    narratives = state["scenario_narratives"]
    sends = []

    for narrative in narratives:
        for model_id in ALL_MODEL_SPECS:
            sends.append(
                Send(
                    "extract_single_parameters",
                    {
                        **state,
                        "current_scenario_id": narrative["scenario_id"],
                        "current_model_id": model_id,
                        "parameter_sets": [],  # Reset accumulator for this branch
                    },
                )
            )

    logger.info(f"Dispatching {len(sends)} parameter extraction tasks")
    return sends


def extract_single_parameters(state: OverallSimulationState) -> dict:
    """Extract parameters for a single (scenario, model) pair."""
    scenario_id_str = state["current_scenario_id"]
    model_id = state["current_model_id"]

    config = PipelineConfig(**state["config"])
    llm = get_llm(
        provider=config.llm.provider,
        model=config.llm.model,
        temperature=config.llm.temperature,
        **config.llm.extra_kwargs,
    )

    extractor = build_parameter_extractor(llm)

    # Find the narrative for this scenario
    narrative_data = None
    for n in state["scenario_narratives"]:
        if n["scenario_id"] == scenario_id_str:
            narrative_data = n
            break

    if narrative_data is None:
        return {"errors": [f"No narrative found for scenario {scenario_id_str}"]}

    scenario_id = Scenario(scenario_id_str)
    model_spec = ALL_MODEL_SPECS[model_id]

    scenario_obj = ScenarioNarrative(
        scenario_id=scenario_id,
        label=narrative_data["label"],
        description="",
        narrative_timeline=narrative_data["narrative"],
        quantitative_assumptions=[
            QuantitativeAssumption(variable=k, value=str(v))
            for k, v in narrative_data["quantitative_assumptions"].items()
        ],
    )

    extraction = extractor.invoke({
        "scenario": scenario_obj,
        "model_spec": model_spec,
    })

    param_set = {
        "scenario_id": scenario_id_str,
        "model_id": model_id,
        "parameters": [
            {
                "name": p.name,
                "value": p.value,
                "unit": p.unit,
                "confidence": p.confidence.value if hasattr(p.confidence, "value") else p.confidence,
                "extraction_note": p.extraction_note,
            }
            for p in extraction.parameters
        ],
        "validation_status": ValidationStatus.PENDING.value,
    }

    return {"parameter_sets": [param_set]}


def review_parameters(state: OverallSimulationState) -> dict:
    """HITL Checkpoint 2: Analyst review of extracted parameters.

    Uses interrupt() to pause for analyst validation.
    """
    logger.info("Node: review_parameters (HITL checkpoint)")

    review_content = []
    for ps in state["parameter_sets"]:
        params_summary = [
            {
                "name": p["name"],
                "value": p["value"],
                "unit": p.get("unit"),
                "confidence": p["confidence"],
            }
            for p in ps["parameters"]
        ]
        review_content.append({
            "scenario_id": ps["scenario_id"],
            "model_id": ps["model_id"],
            "parameters": params_summary,
        })

    decision = interrupt({
        "checkpoint": "parameter_review",
        "title": "Extracted Parameters",
        "content": review_content,
        "instruction": "Review extracted parameters. Resume with {status: approved/rejected, comments: ...}",
    })

    if decision.get("status") == "approved":
        now = datetime.now(timezone.utc).isoformat()
        updated = []
        for ps in state["parameter_sets"]:
            ps_copy = dict(ps)
            ps_copy["validation_status"] = ValidationStatus.APPROVED.value
            ps_copy["validated_at"] = now
            updated.append(ps_copy)
        logger.info("Parameters approved by analyst")
        # We need to replace, not append, so return as a full state update
        # Since parameter_sets uses operator.add, we handle this at graph level
        return {"parameters_validated": True}
    else:
        comments = decision.get("comments", "No reason given")
        logger.warning(f"Parameters rejected: {comments}")
        return {
            "parameters_validated": False,
            "errors": [f"Parameters rejected: {comments}"],
        }


_COMMODITY_LEVELS = (
    AnalyticalLevel.COMBAT,
    AnalyticalLevel.COMMODITY,
)
_COMMODITY_DOWNSTREAM_LEVELS = (
    AnalyticalLevel.COMMODITY_DOWNSTREAM,
)
_MACRO_LEVELS = (
    AnalyticalLevel.SHORT_RUN_MACRO,
    AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC,
)


def _params_dict_for_model(
    parameter_sets: list[dict], scenario_id: str, model_id: str
) -> dict[str, Any] | None:
    """Return the LATEST parameters dict for a (scenario, model) pair.

    Because ``parameter_sets`` uses ``operator.add`` reduction, the
    upstream-to-macro merge barrier may add a *second* entry for the
    same (scenario, model) pair carrying the post-merge parameters.
    The dispatcher must pick the most recent one so the macro model
    receives the upstream-derived shocks.
    """
    latest: dict | None = None
    for ps in parameter_sets:
        if ps["scenario_id"] == scenario_id and ps["model_id"] == model_id:
            latest = ps
    if latest is None:
        return None
    return {p["name"]: p["value"] for p in latest["parameters"]}


def _overrides_for_model(
    parameter_sets: list[dict], scenario_id: str, model_id: str
) -> list[dict]:
    """Return the upstream-override records the merge node attached, if any."""
    latest: dict | None = None
    for ps in parameter_sets:
        if (
            ps["scenario_id"] == scenario_id
            and ps["model_id"] == model_id
            and ps.get("_upstream_overrides")
        ):
            latest = ps
    return list(latest.get("_upstream_overrides") or []) if latest else []


def _dispatch_models_at_levels(
    state: OverallSimulationState,
    levels: tuple[AnalyticalLevel, ...],
    target_node: str,
) -> list[Send]:
    """Shared fan-out helper used by the commodity and macro dispatchers."""
    registry = build_default_registry(default_config_dir())
    sends: list[Send] = []

    seen_pairs: set[tuple[str, str]] = set()

    scenario_ids: list[str] = []
    seen_scenarios: set[str] = set()
    for ps in state["parameter_sets"]:
        sid = ps["scenario_id"]
        if sid not in seen_scenarios:
            seen_scenarios.add(sid)
            scenario_ids.append(sid)

    for level in levels:
        level_adapters = registry.get_by_analytical_level(level)
        level_model_ids = {a.model_id for a in level_adapters}
        for scenario_id in scenario_ids:
            for model_id in level_model_ids:
                pair = (scenario_id, model_id)
                if pair in seen_pairs:
                    continue
                params = _params_dict_for_model(
                    state["parameter_sets"], scenario_id, model_id
                )
                if params is None:
                    continue
                seen_pairs.add(pair)
                overrides = _overrides_for_model(
                    state["parameter_sets"], scenario_id, model_id
                )
                sends.append(
                    Send(
                        target_node,
                        {
                            **state,
                            "current_scenario_id": scenario_id,
                            "current_model_id": model_id,
                            "current_params": params,
                            "current_upstream_overrides": overrides,
                            "execution_results": [],
                        },
                    )
                )
    return sends


def dispatch_commodity_models(state: OverallSimulationState) -> list[Send]:
    """Fan-out: dispatch combat + commodity tier models for every scenario."""
    logger.info("Node: dispatch_commodity_models (fan-out)")
    sends = _dispatch_models_at_levels(
        state, _COMMODITY_LEVELS, "execute_commodity_model"
    )
    logger.info(f"Dispatching {len(sends)} commodity-tier model tasks")
    return sends


def _merge_upstream_into_downstream(
    state: OverallSimulationState,
    target_levels: tuple[AnalyticalLevel, ...],
    barrier_label: str,
) -> dict:
    """Shared barrier-node body for both upstream-to-downstream merges.

    Reads the now-completed upstream ``execution_results`` and, for each
    downstream model registered at one of ``target_levels`` AND declared
    in ``configs/upstream_forwarding_mapping.yaml``, replaces the
    LLM-extracted shock parameters with values computed from upstream
    model outputs. Override records (LLM value, upstream value,
    deviation) are attached to the new parameter_set so the downstream
    executor can persist them into the model's outputs.

    Returns a delta ``parameter_sets`` list (LangGraph appends it to
    the existing ones via the ``operator.add`` reducer); downstream
    dispatchers use the LATEST entry per (scenario, model).
    """
    logger.info(f"Node: {barrier_label} (barrier)")
    mapping = load_mapping()
    if not mapping.by_model:
        logger.info(f"[{barrier_label}] no mapping rules; skipping merge")
        return {}

    # Restrict the merge to downstream models that live at one of the
    # current barrier's target levels. This is what makes the same
    # function reusable for the COMMODITY -> COMMODITY_DOWNSTREAM and
    # COMMODITY+COMMODITY_DOWNSTREAM -> MACRO transitions.
    registry = build_default_registry(default_config_dir())
    target_model_ids: set[str] = set()
    for level in target_levels:
        for adapter in registry.get_by_analytical_level(level):
            target_model_ids.add(adapter.model_id)

    scenario_ids: list[str] = []
    seen: set[str] = set()
    for ps in state["parameter_sets"]:
        sid = ps["scenario_id"]
        if sid not in seen:
            seen.add(sid)
            scenario_ids.append(sid)

    new_param_sets: list[dict] = []
    for scenario_id in scenario_ids:
        upstream_results = [
            r for r in state["execution_results"]
            if r.get("scenario_id") == scenario_id
        ]
        per_downstream = compute_downstream_inputs(
            scenario_id,
            upstream_results,
            mapping,
            target_models=target_model_ids,
        )
        if not per_downstream:
            continue
        for downstream_model_id, computed in per_downstream.items():
            llm_params = _params_dict_for_model(
                state["parameter_sets"], scenario_id, downstream_model_id
            )
            if llm_params is None:
                logger.info(
                    "[%s] No LLM params for downstream model %s/%s; skipping merge",
                    barrier_label,
                    scenario_id,
                    downstream_model_id,
                )
                continue
            merged, records = merge_into_params(
                downstream_model_id, llm_params, computed
            )
            if not records:
                continue
            new_param_sets.append({
                "scenario_id": scenario_id,
                "model_id": downstream_model_id,
                "parameters": [
                    {"name": k, "value": v} for k, v in merged.items()
                ],
                "validation_status": ValidationStatus.APPROVED.value,
                "_upstream_overrides": [r.to_dict() for r in records],
                "_override_phase": True,
            })

    if not new_param_sets:
        logger.info(
            f"[{barrier_label}] no overrides produced "
            "(no upstream outputs matched any rule)"
        )
        return {}

    logger.info(
        "[%s] merged upstream outputs into %d downstream parameter sets",
        barrier_label,
        len(new_param_sets),
    )
    return {"parameter_sets": new_param_sets}


def merge_upstream_into_commodity_downstream_params(
    state: OverallSimulationState,
) -> dict:
    """Barrier 1: commodity outputs -> commodity_downstream inputs.

    Today this fires for the helium -> SimRLFab / Argonne ABM
    transition: ``world_helium_model.effective_supply_gap_pct`` flows
    into ``simrlfab.helium_supply_reduction_pct`` and
    ``argonne_abm.supply_shock_pct``. See
    ``configs/upstream_forwarding_mapping.yaml`` for the full rule set.
    """
    return _merge_upstream_into_downstream(
        state,
        _COMMODITY_DOWNSTREAM_LEVELS,
        "merge_upstream_into_commodity_downstream_params",
    )


def merge_upstream_into_macro_params(state: OverallSimulationState) -> dict:
    """Barrier 2: commodity (+ commodity_downstream) outputs -> macro inputs.

    The execution_results accumulated by the time this barrier runs
    cover both prior phases, so macro-tier rules (e.g.
    ``opencge.commodity_price_shocks.helium`` <-
    ``world_helium_model.price_change_pct``) keep working unchanged.
    """
    return _merge_upstream_into_downstream(
        state,
        _MACRO_LEVELS,
        "merge_upstream_into_macro_params",
    )


def dispatch_commodity_downstream_models(
    state: OverallSimulationState,
) -> list[Send]:
    """Fan-out: dispatch the commodity_downstream tier (SimRLFab, Argonne ABM)."""
    logger.info("Node: dispatch_commodity_downstream_models (fan-out)")
    sends = _dispatch_models_at_levels(
        state, _COMMODITY_DOWNSTREAM_LEVELS, "execute_commodity_downstream_model"
    )
    logger.info(f"Dispatching {len(sends)} commodity-downstream model tasks")
    return sends


def dispatch_macro_models(state: OverallSimulationState) -> list[Send]:
    """Fan-out: dispatch short-run + long-run macro tier models."""
    logger.info("Node: dispatch_macro_models (fan-out)")
    sends = _dispatch_models_at_levels(
        state, _MACRO_LEVELS, "execute_macro_model"
    )
    logger.info(f"Dispatching {len(sends)} macro-tier model tasks")
    return sends


def _execute_one_model_node(state: OverallSimulationState) -> dict:
    """Execute a single domain model for a scenario.

    Handles NotImplementedError (SKIPPED), timeouts (FAILED), and
    general exceptions (FAILED) gracefully. Sets environment
    variables for GPU device and thread control based on the
    adapter's resource requirements. Attaches any upstream-override
    records carried in ``state["current_upstream_overrides"]`` to the
    output dict so they survive into Module 4 synthesis.
    """
    import os

    scenario_id_str = state["current_scenario_id"]
    model_id = state["current_model_id"]
    params = state["current_params"]
    overrides = state.get("current_upstream_overrides") or []

    registry = build_default_registry(default_config_dir())
    adapter = registry.get(model_id)

    if adapter is None:
        return {
            "execution_results": [{
                "scenario_id": scenario_id_str,
                "model_id": model_id,
                "status": ModelExecutionStatus.FAILED.value,
                "error_message": f"Model {model_id} not found in registry",
            }]
        }

    reqs = adapter.resource_requirements
    config = PipelineConfig(**state["config"])

    threads = config.execution.cpu_threads_per_model
    if reqs.supports_multi_threading:
        threads = max(threads, reqs.max_threads)
    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ["MKL_NUM_THREADS"] = str(threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(threads)

    started_at = datetime.now(timezone.utc)

    try:
        validation = adapter.validate_inputs(params)
        if not validation.valid:
            return {
                "execution_results": [{
                    "scenario_id": scenario_id_str,
                    "model_id": model_id,
                    "status": ModelExecutionStatus.FAILED.value,
                    "error_message": f"Validation failed: {'; '.join(validation.errors)}",
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }]
            }

        native_inputs = adapter.translate_inputs(params)
        output = maybe_run_with_uncertainty(
            adapter, native_inputs, config.execution.uncertainty
        )

        completed_at = datetime.now(timezone.utc)
        outputs_dict = register_overrides_in_outputs(output.outputs, overrides)
        result_entry: dict[str, Any] = {
            "scenario_id": scenario_id_str,
            "model_id": model_id,
            "status": ModelExecutionStatus.COMPLETED.value,
            "outputs": outputs_dict,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "runtime_seconds": (completed_at - started_at).total_seconds(),
            "requires_gpu": reqs.requires_gpu,
            "gpu_device": output.gpu_device,
            "worker_id": output.worker_id,
        }
        if output.uncertainty is not None:
            result_entry["uncertainty"] = output.uncertainty.model_dump()
        return {"execution_results": [result_entry]}

    except NotImplementedError as e:
        return {
            "execution_results": [{
                "scenario_id": scenario_id_str,
                "model_id": model_id,
                "status": ModelExecutionStatus.SKIPPED.value,
                "error_message": f"Not yet implemented: {e}",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }]
        }

    except Exception as e:
        return {
            "execution_results": [{
                "scenario_id": scenario_id_str,
                "model_id": model_id,
                "status": ModelExecutionStatus.FAILED.value,
                "error_message": f"{type(e).__name__}: {e}",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }]
        }


def execute_commodity_model(state: OverallSimulationState) -> dict:
    """Execute one combat- or commodity-tier model for one scenario."""
    return _execute_one_model_node(state)


def execute_commodity_downstream_model(state: OverallSimulationState) -> dict:
    """Execute one commodity-downstream-tier model for one scenario.

    Same body as :func:`execute_commodity_model`; named separately so
    LangGraph can attach a distinct conditional edge (and so the
    upstream-merged parameters land here, not on the upstream
    commodity executor).
    """
    return _execute_one_model_node(state)


def execute_macro_model(state: OverallSimulationState) -> dict:
    """Execute one macro-tier model for one scenario.

    Differs from :func:`execute_commodity_model` only in that the
    parameters arriving here may have been replaced by the
    ``merge_upstream_into_macro_params`` barrier with upstream-derived
    shocks; the override records ride along in the state so they end
    up on the result's ``outputs["_upstream_overrides"]``.
    """
    return _execute_one_model_node(state)


# Kept as an alias so older callers / imports keep working.
execute_single_model = execute_commodity_model


def synthesize_results(state: OverallSimulationState) -> dict:
    """Module 4: Run consistency checks and synthesize results."""
    logger.info("Node: synthesize_results")

    config = PipelineConfig(**state["config"])
    llm = get_llm(
        provider=config.llm.provider,
        model=config.llm.model,
        temperature=config.llm.temperature,
        **config.llm.extra_kwargs,
    )
    synthesizer = build_synthesizer(llm)

    all_flags = []
    all_synthesis = []

    for scenario in Scenario:
        scenario_results = [
            ModelExecutionResult(**r)
            for r in state["execution_results"]
            if r["scenario_id"] == scenario.value
        ]

        if not scenario_results:
            continue

        # Find narrative
        narrative_data = None
        for n in state["scenario_narratives"]:
            if n["scenario_id"] == scenario.value:
                narrative_data = n
                break

        if narrative_data is None:
            continue

        narrative_state = ScenarioNarrativeState(
            scenario_id=scenario,
            label=narrative_data["label"],
            narrative=narrative_data["narrative"],
            quantitative_assumptions=narrative_data["quantitative_assumptions"],
            consistency_notes=narrative_data.get("consistency_notes", ""),
        )

        # Consistency checks
        flags = check_consistency(scenario, scenario_results, config.consistency)
        all_flags.extend([f.model_dump() for f in flags])

        # Synthesis via LLM
        synthesis = synthesizer.invoke({
            "narrative": narrative_state,
            "results": scenario_results,
            "consistency_flags": flags,
        })

        for section in synthesis.sections:
            for outcome in section.outcomes:
                all_synthesis.append({
                    "scenario_id": scenario.value,
                    "time_horizon": section.time_horizon.value,
                    "outcome_scope": section.outcome_scope.value,
                    "outcome_variable": outcome.variable,
                    "value": outcome.value,
                    "source_model_id": outcome.source_model_id,
                    "narrative_summary": outcome.narrative,
                })

    return {
        "consistency_flags": all_flags,
        "synthesis_results": all_synthesis,
    }


def review_synthesis(state: OverallSimulationState) -> dict:
    """HITL Checkpoint 3: Analyst review of synthesis results.

    Uses interrupt() to pause for final analyst validation.
    """
    logger.info("Node: review_synthesis (HITL checkpoint)")

    # Build provenance-aware review payload
    review_content = {
        "total_synthesis_results": len(state["synthesis_results"]),
        "consistency_flags": state["consistency_flags"],
        "synthesis_summary": state["synthesis_results"][:20],  # First 20 for review
    }

    decision = interrupt({
        "checkpoint": "synthesis_review",
        "title": "Synthesis Results",
        "content": review_content,
        "instruction": "Review synthesis with consistency flags. Resume with {status: approved/rejected, comments: ...}",
    })

    if decision.get("status") == "approved":
        logger.info("Synthesis approved by analyst")
        return {
            "synthesis_validated": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        comments = decision.get("comments", "No reason given")
        logger.warning(f"Synthesis rejected: {comments}")
        return {
            "synthesis_validated": False,
            "errors": [f"Synthesis rejected: {comments}"],
        }


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def route_after_scenario_review(state: OverallSimulationState) -> str:
    """Route based on scenario review outcome."""
    if state.get("scenarios_validated"):
        return "extract_parameters"
    return END


def route_after_parameter_review(state: OverallSimulationState) -> str:
    """Route based on parameter review outcome."""
    if state.get("parameters_validated"):
        return "dispatch_model_execution"
    return END


def route_after_synthesis_review(state: OverallSimulationState) -> str:
    """Route based on synthesis review outcome."""
    return END


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_pipeline_graph() -> StateGraph:
    """Build the LangGraph StateGraph for the full crisis analysis pipeline.

    Graph structure (Algorithm 1, with the two upstream-to-downstream
    feed-forward barriers from step 11):

        generate_scenarios
            → review_scenarios (HITL interrupt)
                → extract_parameters (fan-out)
                    → [extract_single_parameters] * N (parallel)
                        → review_parameters (HITL interrupt)
                            → dispatch_commodity_models (fan-out)
                                → [execute_commodity_model] * M_c (parallel)
                                    → merge_upstream_into_commodity_downstream_params
                                        → dispatch_commodity_downstream_models (fan-out)
                                            → [execute_commodity_downstream_model] * M_cd
                                                → merge_upstream_into_macro_params
                                                    → dispatch_macro_models (fan-out)
                                                        → [execute_macro_model] * M_m
                                                            → synthesize_results
                                                                → review_synthesis (HITL)
                                                                    → END

    Returns:
        Compiled StateGraph ready for execution.
    """
    builder = StateGraph(OverallSimulationState)

    builder.add_node("generate_scenarios", generate_scenarios)
    builder.add_node("review_scenarios", review_scenarios)
    builder.add_node("extract_single_parameters", extract_single_parameters)
    builder.add_node("review_parameters", review_parameters)
    builder.add_node("execute_commodity_model", execute_commodity_model)
    builder.add_node(
        "merge_upstream_into_commodity_downstream_params",
        merge_upstream_into_commodity_downstream_params,
    )
    builder.add_node(
        "execute_commodity_downstream_model", execute_commodity_downstream_model
    )
    builder.add_node(
        "merge_upstream_into_macro_params", merge_upstream_into_macro_params
    )
    builder.add_node("execute_macro_model", execute_macro_model)
    builder.add_node("synthesize_results", synthesize_results)
    builder.add_node("review_synthesis", review_synthesis)

    builder.set_entry_point("generate_scenarios")

    builder.add_edge("generate_scenarios", "review_scenarios")

    builder.add_conditional_edges(
        "review_scenarios",
        extract_parameters,
        ["extract_single_parameters"],
    )

    builder.add_edge("extract_single_parameters", "review_parameters")

    # After parameter review: fan out the COMMODITY tier first.
    builder.add_conditional_edges(
        "review_parameters",
        dispatch_commodity_models,
        ["execute_commodity_model"],
    )

    # All commodity-tier results converge at barrier #1, which rewrites
    # the COMMODITY_DOWNSTREAM parameter sets with upstream-derived
    # shocks (today: helium -> SimRLFab / Argonne ABM).
    builder.add_edge(
        "execute_commodity_model",
        "merge_upstream_into_commodity_downstream_params",
    )

    # Fan out the COMMODITY_DOWNSTREAM tier with the merged params.
    builder.add_conditional_edges(
        "merge_upstream_into_commodity_downstream_params",
        dispatch_commodity_downstream_models,
        ["execute_commodity_downstream_model"],
    )

    # All commodity_downstream results converge at barrier #2, which
    # rewrites the MACRO parameter sets with upstream-derived shocks
    # drawn from BOTH commodity and commodity_downstream outputs.
    builder.add_edge(
        "execute_commodity_downstream_model",
        "merge_upstream_into_macro_params",
    )

    # Then fan out the MACRO tier with the merged params.
    builder.add_conditional_edges(
        "merge_upstream_into_macro_params",
        dispatch_macro_models,
        ["execute_macro_model"],
    )

    builder.add_edge("execute_macro_model", "synthesize_results")

    builder.add_edge("synthesize_results", "review_synthesis")
    builder.add_edge("review_synthesis", END)

    return builder


def create_initial_state(
    crisis_description: str,
    framework: ScenarioFramework,
    config: PipelineConfig | None = None,
) -> OverallSimulationState:
    """Create the initial state for a pipeline run.

    Args:
        crisis_description: Structured description of the crisis.
        framework: Schwartz scenario framework specification.
        config: Pipeline configuration (uses defaults if None).

    Returns:
        Initial OverallSimulationState ready for graph execution.
    """
    config = config or PipelineConfig()

    return {
        "run_id": str(uuid.uuid4()),
        "crisis_description": crisis_description,
        "framework": framework.model_dump(),
        "config": config.model_dump(),
        "scenario_narratives": [],
        "scenarios_validated": False,
        "parameter_sets": [],
        "parameters_validated": False,
        "execution_results": [],
        "consistency_flags": [],
        "synthesis_results": [],
        "synthesis_validated": False,
        "errors": [],
        "completed_at": None,
        "current_scenario_id": None,
        "current_model_id": None,
        "current_params": None,
        "current_upstream_overrides": None,
    }
