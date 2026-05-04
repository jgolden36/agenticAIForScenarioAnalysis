"""Input specifications for fertilizer and agricultural trade domain models."""

FERTILIZER_MODEL_SPECS: dict[str, dict] = {
    "capri": {
        "model_id": "capri",
        "description": "CAPRI — regional agricultural policy impact modeling",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_price_shock_pct", "description": "Percentage increase in fertilizer prices", "unit": "percent", "type": "number"},
            {"name": "energy_price_change_pct", "description": "Change in energy prices affecting agriculture", "unit": "percent", "type": "number"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number"},
        ],
    },
    "magpie": {
        "model_id": "magpie",
        "description": "MAgPIE — recursive-dynamic land-use and agricultural production optimization (PIK)",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "platform": "GAMS (CONOPT solver) orchestrated via R",
        "required_parameters": [
            {"name": "fertilizer_price_shock_pct", "description": "Percentage increase in fertilizer prices (affects module 38 factor costs)", "unit": "percent", "type": "number"},
            {"name": "crop_yield_impact_pct", "description": "Direct impact on crop yields (negative = reduction; module 14)", "unit": "percent", "type": "number"},
            {"name": "water_availability_change_pct", "description": "Change in agricultural water availability (negative = less water; module 43)", "unit": "percent", "type": "number"},
        ],
        "optional_parameters": [
            {"name": "energy_price_shock_pct", "description": "Energy price increase affecting transport costs (module 40)", "unit": "percent", "type": "number"},
            {"name": "trade_restriction_flag", "description": "Whether to tighten trade self-sufficiency constraints (module 21)", "unit": "boolean", "type": "boolean"},
            {"name": "affected_regions", "description": "ISO country codes for region-specific shocks", "unit": "list", "type": "list"},
            {"name": "ssp_scenario", "description": "SSP scenario for population/GDP drivers: SSP1-SSP5", "unit": "categorical", "type": "string"},
        ],
        "output_variables": [
            {"name": "production", "description": "Agricultural production by crop group", "unit": "Mt/yr"},
            {"name": "prices", "description": "Food prices by commodity", "unit": "$/t"},
            {"name": "land_use", "description": "Land cover by type", "unit": "Mha"},
            {"name": "water_use", "description": "Agricultural water use", "unit": "km³/yr"},
            {"name": "fertilizer_use", "description": "Nitrogen fertilizer use", "unit": "Mt N/yr"},
            {"name": "emissions", "description": "GHG emissions from land use", "unit": "Mt CO2eq/yr"},
        ],
    },
    "simple_g": {
        "model_id": "simple_g",
        "description": "SIMPLE-G — general equilibrium agricultural trade model",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_price_shock_pct", "description": "Percentage increase in fertilizer prices", "unit": "percent", "type": "number"},
            {"name": "energy_price_shock_pct", "description": "Percentage increase in energy prices", "unit": "percent", "type": "number"},
            {"name": "trade_disruption_index", "description": "Index of agricultural trade disruption", "unit": "index", "type": "non_negative_number"},
        ],
    },
    "world_fertilizer": {
        "model_id": "world_fertilizer",
        "description": "World Fertilizer Model — global fertilizer supply-demand dynamics",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "natural_gas_price_change_pct", "description": "Change in natural gas price (key input)", "unit": "percent", "type": "number"},
            {"name": "middle_east_production_loss_pct", "description": "Loss of Middle East fertilizer production", "unit": "percent", "type": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number"},
        ],
    },
    "gtap": {
        "model_id": "gtap",
        "description": "GTAP — global agricultural and commodity trade flow CGE",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent", "type": "number"},
            {"name": "fertilizer_price_shock_pct", "description": "Fertilizer price shock", "unit": "percent", "type": "number"},
            {"name": "trade_route_disruption_spec", "description": "Specification of disrupted trade routes", "unit": "spec", "type": "dict"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number"},
        ],
    },
    "apsim": {
        "model_id": "apsim",
        "description": "APSIM — physical crop yield response to input disruption",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "fertilizer_application_reduction_pct", "description": "Reduction in fertilizer application", "unit": "percent", "type": "percent"},
            {"name": "irrigation_water_reduction_pct", "description": "Reduction in irrigation water", "unit": "percent", "type": "percent"},
            {"name": "growing_season", "description": "Affected growing season(s)", "unit": "categorical", "type": "string"},
        ],
    },
    "futures": {
        "model_id": "futures",
        "description": "Commodity futures price trajectory forecasting",
        "commodity_system": "fertilizer_agriculture",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "initial_price_shock_pct", "description": "Initial commodity price shock", "unit": "percent", "type": "number"},
            {"name": "commodities", "description": "List of commodities to forecast", "unit": "list", "type": "list"},
            {"name": "forecast_horizon_months", "description": "Forecast time horizon", "unit": "months", "type": "positive_number"},
        ],
    },
}
