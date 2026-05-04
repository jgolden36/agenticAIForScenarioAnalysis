"""Adapter for the Energy Flux US Gas Power Build-Out Constraint Model v1.0.

This Excel workbook models throughput-constrained commissioning of US
gas-fired power generation capacity and translates cumulative capacity
additions into incremental gas demand (Bcf/d).  It answers the question:
*"How fast can the US actually build new gas-fired power, and how much
additional gas will that require?"*

The pipeline of projects flows through a priority queue:
    Construction → Pre-construction → Announced
Each year the model adds ``min(build_cap, remaining_in_bucket)`` from each
bucket in priority order.

Supports two execution modes:
  1. **Python-native** (default): reimplements the spreadsheet formulas.
  2. **Excel-based**: drives the actual workbook via ``ExcelAdapter``.

The workbook lives at:
  ``Models/LNG/Energy-Flux-US-Gas-Power-Build-Out-Constraint-Model-v1.0.xlsx``
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.excel_adapter import CellMapping, ExcelAdapter, ExcelConfig
from src.models.base import ModelOutput, ValidationResult

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class YearlyResult(BaseModel):
    """Throughput-model results for a single year."""

    year: int
    added_construction_mw: float
    added_pre_construction_mw: float
    added_announced_mw: float
    total_added_mw: float
    cumulative_added_gw: float
    remaining_construction_mw: float
    remaining_pre_construction_mw: float
    remaining_announced_mw: float
    remaining_total_mw: float
    incremental_bcf_per_day_low: float
    incremental_bcf_per_day_mid: float
    incremental_bcf_per_day_high: float


class SegmentedResult(BaseModel):
    """Data-centre vs. non-DC gas burn segmentation for one year."""

    year: int
    cumulative_gw: float
    dc_capacity_gw: float
    non_dc_capacity_gw: float
    dc_effective_cf: float
    non_dc_effective_cf: float
    blended_bcf_per_day: float


class GasPowerResult(BaseModel):
    """Complete output from the gas-power build-out calculation."""

    yearly_results: list[YearlyResult]
    total_pipeline_mw: float
    build_cap_mw_yr: float
    build_scenario: str
    total_commissioned_gw: float
    years_to_clear_backlog: int | None
    by_2030_new_gw: float
    by_2030_bcf_per_day_mid: float
    by_2035_new_gw: float
    by_2035_bcf_per_day_mid: float
    segmented_results: list[SegmentedResult] | None = None


# ---------------------------------------------------------------------------
# Build-cap scenario presets (from workbook Inputs!B12:B15)
# ---------------------------------------------------------------------------

BUILD_SCENARIOS: dict[str, float] = {
    "conservative": 7_264.0,   # post-2020 average
    "central": 10_135.0,       # 2010-2024 average
    "stretch": 22_697.0,       # peak since 2010
    "2002_dash": 63_975.0,     # all-time high (2002)
}

# Gas-burn translation assumptions (from workbook Inputs!B19:D21)
CF_PRESETS = {"low": 0.35, "mid": 0.45, "high": 0.60}
HR_PRESETS = {"low": 6_800, "mid": 7_200, "high": 7_600}  # Btu/kWh
MMBTU_PER_BCF = 1_037_000

# Pipeline defaults (from workbook Inputs!B5:B7)
_DEFAULT_CONSTRUCTION_MW = 30_000
_DEFAULT_PRE_CONSTRUCTION_MW = 159_000
_DEFAULT_ANNOUNCED_MW = 63_000

# Segmentation defaults (from Marginal_CF_Segmentation!C6:C8)
_DEFAULT_DC_SHARE = 0.37
_DEFAULT_DC_BACKUP_CF_MULT = 1.0
_DEFAULT_OTHER_BACKUP_CF_MULT = 1.0

# Prime power CF defaults (from Marginal_CF_Segmentation!B14:C16)
_PRIME_PRESETS = {
    "low":  {"p_prime": 0.60, "cf_prime": 0.70},
    "mid":  {"p_prime": 0.70, "cf_prime": 0.80},
    "high": {"p_prime": 0.80, "cf_prime": 0.90},
}


# ---------------------------------------------------------------------------
# Python calculation engine
# ---------------------------------------------------------------------------

def _gas_burn_bcf_per_day(
    cumulative_gw: float,
    capacity_factor: float,
    heat_rate: float,
) -> float:
    """Convert cumulative GW to incremental gas burn (Bcf/d).

    Formula:  GW × 1e6 kW × CF × 24 h × HR Btu/kWh  ÷  (1e6 × MMBTU_PER_BCF)
    Simplifies to:  GW × CF × 24 × HR / MMBTU_PER_BCF
    """
    return cumulative_gw * capacity_factor * 24 * heat_rate / MMBTU_PER_BCF


def compute_buildout(
    *,
    construction_mw: float = _DEFAULT_CONSTRUCTION_MW,
    pre_construction_mw: float = _DEFAULT_PRE_CONSTRUCTION_MW,
    announced_mw: float = _DEFAULT_ANNOUNCED_MW,
    build_cap_mw_yr: float | None = None,
    build_scenario: str = "central",
    projection_years: int = 10,
    start_year: int = 2026,
    cf_low: float = CF_PRESETS["low"],
    cf_mid: float = CF_PRESETS["mid"],
    cf_high: float = CF_PRESETS["high"],
    hr_low: float = HR_PRESETS["low"],
    hr_mid: float = HR_PRESETS["mid"],
    hr_high: float = HR_PRESETS["high"],
) -> GasPowerResult:
    """Reimplement the workbook's throughput-constrained commissioning model.

    Priority order: Construction → Pre-construction → Announced.
    Each year draws ``min(build_cap, remaining)`` from each bucket.
    """
    if build_cap_mw_yr is None:
        build_cap_mw_yr = BUILD_SCENARIOS.get(build_scenario, BUILD_SCENARIOS["central"])

    total_pipeline = construction_mw + pre_construction_mw + announced_mw
    rem_c = construction_mw
    rem_p = pre_construction_mw
    rem_a = announced_mw
    cumulative_mw = 0.0

    yearly: list[YearlyResult] = []
    cleared_year: int | None = None

    for yi in range(projection_years):
        budget = build_cap_mw_yr

        add_c = min(budget, rem_c)
        budget -= add_c
        rem_c -= add_c

        add_p = min(budget, rem_p)
        budget -= add_p
        rem_p -= add_p

        add_a = min(budget, rem_a)
        rem_a -= add_a

        total_add = add_c + add_p + add_a
        cumulative_mw += total_add
        cum_gw = cumulative_mw / 1_000

        rem_total = rem_c + rem_p + rem_a
        if cleared_year is None and rem_total <= 0:
            cleared_year = yi + 1

        yearly.append(YearlyResult(
            year=start_year + yi,
            added_construction_mw=add_c,
            added_pre_construction_mw=add_p,
            added_announced_mw=add_a,
            total_added_mw=total_add,
            cumulative_added_gw=cum_gw,
            remaining_construction_mw=rem_c,
            remaining_pre_construction_mw=rem_p,
            remaining_announced_mw=rem_a,
            remaining_total_mw=rem_total,
            incremental_bcf_per_day_low=_gas_burn_bcf_per_day(cum_gw, cf_low, hr_low),
            incremental_bcf_per_day_mid=_gas_burn_bcf_per_day(cum_gw, cf_mid, hr_mid),
            incremental_bcf_per_day_high=_gas_burn_bcf_per_day(cum_gw, cf_high, hr_high),
        ))

    by_2030_idx = min(4, len(yearly) - 1)  # year index for 2030
    by_2035_idx = min(9, len(yearly) - 1)  # year index for 2035

    return GasPowerResult(
        yearly_results=yearly,
        total_pipeline_mw=total_pipeline,
        build_cap_mw_yr=build_cap_mw_yr,
        build_scenario=build_scenario,
        total_commissioned_gw=yearly[-1].cumulative_added_gw if yearly else 0,
        years_to_clear_backlog=cleared_year,
        by_2030_new_gw=yearly[by_2030_idx].cumulative_added_gw,
        by_2030_bcf_per_day_mid=yearly[by_2030_idx].incremental_bcf_per_day_mid,
        by_2035_new_gw=yearly[by_2035_idx].cumulative_added_gw,
        by_2035_bcf_per_day_mid=yearly[by_2035_idx].incremental_bcf_per_day_mid,
    )


def compute_segmented_burn(
    yearly_results: list[YearlyResult],
    *,
    dc_share: float = _DEFAULT_DC_SHARE,
    p_prime: float = _PRIME_PRESETS["mid"]["p_prime"],
    cf_prime: float = _PRIME_PRESETS["mid"]["cf_prime"],
    dc_backup_cf_mult: float = _DEFAULT_DC_BACKUP_CF_MULT,
    other_backup_cf_mult: float = _DEFAULT_OTHER_BACKUP_CF_MULT,
    fleet_avg_cf: float = CF_PRESETS["mid"],
    heat_rate: float = HR_PRESETS["mid"],
) -> list[SegmentedResult]:
    """Apply data-centre segmented CF analysis to yearly capacity additions.

    Data centres use prime power at high CF, with backup at a different CF.
    Non-DC capacity runs at fleet-average CF.  The blended CF determines
    total gas burn.
    """
    results: list[SegmentedResult] = []
    for yr in yearly_results:
        gw = yr.cumulative_added_gw
        dc_gw = gw * dc_share
        non_dc_gw = gw * (1 - dc_share)

        cf_backup_dc = fleet_avg_cf * dc_backup_cf_mult
        dc_eff_cf = p_prime * cf_prime + (1 - p_prime) * cf_backup_dc

        cf_backup_other = fleet_avg_cf * other_backup_cf_mult
        non_dc_eff_cf = cf_backup_other

        blended_bcf = (
            _gas_burn_bcf_per_day(dc_gw, dc_eff_cf, heat_rate)
            + _gas_burn_bcf_per_day(non_dc_gw, non_dc_eff_cf, heat_rate)
        )

        results.append(SegmentedResult(
            year=yr.year,
            cumulative_gw=gw,
            dc_capacity_gw=dc_gw,
            non_dc_capacity_gw=non_dc_gw,
            dc_effective_cf=dc_eff_cf,
            non_dc_effective_cf=non_dc_eff_cf,
            blended_bcf_per_day=blended_bcf,
        ))
    return results


# ---------------------------------------------------------------------------
# Excel I/O utilities
# ---------------------------------------------------------------------------

def read_workbook_inputs(workbook_path: str | Path) -> dict[str, Any]:
    """Read current input values from the Gas Power Build-Out workbook."""
    from openpyxl import load_workbook

    wb = load_workbook(str(workbook_path), data_only=True)
    inp = wb["Inputs"]

    pipeline = {
        "construction_mw": inp["B5"].value,
        "pre_construction_mw": inp["B6"].value,
        "announced_mw": inp["B7"].value,
    }
    build_caps = {
        "conservative_cap": inp["B12"].value,
        "central_cap": inp["B13"].value,
        "stretch_cap": inp["B14"].value,
        "dash_2002_cap": inp["B15"].value,
    }
    burn_assumptions = {
        "cf_low": inp["B19"].value,
        "cf_mid": inp["B20"].value if inp["B20"].value else inp["C19"].value,
        "cf_high": inp["B21"].value if inp["B21"].value else inp["D19"].value,
        "hr_low": inp["C19"].value if inp["C19"].value else inp["B20"].value,
        "hr_mid": inp["C20"].value if inp["C20"].value else inp["C20"].value,
        "hr_high": inp["C21"].value if inp["C21"].value else inp["D21"].value,
    }

    seg_data: dict[str, Any] = {}
    if "Marginal_CF_Segmentation" in wb.sheetnames:
        seg = wb["Marginal_CF_Segmentation"]
        seg_data = {
            "dc_share": seg["C6"].value,
            "dc_backup_cf_mult": seg["C7"].value,
            "other_backup_cf_mult": seg["C8"].value,
        }

    wb.close()
    return {**pipeline, **build_caps, **burn_assumptions, **seg_data}


def write_scenario_workbook(
    source_path: str | Path,
    output_path: str | Path,
    params: dict[str, Any],
) -> Path:
    """Create a copy of the workbook with scenario parameters injected."""
    import shutil

    from openpyxl import load_workbook

    output_path = Path(output_path)
    shutil.copy2(str(source_path), str(output_path))

    wb = load_workbook(str(output_path))
    inp = wb["Inputs"]

    cell_map: dict[str, str] = {
        "construction_mw": "B5",
        "pre_construction_mw": "B6",
        "announced_mw": "B7",
    }
    for param, cell in cell_map.items():
        if param in params:
            inp[cell] = params[param]

    if "Marginal_CF_Segmentation" in wb.sheetnames:
        seg = wb["Marginal_CF_Segmentation"]
        seg_map: dict[str, str] = {
            "dc_share": "C6",
            "dc_backup_cf_mult": "C7",
            "other_backup_cf_mult": "C8",
        }
        for param, cell in seg_map.items():
            if param in params:
                seg[cell] = params[param]

    wb.save(str(output_path))
    wb.close()
    return output_path


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class EnergyFluxGasPowerAdapter(ExcelAdapter):
    """Adapter for the Energy Flux US Gas Power Build-Out Constraint Model v1.0.

    Accepts a ``build_scenario`` name (``conservative``, ``central``,
    ``stretch``, ``2002_dash``) or a ``custom_build_cap_mw_yr`` override.
    Pipeline capacity can be adjusted to reflect crisis-driven acceleration
    or delay of projects.

    When an ``ExcelConfig`` is supplied the adapter can drive the actual
    workbook via xlwings.  Without a config, runs in Python-native mode.
    """

    def __init__(self, config: ExcelConfig | None = None) -> None:
        super().__init__(config)

    # -- ModelAdapter metadata -----------------------------------------------

    @property
    def model_id(self) -> str:
        return "energy_flux_gas_power"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Energy Flux US Gas Power Build-Out Constraint Model v1.0: models "
            "throughput-constrained commissioning of US gas-fired power capacity "
            "and translates cumulative additions into incremental gas demand (Bcf/d)."
        )

    # -- ExcelAdapter mappings -----------------------------------------------

    @property
    def input_mappings(self) -> list[CellMapping]:
        return [
            CellMapping(sheet="Inputs", cell="B5", param_name="construction_mw"),
            CellMapping(sheet="Inputs", cell="B6", param_name="pre_construction_mw"),
            CellMapping(sheet="Inputs", cell="B7", param_name="announced_mw"),
            CellMapping(sheet="Marginal_CF_Segmentation", cell="C6", param_name="dc_share"),
            CellMapping(sheet="Marginal_CF_Segmentation", cell="C7", param_name="dc_backup_cf_mult"),
            CellMapping(sheet="Marginal_CF_Segmentation", cell="C8", param_name="other_backup_cf_mult"),
        ]

    @property
    def output_mappings(self) -> list[CellMapping]:
        return [
            CellMapping(sheet="Total GW", cell="B13", param_name="conservative_2035_gw"),
            CellMapping(sheet="Total GW", cell="C13", param_name="central_2035_gw"),
            CellMapping(sheet="Total GW", cell="D13", param_name="stretch_2035_gw"),
            CellMapping(sheet="Total GW", cell="E13", param_name="dash_2035_gw"),
            CellMapping(sheet="Total bcfd", cell="B13", param_name="conservative_2035_bcfd"),
            CellMapping(sheet="Total bcfd", cell="C13", param_name="central_2035_bcfd"),
            CellMapping(sheet="Total bcfd", cell="D13", param_name="stretch_2035_bcfd"),
            CellMapping(sheet="Total bcfd", cell="E13", param_name="dash_2035_bcfd"),
        ]

    # -- Validation ----------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        scenario = params.get("build_scenario", "central")
        custom_cap = params.get("custom_build_cap_mw_yr")

        if custom_cap is None and scenario not in BUILD_SCENARIOS:
            errors.append(
                f"'build_scenario' must be one of {list(BUILD_SCENARIOS)} "
                f"or provide 'custom_build_cap_mw_yr'; got '{scenario}'"
            )

        if custom_cap is not None:
            if not isinstance(custom_cap, (int, float)):
                errors.append("'custom_build_cap_mw_yr' must be numeric")
            elif custom_cap <= 0:
                errors.append(f"'custom_build_cap_mw_yr' must be positive; got {custom_cap}")
            elif custom_cap > 100_000:
                warnings.append(
                    f"'custom_build_cap_mw_yr' of {custom_cap:,.0f} MW exceeds "
                    "the historical all-time high (63,975 MW in 2002)"
                )

        for key in ("construction_mw", "pre_construction_mw", "announced_mw"):
            v = params.get(key)
            if v is not None:
                if not isinstance(v, (int, float)):
                    errors.append(f"'{key}' must be numeric")
                elif v < 0:
                    errors.append(f"'{key}' must be non-negative; got {v}")

        dc = params.get("dc_share")
        if dc is not None:
            if not isinstance(dc, (int, float)):
                errors.append("'dc_share' must be numeric")
            elif not 0 <= dc <= 1:
                errors.append(f"'dc_share' must be in [0, 1]; got {dc}")

        years = params.get("projection_years", 10)
        if not isinstance(years, int) or years < 1:
            errors.append(f"'projection_years' must be a positive integer; got {years}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- Translation ---------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Resolve build_scenario to a numeric cap and fill defaults."""
        translated = dict(params)

        if "custom_build_cap_mw_yr" in translated:
            translated["build_cap_mw_yr"] = translated.pop("custom_build_cap_mw_yr")
            translated.setdefault("build_scenario", "custom")
        else:
            scenario = translated.get("build_scenario", "central")
            translated["build_cap_mw_yr"] = BUILD_SCENARIOS.get(
                scenario, BUILD_SCENARIOS["central"]
            )

        translated.setdefault("construction_mw", _DEFAULT_CONSTRUCTION_MW)
        translated.setdefault("pre_construction_mw", _DEFAULT_PRE_CONSTRUCTION_MW)
        translated.setdefault("announced_mw", _DEFAULT_ANNOUNCED_MW)
        translated.setdefault("projection_years", 10)

        # LLM extraction can return floats (``projection_years: 10.0``);
        # the buildout loop uses ``range(projection_years)`` so coerce
        # back to int here.
        py = translated.get("projection_years")
        if py is not None and not isinstance(py, int):
            try:
                translated["projection_years"] = int(round(float(py)))
            except (TypeError, ValueError):
                pass
        return translated

    # -- Execution -----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        if self._config is not None and self._config.use_xlwings:
            return super()._execute_xlwings(inputs)

        return self._execute_python(inputs)

    def _execute_python(self, inputs: dict[str, Any]) -> ModelOutput:
        result = compute_buildout(
            construction_mw=inputs.get("construction_mw", _DEFAULT_CONSTRUCTION_MW),
            pre_construction_mw=inputs.get("pre_construction_mw", _DEFAULT_PRE_CONSTRUCTION_MW),
            announced_mw=inputs.get("announced_mw", _DEFAULT_ANNOUNCED_MW),
            build_cap_mw_yr=inputs.get("build_cap_mw_yr"),
            build_scenario=inputs.get("build_scenario", "central"),
            projection_years=inputs.get("projection_years", 10),
            cf_low=inputs.get("cf_low", CF_PRESETS["low"]),
            cf_mid=inputs.get("cf_mid", CF_PRESETS["mid"]),
            cf_high=inputs.get("cf_high", CF_PRESETS["high"]),
            hr_low=inputs.get("hr_low", HR_PRESETS["low"]),
            hr_mid=inputs.get("hr_mid", HR_PRESETS["mid"]),
            hr_high=inputs.get("hr_high", HR_PRESETS["high"]),
        )

        seg = None
        if inputs.get("include_segmentation", True):
            seg = compute_segmented_burn(
                result.yearly_results,
                dc_share=inputs.get("dc_share", _DEFAULT_DC_SHARE),
                p_prime=inputs.get("p_prime", _PRIME_PRESETS["mid"]["p_prime"]),
                cf_prime=inputs.get("cf_prime", _PRIME_PRESETS["mid"]["cf_prime"]),
                dc_backup_cf_mult=inputs.get("dc_backup_cf_mult", _DEFAULT_DC_BACKUP_CF_MULT),
                other_backup_cf_mult=inputs.get("other_backup_cf_mult", _DEFAULT_OTHER_BACKUP_CF_MULT),
                fleet_avg_cf=inputs.get("cf_mid", CF_PRESETS["mid"]),
                heat_rate=inputs.get("hr_mid", HR_PRESETS["mid"]),
            )
            result.segmented_results = seg

        return self.parse_outputs(result)

    # -- Output parsing ------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw

        if isinstance(raw, GasPowerResult):
            outputs: dict[str, Any] = {
                "build_scenario": raw.build_scenario,
                "build_cap_mw_yr": raw.build_cap_mw_yr,
                "total_pipeline_mw": raw.total_pipeline_mw,
                "total_commissioned_gw": raw.total_commissioned_gw,
                "years_to_clear_backlog": raw.years_to_clear_backlog,
                "by_2030_new_gw": raw.by_2030_new_gw,
                "by_2030_bcf_per_day_mid": raw.by_2030_bcf_per_day_mid,
                "by_2035_new_gw": raw.by_2035_new_gw,
                "by_2035_bcf_per_day_mid": raw.by_2035_bcf_per_day_mid,
                "yearly_results": [yr.model_dump() for yr in raw.yearly_results],
            }
            if raw.segmented_results:
                outputs["segmented_results"] = [
                    s.model_dump() for s in raw.segmented_results
                ]

            return ModelOutput(
                model_id=self.model_id,
                outputs=outputs,
                metadata={"engine": "python", "convergence": "exact"},
                convergence_status="converged",
            )

        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"parse_status": "passthrough"},
        )
