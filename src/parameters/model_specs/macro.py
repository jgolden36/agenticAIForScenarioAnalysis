"""Input specifications for macroeconomic / general equilibrium models."""

MACRO_MODEL_SPECS: dict[str, dict] = {
    "nems": {
        "model_id": "nems",
        "description": "NEMS (EIA AEO2025) — integrated U.S. energy-economy model with 16 modules",
        "commodity_system": "macroeconomic",
        "analytical_level": "short_run_macro",
        "platform": "Fortran + AIMMS + Python + GAMS (Windows only)",
        "execution_mode": "output_ingestion (reads pre-computed results; full runs take ~20 hours)",
        "required_parameters": [
            {"name": "scenario_id", "description": "Scenario identifier to locate pre-computed NEMS output directory", "unit": "string", "type": "string"},
        ],
        "optional_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock injected via OGWPRNG override (subprocess mode)", "unit": "percent", "type": "number"},
            {"name": "natural_gas_price_shock_pct", "description": "Natural gas price shock via EXG override", "unit": "percent", "type": "number"},
            {"name": "lng_price_shock_pct", "description": "LNG price shock via EXL override", "unit": "percent", "type": "number"},
            {"name": "industrial_demand_shock_pct", "description": "Industrial demand shock via EXI override", "unit": "percent", "type": "number"},
            {"name": "electricity_demand_shock_pct", "description": "Electricity demand shock via EXE override", "unit": "percent", "type": "number"},
            {"name": "disruption_duration_months", "description": "Disruption duration (clamps LASTYR window)", "unit": "months", "type": "positive_number"},
            {"name": "shock_window_start_year", "description": "First year of the shock window (defaults to baseline_year)", "unit": "year", "type": "positive_number"},
            {"name": "scedes_overrides", "description": "Direct scedes KEY=VALUE overrides; takes precedence over auto-derived ones", "unit": "dict", "type": "dict"},
            {"name": "modules_on", "description": "List of NEMS modules to enable (e.g., ['IDM','EMM'])", "unit": "list", "type": "list"},
            {"name": "modules_off", "description": "List of NEMS modules to disable", "unit": "list", "type": "list"},
            {"name": "base_scedes", "description": "Base scedes scenario name (e.g., 'ref2025')", "unit": "string", "type": "string"},
        ],
        "output_variables": [
            {"name": "oil_price_wti", "description": "WTI oil price", "unit": "$/bbl"},
            {"name": "natural_gas_price_hh", "description": "Henry Hub natural gas price", "unit": "$/MMBtu"},
            {"name": "gdp_growth_pct", "description": "Real GDP growth rate", "unit": "%"},
            {"name": "cpi_inflation_pct", "description": "Consumer price inflation", "unit": "%"},
            {"name": "unemployment_rate_pct", "description": "Unemployment rate", "unit": "%"},
            {"name": "total_energy_consumption_quads", "description": "Total energy consumption", "unit": "quadrillion BTU"},
            {"name": "petroleum_consumption_mbpd", "description": "Petroleum consumption", "unit": "million bbl/day"},
            {"name": "electricity_price_cents_kwh", "description": "Average electricity price", "unit": "cents/kWh"},
            {"name": "refinery_utilization_pct", "description": "Refinery utilization rate", "unit": "%"},
            {"name": "lng_exports_bcf", "description": "LNG exports", "unit": "billion cubic feet"},
        ],
    },
    "mam": {
        "model_id": "mam",
        "description": "MAM (EIA Macroeconomic Activity Module) — IHS Markit-derived U.S. macro forecasts; standalone of NEMS",
        "commodity_system": "macroeconomic",
        "analytical_level": "short_run_macro",
        "platform": "EViews 13+ (Windows) — default mode reads AEO XLSX with openpyxl",
        "execution_mode": "aeo_ingestion (default) or eviews_subprocess",
        "required_parameters": [
            {"name": "scenario_id", "description": "Scenario identifier to locate the AEO worksheet via scenario_sheet_mapping", "unit": "string", "type": "string"},
        ],
        "optional_parameters": [
            {"name": "oil_price_path", "description": "Annual oil price trajectory (eviews_subprocess mode only)", "unit": "usd_per_barrel_series", "type": "list"},
            {"name": "natural_gas_price_path", "description": "Annual natural gas price trajectory (eviews_subprocess mode only)", "unit": "usd_per_mmbtu_series", "type": "list"},
            {"name": "disruption_duration_months", "description": "Disruption duration", "unit": "months", "type": "positive_number"},
        ],
        "output_variables": [
            {"name": "gdp_growth_pct", "description": "Real GDP growth rate", "unit": "%"},
            {"name": "cpi_inflation_pct", "description": "Consumer price inflation", "unit": "%"},
            {"name": "unemployment_rate_pct", "description": "Unemployment rate", "unit": "%"},
            {"name": "industrial_production_index", "description": "Industrial production index", "unit": "index"},
            {"name": "interest_rate_3m", "description": "3-month Treasury bill rate", "unit": "%"},
            {"name": "disposable_income_growth_pct", "description": "Real disposable income growth", "unit": "%"},
            {"name": "federal_funds_rate_pct", "description": "Federal funds rate", "unit": "%"},
        ],
    },
    "nrel": {
        "model_id": "nrel",
        "description": "NREL baseline — electricity sector baseline and disruption impacts",
        "commodity_system": "macroeconomic",
        "analytical_level": "short_run_macro",
        "required_parameters": [
            {"name": "natural_gas_price_change_pct", "description": "Change in natural gas price", "unit": "percent", "type": "number"},
            {"name": "electricity_demand_change_pct", "description": "Change in electricity demand", "unit": "percent", "type": "number"},
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number"},
        ],
    },
    "mpsge_jl": {
        "model_id": "mpsge_jl",
        "description": "MPSGE.jl / GTAP — Julia-based CGE trade and welfare analysis",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock", "unit": "percent", "type": "number", "value_range": [-100.0, 500.0]},
            {"name": "trade_disruption_spec", "description": "Specification of disrupted trade routes and volumes (object with keys like 'corridors' [list], 'volume_disruption_pct' [number])", "unit": "spec", "type": "dict"},
            {
                "name": "commodity_price_shocks",
                "description": (
                    "Dict mapping commodity name -> percentage price shock as a bare number "
                    "(e.g. {\"lng\": 40.0}). Do NOT wrap each value in {shock, unit}. "
                    "Recognised commodity keys: 'oil', 'lng', 'fertilizer', 'helium', "
                    "and 'water' (the latter is interpreted as an unmet-demand "
                    "percentage and is only injected automatically by the upstream-"
                    "to-macro merge under the infrastructure_collapse scenario)."
                ),
                "unit": "dict[str, percent]",
                "type": "dict",
                "value_schema": "dict[str, number]",
            },
            {"name": "disruption_duration_months", "description": "Duration of disruption", "unit": "months", "type": "positive_number", "value_range": [0, 24]},
        ],
    },
    "opencge": {
        "model_id": "opencge",
        "description": "OpenCGE (PSL OG-Core / OG-USA) — dynamic OLG CGE for cross-validation",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "platform": "Python (ogcore + ogusa + dask[distributed])",
        "required_parameters": [
            {
                "name": "oil_price_shock_pct",
                "description": "Oil price shock (mapped to aggregate productivity Z); positive = price increase",
                "unit": "percent",
                "type": "number",
                "value_range": [-100.0, 500.0],
            },
            {
                "name": "commodity_price_shocks",
                "description": (
                    "Dict mapping commodity name to a percentage price shock (mapped via "
                    "shock_to_productivity). Recognised commodity keys: 'oil', 'lng', "
                    "'fertilizer', 'helium', and 'water' (the latter is interpreted as "
                    "the CWatM unmet-demand percentage and is normally only injected by "
                    "the upstream-to-macro merge under the infrastructure_collapse "
                    "scenario). Each VALUE must be a bare number (e.g. 40.0 for +40%), "
                    "NOT an object like {'shock': 40, 'unit': 'percent'}. "
                    "Example: {\"lng\": 40.0, \"fertilizer\": 25.0}."
                ),
                "unit": "dict[str, percent]",
                "type": "dict",
                "value_schema": "dict[str, number] — keys are commodity names from {oil, lng, fertilizer, helium, water}; values are bare percentage numbers (no nested {shock, unit} objects).",
            },
            {"name": "disruption_duration_months", "description": "Duration of disruption (drives the Z time-path window)", "unit": "months", "type": "positive_number", "value_range": [0, 24]},
        ],
        "optional_parameters": [
            {"name": "closure_rule", "description": "Macro closure: 'full_employment' or 'fixed_capital'", "unit": "categorical", "type": "string"},
            {"name": "solution_method", "description": "'TPI' (transition path) or 'SS' (steady state only)", "unit": "categorical", "type": "string"},
            {"name": "baseline_year", "description": "First year of the simulation (start_year in OG-Core)", "unit": "year", "type": "positive_number"},
            {"name": "budget_balance", "description": "Force government budget balance (lump-sum closure)", "unit": "boolean", "type": "boolean"},
        ],
        "output_variables": [
            {"name": "welfare_pct_change", "description": "Hicksian-equivalent welfare change at SS", "unit": "%"},
            {"name": "gdp_pct_change_path", "description": "GDP percent-change-from-baseline path", "unit": "% per year"},
            {"name": "wage_pct_change_path", "description": "Real wage percent-change-from-baseline path", "unit": "% per year"},
            {"name": "interest_rate_path", "description": "Real interest rate path", "unit": "% per year"},
            {"name": "consumption_pct_change", "description": "Aggregate consumption percent-change path", "unit": "% per year"},
            {"name": "gdp_impact_pct", "description": "Year-1 GDP impact (consistency-check scalar)", "unit": "%"},
        ],
    },
    "pycge": {
        "model_id": "pycge",
        "description": "PyCGE (cge_modeling) — static Python CGE for sensitivity analysis and cross-validation",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "platform": "Python (cge_modeling + scipy/jax)",
        "required_parameters": [
            {
                "name": "oil_price_shock_pct",
                "description": "Oil price shock (mapped to SAM parameter); positive = price increase",
                "unit": "percent",
                "type": "number",
                "value_range": [-100.0, 500.0],
            },
            {
                "name": "commodity_price_shocks",
                "description": (
                    "Dict mapping commodity name to a percentage price shock (mapped via "
                    "commodity_to_sam_param). Recognised commodity keys: 'oil', 'lng', "
                    "'fertilizer', 'helium', and 'water' (the latter is interpreted as "
                    "the CWatM unmet-demand percentage and is normally only injected by "
                    "the upstream-to-macro merge under the infrastructure_collapse "
                    "scenario). Each VALUE must be a bare number (e.g. 40.0 for +40%), "
                    "NOT an object like {'shock': 40, 'unit': 'percent'}. "
                    "Example: {\"lng\": 40.0, \"fertilizer\": 25.0}."
                ),
                "unit": "dict[str, percent]",
                "type": "dict",
                "value_schema": "dict[str, number] — keys are commodity names from {oil, lng, fertilizer, helium, water}; values are bare percentage numbers (no nested {shock, unit} objects).",
            },
            {"name": "disruption_duration_months", "description": "Disruption duration (annotates output, does not affect static solve)", "unit": "months", "type": "positive_number", "value_range": [0, 24]},
        ],
        "optional_parameters": [
            {"name": "numeraire", "description": "cge_modeling numeraire variable", "unit": "string", "type": "string"},
            {"name": "solver", "description": "Solver: 'root', 'minimize', or 'euler'", "unit": "categorical", "type": "string"},
            {"name": "tol", "description": "Solver tolerance", "unit": "float", "type": "positive_number"},
            {"name": "rebuild_baseline", "description": "Force baseline equilibrium rebuild", "unit": "boolean", "type": "boolean"},
        ],
        "output_variables": [
            {"name": "gdp_impact_pct", "description": "GDP impact at new equilibrium (consistency-check scalar)", "unit": "%"},
            {"name": "consumption_impact_pct", "description": "Aggregate consumption impact", "unit": "%"},
            {"name": "wage_impact_pct", "description": "Wage impact", "unit": "%"},
            {"name": "welfare_pct_change", "description": "Hicksian-equivalent variation", "unit": "%"},
            {"name": "sectoral_output_pct_change", "description": "Sector-by-sector output deltas", "unit": "dict[%]"},
        ],
    },
    "miragrodep": {
        "model_id": "miragrodep",
        "description": "MIRAGRODEP — multi-region CGE with agricultural-trade linkages (live GAMS)",
        "commodity_system": "macroeconomic",
        "analytical_level": "long_run_macro_strategic",
        "platform": "GAMS (CONOPT or PATH solver)",
        "execution_mode": "calib → MSD → REF → Simul phase sequence with auto-injected shock includes",
        "required_parameters": [
            {"name": "oil_price_shock_pct", "description": "Oil price shock (injected via shock_oil.inc on the 'ffl' sector)", "unit": "percent", "type": "number"},
            {"name": "fertilizer_price_shock_pct", "description": "Fertilizer price shock (injected via shock_fertilizer.inc on the 'crp' sector)", "unit": "percent", "type": "number"},
            {"name": "agricultural_trade_disruption_spec", "description": "Trade shock: {'affected_corridors': [(O,D), ...], 'shipping_cost_multiplier': float, 'affected_commodities': [sector, ...]}", "unit": "spec", "type": "dict"},
            {"name": "disruption_duration_months", "description": "Duration of disruption (annotated in metadata)", "unit": "months", "type": "positive_number"},
        ],
        "optional_parameters": [
            {"name": "skip_calib_if_present", "description": "Reuse calibration / MSD / REF restarts across scenarios", "unit": "boolean", "type": "boolean"},
            {"name": "keep_working_copy", "description": "Preserve the per-scenario working copy after completion", "unit": "boolean", "type": "boolean"},
        ],
        "output_variables": [
            {"name": "world_aggregate_vars", "description": "Records from Results/var.csv", "unit": "list[dict]"},
            {"name": "regional_vars", "description": "Records from Results/R_var.csv", "unit": "list[dict]"},
            {"name": "regional_sectoral_vars", "description": "Records from Results/RS_var.csv", "unit": "list[dict]"},
            {"name": "interregional_vars", "description": "Records from Results/IR_var.csv", "unit": "list[dict]"},
            {"name": "welfare_pct_change", "description": "Headline welfare scalar (extracted from regional_vars when present)", "unit": "%"},
            {"name": "gdp_impact_pct", "description": "Headline GDP scalar (extracted from regional_vars when present)", "unit": "%"},
        ],
    },
}
