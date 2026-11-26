# Run comparison: `llm_rev_20261102_llama8b_r2` vs `baseline_rev_apsimgtap`

Sources: `/home/dagolden/agenticAIForScenarioAnalysis/data/reports/rev_20261102_llama8b_r2` and `/home/dagolden/agenticAIForScenarioAnalysis/data/reports/baseline_rev_apsimgtap`. Tolerance for 'within_tolerance': 0.5 pct relative.

## Outputs

- Numeric output keys compared: **5080**
- Categories: {'differs': 1215, 'identical': 344, 'only_in_b': 3442, 'within_tolerance': 5, 'only_in_a': 74}

## Inputs recorded by the adapters

- Input echo keys compared: **45**
- Categories: {'only_in_b': 15, 'differs': 30}

## Determinism check

- Cells with identical recorded inputs in both runs: **0** of 104
- Cells where identical inputs gave different outputs: **0** (none)

## Execution status pairs (a -> b)

| pair | cells |
|---|---|
| absent->completed | 5 |
| absent->failed | 1 |
| completed->completed | 84 |
| failed->completed | 10 |
| failed->failed | 21 |
| failed->skipped | 1 |
| skipped->completed | 5 |
| skipped->skipped | 48 |

## Largest output differences

| scenario | model | key | llm_rev_20261102_llama8b_r2 | baseline_rev_apsimgtap | rel diff pct |
|---|---|---|---|---|---|
| infrastructure_collapse | mpsge_jl | gdp_impact_pct_by_region.MENA_OTHER | 0.4635 | -0.3198 | 168.9968 |
| infrastructure_collapse | nrel | co2_emissions_pct_change | 1.321 | -0.702 | 153.1416 |
| swift_contained | mpsge_jl | consumption_impact_pct_by_region.MENA_GCC | -0.1148 | 0.3846 | 129.8492 |
| swift_contained | mpsge_jl | equivalent_variation_pct_by_region.MENA_GCC | -0.1148 | 0.3846 | 129.8492 |
| swift_contained | mpsge_jl | welfare_pct_change_by_region.MENA_GCC | -0.1148 | 0.3846 | 129.8492 |
| infrastructure_collapse | ais_project | additional_transit_days | 0.0 | 9.5 | 100.0 |
| infrastructure_collapse | ais_project | effective_fleet_capacity_loss_pct | 0.0 | 39.688 | 100.0 |
| infrastructure_collapse | ais_project | tanker_rate_change_pct | 0.0 | 55.562 | 100.0 |
| infrastructure_collapse | ais_project | voyage_days_lost_per_baseline_voyage | 0.0 | 77.01 | 100.0 |
| infrastructure_collapse | argonne_abm | consumers_in_distress_mean | 0.0 | 34.1 | 100.0 |
| infrastructure_collapse | cwatm | desalination_capacity_factor | 1.0 | 0.0 | 100.0 |
| infrastructure_collapse | cwatm | mean_discharge_deviation_pct | -0.0 | -50.0 | 100.0 |
| infrastructure_collapse | lngst | uae_export_reduction_pct | 0.0 | 60.0 | 100.0 |
| infrastructure_collapse | nrel | electricity_demand_change_pct | 0.0 | -3.5 | 100.0 |
| infrastructure_collapse | world_helium_model | inventory_drawdown_months | 0.0 | 0.01 | 100.0 |
| prolonged_contained | ais_project | additional_transit_days | 0.0 | 9.5 | 100.0 |
| prolonged_contained | ais_project | effective_fleet_capacity_loss_pct | 0.0 | 34.688 | 100.0 |
| prolonged_contained | ais_project | tanker_rate_change_pct | 0.0 | 48.562 | 100.0 |
| prolonged_contained | ais_project | voyage_days_lost_per_baseline_voyage | 0.0 | 28.88 | 100.0 |
| prolonged_contained | apsim | irrigation_water_reduction_pct | 0.0 | 1.961 | 100.0 |
| prolonged_contained | apsim | water_limited_yield_share_by_crop.wheat | 0.0 | 0.096 | 100.0 |
| prolonged_contained | argonne_abm | consumers_in_distress_mean | 0.0 | 36.2 | 100.0 |
| prolonged_contained | argonne_abm | critical_application_failure_rate_mean | 0.0 | 8.69 | 100.0 |
| prolonged_contained | argonne_abm | critical_application_failure_rate_std | 0.0 | 2.012 | 100.0 |
| prolonged_contained | argonne_abm | equilibrium_price_change_pct_mean | 0.0 | 38.006 | 100.0 |

## Per cell

| scenario | model | status llm_rev_20261102_llama8b_r2 | status baseline_rev_apsimgtap | inputs identical | output keys | identical | within tol | differs | only llm_rev_20261102_llama8b_r2 | only baseline_rev_apsimgtap | max rel diff pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| infrastructure_collapse | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| infrastructure_collapse | aisdb | completed | completed | None | 14 | 5 | 1 | 3 | 0 | 5 | 25.0 |
| infrastructure_collapse | apsim | completed | completed | None | 16 | 1 | 0 | 9 | 6 | 0 | 90.909 |
| infrastructure_collapse | argonne_abm | completed | completed | None | 35 | 13 | 0 | 22 | 0 | 0 | 100.0 |
| infrastructure_collapse | cwatm | completed | completed | None | 6 | 1 | 0 | 5 | 0 | 0 | 100.0 |
| infrastructure_collapse | energy_flux_gas_power | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| infrastructure_collapse | energy_flux_lng_profits | failed | completed | False | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| infrastructure_collapse | fed_oil | completed | completed | None | 9 | 1 | 0 | 8 | 0 | 0 | 66.3067 |
| infrastructure_collapse | futures | completed | completed | None | 11 | 0 | 0 | 2 | 4 | 5 | 65.0 |
| infrastructure_collapse | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| infrastructure_collapse | mam | skipped | completed | None | 523 | 0 | 0 | 0 | 0 | 523 | 0.0 |
| infrastructure_collapse | marketsim | completed | completed | None | 23 | 2 | 0 | 21 | 0 | 0 | 78.3619 |
| infrastructure_collapse | mpsge_jl | completed | completed | None | 75 | 0 | 0 | 75 | 0 | 0 | 168.9968 |
| infrastructure_collapse | nrel | completed | completed | None | 33 | 15 | 0 | 18 | 0 | 0 | 153.1416 |
| infrastructure_collapse | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 68.8889 |
| infrastructure_collapse | pycge | completed | completed | False | 22 | 0 | 0 | 22 | 0 | 0 | 84.2636 |
| infrastructure_collapse | simrlfab | failed | completed | None | 33 | 0 | 0 | 0 | 0 | 33 | 0.0 |
| infrastructure_collapse | weap_mena | completed | completed | None | 32 | 9 | 0 | 7 | 6 | 10 | 80.244 |
| infrastructure_collapse | world_fertilizer | completed | completed | None | 17 | 3 | 0 | 14 | 0 | 0 | 64.7059 |
| infrastructure_collapse | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| prolonged_contained | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| prolonged_contained | aisdb | completed | completed | None | 13 | 5 | 1 | 3 | 0 | 4 | 25.0 |
| prolonged_contained | apsim | completed | completed | None | 16 | 1 | 0 | 9 | 6 | 0 | 100.0 |
| prolonged_contained | apsim_gtap | absent | completed | None | 125 | 0 | 0 | 0 | 0 | 125 | 0.0 |
| prolonged_contained | argonne_abm | completed | completed | None | 35 | 13 | 0 | 22 | 0 | 0 | 100.0 |
| prolonged_contained | cwatm | completed | completed | None | 6 | 2 | 0 | 4 | 0 | 0 | 100.0 |
| prolonged_contained | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | energy_flux_lng_profits | failed | completed | False | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| prolonged_contained | fed_oil | completed | completed | None | 9 | 2 | 0 | 7 | 0 | 0 | 60.7339 |
| prolonged_contained | futures | completed | completed | None | 9 | 0 | 0 | 2 | 2 | 5 | 66.6667 |
| prolonged_contained | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| prolonged_contained | mam | skipped | completed | None | 523 | 0 | 0 | 0 | 0 | 523 | 0.0 |
| prolonged_contained | marketsim | completed | completed | None | 23 | 2 | 0 | 21 | 0 | 0 | 31.9268 |
| prolonged_contained | mpsge_jl | completed | completed | None | 74 | 0 | 0 | 74 | 0 | 0 | 100.0 |
| prolonged_contained | nrel | completed | completed | None | 33 | 12 | 0 | 21 | 0 | 0 | 100.0 |
| prolonged_contained | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 100.0 |
| prolonged_contained | pycge | completed | completed | False | 22 | 0 | 0 | 22 | 0 | 0 | 53.4232 |
| prolonged_contained | simrlfab | failed | completed | None | 33 | 0 | 0 | 0 | 0 | 33 | 0.0 |
| prolonged_contained | weap_mena | completed | completed | None | 32 | 9 | 0 | 7 | 6 | 10 | 97.8909 |
| prolonged_contained | world_fertilizer | completed | completed | None | 17 | 4 | 0 | 13 | 0 | 0 | 57.1429 |
| prolonged_contained | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| prolonged_escalated | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| prolonged_escalated | aisdb | completed | completed | None | 14 | 5 | 1 | 3 | 0 | 5 | 25.0 |
| prolonged_escalated | apsim | completed | completed | None | 16 | 1 | 0 | 9 | 6 | 0 | 100.0 |
| prolonged_escalated | apsim_gtap | absent | completed | None | 125 | 0 | 0 | 0 | 0 | 125 | 0.0 |
| prolonged_escalated | argonne_abm | completed | completed | None | 35 | 13 | 0 | 22 | 0 | 0 | 96.2963 |
| prolonged_escalated | cwatm | completed | completed | None | 6 | 1 | 0 | 5 | 0 | 0 | 100.0 |
| prolonged_escalated | energy_flux_gas_power | completed | completed | None | 7 | 1 | 0 | 6 | 0 | 0 | 55.3465 |
| prolonged_escalated | energy_flux_lng_profits | failed | completed | False | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| prolonged_escalated | fed_oil | completed | completed | None | 9 | 2 | 0 | 7 | 0 | 0 | 66.9796 |
| prolonged_escalated | futures | completed | completed | None | 9 | 0 | 0 | 2 | 2 | 5 | 53.3333 |
| prolonged_escalated | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| prolonged_escalated | mam | skipped | completed | None | 523 | 0 | 0 | 0 | 0 | 523 | 0.0 |
| prolonged_escalated | marketsim | completed | completed | None | 23 | 2 | 0 | 21 | 0 | 0 | 42.8571 |
| prolonged_escalated | mpsge_jl | completed | completed | None | 75 | 0 | 0 | 74 | 1 | 0 | 68.3811 |
| prolonged_escalated | nrel | completed | completed | None | 33 | 15 | 0 | 18 | 0 | 0 | 100.0 |
| prolonged_escalated | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 100.0 |
| prolonged_escalated | pycge | completed | completed | False | 22 | 0 | 0 | 22 | 0 | 0 | 67.214 |
| prolonged_escalated | simrlfab | failed | completed | None | 33 | 0 | 0 | 0 | 0 | 33 | 0.0 |
| prolonged_escalated | weap_mena | completed | completed | None | 32 | 10 | 0 | 6 | 6 | 10 | 68.364 |
| prolonged_escalated | world_fertilizer | completed | completed | None | 17 | 3 | 0 | 14 | 0 | 0 | 62.5 |
| prolonged_escalated | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| swift_contained | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| swift_contained | aisdb | completed | completed | None | 13 | 5 | 1 | 3 | 0 | 4 | 25.0 |
| swift_contained | apsim | completed | completed | None | 16 | 3 | 0 | 7 | 6 | 0 | 100.0 |
| swift_contained | apsim_gtap | absent | completed | None | 125 | 0 | 0 | 0 | 0 | 125 | 0.0 |
| swift_contained | argonne_abm | completed | completed | None | 35 | 13 | 0 | 22 | 0 | 0 | 100.0 |
| swift_contained | cwatm | completed | completed | None | 6 | 5 | 0 | 1 | 0 | 0 | 86.6667 |
| swift_contained | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_contained | energy_flux_lng_profits | failed | completed | False | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| swift_contained | fed_oil | completed | completed | None | 9 | 3 | 0 | 6 | 0 | 0 | 33.3333 |
| swift_contained | futures | completed | completed | None | 11 | 0 | 0 | 2 | 2 | 7 | 58.3333 |
| swift_contained | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| swift_contained | mam | skipped | completed | None | 523 | 0 | 0 | 0 | 0 | 523 | 0.0 |
| swift_contained | marketsim | completed | completed | None | 23 | 2 | 0 | 21 | 0 | 0 | 97.3179 |
| swift_contained | mpsge_jl | completed | completed | None | 74 | 0 | 0 | 74 | 0 | 0 | 129.8492 |
| swift_contained | nrel | completed | completed | None | 33 | 12 | 0 | 21 | 0 | 0 | 100.0 |
| swift_contained | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 100.0 |
| swift_contained | pycge | completed | completed | False | 22 | 0 | 0 | 22 | 0 | 0 | 66.6667 |
| swift_contained | simrlfab | failed | completed | None | 33 | 0 | 0 | 0 | 0 | 33 | 0.0 |
| swift_contained | weap_mena | completed | completed | None | 32 | 9 | 0 | 7 | 6 | 10 | 100.0 |
| swift_contained | world_fertilizer | completed | completed | None | 17 | 3 | 0 | 14 | 0 | 0 | 100.0 |
| swift_contained | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| swift_escalated | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| swift_escalated | aisdb | completed | completed | None | 14 | 5 | 1 | 3 | 0 | 5 | 25.0 |
| swift_escalated | apsim | completed | completed | None | 16 | 1 | 0 | 9 | 6 | 0 | 78.7876 |
| swift_escalated | apsim_gtap | absent | completed | None | 125 | 0 | 0 | 0 | 0 | 125 | 0.0 |
| swift_escalated | argonne_abm | completed | completed | None | 35 | 13 | 0 | 22 | 0 | 0 | 100.0 |
| swift_escalated | cwatm | completed | completed | None | 6 | 0 | 0 | 6 | 0 | 0 | 100.0 |
| swift_escalated | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | energy_flux_lng_profits | failed | completed | False | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| swift_escalated | fed_oil | completed | completed | None | 9 | 3 | 0 | 6 | 0 | 0 | 50.5322 |
| swift_escalated | futures | completed | completed | None | 9 | 0 | 0 | 2 | 2 | 5 | 66.6667 |
| swift_escalated | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| swift_escalated | mam | skipped | completed | None | 523 | 0 | 0 | 0 | 0 | 523 | 0.0 |
| swift_escalated | marketsim | completed | completed | None | 23 | 4 | 0 | 19 | 0 | 0 | 62.5796 |
| swift_escalated | mpsge_jl | completed | completed | None | 75 | 0 | 0 | 74 | 1 | 0 | 100.0 |
| swift_escalated | nrel | completed | completed | None | 33 | 12 | 0 | 21 | 0 | 0 | 100.0 |
| swift_escalated | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 100.0 |
| swift_escalated | pycge | completed | completed | False | 22 | 0 | 0 | 22 | 0 | 0 | 62.5 |
| swift_escalated | simrlfab | failed | completed | None | 33 | 0 | 0 | 0 | 0 | 33 | 0.0 |
| swift_escalated | weap_mena | completed | completed | None | 32 | 9 | 0 | 7 | 6 | 10 | 88.1367 |
| swift_escalated | world_fertilizer | completed | completed | None | 17 | 3 | 0 | 14 | 0 | 0 | 62.5 |
| swift_escalated | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
