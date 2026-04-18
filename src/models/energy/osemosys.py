"""OSeMOSYSAdapter — Open Source Energy Modelling System integration.

Drives an OSeMOSYS (GNU MathProg) model end-to-end through the standard
``otoole`` → ``glpsol`` → ``otoole`` pipeline:

    1. Materialize a per-scenario working copy of the baseline OSeMOSYS
       data (CSVs, datafile, or XLSX) under a scratch directory.
    2. Apply pipeline-derived shocks to the relevant CSVs (fuel
       availability, capital cost multipliers, exogenous fuel price
       paths, etc.).
    3. Run ``otoole convert <input_format> datafile <inputs> <out.txt>``
       to produce a GLPK MathProg datafile.
    4. Run ``glpsol -m OSeMOSYS.txt -d scenario.txt -w solution.sol``
       (or ``--out`` for plain text) to solve the LP.
    5. Run ``otoole results sol <solution.sol> csv <results_dir>`` to
       parse the GLPK solution into per-variable result CSVs.
    6. Read ``NewCapacity``, ``ProductionByTechnology``, and
       ``TotalDiscountedCost`` into the standardized ``ModelOutput``.

Real implementation requirements:
    - The OSeMOSYS source repo vendored at ``Models/Energy/OSeMOSYS/``
      (provides ``OSeMOSYS.txt`` MathProg formulation).
    - ``otoole`` (>=1.0) installed in the active Python environment.
    - GLPK ``glpsol`` on PATH (or pointed to via ``glpsol_executable``).
    - Optional: CBC for larger model sizes (set ``solver: cbc`` and
      provide the cbc executable path).
"""

from __future__ import annotations

import csv
import logging
import shutil
import subprocess
import tempfile
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

DEFAULT_OSEMOSYS_DIR = Path("Models/Energy/OSeMOSYS")


class OSeMOSYSConfig(BaseModel):
    """Configuration for the OSeMOSYSAdapter."""

    osemosys_dir: Path = Field(
        default=DEFAULT_OSEMOSYS_DIR,
        description=(
            "Root of the vendored OSeMOSYS repository (must contain the "
            "MathProg formulation file referenced by ``model_file``)."
        ),
    )
    model_file: str = Field(
        default="osemosys.txt",
        description=(
            "Filename of the OSeMOSYS MathProg formulation inside "
            "osemosys_dir (e.g., 'osemosys.txt' or 'osemosys_short.txt')."
        ),
    )
    baseline_data_dir: Path = Field(
        default=Path("data/osemosys/baseline"),
        description=(
            "Directory containing the baseline OSeMOSYS dataset "
            "(CSV-per-parameter layout that otoole expects)."
        ),
    )
    otoole_config: Path = Field(
        default=Path("data/osemosys/baseline/config.yaml"),
        description="Path to the otoole config.yaml describing the dataset.",
    )
    input_format: Literal["csv", "datafile", "excel"] = Field(
        default="csv",
        description="Format of the baseline data (matches otoole's --input_format).",
    )
    output_dir: Path = Field(
        default=Path("data/outputs/osemosys"),
        description="Directory where solved-result CSVs are written per scenario.",
    )
    solver: Literal["glpk", "cbc", "cplex", "gurobi"] = Field(
        default="glpk",
        description="LP solver used by glpsol (or directly via otoole solve).",
    )
    glpsol_executable: str = Field(
        default="glpsol",
        description="Path to the GLPK glpsol binary.",
    )
    cbc_executable: str = Field(
        default="cbc",
        description="Path to the CBC binary (used when solver != 'glpk').",
    )
    otoole_executable: str = Field(
        default="otoole",
        description="Path to the otoole CLI.",
    )
    timeout_seconds: int = Field(
        default=7200,
        description="Per-phase subprocess timeout (default 2 hours).",
    )
    keep_working_copy: bool = Field(
        default=False,
        description="Keep the per-scenario working copy after completion.",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PARAMS = frozenset(
    {
        "oil_supply_loss_mbd",
        "gas_supply_loss_bcfd",
        "disruption_duration_months",
        "lng_export_capacity_loss_pct",
        "capital_cost_multiplier",
        "co2_price_baseline_usd_per_t",
    }
)

# Result CSVs we ingest from otoole's output. These are the long-run
# decision-support variables most useful for cross-model consistency.
RESULT_VARIABLES = (
    "NewCapacity",
    "ProductionByTechnology",
    "TotalDiscountedCost",
    "UseByTechnology",
    "AnnualEmissions",
)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OSeMOSYSAdapter(ModelAdapter):
    """Live adapter for the OSeMOSYS energy-system optimization model."""

    def __init__(self, config: OSeMOSYSConfig | None = None) -> None:
        self._config = config or OSeMOSYSConfig()

    @property
    def model_id(self) -> str:
        return "osemosys"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.ENERGY_SYSTEMS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "OSeMOSYS — Open Source Energy Modelling System. Long-run "
            "least-cost capacity expansion via GLPK MathProg, driven through "
            "the otoole → glpsol → otoole pipeline. Parameterized with "
            "Hormuz-class fuel-supply, fuel-price, and capital-cost shocks."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=2,
            memory_gb=8.0,
            supports_multi_threading=False,
            prefers_process_isolation=True,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        missing = REQUIRED_PARAMS - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        oil_loss = params["oil_supply_loss_mbd"]
        if not isinstance(oil_loss, (int, float)):
            errors.append("'oil_supply_loss_mbd' must be numeric")
        elif not (0.0 <= oil_loss <= 30.0):
            warnings.append(
                f"'oil_supply_loss_mbd' value {oil_loss} is outside the "
                "expected range [0, 30] mb/d for Hormuz-class disruptions"
            )

        gas_loss = params["gas_supply_loss_bcfd"]
        if not isinstance(gas_loss, (int, float)):
            errors.append("'gas_supply_loss_bcfd' must be numeric")
        elif not (0.0 <= gas_loss <= 100.0):
            warnings.append(
                f"'gas_supply_loss_bcfd' value {gas_loss} is outside the "
                "expected range [0, 100] bcf/d"
            )

        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append("'disruption_duration_months' must be a positive number")

        lng_loss_pct = params["lng_export_capacity_loss_pct"]
        if not isinstance(lng_loss_pct, (int, float)):
            errors.append("'lng_export_capacity_loss_pct' must be numeric")
        elif not (0.0 <= lng_loss_pct <= 100.0):
            errors.append(
                f"'lng_export_capacity_loss_pct' must be in [0, 100]; got {lng_loss_pct}"
            )

        capex_mult = params["capital_cost_multiplier"]
        if not isinstance(capex_mult, (int, float)) or capex_mult <= 0:
            errors.append("'capital_cost_multiplier' must be a positive number")
        elif capex_mult > 5.0:
            warnings.append(
                f"'capital_cost_multiplier' value {capex_mult} is unusually large"
            )

        co2_price = params["co2_price_baseline_usd_per_t"]
        if not isinstance(co2_price, (int, float)) or co2_price < 0:
            errors.append("'co2_price_baseline_usd_per_t' must be non-negative numeric")

        # Surface integration prerequisites.
        cfg = self._config
        if not cfg.osemosys_dir.exists():
            warnings.append(
                f"OSeMOSYS source dir does not exist: {cfg.osemosys_dir}. "
                "execute() will fail until the OSeMOSYS repo is vendored "
                "at this path."
            )
        elif not (cfg.osemosys_dir / cfg.model_file).exists():
            warnings.append(
                f"MathProg formulation '{cfg.model_file}' not found in "
                f"{cfg.osemosys_dir}"
            )

        if not cfg.baseline_data_dir.exists():
            warnings.append(
                f"OSeMOSYS baseline_data_dir does not exist: {cfg.baseline_data_dir}"
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate pipeline shocks into OSeMOSYS dataset overrides.

        Returns a dict with ``scenario_id`` plus a ``shocks`` mapping
        keyed by OSeMOSYS parameter name (e.g., ``CapitalCost``,
        ``TotalAnnualMaxCapacity``). The dict is consumed by
        ``_apply_shocks_to_dataset`` during execute().
        """
        scenario_id = params.get("scenario_id", "default")

        oil_loss_pj_per_yr = float(params["oil_supply_loss_mbd"]) * 365.0 * 5.8e-3
        gas_loss_pj_per_yr = float(params["gas_supply_loss_bcfd"]) * 365.0 * 1.055e-3

        return {
            "scenario_id": scenario_id,
            "shocks": {
                "oil_supply_loss_pj_per_yr": oil_loss_pj_per_yr,
                "gas_supply_loss_pj_per_yr": gas_loss_pj_per_yr,
                "duration_years": float(params["disruption_duration_months"]) / 12.0,
                "oil_price_path_override_usd": params.get("oil_price_path_override_usd"),
                "lng_export_capacity_loss_pct": float(params["lng_export_capacity_loss_pct"]),
                "capital_cost_multiplier": float(params["capital_cost_multiplier"]),
                "co2_price_baseline_usd_per_t": float(params["co2_price_baseline_usd_per_t"]),
            },
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Run the full otoole → glpsol → otoole pipeline for one scenario."""
        cfg = self._config
        scenario_id = inputs["scenario_id"]

        if not cfg.osemosys_dir.exists():
            raise FileNotFoundError(
                f"OSeMOSYS source dir not found: {cfg.osemosys_dir}. "
                "Vendor the OSeMOSYS repo (https://github.com/OSeMOSYS/OSeMOSYS) "
                f"at {DEFAULT_OSEMOSYS_DIR} or override OSeMOSYSConfig.osemosys_dir."
            )
        if not cfg.baseline_data_dir.exists():
            raise FileNotFoundError(
                f"OSeMOSYS baseline_data_dir not found: {cfg.baseline_data_dir}. "
                "Provide a baseline dataset (CSV-per-parameter layout)."
            )

        work_dir = Path(tempfile.mkdtemp(prefix=f"osemosys_{scenario_id}_"))
        try:
            data_copy = work_dir / "data"
            shutil.copytree(cfg.baseline_data_dir, data_copy)

            self._apply_shocks_to_dataset(data_copy, inputs["shocks"])

            datafile = work_dir / "scenario.txt"
            self._run_otoole_convert(data_copy, datafile)

            solution_file = work_dir / "solution.sol"
            start = time.time()
            self._run_solver(datafile, solution_file)
            elapsed = time.time() - start

            results_dir = cfg.output_dir / scenario_id
            results_dir.mkdir(parents=True, exist_ok=True)
            self._run_otoole_results(solution_file, datafile, results_dir)

            outputs = self._parse_results(results_dir)
            outputs["_applied_shocks"] = inputs["shocks"]

            return ModelOutput(
                model_id=self.model_id,
                outputs=outputs,
                convergence_status="completed",
                metadata={
                    "scenario_id": scenario_id,
                    "work_dir": str(work_dir) if cfg.keep_working_copy else None,
                    "results_dir": str(results_dir),
                    "elapsed_seconds_solve": elapsed,
                    "solver": cfg.solver,
                },
            )
        finally:
            if not cfg.keep_working_copy:
                shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Wrap raw parsed outputs in a standardized ModelOutput."""
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_shocks_to_dataset(
        self, data_dir: Path, shocks: dict[str, Any]
    ) -> None:
        """Apply pipeline-derived shocks to the OSeMOSYS CSV dataset.

        Conventions:
            - ``CapitalCost.csv`` is multiplied by ``capital_cost_multiplier``.
            - ``TotalAnnualMaxCapacity.csv`` rows whose TECHNOLOGY contains
              "LNG" are reduced by ``lng_export_capacity_loss_pct``.
            - ``TotalTechnologyAnnualActivityUpperLimit.csv`` rows whose
              FUEL contains "OIL"/"GAS" are reduced by the converted
              supply-loss values for the duration window.
            - ``EmissionsPenalty.csv`` is set to ``co2_price_baseline_usd_per_t``
              (constant across years where present).

        This is intentionally permissive — missing CSVs are skipped with
        a debug log so the adapter works against a wide range of OSeMOSYS
        baselines.
        """
        capex_mult = float(shocks["capital_cost_multiplier"])
        if capex_mult != 1.0:
            self._scale_csv_value(
                data_dir / "CapitalCost.csv",
                column="VALUE",
                multiplier=capex_mult,
            )

        lng_loss_pct = float(shocks["lng_export_capacity_loss_pct"])
        if lng_loss_pct > 0:
            self._scale_csv_value(
                data_dir / "TotalAnnualMaxCapacity.csv",
                column="VALUE",
                multiplier=1.0 - lng_loss_pct / 100.0,
                row_filter=lambda row: "LNG" in str(row.get("TECHNOLOGY", "")).upper(),
            )

        oil_loss_pj = float(shocks["oil_supply_loss_pj_per_yr"])
        gas_loss_pj = float(shocks["gas_supply_loss_pj_per_yr"])
        duration_years = float(shocks["duration_years"])
        if oil_loss_pj > 0 or gas_loss_pj > 0:
            self._reduce_supply_upper_limit(
                data_dir / "TotalTechnologyAnnualActivityUpperLimit.csv",
                oil_reduction_pj=oil_loss_pj,
                gas_reduction_pj=gas_loss_pj,
                duration_years=duration_years,
            )

        co2_price = float(shocks["co2_price_baseline_usd_per_t"])
        if co2_price > 0:
            self._set_csv_value(
                data_dir / "EmissionsPenalty.csv",
                column="VALUE",
                value=co2_price,
            )

    def _scale_csv_value(
        self,
        csv_path: Path,
        column: str,
        multiplier: float,
        row_filter=None,
    ) -> None:
        if not csv_path.exists():
            logger.debug("OSeMOSYS shock target CSV missing, skipping: %s", csv_path)
            return
        rows = list(csv.DictReader(csv_path.open(newline="")))
        if not rows:
            return
        for row in rows:
            if row_filter is not None and not row_filter(row):
                continue
            try:
                row[column] = str(float(row[column]) * multiplier)
            except (KeyError, ValueError):
                continue
        with csv_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def _set_csv_value(
        self, csv_path: Path, column: str, value: float
    ) -> None:
        if not csv_path.exists():
            logger.debug("OSeMOSYS shock target CSV missing, skipping: %s", csv_path)
            return
        rows = list(csv.DictReader(csv_path.open(newline="")))
        if not rows:
            return
        for row in rows:
            row[column] = str(value)
        with csv_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def _reduce_supply_upper_limit(
        self,
        csv_path: Path,
        oil_reduction_pj: float,
        gas_reduction_pj: float,
        duration_years: float,
    ) -> None:
        if not csv_path.exists():
            logger.debug("OSeMOSYS supply upper-limit CSV missing: %s", csv_path)
            return
        rows = list(csv.DictReader(csv_path.open(newline="")))
        if not rows:
            return

        years_affected = self._collect_affected_years(rows, duration_years)
        for row in rows:
            tech = str(row.get("TECHNOLOGY", "")).upper()
            year = row.get("YEAR")
            if year not in years_affected:
                continue
            try:
                value = float(row["VALUE"])
            except (KeyError, ValueError):
                continue
            if "OIL" in tech and oil_reduction_pj > 0:
                row["VALUE"] = str(max(0.0, value - oil_reduction_pj))
            elif "GAS" in tech and gas_reduction_pj > 0:
                row["VALUE"] = str(max(0.0, value - gas_reduction_pj))

        with csv_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _collect_affected_years(
        rows: list[dict[str, Any]], duration_years: float
    ) -> set[str]:
        years = sorted({row["YEAR"] for row in rows if row.get("YEAR")})
        if not years:
            return set()
        n = max(1, int(round(duration_years)))
        return set(years[:n])

    def _run_otoole_convert(self, data_dir: Path, datafile: Path) -> None:
        cfg = self._config
        cmd = [
            cfg.otoole_executable, "convert",
            cfg.input_format, "datafile",
            str(data_dir), str(datafile),
            str(cfg.otoole_config),
        ]
        self._run_subprocess(cmd, label="otoole convert")

    def _run_solver(self, datafile: Path, solution_file: Path) -> None:
        cfg = self._config
        model_path = cfg.osemosys_dir / cfg.model_file
        if cfg.solver == "glpk":
            cmd = [
                cfg.glpsol_executable,
                "-m", str(model_path),
                "-d", str(datafile),
                "-w", str(solution_file),
            ]
            self._run_subprocess(cmd, label="glpsol")
        else:
            # otoole solve handles cbc/cplex/gurobi via Pyomo internally.
            cmd = [
                cfg.otoole_executable, "solve",
                "datafile", str(datafile),
                str(solution_file),
                "--solver", cfg.solver,
            ]
            self._run_subprocess(cmd, label=f"otoole solve ({cfg.solver})")

    def _run_otoole_results(
        self, solution_file: Path, datafile: Path, results_dir: Path
    ) -> None:
        cfg = self._config
        cmd = [
            cfg.otoole_executable, "results",
            "sol" if cfg.solver == "glpk" else cfg.solver,
            str(solution_file),
            "csv",
            str(results_dir),
            str(cfg.otoole_config),
            "--input_datafile", str(datafile),
        ]
        self._run_subprocess(cmd, label="otoole results")

    def _run_subprocess(self, cmd: list[str], label: str) -> None:
        logger.info("OSeMOSYS [%s]: %s", label, " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self._config.timeout_seconds,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"OSeMOSYS {label} failed (exit {exc.returncode}).\n"
                f"stdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"OSeMOSYS {label} timed out after {self._config.timeout_seconds}s"
            ) from exc
        if result.stdout:
            logger.debug("OSeMOSYS [%s] stdout:\n%s", label, result.stdout)

    def _parse_results(self, results_dir: Path) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for var in RESULT_VARIABLES:
            csv_path = results_dir / f"{var}.csv"
            if not csv_path.exists():
                continue
            rows = list(csv.DictReader(csv_path.open(newline="")))
            outputs[var] = rows
        if "TotalDiscountedCost" in outputs:
            try:
                outputs["total_system_cost_usd"] = sum(
                    float(r.get("VALUE", 0.0))
                    for r in outputs["TotalDiscountedCost"]
                )
            except (TypeError, ValueError):
                pass
        return outputs
