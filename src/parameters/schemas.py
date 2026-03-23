"""Pydantic schemas for extracted parameters (Module 2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.common.types import ConfidenceLevel, Scenario


class ExtractedParameter(BaseModel):
    """A single parameter extracted from a scenario narrative."""

    name: str
    value: Any
    unit: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    directly_stated: bool = True
    extraction_note: str = ""


class ModelParameterExtraction(BaseModel):
    """Parameters extracted for a specific (scenario, model) pair."""

    scenario_id: Scenario
    model_id: str
    parameters: list[ExtractedParameter] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParameterExtractionSet(BaseModel):
    """All extracted parameters for all (scenario, model) pairs."""

    extractions: list[ModelParameterExtraction] = Field(default_factory=list)
