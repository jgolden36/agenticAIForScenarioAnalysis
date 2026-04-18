"""TEMOAAdapter — Tools for Energy Model Optimization and Analysis.

TEMOA is a Pyomo-based energy-systems optimization framework. Inputs
and outputs both live in a SQLite database. The execution flow is:

    1. Copy a baseline TEMOA SQLite database (vendored under
       ``Models/Energy/TEMOA/data_files/`` or supplied via config)
       into a per-scenario working copy.
    2. Apply pipeline-derived shocks via SQL ``UPDATE`` statements on
       the relevant tables: ``CostInvest`` (× capital_cost_multiplier),
       ``CostVariable`` (oil/gas price overrides), ``MaxActivity``
       (oil/gas supply caps), ``MaxCapacity`` (LNG export reductions),
       ``CostEmission`` (CO2 price baseline).
    3. Write a TEMOA config file pointing at the modified DB and the
       requested solver.
    4. Invoke ``python -m temoa.temoa_run --config <cfg>`` (or the
       vendored ``temoa_model/temoa_run.py`` entry point).
    5. Read solved variables ``Output_VFlow_Out``, ``Output_V_Capacity``,
       and ``Output_Costs`` directly from the result DB and parse into
       the standardized ``ModelOutput``.

Real implementation requirements:
    - Python: ``temoa-energysystem`` (or vendored ``Models/Energy/TEMOA/``
      checkout) and ``pyomo`` (>=6.7).
    - A solver Pyomo can drive (``cbc`` recommended for open-source
      installations; ``cplex``/``gurobi`` if licensed).
    - A baseline SQLite DB under ``baseline_db_path`` (the vendored repo
      ships several under ``data_files/``).
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
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

DEFAULT_TEMOA_DIR = Path("Models/Energy/TEMOA")


class TEMOAConfig(BaseModel):
    """Configuration for the TEMOAAdapter."""

    temoa_dir: Path = Field(
        default=DEFAULT_TEMOA_DIR,
        description="Root of the vendored TEMOA repository.",
    )
    baseline_db_path: Path = Field(
        default=Path("Models/Energy/TEMOA/data_files/utopia.sqlite"),
        description="Baseline TEMOA SQLite database (input + populated with results).",
    )
    output_dir: Path = Field(
        default=Path("data/outputs/temoa"),
        description="Directory where per-scenario result DBs are written.",
    )
    solver: Literal["cbc", "cplex", "gurobi", "glpk", "appsi_highs"] = Field(
        default="cbc",
        description="Pyomo solver to invoke from temoa_run.",
    )
    python_executable: str = Field(
        default="python",
        description="Python interpreter used to invoke temoa.temoa_run.",
    )
    temoa_module: str = Field(
        default="temoa.temoa_run",
        description=(
            "Python module that runs TEMOA. The legacy entry point is "
            "'temoa_model.temoa_run' for older checkouts."
        ),
    )
    timeout_seconds: int = Field(
        default=14400,
        description="Subprocess timeout (default 4 hours).",
    )
    keep_working_copy: bool = Field(
        default=False,
        description="Keep the per-scenario working DB after completion.",
    )
    oil_fuel_pattern: str = Field(
        default="OIL",
        description=(
            "Substring (case-insensitive) used to identify oil-related "
            "TEMOA technology IDs in CostVariable / MaxActivity rows."
        ),
    )
    gas_fuel_pattern: str = Field(
        default="GAS",
        description="Substring used to identify gas-related TEMOA technologies.",
    )
    lng_pattern: str = Field(
        default="LNG",
        description="Substring used to identify LNG export-related TEMOA technologies.",
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


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class TEMOAAdapter(ModelAdapter):
    """Live adapter for the TEMOA energy-systems optimization framework."""

    def __init__(self, config: TEMOAConfig | None = None) -> None:
        self._config = config or TEMOAConfig()

    @property
    def model_id(self) -> str:
        return "temoa"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.ENERGY_SYSTEMS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "TEMOA — Tools for Energy Model Optimization and Analysis. Pyomo "
            "+ CBC long-run least-cost capacity expansion. Driven by SQL "
            "shock injection into a per-scenario SQLite working copy."
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

        for name in REQUIRED_PARAMS:
            value = params[name]
            if not isinstance(value, (int, float)):
                errors.append(f"'{name}' must be numeric; got {type(value).__name__}")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        if params["disruption_duration_months"] <= 0:
            errors.append("'disruption_duration_months' must be positive")
        if params["capital_cost_multiplier"] <= 0:
            errors.append("'capital_cost_multiplier' must be positive")
        if not (0.0 <= params["lng_export_capacity_loss_pct"] <= 100.0):
            errors.append("'lng_export_capacity_loss_pct' must be in [0, 100]")
        if params["co2_price_baseline_usd_per_t"] < 0:
            errors.append("'co2_price_baseline_usd_per_t' must be non-negative")

        cfg = self._config
        if not cfg.baseline_db_path.exists():
            warnings.append(
                f"TEMOA baseline DB not found at {cfg.baseline_db_path}; "
                "execute() will fail until a baseline SQLite database is provided."
            )

        try:
            import pyomo  # noqa: F401
        except ImportError:
            warnings.append(
                "pyomo is not installed; install via "
                "`pip install hormuz-pipeline[energy]` before calling execute()."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        scenario_id = params.get("scenario_id", "default")
        return {
            "scenario_id": scenario_id,
            "shocks": {
                "oil_supply_loss_mbd": float(params["oil_supply_loss_mbd"]),
                "gas_supply_loss_bcfd": float(params["gas_supply_loss_bcfd"]),
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
        cfg = self._config
        scenario_id = inputs["scenario_id"]

        if not cfg.baseline_db_path.exists():
            raise FileNotFoundError(
                f"TEMOA baseline DB not found: {cfg.baseline_db_path}. "
                "Vendor a baseline SQLite (e.g. utopia.sqlite) under "
                f"{DEFAULT_TEMOA_DIR}/data_files/ or override "
                "TEMOAConfig.baseline_db_path."
            )

        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        scenario_db = cfg.output_dir / f"{scenario_id}.sqlite"
        shutil.copyfile(cfg.baseline_db_path, scenario_db)

        self._apply_shocks(scenario_db, inputs["shocks"])

        with tempfile.TemporaryDirectory(prefix=f"temoa_{scenario_id}_") as work_dir:
            config_path = Path(work_dir) / "temoa_config.txt"
            self._write_temoa_config(config_path, scenario_db)

            start = time.time()
            self._run_temoa(config_path)
            elapsed = time.time() - start

        outputs = self._read_results(scenario_db)
        outputs["_applied_shocks"] = inputs["shocks"]

        result = ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="completed",
            metadata={
                "scenario_id": scenario_id,
                "scenario_db": str(scenario_db),
                "solver": cfg.solver,
                "elapsed_seconds_solve": elapsed,
            },
        )

        if not cfg.keep_working_copy:
            # Even when not keeping the working copy, retain the DB if
            # callers want to drill into the full TEMOA result set.
            pass

        return result

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
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

    def _apply_shocks(self, db_path: Path, shocks: dict[str, Any]) -> None:
        """Inject pipeline shocks into the per-scenario SQLite copy.

        Each statement is wrapped in try/except so the adapter degrades
        gracefully against TEMOA baselines whose schemas omit some
        cost / bound tables (e.g. minimal Utopia variants).
        """
        cfg = self._config
        capex_mult = float(shocks["capital_cost_multiplier"])
        co2_price = float(shocks["co2_price_baseline_usd_per_t"])
        lng_loss_pct = float(shocks["lng_export_capacity_loss_pct"])
        oil_loss = float(shocks["oil_supply_loss_mbd"])
        gas_loss = float(shocks["gas_supply_loss_bcfd"])
        duration_years = float(shocks["duration_years"])

        oil_pj_per_yr = oil_loss * 365.0 * 5.8e-3
        gas_pj_per_yr = gas_loss * 365.0 * 1.055e-3

        statements: list[tuple[str, list[Any]]] = []

        if capex_mult != 1.0:
            statements.append((
                "UPDATE CostInvest SET cost_invest = cost_invest * ?",
                [capex_mult],
            ))

        if co2_price > 0:
            statements.append((
                "UPDATE CostEmission SET cost_emission = ?",
                [co2_price],
            ))

        if lng_loss_pct > 0:
            statements.append((
                f"UPDATE MaxCapacity SET maxcap = maxcap * ? "
                f"WHERE UPPER(tech) LIKE '%' || ? || '%'",
                [1.0 - lng_loss_pct / 100.0, cfg.lng_pattern.upper()],
            ))

        if oil_pj_per_yr > 0 or gas_pj_per_yr > 0:
            affected_years = self._first_n_years(db_path, max(1, int(round(duration_years))))
            for year in affected_years:
                if oil_pj_per_yr > 0:
                    statements.append((
                        "UPDATE MaxActivity SET maxact = MAX(maxact - ?, 0) "
                        "WHERE periods = ? AND UPPER(tech) LIKE '%' || ? || '%'",
                        [oil_pj_per_yr, year, cfg.oil_fuel_pattern.upper()],
                    ))
                if gas_pj_per_yr > 0:
                    statements.append((
                        "UPDATE MaxActivity SET maxact = MAX(maxact - ?, 0) "
                        "WHERE periods = ? AND UPPER(tech) LIKE '%' || ? || '%'",
                        [gas_pj_per_yr, year, cfg.gas_fuel_pattern.upper()],
                    ))

        oil_price_override = shocks.get("oil_price_path_override_usd")
        if oil_price_override:
            usd_per_pj = float(oil_price_override) / 5.8e-3
            statements.append((
                "UPDATE CostVariable SET cost_variable = ? "
                "WHERE UPPER(tech) LIKE '%' || ? || '%'",
                [usd_per_pj, cfg.oil_fuel_pattern.upper()],
            ))

        with sqlite3.connect(db_path) as conn:
            for sql, args in statements:
                try:
                    conn.execute(sql, args)
                except sqlite3.OperationalError as exc:
                    logger.warning(
                        "TEMOA shock SQL skipped (%s): %s", exc, sql
                    )
            conn.commit()

    def _first_n_years(self, db_path: Path, n: int) -> list[int]:
        try:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT t_periods FROM time_periods "
                    "WHERE flag = 'f' ORDER BY t_periods ASC LIMIT ?",
                    [n],
                ).fetchall()
            return [r[0] for r in rows]
        except sqlite3.OperationalError as exc:
            logger.warning("Could not read time_periods from %s: %s", db_path, exc)
            return []

    def _write_temoa_config(self, config_path: Path, db_path: Path) -> None:
        cfg = self._config
        config_path.write_text(
            textwrap.dedent(
                f"""\
                # Auto-generated TEMOA config — Hormuz pipeline
                --input    {db_path}
                --output   {db_path}
                --scenario hormuz
                --solver   {cfg.solver}
                """
            )
        )

    def _run_temoa(self, config_path: Path) -> None:
        cfg = self._config
        cmd = [
            cfg.python_executable, "-m", cfg.temoa_module,
            "--config", str(config_path),
        ]
        env_cwd = cfg.temoa_dir if cfg.temoa_dir.exists() else None
        logger.info("TEMOA: %s (cwd=%s)", " ".join(cmd), env_cwd)
        try:
            result = subprocess.run(
                cmd,
                cwd=str(env_cwd) if env_cwd else None,
                check=True,
                capture_output=True,
                text=True,
                timeout=cfg.timeout_seconds,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"TEMOA run failed (exit {exc.returncode}).\n"
                f"stdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"TEMOA run timed out after {cfg.timeout_seconds}s"
            ) from exc
        if result.stdout:
            logger.debug("TEMOA stdout:\n%s", result.stdout)

    def _read_results(self, db_path: Path) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        result_tables = (
            "Output_VFlow_Out",
            "Output_V_Capacity",
            "Output_Costs",
            "Output_Emissions",
        )
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            for table in result_tables:
                try:
                    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                except sqlite3.OperationalError:
                    continue
                outputs[table] = [dict(r) for r in rows]

        cost_rows = outputs.get("Output_Costs") or []
        if cost_rows:
            try:
                outputs["total_system_cost_usd"] = sum(
                    float(r.get("output_cost", r.get("cost", 0.0)))
                    for r in cost_rows
                )
            except (TypeError, ValueError):
                pass
        return outputs
