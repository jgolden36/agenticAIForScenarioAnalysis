"""Tests for parameter extraction schemas."""

import pytest
from pydantic import ValidationError

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


# ---------------------------------------------------------------------------
# expected_type enforcement
# ---------------------------------------------------------------------------


def test_expected_type_default_is_any():
    """When expected_type is omitted, behaviour matches the legacy schema."""
    p = ExtractedParameter(name="x", value=None)
    assert p.expected_type == "any"
    assert p.value is None


def test_expected_type_number_rejects_null():
    """Required numeric fields must not accept null — that was the
    upstream bug that caused 102/136 model runs to fail validation."""
    with pytest.raises(ValidationError):
        ExtractedParameter(
            name="capital_cost_multiplier",
            value=None,
            expected_type="positive_number",
        )


def test_expected_type_number_coerces_decimal_string():
    """LLMs sometimes return '1.5' as a string instead of 1.5 — coerce it."""
    p = ExtractedParameter(name="x", value="1.5", expected_type="number")
    assert p.value == 1.5
    assert isinstance(p.value, float)


def test_expected_type_number_extracts_leading_numeric():
    """Coerce strings like '5%' or '30 mb/d' to their leading numeric token."""
    p = ExtractedParameter(name="x", value="30 mb/d", expected_type="non_negative_number")
    assert p.value == 30.0


def test_expected_type_positive_number_rejects_zero():
    """positive_number requires strictly > 0."""
    with pytest.raises(ValidationError):
        ExtractedParameter(name="x", value=0, expected_type="positive_number")


def test_expected_type_non_negative_number_rejects_negative():
    """non_negative_number rejects negative values."""
    with pytest.raises(ValidationError):
        ExtractedParameter(name="x", value=-1, expected_type="non_negative_number")
    # but accepts zero
    p = ExtractedParameter(name="x", value=0, expected_type="non_negative_number")
    assert p.value == 0.0


def test_expected_type_percent_range():
    """percent must be in [0, 100]."""
    p = ExtractedParameter(name="x", value=42.5, expected_type="percent")
    assert p.value == 42.5
    with pytest.raises(ValidationError):
        ExtractedParameter(name="x", value=150.0, expected_type="percent")
    with pytest.raises(ValidationError):
        ExtractedParameter(name="x", value=-1.0, expected_type="percent")


def test_expected_type_boolean_coercion():
    """boolean accepts true/false/0/1 and string equivalents."""
    assert ExtractedParameter(name="x", value="true", expected_type="boolean").value is True
    assert ExtractedParameter(name="x", value="no", expected_type="boolean").value is False
    assert ExtractedParameter(name="x", value=1, expected_type="boolean").value is True
    with pytest.raises(ValidationError):
        ExtractedParameter(name="x", value="maybe", expected_type="boolean")


def test_expected_type_string_coerces_to_str():
    """string coerces any value to str."""
    p = ExtractedParameter(name="x", value=42, expected_type="string")
    assert p.value == "42"


def test_expected_type_list_csv_fallback():
    """list expected_type accepts a comma-separated string fallback."""
    p = ExtractedParameter(name="x", value="a, b ,c", expected_type="list")
    assert p.value == ["a", "b", "c"]


def test_expected_type_dict_rejects_non_dict():
    """dict expected_type rejects non-dict values."""
    with pytest.raises(ValidationError):
        ExtractedParameter(name="x", value="not-a-dict", expected_type="dict")
    p = ExtractedParameter(name="x", value={"k": 1}, expected_type="dict")
    assert p.value == {"k": 1}
