# Adapter timings without the LLM or the graph (swift_contained)

Generated 2026-11-08 by `scripts/game/time_fast_adapters.py` on Python 3.13.18, without `configs/model_configs`; mean of 10 executions per adapter; parameters from `hormuz_2026_analyst.yaml`.

| Model | System | Status | ms per call | Note |
|---|---|---|---:|---|
| `apsim` | fertilizer_agriculture | ok | 0.01 | mode=analytical_mvp; fertilizer_application_reduction_pct=7, irrigation_water_reduction_pct=0, mean_yield_pct_change=-10.1, n_use_efficiency_baseline=25 |
| `futures` | fertilizer_agriculture | ok | 0.03 | mode=analytical_mvp; forecast_horizon_months=12, initial_price_shock_pct=20 |
| `world_fertilizer` | fertilizer_agriculture | ok | 0.02 | mode=analytical_mvp; natural_gas_price_change_pct=15, middle_east_production_loss_pct=60, disruption_duration_months=1.25, nitrogen_price_pct=80.2 |
| `argonne_abm` | helium_semiconductors | ok | 0.07 | mode=analytical_mvp; supply_shock_pct=21, disruption_duration_months=1.25, demand_response_elasticity=-0.3, equilibrium_price_change_pct_mean=31.4 |
| `world_helium_model` | helium_semiconductors | ok | 0.01 | mode=analytical_mvp; equilibrium_price_usd_per_mscf=474, baseline_price_usd_per_mscf=280, price_change_pct=69.4, effective_supply_gap_pct=20.8 |
| `energy_flux_gas_power` | lng | ok | 0.08 | mode=full_upstream; build_cap_mw_yr=1.01e+04, total_pipeline_mw=2.52e+05, total_commissioned_gw=101, by_2030_new_gw=50.7 |
| `energy_flux_lng_profits` | lng | ok | 0.05 | mode=full_upstream; total_windfall_usd=6.69e+09, peak_monthly_windfall=3.48e+09, peak_month=2, duration_months=2 |
| `lngst` | lng | ok | 0.01 | mode=analytical_mvp; qatar_export_reduction_pct=85, uae_export_reduction_pct=80, spot_price_multiplier=1.8, disruption_duration_months=1.25 |
| `mpsge_jl` | macroeconomic | ok | 0.09 | mode=analytical_mvp; oil_price_shock_pct=50, trade_cost_multiplier=1.4, disruption_duration_months=1.25, gdp_impact_pct=-0.197 |
| `nrel` | macroeconomic | ok | 0.04 | mode=analytical_mvp; natural_gas_price_change_pct=15, electricity_demand_change_pct=-0.5, disruption_duration_months=1.25, retail_electricity_price_change_pct=6.72 |
| `pycge` | macroeconomic | ok | 0.13 | mode=analytical_mvp; gdp_impact_pct=-0.287, gdp_growth_pct=-0.287, gdp_growth_pct_year1=-0.287, cpi_inflation_pct=1.85 |
| `fed_oil` | oil | ok | 0.06 | mode=analytical_mvp; oil_price_change_pct=50, disruption_duration_quarters=1, fed_funds_rate_baseline=3.75, peak_gdp_impact_pct=-0.563 |
| `marketsim` | oil | ok | 0.01 | mode=analytical_mvp; oil_price_shock_pct=50, natural_gas_price_change_pct=15, disruption_duration_months=1.25, consumer_surplus_loss_oil_bn_usd=14.7 |
| `poles_jrc` | oil | ok | 0.01 | mode=analytical_mvp; peak_price_usd_per_bbl=144, peak_price_change_pct=80.5, baseline_price_usd_per_bbl=80, rerouting_volume_mbd=11.2 |
| `ais_project` | shipping | ok | 0.01 | mode=analytical_mvp; additional_transit_days=9.5, fleet_utilization_multiplier=0.683, effective_fleet_capacity_loss_pct=31.7, tanker_rate_change_pct=44.4 |
| `aisdb` | shipping | ok | 0.01 | mode=analytical_mvp; max_additional_transit_days=9.5, effective_fleet_capacity_loss_pct=30.7, rerouting_cost_multiplier=1.18, war_risk_insurance_premium_pct=200 |
| `cwatm` | water | ok | 0.01 | mode=analytical_mvp; unmet_demand_pct=0, mean_discharge_deviation_pct=-0, cumulative_water_deficit_pct_months=0, desalination_capacity_factor=1 |
| `weap_mena` | water | ok | 0.01 | mode=analytical_mvp; desalination_capacity_loss_pct=0, effective_desalination_loss_pct=0, disruption_duration_weeks=5, aggregate_unmet_demand_pct=0 |
| `messageix` | energy_systems | not implemented | 0.01 | MESSAGEix adapter requires the 'message-ix' and 'ixmp' packages. Install with `pip install -e .[energy]`. |
| `osemosys` | energy_systems | not implemented | 0.00 | OSeMOSYS source dir not found: Models/Energy/OSeMOSYS. Vendor the OSeMOSYS repo (https://github.com/OSeMOSYS/OSeMOSYS) at Models/Energy/OSeM |
| `temoa` | energy_systems | not implemented | 0.01 | TEMOA baseline DB not found: Models/Energy/TEMOA/data_files/utopia.sqlite. Vendor a baseline SQLite (e.g. utopia.sqlite) under Models/Energy |
| `capri` | fertilizer_agriculture | not implemented | 0.00 | CAPRIAdapter.execute is not yet implemented. Real integration requires: (1) a GAMS installation with the CAPRI model repository, (2) writing |
| `gtap` | fertilizer_agriculture | not implemented | 0.00 | GTAPAdapter.execute is not yet implemented. Real integration requires: (1) a licensed GTAP database (version 10+, from the GTAP Center at Pu |
| `magpie` | fertilizer_agriculture | not implemented | 0.01 | MAgPIE source tree not found. Pass magpie_root to the adapter constructor or set the MAGPIE_ROOT environment variable. Tried: none of Models |
| `simple_g` | fertilizer_agriculture | not implemented | 0.00 | SIMPLEGAdapter.execute is not yet implemented. Real integration requires: (1) a GAMS installation with the SIMPLE-G model, (2) writing scena |
| `simrlfab` | helium_semiconductors | error | 0.00 | ValueError: SimRLFabAdapter.translate_inputs_to_dict requires a SimRLFabConfig. Initialize the adapter with one before calling translate_inp |
| `ggm` | lng | not implemented | 0.00 | GGMAdapter.execute() requires a GGMConfig. Prerequisites: |
| `mam` | macroeconomic | not implemented | 0.00 | MAM aeo_ingestion mode requires MAMConfig.aeo_macro_xlsx_path to point at an existing AEO macro tables XLSX. Vendor AEO2025_Tables_19_20.xls |
| `miragrodep` | macroeconomic | not implemented | 0.02 | MIRAGRODEP requires the 'gams' executable on PATH (GAMS + a CONOPT/PATH licence). Install GAMS and ensure 'gams' is on PATH, or set MIRAGROD |
| `nems` | macroeconomic | not implemented | 0.00 | NEMS output directory not found: data/nems_outputs/swift_contained |
| `opencge` | macroeconomic | error | 0.01 | ImportError: OpenCGEAdapter.execute() requires the 'ogcore' package. Install with: pip install ogcore ogusa dask[distributed]
See https://gi |
| `bornstein_krusell_rebelo` | oil | error | 0.01 | FileNotFoundError: BKR section directory not found: Models/Oil/WorldEquilibriumOilModel/Replication Files/Section 5/supply_shocks_to_non_ope |
| `sahysmod` | water | not implemented | 0.00 | SahysModAdapter.execute() requires a SahysModConfig. To integrate SahysMod: |
| `watergap2` | water | not implemented | 0.00 | WaterGAP2Adapter.execute() requires a WaterGAP2Config. To integrate WaterGAP2: |

18 of 34 adapters ran; total wall time for every runnable adapter in sequence: 0.7 ms.
