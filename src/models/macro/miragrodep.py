"""MIRAGRODEPAdapter — GAMS-driven multi-region agricultural CGE.

MIRAGRODEP (Model of International Relations in Agriculture with a Global
Recursive-Dynamic framework for Economic Projections) is a multi-region
GAMS-based CGE with detailed agricultural sector representation. The
local distribution lives at::

    Models/General Equilibrium/MIRAGRODEP_v0-1/MIRAGRODEP_v0-1/

The model is solved in three sequential GAMS phases that mirror the
recipes in ``miragrodep.gpr``:

    1. **calib**  — ``calib.gms`` builds the calibration restart
       (``Restart/calib`` + GDX ``GDX/calib.gdx``).
    2. **MSD**    — ``MSD.gms`` builds the MSD restart (``Restart/msd``).
    3. **REF**    — ``REF.gms`` runs from the MSD restart and produces
       the reference baseline (``Restart/ref``).
    4. **Simul**  — ``Simul.gms`` runs from the REF restart and applies
       the shock include files written by this adapter, producing the
       scenario solution (``Restart/simul``) and the result CSVs in
       ``Results/`` (``var.csv``, ``R_var.csv``, ``RS_var.csv``,
       ``IR_var.csv``).

This adapter does NOT subclass ``GAMSAdapter`` because MIRAGRODEP uses
GAMS save/restart between phases (``s=`` and ``r=`` switches) rather
than a single self-contained job. Instead it invokes the ``gams`` CLI
directly via subprocess for each phase, isolated to a writable working
copy of the model directory.

Real implementation requirements:
- A GAMS installation (the version that produced the .gpr restart files;
  v37+ has been verified). Set the GAMS bin dir on PATH or pass
  ``gams_executable`` explicitly.
- A licensed CONOPT or PATH solver (MIRAGRODEP defaults to CONOPT).
- The MIRAGRODEP source tree at ``model_dir`` (default points to the
  in-repo distribution).
- Optional GTAP data — bundled in the v0-1 distribution.
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

DEFAULT_MIRAGRODEP_DIR = Path(
    "Models/General Equilibrium/MIRAGRODEP_v0-1/MIRAGRODEP_v0-1"
)


class MIRAGRODEPConfig(BaseModel):
    """Configuration for the MIRAGRODEP GAMS driver."""

    model_dir: Path = Field(
        default=DEFAULT_MIRAGRODEP_DIR,
        description="Root of the MIRAGRODEP source tree (contains Simul.gms, etc.)",
    )
    gams_executable: str = Field(
        default="gams",
        description="Path or name of the GAMS executable",
    )
    solver: str = Field(
        default="CONOPT",
        description="GAMS solver to use",
    )
    calib_gms: str = Field(
        default="calib.gms",
        description="Calibration GAMS file (run first)",
    )
    msd_gms: str = Field(
        default="MSD.gms",
        description="MSD shock data GAMS file (run second)",
    )
    ref_gms: str = Field(
        default="REF.gms",
        description="Reference baseline GAMS file (run third)",
    )
    simul_gms: str = Field(
        default="Simul.gms",
        description="Scenario simulation GAMS file (run last)",
    )
    results_subdir: str = Field(
        default="Results",
        description="Subdirectory under model_dir where Simul.gms writes CSV results",
    )
    skip_calib_if_present: bool = Field(
        default=True,
        description=(
            "If True, skip calib + MSD + REF when GAMS save files for them "
            "already exist in the working directory (saves ~hours per scenario)."
        ),
    )
    timeout_seconds: int = Field(
        default=14400,
        description="Per-phase GAMS timeout (default 4 hours)",
    )
    keep_working_copy: bool = Field(
        default=False,
        description="Keep the per-scenario working copy after completion",
    )
    extra_gams_args: list[str] = Field(
        default_factory=lambda: ["lo=2", "ll=0"],
        description="Extra GAMS command-line flags",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "fertilizer_price_shock_pct",
        "agricultural_trade_disruption_spec",
        "disruption_duration_months",
    }
)

# MIRAGRODEP region set (from Results.gms r_(r) Set)
MIRAGRODEP_REGIONS = {
    "ROW", "CHN", "JPN", "KOR", "XAS", "IND", "CAN", "USA",
    "MEX", "XSM", "BRA", "EU27", "XER", "SSA",
}

# MIRAGRODEP sector codes that the shock translator understands.
MIRAGRODEP_SECTORS = {
    "cere", "oagr", "suga", "meat", "natres", "fish", "ffl",
    "ofd", "tex", "wpp", "crp", "mmet", "omf", "elec", "ome",
    "serv", "trade", "trans",
}


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class MIRAGRODEPAdapter(ModelAdapter):
    """Live GAMS adapter for MIRAGRODEP.

    Drives the calib → MSD → REF → Simul phase sequence via the GAMS CLI,
    writes shock include files between MSD and Simul, and parses the
    resulting Results/*.csv files into the standardized ModelOutput
    schema.
    """

    def __init__(self, config: MIRAGRODEPConfig | None = None) -> None:
        self._config = config or MIRAGRODEPConfig()

    @property
    def model_id(self) -> str:
        return "miragrodep"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "MIRAGRODEP: multi-region recursive-dynamic CGE with detailed "
            "agricultural sector representation. Live GAMS adapter driving "
            "the calib→MSD→REF→Simul phase sequence with pipeline-supplied "
            "energy / fertilizer / trade shocks."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=4,
            memory_gb=16.0,
            supports_multi_threading=True,
            max_threads=4,
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

        oil_shock = params["oil_price_shock_pct"]
        if not isinstance(oil_shock, (int, float)):
            errors.append(
                f"'oil_price_shock_pct' must be numeric; got {type(oil_shock).__name__}"
            )
        elif oil_shock < -100.0:
            errors.append(
                f"'oil_price_shock_pct' cannot be less than -100%; got {oil_shock}"
            )
        elif oil_shock > 500.0:
            warnings.append(
                f"'oil_price_shock_pct' is {oil_shock}%, implying more than a 5x "
                "price increase. Verify consistency with commodity-level oil model outputs."
            )

        fert_shock = params["fertilizer_price_shock_pct"]
        if not isinstance(fert_shock, (int, float)):
            errors.append(
                f"'fertilizer_price_shock_pct' must be numeric; got {type(fert_shock).__name__}"
            )
        elif fert_shock < -100.0:
            errors.append(
                f"'fertilizer_price_shock_pct' cannot be less than -100%; got {fert_shock}"
            )
        elif fert_shock > 500.0:
            warnings.append(
                f"'fertilizer_price_shock_pct' is {fert_shock}%, which implies more than "
                "a 5x price increase. Verify consistency with fertilizer model outputs."
            )

        if (
            isinstance(oil_shock, (int, float))
            and isinstance(fert_shock, (int, float))
            and oil_shock < 10.0
            and fert_shock > 100.0
        ):
            warnings.append(
                f"'fertilizer_price_shock_pct' ({fert_shock}%) is large relative to "
                f"'oil_price_shock_pct' ({oil_shock}%). Fertilizer prices are strongly "
                "linked to natural gas prices; verify this combination is intentional."
            )

        trade_spec = params["agricultural_trade_disruption_spec"]
        if not isinstance(trade_spec, dict) or len(trade_spec) == 0:
            errors.append(
                "'agricultural_trade_disruption_spec' must be a non-empty dict describing "
                "the agricultural trade shock (e.g., {'affected_corridors': [...], "
                "'shipping_cost_multiplier': 1.3, 'affected_commodities': [...]})"
            )
        else:
            corridors = trade_spec.get("affected_corridors") or []
            for corridor in corridors:
                # corridors are typically (origin, destination) tuples or strings
                if isinstance(corridor, (list, tuple)) and len(corridor) >= 2:
                    for region in corridor[:2]:
                        if str(region) not in MIRAGRODEP_REGIONS:
                            warnings.append(
                                f"Trade corridor region '{region}' is not in "
                                f"MIRAGRODEP_REGIONS ({sorted(MIRAGRODEP_REGIONS)})"
                            )
            commodities = trade_spec.get("affected_commodities") or []
            for c in commodities:
                if str(c) not in MIRAGRODEP_SECTORS:
                    warnings.append(
                        f"Trade commodity '{c}' is not a MIRAGRODEP sector; "
                        f"valid sectors: {sorted(MIRAGRODEP_SECTORS)}"
                    )

        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append(
                f"'disruption_duration_months' must be numeric; got {type(duration).__name__}"
            )
        elif duration <= 0:
            errors.append(f"'disruption_duration_months' must be positive; got {duration}")
        elif duration > 24:
            warnings.append(
                f"'disruption_duration_months' is {duration}, which exceeds the "
                "expected scenario range (0–24 months). Verify this is intentional."
            )

        # Surface integration prerequisites.
        model_dir = Path(self._config.model_dir)
        if not model_dir.exists():
            warnings.append(
                f"MIRAGRODEP model_dir does not exist: {model_dir}. "
                "execute() will fail until you point model_dir at the source tree."
            )
        else:
            for needed in (
                self._config.calib_gms, self._config.msd_gms,
                self._config.ref_gms, self._config.simul_gms,
            ):
                if not (model_dir / needed).exists():
                    warnings.append(
                        f"MIRAGRODEP source file '{needed}' not found in {model_dir}"
                    )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate pipeline shocks into the MIRAGRODEP shock spec.

        Returns a dict with:
            scenario_id
            oil_price_shock_pct
            fertilizer_price_shock_pct
            trade_spec       (the original dict)
            duration_years
        """
        scenario_id = params.get("scenario_id", "default")
        return {
            "scenario_id": scenario_id,
            "oil_price_shock_pct": float(params["oil_price_shock_pct"]),
            "fertilizer_price_shock_pct": float(params["fertilizer_price_shock_pct"]),
            "trade_spec": dict(params["agricultural_trade_disruption_spec"]),
            "duration_years": float(params["disruption_duration_months"]) / 12.0,
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Drive MIRAGRODEP via four sequential GAMS subprocess calls."""
        cfg = self._config
        scenario_id = inputs["scenario_id"]
        model_dir = Path(cfg.model_dir).resolve()

        if not model_dir.exists():
            raise FileNotFoundError(
                f"MIRAGRODEP model_dir not found: {model_dir}. "
                "Set MIRAGRODEPConfig.model_dir or place the MIRAGRODEP source tree "
                f"at {DEFAULT_MIRAGRODEP_DIR} relative to the project root."
            )

        # Use an isolated working copy so concurrent scenario runs don't
        # collide on Restart/, GDX/, Results/.
        work_dir = Path(tempfile.mkdtemp(prefix=f"miragrodep_{scenario_id}_"))
        try:
            self._copy_model_tree(model_dir, work_dir)

            # Phase 1: calib (skippable if a saved restart already exists).
            saved_calib = work_dir / "Restart" / "calib.g00"
            if not saved_calib.exists() or not cfg.skip_calib_if_present:
                self._run_phase(
                    work_dir, cfg.calib_gms,
                    save="calib", restart=None,
                    extra_defines={"TFP": "1"},
                )

            # Phase 2: MSD
            saved_msd = work_dir / "Restart" / "msd.g00"
            if not saved_msd.exists() or not cfg.skip_calib_if_present:
                self._run_phase(
                    work_dir, cfg.msd_gms,
                    save="msd", restart="calib",
                )

            # Phase 3: REF
            saved_ref = work_dir / "Restart" / "ref.g00"
            if not saved_ref.exists() or not cfg.skip_calib_if_present:
                self._run_phase(
                    work_dir, cfg.ref_gms,
                    save="ref", restart="msd",
                )

            # Phase 4: write shock include files, then run Simul.
            self._write_shock_includes(work_dir, inputs)
            start = time.time()
            self._run_phase(
                work_dir, cfg.simul_gms,
                save="simul", restart="ref",
            )
            elapsed = time.time() - start

            outputs = self._parse_results(work_dir)
            outputs["_applied_shocks"] = {
                "oil_price_shock_pct": inputs["oil_price_shock_pct"],
                "fertilizer_price_shock_pct": inputs["fertilizer_price_shock_pct"],
                "trade_spec": inputs["trade_spec"],
                "duration_years": inputs["duration_years"],
            }

            return ModelOutput(
                model_id=self.model_id,
                outputs=outputs,
                convergence_status="completed",
                metadata={
                    "scenario_id": scenario_id,
                    "work_dir": str(work_dir) if cfg.keep_working_copy else None,
                    "model_dir": str(model_dir),
                    "elapsed_seconds_simul": elapsed,
                },
            )
        finally:
            if not cfg.keep_working_copy:
                shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # GAMS subprocess driver
    # ------------------------------------------------------------------

    def _copy_model_tree(self, src: Path, dest: Path) -> None:
        """Copy the MIRAGRODEP source tree to an isolated working dir."""
        # copytree fails if dest exists; tempfile.mkdtemp pre-creates it,
        # so we copy contents instead of the directory.
        for item in src.iterdir():
            target = dest / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        # Ensure standard subdirs exist.
        for sub in ("Restart", "GDX", "Results"):
            (dest / sub).mkdir(exist_ok=True)

    def _run_phase(
        self,
        work_dir: Path,
        gms_file: str,
        save: str | None,
        restart: str | None,
        extra_defines: dict[str, str] | None = None,
    ) -> None:
        """Invoke ``gams <file>`` with save / restart / define arguments."""
        cfg = self._config
        cmd = [cfg.gams_executable, gms_file]

        if save is not None:
            cmd.append(f"s=Restart/{save}")
        if restart is not None:
            cmd.append(f"r=Restart/{restart}")
        if extra_defines:
            for key, val in extra_defines.items():
                cmd.append(f"--{key}={val}")

        cmd.extend(cfg.extra_gams_args)

        logger.info(
            "MIRAGRODEP: running phase %s (save=%s restart=%s)",
            gms_file, save, restart,
        )

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cfg.timeout_seconds,
            cwd=str(work_dir),
        )

        if proc.returncode != 0:
            # Capture the LST file for diagnostics if available.
            lst_path = work_dir / (Path(gms_file).stem + ".lst")
            lst_tail = ""
            if lst_path.exists():
                try:
                    lst_tail = lst_path.read_text(encoding="utf-8", errors="replace")[-3000:]
                except OSError:
                    pass

            raise RuntimeError(
                f"MIRAGRODEP phase '{gms_file}' failed (rc={proc.returncode}).\n"
                f"stderr tail:\n{(proc.stderr or '')[-2000:]}\n"
                f"stdout tail:\n{(proc.stdout or '')[-1000:]}\n"
                f"LST tail:\n{lst_tail}"
            )

    # ------------------------------------------------------------------
    # Shock injection
    # ------------------------------------------------------------------

    def _write_shock_includes(
        self, work_dir: Path, inputs: dict[str, Any],
    ) -> None:
        """Write the three shock include files Simul.gms reads in.

        Convention: Simul.gms uses ``$include shock_oil.inc`` /
        ``$include shock_fertilizer.inc`` / ``$include shock_trade.inc``
        guarded by ``$ifThen.exist``. If those statements are not present
        in the bundled Simul.gms, the analyst must add them once. The
        files are written every run so the latest scenario shocks are used.
        """
        oil_pct = inputs["oil_price_shock_pct"]
        fert_pct = inputs["fertilizer_price_shock_pct"]
        trade = inputs["trade_spec"]

        # ---- shock_oil.inc -----------------------------------------------
        # Multiplicative price shock on the 'ffl' (fossil fuel) sector via
        # the production tax (taxP). Formulation: tax_new = tax_old + shock.
        oil_factor = oil_pct / 100.0
        oil_inc = self._format_inc(
            "Pipeline-injected oil price shock",
            f"taxPend('ffl', r, Temps, 'sim') = taxP('ffl', r, Temps, 'ref') + {oil_factor};",
            f"taxccend('ffl', r, Temps, 'sim') = taxcc('ffl', r, Temps, 'ref') + {oil_factor};",
        )
        (work_dir / "shock_oil.inc").write_text(oil_inc, encoding="utf-8")

        # ---- shock_fertilizer.inc ----------------------------------------
        # Multiplicative price shock on the 'crp' (chemicals/fertilizer) sector.
        fert_factor = fert_pct / 100.0
        fert_inc = self._format_inc(
            "Pipeline-injected fertilizer price shock",
            f"taxPend('crp', r, Temps, 'sim') = taxP('crp', r, Temps, 'ref') + {fert_factor};",
            f"taxccend('crp', r, Temps, 'sim') = taxcc('crp', r, Temps, 'ref') + {fert_factor};",
        )
        (work_dir / "shock_fertilizer.inc").write_text(fert_inc, encoding="utf-8")

        # ---- shock_trade.inc ---------------------------------------------
        corridors = trade.get("affected_corridors") or []
        commodities = trade.get("affected_commodities") or list(MIRAGRODEP_SECTORS)
        cost_mult = trade.get("shipping_cost_multiplier", 1.0)
        try:
            cost_pct = (float(cost_mult) - 1.0)
        except (TypeError, ValueError):
            cost_pct = 0.0

        trade_lines: list[str] = []
        for corridor in corridors:
            if isinstance(corridor, (list, tuple)) and len(corridor) >= 2:
                origin, dest = str(corridor[0]), str(corridor[1])
            elif isinstance(corridor, str) and "-" in corridor:
                origin, dest = corridor.split("-", 1)
            else:
                continue
            if origin not in MIRAGRODEP_REGIONS or dest not in MIRAGRODEP_REGIONS:
                continue
            for c in commodities:
                if str(c) not in MIRAGRODEP_SECTORS:
                    continue
                trade_lines.append(
                    f"taxAMFend('{c}', '{origin}', '{dest}', Temps, 'sim') = "
                    f"taxAMF('{c}', '{origin}', '{dest}', Temps, 'ref') + {cost_pct};"
                )
                trade_lines.append(
                    f"taxEXPend('{c}', '{origin}', '{dest}', Temps, 'sim') = "
                    f"taxEXP('{c}', '{origin}', '{dest}', Temps, 'ref') + {cost_pct};"
                )

        if not trade_lines:
            trade_lines.append("* No affected corridors specified; trade shock is a no-op.")

        trade_inc = self._format_inc(
            "Pipeline-injected agricultural trade shock", *trade_lines
        )
        (work_dir / "shock_trade.inc").write_text(trade_inc, encoding="utf-8")

    @staticmethod
    def _format_inc(header: str, *statements: str) -> str:
        body = "\n".join(statements)
        return (
            f"*-------------------------------------------------------------------------------\n"
            f"* {header}\n"
            f"* Auto-generated by MIRAGRODEPAdapter — do not edit by hand.\n"
            f"*-------------------------------------------------------------------------------\n"
            f"{body}\n"
        )

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_results(self, work_dir: Path) -> dict[str, Any]:
        """Read Results/*.csv into a serializable dict.

        Columns vary across the four MIRAGRODEP result files; we treat each
        CSV as a flat list of records (with column headers preserved).
        """
        results_dir = work_dir / self._config.results_subdir
        out: dict[str, Any] = {"_results_dir": str(results_dir)}

        if not results_dir.exists():
            out["_warning"] = (
                f"Results directory {results_dir} not found. Simul.gms may "
                "have failed silently; check the LST file."
            )
            return out

        for csv_name, std_key in (
            ("var.csv",    "world_aggregate_vars"),
            ("R_var.csv",  "regional_vars"),
            ("RS_var.csv", "regional_sectoral_vars"),
            ("IR_var.csv", "interregional_vars"),
        ):
            csv_path = results_dir / csv_name
            if not csv_path.exists():
                continue
            out[std_key] = self._read_csv(csv_path)

        # Extract a couple of headline scalars for cross-model consistency
        # checks (welfare and GDP if present in regional_vars).
        regional = out.get("regional_vars") or []
        for record in regional:
            var_name = (
                record.get("var") or record.get("variable") or record.get("name")
            )
            if not var_name:
                continue
            label = str(var_name).strip().lower()
            try:
                value = float(record.get("value") or record.get("val") or "nan")
            except (TypeError, ValueError):
                continue
            if label in {"welfare", "ev", "wwelf", "varwwelf"}:
                out.setdefault("welfare_pct_change", value)
            elif label in {"gdp", "gdpvol", "gdp_pct"}:
                out.setdefault("gdp_impact_pct", value)

        return out

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, Any]]:
        """Read a CSV into a list of {column: value} dicts."""
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                return [dict(row) for row in reader]
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return []

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
