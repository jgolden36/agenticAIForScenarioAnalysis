"""Tests for YAML-based declarative consistency rules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.state import ModelExecutionResult
from src.synthesis.consistency import (
    DEFAULT_RULES,
    check_consistency,
    get_consistency_rules,
    load_rules_from_yaml,
)


class TestLoadRulesFromYaml:
    def test_load_from_existing_yaml(self):
        """Test loading rules from the project's consistency_rules.yaml."""
        project_root = Path(__file__).parent.parent.parent
        yaml_path = project_root / "configs" / "consistency_rules.yaml"

        if yaml_path.exists():
            rules = load_rules_from_yaml(yaml_path)
            assert len(rules) > 0
            # Check that each rule has required fields
            for rule in rules:
                assert "model_a" in rule
                assert "model_b" in rule
                assert "variable_a" in rule
                assert "variable_b" in rule
                assert "tolerance_pct" in rule
                assert "description" in rule

    def test_falls_back_to_defaults_on_missing_file(self):
        rules = load_rules_from_yaml("/nonexistent/path/rules.yaml")
        assert rules == DEFAULT_RULES

    def test_custom_yaml_with_per_rule_tolerance(self):
        """Test that per-rule tolerance_pct is respected."""
        yaml_content = """
rules:
  - model_a: model_x
    model_b: model_y
    variable_a: price
    variable_b: price
    tolerance_pct: 5.0
    description: Tight tolerance test
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()

            rules = load_rules_from_yaml(f.name)
            assert len(rules) == 1
            assert rules[0]["tolerance_pct"] == 5.0
            assert rules[0]["model_a"] == "model_x"

    def test_empty_yaml_falls_back_to_defaults(self):
        yaml_content = "rules: []\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()

            rules = load_rules_from_yaml(f.name)
            assert rules == DEFAULT_RULES


class TestPerRuleTolerance:
    def test_per_rule_tolerance_override(self):
        """Test that check_consistency uses per-rule tolerance from YAML."""
        import src.synthesis.consistency as consistency_mod

        # Set up custom rules with tight tolerance
        custom_rules = [
            {
                "model_a": "model_a",
                "model_b": "model_b",
                "variable_a": "price",
                "variable_b": "price",
                "tolerance_pct": 5.0,  # Very tight
                "description": "Tight check",
            },
        ]

        # Monkey-patch the cached rules
        old_rules = consistency_mod._loaded_rules
        consistency_mod._loaded_rules = custom_rules

        try:
            # Create results that differ by 10% (exceeds 5% tolerance)
            results = [
                ModelExecutionResult(
                    scenario_id=Scenario.A,
                    model_id="model_a",
                    status=ModelExecutionStatus.COMPLETED,
                    outputs={"price": 100.0},
                ),
                ModelExecutionResult(
                    scenario_id=Scenario.A,
                    model_id="model_b",
                    status=ModelExecutionStatus.COMPLETED,
                    outputs={"price": 110.0},
                ),
            ]

            flags = check_consistency(Scenario.A, results)
            assert len(flags) == 1
            assert flags[0].tolerance_pct == 5.0
            assert flags[0].deviation_pct > 5.0

        finally:
            consistency_mod._loaded_rules = old_rules

    def test_within_per_rule_tolerance_no_flag(self):
        """Values within per-rule tolerance should not flag."""
        import src.synthesis.consistency as consistency_mod

        custom_rules = [
            {
                "model_a": "model_a",
                "model_b": "model_b",
                "variable_a": "price",
                "variable_b": "price",
                "tolerance_pct": 50.0,  # Very loose
                "description": "Loose check",
            },
        ]

        old_rules = consistency_mod._loaded_rules
        consistency_mod._loaded_rules = custom_rules

        try:
            results = [
                ModelExecutionResult(
                    scenario_id=Scenario.A,
                    model_id="model_a",
                    status=ModelExecutionStatus.COMPLETED,
                    outputs={"price": 100.0},
                ),
                ModelExecutionResult(
                    scenario_id=Scenario.A,
                    model_id="model_b",
                    status=ModelExecutionStatus.COMPLETED,
                    outputs={"price": 130.0},
                ),
            ]

            flags = check_consistency(Scenario.A, results)
            assert len(flags) == 0

        finally:
            consistency_mod._loaded_rules = old_rules
