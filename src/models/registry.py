"""Model registry — maps model IDs to adapter instances.

Supports querying by commodity system and analytical level.
Can optionally load YAML configs from configs/model_configs/ to
instantiate adapters with real execution configurations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.common.logging import get_logger
from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter

logger = get_logger(__name__)


class ModelRegistry:
    """Registry of available domain model adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}

    def register(self, adapter: ModelAdapter) -> None:
        """Register a model adapter instance."""
        if adapter.model_id in self._adapters:
            logger.warning(f"Overwriting existing adapter for {adapter.model_id}")
        self._adapters[adapter.model_id] = adapter
        logger.info(
            f"Registered model: {adapter.model_id} "
            f"({adapter.commodity_system.value}/{adapter.analytical_level.value})"
        )

    def get(self, model_id: str) -> ModelAdapter | None:
        """Get an adapter by model ID."""
        return self._adapters.get(model_id)

    def get_by_commodity_system(
        self, system: CommoditySystem
    ) -> list[ModelAdapter]:
        """Get all adapters for a commodity system."""
        return [
            a for a in self._adapters.values() if a.commodity_system == system
        ]

    def get_by_analytical_level(
        self, level: AnalyticalLevel
    ) -> list[ModelAdapter]:
        """Get all adapters at a given analytical level."""
        return [
            a for a in self._adapters.values() if a.analytical_level == level
        ]

    def all_model_ids(self) -> list[str]:
        """Return all registered model IDs."""
        return list(self._adapters.keys())

    def all_adapters(self) -> list[ModelAdapter]:
        """Return all registered adapters."""
        return list(self._adapters.values())

    def get_gpu_models(self) -> list[ModelAdapter]:
        """Return adapters that require GPU acceleration."""
        return [a for a in self._adapters.values() if a.resource_requirements.requires_gpu]

    def get_cpu_models(self) -> list[ModelAdapter]:
        """Return adapters that do NOT require GPU acceleration."""
        return [a for a in self._adapters.values() if not a.resource_requirements.requires_gpu]

    def get_by_resource_class(self, requires_gpu: bool) -> list[ModelAdapter]:
        """Filter adapters by GPU requirement."""
        return [
            a for a in self._adapters.values()
            if a.resource_requirements.requires_gpu == requires_gpu
        ]

    def total_gpu_memory_required(self) -> float:
        """Sum of GPU memory requirements across all GPU models (GB)."""
        return sum(
            a.resource_requirements.gpu_memory_gb
            for a in self._adapters.values()
            if a.resource_requirements.requires_gpu
        )

    def __len__(self) -> int:
        return len(self._adapters)


def default_config_dir() -> Path | None:
    """Resolve ``configs/model_configs/`` from the project root, or None.

    Used by the SLURM stage scripts and the LangGraph nodes so that
    ``build_default_registry()`` is rarely called without a ``config_dir``.
    Without this, configured adapters (OSeMOSYS, NEMS, MAM, MIRAGRODEP,
    OpenCGE, BKR, MESSAGEix, TEMOA, MAgPIE, GGM, SahysMod, CWatM, ...)
    silently fall back to default paths that do not exist on the cluster
    and raise ``FileNotFoundError`` at execute time.
    """
    root = Path(__file__).resolve().parents[2]
    cfg = root / "configs" / "model_configs"
    return cfg if cfg.exists() else None


def _load_yaml_config(config_path: Path) -> dict[str, Any] | None:
    """Load a YAML config file, returning None if not found or invalid."""
    if not config_path.exists():
        return None
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load config {config_path}: {e}")
        return None


def _build_ggm_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build GGMAdapter with optional YAML config."""
    from src.models.lng.ggm import GGMAdapter, GGMConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "ggm.yaml")
        if raw and raw.get("gams_system_dir") and raw.get("model_dir"):
            config = GGMConfig(
                gams_system_dir=Path(raw["gams_system_dir"]),
                model_dir=Path(raw["model_dir"]),
                solver=raw.get("solver", "CPLEX"),
                timeout_seconds=raw.get("timeout_seconds", 7200),
                gams_executable=raw.get("gams_executable", "gams"),
                keep_working_copy=raw.get("keep_working_copy", False),
            )
            logger.info("GGMAdapter: loaded GGMConfig from ggm.yaml")
            return GGMAdapter(config=config)

    return GGMAdapter()


def _build_magpie_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build MAgPIEAdapter with optional YAML config."""
    from src.models.fertilizer.magpie import MAgPIEAdapter

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "magpie.yaml")
        if raw and raw.get("r_script_path"):
            from src.models.adapters.r_adapter import RConfig
            r_libs = raw.get("r_libs_path")
            config = RConfig(
                r_script_path=Path(raw["r_script_path"]),
                r_executable=raw.get("r_executable", "Rscript"),
                timeout_seconds=raw.get("timeout_seconds", 14400),
                extra_args=raw.get("extra_args", ["--vanilla"]),
                r_libs_path=Path(r_libs) if r_libs else None,
            )
            logger.info("MAgPIEAdapter: loaded RConfig from magpie.yaml")
            return MAgPIEAdapter(config=config)

    return MAgPIEAdapter()


def _build_opencge_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build OpenCGEAdapter with optional YAML config."""
    from src.models.macro.opencge import OpenCGEAdapter, OpenCGEConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "opencge.yaml")
        if raw:
            ogusa_data = raw.get("ogusa_data_dir")
            cfg_kwargs = {
                "baseline_dir": Path(raw.get("baseline_dir", "data/opencge/baseline")),
                "reform_dir": Path(raw.get("reform_dir", "data/opencge/reform")),
                "num_workers": raw.get("num_workers", 4),
                "time_path_iter": raw.get("time_path_iter", 200),
                "solution_method": raw.get("solution_method", "TPI"),
                "closure_rule": raw.get("closure_rule", "full_employment"),
                "baseline_year": raw.get("baseline_year", 2026),
                "budget_balance": raw.get("budget_balance", False),
                "skip_baseline_if_present": raw.get("skip_baseline_if_present", True),
                "timeout_seconds": raw.get("timeout_seconds", 14400),
            }
            if ogusa_data:
                cfg_kwargs["ogusa_data_dir"] = Path(ogusa_data)
            mapping = raw.get("shock_to_productivity")
            if mapping:
                cfg_kwargs["shock_to_productivity"] = mapping
            config = OpenCGEConfig(**cfg_kwargs)
            logger.info("OpenCGEAdapter: loaded OpenCGEConfig from opencge.yaml")
            return OpenCGEAdapter(config=config)

    return OpenCGEAdapter()


def _build_pycge_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build PyCGEAdapter with optional YAML config."""
    from src.models.macro.pycge import PyCGEAdapter, PyCGEConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "pycge.yaml")
        if raw:
            mdef = raw.get("model_definition_path")
            cfg_kwargs = {
                "sam_path": Path(raw.get("sam_path", "data/sams/hosoe_2region.json")),
                "numeraire": raw.get("numeraire", "px[capital]"),
                "solver": raw.get("solver", "root"),
                "tol": raw.get("tol", 1e-8),
                "max_iter": raw.get("max_iter", 2000),
                "baseline_cache_path": Path(
                    raw.get("baseline_cache_path", "data/pycge_baseline.pkl")
                ),
                "rebuild_baseline": raw.get("rebuild_baseline", False),
                "timeout_seconds": raw.get("timeout_seconds", 600),
            }
            if mdef:
                cfg_kwargs["model_definition_path"] = Path(mdef)
            mapping = raw.get("commodity_to_sam_param")
            if mapping:
                cfg_kwargs["commodity_to_sam_param"] = mapping
            config = PyCGEConfig(**cfg_kwargs)
            logger.info("PyCGEAdapter: loaded PyCGEConfig from pycge.yaml")
            return PyCGEAdapter(config=config)

    return PyCGEAdapter()


def _build_mam_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build MAMAdapter with optional YAML config."""
    import os

    from src.models.macro.mam import MAMAdapter, MAMConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "mam.yaml")
        if raw:
            xlsx = raw.get("aeo_macro_xlsx_path")
            eviews_exe = raw.get("eviews_executable")
            mam_dir = raw.get("mam_program_dir")
            cfg_kwargs = {
                "mode": raw.get("mode", "aeo_ingestion"),
                "aeo_year": raw.get("aeo_year", 2025),
                "scenario_sheet_mapping": raw.get("scenario_sheet_mapping", {}),
                "eviews_main_program": raw.get("eviews_main_program", "mam_main.prg"),
                "timeout_seconds": raw.get("timeout_seconds", 3600),
            }
            # Environment override (set by the SLURM driver after
            # auto-vendoring the AEO XLSX) takes precedence over the
            # YAML so the cluster job stays generic across users.
            env_xlsx = os.environ.get("HORMUZ_MAM_AEO_XLSX_PATH")
            if env_xlsx:
                cfg_kwargs["aeo_macro_xlsx_path"] = Path(env_xlsx)
            elif xlsx:
                cfg_kwargs["aeo_macro_xlsx_path"] = Path(xlsx)
            if eviews_exe:
                cfg_kwargs["eviews_executable"] = Path(eviews_exe)
            if mam_dir:
                cfg_kwargs["mam_program_dir"] = Path(mam_dir)
            config = MAMConfig(**cfg_kwargs)
            logger.info("MAMAdapter: loaded MAMConfig from mam.yaml")
            return MAMAdapter(config=config)

    # No YAML config — still honour the env var so a freshly cloned
    # repo on the cluster picks up the auto-vendored XLSX.
    env_xlsx = os.environ.get("HORMUZ_MAM_AEO_XLSX_PATH")
    if env_xlsx:
        return MAMAdapter(config=MAMConfig(aeo_macro_xlsx_path=Path(env_xlsx)))
    return MAMAdapter()


def _build_miragrodep_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build MIRAGRODEPAdapter with optional YAML config."""
    from src.models.macro.miragrodep import MIRAGRODEPAdapter, MIRAGRODEPConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "miragrodep.yaml")
        if raw:
            cfg_kwargs = {
                "model_dir": Path(raw.get(
                    "model_dir",
                    "Models/General Equilibrium/MIRAGRODEP_v0-1/MIRAGRODEP_v0-1",
                )),
                "gams_executable": raw.get("gams_executable", "gams"),
                "solver": raw.get("solver", "CONOPT"),
                "calib_gms": raw.get("calib_gms", "calib.gms"),
                "msd_gms": raw.get("msd_gms", "MSD.gms"),
                "ref_gms": raw.get("ref_gms", "REF.gms"),
                "simul_gms": raw.get("simul_gms", "Simul.gms"),
                "results_subdir": raw.get("results_subdir", "Results"),
                "skip_calib_if_present": raw.get("skip_calib_if_present", True),
                "timeout_seconds": raw.get("timeout_seconds", 14400),
                "keep_working_copy": raw.get("keep_working_copy", False),
                "extra_gams_args": raw.get("extra_gams_args", ["lo=2", "ll=0"]),
            }
            config = MIRAGRODEPConfig(**cfg_kwargs)
            logger.info("MIRAGRODEPAdapter: loaded MIRAGRODEPConfig from miragrodep.yaml")
            return MIRAGRODEPAdapter(config=config)

    return MIRAGRODEPAdapter()


def _build_nems_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build NEMSAdapter with optional YAML config."""
    from src.models.macro.nems import NEMSAdapter, NEMSConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "nems.yaml")
        if raw:
            install_dir = raw.get("nems_install_dir")
            sbatch_script = raw.get("sbatch_script")
            config = NEMSConfig(
                mode=raw.get("mode", "output_ingestion"),
                output_base_dir=Path(raw.get("output_base_dir", "data/nems_outputs")),
                scenario_dir_mapping=raw.get("scenario_dir_mapping", {}),
                nems_install_dir=Path(install_dir) if install_dir else None,
                python_env_path=raw.get("python_env_path"),
                run_mode=raw.get("run_mode", "par"),
                num_cycles=raw.get("num_cycles", 4),
                max_iterations=raw.get("max_iterations", 4),
                last_projection_year=raw.get("last_projection_year", 2050),
                use_nems_setup=raw.get("use_nems_setup", True),
                sbatch_script=Path(sbatch_script) if sbatch_script else None,
                slurm_partition=raw.get("slurm_partition"),
                slurm_account=raw.get("slurm_account"),
                slurm_extra_args=raw.get("slurm_extra_args", []),
                mam_link_table=raw.get("mam_link_table", {}),
                timeout_seconds=raw.get("timeout_seconds", 86400),
            )
            logger.info("NEMSAdapter: loaded NEMSConfig from nems.yaml")
            return NEMSAdapter(config=config)

    return NEMSAdapter()


# ---------------------------------------------------------------------------
# Water adapters
# ---------------------------------------------------------------------------

def _build_sahysmod_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build SahysModAdapter with optional YAML config."""
    from src.models.water.sahysmod import LineRange, SahysModAdapter, SahysModConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "sahysmod.yaml")
        if raw and raw.get("executable_path") and raw.get("baseline_input_deck"):
            irrigation_ranges = [
                LineRange(**r) for r in (raw.get("irrigation_line_ranges") or [])
            ]
            salinity_ranges = [
                LineRange(**r) for r in (raw.get("salinity_line_ranges") or [])
            ]
            config = SahysModConfig(
                executable_path=Path(raw["executable_path"]),
                baseline_input_deck=Path(raw["baseline_input_deck"]),
                timeout_seconds=raw.get("timeout_seconds", 600),
                keep_working_copy=raw.get("keep_working_copy", False),
                irrigation_line_ranges=irrigation_ranges,
                salinity_line_ranges=salinity_ranges,
                cli_invocation=raw.get("cli_invocation", "positional"),
                sentinel_min=raw.get("sentinel_min", -2.0),
            )
            logger.info("SahysModAdapter: loaded SahysModConfig from sahysmod.yaml")
            return SahysModAdapter(config=config)

    return SahysModAdapter()


def _build_cwatm_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build CWatMAdapter with optional YAML config.

    Only the canonical 'cwatm.yaml' triggers a real CWatMConfig; the
    'cwatm.yaml.example' template is intentionally ignored so a freshly
    cloned repo doesn't try to launch a CWatM that isn't installed.
    """
    from src.models.water.cwatm import CWatMAdapter, CWatMConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "cwatm.yaml")
        if (
            raw
            and raw.get("cwatm_root")
            and raw.get("baseline_settings_path")
            and raw.get("data_path")
        ):
            kwargs: dict[str, Any] = {
                "cwatm_root": Path(raw["cwatm_root"]),
                "baseline_settings_path": Path(raw["baseline_settings_path"]),
                "data_path": Path(raw["data_path"]),
                "output_dir": Path(raw.get("output_dir", "data/outputs/cwatm")),
                "python_executable": raw.get("python_executable", "python"),
                "entry_point": raw.get("entry_point", "run_cwatm.py"),
                "timeout_seconds": raw.get("timeout_seconds", 14400),
                "keep_working_copy": raw.get("keep_working_copy", False),
                "extra_env": raw.get("extra_env") or {},
                "omp_num_threads": raw.get("omp_num_threads", 1),
            }
            if raw.get("demand_keys"):
                kwargs["demand_keys"] = list(raw["demand_keys"])
            if raw.get("infra_keys"):
                kwargs["infra_keys"] = list(raw["infra_keys"])
            config = CWatMConfig(**kwargs)
            logger.info("CWatMAdapter: loaded CWatMConfig from cwatm.yaml")
            return CWatMAdapter(config=config)

    return CWatMAdapter()


def _build_weap_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build WEAPAdapter with optional YAML config (config-aware stub)."""
    from src.models.water.weap import WEAPAdapter, WEAPConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "weap_mena.yaml")
        if raw and raw.get("weap_executable") and raw.get("study_path"):
            config = WEAPConfig(
                weap_executable=Path(raw["weap_executable"]),
                study_path=Path(raw["study_path"]),
                scenario_branch_name=raw.get("scenario_branch_name", "HormuzCrisis"),
                result_export_path=Path(
                    raw.get("result_export_path", "data/outputs/weap_mena")
                ),
                use_com_automation=raw.get("use_com_automation", True),
                timeout_seconds=raw.get("timeout_seconds", 3600),
            )
            logger.info("WEAPAdapter: loaded WEAPConfig from weap_mena.yaml")
            return WEAPAdapter(config=config)

    return WEAPAdapter()


def _build_watergap2_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build WaterGAP2Adapter with optional YAML config (config-aware stub)."""
    from src.models.water.watergap2 import WaterGAP2Adapter, WaterGAP2Config

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "watergap2.yaml")
        if raw and raw.get("forcing_data_path") and (
            raw.get("executable_path") or raw.get("api_url")
        ):
            try:
                config = WaterGAP2Config(
                    executable_path=(
                        Path(raw["executable_path"])
                        if raw.get("executable_path")
                        else None
                    ),
                    api_url=raw.get("api_url"),
                    forcing_data_path=Path(raw["forcing_data_path"]),
                    output_dir=Path(raw.get("output_dir", "data/outputs/watergap2")),
                    simulation_period_years=raw.get("simulation_period_years", 5),
                    timeout_seconds=raw.get("timeout_seconds", 7200),
                    extra_env=raw.get("extra_env") or {},
                )
            except ValueError as exc:
                logger.warning(
                    "WaterGAP2Adapter: invalid config (%s); using stub", exc
                )
                return WaterGAP2Adapter()
            logger.info("WaterGAP2Adapter: loaded WaterGAP2Config from watergap2.yaml")
            return WaterGAP2Adapter(config=config)

    return WaterGAP2Adapter()


def _build_osemosys_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build OSeMOSYSAdapter with optional YAML config."""
    from src.models.energy.osemosys import OSeMOSYSAdapter, OSeMOSYSConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "osemosys.yaml")
        if raw:
            cfg_kwargs: dict[str, Any] = {
                "osemosys_dir": Path(raw.get("osemosys_dir", "Models/Energy/OSeMOSYS")),
                "model_file": raw.get("model_file", "osemosys.txt"),
                "baseline_data_dir": Path(
                    raw.get("baseline_data_dir", "data/osemosys/baseline")
                ),
                "otoole_config": Path(
                    raw.get("otoole_config", "data/osemosys/baseline/config.yaml")
                ),
                "input_format": raw.get("input_format", "csv"),
                "output_dir": Path(raw.get("output_dir", "data/outputs/osemosys")),
                "solver": raw.get("solver", "glpk"),
                "glpsol_executable": raw.get("glpsol_executable", "glpsol"),
                "cbc_executable": raw.get("cbc_executable", "cbc"),
                "otoole_executable": raw.get("otoole_executable", "otoole"),
                "timeout_seconds": raw.get("timeout_seconds", 7200),
                "keep_working_copy": raw.get("keep_working_copy", False),
            }
            config = OSeMOSYSConfig(**cfg_kwargs)
            logger.info("OSeMOSYSAdapter: loaded OSeMOSYSConfig from osemosys.yaml")
            return OSeMOSYSAdapter(config=config)

    return OSeMOSYSAdapter()


def _build_messageix_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build MESSAGEixAdapter with optional YAML config."""
    from src.models.energy.messageix import MESSAGEixAdapter, MESSAGEixConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "messageix.yaml")
        if raw:
            cfg_kwargs: dict[str, Any] = {
                "messageix_dir": Path(
                    raw.get("messageix_dir", "Models/Energy/MESSAGEix")
                ),
                "platform_name": raw.get("platform_name", "local"),
                "baseline_model": raw.get("baseline_model", "Westeros Electrified"),
                "baseline_scenario": raw.get("baseline_scenario", "baseline"),
                "baseline_version": raw.get("baseline_version"),
                "target_model": raw.get("target_model", "Hormuz Disruption"),
                "solve_model": raw.get("solve_model", "MESSAGE"),
                "output_dir": Path(raw.get("output_dir", "data/outputs/messageix")),
                "timeout_seconds": raw.get("timeout_seconds", 14400),
                "keep_clone_after_run": raw.get("keep_clone_after_run", True),
            }
            mapping = raw.get("fuel_to_commodity")
            if mapping:
                cfg_kwargs["fuel_to_commodity"] = mapping
            config = MESSAGEixConfig(**cfg_kwargs)
            logger.info("MESSAGEixAdapter: loaded MESSAGEixConfig from messageix.yaml")
            return MESSAGEixAdapter(config=config)

    return MESSAGEixAdapter()


def _build_temoa_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build TEMOAAdapter with optional YAML config."""
    from src.models.energy.temoa import TEMOAAdapter, TEMOAConfig

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "temoa.yaml")
        if raw:
            cfg_kwargs: dict[str, Any] = {
                "temoa_dir": Path(raw.get("temoa_dir", "Models/Energy/TEMOA")),
                "baseline_db_path": Path(
                    raw.get(
                        "baseline_db_path",
                        "Models/Energy/TEMOA/data_files/utopia.sqlite",
                    )
                ),
                "output_dir": Path(raw.get("output_dir", "data/outputs/temoa")),
                "solver": raw.get("solver", "cbc"),
                "python_executable": raw.get("python_executable", "python"),
                "temoa_module": raw.get("temoa_module", "temoa.temoa_run"),
                "timeout_seconds": raw.get("timeout_seconds", 14400),
                "keep_working_copy": raw.get("keep_working_copy", False),
                "oil_fuel_pattern": raw.get("oil_fuel_pattern", "OIL"),
                "gas_fuel_pattern": raw.get("gas_fuel_pattern", "GAS"),
                "lng_pattern": raw.get("lng_pattern", "LNG"),
            }
            config = TEMOAConfig(**cfg_kwargs)
            logger.info("TEMOAAdapter: loaded TEMOAConfig from temoa.yaml")
            return TEMOAAdapter(config=config)

    return TEMOAAdapter()


def _build_bornstein_krusell_rebelo_adapter(
    config_dir: Path | None = None,
) -> ModelAdapter:
    """Build BornsteinKrusellRebeloAdapter with optional YAML config."""
    from src.models.oil.bornstein_krusell_rebelo import (
        BornsteinKrusellRebeloAdapter,
        BornsteinKrusellRebeloConfig,
    )

    if config_dir is not None:
        raw = _load_yaml_config(config_dir / "bornstein_krusell_rebelo.yaml")
        if raw:
            calib_path = raw.get("calibration_mat_path")
            cfg_kwargs: dict[str, Any] = {
                "octave_executable": raw.get("octave_executable", "octave-cli"),
                "dynare_path": Path(
                    raw.get("dynare_path", "/usr/lib/dynare/matlab")
                ),
                "replication_files_dir": Path(
                    raw.get(
                        "replication_files_dir",
                        "Models/Oil/WorldEquilibriumOilModel/Replication Files",
                    )
                ),
                "section": raw.get(
                    "section", "Section 5/supply_shocks_to_non_opec"
                ),
                "mod_file": raw.get("mod_file"),
                "irf_horizon_quarters": raw.get("irf_horizon_quarters", 20),
                "timeout_seconds": raw.get("timeout_seconds", 1800),
                "keep_working_copy": raw.get("keep_working_copy", False),
            }
            if calib_path:
                cfg_kwargs["calibration_mat_path"] = Path(calib_path)
            config = BornsteinKrusellRebeloConfig(**cfg_kwargs)
            logger.info(
                "BornsteinKrusellRebeloAdapter: loaded "
                "BornsteinKrusellRebeloConfig from bornstein_krusell_rebelo.yaml"
            )
            return BornsteinKrusellRebeloAdapter(config=config)

    return BornsteinKrusellRebeloAdapter()


def build_default_registry(
    config_dir: Path | str | None = None,
) -> ModelRegistry:
    """Build a registry with all model adapters.

    If config_dir is provided (e.g., ``Path("configs/model_configs")``),
    adapters with matching YAML config files are instantiated with real
    execution configurations. Adapters without configs are instantiated
    as stubs.

    Args:
        config_dir: Path to directory containing model config YAML files.
                    Pass None to instantiate all adapters as stubs.
    """
    from src.models.fertilizer.apsim import APSIMAdapter
    from src.models.fertilizer.capri import CAPRIAdapter
    from src.models.fertilizer.futures import FuturesAdapter
    from src.models.fertilizer.gtap import GTAPAdapter
    from src.models.fertilizer.simple_g import SIMPLEGAdapter
    from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter
    from src.models.helium.argonne_abm import ArgonneABMAdapter
    from src.models.helium.simrlfab import SimRLFabAdapter
    from src.models.helium.world_helium_model import WorldHeliumModelAdapter
    from src.models.lng.energy_flux_gas_power import EnergyFluxGasPowerAdapter
    from src.models.lng.energy_flux_lng_profits import EnergyFluxLNGProfitsAdapter
    from src.models.lng.lngst import LNGSTAdapter
    from src.models.macro.mpsge_jl import MPSGEJLAdapter
    from src.models.macro.nrel import NRELAdapter
    from src.models.oil.fed_oil import FedOilAdapter
    from src.models.oil.marketsim import MarketSimAdapter
    from src.models.oil.poles_jrc import POLESJRCAdapter
    from src.models.shipping.ais_project import AISProjectAdapter
    from src.models.shipping.aisdb import AISDBAdapter

    # Note: water adapters (CWatM, SahysMod, WaterGAP2, WEAP) are imported
    # inside the per-model _build_* helpers above and dispatched into the
    # config_aware list below.

    cfg_dir = Path(config_dir) if config_dir is not None else None

    registry = ModelRegistry()

    # Models with real integration (config-aware builders)
    config_aware = [
        _build_ggm_adapter(cfg_dir),
        _build_magpie_adapter(cfg_dir),
        _build_nems_adapter(cfg_dir),
        _build_mam_adapter(cfg_dir),
        _build_opencge_adapter(cfg_dir),
        _build_pycge_adapter(cfg_dir),
        _build_miragrodep_adapter(cfg_dir),
        # Water — full integration (SahysMod, CWatM) and config-aware stubs
        # (WEAP-MENA, WaterGAP2). All four pick up YAML configs from cfg_dir
        # when present and fall back to stub instances otherwise.
        _build_sahysmod_adapter(cfg_dir),
        _build_cwatm_adapter(cfg_dir),
        _build_weap_adapter(cfg_dir),
        _build_watergap2_adapter(cfg_dir),
        # Oil — BKR is now a real Octave + Dynare driver
        _build_bornstein_krusell_rebelo_adapter(cfg_dir),
        # Energy systems — OSeMOSYS, MESSAGEix, TEMOA
        _build_osemosys_adapter(cfg_dir),
        _build_messageix_adapter(cfg_dir),
        _build_temoa_adapter(cfg_dir),
    ]

    # Remaining stub adapters (no model code in Models/ yet)
    stubs = [
        # Oil (BKR handled above)
        POLESJRCAdapter(),
        MarketSimAdapter(), FedOilAdapter(),
        # LNG (excluding GGM — handled above)
        EnergyFluxGasPowerAdapter(), EnergyFluxLNGProfitsAdapter(), LNGSTAdapter(),
        # Helium & Semiconductors
        WorldHeliumModelAdapter(), ArgonneABMAdapter(), SimRLFabAdapter(),
        # Fertilizer & Agriculture (excluding MAgPIE — handled above)
        CAPRIAdapter(), SIMPLEGAdapter(), WorldFertilizerAdapter(),
        GTAPAdapter(), APSIMAdapter(), FuturesAdapter(),
        # Shipping
        AISDBAdapter(), AISProjectAdapter(),
        # Macro (NEMS, MAM, OpenCGE, PyCGE, MIRAGRODEP — handled above)
        NRELAdapter(), MPSGEJLAdapter(),
    ]

    for adapter in config_aware + stubs:
        registry.register(adapter)

    return registry
