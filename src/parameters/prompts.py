"""Prompt templates for parameter extraction (Module 2)."""

from langchain_core.prompts import ChatPromptTemplate

PARAMETER_EXTRACTION_SYSTEM = """You are a quantitative analyst extracting structured parameters from scenario \
narratives. Your task is to parse a scenario narrative and extract the specific quantitative values needed by a \
domain model.

Rules:
1. Only extract values that are directly stated or can be confidently inferred from the narrative.
2. For each parameter, indicate whether it was directly stated or inferred.
3. Assign a confidence level: high (directly stated), medium (strongly implied), low (required inference).
4. Flag any parameters that the model requires but the narrative does not address.
5. Output your response as valid JSON matching the provided schema."""

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

## Required Parameters
The model requires the following parameters:
{required_parameters}

Extract each required parameter from the scenario narrative. If a parameter cannot be determined, \
note it in the warnings list."""

PARAMETER_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", PARAMETER_EXTRACTION_SYSTEM),
        ("human", PARAMETER_EXTRACTION_HUMAN),
    ]
)
