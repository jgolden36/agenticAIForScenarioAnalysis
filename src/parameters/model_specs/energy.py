"""Input specifications for energy-systems domain models.

Covers OSeMOSYS, MESSAGEix, and TEMOA. These models operate at the
LONG_RUN_MACRO_STRATEGIC analytical level and ingest fuel-supply,
fuel-price, and capital-cost shocks derived from a Hormuz-class
commodity disruption.
"""

ENERGY_MODEL_SPECS: dict[str, dict] = {
    "osemosys": {
        "model_id": "osemosys",
        "description": (
            "OSeMOSYS — Open Source Energy Modelling System. Long-run least-cost "
            "capacity expansion (GLPK MathProg). Used here to project the energy-mix "
            "response to sustained oil/gas supply disruption."
        ),
        "commodity_system": "energy_systems",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_supply_loss_mbd", "description": "Oil supply loss attributable to the disruption", "unit": "mb/d"},
            {"name": "gas_supply_loss_bcfd", "description": "Natural gas supply loss attributable to the disruption", "unit": "bcf/d"},
            {"name": "disruption_duration_months", "description": "Duration of the supply disruption", "unit": "months"},
            {"name": "oil_price_path_override_usd", "description": "Optional exogenous Brent price path ($/bbl) overriding model defaults", "unit": "usd_per_bbl"},
            {"name": "lng_export_capacity_loss_pct", "description": "Reduction in global LNG export capacity from infrastructure damage", "unit": "percent"},
            {"name": "capital_cost_multiplier", "description": "Multiplier on new-build capital costs (war risk premium)", "unit": "factor"},
            {"name": "co2_price_baseline_usd_per_t", "description": "Baseline carbon price assumed in the long-run scenario", "unit": "usd_per_tCO2"},
        ],
    },
    "messageix": {
        "model_id": "messageix",
        "description": (
            "MESSAGEix (IIASA) — integrated assessment energy-systems model with "
            "ixmp scenario management. Used for global long-run energy-mix "
            "projections under disruption shocks."
        ),
        "commodity_system": "energy_systems",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_supply_loss_mbd", "description": "Oil supply loss attributable to the disruption", "unit": "mb/d"},
            {"name": "gas_supply_loss_bcfd", "description": "Natural gas supply loss attributable to the disruption", "unit": "bcf/d"},
            {"name": "disruption_duration_months", "description": "Duration of the supply disruption", "unit": "months"},
            {"name": "oil_price_path_override_usd", "description": "Optional exogenous Brent price path ($/bbl)", "unit": "usd_per_bbl"},
            {"name": "lng_export_capacity_loss_pct", "description": "Reduction in global LNG export capacity", "unit": "percent"},
            {"name": "capital_cost_multiplier", "description": "Multiplier on new-build capital costs", "unit": "factor"},
            {"name": "co2_price_baseline_usd_per_t", "description": "Baseline carbon price", "unit": "usd_per_tCO2"},
        ],
    },
    "temoa": {
        "model_id": "temoa",
        "description": (
            "TEMOA — Tools for Energy Model Optimization and Analysis. Pyomo-based "
            "open-source energy systems optimization. Used for US-scope long-run "
            "capacity expansion under disruption shocks."
        ),
        "commodity_system": "energy_systems",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_supply_loss_mbd", "description": "Oil supply loss attributable to the disruption", "unit": "mb/d"},
            {"name": "gas_supply_loss_bcfd", "description": "Natural gas supply loss attributable to the disruption", "unit": "bcf/d"},
            {"name": "disruption_duration_months", "description": "Duration of the supply disruption", "unit": "months"},
            {"name": "oil_price_path_override_usd", "description": "Optional exogenous Brent price path ($/bbl)", "unit": "usd_per_bbl"},
            {"name": "lng_export_capacity_loss_pct", "description": "Reduction in global LNG export capacity", "unit": "percent"},
            {"name": "capital_cost_multiplier", "description": "Multiplier on new-build capital costs", "unit": "factor"},
            {"name": "co2_price_baseline_usd_per_t", "description": "Baseline carbon price", "unit": "usd_per_tCO2"},
        ],
    },
}
