"""Input specifications for shipping domain models."""

SHIPPING_MODEL_SPECS: dict[str, dict] = {
    "aisdb": {
        "model_id": "aisdb",
        "description": "AISdb — AIS vessel tracking data processing and rerouting calibration",
        "commodity_system": "shipping",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "strait_closure_flag", "description": "Whether the Strait of Hormuz is closed", "unit": "boolean"},
            {"name": "alternative_routes", "description": "List of alternative shipping routes to evaluate", "unit": "list"},
            {"name": "vessel_types", "description": "Types of vessels to analyze (tanker, LNG, container)", "unit": "list"},
        ],
    },
    "ais_project": {
        "model_id": "ais_project",
        "description": "AIS_project — transit time and fleet utilization under Strait closure",
        "commodity_system": "shipping",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "strait_closure_flag", "description": "Whether the Strait is closed", "unit": "boolean"},
            {"name": "rerouting_via_cape", "description": "Whether Cape of Good Hope rerouting is in effect", "unit": "boolean"},
            {"name": "fleet_size_change_pct", "description": "Change in available fleet size", "unit": "percent"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months"},
        ],
    },
}
