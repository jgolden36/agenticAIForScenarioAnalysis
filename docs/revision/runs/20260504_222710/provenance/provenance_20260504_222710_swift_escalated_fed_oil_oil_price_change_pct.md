# Provenance chain: `oil_price_change_pct` from `fed_oil` (scenario swift_escalated)

Run `20260504_222710`; chain links found: narrative=yes, parameters=yes, model_run=yes, synthesis=yes (complete)

| step | content |
|---|---|
| 1. Scenario narrative (Swift Escalated Conflict) | **oil_price_change_pct**: "The closure disrupts approximately 21% of global oil supply and 25% of global LNG trade." "February 25, 2026: The conflict escalates, with both sides suffering significant losses." |
| 2. Extracted parameters (analyst validation: approved) | `oil_price_change_pct` = 25 % (confidence high)<br>`shock_type` = supply  (confidence high)<br>`disruption_duration_quarters` = 1 quarters (confidence low)<br>`fed_funds_rate_baseline` = 2.5 % (confidence low) |
| 3. Adapter inputs (upstream forwarding overrides) | `oil_price_change_pct`: LLM-extracted 25 -> upstream 58.25 from `poles_jrc.peak_price_change_pct` via identity; deviation 79.8799% (flagged at 50%) (source completed in this run) |
| 4. Model output | `fed_oil.oil_price_change_pct` = 58.25 (status completed; runtime 0.000206s) |
| 5. Synthesis | [short_run/macro] value 58.25: "The oil price is expected to increase by 58.25% due to the disruption in the Strait of Hormuz." |
