"""Adapter stub for SahysMod — Spatially distributed agro-hydro-salinity model.

SahysMod simulates the coupled dynamics of soil salinity, groundwater depth, and
crop yield across spatially distributed irrigation districts. In the Hormuz pipeline
it captures the downstream agricultural consequences of reduced irrigation water
availability (caused by desalination disruption and disrupted fertiliser supply
logistics) and the associated secondary salinity accumulation in soils and
shallow aquifers.

Real integration requirements:
- A SahysMod installation (ILRI / QuantumGIS plugin, or the standalone Fortran
  executable) accessible on the execution host.
- A pre-configured SahysMod input polygon network covering the affected Gulf and
  Near-East irrigation districts (typically prepared as *.sam files).
- A subprocess or file-based driver that writes per-season input decks from the
  ``inputs`` dict, invokes the SahysMod CLI, and captures stdout/stderr.
- Post-run extraction of seasonal output tables (soil salinity ECe [dS/m],
  groundwater depth [m], relative crop yield [-]) from SahysMod's fixed-format
  ASCII output files.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Required parameter names, sourced from WATER_MODEL_SPECS["sahysmod"].
_REQUIRED_PARAMS: list[str] = [
    "irrigation_water_reduction_pct",
    "salinity_increase_factor",
    "disruption_duration_weeks",
]

# Plausibility bounds for numeric parameters.
_BOUNDS: dict[str, tuple[float, float]] = {
    "irrigation_water_reduction_pct": (0.0, 100.0),
    "salinity_increase_factor": (1.0, 20.0),   # factor >=1 (1 = no change)
    "disruption_duration_weeks": (0.0, 260.0),
}


class SahysModAdapter(ModelAdapter):
    """Adapter stub for the SahysMod agro-hydro-salinity model."""

    # ------------------------------------------------------------------
    # Identity properties
    # ------------------------------------------------------------------

    @property
    def model_id(self) -> str:
        return "sahysmod"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "SahysMod: Spatially distributed agro-hydro-salinity model. Simulates "
            "the impact of reduced irrigation water availability on soil salinity, "
            "groundwater depth, and relative crop yield across Gulf and Near-East "
            "irrigation districts under Strait of Hormuz closure scenarios."
        )

    # ------------------------------------------------------------------
    # Pipeline interface
    # ------------------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Check that all required parameters are present and within plausible ranges.

        Args:
            params: Parameter dictionary from the extraction module.

        Returns:
            ValidationResult describing any errors or warnings found.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Presence check
        for name in _REQUIRED_PARAMS:
            if name not in params:
                errors.append(f"Missing required parameter: '{name}'")

        # Plausibility / type checks
        for param_name, (lo, hi) in _BOUNDS.items():
            if param_name not in params:
                continue
            value = params[param_name]
            try:
                fval = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"Parameter '{param_name}' must be numeric; got {value!r}"
                )
                continue
            if not (lo <= fval <= hi):
                warnings.append(
                    f"Parameter '{param_name}' value {fval} is outside expected "
                    f"range [{lo}, {hi}]; verify before running."
                )

        # salinity_increase_factor < 1 would mean salinity decreases, which is
        # implausible under a supply disruption scenario.
        if "salinity_increase_factor" in params:
            try:
                factor = float(params["salinity_increase_factor"])
                if factor < 1.0:
                    errors.append(
                        "Parameter 'salinity_increase_factor' must be >= 1.0 "
                        "(a factor < 1 implies salinity improvement, which is "
                        "inconsistent with a supply disruption scenario)."
                    )
            except (TypeError, ValueError):
                pass  # already flagged above

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through unchanged.

        SahysMod uses fixed-format ASCII input decks (.sam files). Input translation
        (writing season-by-season input records for each spatial polygon) is the
        responsibility of the real execute() implementation.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same dictionary, unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute SahysMod. Raises NotImplementedError until model is integrated.

        Real implementation requirements:
        - Path to the SahysMod executable set in model_configs/default.yaml under
          ``sahysmod.executable_path``.
        - Path to the baseline polygon network (.sam) set under
          ``sahysmod.baseline_network_path``.
        - Logic to scale irrigation water inputs and initial salinity conditions from
          the ``inputs`` dict, write modified .sam input decks to a temporary
          working directory, and invoke the SahysMod CLI:
              sahysmod <input_deck> <output_prefix>
        - Capture of stdout/stderr for convergence diagnostics.
        - Post-run parsing of ASCII output tables into a structured dict for
          parse_outputs to consume.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until integration is complete.
        """
        raise NotImplementedError(
            "SahysModAdapter.execute() is a stub. To integrate SahysMod: "
            "(1) configure 'sahysmod.executable_path' and 'sahysmod.baseline_network_path' "
            "in configs/model_configs/default.yaml; "
            "(2) implement logic to write modified .sam input decks from the inputs dict "
            "into a temporary working directory; "
            "(3) invoke the SahysMod CLI via subprocess and capture stdout/stderr; "
            "(4) parse fixed-format ASCII output tables and return a ModelOutput."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through as a ModelOutput container.

        The real implementation should parse SahysMod's fixed-format ASCII output
        tables and populate the ``outputs`` dict with standardised keys such as:
            - ``soil_salinity_dS_m``: dict mapping polygon_id -> season -> float
            - ``groundwater_depth_m``: dict mapping polygon_id -> season -> float
            - ``relative_crop_yield``: dict mapping polygon_id -> season -> float (0–1)

        Args:
            raw: Raw output from execute() (passthrough for stub).

        Returns:
            ModelOutput wrapping the raw value unchanged.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
