"""Adapter stub for the LNG Spreadsheet Tool (LNGST).

LNGST is an Excel-based scenario-level LNG trade flow simulation tool. It
models how export reductions from Qatar and the UAE, combined with spot price
multiplier assumptions, translate into regional supply gaps and trade flow
shifts. As a spreadsheet tool, it is well-suited for rapid scenario screening
and communicating results to non-specialist stakeholders.

Real integration requirements:
- The LNGST Excel workbook (or a compatible .xlsx template)
- openpyxl (for programmatic read/write of workbook cells) or xlwings (for
  live COM automation if macro execution is required)
- Identification of the specific named cells or ranges for each input parameter
  and each output variable within the workbook
- If the workbook contains VBA macros that perform the simulation, either
  xlwings + a local Excel installation (Windows/macOS) or a macro-free Python
  reimplementation of the calculation logic will be required
- Output: regional LNG supply shortfalls (bcm or mtpa), spot price paths by
  hub (Henry Hub, TTF, JKM), and trade flow re-allocation matrices
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model. Each entry is (name, description, unit).
_REQUIRED_PARAMS: list[tuple[str, str, str]] = [
    (
        "qatar_export_reduction_pct",
        "Percentage reduction in Qatari LNG exports due to the Strait closure",
        "percent",
    ),
    (
        "uae_export_reduction_pct",
        "Percentage reduction in UAE LNG exports due to the Strait closure",
        "percent",
    ),
    (
        "spot_price_multiplier",
        "Multiplier applied to baseline LNG spot prices to reflect scarcity premium "
        "(e.g., 1.5 = 50% above baseline)",
        "dimensionless",
    ),
    (
        "disruption_duration_months",
        "Duration of the Strait closure and associated LNG supply disruption",
        "months",
    ),
]

_REQUIRED_PARAM_NAMES: frozenset[str] = frozenset(p[0] for p in _REQUIRED_PARAMS)


class LNGSTAdapter(ModelAdapter):
    """Adapter for the LNG Spreadsheet Tool (LNGST).

    Simulates scenario-level LNG trade flow adjustments driven by Persian Gulf
    export reductions and spot price shocks. LNGST operates at the scenario
    level (not time-step resolution) and is particularly useful for rapid
    cross-scenario comparison. Required parameters capture the export loss
    fractions for the two primary Gulf LNG exporters, the spot price response,
    and the disruption timeline.

    Note: the real implementation requires openpyxl (or xlwings) to interface
    with the Excel workbook. If the workbook relies on VBA macros, a live Excel
    installation accessible via COM automation will also be needed.
    """

    @property
    def model_id(self) -> str:
        return "lngst"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "LNG Spreadsheet Tool (LNGST): Excel-based scenario-level simulation of "
            "LNG trade flow adjustments, regional supply shortfalls, and spot price "
            "paths under Strait of Hormuz closure scenarios affecting Qatari and UAE "
            "exports."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Check that all required parameters are present and within plausible ranges.

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult listing any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        missing = _REQUIRED_PARAM_NAMES - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if not missing:
            qatar_loss = params["qatar_export_reduction_pct"]
            if not isinstance(qatar_loss, (int, float)):
                errors.append("'qatar_export_reduction_pct' must be numeric")
            elif not (0.0 <= qatar_loss <= 100.0):
                errors.append(
                    f"'qatar_export_reduction_pct' must be in [0, 100]; got {qatar_loss}"
                )

            uae_loss = params["uae_export_reduction_pct"]
            if not isinstance(uae_loss, (int, float)):
                errors.append("'uae_export_reduction_pct' must be numeric")
            elif not (0.0 <= uae_loss <= 100.0):
                errors.append(
                    f"'uae_export_reduction_pct' must be in [0, 100]; got {uae_loss}"
                )

            if (
                isinstance(qatar_loss, (int, float))
                and isinstance(uae_loss, (int, float))
                and qatar_loss == 0.0
                and uae_loss == 0.0
            ):
                warnings.append(
                    "Both 'qatar_export_reduction_pct' and 'uae_export_reduction_pct' "
                    "are 0; verify that a Strait closure scenario is intended"
                )

            multiplier = params["spot_price_multiplier"]
            if not isinstance(multiplier, (int, float)):
                errors.append("'spot_price_multiplier' must be numeric")
            elif multiplier <= 0.0:
                errors.append(
                    f"'spot_price_multiplier' must be positive; got {multiplier}"
                )
            elif multiplier < 1.0:
                warnings.append(
                    f"'spot_price_multiplier' of {multiplier} implies a price decrease "
                    "relative to baseline; verify this is intentional for a supply "
                    "disruption scenario"
                )
            elif multiplier > 5.0:
                warnings.append(
                    f"'spot_price_multiplier' of {multiplier} (i.e., {multiplier:.0f}x "
                    "baseline) is extremely high; verify this is intentional"
                )

            duration = params["disruption_duration_months"]
            if not isinstance(duration, (int, float)):
                errors.append("'disruption_duration_months' must be numeric")
            elif duration <= 0:
                errors.append(
                    f"'disruption_duration_months' must be positive; got {duration}"
                )
            elif duration > 24:
                warnings.append(
                    f"'disruption_duration_months' of {duration} exceeds 24 months; "
                    "verify this is intentional"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through unchanged.

        The real implementation will map these parameters onto specific named
        cell ranges within the LNGST Excel workbook using openpyxl (for
        formula-only workbooks) or xlwings (for workbooks requiring live Excel
        and VBA macro execution).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same parameter dictionary (passthrough).
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the LNG Spreadsheet Tool.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: This stub is not yet integrated with the LNGST
                Excel workbook. Integration requires: (1) the LNGST .xlsx
                workbook file, (2) openpyxl installed (for formula-only
                workbooks) or xlwings + a licensed Excel installation (for
                workbooks relying on VBA macros), (3) a cell-range mapping that
                identifies which cells correspond to each input parameter and
                output variable, and (4) a post-calculation read step to
                extract results after Excel recalculates.
        """
        raise NotImplementedError(
            "LNGSTAdapter.execute is not yet implemented. "
            "Integration requires the LNGST Excel workbook, the openpyxl library "
            "(pip install openpyxl) for programmatic cell access, and a mapping of "
            "scenario parameters to named cell ranges within the workbook. If the "
            "workbook uses VBA macros, xlwings and a local Excel installation are "
            "also required. Obtain the workbook from the model's custodian."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse raw LNGST output into a standardized ModelOutput.

        The real implementation will read computed cell values from the LNGST
        workbook after execution and extract: regional LNG supply shortfalls
        (bcm or mtpa by hub), spot price paths (Henry Hub, TTF, JKM), and
        bilateral trade flow re-allocation matrices.

        Args:
            raw: Raw output from execute (passthrough for now).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"parse_status": "passthrough"},
        )
