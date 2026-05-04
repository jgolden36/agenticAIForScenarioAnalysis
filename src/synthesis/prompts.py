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

### Upstream-to-Macro Overrides
The following macro-model inputs were REPLACED with values computed by upstream \
commodity-tier models (see `configs/upstream_to_macro_mapping.yaml`). When the LLM-extracted \
value and the upstream value disagree materially, mention this in the relevant macro \
outcome's narrative so the analyst can audit the substitution.

{upstream_overrides}

### Regional / country-level model outputs (pre-aggregated)
The tables below are computed from completed model outputs and rolled up to the unified \
region taxonomy `{{US, CHN, IND, EU, MENA_GCC, MENA_OTHER, SSA, LAC, ROW, GLOBAL}}` via \
`configs/region_crosswalk.yaml`. Treat these as the authoritative regional numbers.

{regional_breakdowns}

### Sectoral model outputs
{sectoral_breakdowns}

### Consistency Flags
{consistency_flags}

### Models That Failed or Were Skipped
{failed_models}

Produce a synthesis organized by time horizon (short_run, long_run) and outcome scope \
(micro, macro, strategic). For each outcome variable:
- State the quantitative result with its source model.
- Provide a brief narrative interpretation.
- Flag any concerns about reliability or consistency.
- When the source model produced regional or sectoral data above, write a 1-2 sentence \
`distribution_note` in plain prose calling out the most- and least-affected regions or \
sectors. **Never invent regional or sectoral numbers that are not in the tables above.** \
Leave the `regional_distribution` and `sectoral_distribution` fields empty in your JSON \
response — they will be populated automatically from the upstream model outputs."""

SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYNTHESIS_SYSTEM),
        ("human", SYNTHESIS_HUMAN),
    ]
)


# ====================================================================
# Section-scoped synthesis prompt (used by chunked synthesis)
# ====================================================================
#
# The chunked Module 4 synthesizer makes one LLM call per
# (scenario, time_horizon, outcome_scope) section instead of one
# monolithic call per scenario. Each call only carries the model
# outputs that route to that section (see src/synthesis/sectioning.py),
# which keeps every prompt safely under the served context window.
#
# The system prompt below differs from the full one by:
#   * naming the specific section the LLM is responsible for
#   * forbidding the LLM from emitting outcomes for *other* sections
#     (the run_synthesis driver merges per-section ScopedSynthesis
#     objects into a single ScenarioSynthesis afterwards)
#   * keeping the same anti-fabrication and anti-distribution-invention
#     guard rails as the full prompt.

SECTION_SYNTHESIS_SYSTEM = """You are an expert analyst synthesizing one section of a multi-scenario \
crisis-modelling report. The orchestrator has pre-bucketed the model outputs that are \
relevant to your section; outputs for other sections will be synthesized in separate calls.

Critical rules:
1. You MUST NOT fabricate, interpolate, or modify quantitative model outputs.
2. You MUST restrict your synthesis to the assigned section: \
time_horizon = {section_time_horizon}, outcome_scope = {section_outcome_scope}. \
Do not emit outcomes that belong to a different time_horizon or outcome_scope.
3. You generate narrative summaries that contextualize and explain the quantitative results.
4. You must note which models in this section succeeded and which failed — no silent omissions.
5. You must flag any results that appear implausible or contradictory.
6. Leave the `regional_distribution` and `sectoral_distribution` fields empty in your JSON — \
they are populated automatically from upstream model outputs after your call returns.

Output your response as valid JSON matching the provided schema."""


SECTION_SYNTHESIS_HUMAN = """Synthesize the model outputs below into a structured analysis for ONE section only.

## Scenario: {scenario_id} — {scenario_label}
## Section: time_horizon={section_time_horizon}, outcome_scope={section_outcome_scope}

### Scenario Narrative Summary
{scenario_description}

### Model Results (only models routed to this section)
{model_results}

### Upstream-to-Macro Overrides (for models in this section)
The following macro-model inputs were REPLACED with values computed by upstream commodity-tier \
models. When the LLM-extracted value and the upstream value disagree materially, mention this in \
the relevant outcome's narrative.

{upstream_overrides}

### Regional / country-level model outputs (pre-aggregated, models in this section)
{regional_breakdowns}

### Sectoral model outputs (models in this section)
{sectoral_breakdowns}

### Consistency Flags (relevant to this section)
{consistency_flags}

### Models in this section that failed or were skipped
{failed_models}

Produce a `ScopedSynthesis` whose `time_horizon` is `{section_time_horizon}` and whose \
`outcome_scope` is `{section_outcome_scope}`. For each outcome variable in this section:
- State the quantitative result with its source model.
- Provide a brief narrative interpretation.
- Flag any concerns about reliability or consistency.
- When the source model produced regional or sectoral data above, write a 1-2 sentence \
`distribution_note` in plain prose calling out the most- and least-affected regions or sectors. \
**Never invent regional or sectoral numbers that are not in the tables above.** Leave the \
`regional_distribution` and `sectoral_distribution` fields empty in your JSON — they will be \
populated automatically from the upstream model outputs."""


SECTION_SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SECTION_SYNTHESIS_SYSTEM),
        ("human", SECTION_SYNTHESIS_HUMAN),
    ]
)


# ====================================================================
# Uncertainty-interpretation prompt (one extra LLM call per scenario
# when uncertainty quantification is enabled).
# ====================================================================
#
# This call is *qualitative only*. The numeric quantiles are computed
# by src/models/uncertainty.py from the perturbation replicates (or
# from the adapter's native UQ) and are pre-attached to each
# SynthesizedOutcome.uncertainty before the LLM is asked anything.
# The LLM's job is to read the band widths and tell the analyst what
# they mean for confidence in the scenario's findings — never to
# generate, modify, or paraphrase the numbers themselves.

UNCERTAINTY_INTERPRETATION_SYSTEM = """You are a quantitative-decision analyst interpreting the uncertainty \
profile of a multi-model crisis scenario. Your inputs are pre-computed model output bands \
(p05, p25, p50, p75, p95) — these came from the underlying domain models, not from you.

Critical rules:
1. You MUST NOT invent, paraphrase, or restate any numeric value that is not already present \
in the band table below. Refer to outputs by name (e.g. "GDP impact (pycge)") instead.
2. You write a qualitative reading: which findings are tight enough to act on, which are \
loose enough that the central estimate should be treated as illustrative, and what that \
means for the analyst's decision posture.
3. Distinguish between "models agree on a central value with narrow bands" (high confidence), \
"models agree on direction but have wide bands" (medium confidence), and "p05-p95 spans a \
decision-relevant threshold" (low confidence — the central estimate is one draw among many).
4. Note when uncertainty is concentrated in one tier (e.g. macro CGE GDP wide; commodity \
prices tight) — that has different implications than uniformly wide bands.

Output your response as valid JSON matching the UncertaintyInterpretation schema."""

UNCERTAINTY_INTERPRETATION_HUMAN = """Interpret the uncertainty profile of this scenario.

## Scenario: {scenario_id} — {scenario_label}

### Scenario Narrative
{scenario_description}

### Uncertainty quantification method
Method: {uncertainty_method}
Replicates per model (when applicable): {n_replicates}
Note: bands below are pre-computed from those replicates (or from the adapter's native \
UQ where available). You must NOT modify or restate any numeric value below.

### Per-outcome uncertainty bands
Each row shows mean, std, and the p05-p95 spread for one (model, output) pair.
Bands are formatted as `mean ± std  [p05 – p95]`.

{uncertainty_table}

### Outcomes with no uncertainty data
{models_without_uq}

Produce an `UncertaintyInterpretation` with:
- a 2-4 sentence `summary` of the overall confidence picture
- `high_confidence_findings`: outcomes whose bands are tight enough to plan against (cite \
the variable + source model exactly as listed in the table)
- `low_confidence_findings`: outcomes whose bands span a decision-relevant threshold
- `decision_implications`: how the analyst should weight this scenario's findings given \
the uncertainty profile.

Never introduce numbers that are not in the table above."""

UNCERTAINTY_INTERPRETATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", UNCERTAINTY_INTERPRETATION_SYSTEM),
        ("human", UNCERTAINTY_INTERPRETATION_HUMAN),
    ]
)
