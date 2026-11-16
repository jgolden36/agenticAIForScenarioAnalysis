# Elasticity Latin hypercube

Generated 2026-11-08T19:58:25.686249+00:00. 500 seeded draws (seed 20261010), every knob multiplied by a factor in [0.5, 1.5], each draw re-running the analytical chain (poles_jrc, world_fertilizer, futures, world_helium_model, lngst, aisdb, ais_project, cwatm, apsim, argonne_abm, marketsim, fed_oil, nrel, pycge, mpsge_jl) for all scenarios on the analyst-baseline inputs with upstream forwarding. Port of the AgResilience E9 analysis.

Point control (all factors 1) reproduces the no-override run: **True**. Draws with a missing headline value: 0. Wall time 49 s.

## Knobs

| knob | kind | target | source |
|---|---|---|---|
| gdp_elasticity_oil | constant | `src.models.macro.macro_kernel.GDP_ELASTICITY_TO_OIL_PCT` | Hamilton (2003; 2009) -0.025 pp GDP per 1% oil |
| cpi_elasticity_oil | constant | `src.models.macro.macro_kernel.CPI_ELASTICITY_TO_OIL_PCT` | Blanchard & Gali (2007) 0.04 pp CPI per 1% oil |
| gdp_elasticity_lng | constant | `src.models.macro.macro_kernel.GDP_ELASTICITY_TO_LNG_PCT` |  |
| gdp_elasticity_fertilizer | constant | `src.models.macro.macro_kernel.GDP_ELASTICITY_TO_FERTILIZER_PCT` |  |
| cpi_elasticity_fertilizer | constant | `src.models.macro.macro_kernel.CPI_ELASTICITY_TO_FERTILIZER_PCT` |  |
| oil_demand_elasticity | constant | `src.models.oil.poles_jrc._ELASTICITY_DEMAND` | POLES-JRC reduction short-run demand elasticity -0.06 |
| oil_supply_elasticity | constant | `src.models.oil.poles_jrc._ELASTICITY_SUPPLY` |  |
| gas_to_nitrogen_passthrough | constant | `src.models.fertilizer.world_fertilizer._NG_PASSTHROUGH_TO_NITROGEN` |  |
| me_loss_to_nitrogen_passthrough | constant | `src.models.fertilizer.world_fertilizer._ME_LOSS_PASSTHROUGH_TO_NITROGEN` |  |
| freight_elasticity | constant | `src.models.shipping.aisdb._FREIGHT_ELASTICITY` |  |
| trade_cost_to_capex | constant | `src.models.macro.mpsge_jl._TRADE_COST_TO_CAPEX_PASSTHROUGH` |  |
| fertilizer_demand_elasticity | forwarding | `apsim.fertilizer_application_reduction_pct source 0 `elasticity`` | Hendricks & Smith (2018) own-price elasticity 0.35 |

## Bands (p05 / p50 / p95; point = calibrated)

| output | scenario | point | p05 | p50 | p95 |
|---|---|---|---|---|---|
| apsim.mean_yield_pct_change | swift_contained | -15.93 | -22.93 | -15.22 | -9.344 |
| apsim.mean_yield_pct_change | prolonged_contained | -20.22 | -28.25 | -19.44 | -12.73 |
| apsim.mean_yield_pct_change | swift_escalated | -40.77 | -48.65 | -39.97 | -33.38 |
| apsim.mean_yield_pct_change | prolonged_escalated | -44.04 | -53.03 | -43.33 | -35.68 |
| apsim.mean_yield_pct_change | infrastructure_collapse | -66.93 | -76.54 | -66.24 | -58.08 |
| fed_oil.peak_gdp_impact_pct | swift_contained | -0.9061 | -1.332 | -0.8999 | -0.501 |
| fed_oil.peak_gdp_impact_pct | prolonged_contained | -1.733 | -2.546 | -1.729 | -0.9597 |
| fed_oil.peak_gdp_impact_pct | swift_escalated | -1.325 | -1.949 | -1.321 | -0.7322 |
| fed_oil.peak_gdp_impact_pct | prolonged_escalated | -2.501 | -3.669 | -2.497 | -1.382 |
| fed_oil.peak_gdp_impact_pct | infrastructure_collapse | -4.305 | -6.316 | -4.301 | -2.38 |
| marketsim.consumer_surplus_loss_bn_usd | swift_contained | 15.58 | 15.58 | 15.58 | 15.58 |
| marketsim.consumer_surplus_loss_bn_usd | prolonged_contained | 74.47 | 74.47 | 74.47 | 74.47 |
| marketsim.consumer_surplus_loss_bn_usd | swift_escalated | 22.65 | 22.65 | 22.65 | 22.65 |
| marketsim.consumer_surplus_loss_bn_usd | prolonged_escalated | 124 | 124 | 124 | 124 |
| marketsim.consumer_surplus_loss_bn_usd | infrastructure_collapse | 297.9 | 297.9 | 297.9 | 297.9 |
| mpsge_jl.gdp_impact_pct | swift_contained | -0.3697 | -0.4875 | -0.3714 | -0.2505 |
| mpsge_jl.gdp_impact_pct | prolonged_contained | -1.849 | -2.429 | -1.857 | -1.24 |
| mpsge_jl.gdp_impact_pct | swift_escalated | -0.6293 | -0.8317 | -0.6329 | -0.4221 |
| mpsge_jl.gdp_impact_pct | prolonged_escalated | -3.368 | -4.428 | -3.38 | -2.247 |
| mpsge_jl.gdp_impact_pct | infrastructure_collapse | -7.924 | -10.09 | -7.956 | -5.627 |
| poles_jrc.peak_price_change_pct | swift_contained | 80.54 | 73.87 | 80.39 | 89.38 |
| poles_jrc.peak_price_change_pct | prolonged_contained | 99.06 | 91.92 | 98.89 | 108.5 |
| poles_jrc.peak_price_change_pct | swift_escalated | 117.8 | 108.5 | 117.5 | 130.3 |
| poles_jrc.peak_price_change_pct | prolonged_escalated | 142.9 | 133.1 | 142.7 | 156.3 |
| poles_jrc.peak_price_change_pct | infrastructure_collapse | 143.5 | 134 | 143.3 | 157.1 |
| pycge.cpi_inflation_pct | swift_contained | 2.69 | 1.895 | 2.683 | 3.511 |
| pycge.cpi_inflation_pct | prolonged_contained | 3.465 | 2.489 | 3.456 | 4.458 |
| pycge.cpi_inflation_pct | swift_escalated | 3.722 | 2.592 | 3.724 | 4.913 |
| pycge.cpi_inflation_pct | prolonged_escalated | 5.537 | 3.961 | 5.527 | 7.17 |
| pycge.cpi_inflation_pct | infrastructure_collapse | 10.25 | 7.499 | 10.24 | 13.07 |
| pycge.gdp_impact_pct | swift_contained | -0.4217 | -0.5654 | -0.4199 | -0.2723 |
| pycge.gdp_impact_pct | prolonged_contained | -1.651 | -2.199 | -1.639 | -1.07 |
| pycge.gdp_impact_pct | swift_escalated | -0.7176 | -0.9693 | -0.7174 | -0.4575 |
| pycge.gdp_impact_pct | prolonged_escalated | -2.815 | -3.79 | -2.799 | -1.815 |
| pycge.gdp_impact_pct | infrastructure_collapse | -5.106 | -6.798 | -5.102 | -3.332 |
| world_fertilizer.fertilizer_price_index_pct | swift_contained | 38.32 | 22.69 | 38.84 | 53.7 |
| world_fertilizer.fertilizer_price_index_pct | prolonged_contained | 46.68 | 28.48 | 47.23 | 64.76 |
| world_fertilizer.fertilizer_price_index_pct | swift_escalated | 45.36 | 27.24 | 45.99 | 63.36 |
| world_fertilizer.fertilizer_price_index_pct | prolonged_escalated | 55.03 | 33.81 | 55.66 | 75.73 |
| world_fertilizer.fertilizer_price_index_pct | infrastructure_collapse | 60.52 | 37.53 | 61.1 | 82.43 |

## Ordering robustness

Share of draws in which a scenario pair keeps its calibrated ordering. Below 0.95 is marked.

| output | pair (calibrated order) | share kept |
|---|---|---|
| apsim.mean_yield_pct_change | swift_contained > prolonged_contained | 1.000 |
| apsim.mean_yield_pct_change | swift_contained > swift_escalated | 1.000 |
| apsim.mean_yield_pct_change | swift_contained > prolonged_escalated | 1.000 |
| apsim.mean_yield_pct_change | swift_contained > infrastructure_collapse | 1.000 |
| apsim.mean_yield_pct_change | prolonged_contained > swift_escalated | 1.000 |
| apsim.mean_yield_pct_change | prolonged_contained > prolonged_escalated | 1.000 |
| apsim.mean_yield_pct_change | prolonged_contained > infrastructure_collapse | 1.000 |
| apsim.mean_yield_pct_change | swift_escalated > prolonged_escalated | 1.000 |
| apsim.mean_yield_pct_change | swift_escalated > infrastructure_collapse | 1.000 |
| apsim.mean_yield_pct_change | prolonged_escalated > infrastructure_collapse | 1.000 |
| fed_oil.peak_gdp_impact_pct | swift_contained > prolonged_contained | 1.000 |
| fed_oil.peak_gdp_impact_pct | swift_contained > swift_escalated | 1.000 |
| fed_oil.peak_gdp_impact_pct | swift_contained > prolonged_escalated | 1.000 |
| fed_oil.peak_gdp_impact_pct | swift_contained > infrastructure_collapse | 1.000 |
| fed_oil.peak_gdp_impact_pct | prolonged_contained < swift_escalated | 1.000 |
| fed_oil.peak_gdp_impact_pct | prolonged_contained > prolonged_escalated | 1.000 |
| fed_oil.peak_gdp_impact_pct | prolonged_contained > infrastructure_collapse | 1.000 |
| fed_oil.peak_gdp_impact_pct | swift_escalated > prolonged_escalated | 1.000 |
| fed_oil.peak_gdp_impact_pct | swift_escalated > infrastructure_collapse | 1.000 |
| fed_oil.peak_gdp_impact_pct | prolonged_escalated > infrastructure_collapse | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | swift_contained < prolonged_contained | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | swift_contained < swift_escalated | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | swift_contained < prolonged_escalated | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | swift_contained < infrastructure_collapse | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | prolonged_contained > swift_escalated | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | prolonged_contained < prolonged_escalated | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | prolonged_contained < infrastructure_collapse | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | swift_escalated < prolonged_escalated | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | swift_escalated < infrastructure_collapse | 1.000 |
| marketsim.consumer_surplus_loss_bn_usd | prolonged_escalated < infrastructure_collapse | 1.000 |
| mpsge_jl.gdp_impact_pct | swift_contained > prolonged_contained | 1.000 |
| mpsge_jl.gdp_impact_pct | swift_contained > swift_escalated | 1.000 |
| mpsge_jl.gdp_impact_pct | swift_contained > prolonged_escalated | 1.000 |
| mpsge_jl.gdp_impact_pct | swift_contained > infrastructure_collapse | 1.000 |
| mpsge_jl.gdp_impact_pct | prolonged_contained < swift_escalated | 1.000 |
| mpsge_jl.gdp_impact_pct | prolonged_contained > prolonged_escalated | 1.000 |
| mpsge_jl.gdp_impact_pct | prolonged_contained > infrastructure_collapse | 1.000 |
| mpsge_jl.gdp_impact_pct | swift_escalated > prolonged_escalated | 1.000 |
| mpsge_jl.gdp_impact_pct | swift_escalated > infrastructure_collapse | 1.000 |
| mpsge_jl.gdp_impact_pct | prolonged_escalated > infrastructure_collapse | 1.000 |
| poles_jrc.peak_price_change_pct | swift_contained < prolonged_contained | 1.000 |
| poles_jrc.peak_price_change_pct | swift_contained < swift_escalated | 1.000 |
| poles_jrc.peak_price_change_pct | swift_contained < prolonged_escalated | 1.000 |
| poles_jrc.peak_price_change_pct | swift_contained < infrastructure_collapse | 1.000 |
| poles_jrc.peak_price_change_pct | prolonged_contained < swift_escalated | 1.000 |
| poles_jrc.peak_price_change_pct | prolonged_contained < prolonged_escalated | 1.000 |
| poles_jrc.peak_price_change_pct | prolonged_contained < infrastructure_collapse | 1.000 |
| poles_jrc.peak_price_change_pct | swift_escalated < prolonged_escalated | 1.000 |
| poles_jrc.peak_price_change_pct | swift_escalated < infrastructure_collapse | 1.000 |
| poles_jrc.peak_price_change_pct | prolonged_escalated < infrastructure_collapse | 1.000 |
| pycge.cpi_inflation_pct | swift_contained < prolonged_contained | 1.000 |
| pycge.cpi_inflation_pct | swift_contained < swift_escalated | 1.000 |
| pycge.cpi_inflation_pct | swift_contained < prolonged_escalated | 1.000 |
| pycge.cpi_inflation_pct | swift_contained < infrastructure_collapse | 1.000 |
| pycge.cpi_inflation_pct | prolonged_contained < swift_escalated | 1.000 |
| pycge.cpi_inflation_pct | prolonged_contained < prolonged_escalated | 1.000 |
| pycge.cpi_inflation_pct | prolonged_contained < infrastructure_collapse | 1.000 |
| pycge.cpi_inflation_pct | swift_escalated < prolonged_escalated | 1.000 |
| pycge.cpi_inflation_pct | swift_escalated < infrastructure_collapse | 1.000 |
| pycge.cpi_inflation_pct | prolonged_escalated < infrastructure_collapse | 1.000 |
| pycge.gdp_impact_pct | swift_contained > prolonged_contained | 1.000 |
| pycge.gdp_impact_pct | swift_contained > swift_escalated | 1.000 |
| pycge.gdp_impact_pct | swift_contained > prolonged_escalated | 1.000 |
| pycge.gdp_impact_pct | swift_contained > infrastructure_collapse | 1.000 |
| pycge.gdp_impact_pct | prolonged_contained < swift_escalated | 1.000 |
| pycge.gdp_impact_pct | prolonged_contained > prolonged_escalated | 1.000 |
| pycge.gdp_impact_pct | prolonged_contained > infrastructure_collapse | 1.000 |
| pycge.gdp_impact_pct | swift_escalated > prolonged_escalated | 1.000 |
| pycge.gdp_impact_pct | swift_escalated > infrastructure_collapse | 1.000 |
| pycge.gdp_impact_pct | prolonged_escalated > infrastructure_collapse | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | swift_contained < prolonged_contained | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | swift_contained < swift_escalated | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | swift_contained < prolonged_escalated | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | swift_contained < infrastructure_collapse | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | prolonged_contained > swift_escalated | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | prolonged_contained < prolonged_escalated | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | prolonged_contained < infrastructure_collapse | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | swift_escalated < prolonged_escalated | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | swift_escalated < infrastructure_collapse | 1.000 |
| world_fertilizer.fertilizer_price_index_pct | prolonged_escalated < infrastructure_collapse | 1.000 |

## Dominant knobs (mean first-order index over scenarios)

| output | top knob | S1 | second | S1 |
|---|---|---|---|---|
| apsim.mean_yield_pct_change | fertilizer_demand_elasticity | 0.543 | me_loss_to_nitrogen_passthrough | 0.363 |
| fed_oil.peak_gdp_impact_pct | gdp_elasticity_oil | 0.957 | oil_demand_elasticity | 0.0411 |
| mpsge_jl.gdp_impact_pct | gdp_elasticity_oil | 0.616 | gdp_elasticity_lng | 0.333 |
| poles_jrc.peak_price_change_pct | oil_demand_elasticity | 0.558 | oil_supply_elasticity | 0.393 |
| pycge.cpi_inflation_pct | cpi_elasticity_oil | 0.864 | cpi_elasticity_fertilizer | 0.0909 |
| pycge.gdp_impact_pct | gdp_elasticity_oil | 0.89 | gdp_elasticity_lng | 0.0589 |
| world_fertilizer.fertilizer_price_index_pct | me_loss_to_nitrogen_passthrough | 0.96 | freight_elasticity | 0.0356 |

Variables with no variance across draws (no knob reaches them) have no index.
