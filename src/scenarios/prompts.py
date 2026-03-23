"""Prompt templates for scenario generation (Module 1)."""

from langchain_core.prompts import ChatPromptTemplate

SCENARIO_GENERATION_SYSTEM = """You are a geopolitical and economic scenario analyst. Your task is to generate \
detailed, internally consistent scenario narratives within a structured scenario framework.

Each scenario must:
1. Be structurally distinct from other scenarios — they are NOT perturbations around a baseline.
2. Include a detailed narrative timeline with specific dates or date ranges.
3. Explicitly state all quantitative assumptions as structured key-value pairs.
4. Include internal consistency verification notes.
5. Be machine-parseable for subsequent parameter extraction.

Output your response as valid JSON matching the provided schema."""

SCENARIO_GENERATION_HUMAN = """Generate {num_scenarios} scenario narratives for the following crisis and framework.

## Crisis Description
{crisis_description}

## Scenario Framework

### Focal Issue
{focal_issue}

### Predetermined Elements (appear in ALL scenarios)
{predetermined_elements}

### Critical Uncertainties (scenario matrix axes)
X-axis: {uncertainty_x_name}
  - Low pole: {uncertainty_x_low}
  - High pole: {uncertainty_x_high}
Y-axis: {uncertainty_y_name}
  - Low pole: {uncertainty_y_low}
  - High pole: {uncertainty_y_high}

### Driving Forces
{driving_forces}

### Key Factors
{key_factors}

## Required Scenarios
{quadrant_descriptions}

For each scenario, provide:
- scenario_id: The scenario letter (A, B, C, or D)
- label: A descriptive short name
- description: A 1-2 sentence summary
- narrative_timeline: A detailed multi-paragraph narrative with specific timeline
- quantitative_assumptions: A list of {{variable, value, unit, rationale}} objects
- consistency_notes: Notes on internal consistency of the scenario"""

SCENARIO_GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SCENARIO_GENERATION_SYSTEM),
        ("human", SCENARIO_GENERATION_HUMAN),
    ]
)
