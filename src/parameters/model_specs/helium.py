"""Input specifications for helium and semiconductor domain models."""

HELIUM_MODEL_SPECS: dict[str, dict] = {
    "world_helium_model": {
        "model_id": "world_helium_model",
        "description": "World Helium Model (IFP Energies Nouvelles) — global helium supply-demand equilibrium",
        "commodity_system": "helium_semiconductors",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "qatar_helium_supply_loss_pct", "description": "Percentage loss of Qatar helium supply (% of global)", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of supply disruption", "unit": "months"},
            {"name": "strategic_reserve_release", "description": "Whether strategic helium reserves are released", "unit": "boolean"},
        ],
    },
    "argonne_abm": {
        "model_id": "argonne_abm",
        "description": "Argonne Helium ABM — agent-based model of contemporary helium market dynamics",
        "commodity_system": "helium_semiconductors",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "supply_shock_pct", "description": "Percentage reduction in global helium supply", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
            {"name": "demand_response_elasticity", "description": "Demand-side response elasticity", "unit": "elasticity"},
        ],
    },
    "simrlfab": {
        "model_id": "simrlfab",
        "description": "SimRLFab — RL simulation of semiconductor fabrication disruption impacts",
        "commodity_system": "helium_semiconductors",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "helium_supply_reduction_pct", "description": "Reduction in helium supply for semiconductor fabs", "unit": "percent"},
            {"name": "neon_supply_status", "description": "Status of neon gas supply (used in lithography)", "unit": "categorical"},
            {"name": "disruption_duration_months", "description": "Duration of supply disruption", "unit": "months"},
            {"name": "fab_utilization_baseline", "description": "Baseline fab utilization rate", "unit": "percent"},
        ],
    },
}
