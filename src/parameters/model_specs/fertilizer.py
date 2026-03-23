"""Input specifications for fertilizer and agricultural trade domain models."""

FERTILIZER_MODEL_SPECS: dict[str, dict] = {
    "capri": {
        "model_id": "capri",
        "description": "CAPRI — regional agricultural policy impact modeling",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_price_shock_pct", "description": "Percentage increase in fertilizer prices", "unit": "percent"},
            {"name": "energy_price_change_pct", "description": "Change in energy prices affecting agriculture", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "magpie": {
        "model_id": "magpie",
        "description": "MAgPIE — land-use and agricultural production optimization",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_price_shock_pct", "description": "Percentage increase in fertilizer prices", "unit": "percent"},
            {"name": "crop_yield_impact_pct", "description": "Direct impact on crop yields", "unit": "percent"},
            {"name": "water_availability_change_pct", "description": "Change in agricultural water availability", "unit": "percent"},
        ],
    },
    "simple_g": {
        "model_id": "simple_g",
        "description": "SIMPLE-G — general equilibrium agricultural trade model",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_price_shock_pct", "description": "Percentage increase in fertilizer prices", "unit": "percent"},
            {"name": "energy_price_shock_pct", "description": "Percentage increase in energy prices", "unit": "percent"},
            {"name": "trade_disruption_index", "description": "Index of agricultural trade disruption", "unit": "index"},
        ],
    },
    "world_fertilizer": {
        "model_id": "world_fertilizer",
        "description": "World Fertilizer Model — global fertilizer supply-demand dynamics",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "natural_gas_price_change_pct", "description": "Change in natural gas price (key input)", "unit": "percent"},
            {"name": "middle_east_production_loss_pct", "description": "Loss of Middle East fertilizer production", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "gtap": {
        "model_id": "gtap",
        "description": "GTAP — global agricultural and commodity trade flow CGE",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent"},
            {"name": "fertilizer_price_shock_pct", "description": "Fertilizer price shock", "unit": "percent"},
            {"name": "trade_route_disruption_spec", "description": "Specification of disrupted trade routes", "unit": "spec"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "apsim": {
        "model_id": "apsim",
        "description": "APSIM — physical crop yield response to input disruption",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_application_reduction_pct", "description": "Reduction in fertilizer application", "unit": "percent"},
            {"name": "irrigation_water_reduction_pct", "description": "Reduction in irrigation water", "unit": "percent"},
            {"name": "growing_season", "description": "Affected growing season(s)", "unit": "categorical"},
        ],
    },
    "futures": {
        "model_id": "futures",
        "description": "Commodity futures price trajectory forecasting",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "initial_price_shock_pct", "description": "Initial commodity price shock", "unit": "percent"},
            {"name": "commodities", "description": "List of commodities to forecast", "unit": "list"},
            {"name": "forecast_horizon_months", "description": "Forecast time horizon", "unit": "months"},
        ],
    },
}
