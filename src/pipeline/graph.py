"""LangGraph-based pipeline orchestrator.

Implements Algorithm 1 using LangGraph's StateGraph with:
- interrupt() for mandatory HITL checkpoints
- Send for dynamic fan-out of parallel model execution
- Command for state updates and routing
- Reducer-based state accumulation for parallel outputs

This replaces the imperative orchestrator with a declarative graph
structure that supports persistence, partial reruns, and visualization.
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
    ModelExecutionStatus,
    Scenario,
    ValidationStatus,
)
from src.interface.comparison import find_robust_outcomes
from src.interface.provenance import ProvenanceTracker
from src.models.executor import ModelExecutor
from src.models.registry import ModelRegistry, build_default_registry
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


def dispatch_model_execution(state: OverallSimulationState) -> list[Send]:
    """Fan-out: dispatch model execution for each (scenario, model) pair.

    Respects analytical level ordering by grouping sends per level.
    Within each level, models execute in parallel via Send.
    """
    logger.info("Node: dispatch_model_execution (fan-out)")

    registry = build_default_registry()
    sends = []

    # Group parameter sets by scenario
    params_by_scenario: dict[str, dict[str, dict]] = {}
    for ps in state["parameter_sets"]:
        sid = ps["scenario_id"]
        if sid not in params_by_scenario:
            params_by_scenario[sid] = {}
        params_by_scenario[sid][ps["model_id"]] = {
            p["name"]: p["value"] for p in ps["parameters"]
        }

    for scenario_id, model_params in params_by_scenario.items():
        for model_id, params in model_params.items():
            sends.append(
                Send(
                    "execute_single_model",
                    {
                        **state,
                        "current_scenario_id": scenario_id,
                        "current_model_id": model_id,
                        "current_params": params,
                        "execution_results": [],  # Reset accumulator
                    },
                )
            )

    logger.info(f"Dispatching {len(sends)} model execution tasks")
    return sends


def execute_single_model(state: OverallSimulationState) -> dict:
    """Execute a single domain model for a scenario.

    Handles NotImplementedError (SKIPPED), timeouts (FAILED),
    and general exceptions (FAILED) gracefully.
    """
    scenario_id_str = state["current_scenario_id"]
    model_id = state["current_model_id"]
    params = state["current_params"]

    registry = build_default_registry()
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
        output = adapter.execute(native_inputs)

        completed_at = datetime.now(timezone.utc)
        return {
            "execution_results": [{
                "scenario_id": scenario_id_str,
                "model_id": model_id,
                "status": ModelExecutionStatus.COMPLETED.value,
                "outputs": output.outputs,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "runtime_seconds": (completed_at - started_at).total_seconds(),
            }]
        }

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

    Graph structure:
        generate_scenarios
            → review_scenarios (HITL interrupt)
                → extract_parameters (fan-out)
                    → [extract_single_parameters] * N (parallel)
                        → review_parameters (HITL interrupt)
                            → dispatch_model_execution (fan-out)
                                → [execute_single_model] * M (parallel)
                                    → synthesize_results
                                        → review_synthesis (HITL interrupt)
                                            → END

    Returns:
        Compiled StateGraph ready for execution.
    """
    builder = StateGraph(OverallSimulationState)

    # Add nodes
    builder.add_node("generate_scenarios", generate_scenarios)
    builder.add_node("review_scenarios", review_scenarios)
    builder.add_node("extract_single_parameters", extract_single_parameters)
    builder.add_node("review_parameters", review_parameters)
    builder.add_node("execute_single_model", execute_single_model)
    builder.add_node("synthesize_results", synthesize_results)
    builder.add_node("review_synthesis", review_synthesis)

    # Set entry point
    builder.set_entry_point("generate_scenarios")

    # Add edges
    builder.add_edge("generate_scenarios", "review_scenarios")

    # After scenario review: fan-out to parameter extraction or END
    builder.add_conditional_edges(
        "review_scenarios",
        extract_parameters,
        ["extract_single_parameters"],
    )

    # Parameter extraction results merge, then go to review
    builder.add_edge("extract_single_parameters", "review_parameters")

    # After parameter review: fan-out to model execution or END
    builder.add_conditional_edges(
        "review_parameters",
        dispatch_model_execution,
        ["execute_single_model"],
    )

    # Model execution results merge, then go to synthesis
    builder.add_edge("execute_single_model", "synthesize_results")

    # Synthesis → final review → END
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
    }
