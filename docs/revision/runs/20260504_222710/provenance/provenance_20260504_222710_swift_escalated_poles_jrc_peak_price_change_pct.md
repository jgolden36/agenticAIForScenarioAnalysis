# Provenance chain: `peak_price_change_pct` from `poles_jrc` (scenario swift_escalated)

Run `20260504_222710`; chain links found: narrative=yes, parameters=yes, model_run=yes, synthesis=no (incomplete)

| step | content |
|---|---|
| 1. Scenario narrative (Swift Escalated Conflict) | **disruption_duration_months**: "The closure lasted for 4 months, causing significant economic disruption." |
| 2. Extracted parameters (analyst validation: approved) | `supply_loss_mbd` = 4.32 mb/d (confidence high)<br>`disruption_duration_months` = 4 months (confidence high)<br>`rerouting_cost_multiplier` = 1.6 factor (confidence medium)<br>`insurance_premium_increase_pct` = 100 percent (confidence low)<br>`substitute_energy_availability` = 0 fraction (confidence low) |
| 3. Adapter inputs | LLM-extracted parameters used as-is (no upstream override recorded) |
| 4. Model output | `poles_jrc.peak_price_change_pct` = 58.25 (status completed; runtime 0.000143s) |
| 5. Synthesis | _no synthesis outcome cites this (model, variable)_ |
