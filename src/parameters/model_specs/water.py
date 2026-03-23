"""Input specifications for water domain models."""

WATER_MODEL_SPECS: dict[str, dict] = {
    "weap_mena": {
        "model_id": "weap_mena",
        "description": "WEAP-MENA integrated water resource planning for Persian Gulf region",
        "commodity_system": "water",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "desalination_capacity_loss_pct", "description": "Percentage of desalination capacity lost due to conflict", "unit": "percent"},
            {"name": "disruption_duration_weeks", "description": "Duration of infrastructure disruption", "unit": "weeks"},
            {"name": "affected_countries", "description": "List of countries with disrupted water supply", "unit": "list"},
            {"name": "alternative_supply_available", "description": "Whether alternative water sources are accessible", "unit": "boolean"},
            {"name": "population_affected_millions", "description": "Population dependent on disrupted desalination", "unit": "millions"},
        ],
    },
    "sahysmod": {
        "model_id": "sahysmod",
        "description": "Spatially distributed agro-hydro-salinity modeling",
        "commodity_system": "water",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "irrigation_water_reduction_pct", "description": "Reduction in irrigation water availability", "unit": "percent"},
            {"name": "salinity_increase_factor", "description": "Factor increase in soil/water salinity", "unit": "factor"},
            {"name": "disruption_duration_weeks", "description": "Duration of water supply disruption", "unit": "weeks"},
        ],
    },
    "watergap2": {
        "model_id": "watergap2",
        "description": "Global gridded hydrological modeling of infrastructure disruption",
        "commodity_system": "water",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "infrastructure_damage_index", "description": "Index of water infrastructure damage (0-1 scale)", "unit": "index"},
            {"name": "affected_grid_cells", "description": "Geographic extent of disruption", "unit": "region_spec"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
    "cwatm": {
        "model_id": "cwatm",
        "description": "Community-scale water availability under disruption",
        "commodity_system": "water",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "water_demand_change_pct", "description": "Change in water demand due to crisis", "unit": "percent"},
            {"name": "supply_infrastructure_status", "description": "Status of water supply infrastructure", "unit": "categorical"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
}
