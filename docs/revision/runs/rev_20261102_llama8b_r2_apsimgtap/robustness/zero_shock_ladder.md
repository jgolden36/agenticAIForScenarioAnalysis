# Zero-shock residual and dose ladder

Generated 2026-11-08T19:57:33.633987+00:00. Each model runs alone on its analyst-baseline inputs (`configs/baselines/hormuz_2026_analyst.yaml`), with the shock fields in `configs/robustness/shock_fields.yaml` set to neutral (zero shock) or scaled by 0, 0.25, 0.5, 0.75, 1, 1.25, 1.6. Ported from the AgResilience E0 check.

Zero-shock pass: |change-type headline output| <= 0.0001. Monotone: the output never reverses direction along the ladder.

## By model

| model | run status | zero-shock checks | zero-shock failures | ladders | non-monotone | sign flips |
|---|---|---|---|---|---|---|
| ais_project | completed | 10 | 0 | 25 | 0 | 0 |
| aisdb | completed | 10 | 0 | 20 | 0 | 0 |
| apsim | completed | 15 | 0 | 15 | 0 | 0 |
| apsim_gtap | completed | 20 | 0 | 16 | 4 | 1 |
| argonne_abm | completed | 10 | 0 | 15 | 0 | 0 |
| cwatm | completed | 15 | 0 | 20 | 0 | 0 |
| fed_oil | completed | 25 | 0 | 30 | 0 | 0 |
| futures | completed | 5 | 0 | 10 | 0 | 0 |
| lngst | completed | 10 | 0 | 30 | 0 | 0 |
| marketsim | completed | 20 | 0 | 30 | 0 | 0 |
| mpsge_jl | completed | 35 | 0 | 40 | 0 | 0 |
| nrel | completed | 30 | 0 | 40 | 0 | 0 |
| poles_jrc | completed | 10 | 0 | 25 | 0 | 0 |
| pycge | completed | 35 | 0 | 35 | 0 | 0 |
| weap_mena | completed | 20 | 0 | 25 | 0 | 0 |
| world_fertilizer | completed | 35 | 0 | 35 | 0 | 0 |
| world_helium_model | completed | 10 | 0 | 25 | 0 | 0 |

## Non-monotone or sign-changing ladders

| model | scenario | output | monotone | one sign | clipped dose |
|---|---|---|---|---|---|
| apsim_gtap | swift_contained | us_gdp_pct | False | True | False |
| apsim_gtap | prolonged_contained | us_gdp_pct | False | False | True |
| apsim_gtap | swift_escalated | us_gdp_pct | False | True | True |
| apsim_gtap | swift_escalated | us_maize_yield_change_pct | False | True | True |
