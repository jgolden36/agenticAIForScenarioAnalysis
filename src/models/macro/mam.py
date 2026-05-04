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

# AEO Tables 19 (macro reference) and 20 (macro alternative cases) variable
# names normalised into pipeline-standard keys.
AEO_VARIABLE_MAPPING: dict[str, str] = {
    # AEO label                      -> pipeline standard key
    "Real GDP (billion 2017 dollars)":          "gdp_real_billion_usd",
    "Real GDP growth rate (percent)":           "gdp_growth_pct",
    "Consumer Price Index, all urban":          "cpi_index",
    "CPI inflation (percent)":                  "cpi_inflation_pct",
    "Unemployment rate (percent)":              "unemployment_rate_pct",
    "Industrial production index":              "industrial_production_index",
    "Real disposable personal income":          "disposable_income_real",
    "Real disposable income growth (percent)":  "disposable_income_growth_pct",
    "Federal funds rate (percent)":             "federal_funds_rate_pct",
    "3-month Treasury bill rate (percent)":     "interest_rate_3m",
    "10-year Treasury note rate (percent)":     "interest_rate_10y",
    "Population (millions)":                    "population_millions",
    "Total non-farm employment (millions)":     "non_farm_employment_millions",
    "Real consumption expenditures":            "real_consumption",
    "Real fixed investment":                    "real_investment",
    "Real exports":                             "real_exports",
    "Real imports":                             "real_imports",
}


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
        outputs = self._standardize_aeo_rows(rows)
        outputs["_source_xlsx"] = str(xlsx_path)
        outputs["_source_sheet"] = sheet_name
        outputs["_aeo_year"] = inputs.get("aeo_year")

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
    def _standardize_aeo_rows(rows: list[list[Any]]) -> dict[str, Any]:
        """Match AEO row labels against AEO_VARIABLE_MAPPING.

        AEO macro tables typically have:
            row 0..k: title / header rows (years across columns)
            row k+1..N: one variable per row, with the AEO label in column 0.
        """
        if not rows:
            return {}

        # Find the header row that contains year integers.
        header_row_idx = 0
        years: list[int] = []
        for i, row in enumerate(rows[:30]):
            year_cells = [c for c in row if isinstance(c, int) and 2000 <= c <= 2100]
            if len(year_cells) >= 5:
                header_row_idx = i
                years = year_cells
                break

        out: dict[str, Any] = {"_years": years}
        unmapped: list[str] = []

        for row in rows[header_row_idx + 1:]:
            if not row or row[0] is None:
                continue
            label = str(row[0]).strip()
            std_key = AEO_VARIABLE_MAPPING.get(label)
            if std_key is None:
                unmapped.append(label)
                continue

            values: list[float] = []
            for cell in row[1:]:
                if cell is None or cell == "":
                    continue
                try:
                    values.append(float(cell))
                except (TypeError, ValueError):
                    continue

            if not values:
                continue

            # Store both the path and a year-1 scalar for cross-model consistency.
            out[std_key] = values
            if len(values) > 0:
                out[f"{std_key}_year1"] = values[0]

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
