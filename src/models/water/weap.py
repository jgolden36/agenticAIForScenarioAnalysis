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

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Country-specific desalination dependence (share of municipal water from
# desal). UN-Water 2024 Progress Report; AGCC 2023 Water Statistics.
_DESAL_DEPENDENCE_BY_COUNTRY: dict[str, float] = {
    "uae": 0.42,
    "qatar": 0.60,
    "saudi_arabia": 0.50,
    "ksa": 0.50,
    "bahrain": 0.65,
    "kuwait": 0.92,
    "oman": 0.30,
    "iran": 0.10,
    "iraq": 0.05,
}
# Per-country population weights (millions, 2024 World Bank). Used to
# weight the aggregate unmet-demand percentage when the analyst doesn't
# supply ``population_affected_millions``.
_POPULATION_WEIGHTS_MILLIONS: dict[str, float] = {
    "uae": 9.5,
    "qatar": 2.9,
    "saudi_arabia": 36.0,
    "ksa": 36.0,
    "bahrain": 1.5,
    "kuwait": 4.3,
    "oman": 4.6,
    "iran": 87.0,
    "iraq": 44.0,
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
        """Execute WEAP-MENA.

        With a valid ``WEAPConfig`` set, this method validates the WEAP
        executable / study file and then raises ``NotImplementedError``
        because the COM automation driver is still pending. Without a
        config, this method runs a closed-form country-disaggregated
        unmet-demand calculator so the WATER tier has a country-level
        stand-in alongside ``cwatm`` (which produces global / basin-level
        outputs).
        """
        if self._config is not None:
            self._validate_prerequisites(self._config)
            raise NotImplementedError(
                "WEAPAdapter.execute() is config-validated but the COM "
                "automation / subprocess driver is not yet implemented. "
                "Required next steps:\n"
                "  - Drive WEAP via win32com.client.Dispatch('WEAP.WEAPApplication') "
                "or subprocess weap.exe with the configured study_path.\n"
                "  - Create or update the scenario branch named "
                f"'{self._config.scenario_branch_name}' from the inputs dict.\n"
                "  - Export results to "
                f"'{self._config.result_export_path}' and parse them in parse_outputs."
            )

        params = inputs if isinstance(inputs, dict) else dict(inputs)

        desal_loss_pct = float(params["desalination_capacity_loss_pct"])
        duration_weeks = float(params["disruption_duration_weeks"])
        countries = [str(c).lower() for c in params.get("affected_countries", [])]
        alt_supply = bool(params.get("alternative_supply_available", False))
        population_affected = float(params.get("population_affected_millions", 0.0))

        # Alternative supply (e.g. groundwater rationing, shipped water)
        # softens the desalination shortfall. We use a 30% mitigation
        # assumption (UN-Water 2024 emergency response benchmarks).
        mitigation = 0.3 if alt_supply else 0.0
        effective_loss_pct = desal_loss_pct * (1.0 - mitigation)

        # Per-country unmet demand percentage.
        unmet_by_country: dict[str, float] = {}
        coverage_by_country: dict[str, float] = {}
        for country in countries:
            dependence = _DESAL_DEPENDENCE_BY_COUNTRY.get(country, 0.20)
            unmet_pct = dependence * effective_loss_pct
            unmet_by_country[country] = round(unmet_pct, 3)
            coverage_by_country[country] = round(100.0 - unmet_pct, 3)

        # Aggregate population-weighted unmet demand.
        if countries:
            if population_affected > 0:
                # Use the population_affected_millions value the analyst
                # supplied for the aggregate; per-country values are
                # still derived from the dependence weights above.
                total_pop = population_affected
                # Approximate per-country population shares from the
                # baseline weights restricted to the requested countries.
                per_country_pop = {
                    c: _POPULATION_WEIGHTS_MILLIONS.get(c, 1.0) for c in countries
                }
                pop_total = sum(per_country_pop.values()) or 1.0
                aggregate_unmet_pct = sum(
                    (per_country_pop[c] / pop_total) * unmet_by_country[c]
                    for c in countries
                )
            else:
                # Fall back to baseline population weights only.
                total_pop = sum(
                    _POPULATION_WEIGHTS_MILLIONS.get(c, 1.0) for c in countries
                )
                aggregate_unmet_pct = sum(
                    (_POPULATION_WEIGHTS_MILLIONS.get(c, 1.0) / max(total_pop, 1e-6))
                    * unmet_by_country[c]
                    for c in countries
                )
        else:
            total_pop = 0.0
            aggregate_unmet_pct = 0.0

        # Cumulative water deficit (percent-weeks). Useful downstream for
        # consistency-checking against CWatM's percent-months metric.
        cumulative_pct_weeks = round(
            aggregate_unmet_pct * max(duration_weeks, 0.0), 2
        )

        outputs: dict[str, Any] = {
            "desalination_capacity_loss_pct": desal_loss_pct,
            "effective_desalination_loss_pct": round(effective_loss_pct, 3),
            "alternative_supply_available": alt_supply,
            "disruption_duration_weeks": duration_weeks,
            "affected_countries": countries,
            "unmet_demand_pct_by_country": unmet_by_country,
            "supply_coverage_pct_by_country": coverage_by_country,
            "aggregate_unmet_demand_pct": round(aggregate_unmet_pct, 3),
            "unmet_demand_pct": round(aggregate_unmet_pct, 3),
            "cumulative_water_deficit_pct_weeks": cumulative_pct_weeks,
            "population_affected_millions": total_pop,
            "desal_dependence_by_country": dict(_DESAL_DEPENDENCE_BY_COUNTRY),
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "UN-Water (2024) Progress Report; AGCC (2023) Water "
                    "Statistics; World Bank (2024) population data."
                ),
                "alternative_supply_mitigation": mitigation,
                "desal_dependence_by_country": dict(_DESAL_DEPENDENCE_BY_COUNTRY),
                "population_weights_millions": dict(_POPULATION_WEIGHTS_MILLIONS),
                "note": (
                    "Analytical MVP path. Provide a WEAPConfig in "
                    "configs/model_configs/weap_mena.yaml to invoke the "
                    "real WEAP install. Real path requires: (1) Windows "
                    "host with SEI WEAP license, (2) WEAP-MENA .weap "
                    "study file, (3) COM automation or subprocess driver."
                ),
            },
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
