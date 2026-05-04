"""Adapter for the Energy Flux US LNG War Profits Model v1.0.

This Excel workbook calculates windfall profits for US LNG exporters during a
crisis-driven price spike.  The core computation is a netback-based windfall
calculation over a 12-month price trajectory comparing crisis vs. baseline
cargo economics for EU- and Asia-bound cargoes.

Supports two execution modes:
  1. **Python-native** (default): reimplements the spreadsheet formulas in
     Python — portable, fast, fully testable, no Excel required.
  2. **Excel-based**: drives the actual workbook via the ``ExcelAdapter``
     base class (xlwings for full recalculation, openpyxl for cached values).

The workbook lives at:
  ``Models/LNG/Energy-Flux-US-LNG-War-Profits-Model-v1.0 (1).xlsx``
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.excel_adapter import CellMapping, ExcelAdapter, ExcelConfig
from src.models.base import ModelOutput, ValidationResult

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PriceScheduleRow(BaseModel):
    """One month in the 12-month crisis price trajectory."""

    ttf: float = Field(description="TTF price ($/MMBtu)")
    jkm: float = Field(description="JKM price ($/MMBtu)")
    hh: float = Field(description="Henry Hub price ($/MMBtu)")
    freight_eu: float = Field(description="Freight cost to Europe ($/MMBtu)")
    freight_asia: float = Field(description="Freight cost to Asia ($/MMBtu)")


class MonthlyResult(BaseModel):
    """Windfall results for a single month."""

    month: int
    ttf_price: float
    jkm_price: float
    hh_price: float
    freight_eu: float
    freight_asia: float
    ttf_netback: float
    jkm_netback: float
    eu_cargo_profit: float
    asia_cargo_profit: float
    baseline_eu_cargo_profit: float
    baseline_asia_cargo_profit: float
    eu_windfall_per_cargo: float
    asia_windfall_per_cargo: float
    eu_cargoes: float
    asia_cargoes: float
    monthly_windfall: float
    cumulative_windfall: float


class LNGProfitsResult(BaseModel):
    """Complete output from the LNG War Profits calculation."""

    monthly_results: list[MonthlyResult]
    total_windfall_usd: float
    peak_monthly_windfall: float
    peak_month: int
    eu_cargoes_per_month: float
    asia_cargoes_per_month: float
    total_cargoes_per_month: float
    duration_months: int
    baseline_monthly_revenue_usd: float
    average_ttf_netback: float
    average_jkm_netback: float


# ---------------------------------------------------------------------------
# Default price schedule (from the workbook's "Inputs" sheet, rows 21-32)
# ---------------------------------------------------------------------------

DEFAULT_PRICE_SCHEDULE: list[PriceScheduleRow] = [
    PriceScheduleRow(ttf=18.5,  jkm=23.0, hh=3.041, freight_eu=1.30, freight_asia=1.40),
    PriceScheduleRow(ttf=25.0,  jkm=29.0, hh=3.5,   freight_eu=1.55, freight_asia=1.80),
    PriceScheduleRow(ttf=33.0,  jkm=36.0, hh=4.2,   freight_eu=1.85, freight_asia=2.20),
    PriceScheduleRow(ttf=43.0,  jkm=44.0, hh=5.0,   freight_eu=2.20, freight_asia=2.60),
    PriceScheduleRow(ttf=52.0,  jkm=50.0, hh=5.5,   freight_eu=2.50, freight_asia=2.90),
    PriceScheduleRow(ttf=58.0,  jkm=55.0, hh=6.0,   freight_eu=2.70, freight_asia=3.10),
    PriceScheduleRow(ttf=60.0,  jkm=57.0, hh=6.5,   freight_eu=2.80, freight_asia=3.20),
    PriceScheduleRow(ttf=58.0,  jkm=55.0, hh=6.5,   freight_eu=2.70, freight_asia=3.10),
    PriceScheduleRow(ttf=54.0,  jkm=52.0, hh=6.0,   freight_eu=2.50, freight_asia=2.90),
    PriceScheduleRow(ttf=50.0,  jkm=48.0, hh=5.5,   freight_eu=2.30, freight_asia=2.70),
    PriceScheduleRow(ttf=46.0,  jkm=44.0, hh=5.0,   freight_eu=2.10, freight_asia=2.50),
    PriceScheduleRow(ttf=42.0,  jkm=40.0, hh=4.8,   freight_eu=1.90, freight_asia=2.30),
]

# Current market prices (Inputs!B14:B17) — used for the price schedule,
# but NOT as the windfall baseline.
_DEFAULT_SPOT_PRICES = {
    "hh": 3.041,
    "ttf": 16.98,
    "jkm": 21.185,
    "brent": 81.0,
}

# 6-month pre-crisis baseline (Iran Analysis!B5:B13)
# These are computed from AVERAGEIFS on the Historical Data sheet
# covering Sep 1 2025 – Mar 1 2026.  The windfall for each month is
# calculated relative to these historical averages, NOT current spot.
_DEFAULT_BASELINE_CARGO_PROFIT = {
    "eu": 22_130_764,     # $/cargo  (Iran Analysis!B10)
    "asia": 21_588_010,   # $/cargo  (Iran Analysis!B11)
}
_DEFAULT_BASELINE_NETBACK = {
    "ttf": 5.91,   # $/MMBtu  (Iran Analysis!B8)
    "jkm": 5.77,   # $/MMBtu  (Iran Analysis!B9)
}
_DEFAULT_BASELINE_HH = 3.62       # $/MMBtu  (Iran Analysis!B5)
_DEFAULT_BASELINE_FREIGHT = {
    "eu": 0.40,    # $/MMBtu  (Iran Analysis!B12)
    "asia": 0.91,  # $/MMBtu  (Iran Analysis!B13)
}

# Workbook defaults for cost / volume assumptions
_DEFAULT_LIQ_TOLL = 2.10          # $/MMBtu  (Inputs!B35)
_DEFAULT_CARGO_MMBTU = 3_740_000  # MMBtu    (Inputs!B36)
_DEFAULT_CARGO_BCF = 3.3          # Bcf      (Inputs!B37)
_DEFAULT_EXPORT_BCF = 500.0       # Bcf/mo   (Inputs!B45)
_DEFAULT_EU_SHARE = 0.50          #          (Inputs!C45)
_DEFAULT_ASIA_SHARE = 0.37        #          (Inputs!D45)

# Ukraine windfall benchmark ($83.7 B over 12 months)
_UKRAINE_WINDFALL_12MO = 83.7e9


# ---------------------------------------------------------------------------
# Price-schedule generators
# ---------------------------------------------------------------------------

def generate_price_schedule(
    baseline_ttf: float,
    baseline_jkm: float,
    baseline_hh: float,
    peak_ttf: float,
    peak_jkm: float,
    peak_hh: float,
    *,
    peak_month: int = 7,
    months: int = 12,
    floor_fraction: float = 0.40,
    baseline_freight_eu: float = 1.30,
    baseline_freight_asia: float = 1.40,
    peak_freight_eu: float = 2.80,
    peak_freight_asia: float = 3.20,
) -> list[PriceScheduleRow]:
    """Build a spike-and-decline price schedule from peak values.

    The trajectory ramps linearly to *peak_month*, then declines linearly
    toward a floor equal to ``baseline + floor_fraction * (peak - baseline)``
    by month 12.  Freight costs follow the same envelope.
    """
    months = int(round(float(months)))
    peak_month = int(round(float(peak_month)))
    rows: list[PriceScheduleRow] = []
    for m in range(1, months + 1):
        if m <= peak_month:
            w = m / peak_month
        else:
            remaining = months - peak_month
            w = 1.0 - (1.0 - floor_fraction) * (m - peak_month) / remaining

        rows.append(PriceScheduleRow(
            ttf=round(baseline_ttf + w * (peak_ttf - baseline_ttf), 2),
            jkm=round(baseline_jkm + w * (peak_jkm - baseline_jkm), 2),
            hh=round(baseline_hh + w * (peak_hh - baseline_hh), 2),
            freight_eu=round(baseline_freight_eu + w * (peak_freight_eu - baseline_freight_eu), 2),
            freight_asia=round(baseline_freight_asia + w * (peak_freight_asia - baseline_freight_asia), 2),
        ))
    return rows


# ---------------------------------------------------------------------------
# Python calculation engine
# ---------------------------------------------------------------------------

def compute_windfall(
    price_schedule: list[PriceScheduleRow],
    *,
    baseline_eu_cargo_profit: float = _DEFAULT_BASELINE_CARGO_PROFIT["eu"],
    baseline_asia_cargo_profit: float = _DEFAULT_BASELINE_CARGO_PROFIT["asia"],
    liquefaction_toll: float = _DEFAULT_LIQ_TOLL,
    cargo_size_mmbtu: float = _DEFAULT_CARGO_MMBTU,
    cargo_size_bcf: float = _DEFAULT_CARGO_BCF,
    monthly_export_bcf: float = _DEFAULT_EXPORT_BCF,
    eu_share: float = _DEFAULT_EU_SHARE,
    asia_share: float = _DEFAULT_ASIA_SHARE,
    duration_months: int = 12,
) -> LNGProfitsResult:
    """Re-implement the workbook's Iran Analysis calculation in Python.

    Netback formula (mirrors the Excel model exactly):
        ``netback = dest_price - HH * 1.15 - liq_toll - freight``

    The windfall for each month is computed relative to the **6-month
    pre-crisis historical average** cargo profits (Iran Analysis!B10, B11),
    *not* current spot-derived baselines.  This matches the workbook's
    AVERAGEIFS-based baseline methodology.
    """
    total_cargoes = monthly_export_bcf / cargo_size_bcf
    eu_cargoes = total_cargoes * eu_share
    asia_cargoes = total_cargoes * asia_share
    baseline_monthly_rev = (
        baseline_eu_cargo_profit * eu_cargoes
        + baseline_asia_cargo_profit * asia_cargoes
    )

    duration_months = int(round(float(duration_months)))
    n = min(duration_months, len(price_schedule))
    monthly: list[MonthlyResult] = []
    cumulative = 0.0
    peak_windfall = 0.0
    peak_month = 1
    ttf_netback_sum = 0.0
    jkm_netback_sum = 0.0

    for i in range(n):
        ps = price_schedule[i]
        ttf_nb = ps.ttf - ps.hh * 1.15 - liquefaction_toll - ps.freight_eu
        jkm_nb = ps.jkm - ps.hh * 1.15 - liquefaction_toll - ps.freight_asia
        eu_cp = ttf_nb * cargo_size_mmbtu
        asia_cp = jkm_nb * cargo_size_mmbtu
        eu_wpc = eu_cp - baseline_eu_cargo_profit
        asia_wpc = asia_cp - baseline_asia_cargo_profit
        mw = eu_wpc * eu_cargoes + asia_wpc * asia_cargoes
        cumulative += mw

        ttf_netback_sum += ttf_nb
        jkm_netback_sum += jkm_nb

        if mw > peak_windfall:
            peak_windfall = mw
            peak_month = i + 1

        monthly.append(MonthlyResult(
            month=i + 1,
            ttf_price=ps.ttf,
            jkm_price=ps.jkm,
            hh_price=ps.hh,
            freight_eu=ps.freight_eu,
            freight_asia=ps.freight_asia,
            ttf_netback=ttf_nb,
            jkm_netback=jkm_nb,
            eu_cargo_profit=eu_cp,
            asia_cargo_profit=asia_cp,
            baseline_eu_cargo_profit=baseline_eu_cargo_profit,
            baseline_asia_cargo_profit=baseline_asia_cargo_profit,
            eu_windfall_per_cargo=eu_wpc,
            asia_windfall_per_cargo=asia_wpc,
            eu_cargoes=eu_cargoes,
            asia_cargoes=asia_cargoes,
            monthly_windfall=mw,
            cumulative_windfall=cumulative,
        ))

    return LNGProfitsResult(
        monthly_results=monthly,
        total_windfall_usd=cumulative,
        peak_monthly_windfall=peak_windfall,
        peak_month=peak_month,
        eu_cargoes_per_month=eu_cargoes,
        asia_cargoes_per_month=asia_cargoes,
        total_cargoes_per_month=total_cargoes,
        duration_months=n,
        baseline_monthly_revenue_usd=baseline_monthly_rev,
        average_ttf_netback=ttf_netback_sum / n if n else 0,
        average_jkm_netback=jkm_netback_sum / n if n else 0,
    )


# ---------------------------------------------------------------------------
# Excel I/O utilities
# ---------------------------------------------------------------------------

def read_workbook_inputs(workbook_path: str | Path) -> dict[str, Any]:
    """Read current input values from the LNG War Profits workbook.

    Reads both the ``Inputs`` sheet (price schedule, costs, volumes)
    and the ``Iran Analysis`` sheet (6-month pre-crisis baseline cargo
    profits used as the windfall reference point).

    Returns a dict suitable for passing (after modification) to
    ``translate_inputs`` → ``execute``.
    """
    from openpyxl import load_workbook

    wb = load_workbook(str(workbook_path), data_only=True)
    inp = wb["Inputs"]

    spot_prices = {
        "spot_hh": inp["B14"].value,
        "spot_ttf": inp["B15"].value,
        "spot_jkm": inp["B16"].value,
        "spot_brent": inp["B17"].value,
    }

    schedule: list[dict[str, float]] = []
    for row in range(21, 33):
        schedule.append({
            "ttf": inp[f"B{row}"].value,
            "jkm": inp[f"C{row}"].value,
            "hh": inp[f"D{row}"].value,
            "freight_eu": inp[f"E{row}"].value,
            "freight_asia": inp[f"F{row}"].value,
        })

    costs = {
        "liquefaction_toll": inp["B35"].value,
        "cargo_size_mmbtu": inp["B36"].value,
        "cargo_size_bcf": inp["B37"].value,
    }

    volumes = {
        "monthly_export_bcf": inp["B45"].value,
        "eu_share": inp["C45"].value,
        "asia_share": inp["D45"].value,
    }

    # 6-month pre-crisis baseline from Iran Analysis sheet
    iran = wb["Iran Analysis"]
    baseline = {
        "baseline_hh": iran["B5"].value,
        "baseline_ttf_netback": iran["B8"].value,
        "baseline_jkm_netback": iran["B9"].value,
        "baseline_eu_cargo_profit": iran["B10"].value,
        "baseline_asia_cargo_profit": iran["B11"].value,
        "baseline_freight_eu": iran["B12"].value,
        "baseline_freight_asia": iran["B13"].value,
    }

    wb.close()
    return {**spot_prices, "price_schedule": schedule, **costs, **volumes, **baseline}


def write_scenario_workbook(
    source_path: str | Path,
    output_path: str | Path,
    params: dict[str, Any],
) -> Path:
    """Create a copy of the workbook with scenario parameters injected.

    The copy must be opened in Excel (or via xlwings) to recalculate
    formulas after the inputs are overwritten.
    """
    import shutil

    from openpyxl import load_workbook

    output_path = Path(output_path)
    shutil.copy2(str(source_path), str(output_path))

    wb = load_workbook(str(output_path))
    inp = wb["Inputs"]

    simple_mappings: dict[str, str] = {
        "baseline_hh": "B14",
        "baseline_ttf": "B15",
        "baseline_jkm": "B16",
        "baseline_brent": "B17",
        "liquefaction_toll": "B35",
        "cargo_size_mmbtu": "B36",
        "cargo_size_bcf": "B37",
        "monthly_export_bcf": "B45",
        "eu_share": "C45",
        "asia_share": "D45",
    }
    for param, cell in simple_mappings.items():
        if param in params:
            inp[cell] = params[param]

    if "price_schedule" in params:
        sched = params["price_schedule"]
        col_map = {"ttf": "B", "jkm": "C", "hh": "D", "freight_eu": "E", "freight_asia": "F"}
        for i, row_data in enumerate(sched):
            excel_row = 21 + i
            if isinstance(row_data, dict):
                for key, col in col_map.items():
                    if key in row_data:
                        inp[f"{col}{excel_row}"] = row_data[key]
            elif isinstance(row_data, PriceScheduleRow):
                for key, col in col_map.items():
                    inp[f"{col}{excel_row}"] = getattr(row_data, key)

    wb.save(str(output_path))
    wb.close()
    return output_path


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

# All parameters accepted by validate_inputs / translate_inputs
_ACCEPTED_PARAMS: dict[str, str] = {
    "disruption_duration_months": "Duration of crisis in months (1–12)",
    "price_schedule": "Explicit 12-month schedule (list of dicts or PriceScheduleRow)",
    "ttf_peak_price": "Peak TTF price for auto-generated schedule ($/MMBtu)",
    "jkm_peak_price": "Peak JKM price for auto-generated schedule ($/MMBtu)",
    "hh_crisis_price": "Peak HH price for auto-generated schedule ($/MMBtu)",
    "peak_month": "Month at which prices peak (default 7)",
    "monthly_export_bcf": "US LNG export volume (Bcf/month)",
    "eu_share": "Fraction of exports routed to Europe (0–1)",
    "asia_share": "Fraction of exports routed to Asia (0–1)",
    "liquefaction_toll": "Liquefaction cost ($/MMBtu)",
    "cargo_size_mmbtu": "Cargo size in MMBtu",
    "cargo_size_bcf": "Cargo size in Bcf",
    "baseline_eu_cargo_profit": "6-month avg pre-crisis EU cargo profit ($/cargo)",
    "baseline_asia_cargo_profit": "6-month avg pre-crisis Asia cargo profit ($/cargo)",
}


class EnergyFluxLNGProfitsAdapter(ExcelAdapter):
    """Adapter for the Energy Flux US LNG War Profits Model v1.0.

    Accepts either:
      * An explicit 12-month ``price_schedule``, **or**
      * Peak price values (``ttf_peak_price``, ``jkm_peak_price``,
        ``hh_crisis_price``) from which a schedule is auto-generated.

    When an ``ExcelConfig`` is supplied the adapter can also drive the
    actual workbook via xlwings (full recalculation) or openpyxl (cached
    values only).  Without a config the adapter runs in Python-native mode.
    """

    def __init__(self, config: ExcelConfig | None = None) -> None:
        super().__init__(config)

    # -- ModelAdapter metadata -----------------------------------------------

    @property
    def model_id(self) -> str:
        return "energy_flux_lng_profits"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Energy Flux US LNG War Profits Model v1.0: calculates windfall "
            "profits for US LNG exporters under crisis-driven price spikes "
            "using a 12-month netback-based windfall methodology."
        )

    # -- ExcelAdapter mappings (for xlwings / openpyxl mode) -----------------

    @property
    def input_mappings(self) -> list[CellMapping]:
        return [
            CellMapping(sheet="Inputs", cell="B14", param_name="baseline_hh"),
            CellMapping(sheet="Inputs", cell="B15", param_name="baseline_ttf"),
            CellMapping(sheet="Inputs", cell="B16", param_name="baseline_jkm"),
            CellMapping(sheet="Inputs", cell="B17", param_name="baseline_brent"),
            CellMapping(sheet="Inputs", cell="B35", param_name="liquefaction_toll"),
            CellMapping(sheet="Inputs", cell="B36", param_name="cargo_size_mmbtu"),
            CellMapping(sheet="Inputs", cell="B37", param_name="cargo_size_bcf"),
            CellMapping(sheet="Inputs", cell="B45", param_name="monthly_export_bcf"),
            CellMapping(sheet="Inputs", cell="C45", param_name="eu_share"),
            CellMapping(sheet="Inputs", cell="D45", param_name="asia_share"),
        ]

    @property
    def output_mappings(self) -> list[CellMapping]:
        return [
            CellMapping(sheet="Comparison", cell="C6", param_name="total_windfall_12mo"),
            CellMapping(sheet="Comparison", cell="C8", param_name="peak_monthly_windfall"),
            CellMapping(sheet="Comparison", cell="C12", param_name="weeks_to_match_ukraine"),
        ]

    # -- Validation ----------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        has_schedule = "price_schedule" in params
        has_peaks = all(k in params for k in ("ttf_peak_price", "jkm_peak_price", "hh_crisis_price"))

        if not has_schedule and not has_peaks:
            errors.append(
                "Provide either 'price_schedule' (12 rows) or all of "
                "'ttf_peak_price', 'jkm_peak_price', 'hh_crisis_price'."
            )

        dur = params.get("disruption_duration_months", 12)
        if not isinstance(dur, (int, float)):
            errors.append("'disruption_duration_months' must be numeric")
        elif dur < 1 or dur > 12:
            errors.append(f"'disruption_duration_months' must be 1–12; got {dur}")

        if has_schedule:
            sched = params["price_schedule"]
            if not isinstance(sched, list) or len(sched) < 1:
                errors.append("'price_schedule' must be a non-empty list of rows")
            elif len(sched) < dur:
                warnings.append(
                    f"'price_schedule' has {len(sched)} rows but "
                    f"'disruption_duration_months' is {dur}"
                )

        if has_peaks:
            for key in ("ttf_peak_price", "jkm_peak_price", "hh_crisis_price"):
                v = params.get(key)
                if v is not None and not isinstance(v, (int, float)):
                    errors.append(f"'{key}' must be numeric")
                elif v is not None and v < 0:
                    errors.append(f"'{key}' must be non-negative; got {v}")

        eu = params.get("eu_share", _DEFAULT_EU_SHARE)
        asia = params.get("asia_share", _DEFAULT_ASIA_SHARE)
        if isinstance(eu, (int, float)) and isinstance(asia, (int, float)):
            if eu + asia > 1.0:
                errors.append(
                    f"'eu_share' + 'asia_share' must not exceed 1.0; "
                    f"got {eu} + {asia} = {eu + asia}"
                )

        vol = params.get("monthly_export_bcf", _DEFAULT_EXPORT_BCF)
        if isinstance(vol, (int, float)) and vol <= 0:
            errors.append(f"'monthly_export_bcf' must be positive; got {vol}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- Translation ---------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert high-level scenario params into the full calculation input set.

        If ``price_schedule`` is missing, one is generated from the peak-price
        parameters using :func:`generate_price_schedule`.
        """
        translated = dict(params)

        # LLM-extracted parameters often arrive as floats (e.g.
        # ``disruption_duration_months: 4.0``); coerce the integer-typed
        # fields here so downstream ``range()`` / indexing operations don't
        # raise ``TypeError: 'float' object cannot be interpreted as an integer``.
        for _int_field in ("disruption_duration_months", "peak_month"):
            if _int_field in translated and translated[_int_field] is not None:
                try:
                    translated[_int_field] = int(round(float(translated[_int_field])))
                except (TypeError, ValueError):
                    pass

        if "price_schedule" not in translated:
            translated["price_schedule"] = generate_price_schedule(
                baseline_ttf=_DEFAULT_SPOT_PRICES["ttf"],
                baseline_jkm=_DEFAULT_SPOT_PRICES["jkm"],
                baseline_hh=_DEFAULT_SPOT_PRICES["hh"],
                peak_ttf=translated["ttf_peak_price"],
                peak_jkm=translated["jkm_peak_price"],
                peak_hh=translated["hh_crisis_price"],
                peak_month=translated.get("peak_month", 7),
            )
        else:
            raw = translated["price_schedule"]
            coerced: list[PriceScheduleRow] = []
            for row in raw:
                if isinstance(row, PriceScheduleRow):
                    coerced.append(row)
                elif isinstance(row, dict):
                    coerced.append(PriceScheduleRow(**row))
                else:
                    raise TypeError(f"Unexpected price_schedule row type: {type(row)}")
            translated["price_schedule"] = coerced

        return translated

    # -- Execution -----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Run the windfall calculation.

        Uses the Python engine by default.  If an ``ExcelConfig`` is set *and*
        ``use_xlwings`` is True, delegates to the parent ``ExcelAdapter``
        (which drives the actual workbook through Excel COM automation).
        """
        if self._config is not None and self._config.use_xlwings:
            return self._execute_via_excel(inputs)

        return self._execute_python(inputs)

    def _execute_python(self, inputs: dict[str, Any]) -> ModelOutput:
        result = compute_windfall(
            price_schedule=inputs["price_schedule"],
            baseline_eu_cargo_profit=inputs.get(
                "baseline_eu_cargo_profit", _DEFAULT_BASELINE_CARGO_PROFIT["eu"]
            ),
            baseline_asia_cargo_profit=inputs.get(
                "baseline_asia_cargo_profit", _DEFAULT_BASELINE_CARGO_PROFIT["asia"]
            ),
            liquefaction_toll=inputs.get("liquefaction_toll", _DEFAULT_LIQ_TOLL),
            cargo_size_mmbtu=inputs.get("cargo_size_mmbtu", _DEFAULT_CARGO_MMBTU),
            cargo_size_bcf=inputs.get("cargo_size_bcf", _DEFAULT_CARGO_BCF),
            monthly_export_bcf=inputs.get("monthly_export_bcf", _DEFAULT_EXPORT_BCF),
            eu_share=inputs.get("eu_share", _DEFAULT_EU_SHARE),
            asia_share=inputs.get("asia_share", _DEFAULT_ASIA_SHARE),
            duration_months=inputs.get("disruption_duration_months", 12),
        )
        return self.parse_outputs(result)

    def _execute_via_excel(self, inputs: dict[str, Any]) -> ModelOutput:
        """Drive the actual workbook via xlwings for full recalculation.

        Injects both single-cell parameters *and* the 12-month price schedule
        range, then recalculates and reads output cells.
        """
        import shutil
        import tempfile

        try:
            import xlwings as xw
        except ImportError as exc:
            raise ImportError(
                "xlwings is required for Excel-based execution. "
                "Install with: pip install xlwings"
            ) from exc

        config = self.excel_config
        tmp_dir = Path(tempfile.mkdtemp(prefix="lng_profits_"))
        workbook_copy = tmp_dir / config.workbook_path.name
        shutil.copy2(str(config.workbook_path), str(workbook_copy))

        app = xw.App(visible=False)
        try:
            wb = app.books.open(str(workbook_copy))
            inp_sheet = wb.sheets["Inputs"]

            for mapping in self.input_mappings:
                if mapping.param_name in inputs:
                    inp_sheet.range(mapping.cell).value = inputs[mapping.param_name]

            if "price_schedule" in inputs:
                sched = inputs["price_schedule"]
                for i, row in enumerate(sched):
                    excel_row = 21 + i
                    if isinstance(row, PriceScheduleRow):
                        row = row.model_dump()
                    inp_sheet.range(f"B{excel_row}").value = row["ttf"]
                    inp_sheet.range(f"C{excel_row}").value = row["jkm"]
                    inp_sheet.range(f"D{excel_row}").value = row["hh"]
                    inp_sheet.range(f"E{excel_row}").value = row["freight_eu"]
                    inp_sheet.range(f"F{excel_row}").value = row["freight_asia"]

            app.calculate()

            results: dict[str, Any] = {}
            for mapping in self.output_mappings:
                results[mapping.param_name] = (
                    wb.sheets[mapping.sheet].range(mapping.cell).value
                )

            iran = wb.sheets["Iran Analysis"]
            monthly_windfalls = []
            for r in range(17, 29):
                val = iran.range(f"H{r}").value
                if val is not None:
                    monthly_windfalls.append(val)
            results["monthly_windfalls"] = monthly_windfalls

            wb.save()
            return ModelOutput(
                model_id=self.model_id,
                outputs=results,
                metadata={
                    "engine": "xlwings",
                    "workbook_copy": str(workbook_copy),
                },
            )
        finally:
            wb.close()
            app.quit()

    # -- Output parsing ------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw

        if isinstance(raw, LNGProfitsResult):
            outputs = {
                "total_windfall_usd": raw.total_windfall_usd,
                "peak_monthly_windfall": raw.peak_monthly_windfall,
                "peak_month": raw.peak_month,
                "duration_months": raw.duration_months,
                "eu_cargoes_per_month": raw.eu_cargoes_per_month,
                "asia_cargoes_per_month": raw.asia_cargoes_per_month,
                "total_cargoes_per_month": raw.total_cargoes_per_month,
                "baseline_monthly_revenue_usd": raw.baseline_monthly_revenue_usd,
                "average_ttf_netback": raw.average_ttf_netback,
                "average_jkm_netback": raw.average_jkm_netback,
                "monthly_results": [m.model_dump() for m in raw.monthly_results],
            }

            weeks = None
            if raw.total_windfall_usd > 0:
                avg_weekly = raw.total_windfall_usd / (raw.duration_months * 4.333)
                if avg_weekly > 0:
                    weeks = _UKRAINE_WINDFALL_12MO / avg_weekly
            outputs["weeks_to_match_ukraine_windfall"] = weeks

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
