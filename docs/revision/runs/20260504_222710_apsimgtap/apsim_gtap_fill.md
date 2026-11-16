# APSIM-GTAP cells for run `20260504_222710`

Executed under `fill_apsimgtap_20260504_222710` with no LLM call. Inputs come from the run's own parameter records and model outputs; the original synthesis saw none of these cells.

## Inputs

| scenario | input | value | source | kind |
|---|---|---|---|---|
| infrastructure_collapse | middle_east_fertilizer_production_loss_pct | 30.0 | world_fertilizer.middle_east_production_loss_pct | run_parameter |
| infrastructure_collapse | gulf_oil_supply_loss_mbd | 4.2 | poles_jrc.supply_loss_mbd | run_parameter |
| infrastructure_collapse | disruption_duration_months | 7.0 | poles_jrc.disruption_duration_months | run_parameter |
| infrastructure_collapse | trade_cost_multiplier | 1.1869 | aisdb.rerouting_cost_multiplier | forwarded_model_output |
| prolonged_contained | middle_east_fertilizer_production_loss_pct | 30.0 | world_fertilizer.middle_east_production_loss_pct | run_parameter |
| prolonged_contained | gulf_oil_supply_loss_mbd | 4.32 | poles_jrc.supply_loss_mbd | run_parameter |
| prolonged_contained | disruption_duration_months | 4.0 | poles_jrc.disruption_duration_months | run_parameter |
| prolonged_contained | trade_cost_multiplier | 1.1869 | aisdb.rerouting_cost_multiplier | forwarded_model_output |
| prolonged_escalated | middle_east_fertilizer_production_loss_pct | 30.0 | world_fertilizer.middle_east_production_loss_pct | run_parameter |
| prolonged_escalated | gulf_oil_supply_loss_mbd | 4.3 | poles_jrc.supply_loss_mbd | run_parameter |
| prolonged_escalated | disruption_duration_months | 7.0 | poles_jrc.disruption_duration_months | run_parameter |
| prolonged_escalated | trade_cost_multiplier | 1.1869 | aisdb.rerouting_cost_multiplier | forwarded_model_output |
| swift_contained | middle_east_fertilizer_production_loss_pct | 0.0 | world_fertilizer.middle_east_production_loss_pct | run_parameter |
| swift_contained | gulf_oil_supply_loss_mbd | 4.38 | poles_jrc.supply_loss_mbd | run_parameter |
| swift_contained | disruption_duration_months | 0.42 | poles_jrc.disruption_duration_months | run_parameter |
| swift_contained | trade_cost_multiplier | 1.1869 | aisdb.rerouting_cost_multiplier | forwarded_model_output |
| swift_escalated | middle_east_fertilizer_production_loss_pct | 30.0 | world_fertilizer.middle_east_production_loss_pct | run_parameter |
| swift_escalated | gulf_oil_supply_loss_mbd | 4.32 | poles_jrc.supply_loss_mbd | run_parameter |
| swift_escalated | disruption_duration_months | 4.0 | poles_jrc.disruption_duration_months | run_parameter |
| swift_escalated | trade_cost_multiplier | 1.1869 | aisdb.rerouting_cost_multiplier | forwarded_model_output |

Analyst-baseline fallbacks: 0

## Results

| scenario | status | US GDP % | Gulf GDP % | US maize yield % | converged | zero-shock residual | runtime s |
|---|---|---|---|---|---|---|---|
| infrastructure_collapse | completed | -0.0001594509866920113 | -0.3845108237618411 | 2.2515723863136827e-05 | True | 0.0 | 151.83548996504396 |
| prolonged_contained | completed | 0.0001236948674154803 | -0.2622476315968014 | 2.2515723863136827e-05 | True | 0.0 | 139.1722189327702 |
| prolonged_escalated | completed | -0.0001598219236287335 | -0.38522832505540894 | 2.2515723863136827e-05 | True | 0.0 | 149.6564194150269 |
| swift_contained | completed | 1.130536597671039e-06 | -0.0011854445818082482 | -1.5010482568023065e-05 | True | 0.0 | 4.891988881863654 |
| swift_escalated | completed | 0.0001236948674154803 | -0.2622476315968014 | 2.2515723863136827e-05 | True | 0.0 | 4.705604849383235 |
