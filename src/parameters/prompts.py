"""Prompt templates for parameter extraction (Module 2)."""

from langchain_core.prompts import ChatPromptTemplate

PARAMETER_EXTRACTION_SYSTEM = """You are a quantitative analyst extracting structured parameters from scenario \
narratives. Your task is to parse a scenario narrative and extract the specific quantitative values needed by a \
domain model.

Rules:
1. Extract values directly stated when available; otherwise infer a best-effort estimate from the narrative \
context, the scenario's quantitative assumptions, and standard reference values for the domain.
2. For each parameter, indicate whether it was directly stated (`directly_stated=true`) or inferred \
(`directly_stated=false`).
3. Assign a confidence level: `high` (directly stated), `medium` (strongly implied), `low` (required substantial \
inference or domain-knowledge defaults).
4. NEVER return `null` for a required parameter. Required numeric parameters MUST be non-null numbers. If you \
cannot extract a value, supply your best domain-knowledge default and mark `confidence='low'` with \
`directly_stated=false`. Returning `null` causes the entire model run to fail downstream.
5. Honor the `expected_type` annotation for each parameter:
   - `number` / `non_negative_number` / `positive_number` / `percent` — return a numeric (int or float).
     - `non_negative_number` must be >= 0.
     - `positive_number` must be strictly > 0.
     - `percent` must be in the range [0, 100] (e.g., write 25 for "25%", not 0.25).
   - `boolean` — return `true` or `false`.
   - `string` — return a free-text or categorical string.
   - `list` — return a JSON list.
   - `dict` — return a JSON object.
6. Honor any extra annotations rendered in square brackets after the type:
   - `value_range: [lo, hi]` — your numeric value MUST satisfy lo <= value <= hi (clip your \
estimate to the range rather than reporting an outlier).
   - `valid_values: [...]` — your value MUST be drawn from this exact set; for `list` types every \
list element must be one of the listed identifiers (use the EXACT spelling — snake_case, no spaces).
   - `value_schema: ...` — describes the inner shape of a `dict` or `list` value. For \
`dict[str, number]`, emit a flat object whose values are bare numbers — DO NOT wrap each value in \
a nested object with `shock` / `unit` keys.
7. Optional parameters that are not addressed by the narrative may be omitted entirely (do not include them \
with `null` values).
8. Use the `warnings` field to flag any required parameters where you had to fall back to a domain default.
9. Output your response as valid JSON matching the provided schema."""

PARAMETER_EXTRACTION_HUMAN = """Extract quantitative parameters from the following scenario narrative for the \
specified domain model.

## Scenario Narrative
Scenario ID: {scenario_id}
Label: {scenario_label}

{scenario_narrative}

## Quantitative Assumptions from Scenario
{quantitative_assumptions}

## Target Model
Model ID: {model_id}
Description: {model_description}

## Required Parameters (every entry below MUST be returned with a non-null value of the indicated expected_type)
{required_parameters}

## Optional Parameters (omit entirely if the narrative does not support them)
{optional_parameters}

{correction_hint}

Extract each required parameter from the scenario narrative. For any required parameter where the narrative is \
silent, supply a best-effort domain-knowledge default with `confidence='low'` and add a note in `warnings`. \
Do NOT emit `null` for required parameters."""

PARAMETER_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", PARAMETER_EXTRACTION_SYSTEM),
        ("human", PARAMETER_EXTRACTION_HUMAN),
    ]
)
