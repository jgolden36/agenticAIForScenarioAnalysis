# Open loop vs fixed point, and the forwarding barrier

Generated 2026-11-08T19:58:27.263524+00:00. Port of the AgResilience E3 comparison.

## (a) APSIM-GTAP: one pass vs GTAP-crop fixed point

| run | scenario | variable | one pass | fixed point | gap | gap % | iterations |
|---|---|---|---|---|---|---|---|
| rev_20261102_llama8b_r2 | infrastructure_collapse | yield_change_pct | 2.252e-05 | 2.252e-05 | 0 | 0 | 2 |
| rev_20261102_llama8b_r2 | infrastructure_collapse | us_gro_price_pct | 0.05793 | 0.0579 | -2.284e-05 | -0.0394 | 2 |
| rev_20261102_llama8b_r2 | infrastructure_collapse | us_gro_production_pct | 0.1494 | 0.1494 | 6.952e-06 | 0.00465 | 2 |
| rev_20261102_llama8b_r2 | infrastructure_collapse | us_gdp_pct | -0.0001595 | -0.0001595 | 7.557e-08 | -0.0474 | 2 |
| rev_20261102_llama8b_r2 | prolonged_contained | yield_change_pct | 2.252e-05 | 2.252e-05 | 0 | 0 | 2 |
| rev_20261102_llama8b_r2 | prolonged_contained | us_gro_price_pct | 0.03697 | 0.03695 | -2.284e-05 | -0.0618 | 2 |
| rev_20261102_llama8b_r2 | prolonged_contained | us_gro_production_pct | 0.09475 | 0.09476 | 6.95e-06 | 0.00734 | 2 |
| rev_20261102_llama8b_r2 | prolonged_contained | us_gdp_pct | 0.0001236 | 0.0001237 | 7.552e-08 | 0.0611 | 2 |
| rev_20261102_llama8b_r2 | prolonged_escalated | yield_change_pct | 2.252e-05 | 2.252e-05 | 0 | 0 | 2 |
| rev_20261102_llama8b_r2 | prolonged_escalated | us_gro_price_pct | 0.05798 | 0.05795 | -2.284e-05 | -0.0394 | 2 |
| rev_20261102_llama8b_r2 | prolonged_escalated | us_gro_production_pct | 0.1494 | 0.1494 | 6.952e-06 | 0.00465 | 2 |
| rev_20261102_llama8b_r2 | prolonged_escalated | us_gdp_pct | -0.0001599 | -0.0001598 | 7.557e-08 | -0.0473 | 2 |
| rev_20261102_llama8b_r2 | swift_contained | yield_change_pct | -1.501e-05 | -1.501e-05 | 0 | -0 | 2 |
| rev_20261102_llama8b_r2 | swift_contained | us_gro_price_pct | 0.0002692 | 0.0002845 | 1.522e-05 | 5.65 | 2 |
| rev_20261102_llama8b_r2 | swift_contained | us_gro_production_pct | 0.0003973 | 0.0003927 | -4.631e-06 | -1.17 | 2 |
| rev_20261102_llama8b_r2 | swift_contained | us_gdp_pct | 1.181e-06 | 1.131e-06 | -5.028e-08 | -4.26 | 2 |
| rev_20261102_llama8b_r2 | swift_escalated | yield_change_pct | 2.252e-05 | 2.252e-05 | 0 | 0 | 2 |
| rev_20261102_llama8b_r2 | swift_escalated | us_gro_price_pct | 0.03697 | 0.03695 | -2.284e-05 | -0.0618 | 2 |
| rev_20261102_llama8b_r2 | swift_escalated | us_gro_production_pct | 0.09475 | 0.09476 | 6.95e-06 | 0.00734 | 2 |
| rev_20261102_llama8b_r2 | swift_escalated | us_gdp_pct | 0.0001236 | 0.0001237 | 7.552e-08 | 0.0611 | 2 |

## (b) Forwarding barrier on vs off (analyst-baseline inputs)

`forwarded inputs` counts the inputs the barrier replaced for that model and scenario.

| scenario | model | output | forwarded inputs | with barrier | without | difference | difference % |
|---|---|---|---|---|---|---|---|
| swift_contained | pycge | gdp_impact_pct | 3 | -0.4217 | -0.2872 | -0.1345 | 46.8 |
| swift_contained | pycge | cpi_inflation_pct | 3 | 2.69 | 1.85 | 0.8398 | 45.4 |
| swift_contained | mpsge_jl | gdp_impact_pct | 5 | -0.3697 | -0.1965 | -0.1732 | 88.1 |
| swift_contained | fed_oil | peak_gdp_impact_pct | 1 | -0.9061 | -0.5626 | -0.3435 | 61.1 |
| swift_contained | poles_jrc | peak_price_change_pct | 0 | 80.54 | 80.54 | 0 | 0 |
| swift_contained | world_fertilizer | fertilizer_price_index_pct | 0 | 38.32 | 38.32 | 0 | 0 |
| swift_contained | apsim | mean_yield_pct_change | 2 | -15.93 | -10.1 | -5.824 | 57.6 |
| swift_contained | marketsim | consumer_surplus_loss_bn_usd | 0 | 15.58 | 15.58 | 0 | 0 |
| prolonged_contained | pycge | gdp_impact_pct | 3 | -1.651 | -1.213 | -0.4384 | 36.1 |
| prolonged_contained | pycge | cpi_inflation_pct | 3 | 3.465 | 2.638 | 0.8271 | 31.4 |
| prolonged_contained | mpsge_jl | gdp_impact_pct | 5 | -1.849 | -0.972 | -0.8775 | 90.3 |
| prolonged_contained | fed_oil | peak_gdp_impact_pct | 1 | -1.733 | -1.137 | -0.5959 | 52.4 |
| prolonged_contained | poles_jrc | peak_price_change_pct | 0 | 99.06 | 99.06 | 0 | 0 |
| prolonged_contained | world_fertilizer | fertilizer_price_index_pct | 0 | 46.68 | 46.68 | 0 | 0 |
| prolonged_contained | apsim | mean_yield_pct_change | 2 | -20.22 | -15.87 | -4.359 | 27.5 |
| prolonged_contained | marketsim | consumer_surplus_loss_bn_usd | 0 | 74.47 | 74.47 | 0 | 0 |
| swift_escalated | pycge | gdp_impact_pct | 3 | -0.7176 | -0.4316 | -0.286 | 66.3 |
| swift_escalated | pycge | cpi_inflation_pct | 3 | 3.722 | 2.375 | 1.347 | 56.7 |
| swift_escalated | mpsge_jl | gdp_impact_pct | 5 | -0.6293 | -0.2968 | -0.3325 | 112 |
| swift_escalated | fed_oil | peak_gdp_impact_pct | 1 | -1.325 | -0.675 | -0.6497 | 96.3 |
| swift_escalated | poles_jrc | peak_price_change_pct | 0 | 117.8 | 117.8 | 0 | 0 |
| swift_escalated | world_fertilizer | fertilizer_price_index_pct | 0 | 45.36 | 45.36 | 0 | 0 |
| swift_escalated | apsim | mean_yield_pct_change | 2 | -40.77 | -17.07 | -23.71 | 139 |
| swift_escalated | marketsim | consumer_surplus_loss_bn_usd | 0 | 22.65 | 22.65 | 0 | 0 |
| prolonged_escalated | pycge | gdp_impact_pct | 3 | -2.815 | -1.867 | -0.9484 | 50.8 |
| prolonged_escalated | pycge | cpi_inflation_pct | 3 | 5.537 | 3.922 | 1.614 | 41.2 |
| prolonged_escalated | mpsge_jl | gdp_impact_pct | 5 | -3.368 | -1.643 | -1.725 | 105 |
| prolonged_escalated | fed_oil | peak_gdp_impact_pct | 1 | -2.501 | -1.4 | -1.101 | 78.7 |
| prolonged_escalated | poles_jrc | peak_price_change_pct | 0 | 142.9 | 142.9 | 0 | 0 |
| prolonged_escalated | world_fertilizer | fertilizer_price_index_pct | 0 | 55.03 | 55.03 | 0 | 0 |
| prolonged_escalated | apsim | mean_yield_pct_change | 2 | -44.04 | -25.48 | -18.56 | 72.9 |
| prolonged_escalated | marketsim | consumer_surplus_loss_bn_usd | 0 | 124 | 124 | 0 | 0 |
| infrastructure_collapse | pycge | gdp_impact_pct | 4 | -5.106 | -3.892 | -1.214 | 31.2 |
| infrastructure_collapse | pycge | cpi_inflation_pct | 4 | 10.25 | 8.298 | 1.954 | 23.5 |
| infrastructure_collapse | mpsge_jl | gdp_impact_pct | 6 | -7.924 | -4.389 | -3.535 | 80.5 |
| infrastructure_collapse | fed_oil | peak_gdp_impact_pct | 1 | -4.305 | -2.849 | -1.456 | 51.1 |
| infrastructure_collapse | poles_jrc | peak_price_change_pct | 0 | 143.5 | 143.5 | 0 | 0 |
| infrastructure_collapse | world_fertilizer | fertilizer_price_index_pct | 0 | 60.52 | 60.52 | 0 | 0 |
| infrastructure_collapse | apsim | mean_yield_pct_change | 2 | -66.93 | -40.5 | -26.44 | 65.3 |
| infrastructure_collapse | marketsim | consumer_surplus_loss_bn_usd | 0 | 297.9 | 297.9 | 0 | 0 |
