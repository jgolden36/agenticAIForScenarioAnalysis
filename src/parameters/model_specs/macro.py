"""Input specifications for macroeconomic / general equilibrium models."""

MACRO_MODEL_SPECS: dict[str, dict] = {
    "nems": {
        "model_id": "nems",
        "description": "NEMS (EIA baseline) — national energy-economy baseline projections",
        "commodity_system": "macroeconomic",
        "analytical_level": "short_run_macro",
        "required_parameters": [
            {"name": "oil_price_path", "description": "Oil price trajectory over disruption period", "unit": "usd_per_barrel_series"},
            {"name": "natural_gas_price_path", "description": "Natural gas price trajectory", "unit": "usd_per_mmbtu_series"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "nrel": {
        "model_id": "nrel",
        "description": "NREL baseline — electricity sector baseline and disruption impacts",
        "commodity_system": "macroeconomic",
        "analytical_level": "short_run_macro",
        "required_parameters": [
            {"name": "natural_gas_price_change_pct", "description": "Change in natural gas price", "unit": "percent"},
            {"name": "electricity_demand_change_pct", "description": "Change in electricity demand", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "mpsge_jl": {
        "model_id": "mpsge_jl",
        "description": "MPSGE.jl / GTAP — Julia-based CGE trade and welfare analysis",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent"},
            {"name": "trade_disruption_spec", "description": "Specification of disrupted trade routes and volumes", "unit": "spec"},
            {"name": "commodity_price_shocks", "description": "Dict of commodity price shocks from upstream models", "unit": "dict"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "opencge": {
        "model_id": "opencge",
        "description": "OpenCGE — open-source CGE for cross-validation",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent"},
            {"name": "commodity_price_shocks", "description": "Dict of commodity price shocks", "unit": "dict"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "pycge": {
        "model_id": "pycge",
        "description": "pycge / cge_modeling — Python CGE for sensitivity analysis",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent"},
            {"name": "commodity_price_shocks", "description": "Dict of commodity price shocks", "unit": "dict"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "miragrodep": {
        "model_id": "miragrodep",
        "description": "MIRAGRODEP — multi-region CGE with agricultural-trade linkages",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent"},
            {"name": "fertilizer_price_shock_pct", "description": "Fertilizer price shock", "unit": "percent"},
            {"name": "agricultural_trade_disruption_spec", "description": "Agricultural trade disruption specification", "unit": "spec"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
}
