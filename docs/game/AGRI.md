# The agricultural module: two services for the game's `agri` ruleset

The economic war game (repo `EconomicWarGames`) has an agricultural ruleset, `agri`: a quarterly
clock, crop calendars, export bans and tariffs, crop and livestock disease, and a Strait of
Hormuz link to fertilizer and Gulf food imports. This repo serves it in two ways.

| Service | Where | LLM | What it answers |
|---|---|---|---|
| Tier 1 agricultural adjudicator | `src/game/agri.py`, `POST /adjudicate/agri` on `python -m src.game.api` (port 8031) | none | fertilizer prices, farm-gate prices, application cuts, crop yields, forward curves, macro rows |
| Control-cell LLM tools | `src/control_cell/`, `python -m src.control_cell.api` (port 8032) | yes | draft shock cards; map a team's free-text novel action onto the menus |

Two rules bind both.

- The game calls each service from its request handler and records the whole answer in the
  action payload. The ruleset reads only the payload, so a replay never calls out.
- A failure is an answer, never an exception. The adjudicator lists failed models under
  `fallbacks`; the control cell answers `{"status": "unavailable", "reason"}` with HTTP 200.

## Running them

```
pip install -e ".[dev,game]"
python -m src.game.api --port 8031
python -m src.control_cell.api --port 8032
```

The game points at them with `EWG_ADJUDICATOR_URL=http://127.0.0.1:8031` and
`EWG_CONTROL_CELL_URL=http://127.0.0.1:8032`.

The control cell needs an LLM: `PIPELINE_LLM_PROVIDER`, `PIPELINE_LLM_MODEL`, and the provider's
key and package (for example `pip install -e ".[llm-providers]"` and `ANTHROPIC_API_KEY`), exactly
as `src/common/llm.py` reads them. The OpenAI-compatible providers (`openai`, `vllm`, `ollama`)
need no extra package. Without one, `GET /healthz` says
`llm_configured: false` with the reason, and the game's host plays from the menus alone.

## 1. The Tier 1 adjudicator (`POST /adjudicate/agri`)

### Request

```json
{
  "game_id": "g1", "turn": 2, "seed": 0, "date": "2027-04-01",
  "world": {
    "gas_price_change_pct": 78.0, "middle_east_fertilizer_loss_pct": 30.0,
    "hormuz_transit_capacity_pct": 70.0, "fertilizer_price_change_pct": 45.0,
    "hormuz_component_pct": 39.0, "expected_shock_months": 6.0,
    "crop_price_change_pct": {"wheat": 12.0, "rice": 3.0, "maize": 8.0, "soybeans": 5.0}
  },
  "teams": {
    "US":  {"region": "US", "fertilizer_passthrough": 0.5, "fertilizer_subsidy_pct": 0.0,
            "water_deficit_pct_by_crop": {}},
    "IND": {"region": "IND", "fertilizer_passthrough": 0.6, "fertilizer_subsidy_pct": 30.0,
            "water_deficit_pct_by_crop": {"wheat": 40.0}}
  }
}
```

- Crops are always the game's names: `wheat`, `rice`, `maize`, `soybeans`. Unknown crops are a 422.
- `fertilizer_price_change_pct` is the game's Tier 0 world nitrogen change, every cause included.
  `hormuz_component_pct` is the part of it the game attributes to the Hormuz link.
- Teams are the seats plus `ROW`. The request carries each team's macro-kernel region.

### What runs, in order

1. `world_fertilizer`, only when the round carries a Hormuz shock (a gas price change or a
   Middle East production loss). Its `nitrogen_price_pct` replaces the game's Hormuz component.
   The export-ban and control-cell parts of the game's number stay the game's:
   `n_world = nitrogen_price_pct + fertilizer_price_change_pct - hormuz_component_pct`.
   Without a Hormuz shock, or when the model fails, `n_world` is the game's number.
2. Per team, the farm-gate rule and the pipeline's own bridge:
   - `farmgate = 100 x ((1 + passthrough x n_world / 100) x (1 - subsidy / 100) - 1)`
   - `cut = clamp(0.35 x max(0, farmgate), 0, 95)`. The elasticity and the cap are read from the
     APSIM rule in `configs/upstream_forwarding_mapping.yaml` (`price_to_demand_reduction`,
     Hendricks & Smith 2018). The baseline file holds a copy used only if that rule is gone.
   - APSIM, nitrogen only, all four crops. Then one water-only APSIM run per crop under a drought.
3. `futures`, once per priced crop (seeded with the game's crop price change) and once for urea
   (seeded with `n_world`), 12 months ahead.
4. The macro kernel, `compute_regional_macro_outcomes({"fertilizer": n_world}, ...)`, one row per
   team by its region.

Every parameter is an expression in `configs/game/agri_state_to_parameters.yaml`. The designer
constants and crop-name crosswalks are in `configs/game/agri_2027_baseline.yaml`, every number a
`{value, unit, source, status}` record tagged `designer`.

### Response

| Field | Meaning |
|---|---|
| `fertilizer` | `nitrogen_price_pct`, `phosphate_price_pct`, `potash_price_pct`, `fertilizer_price_index_pct` (null when the model did not run), `world_change_pct` (the `n_world` every team used), `source_model` (`world_fertilizer` or `game`), `implementation_mode` |
| `farmgate_fertilizer_price_change_pct` | per team |
| `application_reduction_pct` | per team, the bridge's output |
| `yields` | `yields[team][crop] = {n_pct, water_pct}`, percent yield change (negative is a loss). `water_pct` is 0.0 without a drought. A value is `null` when its APSIM run failed: unknown, not zero |
| `forward_curves`, `time_to_normalization_months` | per crop and `urea` |
| `macro_by_team` | `{region, gdp_impact_pct, cpi_inflation_pct, consumption_impact_pct}` per team |
| `provenance` | one row per number: `model_id, output_key, value, implementation_mode, runtime_ms` |
| `runs` | one row per adapter call, with a `label` such as `IND:water:wheat` |
| `overrides` | the bridge per team, and the Tier 1 nitrogen replacing the game's Hormuz component |
| `flags` | `tier0_vs_tier1` when Tier 1 nitrogen and the game's Hormuz component differ by more than 50 pct |
| `fallbacks`, `derived`, `elapsed_ms`, `no_llm` | as in the Hormuz adjudicator |

`GET /models/agri` lists the models and their modes; `GET /baseline/agri` returns the baseline
with its records and the bridge in force.

### Limits to state in the classroom

- Every model here runs as an analytical reduction (a dagger in the pipeline's reports): APSIM is
  a closed-form Mitscherlich N curve plus the FAO water response, the fertilizer model is a
  pass-through rule, the futures are AR(1) decays, the macro kernel is a calibrated closed form.
- APSIM's N curve is steep for small cuts (the response is a power 0.7 of the cut). With the 0.35
  bridge, a doubling of the farm-gate price takes a quarter to a third off a cereal yield. The game
  tags both as designer parameters to calibrate in playtests.
- Crop prices are not computed here. The game clears them with its own Tier 0 rule, including
  bilateral tariffs and bans. The Tier 2 path for prices and bilateral trade is MAgPIE (GAMS),
  MIRAGRODEP (GAMS) or GTAP. The GTAP Julia server in the `AgResilienceDana` repo already takes
  tariff and production shocks and is the natural Tier 2 partner; it is not wired yet.

## 2. The control-cell LLM tools

The integration plan (Section 6) turns the pipeline's LLM modules into control-cell tools. For
agriculture there are two, each a proposal the game's host approves or rejects.

The game sends its own menus with every request. The service checks every item the LLM proposes
against them (`src/control_cell/validate.py`): the move must exist, required fields must be
present, a pick must be one of the options, a number must lie in `[min, max]` (and be whole when
`int` is set), text must fit, and a field the move does not declare must be null. A failing item
goes to `rejected` with its reasons. Nothing is clamped or repaired.

### `POST /agri/cards`: draft shock cards

Request: `{game_id, turn, date, quarter, n_cards (1..6), focus[], guidance, state, menu}`.
`state` is the game's summary: seats and teams, crops, what is growing and about to be planted,
prices, the fertilizer index, the Hormuz status, measures in force, outbreaks, main suppliers per
importer, recent log lines. `menu` is the game's control moves with their fields.

Response:

```json
{"status": "ok",
 "cards": [{"card_id": "c-1a2b3c4d", "move": "drought", "category": "harvest",
            "fields": {"team": "IND", "crop": "wheat", "a": 35.0, "b": null, "text": null},
            "headline": "...", "rationale": "...", "partner_effects": "...", "confidence": "medium",
            "assumption_note": "The magnitude is a scenario assumption for play, not a model output."}],
 "rejected": [{"card": {}, "reasons": ["drought: water_deficit_pct = 120 is above max 90"]}],
 "llm": {"provider": "...", "model": "...", "temperature": 0.4, "prompt_sha256": "...", "raw": {}},
 "elapsed_ms": 1234.0}
```

- `card_id` is `"c-"` plus the first 8 hex digits of the SHA-256 of `{move, fields, headline}`.
- `category` is one of `harvest, disease, hormuz, partner_loss, trade, other`.
- At most one card per (team, crop), and no more than `n_cards`.
- The prompt (`src/control_cell/prompts.py`) asks for cards timed to crops in the ground, spread
  across the focus, with magnitudes stated as scenario assumptions and no invented statistics or
  sources.

### `POST /agri/novel`: map a novel action

Request: `{game_id, turn, seat, seat_name, text, state, order_menu, control_menu}`.

Response: `{status, interpretation, orders[{type, fields}], control[{move, fields}], confidence,
inferred[], unmapped, rejected[], llm, elapsed_ms}`. Order fields are
`crop, partner, a, b, text`; control fields are `team, crop, a, b, text`. At most 3 orders and 2
control moves. `inferred` lists every guess (a partner, a crop, a number the text did not state);
`unmapped` says what no menu entry covers.

### `GET /healthz`

`{ok, llm_configured, provider, model, reason}`. A provider package that builds without a key may
report `llm_configured: true` and still answer `unavailable` on the first call; the reason says why.

## Tests

```
python -m pytest tests/test_game/test_agri.py tests/test_control_cell -q
```

The adjudicator tests run the real analytical-MVP adapters. The control-cell tests use a fake LLM
(`with_structured_output` returning a `RunnableLambda`), so they need no key and no network.
