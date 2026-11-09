# The game adjudicator (`src/game/`)

The economic war game (repo `EconomicWarGames`) runs a weekly Hormuz crisis clock. Each round it
clears markets with its own Tier 0 rule, then asks this service for the numbers the pipeline's
analytical-MVP adapters compute for the same world state. This document is the contract.

## What it is, and is not

- It calls adapters directly through the `ModelAdapter` contract: `validate_inputs`,
  `translate_inputs`, `execute`. No LangGraph graph, no LLM, no scenario narrative.
- It applies the pipeline's forwarding rules (`configs/upstream_forwarding_mapping.yaml`) between
  models and records every replacement as an override, the same Replace-with-metadata policy
  Algorithm 1 step 11 uses.
- Every number it returns names the model id, output key and implementation mode it came from.
  Today every model runs as an `analytical_reduction` (a dagger in the pipeline's reports).
- A failed, timed-out or invalid model becomes a `fallbacks` entry. The response is always
  complete. The game then keeps its previous multiplier for that commodity and shows a badge.

## Running it

```
pip install -e ".[dev,game]"
python -m src.game.api --port 8031
curl -s localhost:8031/healthz
curl -s localhost:8031/models
```

The game server points at it with `EWG_ADJUDICATOR_URL=http://127.0.0.1:8031`.

## Request: `POST /adjudicate`

```json
{
  "game_id": "demo", "turn": 3, "seed": 7,
  "world": {
    "transit_capacity_pct": 20, "mine_density": 0.5, "escalation_rung": 6,
    "qatar_damaged_share": 0.17, "bypass_used_mbd": 4.0, "stock_release_mbd": 2.0,
    "demand_restraint_mbd": 0.0, "war_risk_premium_pct": 5.0,
    "weeks_elapsed": 2, "expected_remaining_weeks": 6,
    "rerouting_via_cape": true, "helium_reserve_release_mmscf": 0.0
  },
  "teams": {"US": {"region": "US"}, "GCC": {"region": "MENA_GCC"}}
}
```

`teams` may be omitted; the six baseline teams and their regions are then used.

## Response

| Field | Meaning |
|---|---|
| `multipliers` | Price ratio to baseline this round per good: `oil, diesel, lng, fertilizer_n, helium`. The model peak is spread over the first rounds by a designer ramp. |
| `peak_multipliers` | The model's full-disruption peak before the ramp. |
| `lane` | `rerouting_cost_multiplier` (mean of AISdb and AIS_project), `effective_fleet_capacity_loss_pct`, `war_risk_insurance_premium_pct`. |
| `shocks` | The raw percent shocks the macro kernel consumed. |
| `macro_by_team` | Per seat: `gdp_impact_pct`, `cpi_inflation_pct`, `consumption_impact_pct` from `compute_regional_macro_outcomes`, mapped by the team crosswalk. |
| `provenance` | One row per numeric output: `model_id, output_key, value, implementation_mode, runtime_ms`. |
| `runs` | One row per adapter call with status, mode, the inputs it actually received, and any error. |
| `overrides` | The forwarding records (`OverrideRecord.to_dict()`). |
| `flags` | Cross-source disagreement flags from `src/synthesis/consistency.py`. |
| `fallbacks` | Models that did not produce a value and why. |
| `derived` | The intermediate quantities from the mapping file (closure fraction, net loss, duration). |
| `scenario_label` | The pipeline scenario id used for scenario-scoped rules, derived from rung, duration and damage. |

## How world state becomes parameters

`configs/game/game_state_to_parameters.yaml` holds one block per adapter. A parameter is a
literal or an `{expr: ...}` over `world.*`, `baseline.*` and `derived.*`. The evaluator accepts
arithmetic, comparisons, boolean logic, the ternary, dotted and indexed lookups and the functions
`min max abs round clamp`, nothing else. The draft rules follow Section 5.1 of the integration plan:

| Game variable | Parameter |
|---|---|
| transit capacity, bypass used, releases, restraint | `poles_jrc.supply_loss_mbd` = 20.9 x (1 - T/100) - bypass - releases - restraint, floored at 0 |
| weeks elapsed + expected remaining | every `disruption_duration_months` |
| transit capacity, Qatar damaged share | `lngst.qatar_export_reduction_pct`, `world_helium_model.qatar_helium_supply_loss_pct` |
| escalation rung | `lngst.spot_price_multiplier` (designer curve) and the shipping models' alternative routes |
| war-risk premium | `poles_jrc.insurance_premium_increase_pct` relative to the 0.25 pct pre-war rate |

## Execution order and forwarding

1. `aisdb`, `ais_project`
2. `poles_jrc`, `lngst`, `world_helium_model`, `world_fertilizer`, `futures`
3. `marketsim`, `fed_oil`, then the macro kernel

Forwarding is resolved per model from every completed run so far. This matters because the
pipeline's `ModelExecutor` applies forwarding only between analytical levels, and the shipping
models and POLES-JRC share the COMMODITY level, so the `combine: mean` rule for
`poles_jrc.rerouting_cost_multiplier` never fires there. Here it does. The game file adds three
rules the pipeline mapping lacks (LNGST gas impulse into the fertilizer model and MarketSim, the
fertilizer index into the futures curves) and turns one off (the war-risk premium is observed game
state, not an estimate to replace).

## The frozen baseline

`configs/game/hormuz_2026_baseline.yaml`, as of 8 November 2026. Every value is a record
`{value, unit, source, status}` with status `primary`, `secondary` or `designer`. `GET /baseline`
returns the values and the flat record table. The game mirrors the numbers it needs into
`scenarios/hormuz-2026/crisis.json` and labels them with this date.

## Limits to state in the classroom

- Analytical reductions have known limits: POLES-JRC here is a constant-elasticity impulse with
  geometric decay, the Fed oil model's IRFs are geometric, and the macro kernel is a calibrated
  closed form. The rendered mode on every number says so.
- The Japan-Korea team maps to the kernel's `ROW` region, which understates its import exposure.
- The price ramp, the LNG spot multiplier by rung and the diesel pass-through are designer
  parameters, tagged as such in the baseline file.
