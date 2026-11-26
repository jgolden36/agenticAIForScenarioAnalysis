"""MAMAdapter — EIA Macroeconomic Activity Module (standalone macro projections).

The Macroeconomic Activity Module (MAM) is the EViews-based macroeconomic
component of NEMS, derived from the IHS Markit / S&P Global "Macro
Forecasts of US Economy" model. EIA documents the AEO 2025 release of MAM
in ``Models/General Equilibrium/EIA/MAM_AEO2025.pdf``.

Standalone use of MAM is rare: in production it is run inside the NEMS
feedback loop. This adapter provides a *thin* Python entry point that
serves two narrower purposes:

1. **AEO ingestion (default)** — read the macro tables EIA publishes
   alongside each AEO release (Tables 19/20 in AEO2025) so the pipeline
   can compare scenario-level commodity shocks against EIA's published
   reference macro path without driving NEMS end-to-end.

2. **EViews subprocess (optional)** — invoke ``EViews.exe -r mam_main.prg``
   on a Windows host with a licensed EViews 13+ installation when the
   analyst wants a live MAM run with custom oil/gas price paths.

Both modes return the same standardized output schema so synthesis logic
can compare MAM's macro projections to NEMS, OpenCGE, PyCGE, and
MIRAGRODEP without branching on execution mode.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import (
    ModelAdapter,
    ModelOutput,
    ResourceRequirements,
    ValidationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class MAMConfig(BaseModel):
    """Configuration for the MAM adapter."""

    mode: Literal["aeo_ingestion", "eviews_subprocess"] = Field(
        default="aeo_ingestion",
        description="Execution mode",
    )

    # --- AEO ingestion mode ---
    aeo_macro_xlsx_path: Path | None = Field(
        default=None,
        description=(
            "Path to the AEO macro tables XLSX (e.g., 'AEO2025_Tables_19_20.xlsx'). "
            "Required for aeo_ingestion mode."
        ),
    )
    aeo_year: int = Field(
        default=2025,
        description="AEO release year (matches the file naming and table structure)",
    )
    reference_year: int = Field(
        default=2026,
        description=(
            "Calendar year whose values are reported as headline scalars "
            "(the crisis year). Year-on-year growth rates use reference_year-1."
        ),
    )
    scenario_sheet_mapping: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps pipeline scenario IDs to AEO XLSX sheet names. "
            "E.g. {'baseline': 'Reference Case', 'scenario_a': 'High Oil Price'}"
        ),
    )

    # --- EViews subprocess mode ---
    eviews_executable: Path | None = Field(
        default=None,
        description="Path to EViews.exe (required for eviews_subprocess mode)",
    )
    mam_program_dir: Path | None = Field(
        default=None,
        description=(
            "Directory containing mam_main.prg and the MAM workspace files "
            "(required for eviews_subprocess mode)"
        ),
    )
    eviews_main_program: str = Field(
        default="mam_main.prg",
        description="MAM EViews program entry point",
    )
    timeout_seconds: int = Field(
        default=3600,
        description="EViews subprocess timeout (default 1 hour)",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# AEO Table 20 ("Macroeconomic Indicators") rows, keyed by the EIA series
# key in column A (stable across AEO2021-AEO2026 releases). Column B holds
# the indented row label; the year columns follow and the last column is
# the compound growth rate, which is NOT a year value.
#
# NOTE: the legacy URL .../aeo/excel/aeotab_19.xlsx (with underscore)
# serves AEO2021 Table 19 (CO2 emissions by end use). That file is what
# the cluster job ingested before November 2026, so MAM's "completed"
# cells on runs 20260504_222710 et al. contained no macro data. The AEO2025
# reference-case Table 20 is
# https://www.eia.gov/outlooks/archive/aeo25/excel/aeotab20.xlsx.
AEO_TABLE20_SERIES: dict[str, str] = {
    "MEI000:ba_RealGrossDome": "real_gdp_bn_2012usd",
    "MEI000:ba_RealConsumpti": "real_consumption_bn_2012usd",
    "MEI000:ba_RealInvestmen": "real_business_fixed_investment_bn_2012usd",
    "MEI000:ba_RealGovernmen": "real_government_spending_bn_2012usd",
    "MEI000:ba_RealExports": "real_exports_bn_2012usd",
    "MEI000:ba_RealImports": "real_imports_bn_2012usd",
    "MEI000:da_GDPChain-Type": "gdp_price_index",
    "MEI000:da_ConsumerPrice": "cpi_all_urban_index",
    "MEI000:da_ConEnCom&Serv": "cpi_energy_index",
    "MEI000:da_FuelandPower": "wpi_fuel_and_power_index",
    "MEI000:ea_FederalFundsR": "federal_funds_rate_pct",
    "MEI000:ea_10-YearTreasu": "treasury_10y_pct",
    "MEI000:ja_Manufacturing": "manufacturing_shipments_bn_2012usd",
    "MEI000:ja_EnergyIntensi": "energy_intensive_shipments_bn_2012usd",
    "MEI000:ka_Employment,No": "nonfarm_employment_millions",
    "MEI000:ka_Employment,Ma": "manufacturing_employment_millions",
    "MEI000:ka_LaborForce": "labor_force_millions",
    "MEI000:fa_UnemploymentR": "unemployment_rate_pct",
    "MEI000:ba_RealDisposabl": "real_disposable_income_bn_2012usd",
}

# Label fallback (normalised: lower case, whitespace collapsed) for files
# whose series keys are missing.
AEO_TABLE20_LABELS: dict[str, str] = {
    "real gross domestic product": "real_gdp_bn_2012usd",
    "real consumption": "real_consumption_bn_2012usd",
    "real business fixed investment": "real_business_fixed_investment_bn_2012usd",
    "real government spending": "real_government_spending_bn_2012usd",
    "real exports": "real_exports_bn_2012usd",
    "real imports": "real_imports_bn_2012usd",
    "all-urban": "cpi_all_urban_index",
    "federal funds rate": "federal_funds_rate_pct",
    "10-year treasury note": "treasury_10y_pct",
    "employment, nonfarm": "nonfarm_employment_millions",
    "unemployment rate (percentage)": "unemployment_rate_pct",
    "unemployment rate (percent)": "unemployment_rate_pct",
    "real disposable personal income": "real_disposable_income_bn_2012usd",
}

# Backwards-compatible name (older code imported it).
AEO_VARIABLE_MAPPING = AEO_TABLE20_SERIES


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class MAMAdapter(ModelAdapter):
    """Adapter for the EIA Macroeconomic Activity Module (MAM).

    Default mode is ``aeo_ingestion`` — reads pre-computed AEO macro
    tables from XLSX and standardizes them into the pipeline schema. The
    ``eviews_subprocess`` mode invokes EViews on a Windows host with a
    licensed installation; it is wired but documented as requiring
    Windows + EViews 13+.
    """

    def __init__(self, config: MAMConfig | None = None) -> None:
        self._config = config or MAMConfig()

    # -- Identity --------------------------------------------------------

    @property
    def model_id(self) -> str:
        return "mam"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.SHORT_RUN_MACRO

    @property
    def description(self) -> str:
        return (
            "MAM (EIA Macroeconomic Activity Module): standalone macroeconomic "
            "projections derived from the IHS Markit / S&P Global U.S. macro "
            "model used inside NEMS. Default mode reads pre-computed AEO macro "
            "tables (Tables 19/20). Optional eviews_subprocess mode drives a "
            "live MAM run via EViews on a Windows host with EViews 13+."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=1,
            memory_gb=2.0,
            supports_multi_threading=False,
            max_threads=1,
            prefers_process_isolation=False,
        )

    # -- Validation ------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if "scenario_id" not in params:
            errors.append("Missing required parameter: 'scenario_id'")

        mode = self._config.mode
        if mode == "aeo_ingestion":
            self._validate_ingestion(params, errors, warnings)
        elif mode == "eviews_subprocess":
            self._validate_eviews(params, errors, warnings)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _validate_ingestion(
        self, params: dict[str, Any], errors: list[str], warnings: list[str],
    ) -> None:
        # Missing XLSX is a vendoring gap, not a malformed input. Surface
        # it as a warning so validate_inputs returns valid=True; the
        # actual execute() path raises NotImplementedError instead, which
        # the SLURM runner classifies as SKIPPED rather than FAILED.
        xlsx = self._config.aeo_macro_xlsx_path
        if xlsx is None:
            warnings.append(
                "MAMConfig.aeo_macro_xlsx_path is not set; MAM will be SKIPPED. "
                "Point it at the AEO macro tables XLSX (e.g., 'AEO2025_Tables_19_20.xlsx') "
                "or set HORMUZ_MAM_AEO_XLSX_PATH."
            )
            return
        if not Path(xlsx).exists():
            warnings.append(
                f"AEO macro XLSX not found at {xlsx}; MAM will be SKIPPED."
            )
            return

        sid = params.get("scenario_id")
        mapping = self._config.scenario_sheet_mapping
        if mapping and sid is not None and sid not in mapping:
            available = ", ".join(sorted(mapping.keys()))
            warnings.append(
                f"scenario_id '{sid}' is not in scenario_sheet_mapping "
                f"(known: {available}); will fall back to the Reference Case sheet."
            )

    def _validate_eviews(
        self, params: dict[str, Any], errors: list[str], warnings: list[str],
    ) -> None:
        if self._config.eviews_executable is None:
            errors.append(
                "MAMConfig.eviews_executable is required for eviews_subprocess mode."
            )
        elif not Path(self._config.eviews_executable).exists():
            errors.append(
                f"EViews executable not found at {self._config.eviews_executable}"
            )
        if self._config.mam_program_dir is None:
            errors.append(
                "MAMConfig.mam_program_dir is required for eviews_subprocess mode."
            )
        elif not Path(self._config.mam_program_dir).exists():
            errors.append(
                f"mam_program_dir does not exist: {self._config.mam_program_dir}"
            )
        else:
            entry = Path(self._config.mam_program_dir) / self._config.eviews_main_program
            if not entry.exists():
                errors.append(
                    f"MAM EViews entry program not found: {entry}"
                )

    # -- Input translation -----------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        scenario_id = params.get("scenario_id", "default")

        if self._config.mode == "aeo_ingestion":
            sheet = self._config.scenario_sheet_mapping.get(
                scenario_id, "Reference Case"
            )
            return {
                "mode": "aeo_ingestion",
                "scenario_id": scenario_id,
                "xlsx_path": str(self._config.aeo_macro_xlsx_path),
                "sheet_name": sheet,
                "aeo_year": self._config.aeo_year,
                "reference_year": self._config.reference_year,
                # Ingestion returns EIA's published path; scenario shocks
                # (including forwarded ones) are recorded as ignored.
                "ignored_shock_inputs": sorted(
                    k for k in params
                    if k not in ("scenario_id",) and not k.startswith("_")
                ),
            }

        # EViews subprocess
        return {
            "mode": "eviews_subprocess",
            "scenario_id": scenario_id,
            "eviews_executable": str(self._config.eviews_executable),
            "mam_program_dir": str(self._config.mam_program_dir),
            "main_program": self._config.eviews_main_program,
            "oil_price_path": params.get("oil_price_path"),
            "natural_gas_price_path": params.get("natural_gas_price_path"),
            "disruption_duration_months": params.get("disruption_duration_months"),
            "timeout_seconds": self._config.timeout_seconds,
        }

    # -- Execution -------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        mode = inputs["mode"]
        if mode == "aeo_ingestion":
            return self._execute_ingestion(inputs)
        if mode == "eviews_subprocess":
            return self._execute_eviews(inputs)
        raise ValueError(f"Unknown MAM execution mode: {mode}")

    # --- AEO ingestion --------------------------------------------------

    def _execute_ingestion(self, inputs: dict[str, Any]) -> ModelOutput:
        """Parse AEO macro tables (XLSX) and standardize the variables."""
        xlsx_str = inputs.get("xlsx_path")
        if xlsx_str in (None, "None", "") or not Path(xlsx_str).exists():
            # NotImplementedError → SKIPPED in the SLURM runner. Real
            # execution requires the AEO XLSX to be vendored, which is a
            # data-availability gap rather than a code defect.
            raise NotImplementedError(
                "MAM aeo_ingestion mode requires MAMConfig.aeo_macro_xlsx_path "
                "to point at an existing AEO macro tables XLSX. Vendor "
                "AEO2025_Tables_19_20.xlsx under data/eia/ (the SLURM "
                "driver auto-downloads it when HORMUZ_AUTO_VENDOR=1) or set "
                "HORMUZ_MAM_AEO_XLSX_PATH."
            )
        xlsx_path = Path(xlsx_str)
        sheet_name = inputs["sheet_name"]

        try:
            import openpyxl  # noqa: F401  (used dynamically below)
        except ImportError as exc:
            raise NotImplementedError(
                "MAMAdapter aeo_ingestion mode requires openpyxl. "
                "Install with: pip install -e .[adapters]"
            ) from exc

        rows = self._read_xlsx_sheet(xlsx_path, sheet_name)
        table = self._describe_aeo_table(rows)
        if table["table_number"] != 20:
            # A wrong file (e.g. the AEO2021 Table 19 CO2 workbook the old
            # vendoring URL served) must not produce a "completed" cell
            # with no macro data in it.
            raise ValueError(
                f"{xlsx_path} is not AEO Table 20 (Macroeconomic Indicators): "
                f"found table title {table['title']!r}, report {table['report']!r}. "
                "Download https://www.eia.gov/outlooks/archive/aeo25/excel/aeotab20.xlsx."
            )
        outputs = self._standardize_aeo_rows(
            rows, reference_year=int(inputs.get("reference_year") or 2026)
        )
        if not any(k in outputs for k in AEO_TABLE20_SERIES.values()):
            raise ValueError(f"No Table 20 series recognised in {xlsx_path}")
        outputs["_source_xlsx"] = str(xlsx_path)
        outputs["_source_sheet"] = sheet_name
        outputs["_aeo_year"] = inputs.get("aeo_year")
        outputs["_aeo_report"] = table["report"]
        outputs["_aeo_scenario"] = table["scenario"]
        outputs["_baseline_only"] = True
        outputs["_note"] = (
            "Published EIA AEO reference-case macro path. It does not respond "
            "to the scenario's shocks; use it as the no-crisis baseline."
        )
        if inputs.get("ignored_shock_inputs"):
            outputs["_ignored_shock_inputs"] = list(inputs["ignored_shock_inputs"])
        if table["report"] and str(inputs.get("aeo_year")) not in str(table["report"]):
            # e.g. the legacy .../aeo/excel/aeotab_20.xlsx URL serves AEO2021.
            raise ValueError(
                f"{xlsx_path} is from {table['report']!r}, but MAMConfig.aeo_year is "
                f"{inputs.get('aeo_year')}. Use the matching edition's Table 20."
            )

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="pre_computed",
            metadata={
                "mode": "aeo_ingestion",
                "scenario_id": inputs.get("scenario_id"),
                "xlsx_path": str(xlsx_path),
                "sheet_name": sheet_name,
            },
        )

    @staticmethod
    def _read_xlsx_sheet(
        xlsx_path: Path, sheet_name: str,
    ) -> list[list[Any]]:
        """Read an XLSX worksheet into a list-of-rows."""
        from openpyxl import load_workbook

        wb = load_workbook(str(xlsx_path), data_only=True, read_only=True)
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            # Fallback to the first sheet
            ws = wb[wb.sheetnames[0]]
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        wb.close()
        return rows

    @staticmethod
    def _describe_aeo_table(rows: list[list[Any]]) -> dict[str, Any]:
        """Read the table number, title, report and scenario from the header block."""
        import re

        info: dict[str, Any] = {"table_number": None, "title": None, "report": None, "scenario": None}
        for row in rows[:20]:
            cells = [c for c in row if c is not None]
            for j, c in enumerate(row):
                if not isinstance(c, str):
                    continue
                s = c.strip()
                if info["table_number"] is None:
                    m = re.match(r"^(\d{1,3})\.\s+(\S.*)$", s)
                    if m:
                        info["table_number"] = int(m.group(1))
                        info["title"] = m.group(2).strip()
                nxt = row[j + 1] if j + 1 < len(row) else None
                if s == "Report" and isinstance(nxt, str):
                    info["report"] = nxt.strip()
                if s == "Scenario" and isinstance(nxt, str):
                    info["scenario"] = nxt.strip()
            del cells
        return info

    @staticmethod
    def _norm_label(s: str) -> str:
        return " ".join(str(s).strip().lower().split())

    @classmethod
    def _standardize_aeo_rows(
        cls, rows: list[list[Any]], reference_year: int = 2026,
    ) -> dict[str, Any]:
        """Parse AEO Table 20 rows into year-aligned paths and headline scalars.

        Layout (AEO2021-AEO2026): column A = EIA series key
        (``MEI000:ba_RealGrossDome``), column B = indented label, then one
        column per year, then a compound-growth column. Values are aligned
        to the year header by column index, so the growth column and blank
        cells never enter a path.

        For each recognised series ``k`` the output carries ``k`` (list of
        values in year order) and ``k_by_year`` ({year: value}). Headline
        scalars for the reference year:
        ``real_gdp_bn_usd`` (billion 2012 USD), ``gdp_growth_pct``,
        ``cpi_inflation_pct`` (all-urban CPI, y/y), ``unemployment_rate_pct``,
        ``federal_funds_rate_pct``.
        """
        if not rows:
            return {}

        header_row_idx = None
        year_cols: dict[int, int] = {}
        for i, row in enumerate(rows[:40]):
            cols = {
                j: int(c) for j, c in enumerate(row)
                if isinstance(c, (int, float)) and not isinstance(c, bool)
                and float(c).is_integer() and 2000 <= int(c) <= 2100
            }
            if len(cols) >= 5:
                header_row_idx, year_cols = i, cols
                break
        if header_row_idx is None:
            return {"_years": [], "_parse_error": "no year header row found"}

        years = [year_cols[j] for j in sorted(year_cols)]
        out: dict[str, Any] = {"_years": years}
        unmapped: list[str] = []

        for row in rows[header_row_idx + 1:]:
            if not row:
                continue
            series = str(row[0]).strip() if row[0] is not None else ""
            label = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            std_key = AEO_TABLE20_SERIES.get(series) or AEO_TABLE20_LABELS.get(cls._norm_label(label))
            if std_key is None:
                if series:
                    unmapped.append(f"{series} | {label}")
                continue
            by_year: dict[int, float] = {}
            for j, yr in year_cols.items():
                if j >= len(row):
                    continue
                cell = row[j]
                if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                    by_year[yr] = float(cell)
            if not by_year:
                continue
            out[std_key] = [by_year[y] for y in years if y in by_year]
            out[f"{std_key}_by_year"] = {str(y): v for y, v in sorted(by_year.items())}

        def _level(key: str, yr: int) -> float | None:
            return (out.get(f"{key}_by_year") or {}).get(str(yr))

        def _growth(key: str) -> float | None:
            cur, prev = _level(key, reference_year), _level(key, reference_year - 1)
            if cur is None or prev in (None, 0):
                return None
            return round((cur / prev - 1.0) * 100.0, 4)

        headline = {
            "real_gdp_bn_usd": _level("real_gdp_bn_2012usd", reference_year),
            "gdp_growth_pct": _growth("real_gdp_bn_2012usd"),
            "cpi_inflation_pct": _growth("cpi_all_urban_index"),
            "unemployment_rate_pct": _level("unemployment_rate_pct", reference_year),
            "federal_funds_rate_pct": _level("federal_funds_rate_pct", reference_year),
            "treasury_10y_pct": _level("treasury_10y_pct", reference_year),
            "real_consumption_growth_pct": _growth("real_consumption_bn_2012usd"),
            "nonfarm_employment_millions": _level("nonfarm_employment_millions", reference_year),
        }
        for k, v in headline.items():
            if v is not None:
                out[k] = v
        out["_reference_year"] = reference_year
        out["_units"] = {
            "real_gdp_bn_usd": "billion 2012 chain-weighted USD",
            "gdp_growth_pct": "percent, year on year",
            "cpi_inflation_pct": "percent, year on year (CPI all-urban)",
        }
        if unmapped:
            out["_unmapped_aeo_labels"] = unmapped[:50]
        return out

    # --- EViews subprocess ---------------------------------------------

    def _execute_eviews(self, inputs: dict[str, Any]) -> ModelOutput:
        """Invoke EViews to drive a live MAM run."""
        eviews = Path(inputs["eviews_executable"])
        program_dir = Path(inputs["mam_program_dir"])
        program = inputs["main_program"]
        timeout = inputs.get("timeout_seconds", self._config.timeout_seconds)

        # Persist the shock-path overrides for the EViews program to read.
        shock_dump = {
            "scenario_id": inputs.get("scenario_id"),
            "oil_price_path": inputs.get("oil_price_path"),
            "natural_gas_price_path": inputs.get("natural_gas_price_path"),
            "disruption_duration_months": inputs.get("disruption_duration_months"),
        }
        shock_path = program_dir / "pipeline_shocks.json"
        shock_path.write_text(json.dumps(shock_dump, default=str), encoding="utf-8")

        cmd = [str(eviews), "-r", str(program_dir / program)]

        env = {**os.environ}

        start = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(program_dir),
            env=env,
        )
        elapsed = time.time() - start

        if proc.returncode != 0:
            raise RuntimeError(
                f"MAM EViews run failed (rc={proc.returncode}) after {elapsed:.0f}s.\n"
                f"stderr tail:\n{(proc.stderr or '')[-2000:]}\n"
                f"stdout tail:\n{(proc.stdout or '')[-2000:]}"
            )

        # MAM EViews program is expected to emit a JSON results file alongside
        # pipeline_shocks.json (convention: pipeline_results.json).
        results_path = program_dir / "pipeline_results.json"
        if not results_path.exists():
            raise FileNotFoundError(
                f"Expected MAM results at {results_path} but it was not created. "
                f"stdout tail: {(proc.stdout or '')[-500:]}"
            )

        try:
            outputs = json.loads(results_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"MAM EViews results file at {results_path} is not valid JSON: {exc}"
            ) from exc

        if not isinstance(outputs, dict):
            outputs = {"raw": outputs}

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="completed",
            metadata={
                "mode": "eviews_subprocess",
                "scenario_id": inputs.get("scenario_id"),
                "elapsed_seconds": elapsed,
                "results_path": str(results_path),
            },
        )

    # -- Output parsing --------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"mode": self._config.mode},
        )
