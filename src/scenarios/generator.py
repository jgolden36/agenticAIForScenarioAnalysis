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
    num_scenarios: int = inputs.get("num_scenarios", 4)

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
    quadrant_descriptions = "\n".join(
        f"- Scenario {q['label']}: {q['x']} + {q['y']}" for q in quadrants
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
