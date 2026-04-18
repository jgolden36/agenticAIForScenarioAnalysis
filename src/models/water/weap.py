"""Adapter for WEAP-MENA (Water Evaluation And Planning, MENA configuration).

WEAP-MENA is the Persian Gulf regional configuration of the Water Evaluation And
Planning system. It performs integrated water resource planning simulations that
account for supply infrastructure, demand sites, and allocation priorities. In the
Hormuz pipeline it quantifies the consequences of desalination facility disruption
for human water security across Gulf Cooperation Council states.

Status: **config-aware stub.** This adapter accepts a fully-typed
``WEAPConfig`` and, if one is provided, validates that the WEAP executable
and study file actually exist on disk before raising ``NotImplementedError``.
The ``execute()`` body itself remains a stub because driving WEAP requires
COM automation against a licensed Stockholm Environment Institute install on
a Windows host -- prerequisites that cannot be vendored or auto-installed.

Real integration requirements
-----------------------------
* Windows host with WEAP installed and a valid SEI licence.
* The ``Models/Water/Install_WEAP.exe`` installer is provided in the repo
  but the actual WEAP application + licence must be supplied by the analyst.
* A pre-configured WEAP-MENA study file (``.weap``) covering the Persian
  Gulf region with current-year baseline data.
* COM automation via ``win32com.client.Dispatch("WEAP.WEAPApplication")``
  or a headless subprocess call to ``weap.exe``.
* Scenario branch creation within the WEAP study to represent each crisis
  scenario, parameterised by desalination capacity loss and disruption
  duration.
* Post-run extraction of WEAP result variables (e.g. Unmet Demand, Coverage)
  via the WEAP API or by parsing exported CSV/Excel result files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Required parameter names, sourced from WATER_MODEL_SPECS["weap_mena"].
_REQUIRED_PARAMS: list[str] = [
    "desalination_capacity_loss_pct",
    "disruption_duration_weeks",
    "affected_countries",
    "alternative_supply_available",
    "population_affected_millions",
]

# Plausibility bounds for numeric parameters.
_BOUNDS: dict[str, tuple[float, float]] = {
    "desalination_capacity_loss_pct": (0.0, 100.0),
    "disruption_duration_weeks": (0.0, 260.0),
    "population_affected_millions": (0.0, 500.0),
}


class WEAPConfig(BaseModel):
    """Configuration for the WEAP-MENA adapter.

    All paths refer to the Windows host on which WEAP is installed. The adapter
    validates these at execute() time and surfaces a clear error if they're
    missing.
    """

    model_config = {"protected_namespaces": ()}

    weap_executable: Path = Field(
        description=(
            "Path to weap.exe (installed by the SEI WEAP installer, typically "
            "C:/Program Files (x86)/WEAP/weap.exe)."
        ),
    )
    study_path: Path = Field(
        description=(
            "Path to the WEAP-MENA study area file (.weap) covering the "
            "Persian Gulf region."
        ),
    )
    scenario_branch_name: str = Field(
        default="HormuzCrisis",
        description=(
            "Name of the WEAP scenario branch to create / update when running "
            "Hormuz scenarios."
        ),
    )
    result_export_path: Path = Field(
        description=(
            "Directory where WEAP CSV/Excel result exports are written for the "
            "adapter to read back."
        ),
    )
    use_com_automation: bool = Field(
        default=True,
        description=(
            "If True, drive WEAP via win32com.client.Dispatch. Otherwise fall "
            "back to subprocess invocation of weap.exe."
        ),
    )
    timeout_seconds: int = Field(
        default=3600,
        description="Maximum wall-clock seconds for a WEAP run.",
    )


class WEAPAdapter(ModelAdapter):
    """Adapter (stub) for the WEAP-MENA integrated water resource planning model."""

    def __init__(self, config: WEAPConfig | None = None) -> None:
        self._config = config

    # -- Identity properties ------------------------------------------------

    @property
    def model_id(self) -> str:
        return "weap_mena"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "WEAP-MENA: Integrated water resource planning simulation for the Persian "
            "Gulf region. Quantifies unmet demand and coverage shortfalls resulting "
            "from desalination facility disruption under Strait of Hormuz closure "
            "scenarios."
        )

    # -- Validation ---------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        for name in _REQUIRED_PARAMS:
            if name not in params:
                errors.append(f"Missing required parameter: '{name}'")

        for param_name, (lo, hi) in _BOUNDS.items():
            if param_name not in params:
                continue
            value = params[param_name]
            try:
                fval = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"Parameter '{param_name}' must be numeric; got {value!r}"
                )
                continue
            if not (lo <= fval <= hi):
                warnings.append(
                    f"Parameter '{param_name}' value {fval} is outside expected "
                    f"range [{lo}, {hi}]; verify before running."
                )

        if "affected_countries" in params:
            val = params["affected_countries"]
            if not isinstance(val, list):
                errors.append(
                    f"Parameter 'affected_countries' must be a list; got {type(val).__name__}"
                )
            elif len(val) == 0:
                warnings.append(
                    "Parameter 'affected_countries' is an empty list; "
                    "model results will cover no countries."
                )

        if "alternative_supply_available" in params:
            val = params["alternative_supply_available"]
            if not isinstance(val, bool):
                errors.append(
                    f"Parameter 'alternative_supply_available' must be a boolean; "
                    f"got {type(val).__name__}"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- Input translation --------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

    # -- Execution ----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Stub execute(). Validates the config (if any) before raising.

        With a valid ``WEAPConfig`` set, this method confirms the WEAP
        executable and study file exist on disk and then raises
        ``NotImplementedError`` describing the remaining COM automation work.
        Without a config, raises ``NotImplementedError`` describing setup steps.
        """
        if self._config is None:
            raise NotImplementedError(
                "WEAPAdapter.execute() requires a WEAPConfig. To integrate WEAP-MENA:\n"
                "  1. Install WEAP from Models/Water/Install_WEAP.exe on a Windows "
                "host with a valid SEI licence.\n"
                "  2. Build / acquire a WEAP-MENA study file (.weap).\n"
                "  3. Configure 'weap_executable', 'study_path', and "
                "'result_export_path' in configs/model_configs/weap_mena.yaml.\n"
                "  4. Implement COM automation or subprocess invocation of "
                "weap.exe inside this method.\n"
                "  5. Implement scenario-branch creation from the inputs dict.\n"
                "  6. Parse exported CSV results in parse_outputs."
            )

        self._validate_prerequisites(self._config)

        raise NotImplementedError(
            "WEAPAdapter.execute() is config-validated but the COM automation "
            "/ subprocess driver is not yet implemented. Required next steps:\n"
            "  - Drive WEAP via win32com.client.Dispatch('WEAP.WEAPApplication') "
            "or subprocess weap.exe with the configured study_path.\n"
            "  - Create or update the scenario branch named "
            f"'{self._config.scenario_branch_name}' from the inputs dict.\n"
            "  - Export results to "
            f"'{self._config.result_export_path}' and parse them in parse_outputs."
        )

    # -- Output parsing -----------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through as a ModelOutput container.

        The real implementation should parse WEAP result CSV/Excel exports and
        populate ``outputs`` with standardised keys such as:

            * ``unmet_demand_m3_per_yr``: dict mapping country -> float
            * ``supply_coverage_pct``: dict mapping country -> float
            * ``simulation_years``: list of simulated calendar years
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _validate_prerequisites(config: WEAPConfig) -> None:
        """Check that all configured paths exist before attempting to drive WEAP."""
        if not config.weap_executable.is_file():
            raise FileNotFoundError(
                f"WEAP executable not found: {config.weap_executable}. "
                "Set 'weap_executable' in configs/model_configs/weap_mena.yaml."
            )
        if not config.study_path.is_file():
            raise FileNotFoundError(
                f"WEAP study file not found: {config.study_path}. "
                "Set 'study_path' in configs/model_configs/weap_mena.yaml."
            )
        # Result export dir is created by the (future) execute() implementation;
        # we just check the parent exists so the caller knows where it'll land.
        if not config.result_export_path.parent.is_dir():
            raise FileNotFoundError(
                f"Parent directory of result_export_path does not exist: "
                f"{config.result_export_path.parent}."
            )
