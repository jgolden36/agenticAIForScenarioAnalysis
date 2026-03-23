"""Input specifications for oil domain models."""

OIL_MODEL_SPECS: dict[str, dict] = {
    "bornstein_krusell_rebelo": {
        "model_id": "bornstein_krusell_rebelo",
        "description": "World Equilibrium Model of the Oil Market — structural GE supply disruption analysis",
        "commodity_system": "oil",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "supply_loss_mbd", "description": "Oil supply loss in million barrels per day", "unit": "mb/d"},
            {"name": "disruption_duration_months", "description": "Duration of supply disruption", "unit": "months"},
            {"name": "spr_release_mbd", "description": "Strategic Petroleum Reserve release rate", "unit": "mb/d"},
            {"name": "opec_spare_capacity_mbd", "description": "Available OPEC spare production capacity", "unit": "mb/d"},
            {"name": "demand_elasticity_override", "description": "Override for short-run demand elasticity (optional)", "unit": "elasticity"},
        ],
    },
    "poles_jrc": {
        "model_id": "poles_jrc",
        "description": "POLES-JRC partial equilibrium model for global energy supply and demand",
        "commodity_system": "oil",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "supply_loss_mbd", "description": "Oil supply loss", "unit": "mb/d"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
            {"name": "rerouting_cost_multiplier", "description": "Cost multiplier for alternative shipping routes", "unit": "factor"},
            {"name": "insurance_premium_increase_pct", "description": "Increase in shipping insurance premiums", "unit": "percent"},
            {"name": "substitute_energy_availability", "description": "Availability of substitute energy sources", "unit": "categorical"},
        ],
    },
    "marketsim": {
        "model_id": "marketsim",
        "description": "MarketSim (BOEM) — consumer surplus and energy substitution analysis",
        "commodity_system": "oil",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Percentage increase in oil price", "unit": "percent"},
            {"name": "natural_gas_price_change_pct", "description": "Associated change in natural gas price", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of price shock", "unit": "months"},
        ],
    },
    "fed_oil": {
        "model_id": "fed_oil",
        "description": "Fed Workhorse Oil Model (Baumeister-Hamilton) — US monetary transmission of oil price shocks",
        "commodity_system": "oil",
        "analytical_level": "short_run_macro",
        "required_parameters": [
            {"name": "oil_price_change_pct", "description": "Percentage change in oil price", "unit": "percent"},
            {"name": "shock_type", "description": "Type of oil shock (supply, demand, speculative)", "unit": "categorical"},
            {"name": "disruption_duration_quarters", "description": "Duration of shock in quarters", "unit": "quarters"},
            {"name": "fed_funds_rate_baseline", "description": "Baseline federal funds rate", "unit": "percent"},
        ],
    },
}
