# APSIM-GTAP cells for run `20260504_222710`

Executed under `gate_apsimgtap_20260504_222710` with no LLM call. Inputs come from the run's own parameter records and model outputs; the original synthesis saw none of these cells.

## Inputs

| scenario | input | value | source | kind |
|---|---|---|---|---|
| swift_contained | middle_east_fertilizer_production_loss_pct | 0.0 | world_fertilizer.middle_east_production_loss_pct | run_parameter |
| swift_contained | gulf_oil_supply_loss_mbd | 4.38 | poles_jrc.supply_loss_mbd | run_parameter |
| swift_contained | disruption_duration_months | 0.42 | poles_jrc.disruption_duration_months | run_parameter |
| swift_contained | trade_cost_multiplier | 1.1869 | aisdb.rerouting_cost_multiplier | forwarded_model_output |

Analyst-baseline fallbacks: 0

## Results

| scenario | status | US GDP % | Gulf GDP % | US maize yield % | converged | zero-shock residual | runtime s |
|---|---|---|---|---|---|---|---|
| swift_contained | completed | 1.130536597671039e-06 | -0.0011854445818082482 | -1.5010482568023065e-05 | True | 0.0 | 162.54984958563 |
