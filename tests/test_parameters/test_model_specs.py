"""Tests for model input specifications."""

from src.parameters.model_specs import ALL_MODEL_SPECS


def test_all_model_specs_loaded():
    """Verify all model specs are loaded and have required fields."""
    # Should have all 30 models
    assert len(ALL_MODEL_SPECS) >= 28

    for model_id, spec in ALL_MODEL_SPECS.items():
        assert spec["model_id"] == model_id, f"{model_id}: model_id mismatch"
        assert "description" in spec, f"{model_id}: missing description"
        assert "commodity_system" in spec, f"{model_id}: missing commodity_system"
        assert "analytical_level" in spec, f"{model_id}: missing analytical_level"
        assert "required_parameters" in spec, f"{model_id}: missing required_parameters"
        assert len(spec["required_parameters"]) > 0, f"{model_id}: no required parameters"


def test_model_spec_parameter_format():
    """Verify each parameter spec has name, description, and unit."""
    for model_id, spec in ALL_MODEL_SPECS.items():
        for param in spec["required_parameters"]:
            assert "name" in param, f"{model_id}: param missing name"
            assert "description" in param, f"{model_id}: param missing description"
            assert "unit" in param, f"{model_id}: param missing unit"
