"""Input specifications for oil domain models."""

OIL_MODEL_SPECS: dict[str, dict] = {
    "bornstein_krusell_rebelo": {
        "model_id": "bornstein_krusell_rebelo",
        "description": "World Equilibrium Model of the Oil Market — structural GE supply disruption analysis",
        "commodity_system": "oil",
        "analytical_level": "commodity",
        "required_parameters": [
            {
                "name": "supply_loss_mbd",
                "description": (
                    "Oil supply loss attributable to the disruption. Hormuz transits roughly "
                    "17–21 mb/d but the structural model treats >20 as physically implausible "
                    "(global spare/SPR cannot be netted out). Cap at 20 even for worst-case scenarios."
                ),
                "unit": "mb/d",
                "type": "non_negative_number",
                "value_range": [0, 20],
            },
            {"name": "disruption_duration_months", "description": "Duration of supply disruption", "unit": "months", "type": "positive_number", "value_range": [0, 24]},
            {
                "name": "spr_release_mbd",
                "description": "Strategic Petroleum Reserve release rate (US SPR sustainable max ~4.4 mb/d for short bursts)",
                "unit": "mb/d",
                "type": "non_negative_number",
                "value_range": [0, 5],
            },
            {
                "name": "opec_spare_capacity_mbd",
                "description": "Available OPEC spare production capacity (typically 2–5 mb/d, shrinks during crises)",
                "unit": "mb/d",
                "type": "non_negative_number",
                "value_range": [0, 6],
            },
            {"name": "demand_elasticity_override", "description": "Override for short-run demand elasticity (negative for normal goods, e.g. -0.05 to -0.3)", "unit": "elasticity", "type": "number", "value_range": [-1.0, 0.0]},
        ],
        "optional_parameters": [
            {
                "name": "section",
                "description": (
                    "Replication-package section to run. One of "
                    "'Section 3/benchmark_model' (baseline calibration), "
                    "'Section 5/supply_shocks_to_non_opec' (default — Hormuz-style non-OPEC shock IRFs), "
                    "or 'Section 4/fracking_TD' (transitional fracking dynamics)."
                ),
                "unit": "categorical",
                "type": "string",
            },
            {
                "name": "frisch_elasticity",
                "description": "Override for the Frisch labor-supply elasticity used in the GE block",
                "unit": "elasticity",
                "type": "number",
            },
        ],
    },
    "poles_jrc": {
        "model_id": "poles_jrc",
        "description": "POLES-JRC partial equilibrium model for global energy supply and demand",
        "commodity_system": "oil",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "supply_loss_mbd", "description": "Oil supply loss (cap at 20 — see bornstein_krusell_rebelo.supply_loss_mbd)", "unit": "mb/d", "type": "non_negative_number", "value_range": [0, 20]},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number", "value_range": [0, 24]},
            {"name": "rerouting_cost_multiplier", "description": "Cost multiplier for alternative shipping routes (1.0 = no rerouting; Cape route ~1.4–1.8x)", "unit": "factor", "type": "positive_number", "value_range": [1.0, 4.0]},
            {"name": "insurance_premium_increase_pct", "description": "Increase in shipping insurance premiums", "unit": "percent", "type": "non_negative_number", "value_range": [0, 1000]},
            {
                "name": "substitute_energy_availability",
                "description": (
                    "Availability of substitute energy sources as a fraction in [0.0, 1.0] "
                    "(1 = full substitutability, 0 = none). NOT a percent and NOT a categorical "
                    "label — emit a bare float like 0.4."
                ),
                "unit": "fraction",
                "type": "non_negative_number",
                "value_range": [0.0, 1.0],
            },
        ],
    },
    "marketsim": {
        "model_id": "marketsim",
        "description": "MarketSim (BOEM) — consumer surplus and energy substitution analysis",
        "commodity_system": "oil",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Percentage increase in oil price", "unit": "percent", "type": "number"},
            {"name": "natural_gas_price_change_pct", "description": "Associated change in natural gas price", "unit": "percent", "type": "number"},
            {"name": "disruption_duration_months", "description": "Duration of price shock", "unit": "months", "type": "positive_number"},
        ],
    },
    "fed_oil": {
        "model_id": "fed_oil",
        "description": "Fed Workhorse Oil Model (Baumeister-Hamilton) — US monetary transmission of oil price shocks",
        "commodity_system": "oil",
        "analytical_level": "short_run_macro",
        "required_parameters": [
            {"name": "oil_price_change_pct", "description": "Percentage change in oil price", "unit": "percent", "type": "number"},
            {"name": "shock_type", "description": "Type of oil shock (supply, demand, speculative)", "unit": "categorical", "type": "string"},
            {"name": "disruption_duration_quarters", "description": "Duration of shock in quarters", "unit": "quarters", "type": "positive_number"},
            {"name": "fed_funds_rate_baseline", "description": "Baseline federal funds rate", "unit": "percent", "type": "non_negative_number"},
        ],
    },
}
