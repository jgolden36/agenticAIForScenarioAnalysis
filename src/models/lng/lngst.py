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
from src.models.adapters.excel_adapter import CellMapping, ExcelAdapter, ExcelConfig
from src.models.base import ModelOutput, ValidationResult

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


class LNGSTAdapter(ExcelAdapter):
    """Adapter for the LNG Spreadsheet Tool (LNGST).

    Inherits from ExcelAdapter for openpyxl/xlwings-based workbook I/O.
    Supports both headless openpyxl (cached values only, no recalculation)
    and xlwings (full Excel recalculation, VBA macro support).

    Simulates scenario-level LNG trade flow adjustments driven by Persian Gulf
    export reductions and spot price shocks. LNGST operates at the scenario
    level (not time-step resolution) and is particularly useful for rapid
    cross-scenario comparison.

    WARNING: openpyxl cannot recalculate formulas — if the workbook uses
    formula chains, use xlwings (requires Excel installed, Windows/macOS only).
    """

    def __init__(self, config: ExcelConfig | None = None) -> None:
        super().__init__(config)

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

    @property
    def input_mappings(self) -> list[CellMapping]:
        """Map scenario parameters to workbook input cells.

        These cell references are placeholders — update to match
        the actual LNGST workbook structure once obtained.
        """
        return [
            CellMapping(sheet="Inputs", cell="B4", param_name="qatar_export_reduction_pct"),
            CellMapping(sheet="Inputs", cell="B5", param_name="uae_export_reduction_pct"),
            CellMapping(sheet="Inputs", cell="B6", param_name="spot_price_multiplier"),
            CellMapping(sheet="Inputs", cell="B7", param_name="disruption_duration_months"),
        ]

    @property
    def output_mappings(self) -> list[CellMapping]:
        """Map workbook output cells to result variables.

        These cell references are placeholders — update to match
        the actual LNGST workbook structure once obtained.
        """
        return [
            CellMapping(sheet="Outputs", cell="C12", param_name="lng_price_usd_mmbtu"),
            CellMapping(sheet="Outputs", cell="C13", param_name="supply_shortfall_bcm"),
            CellMapping(sheet="Outputs", cell="C14", param_name="henry_hub_price"),
            CellMapping(sheet="Outputs", cell="C15", param_name="ttf_price"),
            CellMapping(sheet="Outputs", cell="C16", param_name="jkm_price"),
        ]

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

        When an ExcelConfig is provided, the ExcelAdapter base class handles
        workbook I/O (openpyxl or xlwings). Until the actual LNGST workbook
        is available, raises NotImplementedError.
        """
        if self._config is not None:
            return super().execute(inputs)

        raise NotImplementedError(
            "LNGSTAdapter.execute is not yet implemented. "
            "Provide an ExcelConfig with the workbook path to enable execution. "
            "The ExcelAdapter base class handles openpyxl (headless) or xlwings "
            "(full recalculation) based on config. Update input_mappings and "
            "output_mappings once the actual workbook cell layout is known."
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
