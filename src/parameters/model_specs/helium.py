"""Input specifications for helium and semiconductor domain models."""

HELIUM_MODEL_SPECS: dict[str, dict] = {
    "world_helium_model": {
        "model_id": "world_helium_model",
        "description": "World Helium Model (IFP Energies Nouvelles) — global helium supply-demand equilibrium",
        "commodity_system": "helium_semiconductors",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "qatar_helium_supply_loss_pct", "description": "Percentage loss of Qatar helium supply (% of global)", "unit": "percent", "type": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of supply disruption", "unit": "months", "type": "positive_number"},
            {"name": "strategic_reserve_release", "description": "Whether strategic helium reserves are released", "unit": "boolean", "type": "boolean"},
        ],
    },
    "argonne_abm": {
        "model_id": "argonne_abm",
        "description": "Argonne Helium ABM — agent-based model of contemporary helium market dynamics",
        "commodity_system": "helium_semiconductors",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "supply_shock_pct", "description": "Percentage reduction in global helium supply", "unit": "percent", "type": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number", "value_range": [0, 24]},
            {
                "name": "demand_response_elasticity",
                "description": (
                    "Own-price demand elasticity for helium — MUST be a NEGATIVE number "
                    "(typical helium short-run elasticity ~ -0.3 to -0.8). Do NOT emit a "
                    "positive value; that would imply demand rises with price."
                ),
                "unit": "elasticity",
                "type": "number",
                "value_range": [-2.0, 0.0],
            },
        ],
    },
    "simrlfab": {
        "model_id": "simrlfab",
        "description": "SimRLFab — RL simulation of semiconductor fabrication disruption impacts",
        "commodity_system": "helium_semiconductors",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "helium_supply_reduction_pct", "description": "Reduction in helium supply for semiconductor fabs", "unit": "percent", "type": "percent"},
            {
                "name": "neon_supply_status",
                "description": "Status of neon gas supply (used in lithography)",
                "unit": "categorical",
                "type": "string",
                "valid_values": ["normal", "constrained", "severely_disrupted"],
            },
            {"name": "disruption_duration_months", "description": "Duration of supply disruption", "unit": "months", "type": "positive_number", "value_range": [0, 36]},
            {
                "name": "fab_utilization_baseline",
                "description": (
                    "Baseline fab utilization rate as a FRACTION in [0.0, 1.0] "
                    "(0.85 = 85% utilised). NOT a percent — write 0.85, not 85. "
                    "Industry baseline is typically 0.80–0.95."
                ),
                "unit": "fraction",
                "type": "non_negative_number",
                "value_range": [0.0, 1.0],
            },
        ],
    },
}
