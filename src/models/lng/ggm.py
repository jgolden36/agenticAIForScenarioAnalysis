"""Adapter for the Global Gas Model (GGM).

GGM is a global gas trade flow optimization model (QCP solved via CPLEX)
that determines least-cost allocation of LNG and pipeline gas across regions
subject to capacity constraints. Under Strait of Hormuz closure scenarios, it
determines how global LNG flows re-route around the Persian Gulf supply gap,
which buyers bear the highest price exposure, and what residual supply-demand
imbalances persist.

The model is implemented in GAMS and distributed by NTNU/DIW Berlin under MIT
license. This adapter wraps the open-source GGM v3.0 (May 2019).

Execution architecture:
    GGM uses relative $INCLUDE paths and compile-time $call GDXXRW operations
    that require the working directory to be the GGM model root.  Rather than
    the GAMSAdapter base class's temp-directory approach, this adapter:
      1. Copies the model directory to an isolated working copy
      2. Generates a wrapper .gms file with scenario globals
      3. Generates a shock overlay .gms file that modifies cap_p / cost_a
         between data loading and model solve
      4. Runs GAMS via subprocess from the copied model directory
      5. Reads results from the output GDX files

Integration requirements:
    - GAMS installation (47.x+ recommended) with CPLEX solver license
    - gamsapi Python package for GDX reading (pip install gamsapi[transfer])
    - GGM Excel data files in data/SET-Nav/:
        data.xlsx, data_proj.xlsx, data_calib_NPS-Ref.xlsx
    - Writable disk space for model copy (~50 MB per run)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GGM geography constants (from geo_data.csv and in_sets_parms.gms)
# ---------------------------------------------------------------------------

GGM_REGIONS = {
    "RUS", "NAM", "SAM", "EU", "ROE", "CAS", "MEA", "AFR", "ASP",
    "LIQ", "REG",
}

PERSIAN_GULF_COUNTRIES = {"QAT", "ARE", "IRN", "OMN", "KWT", "BHR", "SAU", "IRQ"}

HORMUZ_LNG_EXPORTERS = {"QAT", "ARE", "IRN", "OMN", "YEM"}

VALID_WEO_SCENARIOS = {"NPS", "SDS"}
VALID_SETNAV_MAP = {"NPS": "Ref", "SDS": "Vision"}
VALID_HORIZONS = {"2015", "2025", "2060"}

# ---------------------------------------------------------------------------
# Parameter specifications
# ---------------------------------------------------------------------------

_REQUIRED_PARAMS: dict[str, tuple[str, str]] = {
    "strait_closure_flag": (
        "Whether the Strait of Hormuz is closed",
        "boolean",
    ),
    "qatar_lng_export_loss_pct": (
        "Percentage reduction in Qatari LNG exports due to closure",
        "percent",
    ),
    "uae_lng_export_loss_pct": (
        "Percentage reduction in UAE LNG exports",
        "percent",
    ),
    "iran_lng_export_loss_pct": (
        "Percentage reduction in Iranian gas exports",
        "percent",
    ),
    "rerouting_available": (
        "Whether alternative LNG supply routes are available",
        "boolean",
    ),
    "disruption_duration_months": (
        "Duration of the Strait closure",
        "months",
    ),
}

_OPTIONAL_PARAMS: dict[str, tuple[str, str]] = {
    "oman_lng_export_loss_pct": (
        "Percentage reduction in Omani LNG exports (default: 0)",
        "percent",
    ),
    "yemen_lng_export_loss_pct": (
        "Percentage reduction in Yemeni LNG exports (default: 0)",
        "percent",
    ),
    "insurance_premium_multiplier": (
        "Multiplier on shipping arc costs due to war risk premiums",
        "factor",
    ),
    "scenario_label": (
        "WEO scenario label: 'NPS' or 'SDS'",
        "categorical",
    ),
    "time_horizon": (
        "Last year for the model: '2015', '2025', or '2060'",
        "categorical",
    ),
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class GGMConfig(BaseModel):
    """Configuration for the GGM adapter."""

    model_config = {"protected_namespaces": ()}

    gams_system_dir: Path = Field(
        description="Path to GAMS system directory (e.g. C:/GAMS/47)"
    )
    model_dir: Path = Field(
        description=(
            "Path to the GGM model root directory containing main.gms, "
            "data/, model/, report/ subdirectories"
        )
    )
    solver: str = Field(
        default="CPLEX",
        description="QCP solver (CPLEX required for GGM's quadratic objective)",
    )
    timeout_seconds: int = Field(
        default=7200,
        description="Maximum wall-clock seconds for the GAMS solve",
    )
    keep_working_copy: bool = Field(
        default=False,
        description="If True, do not delete the working copy after execution",
    )
    gams_executable: str = Field(
        default="gams",
        description=(
            "Name or full path of the GAMS executable. "
            "If just 'gams', it must be on the system PATH."
        ),
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class GGMAdapter(ModelAdapter):
    """Adapter for the Global Gas Model (GGM).

    Unlike the generic GAMSAdapter, this adapter uses subprocess execution
    and a wrapper-GMS approach because GGM relies on compile-time $INCLUDE
    paths and $call GDXXRW operations rooted in its own directory tree.
    """

    def __init__(self, config: GGMConfig | None = None) -> None:
        self._config = config

    # -- ModelAdapter interface properties ----------------------------------

    @property
    def model_id(self) -> str:
        return "ggm"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Global Gas Model (GGM): QCP optimization of global LNG and pipeline "
            "gas trade flows under Strait of Hormuz closure. Determines regional "
            "price paths, trade flow rerouting, capacity utilization, and residual "
            "supply gaps across ~80 country nodes."
        )

    # -- Validation ---------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        missing = set(_REQUIRED_PARAMS.keys()) - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        closure_flag = params["strait_closure_flag"]
        if not isinstance(closure_flag, bool):
            errors.append(
                f"'strait_closure_flag' must be boolean; got {type(closure_flag).__name__}"
            )

        for pct_field in [
            "qatar_lng_export_loss_pct",
            "uae_lng_export_loss_pct",
            "iran_lng_export_loss_pct",
        ]:
            val = params[pct_field]
            if not isinstance(val, (int, float)):
                errors.append(f"'{pct_field}' must be numeric")
            elif not (0.0 <= val <= 100.0):
                errors.append(f"'{pct_field}' must be in [0, 100]; got {val}")

        if isinstance(closure_flag, bool) and closure_flag:
            qatar_loss = params.get("qatar_lng_export_loss_pct", 0)
            if isinstance(qatar_loss, (int, float)) and qatar_loss == 0.0:
                warnings.append(
                    "'qatar_lng_export_loss_pct' is 0 while strait is closed; "
                    "Qatar is the world's largest LNG exporter through the Strait"
                )

        rerouting = params["rerouting_available"]
        if not isinstance(rerouting, bool):
            errors.append(
                f"'rerouting_available' must be boolean; got {type(rerouting).__name__}"
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
                f"'disruption_duration_months' of {duration} exceeds 24; "
                "verify this is intentional"
            )

        for pct_field in ["oman_lng_export_loss_pct", "yemen_lng_export_loss_pct"]:
            val = params.get(pct_field)
            if val is not None:
                if not isinstance(val, (int, float)):
                    errors.append(f"'{pct_field}' must be numeric")
                elif not (0.0 <= val <= 100.0):
                    errors.append(f"'{pct_field}' must be in [0, 100]; got {val}")

        insurance_mult = params.get("insurance_premium_multiplier")
        if insurance_mult is not None:
            if not isinstance(insurance_mult, (int, float)):
                errors.append("'insurance_premium_multiplier' must be numeric")
            elif insurance_mult < 1.0:
                warnings.append(
                    f"'insurance_premium_multiplier' is {insurance_mult} (< 1.0); "
                    "this implies lower-than-normal shipping costs"
                )

        scenario_label = params.get("scenario_label")
        if scenario_label is not None and scenario_label not in VALID_WEO_SCENARIOS:
            errors.append(
                f"'scenario_label' must be one of {VALID_WEO_SCENARIOS}; got '{scenario_label}'"
            )

        time_horizon = params.get("time_horizon")
        if time_horizon is not None and str(time_horizon) not in VALID_HORIZONS:
            errors.append(
                f"'time_horizon' must be one of {VALID_HORIZONS}; got '{time_horizon}'"
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- Input translation --------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate scenario parameters into GGM-native structures.

        Produces a dict with:
          - gams_globals: $SETGLOBAL values (WEO, SETNav, last_yr, data)
          - country_capacity_shocks: {country_code: remaining_fraction}
          - arc_cost_multiplier: float for war-risk premium on vessel arcs
          - scenario_id: identifier for file naming
        """
        weo = params.get("scenario_label", "NPS")
        setnav = VALID_SETNAV_MAP.get(weo, "Ref")
        last_yr = str(params.get("time_horizon", "2025"))

        country_shocks: dict[str, float] = {}
        loss_map = {
            "QAT": params.get("qatar_lng_export_loss_pct", 0),
            "ARE": params.get("uae_lng_export_loss_pct", 0),
            "IRN": params.get("iran_lng_export_loss_pct", 0),
            "OMN": params.get("oman_lng_export_loss_pct", 0),
            "YEM": params.get("yemen_lng_export_loss_pct", 0),
        }
        for code, loss_pct in loss_map.items():
            if isinstance(loss_pct, (int, float)) and loss_pct > 0:
                country_shocks[code] = 1.0 - (loss_pct / 100.0)

        return {
            "scenario_id": params.get("scenario_id", "hormuz_default"),
            "gams_globals": {
                "data": "SET-Nav",
                "WEO": weo,
                "SETNav": setnav,
                "last_yr": last_yr,
            },
            "country_capacity_shocks": country_shocks,
            "arc_cost_multiplier": params.get("insurance_premium_multiplier", 1.0),
            "closure_flag": params["strait_closure_flag"],
            "rerouting_available": params["rerouting_available"],
            "disruption_duration_months": params["disruption_duration_months"],
        }

    # -- Execution ----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute GGM via subprocess from an isolated copy of the model directory.

        Steps:
            1. Validate prerequisites (GAMS install, data files)
            2. Copy model directory to temp location
            3. Generate wrapper .gms and shock overlay .gms
            4. Run GAMS via subprocess
            5. Read and return results from output GDX
        """
        if self._config is None:
            raise NotImplementedError(
                "GGMAdapter.execute() requires a GGMConfig. Prerequisites:\n"
                "  1. GAMS installation with CPLEX solver license\n"
                "  2. gamsapi Python package (pip install gamsapi[transfer])\n"
                "  3. GGM model directory with data/SET-Nav/*.xlsx files\n"
                "  4. GGMConfig(gams_system_dir=..., model_dir=...)\n"
            )

        if not isinstance(inputs, dict):
            raise TypeError(f"inputs must be a dict from translate_inputs(); got {type(inputs)}")

        config = self._config
        self._validate_prerequisites(config)

        translated = inputs
        scenario_id = translated.get("scenario_id", "default")
        gams_globals = translated["gams_globals"]
        case_label = f"{gams_globals['WEO']}-{gams_globals['SETNav']}"

        # 1. Create isolated working copy
        work_dir = self._create_working_copy(config.model_dir, scenario_id)
        logger.info("GGM working copy created at %s", work_dir)

        try:
            # 2. Ensure gdx/ output directory exists
            gdx_dir = work_dir / "gdx"
            gdx_dir.mkdir(exist_ok=True)

            # 3. Generate GAMS files
            shock_filename = "hormuz_shock.gms"
            wrapper_filename = "hormuz_run.gms"

            self._write_shock_gms(
                work_dir / shock_filename,
                translated["country_capacity_shocks"],
                translated["arc_cost_multiplier"],
            )
            self._write_wrapper_gms(
                work_dir / wrapper_filename,
                gams_globals,
                shock_filename,
            )

            # 4. Run GAMS
            t_start = time.time()
            gams_result = self._run_gams(
                config, work_dir, wrapper_filename
            )
            elapsed = time.time() - t_start

            # 5. Read results
            data_name = gams_globals["data"]
            last_yr = gams_globals["last_yr"]
            reports_gdx = gdx_dir / f"{data_name}_{case_label}_{last_yr}_REPORTS.gdx"
            solution_gdx = gdx_dir / f"{data_name}_{case_label}_{last_yr}.gdx"

            results = self._read_results(
                config, reports_gdx, solution_gdx, case_label
            )

            return ModelOutput(
                model_id=self.model_id,
                outputs=results,
                convergence_status="optimal",
                metadata={
                    "gams_globals": gams_globals,
                    "case_label": case_label,
                    "elapsed_seconds": round(elapsed, 1),
                    "work_dir": str(work_dir),
                    "reports_gdx": str(reports_gdx),
                    "solution_gdx": str(solution_gdx),
                    "gams_return_code": gams_result.returncode,
                    "unit_notes": {
                        "prices": "EUR/kcm (convert to $/MMBtu: multiply by ~0.0343)",
                        "flows": "mcm/yr or bcm/yr depending on report",
                        "production": "mcm/yr",
                        "consumption": "mcm/yr",
                    },
                },
            )

        except Exception:
            # Capture listing file for diagnostics on failure
            lst_files = list(work_dir.glob("*.lst"))
            if lst_files:
                tail = lst_files[0].read_text(errors="replace")[-5000:]
                logger.error("GAMS listing file tail:\n%s", tail)
            raise

        finally:
            if not config.keep_working_copy:
                shutil.rmtree(work_dir, ignore_errors=True)
                logger.debug("Cleaned up working copy %s", work_dir)

    # -- Output parsing -----------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"unit_notes": {
                "prices": "EUR/kcm (convert to $/MMBtu: multiply by ~0.0343)",
                "flows": "mcm/yr or bcm/yr depending on report",
                "production": "mcm/yr",
                "consumption": "mcm/yr",
            }},
        )

    # ======================================================================
    # Private helpers
    # ======================================================================

    def _validate_prerequisites(self, config: GGMConfig) -> None:
        """Check that all required files and tools are present."""
        model_dir = config.model_dir

        if not model_dir.is_dir():
            raise FileNotFoundError(
                f"GGM model directory not found: {model_dir}"
            )

        required_files = [
            "main.gms",
            "cplex.opt",
            "model/all_eq_and_var.gms",
            "model/solve.gms",
            "data/all_input_data.gms",
            "data/in_sets_parms.gms",
            "data/in_prod.gms",
            "data/in_cons.gms",
            "data/in_arcs.gms",
            "data/in_stor.gms",
            "data/in_market.gms",
            "data/in_period.gms",
            "report/reports.gms",
        ]
        missing = [f for f in required_files if not (model_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"Missing GGM model files in {model_dir}: {missing}"
            )

        data_dir = model_dir / "data" / "SET-Nav"
        required_data = ["data.xlsx"]
        missing_data = [f for f in required_data if not (data_dir / f).exists()]
        if missing_data:
            raise FileNotFoundError(
                f"Missing GGM data files in {data_dir}: {missing_data}. "
                "These Excel workbooks are required for GGM calibration. "
                "See the DIW Data Documentation v3.0 for the data package."
            )

        gams_sys = config.gams_system_dir
        if not gams_sys.is_dir():
            raise FileNotFoundError(
                f"GAMS system directory not found: {gams_sys}"
            )

    def _create_working_copy(self, model_dir: Path, scenario_id: str) -> Path:
        """Copy the GGM model directory to a temp location for isolation.

        This is necessary because GAMS writes intermediate and output files
        (gdx, lst, g00, etc.) to the working directory, and concurrent runs
        would collide.
        """
        tmp_parent = Path(tempfile.mkdtemp(prefix=f"ggm_{scenario_id}_"))
        work_dir = tmp_parent / "GGM"
        shutil.copytree(model_dir, work_dir)
        return work_dir

    def _write_shock_gms(
        self,
        path: Path,
        country_shocks: dict[str, float],
        arc_cost_multiplier: float,
    ) -> None:
        """Generate the GAMS include file that applies Hormuz scenario shocks.

        This file is $INCLUDEd by the wrapper between data loading and solve.
        It modifies:
          - cap_p(n_p, r, y): production capacity for affected country nodes
          - cost_a(av, y): vessel arc costs for war-risk insurance premiums
        """
        lines = [
            "* ===================================================================",
            "* Hormuz scenario shock overlay (auto-generated by GGMAdapter)",
            "* ===================================================================",
            "",
        ]

        if country_shocks:
            lines.append("* --- Production capacity shocks ---")
            lines.append("* Reduce cap_p for nodes belonging to affected countries.")
            lines.append("* cap_p is in Mcm/day; we multiply by the remaining fraction.")
            lines.append("")

            for country_code, remaining_frac in sorted(country_shocks.items()):
                loss_pct = round((1.0 - remaining_frac) * 100, 1)
                lines.extend([
                    f"* {country_code}: {loss_pct}% production loss "
                    f"(remaining fraction = {remaining_frac:.4f})",
                    f"cap_p(n_p, r, y)$(sum(cn$(map_n_cn(n_p, cn) "
                    f"and sameas(cn, '{country_code}')), 1)) "
                    f"= cap_p(n_p, r, y) * {remaining_frac:.6f};",
                    "",
                ])

        if arc_cost_multiplier != 1.0:
            lines.extend([
                "* --- Vessel arc cost multiplier (war-risk insurance premium) ---",
                "* Apply to all LNG vessel arcs (av) originating from Hormuz-transit",
                "* liquefaction nodes. av = vessel arcs, al = liquefaction arcs.",
                "* Affected LNG exporters: QAT, ARE, IRN, OMN, YEM",
                "",
                f"cost_a(av, y)$(sum((n_l, n_r)$(map_a_n_n(av, n_l, n_r) "
                f"and sum(cn$(map_n_cn(n_l, cn) and "
                f"(sameas(cn,'QAT') or sameas(cn,'ARE') or sameas(cn,'IRN') "
                f"or sameas(cn,'OMN') or sameas(cn,'YEM'))), 1)), 1)) "
                f"= cost_a(av, y) * {arc_cost_multiplier:.4f};",
                "",
            ])

        lines.append("* === End of Hormuz shock overlay ===")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug("Wrote shock overlay to %s", path)

    def _write_wrapper_gms(
        self,
        path: Path,
        gams_globals: dict[str, str],
        shock_filename: str,
    ) -> None:
        """Generate the wrapper .gms file that replaces main.gms.

        Replicates the structure of main.gms but inserts the shock overlay
        between data loading and model solve.  Uses $SETGLOBAL for scenario
        selection instead of relying on hardcoded values in main.gms.
        """
        data = gams_globals["data"]
        weo = gams_globals["WEO"]
        setnav = gams_globals["SETNav"]
        last_yr = gams_globals["last_yr"]
        case_label = f"{weo}-{setnav}"

        gms = f"""\
* GGM Hormuz Scenario Run (auto-generated by GGMAdapter)
* Based on main.gms structure from GGM v3.0 (May 2019, NTNU/DIW Berlin)

$oninline $OFFSYMXREF $Offuelxref $offinclude
option   reslim=         7200
         iterlim=        1E9
         limrow=         0
         limcol=         0
;

* --- Scenario and horizon specification ---
$SETGLOBAL data          {data}
$SETGLOBAL WEO           '{weo}'
$SETGLOBAL SETNav        '{setnav}'
$SETGLOBAL last_yr       {last_yr}

* --- Read input data ---
$INCLUDE data\\all_input_data.gms
execute_unload 'gdx\\%data%_%last_yr%_INPUTS.gdx';

* === HORMUZ SCENARIO SHOCK OVERLAY ===
$INCLUDE {shock_filename}
* === END SHOCK OVERLAY ===

* --- Set up model and solve ---
$INCLUDE model\\all_eq_and_var.gms

option QCP= CPLEX;
SGGM.optfile = 1;
SGGM.holdfixed=1;

$INCLUDE model\\solve.gms

* Store solution
execute_unload  'gdx\\%data%_%case%_%last_yr%.gdx' D_A, D_X, D_W, Q_P, Q_S, F_A, F_I, F_X;

* --- Reports ---
$INCLUDE report\\reports.gms
"""
        path.write_text(gms, encoding="utf-8")
        logger.debug("Wrote wrapper GMS to %s", path)

    def _run_gams(
        self,
        config: GGMConfig,
        work_dir: Path,
        gms_filename: str,
    ) -> subprocess.CompletedProcess:
        """Execute GAMS as a subprocess from the GGM working directory."""
        gams_exe = config.gams_executable
        gams_sys = str(config.gams_system_dir)

        cmd = [
            gams_exe,
            gms_filename,
            f"sysDir={gams_sys}",
            "logoption=3",          # log to stdout + listing file
            "pagesize=0",           # no page breaks
            "suppress=1",           # suppress compilation listing
            f"curDir={work_dir}",   # explicit working directory
        ]

        logger.info("Running GGM: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
        )

        if result.returncode not in (0, 1, 2):
            # GAMS return codes: 0=normal, 1=solver issue, 2=compiler error
            # Higher codes indicate more serious failures
            lst_content = ""
            lst_files = list(work_dir.glob("*.lst"))
            if lst_files:
                lst_content = lst_files[0].read_text(errors="replace")[-5000:]

            raise RuntimeError(
                f"GAMS execution failed with return code {result.returncode}.\n"
                f"stdout (last 2000 chars):\n{result.stdout[-2000:]}\n"
                f"stderr:\n{result.stderr[-2000:]}\n"
                f"Listing file tail:\n{lst_content}"
            )

        # Return code 2 means model didn't solve correctly (abort in solve.gms)
        if result.returncode == 2:
            lst_content = ""
            lst_files = list(work_dir.glob("*.lst"))
            if lst_files:
                lst_content = lst_files[0].read_text(errors="replace")[-5000:]
            raise RuntimeError(
                f"GGM model did not solve correctly (GAMS return code 2: "
                f"model status > 2, triggered abort in solve.gms).\n"
                f"Listing file tail:\n{lst_content}"
            )

        logger.info(
            "GGM GAMS run completed (return code %d) in work_dir %s",
            result.returncode, work_dir,
        )
        return result

    def _read_results(
        self,
        config: GGMConfig,
        reports_gdx: Path,
        solution_gdx: Path,
        case_label: str,
    ) -> dict[str, Any]:
        """Read GGM results from output GDX files.

        Attempts to use gamsapi Transfer API (Container) first, falling back
        to subprocess gdxdump if gamsapi is not available.
        """
        results: dict[str, Any] = {}

        try:
            results = self._read_results_transfer_api(
                config, reports_gdx, solution_gdx, case_label
            )
        except ImportError:
            logger.warning(
                "gamsapi not available; falling back to gdxdump subprocess"
            )
            results = self._read_results_gdxdump(
                config, reports_gdx, solution_gdx
            )

        return results

    def _read_results_transfer_api(
        self,
        config: GGMConfig,
        reports_gdx: Path,
        solution_gdx: Path,
        case_label: str,
    ) -> dict[str, Any]:
        """Read results using gamsapi Transfer API (high-performance DataFrames)."""
        from gams.transfer import Container

        results: dict[str, Any] = {}

        # --- Read REPORTS GDX ---
        if reports_gdx.exists():
            ct = Container(system_directory=str(config.gams_system_dir))
            ct.read(str(reports_gdx))

            for symbol_name in ct.data:
                sym = ct.data[symbol_name]
                if hasattr(sym, "records") and sym.records is not None:
                    df = sym.records
                    results[symbol_name] = {
                        "records": df.to_dict(orient="records"),
                        "num_records": len(df),
                    }
        else:
            logger.warning("Reports GDX not found: %s", reports_gdx)

        # --- Read solution GDX for key variables ---
        if solution_gdx.exists():
            ct_sol = Container(system_directory=str(config.gams_system_dir))
            ct_sol.read(str(solution_gdx))

            variable_names = ["D_A", "D_X", "D_W", "Q_P", "Q_S", "F_A", "F_I", "F_X"]
            for var_name in variable_names:
                if var_name in ct_sol.data:
                    sym = ct_sol.data[var_name]
                    if hasattr(sym, "records") and sym.records is not None:
                        df = sym.records
                        results[f"var_{var_name}"] = {
                            "records": df.to_dict(orient="records"),
                            "num_records": len(df),
                        }
        else:
            logger.warning("Solution GDX not found: %s", solution_gdx)

        return results

    def _read_results_gdxdump(
        self,
        config: GGMConfig,
        reports_gdx: Path,
        solution_gdx: Path,
    ) -> dict[str, Any]:
        """Fallback: read results by invoking gdxdump as a subprocess.

        Parses the CSV-format output of gdxdump for each symbol.
        """
        results: dict[str, Any] = {}
        gams_sys = config.gams_system_dir
        gdxdump_exe = gams_sys / "gdxdump"
        if not gdxdump_exe.exists():
            gdxdump_exe = gams_sys / "gdxdump.exe"

        if not gdxdump_exe.exists():
            logger.error("gdxdump not found in %s", gams_sys)
            return results

        for gdx_path, prefix in [
            (reports_gdx, ""),
            (solution_gdx, "var_"),
        ]:
            if not gdx_path.exists():
                continue

            # List symbols
            list_result = subprocess.run(
                [str(gdxdump_exe), str(gdx_path), "-V"],
                capture_output=True, text=True, timeout=60,
            )
            if list_result.returncode != 0:
                logger.error("gdxdump -V failed on %s", gdx_path)
                continue

            for line in list_result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] in ("Par", "Var"):
                    sym_name = parts[0]
                    try:
                        dump_result = subprocess.run(
                            [
                                str(gdxdump_exe), str(gdx_path),
                                f"Symb={sym_name}", "-CSV",
                            ],
                            capture_output=True, text=True, timeout=120,
                        )
                        if dump_result.returncode == 0:
                            csv_lines = dump_result.stdout.strip().splitlines()
                            results[f"{prefix}{sym_name}"] = {
                                "csv_header": csv_lines[0] if csv_lines else "",
                                "num_records": max(len(csv_lines) - 1, 0),
                                "sample_records": csv_lines[1:11],
                            }
                    except Exception as exc:
                        logger.warning(
                            "Failed to dump symbol %s: %s", sym_name, exc
                        )

        return results

    # -- Convenience methods for downstream analysis ------------------------

    def extract_country_prices(
        self, results: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract country-level prices from GGM results.

        Returns a dict with structure:
          {case_label: {region: {country: {year: {season: price}}}}}
        """
        prices: dict[str, Any] = {}
        rep_mass_bal = results.get("rep_mass_bal", {})
        records = rep_mass_bal.get("records", [])

        for rec in records:
            # rep_mass_bal records have keys:
            # case, rgn, cn, node, year, season, sign, type, value
            vals = list(rec.values())
            if len(vals) >= 9 and vals[6] == "0" and vals[7] == "price":
                case, rgn, cn, _node, year, season = vals[:6]
                price_val = vals[8]
                prices.setdefault(case, {}).setdefault(
                    rgn, {}
                ).setdefault(cn, {}).setdefault(
                    year, {}
                )[season] = price_val

        return prices

    def extract_production_by_country(
        self, results: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract country-level production from the geo_map report.

        Returns {case_label: {region: {country: {year: production_bcma}}}}.
        """
        production: dict[str, Any] = {}
        rep_geo_map = results.get("rep_geo_map", {})
        records = rep_geo_map.get("records", [])

        for rec in records:
            vals = list(rec.values())
            if len(vals) >= 6 and vals[4] == "prod":
                case, rgn, cn, year = vals[0], vals[1], vals[2], vals[3]
                val = vals[5]
                production.setdefault(case, {}).setdefault(
                    rgn, {}
                ).setdefault(cn, {})[year] = val

        return production

    def extract_trade_flows(
        self, results: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract regional trade flow data from the geo_trade report.

        Returns {case: {exporter_region: {exporter: {importer_region: {importer: {year: flow}}}}}}.
        """
        flows: dict[str, Any] = {}
        rep_geo_trade = results.get("rep_geo_trade", {})
        records = rep_geo_trade.get("records", [])

        for rec in records:
            vals = list(rec.values())
            if len(vals) >= 7:
                case, exp_rgn, exp_cn, imp_rgn, imp_cn, year, val = vals[:7]
                (
                    flows.setdefault(case, {})
                    .setdefault(exp_rgn, {})
                    .setdefault(exp_cn, {})
                    .setdefault(imp_rgn, {})
                    .setdefault(imp_cn, {})
                )[year] = val

        return flows
