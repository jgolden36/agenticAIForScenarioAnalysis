# APSIM-GTAP: Armington-elasticity Latin hypercube

Generated 2026-11-08T20:07:01.314115+00:00. ESUBM/ESUBD for chemicals and grains in every region scaled by factors in [0.5, 1.5] (seed 20261010, 100 draws), GTAP re-calibrated per draw, all scenarios solved with the GTAP-crop fixed point. Design of AgResilience E9.

Complete draws: 100. Failed cases: 0. Cases failing the zero-shock or convergence gate: 0.

## Bands (p05 / p50 / p95; point = calibrated elasticities)

| output | scenario | point | p05 | p50 | p95 |
|---|---|---|---|---|---|
| gulf_gdp_pct | infrastructure_collapse | -0.3845 | -0.5717 | -0.3864 | -0.2642 |
| gulf_gdp_pct | prolonged_contained | -0.2622 | -0.3569 | -0.2642 | -0.1953 |
| gulf_gdp_pct | prolonged_escalated | -0.3852 | -0.5724 | -0.3871 | -0.2649 |
| gulf_gdp_pct | swift_contained | -0.001185 | -0.001399 | -0.001188 | -0.0009804 |
| gulf_gdp_pct | swift_escalated | -0.2622 | -0.3569 | -0.2642 | -0.1953 |
| us_chm_consumption_pct | infrastructure_collapse | -0.07526 | -0.1014 | -0.07518 | -0.05738 |
| us_chm_consumption_pct | prolonged_contained | -0.05098 | -0.06215 | -0.05097 | -0.04213 |
| us_chm_consumption_pct | prolonged_escalated | -0.07526 | -0.1014 | -0.07518 | -0.05738 |
| us_chm_consumption_pct | swift_contained | -0.0003087 | -0.0003272 | -0.0003085 | -0.0002905 |
| us_chm_consumption_pct | swift_escalated | -0.05098 | -0.06215 | -0.05097 | -0.04213 |
| us_gdp_pct | infrastructure_collapse | -0.0001595 | -0.0004585 | -0.0001348 | 4.398e-05 |
| us_gdp_pct | prolonged_contained | 0.0001237 | -9.681e-05 | 0.0001207 | 0.0002732 |
| us_gdp_pct | prolonged_escalated | -0.0001598 | -0.0004589 | -0.0001352 | 4.36e-05 |
| us_gdp_pct | swift_contained | 1.131e-06 | -7.676e-07 | 1.213e-06 | 2.783e-06 |
| us_gdp_pct | swift_escalated | 0.0001237 | -9.681e-05 | 0.0001207 | 0.0002732 |
| us_gro_price_pct | infrastructure_collapse | 0.0579 | 0.0445 | 0.05846 | 0.06521 |
| us_gro_price_pct | prolonged_contained | 0.03695 | 0.02659 | 0.03739 | 0.04472 |
| us_gro_price_pct | prolonged_escalated | 0.05795 | 0.04455 | 0.05852 | 0.06527 |
| us_gro_price_pct | swift_contained | 0.0002845 | 0.0002112 | 0.0002877 | 0.00035 |
| us_gro_price_pct | swift_escalated | 0.03695 | 0.02659 | 0.03739 | 0.04472 |
| us_maize_yield_change_pct | infrastructure_collapse | 2.252e-05 | 2.252e-05 | 3.002e-05 | 5.254e-05 |
| us_maize_yield_change_pct | prolonged_contained | 2.252e-05 | 7.505e-06 | 2.252e-05 | 3.002e-05 |
| us_maize_yield_change_pct | prolonged_escalated | 2.252e-05 | 2.252e-05 | 3.002e-05 | 5.254e-05 |
| us_maize_yield_change_pct | swift_contained | -1.501e-05 | -1.501e-05 | -1.501e-05 | -1.501e-05 |
| us_maize_yield_change_pct | swift_escalated | 2.252e-05 | 7.505e-06 | 2.252e-05 | 3.002e-05 |

## Ordering robustness

| output | pair (calibrated order) | share kept |
|---|---|---|
| gulf_gdp_pct | infrastructure_collapse < prolonged_contained | 1.000 |
| gulf_gdp_pct | infrastructure_collapse > prolonged_escalated | 1.000 |
| gulf_gdp_pct | infrastructure_collapse < swift_contained | 1.000 |
| gulf_gdp_pct | infrastructure_collapse < swift_escalated | 1.000 |
| gulf_gdp_pct | prolonged_contained > prolonged_escalated | 1.000 |
| gulf_gdp_pct | prolonged_contained < swift_contained | 1.000 |
| gulf_gdp_pct | prolonged_contained = swift_escalated (tie) | 1.000 |
| gulf_gdp_pct | prolonged_escalated < swift_contained | 1.000 |
| gulf_gdp_pct | prolonged_escalated < swift_escalated | 1.000 |
| gulf_gdp_pct | swift_contained > swift_escalated | 1.000 |
| us_chm_consumption_pct | infrastructure_collapse < prolonged_contained | 1.000 |
| us_chm_consumption_pct | infrastructure_collapse > prolonged_escalated | 1.000 |
| us_chm_consumption_pct | infrastructure_collapse < swift_contained | 1.000 |
| us_chm_consumption_pct | infrastructure_collapse < swift_escalated | 1.000 |
| us_chm_consumption_pct | prolonged_contained > prolonged_escalated | 1.000 |
| us_chm_consumption_pct | prolonged_contained < swift_contained | 1.000 |
| us_chm_consumption_pct | prolonged_contained = swift_escalated (tie) | 1.000 |
| us_chm_consumption_pct | prolonged_escalated < swift_contained | 1.000 |
| us_chm_consumption_pct | prolonged_escalated < swift_escalated | 1.000 |
| us_chm_consumption_pct | swift_contained > swift_escalated | 1.000 |
| us_gdp_pct | infrastructure_collapse < prolonged_contained | 1.000 |
| us_gdp_pct | infrastructure_collapse > prolonged_escalated | 1.000 |
| us_gdp_pct | infrastructure_collapse < swift_contained | 0.910 **<0.95** |
| us_gdp_pct | infrastructure_collapse < swift_escalated | 1.000 |
| us_gdp_pct | prolonged_contained > prolonged_escalated | 1.000 |
| us_gdp_pct | prolonged_contained > swift_contained | 0.840 **<0.95** |
| us_gdp_pct | prolonged_contained = swift_escalated (tie) | 1.000 |
| us_gdp_pct | prolonged_escalated < swift_contained | 0.910 **<0.95** |
| us_gdp_pct | prolonged_escalated < swift_escalated | 1.000 |
| us_gdp_pct | swift_contained < swift_escalated | 0.840 **<0.95** |
| us_gro_price_pct | infrastructure_collapse > prolonged_contained | 1.000 |
| us_gro_price_pct | infrastructure_collapse < prolonged_escalated | 1.000 |
| us_gro_price_pct | infrastructure_collapse > swift_contained | 1.000 |
| us_gro_price_pct | infrastructure_collapse > swift_escalated | 1.000 |
| us_gro_price_pct | prolonged_contained < prolonged_escalated | 1.000 |
| us_gro_price_pct | prolonged_contained > swift_contained | 1.000 |
| us_gro_price_pct | prolonged_contained = swift_escalated (tie) | 1.000 |
| us_gro_price_pct | prolonged_escalated > swift_contained | 1.000 |
| us_gro_price_pct | prolonged_escalated > swift_escalated | 1.000 |
| us_gro_price_pct | swift_contained < swift_escalated | 1.000 |
| us_maize_yield_change_pct | infrastructure_collapse = prolonged_contained (tie) | 0.140 **<0.95** |
| us_maize_yield_change_pct | infrastructure_collapse = prolonged_escalated (tie) | 0.870 **<0.95** |
| us_maize_yield_change_pct | infrastructure_collapse > swift_contained | 1.000 |
| us_maize_yield_change_pct | infrastructure_collapse = swift_escalated (tie) | 0.140 **<0.95** |
| us_maize_yield_change_pct | prolonged_contained = prolonged_escalated (tie) | 0.130 **<0.95** |
| us_maize_yield_change_pct | prolonged_contained > swift_contained | 1.000 |
| us_maize_yield_change_pct | prolonged_contained = swift_escalated (tie) | 1.000 |
| us_maize_yield_change_pct | prolonged_escalated > swift_contained | 1.000 |
| us_maize_yield_change_pct | prolonged_escalated = swift_escalated (tie) | 0.130 **<0.95** |
| us_maize_yield_change_pct | swift_contained < swift_escalated | 1.000 |
