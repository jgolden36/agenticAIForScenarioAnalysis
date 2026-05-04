"""LLM-based scenario narrative generation (Module 1).

Takes a crisis description and scenario framework, produces N scenario
narratives using structured output parsing.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnablePassthrough

from src.common.logging import get_logger
from src.scenarios.framework import ScenarioFramework
from src.scenarios.prompts import SCENARIO_GENERATION_PROMPT
from src.scenarios.schemas import ScenarioSet

logger = get_logger(__name__)


def _format_framework_inputs(inputs: dict) -> dict:
    """Format framework data structures into prompt template variables."""
    framework: ScenarioFramework = inputs["framework"]
    crisis_description: str = inputs["crisis_description"]
    # If the caller didn't pin num_scenarios, derive it from the framework
    # so adding entries to ``additional_scenarios`` is a one-file change.
    num_scenarios: int = inputs.get("num_scenarios") or framework.total_scenarios

    predetermined = "\n".join(
        f"- {pe.name}: {pe.description}" for pe in framework.predetermined_elements
    )
    driving_forces = "\n".join(
        f"- [{df.dimension.upper()}] {df.name}: {df.description}"
        for df in framework.driving_forces
    )
    key_factors = "\n".join(
        f"- {kf.name}: {kf.description}" for kf in framework.key_factors
    )
    quadrants = framework.scenario_matrix.quadrants
    quadrant_lines = [
        f"- Scenario {q['label']} (scenario_id derived from matrix): "
        f"{q['x']} + {q['y']}"
        for q in quadrants
    ]
    additional_lines: list[str] = []
    for ps in framework.additional_scenarios:
        seed_block = ""
        if ps.narrative_seeds:
            seed_bullets = "\n    * ".join(ps.narrative_seeds)
            seed_block = f"\n    Required facts to incorporate verbatim:\n    * {seed_bullets}"
        summary = ps.summary or "(no summary provided)"
        additional_lines.append(
            f"- Prescribed scenario (scenario_id={ps.scenario_id!r}, "
            f"label={ps.label!r}): {summary}{seed_block}"
        )

    quadrant_descriptions = "\n".join(quadrant_lines)
    additional_scenarios_block = (
        "\n".join(additional_lines)
        if additional_lines
        else "None — generate only the 2x2 matrix quadrants."
    )

    mx = framework.scenario_matrix

    return {
        "num_scenarios": num_scenarios,
        "crisis_description": crisis_description,
        "focal_issue": framework.focal_issue.description,
        "predetermined_elements": predetermined or "None specified",
        "uncertainty_x_name": mx.uncertainty_x.name,
        "uncertainty_x_low": mx.uncertainty_x.pole_low,
        "uncertainty_x_high": mx.uncertainty_x.pole_high,
        "uncertainty_y_name": mx.uncertainty_y.name,
        "uncertainty_y_low": mx.uncertainty_y.pole_low,
        "uncertainty_y_high": mx.uncertainty_y.pole_high,
        "driving_forces": driving_forces or "None specified",
        "key_factors": key_factors or "None specified",
        "quadrant_descriptions": quadrant_descriptions,
        "additional_scenarios": additional_scenarios_block,
    }


def build_scenario_generator(llm: BaseChatModel) -> Runnable:
    """Build the scenario generation chain.

    Args:
        llm: Configured LangChain LLM instance.

    Returns:
        A Runnable that takes {crisis_description, framework, num_scenarios}
        and returns a ScenarioSet.
    """
    structured_llm = llm.with_structured_output(ScenarioSet)

    chain = (
        RunnablePassthrough.assign(**{})
        | _format_framework_inputs
        | SCENARIO_GENERATION_PROMPT
        | structured_llm
    )

    return chain
