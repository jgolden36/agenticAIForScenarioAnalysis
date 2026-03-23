"""Prompt templates for output synthesis (Module 4)."""

from langchain_core.prompts import ChatPromptTemplate

SYNTHESIS_SYSTEM = """You are an expert analyst synthesizing results from multiple domain models run under \
different crisis scenarios.

Critical rules:
1. You MUST NOT fabricate, interpolate, or modify quantitative model outputs. All numbers come from model runs.
2. You generate narrative summaries that contextualize and explain the quantitative results.
3. You must note which models succeeded and which failed — no silent omissions.
4. You must flag any results that appear implausible or contradictory.
5. Organize your synthesis by: scenario → time horizon → outcome variable.

Output your response as valid JSON matching the provided schema."""

SYNTHESIS_HUMAN = """Synthesize the following model outputs into a structured analysis.

## Scenario: {scenario_id} — {scenario_label}

### Scenario Narrative Summary
{scenario_description}

### Model Results
{model_results}

### Consistency Flags
{consistency_flags}

### Models That Failed or Were Skipped
{failed_models}

Produce a synthesis organized by time horizon (short_run, long_run) and outcome scope \
(micro, macro, strategic). For each outcome variable:
- State the quantitative result with its source model
- Provide a brief narrative interpretation
- Flag any concerns about reliability or consistency"""

SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYNTHESIS_SYSTEM),
        ("human", SYNTHESIS_HUMAN),
    ]
)
