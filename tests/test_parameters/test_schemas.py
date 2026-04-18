"""Tests for parameter extraction schemas."""

from src.common.types import ConfidenceLevel, Scenario
from src.parameters.schemas import (
    ExtractedParameter,
    ModelParameterExtraction,
    ParameterExtractionSet,
)


def test_extracted_parameter():
    """Test parameter with confidence annotation."""
    param = ExtractedParameter(
        name="supply_loss_mbd",
        value=5.0,
        unit="mb/d",
        confidence=ConfidenceLevel.HIGH,
        directly_stated=True,
        extraction_note="Directly stated in narrative",
    )
    assert param.confidence == ConfidenceLevel.HIGH
    assert param.directly_stated is True


def test_model_parameter_extraction():
    """Test extraction for a (scenario, model) pair."""
    extraction = ModelParameterExtraction(
        scenario_id=Scenario.A,
        model_id="bornstein_krusell_rebelo",
        parameters=[
            ExtractedParameter(
                name="supply_loss_mbd", value=5.0, unit="mb/d",
                confidence=ConfidenceLevel.HIGH,
            ),
            ExtractedParameter(
                name="disruption_duration_months", value=1.5, unit="months",
                confidence=ConfidenceLevel.MEDIUM,
            ),
        ],
        warnings=["demand_elasticity_override not found in narrative"],
    )

    assert len(extraction.parameters) == 2
    assert len(extraction.warnings) == 1


def test_parameter_extraction_set():
    """Test collection of extractions."""
    pset = ParameterExtractionSet(
        extractions=[
            ModelParameterExtraction(
                scenario_id=Scenario.A,
                model_id="bornstein_krusell_rebelo",
            ),
            ModelParameterExtraction(
                scenario_id=Scenario.A,
                model_id="poles_jrc",
            ),
        ]
    )
    assert len(pset.extractions) == 2
