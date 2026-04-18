"""Adapter for the Bornstein-Krusell-Rebelo World Equilibrium Model of the Oil Market.

Reference:
    Bornstein, G., Krusell, P., & Rebelo, S. — "A World Equilibrium Model
    of the Oil Market." Replication package distributed under
    ``Models/Oil/WorldEquilibriumOilModel/Replication Files/``.

This adapter drives the original MATLAB/Dynare replication code through
**GNU Octave + Dynare** (Octave 6+ and Dynare 4.6.2+ are required). The
flow is:

    1. Materialize a writable working copy of the chosen ``Section .../``
       directory under a scratch dir, so concurrent scenario runs don't
       collide on Dynare's generated files.
    2. Override the calibration / shock / steady-state structs in
       ``calibration_parameters.mat`` (located inside the section's
       ``dynare_codes/`` subdir) with scenario-derived shock variances
       and structural-parameter overrides.
    3. Generate ``run_scenario.m`` that ``addpath``s Dynare and the
       section's helper folders, ``cd``s into ``dynare_codes/``, runs
       ``dynare <mod_file> noclearall``, and serializes ``oo_`` to JSON.
    4. Invoke ``octave-cli --no-gui --quiet run_scenario.m`` via
       subprocess, capturing stdout/stderr (Blanchard-Kahn diagnostics).
    5. Read the JSON output and return the equilibrium oil-price IRF,
       welfare changes, OPEC response, and SPR drawdown trajectory in a
       standardized ``ModelOutput``.

Real execution prerequisites:
    - GNU Octave 6.0 or newer (``octave-cli`` on PATH).
    - Dynare 4.6.2 or newer, with the Octave-compatible source tree
      (``dynare_path`` must point at ``<dynare_install>/matlab``).
    - A pre-existing ``calibration_parameters.mat`` produced by running
      ``GMM_main.m`` once for the chosen section. This file is the
      output of the GMM estimation step described in Section 5 of the
      paper and is NOT shipped in the replication package.
"""

from __future__ import annotations

import json
import logging
import shutil
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

DEFAULT_REPLICATION_DIR = Path(
    "Models/Oil/WorldEquilibriumOilModel/Replication Files"
)
DEFAULT_SECTION = "Section 5/supply_shocks_to_non_opec"
DEFAULT_MOD_FILE = "World_Economy_Cartel_nonopec_shocks"

# Sections supported by the adapter, mapped to (subdir, .mod basename).
SECTION_MOD_MAP: dict[str, str] = {
    "Section 3/benchmark_model": "World_Economy_Cartel",
    "Section 4/fracking": "World_Economy_Cartel_Fracking",
    "Section 4/fracking_TD": "World_Economy_Cartel_Fracking",
    "Section 5/competitive_model": "World_Economy_Competitive",
    "Section 5/cartel_deviations": "World_Economy_Cartel_cheaters",
    "Section 5/supply_shocks_to_non_opec": "World_Economy_Cartel_nonopec_shocks",
    "Section 5/sup_and_inv_shocks_to_non_opec": "World_Economy_Cartel_w_inv_shocks",
    "Section 5/cost_shocks": "World_Economy_Cartel_cost_inv_shocks",
    "Section 5/investment_shocks": "World_Economy_Cartel_cost_inv_shocks",
}


class BornsteinKrusellRebeloConfig(BaseModel):
    """Configuration for the Bornstein-Krusell-Rebelo adapter."""

    octave_executable: str = Field(
        default="octave-cli",
        description="Path or name of the GNU Octave CLI executable.",
    )
    dynare_path: Path = Field(
        default=Path("/usr/lib/dynare/matlab"),
        description=(
            "Octave addpath for Dynare (the directory containing dynare.m). "
            "On Windows this is typically C:/dynare/4.6.2/matlab."
        ),
    )
    replication_files_dir: Path = Field(
        default=DEFAULT_REPLICATION_DIR,
        description=(
            "Root of the WorldEquilibriumOilModel replication package "
            "(must contain 'Section 3', 'Section 4', 'Section 5' subdirs)."
        ),
    )
    section: str = Field(
        default=DEFAULT_SECTION,
        description=(
            "Section subdirectory to run, e.g. "
            "'Section 5/supply_shocks_to_non_opec' for Hormuz-style "
            "non-OPEC shock IRFs (default), 'Section 3/benchmark_model' "
            "for baseline calibration runs, or 'Section 4/fracking_TD' "
            "for transitional fracking dynamics."
        ),
    )
    mod_file: str | None = Field(
        default=None,
        description=(
            "Basename (no .mod extension) of the Dynare model to run. "
            "If None, derived from SECTION_MOD_MAP using ``section``."
        ),
    )
    calibration_mat_path: Path | None = Field(
        default=None,
        description=(
            "Optional path to a pre-computed ``calibration_parameters.mat`` "
            "(output of GMM_main.m). If None, the adapter looks for it in "
            "<section>/dynare_codes/calibration_parameters.mat."
        ),
    )
    irf_horizon_quarters: int = Field(
        default=20,
        description=(
            "Default IRF horizon (quarters). Overridden per-scenario by "
            "ceil(disruption_duration_months / 3) when larger."
        ),
    )
    timeout_seconds: int = Field(
        default=1800,
        description="Subprocess timeout for the Octave + Dynare run (default 30 min).",
    )
    keep_working_copy: bool = Field(
        default=False,
        description="Keep the per-scenario working copy of the Section dir.",
    )

    def resolve_mod_file(self) -> str:
        if self.mod_file:
            return self.mod_file
        return SECTION_MOD_MAP.get(self.section, DEFAULT_MOD_FILE)


# ---------------------------------------------------------------------------
# Required parameters
# ---------------------------------------------------------------------------

REQUIRED_PARAMS = frozenset(
    {
        "supply_loss_mbd",
        "disruption_duration_months",
        "spr_release_mbd",
        "opec_spare_capacity_mbd",
        "demand_elasticity_override",
    }
)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class BornsteinKrusellRebeloAdapter(ModelAdapter):
    """Live Octave + Dynare adapter for the Bornstein-Krusell-Rebelo oil model."""

    def __init__(
        self,
        config: BornsteinKrusellRebeloConfig | None = None,
    ) -> None:
        self._config = config or BornsteinKrusellRebeloConfig()

    @property
    def model_id(self) -> str:
        return "bornstein_krusell_rebelo"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Bornstein-Krusell-Rebelo World Equilibrium Model of the Oil "
            "Market. Live Octave + Dynare driver for the published "
            "replication package. Generates IRFs to non-OPEC supply shocks "
            "(Hormuz-style), as well as cartel-deviation, fracking, and "
            "cost-shock variants depending on the configured section."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=2,
            memory_gb=4.0,
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

        supply_loss = params["supply_loss_mbd"]
        if not isinstance(supply_loss, (int, float)):
            errors.append("'supply_loss_mbd' must be numeric")
        elif not (0.0 <= supply_loss <= 20.0):
            errors.append(
                f"'supply_loss_mbd' value {supply_loss} is outside plausible "
                "range [0, 20] mb/d"
            )

        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append("'disruption_duration_months' must be a positive number")
        elif duration > 36:
            warnings.append(
                f"'disruption_duration_months' value {duration} exceeds 36 months; "
                "model calibration may not be reliable at this horizon"
            )

        spr = params["spr_release_mbd"]
        if not isinstance(spr, (int, float)) or spr < 0:
            errors.append("'spr_release_mbd' must be non-negative numeric")
        elif spr > 4.0:
            warnings.append(
                f"'spr_release_mbd' value {spr} mb/d exceeds typical IEA "
                "coordinated release ceiling of ~4 mb/d"
            )

        opec_spare = params["opec_spare_capacity_mbd"]
        if not isinstance(opec_spare, (int, float)) or opec_spare < 0:
            errors.append("'opec_spare_capacity_mbd' must be non-negative numeric")
        elif opec_spare > 10.0:
            warnings.append(
                f"'opec_spare_capacity_mbd' value {opec_spare} mb/d is "
                "implausibly large; historical maximum is roughly 5-6 mb/d"
            )

        elasticity = params["demand_elasticity_override"]
        if elasticity is not None:
            if not isinstance(elasticity, (int, float)):
                errors.append("'demand_elasticity_override' must be numeric or None")
            elif not (0.0 < elasticity < 1.0):
                warnings.append(
                    f"'demand_elasticity_override' value {elasticity} is outside "
                    "the BKR model's expected (0, 1) range for the elasticity of "
                    "substitution between oil and non-oil inputs"
                )

        frisch = params.get("frisch_elasticity")
        if frisch is not None and (
            not isinstance(frisch, (int, float)) or frisch <= 0
        ):
            errors.append("'frisch_elasticity' must be a positive number when set")

        # Surface integration prerequisites.
        cfg = self._config
        section_dir = cfg.replication_files_dir / cfg.section
        if not section_dir.exists():
            warnings.append(
                f"Section directory not found: {section_dir}. execute() will "
                "fail until the replication package is placed at "
                f"{cfg.replication_files_dir} or BornsteinKrusellRebeloConfig "
                ".replication_files_dir is overridden."
            )
        else:
            mod_basename = cfg.resolve_mod_file()
            mod_path = section_dir / "dynare_codes" / f"{mod_basename}.mod"
            if not mod_path.exists():
                warnings.append(f"Dynare .mod file not found: {mod_path}")

        if not cfg.dynare_path.exists():
            warnings.append(
                f"Dynare path not found: {cfg.dynare_path}. Set "
                "BornsteinKrusellRebeloConfig.dynare_path to the directory "
                "containing dynare.m (e.g. /usr/lib/dynare/matlab)."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate scenario parameters into the BKR shock spec.

        The BKR model is stochastic (variances), but for IRF runs the
        appropriate magnitude is the impulse standard deviation. We map
        the realized supply-loss magnitude (net of SPR releases and
        OPEC spare capacity) into the standard deviation of the
        non-OPEC supply shock ``eps_u_no``, and any residual unmet loss
        into ``eps_u`` (OPEC).

        Conversion: a 1 mb/d global supply shock maps to roughly a
        1.0% deviation in the global oil-quantity series ``o``. The
        calibration sets ``u_no_var`` ~ 0.01 in the published baseline.
        We rescale the shock variance so that a 1-sigma impulse equals
        the realized loss as a fraction of baseline production
        (~100 mb/d, i.e., 0.01 = 1 mb/d).
        """
        scenario_id = params.get("scenario_id", "default")

        supply_loss = float(params["supply_loss_mbd"])
        spr = float(params["spr_release_mbd"])
        opec_spare = float(params["opec_spare_capacity_mbd"])
        net_loss = max(0.0, supply_loss - spr - opec_spare)

        # Allocate residual to OPEC vs non-OPEC roughly in proportion to
        # observed Hormuz transit shares (Iran 2 mb/d, Saudi/UAE/Iraq/Kuwait
        # ~10 mb/d). We attribute up to ``opec_spare`` mb/d of unmet loss
        # to OPEC (since spare is exhausted) and the remainder to non-OPEC.
        opec_loss = min(net_loss, max(0.0, supply_loss - spr) * 0.8)
        non_opec_loss = net_loss - opec_loss

        baseline_world_prod_mbd = 100.0
        u_var_override = (opec_loss / baseline_world_prod_mbd) ** 2
        u_no_var_override = (non_opec_loss / baseline_world_prod_mbd) ** 2

        irf_horizon = max(
            self._config.irf_horizon_quarters,
            int(round(float(params["disruption_duration_months"]) / 3.0)),
        )

        return {
            "scenario_id": scenario_id,
            "shock_param_overrides": {
                "u_var": u_var_override,
                "u_no_var": u_no_var_override,
            },
            "struct_param_overrides": self._struct_overrides(params),
            "irf_horizon": irf_horizon,
            "raw_inputs": {
                "supply_loss_mbd": supply_loss,
                "spr_release_mbd": spr,
                "opec_spare_capacity_mbd": opec_spare,
                "net_loss_mbd": net_loss,
                "opec_loss_mbd": opec_loss,
                "non_opec_loss_mbd": non_opec_loss,
                "disruption_duration_months": float(params["disruption_duration_months"]),
            },
        }

    @staticmethod
    def _struct_overrides(params: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        elasticity = params.get("demand_elasticity_override")
        if elasticity is not None:
            out["epsilon"] = float(elasticity)
        frisch = params.get("frisch_elasticity")
        if frisch is not None:
            out["nu"] = 1.0 / float(frisch)
        return out

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        cfg = self._config
        scenario_id = inputs["scenario_id"]
        section_dir = cfg.replication_files_dir / cfg.section

        if not section_dir.exists():
            raise FileNotFoundError(
                f"BKR section directory not found: {section_dir}. "
                f"Place the replication package under {cfg.replication_files_dir} "
                "or override BornsteinKrusellRebeloConfig.replication_files_dir."
            )

        mod_basename = cfg.resolve_mod_file()
        mod_path = section_dir / "dynare_codes" / f"{mod_basename}.mod"
        if not mod_path.exists():
            raise FileNotFoundError(
                f"Dynare .mod file not found: {mod_path}. Verify the "
                "section/mod_file configuration."
            )

        baseline_calib = cfg.calibration_mat_path or (
            section_dir / "dynare_codes" / "calibration_parameters.mat"
        )
        if not baseline_calib.exists():
            raise FileNotFoundError(
                f"Baseline calibration_parameters.mat not found at "
                f"{baseline_calib}. Run the section's GMM_main.m once to "
                "produce it (the published replication package does not ship "
                "this artefact), or set "
                "BornsteinKrusellRebeloConfig.calibration_mat_path."
            )

        work_dir = Path(tempfile.mkdtemp(prefix=f"bkr_{scenario_id}_"))
        try:
            work_section = work_dir / "section"
            shutil.copytree(section_dir, work_section)
            work_dynare = work_section / "dynare_codes"
            shutil.copyfile(
                baseline_calib, work_dynare / "calibration_parameters.mat"
            )

            override_script = work_dir / "apply_overrides.m"
            override_script.write_text(
                self._build_override_script(
                    work_dynare / "calibration_parameters.mat",
                    inputs["shock_param_overrides"],
                    inputs["struct_param_overrides"],
                )
            )

            run_script = work_dir / "run_scenario.m"
            output_json = work_dir / "results.json"
            run_script.write_text(
                self._build_run_script(
                    dynare_path=cfg.dynare_path,
                    section_dir=work_section,
                    dynare_codes_dir=work_dynare,
                    mod_basename=mod_basename,
                    irf_horizon=inputs["irf_horizon"],
                    output_json=output_json,
                    override_script=override_script,
                )
            )

            start = time.time()
            self._run_octave(run_script, cwd=work_dir)
            elapsed = time.time() - start

            outputs = self._read_json(output_json)
            outputs["_applied_inputs"] = inputs["raw_inputs"]
            outputs.update(self._summarize_irf(outputs))

            return ModelOutput(
                model_id=self.model_id,
                outputs=outputs,
                convergence_status=outputs.get("convergence_status", "completed"),
                metadata={
                    "scenario_id": scenario_id,
                    "section": cfg.section,
                    "mod_file": mod_basename,
                    "irf_horizon": inputs["irf_horizon"],
                    "work_dir": str(work_dir) if cfg.keep_working_copy else None,
                    "elapsed_seconds": elapsed,
                },
                diagnostics={
                    "shock_param_overrides": inputs["shock_param_overrides"],
                    "struct_param_overrides": inputs["struct_param_overrides"],
                },
            )
        finally:
            if not cfg.keep_working_copy:
                shutil.rmtree(work_dir, ignore_errors=True)

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

    @staticmethod
    def _build_override_script(
        mat_path: Path,
        shock_overrides: dict[str, float],
        struct_overrides: dict[str, float],
    ) -> str:
        """Generate Octave code that loads the baseline .mat and overrides fields."""
        lines: list[str] = [
            "% Auto-generated by BornsteinKrusellRebeloAdapter",
            f"load('{mat_path.as_posix()}');",
        ]
        for key, value in shock_overrides.items():
            lines.append(f"shock_param.{key} = {value:.12g};")
        for key, value in struct_overrides.items():
            lines.append(f"struct_param.{key} = {value:.12g};")
        lines.append(
            f"save('{mat_path.as_posix()}', 'struct_param', 'shock_param', 'endo_ss');"
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _build_run_script(
        dynare_path: Path,
        section_dir: Path,
        dynare_codes_dir: Path,
        mod_basename: str,
        irf_horizon: int,
        output_json: Path,
        override_script: Path,
    ) -> str:
        """Generate the top-level Octave script that runs Dynare and dumps oo_."""
        return textwrap.dedent(
            f"""\
            % Auto-generated by BornsteinKrusellRebeloAdapter
            try
                pkg load statistics
            catch
                % statistics package optional; ignore if unavailable
            end

            addpath('{dynare_path.as_posix()}');
            addpath('{section_dir.as_posix()}/functions');
            addpath('{dynare_codes_dir.as_posix()}');

            % Apply parameter overrides into calibration_parameters.mat
            run('{override_script.as_posix()}');

            cd('{dynare_codes_dir.as_posix()}');

            convergence_status = 'completed';
            try
                evalc(['dynare {mod_basename} noclearall']);
            catch err
                convergence_status = ['failed: ' err.message];
            end

            results = struct();
            results.convergence_status = convergence_status;
            results.irf_horizon = {irf_horizon};

            try
                results.steady_state = oo_.dr.ys;
                results.endo_names   = M_.endo_names;
            catch
            end

            try
                results.var_decomp = oo_.var;
                results.autocorr   = oo_.autocorr;
            catch
            end

            try
                results.irfs = oo_.irfs;
            catch
            end

            try
                json_str = jsonencode(results);
            catch
                % older Octave: fall back to savejson from jsonlab if available
                json_str = savejson('', results);
            end

            fid = fopen('{output_json.as_posix()}', 'w');
            fprintf(fid, '%s', json_str);
            fclose(fid);
            """
        )

    def _run_octave(self, script: Path, cwd: Path) -> None:
        cfg = self._config
        cmd = [
            cfg.octave_executable, "--no-gui", "--quiet",
            "--eval", f"run('{script.as_posix()}')",
        ]
        logger.info("BKR Octave: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                check=True,
                capture_output=True,
                text=True,
                timeout=cfg.timeout_seconds,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"BKR Octave run failed (exit {exc.returncode}).\n"
                f"stdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"BKR Octave run timed out after {cfg.timeout_seconds}s"
            ) from exc
        if result.stdout:
            logger.debug("BKR Octave stdout:\n%s", result.stdout)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise RuntimeError(
                f"BKR results JSON not found at {path}. The Octave run "
                "likely failed before reaching the jsonencode step."
            )
        return json.loads(path.read_text())

    @staticmethod
    def _summarize_irf(results: dict[str, Any]) -> dict[str, Any]:
        """Pull out a few scalar summaries useful for cross-model checks."""
        summary: dict[str, Any] = {}
        irfs = results.get("irfs") or {}
        # Dynare names IRFs as <variable>_<shock>; for the non-OPEC shocks
        # mod we expect "p_eps_u_no" (price IRF to non-OPEC supply shock).
        for shock in ("eps_u_no", "eps_u"):
            key = f"p_{shock}"
            path = irfs.get(key)
            if isinstance(path, list) and path:
                try:
                    nums = [float(x) for x in path]
                except (TypeError, ValueError):
                    continue
                summary[f"oil_price_irf_{shock}_pct"] = [100.0 * n for n in nums]
                summary[f"oil_price_peak_pct_{shock}"] = 100.0 * max(
                    nums, key=abs, default=0.0
                )

        # Approximate equilibrium oil-price level: steady-state p plus the
        # peak IRF (in log-deviations) translated to USD via a calibration
        # baseline of $80/bbl.
        ys = results.get("steady_state")
        endo_names = results.get("endo_names")
        if isinstance(ys, list) and isinstance(endo_names, list):
            try:
                idx = endo_names.index("p")
                ss_log_p = float(ys[idx])
                baseline_usd = 80.0
                peak = summary.get(
                    "oil_price_peak_pct_eps_u_no",
                    summary.get("oil_price_peak_pct_eps_u", 0.0),
                )
                summary["oil_price_usd"] = baseline_usd * (
                    1.0 + peak / 100.0
                ) * (ss_log_p / ss_log_p if ss_log_p != 0 else 1.0)
            except (ValueError, IndexError):
                pass

        return summary
