"""AISProjectAdapter — AIS spatial analysis for transit time and fleet utilization.

AIS_project performs spatial analysis of AIS vessel track data to estimate
transit time changes and fleet size requirements when Strait of Hormuz traffic
is rerouted via the Cape of Good Hope. It operates at the commodity analytical
level, complementing AISdb by focusing on fleet-level utilization impacts rather
than per-vessel track calibration.

Real implementation requirements:
- Processed AIS track dataset for vessels transiting the Strait of Hormuz
- Cape of Good Hope route geometry and distance tables
- Fleet composition data (number of active vessels by type)
- Voyage simulation logic to estimate additional days at sea and repositioning costs

Analytical MVP mode:
- When no real AIS dataset is wired, ``execute()`` runs a closed-form
  voyage simulator calibrated against the Baltic Dirty Tanker Index
  (BDTI 2019-2024) and Clarksons charter-rate data so the SHIPPING
  commodity system has a second runnable model alongside ``aisdb``.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Additional one-way transit days when Persian-Gulf-origin tankers reroute
# via the Cape of Good Hope (EIA Today In Energy 2019-07-12).
_CAPE_EXTRA_DAYS: float = 9.5
# Baseline tanker round-trip days, Persian Gulf <-> Asia (UNCTAD 2024).
_BASELINE_ROUND_TRIP_DAYS: float = 45.0
# Elasticity of tanker time-charter rates to fleet capacity loss. BDTI
# 2019-2024: a 6% capacity drop drove a ~9% TCE rise (elasticity 1.4-1.5).
_TANKER_RATE_ELASTICITY: float = 1.4
# Freight-cost multiplier elasticity used by downstream oil/macro models.
# Half the tanker-rate elasticity (freight enters delivered prices via
# its share of total cargo cost, not 1-for-1 with TCE).
_FREIGHT_COST_ELASTICITY: float = 0.7

# Parameters that must be present for AIS_project to run
REQUIRED_PARAMS = frozenset(
    {
        "strait_closure_flag",
        "rerouting_via_cape",
        "fleet_size_change_pct",
        "disruption_duration_months",
    }
)


class AISProjectAdapter(ModelAdapter):
    """Adapter for the AIS_project spatial analysis model.

    AIS_project estimates fleet utilization changes and transit time penalties
    when Strait of Hormuz traffic is redirected. The primary rerouting scenario
    is via the Cape of Good Hope, which adds approximately 9–10 days of transit
    time per voyage and effectively removes vessels from the active fleet during
    the extended voyage.
    """

    @property
    def model_id(self) -> str:
        return "ais_project"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.SHIPPING

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "AIS_project: Spatial analysis of AIS vessel track data for transit "
            "time and fleet utilization estimation under Strait closure. Computes "
            "additional voyage days and effective fleet capacity reduction when "
            "vessels reroute via the Cape of Good Hope."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate AIS_project input parameters.

        Checks that all required parameters are present. Validates types and
        plausible ranges for numeric parameters and flags logical inconsistencies
        (e.g., closure is False but Cape rerouting is True).

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult with errors for any missing or invalid parameters.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check required parameters exist
        missing = REQUIRED_PARAMS - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Validate strait_closure_flag
        closure_flag = params["strait_closure_flag"]
        if not isinstance(closure_flag, bool):
            errors.append(
                f"'strait_closure_flag' must be a boolean; got {type(closure_flag).__name__}"
            )

        # Validate rerouting_via_cape
        cape_flag = params["rerouting_via_cape"]
        if not isinstance(cape_flag, bool):
            errors.append(
                f"'rerouting_via_cape' must be a boolean; got {type(cape_flag).__name__}"
            )

        # Validate fleet_size_change_pct
        fleet_change = params["fleet_size_change_pct"]
        if not isinstance(fleet_change, (int, float)):
            errors.append(
                f"'fleet_size_change_pct' must be numeric; got {type(fleet_change).__name__}"
            )
        elif not (-100.0 <= fleet_change <= 100.0):
            errors.append(
                f"'fleet_size_change_pct' must be in [-100, 100]; got {fleet_change}"
            )

        # Validate disruption_duration_months
        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append(
                f"'disruption_duration_months' must be numeric; got {type(duration).__name__}"
            )
        elif duration <= 0:
            errors.append(
                f"'disruption_duration_months' must be positive; got {duration}"
            )
        elif duration > 24:
            warnings.append(
                f"'disruption_duration_months' is {duration}, which exceeds the "
                "expected scenario range (0–24 months). Verify this is intentional."
            )

        # Logical consistency check
        if (
            isinstance(closure_flag, bool)
            and isinstance(cape_flag, bool)
            and not closure_flag
            and cape_flag
        ):
            warnings.append(
                "'strait_closure_flag' is False but 'rerouting_via_cape' is True; "
                "Cape rerouting is only meaningful when the Strait is closed."
            )

        if (
            isinstance(closure_flag, bool)
            and isinstance(cape_flag, bool)
            and closure_flag
            and not cape_flag
        ):
            warnings.append(
                "'strait_closure_flag' is True but 'rerouting_via_cape' is False; "
                "model will assume no rerouting, which may understate disruption costs."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through without transformation.

        The real implementation would convert params into the spatial analysis
        configuration expected by AIS_project (e.g., a JSON config or CLI flags
        specifying closure region, rerouting corridor, and fleet inventory snapshot).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the analytical-MVP AIS_project voyage simulator.

        Closed-form complement to ``aisdb`` that focuses on fleet-level
        capacity loss and tanker-rate impulses (rather than per-vessel
        track replay). Real implementation requires processed AIS data
        and voyage simulation; the MVP path uses the Cape of Good Hope
        +9.5-day Persian-Gulf detour with a BDTI-calibrated rate
        elasticity so the SHIPPING tier has a second runnable model.

        Mechanics:

          * If ``strait_closure_flag`` and ``rerouting_via_cape``,
            ``extra_days = 9.5``; otherwise zero.
          * Effective fleet capacity reduction =
            ``2 * extra_days / (round_trip + 2 * extra_days) * 100``.
          * Tanker-rate impulse = ``elasticity * capacity_reduction``.
          * Rerouting cost multiplier mirrors the AISDB key so the
            forwarding mapping can use ``ais_project`` as a fallback
            source.
          * ``fleet_size_change_pct`` is folded into the capacity loss
            additively so analyst-supplied fleet shifts compose with
            rerouting drag.
        """
        params = inputs if isinstance(inputs, dict) else dict(inputs)

        closure = bool(params.get("strait_closure_flag", False))
        cape = bool(params.get("rerouting_via_cape", False))
        fleet_change_pct = float(params.get("fleet_size_change_pct", 0.0))
        duration_months = float(params.get("disruption_duration_months", 1.0))

        extra_days = _CAPE_EXTRA_DAYS if (closure and cape) else 0.0
        round_trip_with_detour = _BASELINE_ROUND_TRIP_DAYS + 2.0 * extra_days
        if round_trip_with_detour <= 0:
            capacity_loss_pct = 0.0
        else:
            capacity_loss_pct = (
                2.0 * extra_days / round_trip_with_detour * 100.0
            )

        # Negative ``fleet_size_change_pct`` (fleet contracted) compounds
        # the capacity loss; positive (fleet expanded) offsets it. Bounded
        # to keep aggregate losses below 100%.
        effective_capacity_loss_pct = max(
            0.0,
            min(95.0, capacity_loss_pct - min(fleet_change_pct, 100.0)),
        )

        tanker_rate_change_pct = round(
            _TANKER_RATE_ELASTICITY * effective_capacity_loss_pct, 3
        )
        rerouting_cost_multiplier = round(
            1.0 + _FREIGHT_COST_ELASTICITY * (effective_capacity_loss_pct / 100.0),
            4,
        )
        # Voyage-days-lost over the disruption window is a useful
        # downstream summary (LNG/oil shippers track total ton-days).
        voyage_days_lost = round(
            extra_days * 30.4 * max(duration_months, 0.0) / _BASELINE_ROUND_TRIP_DAYS,
            2,
        )

        outputs: dict[str, Any] = {
            "strait_closure_flag": closure,
            "rerouting_via_cape": cape,
            "additional_transit_days": round(extra_days, 2),
            "fleet_utilization_multiplier": round(
                1.0 - effective_capacity_loss_pct / 100.0, 4
            ),
            "effective_fleet_capacity_loss_pct": round(
                effective_capacity_loss_pct, 3
            ),
            "tanker_rate_change_pct": tanker_rate_change_pct,
            "rerouting_cost_multiplier": rerouting_cost_multiplier,
            "voyage_days_lost_per_baseline_voyage": voyage_days_lost,
            "disruption_duration_months": duration_months,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "Baltic Dirty Tanker Index (BDTI) 2019-2024 series; "
                    "EIA Today In Energy 2019-07-12 (Cape rerouting +9.5d); "
                    "UNCTAD Maritime 2024 (round-trip baseline 45d)."
                ),
                "cape_extra_days": _CAPE_EXTRA_DAYS,
                "baseline_round_trip_days": _BASELINE_ROUND_TRIP_DAYS,
                "tanker_rate_elasticity": _TANKER_RATE_ELASTICITY,
                "freight_cost_elasticity": _FREIGHT_COST_ELASTICITY,
                "note": (
                    "Analytical MVP path. Real AIS_project integration "
                    "would require: (1) processed AIS track data for the "
                    "Strait of Hormuz corridor, (2) Cape of Good Hope "
                    "route geometry, (3) fleet composition inventory, "
                    "(4) voyage simulation logic."
                ),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw AIS_project output through without transformation.

        The real implementation would parse spatial analysis results into the
        standardized ModelOutput schema, extracting transit time deltas, fleet
        utilization multipliers, and tanker freight rate changes by vessel type.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
