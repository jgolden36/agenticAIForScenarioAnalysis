"""Input specifications for LNG domain models."""

LNG_MODEL_SPECS: dict[str, dict] = {
    "energy_flux_gas_power": {
        "model_id": "energy_flux_gas_power",
        "description": "Energy Flux US Gas Power Build-Out Constraint Model v1.0",
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "lng_supply_disruption_pct", "description": "Percentage of global LNG supply disrupted", "unit": "percent"},
            {"name": "us_gas_price_change_pct", "description": "Change in US natural gas price", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of LNG supply disruption", "unit": "months"},
        ],
    },
    "energy_flux_lng_profits": {
        "model_id": "energy_flux_lng_profits",
        "description": "Energy Flux US LNG War Profits Model v1.0",
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "lng_spot_price_premium_pct", "description": "Premium on LNG spot prices", "unit": "percent"},
            {"name": "us_export_capacity_utilization", "description": "US LNG export capacity utilization rate", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "ggm": {
        "model_id": "ggm",
        "description": "Global Gas Model — global gas trade flow optimization",
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "strait_closure_flag", "description": "Whether the Strait of Hormuz is closed", "unit": "boolean"},
            {"name": "qatar_lng_export_loss_pct", "description": "Percentage loss of Qatar LNG exports", "unit": "percent"},
            {"name": "rerouting_available", "description": "Whether pipeline or alternative route rerouting is possible", "unit": "boolean"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "lngst": {
        "model_id": "lngst",
        "description": "LNG Spreadsheet Tool — Excel-based LNG trade flow simulation",
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "qatar_export_reduction_pct", "description": "Reduction in Qatar LNG exports", "unit": "percent"},
            {"name": "uae_export_reduction_pct", "description": "Reduction in UAE LNG exports", "unit": "percent"},
            {"name": "spot_price_multiplier", "description": "Multiplier on LNG spot prices", "unit": "factor"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
}
