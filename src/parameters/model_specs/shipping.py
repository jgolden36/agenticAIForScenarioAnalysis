"""Input specifications for shipping domain models."""

SHIPPING_MODEL_SPECS: dict[str, dict] = {
    "aisdb": {
        "model_id": "aisdb",
        "description": "AISdb — AIS vessel tracking data processing and rerouting calibration",
        "commodity_system": "shipping",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "strait_closure_flag", "description": "Whether the Strait of Hormuz is closed", "unit": "boolean", "type": "boolean"},
            {
                "name": "alternative_routes",
                "description": (
                    "List of alternative shipping routes to evaluate. Use the EXACT snake_case "
                    "identifiers below — free-text labels like 'Suez Canal' or 'Bosphorus' will "
                    "be rejected. For Hormuz closure scenarios the relevant rerouting option is "
                    "typically ['cape_of_good_hope']."
                ),
                "unit": "list[str]",
                "type": "list",
                "value_schema": "list of strings drawn from valid_values",
                "valid_values": ["cape_of_good_hope", "suez_canal", "northern_sea_route", "none"],
            },
            {
                "name": "vessel_types",
                "description": (
                    "Types of vessels to analyze. Use the EXACT snake_case identifiers below — "
                    "free-text labels like 'LNG' or 'Container Ship' will be rejected. "
                    "LNG carriers are 'lng_carrier'; oil tankers are 'tanker'."
                ),
                "unit": "list[str]",
                "type": "list",
                "value_schema": "list of strings drawn from valid_values",
                "valid_values": [
                    "bulk_carrier",
                    "chemical_tanker",
                    "container",
                    "general_cargo",
                    "lng_carrier",
                    "tanker",
                ],
            },
        ],
    },
    "ais_project": {
        "model_id": "ais_project",
        "description": "AIS_project — transit time and fleet utilization under Strait closure",
        "commodity_system": "shipping",
        "analytical_level": "commodity",
        "required_parameters": [
            {"name": "strait_closure_flag", "description": "Whether the Strait is closed", "unit": "boolean", "type": "boolean"},
            {"name": "rerouting_via_cape", "description": "Whether Cape of Good Hope rerouting is in effect", "unit": "boolean", "type": "boolean"},
            {"name": "fleet_size_change_pct", "description": "Change in available fleet size", "unit": "percent", "type": "number"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number"},
        ],
    },
}
