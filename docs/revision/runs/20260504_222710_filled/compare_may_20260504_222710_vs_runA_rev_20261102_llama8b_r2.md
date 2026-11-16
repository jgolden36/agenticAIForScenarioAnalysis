# Run comparison: `may_20260504_222710` vs `runA_rev_20261102_llama8b_r2`

Sources: `data/20260504_222710` and `data/reports/rev_20261102_llama8b_r2`. Tolerance for 'within_tolerance': 0.5 pct relative.

## Outputs

- Numeric output keys compared: **1643**
- Categories: {'only_in_b': 658, 'identical': 675, 'only_in_a': 5, 'differs': 145, 'within_tolerance': 160}

## Inputs recorded by the adapters

- Input echo keys compared: **30**
- Categories: {'identical': 30}

## Determinism check

- Cells with identical recorded inputs in both runs: **5** of 89
- Cells where identical inputs gave different outputs: **0** (none)

## Execution status pairs (a -> b)

| pair | cells |
|---|---|
| absent->completed | 40 |
| absent->failed | 14 |
| absent->skipped | 16 |
| completed->completed | 44 |
| completed->skipped | 5 |
| failed->failed | 18 |
| skipped->skipped | 32 |

## Largest output differences

| scenario | model | key | may_20260504_222710 | runA_rev_20261102_llama8b_r2 | rel diff pct |
|---|---|---|---|---|---|
| prolonged_contained | apsim | crop_yield_loss_pct | -0.0 | 10.813 | 100.0 |
| prolonged_contained | apsim | fertilizer_application_reduction_pct | 0.0 | 8.3146 | 100.0 |
| prolonged_contained | apsim | mean_yield_pct_change | 0.0 | -10.813 | 100.0 |
| prolonged_contained | apsim | n_limited_yield_share_by_crop.maize | 0.0 | 1.0 | 100.0 |
| prolonged_contained | apsim | n_limited_yield_share_by_crop.rice | 0.0 | 1.0 | 100.0 |
| prolonged_contained | apsim | n_limited_yield_share_by_crop.wheat | 0.0 | 1.0 | 100.0 |
| prolonged_contained | apsim | n_use_efficiency_change_pct | 0.0 | 4.989 | 100.0 |
| prolonged_contained | apsim | yield_pct_change_by_crop.maize | -0.0 | -12.274 | 100.0 |
| prolonged_contained | apsim | yield_pct_change_by_crop.rice | -0.0 | -8.767 | 100.0 |
| prolonged_contained | apsim | yield_pct_change_by_crop.wheat | -0.0 | -11.397 | 100.0 |
| swift_escalated | apsim | crop_yield_loss_pct | -0.0 | 19.226 | 100.0 |
| swift_escalated | apsim | fertilizer_application_reduction_pct | 0.0 | 8.3146 | 100.0 |
| swift_escalated | apsim | irrigation_water_reduction_pct | 0.0 | 9.091 | 100.0 |
| swift_escalated | apsim | mean_yield_pct_change | 0.0 | -19.226 | 100.0 |
| swift_escalated | apsim | n_limited_yield_share_by_crop.maize | 0.0 | 0.582 | 100.0 |
| swift_escalated | apsim | n_limited_yield_share_by_crop.rice | 0.0 | 0.472 | 100.0 |
| swift_escalated | apsim | n_limited_yield_share_by_crop.wheat | 0.0 | 0.633 | 100.0 |
| swift_escalated | apsim | n_use_efficiency_change_pct | 0.0 | 4.989 | 100.0 |
| swift_escalated | apsim | water_limited_yield_share_by_crop.maize | 0.0 | 0.418 | 100.0 |
| swift_escalated | apsim | water_limited_yield_share_by_crop.rice | 0.0 | 0.528 | 100.0 |
| swift_escalated | apsim | water_limited_yield_share_by_crop.wheat | 0.0 | 0.367 | 100.0 |
| swift_escalated | apsim | yield_pct_change_by_crop.maize | -0.0 | -21.085 | 100.0 |
| swift_escalated | apsim | yield_pct_change_by_crop.rice | -0.0 | -18.588 | 100.0 |
| swift_escalated | apsim | yield_pct_change_by_crop.wheat | -0.0 | -18.006 | 100.0 |
| infrastructure_collapse | mpsge_jl | commodity_price_shocks.capex | 5.607000000000001 | 2.8035000000000005 | 50.0 |

## Per cell

| scenario | model | status may_20260504_222710 | status runA_rev_20261102_llama8b_r2 | inputs identical | output keys | identical | within tol | differs | only may_20260504_222710 | only runA_rev_20261102_llama8b_r2 | max rel diff pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| infrastructure_collapse | ais_project | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| infrastructure_collapse | aisdb | absent | completed | None | 9 | 0 | 0 | 0 | 0 | 9 | 0.0 |
| infrastructure_collapse | apsim | absent | completed | None | 16 | 0 | 0 | 0 | 0 | 16 | 0.0 |
| infrastructure_collapse | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| infrastructure_collapse | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| infrastructure_collapse | fed_oil | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| infrastructure_collapse | futures | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| infrastructure_collapse | lngst | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| infrastructure_collapse | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| infrastructure_collapse | marketsim | absent | completed | None | 23 | 0 | 0 | 0 | 0 | 23 | 0.0 |
| infrastructure_collapse | mpsge_jl | completed | completed | None | 75 | 16 | 36 | 21 | 0 | 2 | 50.0 |
| infrastructure_collapse | nrel | completed | completed | None | 33 | 32 | 0 | 0 | 0 | 1 | 0.0 |
| infrastructure_collapse | poles_jrc | absent | completed | None | 8 | 0 | 0 | 0 | 0 | 8 | 0.0 |
| infrastructure_collapse | pycge | completed | completed | True | 22 | 20 | 0 | 0 | 0 | 2 | 0.0 |
| infrastructure_collapse | weap_mena | absent | completed | None | 22 | 0 | 0 | 0 | 0 | 22 | 0.0 |
| infrastructure_collapse | world_fertilizer | absent | completed | None | 17 | 0 | 0 | 0 | 0 | 17 | 0.0 |
| infrastructure_collapse | world_helium_model | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| prolonged_contained | ais_project | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | aisdb | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | apsim | completed | completed | None | 16 | 5 | 0 | 11 | 0 | 0 | 100.0 |
| prolonged_contained | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| prolonged_contained | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| prolonged_contained | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | fed_oil | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | futures | completed | completed | None | 4 | 4 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | lngst | completed | completed | None | 18 | 18 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| prolonged_contained | marketsim | completed | completed | None | 23 | 23 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | mpsge_jl | completed | completed | None | 74 | 16 | 36 | 20 | 0 | 2 | 50.0 |
| prolonged_contained | nrel | completed | completed | None | 33 | 32 | 0 | 0 | 0 | 1 | 0.0 |
| prolonged_contained | poles_jrc | absent | completed | None | 8 | 0 | 0 | 0 | 0 | 8 | 0.0 |
| prolonged_contained | pycge | completed | completed | True | 22 | 20 | 0 | 0 | 0 | 2 | 0.0 |
| prolonged_contained | weap_mena | absent | completed | None | 22 | 0 | 0 | 0 | 0 | 22 | 0.0 |
| prolonged_contained | world_fertilizer | completed | completed | None | 17 | 17 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_contained | world_helium_model | completed | completed | None | 18 | 18 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_escalated | ais_project | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| prolonged_escalated | aisdb | absent | completed | None | 9 | 0 | 0 | 0 | 0 | 9 | 0.0 |
| prolonged_escalated | apsim | absent | completed | None | 16 | 0 | 0 | 0 | 0 | 16 | 0.0 |
| prolonged_escalated | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| prolonged_escalated | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| prolonged_escalated | energy_flux_gas_power | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| prolonged_escalated | fed_oil | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| prolonged_escalated | futures | absent | completed | None | 4 | 0 | 0 | 0 | 0 | 4 | 0.0 |
| prolonged_escalated | lngst | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| prolonged_escalated | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| prolonged_escalated | marketsim | absent | completed | None | 23 | 0 | 0 | 0 | 0 | 23 | 0.0 |
| prolonged_escalated | mpsge_jl | completed | completed | None | 75 | 17 | 35 | 21 | 0 | 2 | 50.0 |
| prolonged_escalated | nrel | completed | completed | None | 33 | 32 | 0 | 0 | 0 | 1 | 0.0 |
| prolonged_escalated | poles_jrc | absent | completed | None | 8 | 0 | 0 | 0 | 0 | 8 | 0.0 |
| prolonged_escalated | pycge | completed | completed | True | 22 | 20 | 0 | 0 | 0 | 2 | 0.0 |
| prolonged_escalated | weap_mena | absent | completed | None | 22 | 0 | 0 | 0 | 0 | 22 | 0.0 |
| prolonged_escalated | world_fertilizer | absent | completed | None | 17 | 0 | 0 | 0 | 0 | 17 | 0.0 |
| prolonged_escalated | world_helium_model | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| swift_contained | ais_project | absent | completed | None | 7 | 0 | 0 | 0 | 0 | 7 | 0.0 |
| swift_contained | aisdb | absent | completed | None | 9 | 0 | 0 | 0 | 0 | 9 | 0.0 |
| swift_contained | apsim | absent | completed | None | 16 | 0 | 0 | 0 | 0 | 16 | 0.0 |
| swift_contained | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| swift_contained | cwatm | absent | completed | None | 6 | 0 | 0 | 0 | 0 | 6 | 0.0 |
| swift_contained | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_contained | fed_oil | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| swift_contained | futures | absent | completed | None | 4 | 0 | 0 | 0 | 0 | 4 | 0.0 |
| swift_contained | lngst | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| swift_contained | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| swift_contained | marketsim | completed | completed | None | 23 | 23 | 0 | 0 | 0 | 0 | 0.0 |
| swift_contained | mpsge_jl | completed | completed | None | 74 | 18 | 17 | 37 | 0 | 2 | 50.0 |
| swift_contained | nrel | completed | completed | None | 33 | 32 | 0 | 0 | 0 | 1 | 0.0 |
| swift_contained | poles_jrc | completed | completed | None | 8 | 8 | 0 | 0 | 0 | 0 | 0.0 |
| swift_contained | pycge | completed | completed | True | 22 | 20 | 0 | 0 | 0 | 2 | 0.0 |
| swift_contained | weap_mena | absent | completed | None | 22 | 0 | 0 | 0 | 0 | 22 | 0.0 |
| swift_contained | world_fertilizer | absent | completed | None | 17 | 0 | 0 | 0 | 0 | 17 | 0.0 |
| swift_contained | world_helium_model | absent | completed | None | 18 | 0 | 0 | 0 | 0 | 18 | 0.0 |
| swift_escalated | ais_project | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | aisdb | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | apsim | completed | completed | None | 16 | 1 | 0 | 15 | 0 | 0 | 100.0 |
| swift_escalated | argonne_abm | absent | completed | None | 35 | 0 | 0 | 0 | 0 | 35 | 0.0 |
| swift_escalated | cwatm | completed | completed | None | 6 | 6 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | energy_flux_gas_power | completed | completed | None | 7 | 7 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | fed_oil | completed | completed | None | 9 | 9 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | futures | completed | completed | None | 4 | 4 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | lngst | completed | completed | None | 18 | 18 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | mam | completed | skipped | None | 1 | 0 | 0 | 0 | 1 | 0 | 0.0 |
| swift_escalated | marketsim | completed | completed | None | 23 | 23 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | mpsge_jl | completed | completed | None | 75 | 17 | 36 | 20 | 0 | 2 | 50.0 |
| swift_escalated | nrel | completed | completed | None | 33 | 32 | 0 | 0 | 0 | 1 | 0.0 |
| swift_escalated | poles_jrc | completed | completed | None | 8 | 8 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | pycge | completed | completed | True | 22 | 20 | 0 | 0 | 0 | 2 | 0.0 |
| swift_escalated | weap_mena | completed | completed | None | 22 | 22 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | world_fertilizer | completed | completed | None | 17 | 17 | 0 | 0 | 0 | 0 | 0.0 |
| swift_escalated | world_helium_model | completed | completed | None | 18 | 18 | 0 | 0 | 0 | 0 | 0.0 |
