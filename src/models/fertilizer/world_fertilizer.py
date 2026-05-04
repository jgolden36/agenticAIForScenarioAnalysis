"""World Fertilizer Model adapter.

The World Fertilizer Model is a market-equilibrium model of global fertilizer
supply and demand. It tracks nitrogen (N), phosphorus (P), and potassium (K)
fertilizer markets, incorporating natural gas as the primary feedstock for
nitrogen fertilizer production. Under Strait of Hormuz closure scenarios, it
quantifies how Middle East production losses and natural gas price increases
cascade into global fertilizer supply shortfalls and price spikes.

Real integration requirements:
    - Access to the World Fertilizer Model codebase and calibrated dataset
    - Platform-specific execution environment (Python, GAMS, or proprietary)
    - Natural gas price and Middle East production capacity inputs
    - Disruption duration for dynamic equilibrium path calculation
"""

from __future__ import annotations

from typing import Any

import math

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.gams_adapter import GAMSAdapter, GAMSConfig
from src.models.base import ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "natural_gas_price_change_pct",
    "middle_east_production_loss_pct",
    "disruption_duration_months",
]

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Pass-through coefficients for the nitrogen-fertilizer marginal cost
# function. Nitrogen production is gas-feedstock-intensive (Yara 2024
# tech notes; ~70% of urea variable cost is gas); the natural-gas
# pass-through coefficient is therefore ~0.55 to retail urea prices and
# the Middle East production loss adds a regional supply-shortfall
# premium of ~1.2 per percent loss.
_NG_PASSTHROUGH_TO_NITROGEN: float = 0.55
_ME_LOSS_PASSTHROUGH_TO_NITROGEN: float = 1.2

# Phosphate (DAP) and potash (MOP) markets are largely independent of
# Middle East gas. They get a small (~5%) sympathetic move from the
# nitrogen index but are otherwise unaffected by the Hormuz channel.
_PHOSPHATE_NITROGEN_SYMPATHY: float = 0.05
_POTASH_NITROGEN_SYMPATHY: float = 0.05

# Aggregate fertilizer index weights (FAO 2024 global trade share).
_FERT_INDEX_WEIGHTS: dict[str, float] = {
    "urea": 0.45,    # nitrogen
    "dap": 0.30,     # phosphate
    "mop": 0.25,     # potash
}

# AR(1) mean-reversion half-life by fertilizer (months). Mirrors
# src/models/fertilizer/futures.py for the urea / dap / potash decay.
_FERT_HALFLIFE_MONTHS: dict[str, float] = {
    "urea": 3.0,
    "dap": 4.0,
    "mop": 5.0,
}


class WorldFertilizerAdapter(GAMSAdapter):
    """Adapter for the World Fertilizer Model market-equilibrium model.

    Inherits from GAMSAdapter for GAMS Control API execution with
    GamsWorkspace/GamsJob orchestration and convergence checking.

    The World Fertilizer Model solves for equilibrium fertilizer prices and
    trade flows under supply and cost shocks. The Strait of Hormuz closure
    directly affects this model through two channels: (1) loss of Middle East
    natural gas feedstock, disrupting nitrogen fertilizer production in Qatar,
    Iran, Saudi Arabia, and UAE; and (2) higher natural gas prices globally,
    raising the marginal cost of nitrogen fertilizer production worldwide.

    IMPORTANT: GamsWorkspace is NOT thread-safe. The GAMSAdapter base class
    allocates isolated temp directories for each execution.
    """

    def __init__(self, config: GAMSConfig | None = None) -> None:
        super().__init__(config)

    @property
    def model_id(self) -> str:
        return "world_fertilizer"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "World Fertilizer Model: market-equilibrium model of global nitrogen, "
            "phosphorus, and potassium fertilizer supply and demand, with natural gas "
            "as the primary feedstock input for nitrogen production."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required World Fertilizer Model parameters are present and in range.

        Args:
            params: Parameter dictionary from the extraction module.

        Returns:
            ValidationResult with errors for missing or out-of-range values.
        """
        errors: list[str] = []
        warnings: list[str] = []

        for key in _REQUIRED_PARAMS:
            if key not in params:
                errors.append(f"Missing required parameter: '{key}'")

        if "natural_gas_price_change_pct" in params:
            val = params["natural_gas_price_change_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'natural_gas_price_change_pct' must be numeric")
            elif val > 1000:
                warnings.append(
                    f"'natural_gas_price_change_pct' = {val}% is extreme; "
                    "verify that this reflects a scenario-consistent shock"
                )

        if "middle_east_production_loss_pct" in params:
            val = params["middle_east_production_loss_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'middle_east_production_loss_pct' must be numeric")
            elif not (0.0 <= val <= 100.0):
                errors.append(
                    f"'middle_east_production_loss_pct' = {val} is out of range; "
                    "expected a value in [0, 100]"
                )
            elif val > 80:
                warnings.append(
                    f"'middle_east_production_loss_pct' = {val}% implies near-total "
                    "regional production loss; confirm this is scenario-consistent"
                )

        if "disruption_duration_months" in params:
            val = params["disruption_duration_months"]
            if not isinstance(val, (int, float)):
                errors.append("'disruption_duration_months' must be numeric")
            elif val <= 0:
                errors.append("'disruption_duration_months' must be > 0")
            elif val > 24:
                warnings.append(
                    f"'disruption_duration_months' = {val} exceeds typical model "
                    "calibration horizon; results may extrapolate beyond validated range"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def populate_database(self, db: Any, params: dict[str, Any]) -> None:
        """Inject scenario parameters into the GAMS database.

        Creates GAMS parameters for natural gas price shock, Middle East
        production loss, and disruption duration. The real implementation
        should match the .gms file's expected parameter names exactly.

        Args:
            db: A gams.GamsDatabase instance.
            params: Validated parameter dictionary.
        """
        gas_param = db.add_parameter("natural_gas_price_change_pct", 0)
        gas_param.add_record().value = params["natural_gas_price_change_pct"]

        prod_param = db.add_parameter("middle_east_production_loss_pct", 0)
        prod_param.add_record().value = params["middle_east_production_loss_pct"]

        dur_param = db.add_parameter("disruption_duration_months", 0)
        dur_param.add_record().value = params["disruption_duration_months"]

    def extract_results(self, out_db: Any) -> dict[str, Any]:
        """Extract equilibrium prices and trade flows from GAMS output.

        Args:
            out_db: The output GamsDatabase from job execution.

        Returns:
            Dict with fertilizer prices (N, P, K) and trade flow data.
        """
        results: dict[str, Any] = {}

        # Extract equilibrium prices by nutrient type
        if "equilibrium_price" in out_db:
            for rec in out_db["equilibrium_price"]:
                results[f"price_{rec.keys[0]}"] = rec.level

        # Extract trade flows if available
        if "trade_flow" in out_db:
            flows = {}
            for rec in out_db["trade_flow"]:
                key = f"{rec.keys[0]}_{rec.keys[1]}" if len(rec.keys) > 1 else rec.keys[0]
                flows[key] = rec.level
            results["trade_flows"] = flows

        # Extract aggregate price index
        if "fertilizer_price_index" in out_db:
            for rec in out_db["fertilizer_price_index"]:
                results["fertilizer_price_index"] = rec.level

        return results

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the World Fertilizer Model.

        When a GAMSConfig is provided, the GAMSAdapter base class handles
        workspace creation, parameter injection, solver execution,
        convergence checking, and result extraction. Otherwise this
        method runs a closed-form supply-demand fallback so the
        FERTILIZER_AGRICULTURE tier has a second runnable model
        alongside ``futures``.

        Mechanics:

          * Nitrogen-price impulse (urea proxy):
            ``0.55 * gas_pct + 1.2 * me_loss_pct``.
          * Phosphate / potash get a small sympathetic move (5%) from
            the nitrogen index plus their own residual.
          * Aggregate fertilizer index = trade-share-weighted blend
            (FAO 2024).
          * AR(1) mean-reversion forward path mirrors
            ``src.models.fertilizer.futures`` so the two adapters
            produce comparable forward-curve outputs.
        """
        if self._config is not None:
            return super().execute(inputs)

        params = inputs if isinstance(inputs, dict) else dict(inputs)

        gas_pct = float(params["natural_gas_price_change_pct"])
        me_loss_pct = float(params["middle_east_production_loss_pct"])
        duration_months = float(params["disruption_duration_months"])

        nitrogen_pct = (
            _NG_PASSTHROUGH_TO_NITROGEN * gas_pct
            + _ME_LOSS_PASSTHROUGH_TO_NITROGEN * me_loss_pct
        )
        phosphate_pct = _PHOSPHATE_NITROGEN_SYMPATHY * nitrogen_pct
        potash_pct = _POTASH_NITROGEN_SYMPATHY * nitrogen_pct

        # Aggregate trade-share-weighted index.
        index_pct = (
            _FERT_INDEX_WEIGHTS["urea"] * nitrogen_pct
            + _FERT_INDEX_WEIGHTS["dap"] * phosphate_pct
            + _FERT_INDEX_WEIGHTS["mop"] * potash_pct
        )

        # AR(1) decay forward path. For each commodity, P(t) =
        # baseline * (1 + shock/100 * exp(-t * ln(2) / half_life)).
        horizon_months = max(12, int(round(duration_months)) + 6)
        forward_curves: dict[str, list[float]] = {}
        for commodity, halflife in _FERT_HALFLIFE_MONTHS.items():
            shock = {
                "urea": nitrogen_pct,
                "dap": phosphate_pct,
                "mop": potash_pct,
            }[commodity]
            curve: list[float] = []
            decay_lambda = math.log(2.0) / max(halflife, 0.1)
            for t in range(horizon_months):
                p_t = 1.0 + (shock / 100.0) * math.exp(-decay_lambda * t)
                curve.append(round(p_t, 4))
            forward_curves[commodity] = curve

        # Trade-flow heuristic: a 10% shortage in ME nitrogen production
        # diverts roughly 8% of global nitrogen trade away from Middle
        # East exporters and toward US / Russia / Algeria. Light-touch
        # estimate; full model needs the GAMS run.
        diverted_share = min(0.6, 0.08 * me_loss_pct / 10.0)
        trade_flows = {
            "middle_east_exports_pct_change": round(-me_loss_pct, 2),
            "us_exports_pct_change": round(diverted_share * 25.0, 2),
            "russia_exports_pct_change": round(diverted_share * 35.0, 2),
            "algeria_exports_pct_change": round(diverted_share * 20.0, 2),
        }

        outputs: dict[str, Any] = {
            "natural_gas_price_change_pct": gas_pct,
            "middle_east_production_loss_pct": me_loss_pct,
            "disruption_duration_months": duration_months,
            "nitrogen_price_pct": round(nitrogen_pct, 3),
            "phosphate_price_pct": round(phosphate_pct, 3),
            "potash_price_pct": round(potash_pct, 3),
            "fertilizer_price_index_pct": round(index_pct, 3),
            "price_urea_pct": round(nitrogen_pct, 3),
            "price_dap_pct": round(phosphate_pct, 3),
            "price_mop_pct": round(potash_pct, 3),
            "forward_price_curves": forward_curves,
            "trade_flows": trade_flows,
            "fertilizer_index_weights": dict(_FERT_INDEX_WEIGHTS),
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "Yara (2024) urea cost structure tech notes; "
                    "FAO (2024) Fertilizer Outlook trade shares; "
                    "Baffes (2007) commodity pass-through; AR(1) decay "
                    "calibration mirrors src.models.fertilizer.futures."
                ),
                "ng_passthrough_to_nitrogen": _NG_PASSTHROUGH_TO_NITROGEN,
                "me_loss_passthrough_to_nitrogen": _ME_LOSS_PASSTHROUGH_TO_NITROGEN,
                "fert_halflife_months": dict(_FERT_HALFLIFE_MONTHS),
                "note": (
                    "Analytical MVP path. Provide a GAMSConfig in "
                    "configs/model_configs/world_fertilizer.yaml to run "
                    "the real GAMS World Fertilizer Model. Requires: "
                    "(1) GAMS install, (2) the .gms model file, "
                    "(3) CONOPT or PATH solver."
                ),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
