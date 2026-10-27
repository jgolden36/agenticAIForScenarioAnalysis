# Run comparison: `llm_20260504_222710` vs `baseline_analyst`

Sources: `data/20260504_222710` and `/home/user/agenticAIForScenarioAnalysis/data/reports/baseline_analyst`. Tolerance for 'within_tolerance': 0.5 pct relative.

## Outputs

- Numeric output keys compared: **1755**
- Categories: {'only_in_b': 770, 'differs': 794, 'identical': 160, 'only_in_a': 29, 'within_tolerance': 2}

## Inputs recorded by the adapters

- Input echo keys compared: **30**
- Categories: {'differs': 30}

## Determinism check

- Cells with identical recorded inputs in both runs: **0** of 95
- Cells where identical inputs gave different outputs: **0** (none)

## Execution status pairs (a -> b)

| pair | cells |
|---|---|
| absent->completed | 43 |
| absent->failed | 12 |
| absent->skipped | 16 |
| completed->completed | 44 |
| completed->skipped | 5 |
| failed->completed | 3 |
| failed->failed | 9 |
| failed->skipped | 6 |
| skipped->skipped | 32 |

## Largest output differences

| scenario | model | key | llm_20260504_222710 | baseline_analyst | rel diff pct |
|---|---|---|---|---|---|
| infrastructure_collapse | nrel | co2_emissions_pct_change | 1.321 | -1.488 | 188.7769 |
| swift_contained | mpsge_jl | consumption_impact_pct_by_region.MENA_GCC | -0.1206 | 0.3788 | 131.8374 |
| swift_contained | mpsge_jl | equivalent_variation_pct_by_region.MENA_GCC | -0.1206 | 0.3788 | 131.8374 |
| swift_contained | mpsge_jl | welfare_pct_change_by_region.MENA_GCC | -0.1206 | 0.3788 | 131.8374 |
| infrastructure_collapse | mpsge_jl | gdp_impact_pct_by_region.MENA_OTHER | 0.4588 | -0.1366 | 129.7733 |
| infrastructure_collapse | nrel | electricity_demand_change_pct | 0.0 | -3.5 | 100.0 |
| prolonged_contained | ais_project | additional_transit_days | 0.0 | 9.5 | 100.0 |
| prolonged_contained | ais_project | effective_fleet_capacity_loss_pct | 0.0 | 34.688 | 100.0 |
| prolonged_contained | ais_project | tanker_rate_change_pct | 0.0 | 48.562 | 100.0 |
| prolonged_contained | ais_project | voyage_days_lost_per_baseline_voyage | 0.0 | 28.88 | 100.0 |
| prolonged_contained | apsim | crop_yield_loss_pct | -0.0 | 20.224 | 100.0 |
| prolonged_contained | apsim | fertilizer_application_reduction_pct | 0.0 | 16.3366 | 100.0 |
| prolonged_contained | apsim | irrigation_water_reduction_pct | 0.0 | 1.961 | 100.0 |
| prolonged_contained | apsim | mean_yield_pct_change | 0.0 | -20.224 | 100.0 |
| prolonged_contained | apsim | n_limited_yield_share_by_crop.wheat | 0.0 | 0.904 | 100.0 |
| prolonged_contained | apsim | n_use_efficiency_change_pct | 0.0 | 9.802 | 100.0 |
| prolonged_contained | apsim | water_limited_yield_share_by_crop.wheat | 0.0 | 0.096 | 100.0 |
| prolonged_contained | apsim | yield_pct_change_by_crop.wheat | -0.0 | -20.224 | 100.0 |
| prolonged_contained | lngst | uae_export_reduction_pct | 0.0 | 85.0 | 100.0 |
| prolonged_contained | mpsge_jl | commodity_price_shocks.helium | 0.0 | 84.84 | 100.0 |
| prolonged_contained | nrel | electricity_demand_change_pct | 0.0 | -1.5 | 100.0 |
| prolonged_contained | world_helium_model | demand_rationing_mmscf | 0.0 | 540.88 | 100.0 |
| prolonged_contained | world_helium_model | effective_supply_gap_pct | 0.0 | 25.453 | 100.0 |
| prolonged_contained | world_helium_model | inventory_drawdown_months | 0.0 | 0.01 | 100.0 |
| prolonged_contained | world_helium_model | price_change_pct | 0.0 | 84.84 | 100.0 |

## Per cell

| scenario | model | status llm_20260504_222710 | status baseline_analyst | inputs identical | output keys | identical | within tol | differs | only llm_20260504_222710 | only baseline_analyst | max rel diff pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| infrastructure_collapse | ais_project | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| infrastructure_collapse | aisdb | absent | completed | None | 14 | 0 | 0 | 0 | 0 | 14 | 0.0 |
| infrastructure_collapse | apsim | absent | completed | None | 10 | 0 | 0 | 0 | 0 | 10 | 0.0 |
| infrastructure_collapse | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| infrastructure_collapse | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| infrastructure_collapse | energy_flux_gas_power | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| infrastructure_collapse | energy_flux_lng_profits | absent | completed | None | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| infrastructure_collapse | fed_oil | completed | completed | None | 9 | 1 | 0 | 8 | 0 | 0 | 66.3067 |
| infrastructure_collapse | futures | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| infrastructure_collapse | lngst | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| infrastructure_collapse | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| infrastructure_collapse | marketsim | absent | completed | None | 23 | 0 | 0 | 0 | 0 | 23 | 0.0 |
| infrastructure_collapse | mpsge_jl | completed | completed | None | 75 | 0 | 0 | 73 | 0 | 2 | 129.7733 |
| infrastructure_collapse | nrel | completed | completed | None | 33 | 15 | 0 | 17 | 0 | 1 | 188.7769 |
| infrastructure_collapse | poles_jrc | absent | completed | None | 8 | 0 | 0 | 0 | 0 | 8 | 0.0 |
| infrastructure_collapse | pycge | completed | completed | False | 22 | 0 | 0 | 20 | 0 | 2 | 86.5026 |
| infrastructure_collapse | weap_mena | absent | completed | None | 26 | 0 | 0 | 0 | 0 | 26 | 0.0 |
| infrastructure_collapse | world_fertilizer | absent | completed | None | 17 | 0 | 0 | 0 | 0 | 17 | 0.0 |
| infrastructure_collapse | world_helium_model | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| prolonged_contained | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| prolonged_contained | aisdb | completed | completed | None | 13 | 5 | 1 | 3 | 0 | 4 | 25.0 |
| prolonged_contained | apsim | completed | completed | None | 16 | 1 | 0 | 9 | 6 | 0 | 100.0 |
| prolonged_contained | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| prolonged_contained | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| prolonged_contained | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | energy_flux_lng_profits | failed | completed | None | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| prolonged_contained | fed_oil | completed | completed | None | 9 | 2 | 0 | 7 | 0 | 0 | 60.7339 |
| prolonged_contained | futures | completed | completed | None | 9 | 0 | 0 | 2 | 2 | 5 | 66.6667 |
| prolonged_contained | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| prolonged_contained | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| prolonged_contained | marketsim | completed | completed | None | 23 | 2 | 0 | 21 | 0 | 0 | 31.9268 |
| prolonged_contained | mpsge_jl | completed | completed | None | 74 | 0 | 0 | 72 | 0 | 2 | 100.0 |
| prolonged_contained | nrel | completed | completed | None | 33 | 12 | 0 | 20 | 0 | 1 | 100.0 |
| prolonged_contained | poles_jrc | absent | completed | None | 8 | 0 | 0 | 0 | 0 | 8 | 0.0 |
| prolonged_contained | pycge | completed | completed | False | 22 | 0 | 0 | 20 | 0 | 2 | 50.2495 |
| prolonged_contained | weap_mena | absent | completed | None | 26 | 0 | 0 | 0 | 0 | 26 | 0.0 |
| prolonged_contained | world_fertilizer | completed | completed | None | 17 | 4 | 0 | 13 | 0 | 0 | 57.1429 |
| prolonged_contained | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| prolonged_escalated | ais_project | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| prolonged_escalated | aisdb | absent | completed | None | 14 | 0 | 0 | 0 | 0 | 14 | 0.0 |
| prolonged_escalated | apsim | absent | completed | None | 10 | 0 | 0 | 0 | 0 | 10 | 0.0 |
| prolonged_escalated | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| prolonged_escalated | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| prolonged_escalated | energy_flux_gas_power | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| prolonged_escalated | energy_flux_lng_profits | absent | completed | None | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| prolonged_escalated | fed_oil | completed | completed | None | 9 | 2 | 0 | 7 | 0 | 0 | 66.9796 |
| prolonged_escalated | futures | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| prolonged_escalated | lngst | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| prolonged_escalated | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| prolonged_escalated | marketsim | absent | completed | None | 23 | 0 | 0 | 0 | 0 | 23 | 0.0 |
| prolonged_escalated | mpsge_jl | completed | completed | None | 75 | 0 | 0 | 72 | 1 | 2 | 68.3811 |
| prolonged_escalated | nrel | completed | completed | None | 33 | 15 | 0 | 17 | 0 | 1 | 100.0 |
| prolonged_escalated | poles_jrc | absent | completed | None | 8 | 0 | 0 | 0 | 0 | 8 | 0.0 |
| prolonged_escalated | pycge | completed | completed | False | 22 | 0 | 0 | 20 | 0 | 2 | 66.8178 |
| prolonged_escalated | weap_mena | absent | completed | None | 26 | 0 | 0 | 0 | 0 | 26 | 0.0 |
| prolonged_escalated | world_fertilizer | absent | completed | None | 17 | 0 | 0 | 0 | 0 | 17 | 0.0 |
| prolonged_escalated | world_helium_model | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| swift_contained | ais_project | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| swift_contained | aisdb | absent | completed | None | 13 | 0 | 0 | 0 | 0 | 13 | 0.0 |
| swift_contained | apsim | absent | completed | None | 10 | 0 | 0 | 0 | 0 | 10 | 0.0 |
| swift_contained | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| swift_contained | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| swift_contained | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_contained | energy_flux_lng_profits | failed | completed | None | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| swift_contained | fed_oil | completed | completed | None | 9 | 3 | 0 | 6 | 0 | 0 | 33.3333 |
| swift_contained | futures | absent | completed | None | 9 | 0 | 0 | 0 | 0 | 9 | 0.0 |
| swift_contained | lngst | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| swift_contained | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| swift_contained | marketsim | completed | completed | None | 23 | 2 | 0 | 21 | 0 | 0 | 97.3179 |
| swift_contained | mpsge_jl | completed | completed | None | 74 | 0 | 0 | 72 | 0 | 2 | 131.8374 |
| swift_contained | nrel | completed | completed | None | 33 | 12 | 0 | 20 | 0 | 1 | 100.0 |
| swift_contained | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 100.0 |
| swift_contained | pycge | completed | completed | False | 22 | 0 | 0 | 20 | 0 | 2 | 66.6667 |
| swift_contained | weap_mena | absent | completed | None | 26 | 0 | 0 | 0 | 0 | 26 | 0.0 |
| swift_contained | world_fertilizer | absent | completed | None | 17 | 0 | 0 | 0 | 0 | 17 | 0.0 |
| swift_contained | world_helium_model | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| swift_escalated | ais_project | completed | completed | None | 7 | 0 | 0 | 7 | 0 | 0 | 100.0 |
| swift_escalated | aisdb | completed | completed | None | 14 | 5 | 1 | 3 | 0 | 5 | 25.0 |
| swift_escalated | apsim | completed | completed | None | 16 | 1 | 0 | 9 | 6 | 0 | 100.0 |
| swift_escalated | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| swift_escalated | cwatm | completed | completed | None | 6 | 0 | 0 | 6 | 0 | 0 | 100.0 |
| swift_escalated | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | energy_flux_lng_profits | failed | completed | None | 11 | 0 | 0 | 0 | 0 | 11 | 0.0 |
| swift_escalated | fed_oil | completed | completed | None | 9 | 3 | 0 | 6 | 0 | 0 | 50.5322 |
| swift_escalated | futures | completed | completed | None | 9 | 0 | 0 | 2 | 2 | 5 | 66.6667 |
| swift_escalated | lngst | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
| swift_escalated | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| swift_escalated | marketsim | completed | completed | None | 23 | 4 | 0 | 19 | 0 | 0 | 62.5796 |
| swift_escalated | mpsge_jl | completed | completed | None | 75 | 0 | 0 | 72 | 1 | 2 | 100.0 |
| swift_escalated | nrel | completed | completed | None | 33 | 12 | 0 | 20 | 0 | 1 | 100.0 |
| swift_escalated | poles_jrc | completed | completed | None | 8 | 1 | 0 | 7 | 0 | 0 | 100.0 |
| swift_escalated | pycge | completed | completed | False | 22 | 0 | 0 | 20 | 0 | 2 | 62.5 |
| swift_escalated | weap_mena | completed | completed | None | 32 | 9 | 0 | 7 | 6 | 10 | 88.1367 |
| swift_escalated | world_fertilizer | completed | completed | None | 17 | 3 | 0 | 14 | 0 | 0 | 62.5 |
| swift_escalated | world_helium_model | completed | completed | None | 18 | 6 | 0 | 12 | 0 | 0 | 100.0 |
