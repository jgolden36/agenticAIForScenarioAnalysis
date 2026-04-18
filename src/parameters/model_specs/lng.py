"""Input specifications for LNG domain models.

These specs define the parameter interface between the LLM-based parameter
extraction module (Module 2) and the model adapters (Module 3).  The
parameter extractor uses these specs to know *what* to extract from each
scenario narrative; the adapter's ``translate_inputs`` then maps the
extracted parameters to the model's native format.
"""

LNG_MODEL_SPECS: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Energy Flux US Gas Power Build-Out Constraint Model v1.0
    # ------------------------------------------------------------------
    "energy_flux_gas_power": {
        "model_id": "energy_flux_gas_power",
        "description": (
            "Energy Flux US Gas Power Build-Out Constraint Model v1.0: "
            "throughput-constrained commissioning model for US gas-fired "
            "power capacity.  Translates pipeline MW into year-by-year "
            "capacity additions and incremental gas demand (Bcf/d)."
        ),
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "platform": "Excel (openpyxl / xlwings)",
        "required_parameters": [
            {
                "name": "build_scenario",
                "description": (
                    "Build-cap scenario: 'conservative' (7,264 MW/yr), "
                    "'central' (10,135 MW/yr), 'stretch' (22,697 MW/yr), "
                    "or '2002_dash' (63,975 MW/yr)"
                ),
                "unit": "categorical",
                "allowed_values": ["conservative", "central", "stretch", "2002_dash"],
            },
        ],
        "optional_parameters": [
            {
                "name": "custom_build_cap_mw_yr",
                "description": "Custom annual build cap in MW (overrides build_scenario)",
                "unit": "MW/yr",
            },
            {
                "name": "construction_mw",
                "description": "Pipeline MW currently under construction (default 30,000)",
                "unit": "MW",
            },
            {
                "name": "pre_construction_mw",
                "description": "Pipeline MW in pre-construction phase (default 159,000)",
                "unit": "MW",
            },
            {
                "name": "announced_mw",
                "description": "Pipeline MW announced but not yet in pre-construction (default 63,000)",
                "unit": "MW",
            },
            {
                "name": "projection_years",
                "description": "Number of years to project (default 10, covering 2026–2035)",
                "unit": "years",
            },
            {
                "name": "dc_share",
                "description": "Data-centre share of incremental capacity (default 0.37)",
                "unit": "fraction",
            },
            {
                "name": "capacity_factor",
                "description": "Mid-case capacity factor for gas burn translation (default 0.45)",
                "unit": "fraction",
            },
            {
                "name": "heat_rate_btu_kwh",
                "description": "Mid-case heat rate for gas burn translation (default 7,200)",
                "unit": "Btu/kWh",
            },
        ],
        "output_variables": [
            {"name": "by_2030_new_gw", "description": "Cumulative new GW commissioned by 2030", "unit": "GW"},
            {"name": "by_2030_bcf_per_day_mid", "description": "Incremental gas burn by 2030 (mid CF)", "unit": "Bcf/d"},
            {"name": "by_2035_new_gw", "description": "Cumulative new GW commissioned by 2035", "unit": "GW"},
            {"name": "by_2035_bcf_per_day_mid", "description": "Incremental gas burn by 2035 (mid CF)", "unit": "Bcf/d"},
            {"name": "total_commissioned_gw", "description": "Total capacity commissioned over projection", "unit": "GW"},
            {"name": "years_to_clear_backlog", "description": "Years to commission entire pipeline", "unit": "years"},
            {"name": "yearly_results", "description": "Year-by-year additions and gas burn", "unit": "structured"},
            {"name": "segmented_results", "description": "DC vs non-DC gas burn segmentation", "unit": "structured"},
        ],
    },

    # ------------------------------------------------------------------
    # Energy Flux US LNG War Profits Model v1.0
    # ------------------------------------------------------------------
    "energy_flux_lng_profits": {
        "model_id": "energy_flux_lng_profits",
        "description": (
            "Energy Flux US LNG War Profits Model v1.0: calculates windfall "
            "profits for US LNG exporters under crisis-driven LNG price spikes "
            "using a 12-month netback-based cargo-economics methodology."
        ),
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "platform": "Excel (openpyxl / xlwings)",
        "required_parameters": [
            {
                "name": "disruption_duration_months",
                "description": "Duration of crisis / elevated prices (1–12 months)",
                "unit": "months",
            },
            {
                "name": "ttf_peak_price",
                "description": (
                    "Peak TTF (Europe hub) price during crisis ($/MMBtu).  "
                    "Used to auto-generate the 12-month price schedule.  "
                    "Not required if price_schedule is provided directly."
                ),
                "unit": "$/MMBtu",
            },
            {
                "name": "jkm_peak_price",
                "description": (
                    "Peak JKM (Asia hub) price during crisis ($/MMBtu).  "
                    "Not required if price_schedule is provided directly."
                ),
                "unit": "$/MMBtu",
            },
            {
                "name": "hh_crisis_price",
                "description": (
                    "Peak Henry Hub (US domestic) price during crisis ($/MMBtu).  "
                    "Not required if price_schedule is provided directly."
                ),
                "unit": "$/MMBtu",
            },
        ],
        "optional_parameters": [
            {
                "name": "price_schedule",
                "description": (
                    "Explicit 12-month price trajectory (list of dicts with "
                    "keys: ttf, jkm, hh, freight_eu, freight_asia).  Overrides "
                    "peak-price auto-generation."
                ),
                "unit": "structured",
            },
            {
                "name": "peak_month",
                "description": "Month at which crisis prices peak (default 7)",
                "unit": "month",
            },
            {
                "name": "monthly_export_bcf",
                "description": "Total US LNG exports per month (default 500 Bcf)",
                "unit": "Bcf/month",
            },
            {
                "name": "eu_share",
                "description": "Fraction of exports destined for Europe (default 0.50)",
                "unit": "fraction",
            },
            {
                "name": "asia_share",
                "description": "Fraction of exports destined for Asia (default 0.37)",
                "unit": "fraction",
            },
            {
                "name": "liquefaction_toll",
                "description": "Liquefaction cost per cargo (default $2.10/MMBtu)",
                "unit": "$/MMBtu",
            },
            {
                "name": "baseline_hh",
                "description": "Pre-crisis Henry Hub price (default $3.041/MMBtu)",
                "unit": "$/MMBtu",
            },
            {
                "name": "baseline_ttf",
                "description": "Pre-crisis TTF price (default $16.98/MMBtu)",
                "unit": "$/MMBtu",
            },
            {
                "name": "baseline_jkm",
                "description": "Pre-crisis JKM price (default $21.185/MMBtu)",
                "unit": "$/MMBtu",
            },
        ],
        "output_variables": [
            {"name": "total_windfall_usd", "description": "Cumulative windfall over duration", "unit": "USD"},
            {"name": "peak_monthly_windfall", "description": "Largest single-month windfall", "unit": "USD"},
            {"name": "peak_month", "description": "Month of peak windfall", "unit": "month"},
            {"name": "weeks_to_match_ukraine_windfall", "description": "Weeks to match Ukraine-era windfall ($83.7B)", "unit": "weeks"},
            {"name": "average_ttf_netback", "description": "Average TTF netback over duration", "unit": "$/MMBtu"},
            {"name": "average_jkm_netback", "description": "Average JKM netback over duration", "unit": "$/MMBtu"},
            {"name": "monthly_results", "description": "Month-by-month windfall breakdown", "unit": "structured"},
        ],
    },

    # ------------------------------------------------------------------
    # Global Gas Model (GGM)
    # ------------------------------------------------------------------
    "ggm": {
        "model_id": "ggm",
        "description": "Global Gas Model — QCP optimization of global LNG and pipeline gas trade flows",
        "commodity_system": "lng",
        "analytical_level": "commodity",
        "platform": "GAMS (CPLEX solver)",
        "required_parameters": [
            {"name": "strait_closure_flag", "description": "Whether the Strait of Hormuz is closed", "unit": "boolean"},
            {"name": "qatar_lng_export_loss_pct", "description": "Percentage loss of Qatar LNG exports (~80 MTPA capacity)", "unit": "percent"},
            {"name": "uae_lng_export_loss_pct", "description": "Percentage loss of UAE LNG exports (Das Island ~6 MTPA)", "unit": "percent"},
            {"name": "iran_lng_export_loss_pct", "description": "Percentage loss of Iranian gas exports", "unit": "percent"},
            {"name": "rerouting_available", "description": "Whether alternative LNG supply routes are available", "unit": "boolean"},
            {"name": "disruption_duration_months", "description": "Duration of Strait closure", "unit": "months"},
        ],
        "optional_parameters": [
            {"name": "oman_lng_export_loss_pct", "description": "Percentage loss of Omani LNG exports (Qalhat ~10 MTPA; NOT through Strait)", "unit": "percent"},
            {"name": "insurance_premium_multiplier", "description": "War-risk premium multiplier on shipping arc costs", "unit": "factor"},
            {"name": "scenario_label", "description": "WEO scenario: 'NPS' or 'SDS'", "unit": "categorical"},
            {"name": "time_horizon", "description": "GGM time horizon: '2015', '2025', or '2060'", "unit": "categorical"},
        ],
        "output_variables": [
            {"name": "regional_prices_eur_per_kcm", "description": "Market clearing gas prices by node/season/year", "unit": "EUR/kcm"},
            {"name": "arc_flows_mcm_per_yr", "description": "Bilateral trade flows on arcs", "unit": "mcm/yr"},
            {"name": "production_mcm_per_yr", "description": "Gas production by country/resource", "unit": "mcm/yr"},
            {"name": "consumption_mcm_per_yr", "description": "Gas consumption by country", "unit": "mcm/yr"},
            {"name": "arc_capacity_expansion_mcm_per_yr", "description": "Infrastructure investment decisions", "unit": "mcm/yr"},
            {"name": "objective_value", "description": "Total system cost (TC + MPA - REV - CS)", "unit": "USD"},
        ],
    },

    # ------------------------------------------------------------------
    # LNG Spreadsheet Tool (LNGST)
    # ------------------------------------------------------------------
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
