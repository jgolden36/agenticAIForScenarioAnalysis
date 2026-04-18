"""Main pipeline orchestrator (Algorithm 1).

Chains Modules 1-5 together, enforcing mandatory analyst checkpoints
and supporting partial reruns.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from src.common.llm import get_llm
from src.common.logging import get_logger
from src.common.types import ModelExecutionStatus, Scenario, ValidationStatus
from src.interface.comparison import find_robust_outcomes
from src.interface.provenance import ProvenanceTracker
from src.interface.review import CLIReviewInterface, ReviewInterface
from src.models.executor import ModelExecutor
from src.models.registry import ModelRegistry, build_default_registry
from src.parameters.extractor import build_parameter_extractor
from src.parameters.model_specs import ALL_MODEL_SPECS
from src.pipeline.config import PipelineConfig
from src.pipeline.state import (
    ModelParameterSet,
    ParameterValue,
    PipelineState,
    ScenarioNarrativeState,
)
from src.scenarios.framework import ScenarioFramework
from src.scenarios.generator import build_scenario_generator
from src.synthesis.consistency import check_consistency
from src.synthesis.synthesizer import build_synthesizer

logger = get_logger(__name__)


class PipelineOrchestrator:
    """Orchestrates the full crisis analysis pipeline.

    Implements Algorithm 1 from the paper with mandatory analyst
    checkpoints after scenario generation, parameter extraction,
    and synthesis.
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        registry: ModelRegistry | None = None,
        review_interface: ReviewInterface | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.registry = registry or build_default_registry()
        self.review = review_interface or CLIReviewInterface()

        self.llm = get_llm(
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature,
            **self.config.llm.extra_kwargs,
        )

        self.scenario_generator = build_scenario_generator(self.llm)
        self.parameter_extractor = build_parameter_extractor(self.llm)
        self.synthesizer = build_synthesizer(self.llm)
        self.executor = ModelExecutor(self.registry, self.config.execution)

    def run(
        self,
        crisis_description: str,
        framework: ScenarioFramework,
        state: PipelineState | None = None,
    ) -> PipelineState:
        """Execute the full pipeline (Algorithm 1).

        Args:
            crisis_description: Structured description of the crisis.
            framework: Schwartz scenario framework specification.
            state: Optional existing state for partial reruns.

        Returns:
            Completed PipelineState with full provenance.
        """
        state = state or PipelineState(
            run_id=str(uuid.uuid4()),
            crisis_description=crisis_description,
        )

        # Step 1: Scenario Generation
        if not state.scenarios_validated:
            self._generate_scenarios(state, crisis_description, framework)

        # Step 2: Analyst Review of Scenarios (MANDATORY CHECKPOINT)
        if not state.scenarios_validated:
            self._review_scenarios(state)

        # Steps 3-12: For each scenario
        if not state.parameters_validated:
            self._extract_all_parameters(state)
            # Step 5: Analyst Review of Parameters (MANDATORY CHECKPOINT)
            self._review_parameters(state)

        # Execute models for all scenarios
        self._execute_all_models(state)

        # Steps 10-12: Consistency checks and synthesis
        self._synthesize_results(state)

        # Step 15: Analyst Review of Synthesis (MANDATORY CHECKPOINT)
        self._review_synthesis(state)

        state.completed_at = datetime.now(timezone.utc)
        return state

    def _generate_scenarios(
        self,
        state: PipelineState,
        crisis_description: str,
        framework: ScenarioFramework,
    ) -> None:
        """Module 1: Generate scenario narratives."""
        logger.info("Module 1: Generating scenario narratives...")

        scenario_set = self.scenario_generator.invoke({
            "crisis_description": crisis_description,
            "framework": framework,
            "num_scenarios": self.config.num_scenarios,
        })

        state.scenario_narratives = [
            ScenarioNarrativeState(
                scenario_id=s.scenario_id,
                label=s.label,
                narrative=s.narrative_timeline,
                quantitative_assumptions={
                    a.variable: a.value
                    for a in s.quantitative_assumptions
                },
                consistency_notes=s.consistency_notes,
            )
            for s in scenario_set.scenarios
        ]

        logger.info(
            f"Generated {len(state.scenario_narratives)} scenario narratives"
        )

    def _review_scenarios(self, state: PipelineState) -> None:
        """Mandatory checkpoint: analyst review of scenarios."""
        content = ""
        for n in state.scenario_narratives:
            content += f"\n### Scenario {n.scenario_id.value}: {n.label}\n"
            content += f"{n.narrative}\n"
            content += f"\nAssumptions: {n.quantitative_assumptions}\n"

        decision = self.review.present_for_review(
            "Scenario Narratives", content
        )

        if decision.status == ValidationStatus.APPROVED:
            state.scenarios_validated = True
            for n in state.scenario_narratives:
                n.validation_status = ValidationStatus.APPROVED
                n.validated_at = datetime.now(timezone.utc)
            logger.info("Scenarios approved by analyst")
        elif decision.status == ValidationStatus.REJECTED:
            logger.warning(f"Scenarios rejected: {decision.comments}")
            state.errors.append(f"Scenarios rejected: {decision.comments}")
        else:
            logger.info(f"Scenarios require modification: {decision.comments}")

    def _extract_all_parameters(self, state: PipelineState) -> None:
        """Module 2: Extract parameters for all (scenario, model) pairs."""
        logger.info("Module 2: Extracting parameters...")

        for narrative in state.scenario_narratives:
            from src.scenarios.schemas import ScenarioNarrative, QuantitativeAssumption

            scenario_obj = ScenarioNarrative(
                scenario_id=narrative.scenario_id,
                label=narrative.label,
                description="",
                narrative_timeline=narrative.narrative,
                quantitative_assumptions=[
                    QuantitativeAssumption(variable=k, value=str(v))
                    for k, v in narrative.quantitative_assumptions.items()
                ],
            )

            for model_id, model_spec in ALL_MODEL_SPECS.items():
                extraction = self.parameter_extractor.invoke({
                    "scenario": scenario_obj,
                    "model_spec": model_spec,
                })

                param_set = ModelParameterSet(
                    scenario_id=narrative.scenario_id,
                    model_id=model_id,
                    parameters=[
                        ParameterValue(
                            name=p.name,
                            value=p.value,
                            unit=p.unit,
                            confidence=p.confidence,
                            extraction_note=p.extraction_note,
                        )
                        for p in extraction.parameters
                    ],
                )
                state.parameter_sets.append(param_set)

        logger.info(f"Extracted {len(state.parameter_sets)} parameter sets")

    def _review_parameters(self, state: PipelineState) -> None:
        """Mandatory checkpoint: analyst review of extracted parameters."""
        content = ""
        for ps in state.parameter_sets:
            content += f"\n### {ps.scenario_id.value} / {ps.model_id}\n"
            for p in ps.parameters:
                content += (
                    f"  - {p.name}: {p.value} {p.unit or ''} "
                    f"[{p.confidence.value}]\n"
                )

        decision = self.review.present_for_review(
            "Extracted Parameters", content
        )

        if decision.status == ValidationStatus.APPROVED:
            state.parameters_validated = True
            now = datetime.now(timezone.utc)
            for ps in state.parameter_sets:
                ps.validation_status = ValidationStatus.APPROVED
                ps.validated_at = now
            logger.info("Parameters approved by analyst")
        elif decision.status == ValidationStatus.REJECTED:
            logger.warning(f"Parameters rejected: {decision.comments}")
            state.errors.append(f"Parameters rejected: {decision.comments}")

    def _execute_all_models(self, state: PipelineState) -> None:
        """Module 3: Execute all models for all scenarios."""
        logger.info("Module 3: Executing domain models...")

        for scenario in Scenario:
            # Build parameter dict for this scenario
            param_dict: dict[str, dict] = {}
            for ps in state.parameter_sets:
                if ps.scenario_id == scenario:
                    param_dict[ps.model_id] = {
                        p.name: p.value for p in ps.parameters
                    }

            if not param_dict:
                continue

            results = asyncio.run(
                self.executor.execute_all(scenario, param_dict)
            )
            state.execution_results.extend(results)

            completed = sum(
                1
                for r in results
                if r.status == ModelExecutionStatus.COMPLETED
            )
            logger.info(
                f"Scenario {scenario.value}: {completed}/{len(results)} "
                f"models completed"
            )

    def _synthesize_results(self, state: PipelineState) -> None:
        """Module 4: Consistency checks and synthesis."""
        logger.info("Module 4: Running consistency checks and synthesis...")

        for scenario in Scenario:
            narrative = state.get_narrative(scenario)
            if not narrative:
                continue

            results = state.get_results_for_scenario(scenario)

            # Consistency checks
            flags = check_consistency(
                scenario, results, self.config.consistency
            )
            state.consistency_flags.extend(flags)

            # Synthesis
            synthesis = self.synthesizer.invoke({
                "narrative": narrative,
                "results": results,
                "consistency_flags": flags,
            })

            # Store synthesis results
            for section in synthesis.sections:
                for outcome in section.outcomes:
                    from src.pipeline.state import SynthesisResult

                    state.synthesis_results.append(
                        SynthesisResult(
                            scenario_id=scenario,
                            time_horizon=section.time_horizon.value,
                            outcome_scope=section.outcome_scope.value,
                            outcome_variable=outcome.variable,
                            value=outcome.value,
                            source_model_id=outcome.source_model_id,
                            narrative_summary=outcome.narrative,
                        )
                    )

    def _review_synthesis(self, state: PipelineState) -> None:
        """Mandatory checkpoint: analyst review of synthesis."""
        # Build summary content
        content = f"Total synthesis results: {len(state.synthesis_results)}\n"
        content += f"Consistency flags: {len(state.consistency_flags)}\n\n"

        for flag in state.consistency_flags:
            content += f"  WARNING: {flag.message}\n"

        # Cross-scenario comparison
        robust, dependent = find_robust_outcomes(state)
        content += f"\nRobust outcomes: {len(robust)}\n"
        for r in robust:
            content += f"  - {r.model_id}/{r.variable}: {r.note}\n"
        content += f"\nScenario-dependent outcomes: {len(dependent)}\n"
        for d in dependent:
            content += f"  - {d.model_id}/{d.variable}: {d.note}\n"

        # Provenance summary
        tracker = ProvenanceTracker(state)
        content += "\n(Full provenance available via ProvenanceTracker)\n"

        decision = self.review.present_for_review("Synthesis Results", content)

        if decision.status == ValidationStatus.APPROVED:
            state.synthesis_validated = True
            logger.info("Synthesis approved by analyst")
        elif decision.status == ValidationStatus.REJECTED:
            logger.warning(f"Synthesis rejected: {decision.comments}")
            state.errors.append(f"Synthesis rejected: {decision.comments}")
