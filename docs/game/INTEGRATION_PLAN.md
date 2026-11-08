# Wiring the Hormuz agentic pipeline into Economic War Games

**Integration plan, v0.2, 8 November 2026.** Supersedes section 9 of the 8 November working
plan (`hormuz_pipeline_to_wargame_integration_plan.md`) now that the game code exists.

This document plans how three repositories become one playable, adjudicated classroom game:

| Repository | Role in the game | State on 8 November 2026 |
|---|---|---|
| `jgolden36/EconomicWarGames` (package `ewg`) | **The game.** Lobby, seats, clock, actions, record, live board | Stages G0 to G3 built: a multi-player shell with a sandbox ruleset on a synthetic Aluminum world, monthly turns, no economics |
| `jgolden36/agenticAIForScenarioAnalysis` (this repo) | **The adjudicator.** Calibrated numbers for each round, the control cell's LLM tools, era-boundary macro runs, provenance | 34 adapters, 18 run with no licence or binary; the deterministic no-LLM path exists (`run_deterministic_baseline.py`) |
| `jgolden36/metalsRAG` | **Data and later scenarios.** Chokepoint and country gazetteers, the map's bundle format, real company maps for the critical-minerals era | Supplies files, never code; `ewg` already lifted its UI |

The one-paragraph version. The game engine stays in `ewg`, behind the ruleset seam it already
has. This repo grows a small **adjudicator service** that turns a round's game state into
adapter parameters, runs the fast adapters, applies the pipeline's own forwarding rules, and
returns calibrated multipliers with provenance. The game calls it over HTTP or a subprocess,
with a hard timeout and a Tier 0 fallback, and never imports it. The two LLM-backed modules
(parameter extraction, synthesis) serve the control cell only, behind the same approval
checkpoints the pipeline already enforces.

---

## 1. What the code says that the two design documents did not know

Reading all three repositories changes four assumptions in the 8 November plan.

1. **The game is not a map UI to be wrapped. It is an engine with a ruleset seam.** `ewg`
   has `GameState`, `Action`, `parse_form`, a `Ruleset` protocol
   (`legal_actions`, `validate`, `apply`, `on_turn_end`), rooms that validate, apply to a copy,
   append to `actions.jsonl` and broadcast, and a `RoomManager.load` that **replays the record
   through the ruleset**. The sealed-order engine, the auction clearing and the shadow run
   all belong there, not in a new `src/game/` here.

2. **Latency is not the problem the plan assumed.** Every analytical-MVP adapter, called
   directly through `validate_inputs`, `translate_inputs`, `execute`, runs in well under a
   millisecond. All 18 runnable adapters together take under one millisecond
   (`docs/game/fast_adapter_timings.md`, regenerate with
   `python scripts/game/time_fast_adapters.py`). The only real costs are process start
   (about 0.3 s to import the registry) and anything that touches a licensed binary.
   Tier 1 can therefore run on every round, inside the round, and the response surface
   (Tier 2 precomputation) is needed only for the macro CGE and the real upstream paths.

3. **The pipeline already has the no-LLM entry point the game needs.**
   `slurm/scripts/run_deterministic_baseline.py` runs Modules 2 to 4 from an
   analyst-authored YAML with the shared `ModelExecutor`, upstream forwarding on, consistency
   checks and a templated synthesis. A game round is the same shape with a different author:
   the game writes the parameter sets instead of the analyst. `baseline_parameter_sets` and
   the executor are reusable as they stand.

4. **`ewg` forbids runtime imports of its sibling repos.** Its `CLAUDE.md` refuses a dependency
   on the metalsRAG tree and lifts files with a provenance row instead. The same rule should
   bind this repo. So the integration is a **wire protocol plus a fallback**, not a package
   import. Section 5 defines it.

Two smaller findings. The game's `Scenario` is the metalsRAG map bundle plus three files, so
a Hormuz world needs a scenario-format extension (section 6) rather than a new board. And the
game's clock is `turn_months` only (`ewg/engine/clock.py :: add_months`), so the weekly
crisis clock needs `add_days` and a ruleset that owns the clock (section 4.2).

---

## 2. Target architecture

```
                        jgolden36/EconomicWarGames (ewg)                       this repo
 ┌──────────────────────────────────────────────────────────────┐   ┌────────────────────────────────┐
 │ browser: lobby, seats, sealed-order panel, board (Leaflet)   │   │ src/game/adjudicator.py        │
 │        htmx POST /ui/g/{id}/act  ─────────────┐              │   │   game_state_to_parameters.yaml │
 │                                                ▼              │   │   Tier 1 adapters (direct)      │
 │ ewg/engine/rooms.py  validate → apply(copy) → record → bcast │   │   upstream_forwarding (mean)    │
 │        │                                                      │   │   consistency flags             │
 │        ▼                                                      │   │   provenance per number         │
 │ ewg/engine/hormuz/   (new ruleset: HormuzRules)               │   ├────────────────────────────────┤
 │   orders.py   sealed orders, menu, caps                       │   │ src/game/service.py  (FastAPI)  │
 │   resolve.py  the published priority order                    │◄──┤   POST /round  POST /extract    │
 │   auction.py  second-price clearing                           │   │   POST /brief  POST /era        │
 │   kernel.py   Tier 0: shortfall, elasticity rule, insurance,  │   │   GET  /surface                 │
 │               legitimacy                                      │   ├────────────────────────────────┤
 │   adjudicator_client.py  HTTP/subprocess, timeout, fallback   │   │ slurm/scripts/                  │
 │   writeback.py  crisis → era                                  │   │   build_response_surface.py     │
 │ ewg/board/  lanes + chokepoints added to the bundle           │   │   (Tier 2 grid, SLURM)          │
 └──────────────────────────────────────────────────────────────┘   └────────────────────────────────┘
          ▲ scenarios/hormuz-2026/ (frozen EIA/IEA snapshot)              ▲ configs/, data/outputs/
          │ metalsRAG gazetteers (chokepoint_gazetteer.csv, countries)     │ configs/baselines/
```

Four layers, each with one contract.

| Layer | Lives in | Contract | Owns |
|---|---|---|---|
| A. UI | `ewg/server/` | htmx partials, the board's `postMessage` seams, the socket | sealed-order panel, countdown, crisis toggle, dashboards, debrief view |
| B. Engine | `ewg/engine/hormuz/` | the `Ruleset` protocol, the record line | state, orders, resolution, auctions, Tier 0 kernel, legitimacy, write-back, replay |
| C. Adjudicator | `src/game/` here | JSON over HTTP or stdin (section 5) | state to parameters, Tier 1 runs, forwarding, flags, provenance, LLM tools behind checkpoints |
| D. Deep runs | `slurm/` here | the existing run layout under `data/outputs/<run_id>/` | response surface, era-boundary macro, debrief shadow runs at Tier 2 |

Rule of the seam: **Tier 0 is always authoritative for playability.** Layer C adjusts Tier 0
coefficients and supplies the numbers Tier 0 does not model. If Layer C is down, slow or
disagrees with itself beyond a threshold, the round still resolves and the UI says which
numbers are baseline.

---

## 3. Tiers and what runs where

| Tier | When | What runs | Where | Budget | Measured |
|---|---|---|---|---:|---|
| 0 | every round | shortfall accounting, elasticity price rule, auctions, insurance, legitimacy | `ewg` kernel | under 1 s | n/a (not built) |
| 1 | every round | `poles_jrc`, `marketsim`, `fed_oil`, `lngst`, `aisdb`, `ais_project`, `world_helium_model`, `world_fertilizer`, `futures`, `apsim`, `argonne_abm`, `cwatm`, `weap_mena`, `nrel` | adjudicator service | under 5 s end to end | under 1 ms compute; about 0.3 s if spawned as a subprocess |
| 2 | era boundary, between classes | `pycge`, `mpsge_jl` (analytical), and whichever real paths the host has (BKR, GGM, MAgPIE, OpenCGE, NEMS, MAM) | `run_deterministic_baseline.py` with the game as author | minutes to hours | `pycge` and `mpsge_jl` analytical paths run in 0.1 ms; real paths need licences |
| 3 | after the session | shadow runs, counterfactual branches, fidelity audit | `ewg` replay plus Tier 2 | offline | n/a |

Two corrections to the earlier plan follow from the timings. First, `argonne_abm`, `apsim`,
`cwatm` and `weap_mena` can join Tier 1 at no cost, which gives the water and crop cards
model-backed numbers. Second, the analytical `pycge` and `mpsge_jl` are fast enough to run
every round too, but they should stay at Tier 2 for a different reason: they answer in
quarters and years, and showing a GDP number that moves weekly would mislead students. Run
them per round only for the debrief's "what the macro models thought this week" strip, never
for scoring.

---

## 4. The game engine side (`ewg`)

This section is the brief for work in the game repo. It uses the design report's Hormuz
subgame spec as the requirement and maps each mechanic onto the seam `ewg` already has.

### 4.1 State extensions

`GameState` today holds players, seats (one `stockpile_t`), placed events and the log. The
crisis needs the design report's state variables. Add a `CrisisState` dataclass held on
`GameState.crisis` (empty outside a crisis) and a `TeamState` per seat:

| Design report variable | Field | Notes |
|---|---|---|
| Strait transit capacity T | `crisis.strait.transit_capacity` (0 to 1) | of 20.9 mb/d oil and 11.4 Bcf/d LNG |
| Mine density M | `crisis.strait.mine_density` | reduced by mine-clearing orders over rounds |
| War-risk premium R per lane | `crisis.lanes[lane].war_risk_pct` | starts 0.25, cap 10 |
| Bypass utilization | `crisis.bypass.{east_west_mbd, adcop_mbd, other_mbd}` | caps 7.0, 1.8; Yanbu berth cap as a second constraint |
| Stocks per team, drawdown caps | `seats[s].stocks.{oil_mb, lng_bcf, ...}`, `stock_caps` | US 4.4 mb/d after a 2-round lag; shared IEA pool as a pseudo-seat |
| LNG availability | derived each round: Qatar output x T x (1 - damaged share) | not stored |
| Escalation rung | `crisis.escalation_rung` (1 to 7) | moved by the control cell |
| Prices | `crisis.prices.{oil_index, lng_index, ...}` | Tier 0 output, Tier 1 calibrated |
| Macro and legitimacy | `seats[s].macro.{gdp_gap, inflation, unemployment, fiscal_space, fx_stress}`, `seats[s].legitimacy` | 5 to 7 indicators, the design report's list |
| Seed | `game.seed`, per-round RNG derived from `(seed, turn)` | the record must replay bit for bit |

Keep the dataclass style and `to_dict` / `from_dict` the repo uses; the snapshot and the
replay depend on it.

### 4.2 Two clocks

The sandbox has one clock in months. Add `clock.add_days` and let the ruleset own the step:
`HormuzRules.on_turn_end` advances `round_weeks * 7` days while `crisis` is set, and
`era_years * 12` months otherwise. A `start_crisis` action (host or control cell) enters the
weekly clock; `end_crisis` runs write-back (section 8) and returns to the era clock. The clock
partial already reads `turn`, `date` and `phase`; it needs one more label for the mode.

### 4.3 Sealed simultaneous orders

The sandbox applies every action immediately and broadcasts it. Sealed orders need one change
in principle and none in the write path:

- A new action `submit_orders` with payload `{orders: [...], round: n}`, up to three orders
  per the design report, validated against the menu and the team's caps. It is recorded as any
  action is, so the record stays complete.
- The ruleset stores it on `seats[s].pending_orders` and the **partials render other seats'
  pending orders as "submitted" only**. The payload sits server-side in `actions.jsonl`,
  which players never read. Nothing hidden needs encryption; it needs a template rule.
- Resolution happens in `on_turn_end`, when every seated player is ready or the countdown
  ends (the host's `end_turn` already exists). Unsubmitted seats default to hold.
- `legal_actions` returns `submit_orders` while the round is open and `amend_orders` until
  the timer ends; after that only `note`.

### 4.4 The published resolution order

`on_turn_end` runs the design report's seven steps in order and writes one log entry per step
so the record reads as the rulebook:

1. Defensive and security orders (escorts lower R, mine-clearing lowers M over rounds).
2. Coercive orders (sanctions, controls; leakage and coalition multiplier per the toolkit table).
3. Stockpile releases and demand restraint (caps and the 2-round SPR lag).
4. Sealed-bid auctions for bypass slots, spot tankers and LNG cargoes (`auction.py`,
   second-price, pro rata for contracted volumes).
5. Market clearing: Tier 0 kernel, then the adjudicator call to calibrate it (section 5).
6. Build-queue progress (era clock only).
7. Macro and legitimacy updates.

Every step appends `LogEntry` rows with `refs` naming the orders it consumed and the
numbers it produced, so a record entry can light the board exactly as events do today.

### 4.5 Tier 0 kernel (`kernel.py`)

The design report's illustrative rule, made explicit so students can audit it:

```
S      = disrupted_volume(T) - bypass - releases - restraint
dP/P   = S / (|eps_t| * world_demand)          eps_t: time-varying, near -0.06 in week 1
R_lane = clamp(R_prev * (1 + attacks*a - escorts*b - diplomacy*c), 0.25, 10)
```

Tier 1 then supplies `oil_index_pct` from POLES and the shipping multipliers from AISdb and
AIS_project; the kernel records both its own number and the model's, and the board shows the
gap as the uncertainty band. The calibration check in the design report (about 10 mb/d lost
against large releases, Brent up about 60 percent in a month) is the first unit test.

### 4.6 The control cell

A `control` seat with `host_is_umpire` powers: trigger or cancel a crisis, move the
escalation rung, inject news, play Iran, Russia, shipping and insurers, adjudicate a free-text
order (section 7), and adjust a parameter with a logged rationale. Every one of these is an
action through `/ui/g/{id}/act`, so the record holds the control cell's moves beside the
players'. That is the game-side half of the pipeline's "no fully autonomous mode" rule.

---

## 5. The adjudicator (this repo)

### 5.1 Contract

One request per round, one response, JSON both ways. The same payload serves an HTTP
endpoint (`src/game/service.py`, FastAPI, one extra dependency the repo does not have today)
and a stdin/stdout CLI (`python -m src.game.adjudicate`), so a classroom laptop can run the
game with the pipeline checked out beside it and no server.

Request, `POST /round`:

```json
{
  "game_id": "…", "turn": 3, "round": 3, "date": "2026-03-21", "seed": 123456,
  "scenario": "hormuz-2026", "baseline_id": "game_baseline_2025",
  "state": {
    "strait": {"transit_capacity": 0.25, "mine_density": 0.4},
    "lanes": {"hormuz": {"war_risk_pct": 4.5}, "bab_el_mandeb": {"contested": false}},
    "bypass": {"east_west_mbd": 6.2, "adcop_mbd": 1.5, "other_mbd": 0.3},
    "releases": {"total_mbd": 2.0, "helium_reserve_release": true},
    "restraint": {"demand_reduction_share": 0.05},
    "damage": {"qatar_lng_share_lost": 0.17, "ras_laffan_share_lost": 0.17},
    "expectations": {"remaining_closure_weeks": 6},
    "losses": {"tankers_seized_or_hit": 3},
    "prices": {"lng_index": 2.1},
    "macro": {"US": {"policy_rate_pct": 3.75}}
  },
  "previous": {"poles_jrc": {"peak_price_change_pct": 61.0}, "aisdb": {"rerouting_cost_multiplier": 1.18}},
  "models": ["poles_jrc", "lngst", "aisdb", "ais_project", "world_helium_model", "world_fertilizer", "marketsim", "fed_oil"],
  "timeout_s": 5
}
```

Response:

```json
{
  "updates": {"prices.oil_index_pct": 68.4, "lanes.cape.cost_multiplier": 1.19, "cards.helium_gap_pct": 20.8},
  "provenance": [{"target": "prices.oil_index_pct", "candidate_sources": [...], "cross_source_deviation_pct": 0.0,
                  "params": {"supply_loss_mbd": 13.7, "...": "..."}, "param_rules": {"supply_loss_mbd": "expr: …"},
                  "implementation_mode": "analytical_reduction", "model_id": "poles_jrc", "runtime_ms": 0.4}],
  "flags": [{"type": "cross_source_disagreement", "rule": "lanes.cape.cost_multiplier", "deviation_pct": 34.0}],
  "skipped": [{"model_id": "cwatm", "reason": "validation_failed: …"}],
  "meta": {"adjudicator_version": "0.1", "mapping_version": 1, "wall_ms": 12}
}
```

Every number in `updates` traces to a `provenance` row, and every row names the adapter, the
mode it ran in (so a reduction is never mistaken for the upstream model, the repo's dagger
rule), the parameters it saw and the mapping rule that produced each parameter. Failed or
skipped adapters appear in `skipped`, never silently.

### 5.2 Implementation, in order

1. `configs/game_state_to_parameters.yaml` (drafted, this commit): inbound rules per adapter
   and outbound rules per state field, in the forwarding mapping's vocabulary.
2. `src/game/mapping.py`: load the YAML; evaluate `expr` rules with a restricted arithmetic
   evaluator over the request's state (no `eval`); resolve `from_previous_round` against the
   `previous` block; emit `(model_id, params, param_rules)`.
3. `src/game/adjudicator.py`: `adjudicate(request) -> response`. For each requested model:
   `validate_inputs`, `translate_inputs`, `execute`, timed. Then run
   `compute_downstream_inputs` from `src/pipeline/upstream_forwarding.py` against the
   completed results for the **intra-round** rules (shipping into `poles_jrc` is the one that
   exists today) and the outbound rules with `combine: mean`, reusing `_cross_source_deviation_pct`
   and `check_cross_source_disagreement`. Wrap each adapter in a per-model timeout.
4. `src/game/service.py`: FastAPI app with `/round`, `/healthz` and, later, `/extract`,
   `/brief`, `/era`, `/surface`. `python -m src.game.adjudicate` reads one request from stdin.
5. Tests under `tests/test_game/`: the mapping evaluator, a golden round on the analyst
   baseline's Scenario A numbers, the fallback path (a model that raises), the provenance row
   shape, and a determinism test (same request, same response, byte for byte).

### 5.3 What the adjudicator must not do

It never holds game state, never decides an auction, never moves legitimacy, never calls an
LLM on the `/round` path, and never returns a number without a provenance row. Those are Tier 0
or control-cell matters, by design in both documents.

---

## 6. A Hormuz scenario for the board

`ewg`'s scenario is the metalsRAG bundle (facilities, firms, LPM lanes, capital-to-capital
flows) plus `scenario.json`, `members.csv` and `countries.json`. Hormuz is a different kind of
world: commodities, chokepoints as capacity-constrained edges, bypass pipelines, lanes with a
premium. Rather than fork the board, extend the format with optional files the sandbox
scenario leaves out:

| New file | Content | Board behaviour |
|---|---|---|
| `chokepoints.geojson` | Hormuz, Bab el-Mandeb, Suez, Cape, Malacca as Points with `capacity`, `kind`; coordinates from metalsRAG `Company Supply Chain Pipeline/schemas/chokepoint_gazetteer.csv` | drawn as a new layer; a capacity ring sized by T |
| `lanes.geojson` | oil and LNG lanes as LineStrings through chokepoints, with `commodity`, `baseline_volume`, `war_risk_pct` | width by volume, colour by premium (the design report's flow lines) |
| `pipelines.geojson` | East-West, ADCOP, West-East 2, Goreh-Jask, Iraq-Turkey with `capacity_mbd`, `status` | bypass utilization bars in the popup |
| `commodities.json` | the 12 to 20 nodes, baseline prices, short-run elasticities, substitution horizons | the price strip and the Sankey per commodity |
| `teams.json` | the six seats, their secret objective ids, starting stocks and caps, legitimacy thresholds | replaces `seats[]` for crisis scenarios |

`scenario.json` gains `kind: "chokepoint"` (versus the default `"commodity_chain"`), and
`validate` requires the new files only for that kind. `nodes.geojson` keeps the firm and
facility layer, which for Hormuz carries Ras Laffan, Ras Tanura, Yanbu, Fujairah and the SPR
sites, so the existing exposure cone still answers "what does a strike here touch".

The world ships as `scenarios/hormuz-2026/` with the frozen snapshot (Phase H0) and the
honesty lines the board already shows, reworded: every number is dated and sourced, not
synthetic, and the manifest names the as-of date.

---

## 7. The control cell's LLM tools

The pipeline's three LLM modules map one to one onto control-cell powers, each behind the
checkpoint the pipeline already has. None of them is on the weekly resolution path.

| Pipeline module | Game use | Checkpoint | Endpoint |
|---|---|---|---|
| Scenario generation (`src/scenarios/generator.py`) | the era's event deck, conditioned on the current state | the instructor picks (scenario review) | `POST /deck` |
| Parameter extraction (`src/parameters/extractor.py :: extract_parameters_batch`) | a free-text novel order becomes parameter deltas with confidence | the control cell approves, edits or rejects (parameter review) | `POST /extract` |
| Synthesis (`src/synthesis/synthesizer.py`, with `src/synthesis/fidelity.py`) | the round's news brief and NPC Iran statements, numbers only from the round's provenance rows | the control cell approves before release (synthesis review) | `POST /brief` |

Determinism rule: the game stores the approved text verbatim in the record (`refs.text`), so a
replay re-reads it and never regenerates it. The fidelity validator runs on every brief, and a
brief with an unmatched number is blocked, not flagged, because a classroom LLM has no analyst
to catch it later.

---

## 8. Replay, the shadow run and the debrief

`RoomManager.load` already rebuilds a game by replaying `actions.jsonl` through the ruleset.
The counterfactual the design report calls the single most valuable debrief artifact is a
replay with a filter:

```
shadow(game, seat, policy="hold") = replay(actions with seat's submit_orders replaced by hold,
                                           same seed, same logged adjudicator responses)
```

Three requirements fall out. The adjudicator's response for each round must be stored in the
record (as the `refs` of the market-clearing log entry), so a shadow run reuses it instead of
re-running models unless asked. The per-round RNG must derive from `(seed, turn)`, never from
the clock. And the ruleset must be pure given the record, which it is today.

The debrief view (an `ewg` page) then shows, per round: the orders, the resolution steps,
the kernel's number beside the model's with the deviation band from `flags`, the shadow run's
price path, and a CSV export of flows, prices, overrides and the Tier 0 coefficients.
`src/interface/provenance.py :: render_chain_markdown` can render the chain for one number.

---

## 9. Write-back and the era loop

`end_crisis` runs `writeback.py` in `ewg`: capital damage into the build queue as a repair
with a lead-time distribution, stock drawdowns with refill cost at post-crisis prices, the
insurance floor reset, trust and credibility updates for free-riding, lead-time discounts on
bypass builds funded during the crisis. These are game rules, not model outputs.

The era-boundary Tier 2 run then uses this repo's deterministic path with the game as author:
`ewg` writes a baseline YAML in the shape `configs/baselines/hormuz_2026_analyst.yaml` already
has (one `models:` block per adapter, `default` and `by_scenario` keyed by era) and calls
`POST /era` or `run_deterministic_baseline.py --baseline <file> --run-id game_<id>_era<n>`. The
macro adapters' `regional_vars` and `*_by_region` tables come back through
`configs/region_crosswalk.yaml` into per-team GDP gap and fiscal space for the next era. The
run lands under `data/outputs/` and `data/reports/` like any other run, so
`build_coverage_ledger.py` and `run_fidelity_audit.py` work on a game's era run unchanged.

---

## 10. Extending to the other scenarios

Because the adjudicator takes a scenario id and a mapping file, each new crisis in the design
report is a scenario folder in `ewg` plus a mapping block here, not a new engine.

| Scenario | `ewg` scenario | Adjudicator models | New work |
|---|---|---|---|
| Red Sea / Bab el-Mandeb | lanes through Suez and the Cape; Houthi NPC | `aisdb`, `ais_project` (Cape detour is their native case) | a `contested` flag per lane, already in the draft mapping |
| Russia-EU gas 2022 | pipeline gas lanes, storage targets, FSRU builds | `lngst`, `energy_flux_*`, `world_fertilizer` | a storage state variable |
| Critical-mineral export controls | **a metalsRAG export imported with `ewg`'s planned S1 importer**: real company maps, the exposure cone, the LPM lanes | none from this repo at first; later `microMacroModel` traces as a Tier 2 | the licensing mechanic as orders |
| Taiwan blockade | fabs and tool makers as nodes; energy inventory clocks | `simrlfab` (needs its Python 3.6 venv), `argonne_abm`, `world_helium_model` | chip stock variables |
| Data-center grid | load nodes competing for firm power | `nrel` (merit order), `energy_flux_gas_power`, later OSeMOSYS or TEMOA | a grid lane kind |
| Food and fertilizer card | second-order card inside any gas crisis | `world_fertilizer`, `futures`, `apsim` | already in the draft mapping |

---

## 11. Phased roadmap (revised)

Stages are named to continue `ewg`'s `BUILDOUT_PLAN.md` numbering, and each lists the repo it
touches. Durations are estimates for one developer plus the control cell's review.

| Stage | Repo | Scope | Exit criterion | Est. |
|---|---|---|---|---|
| **H0 freeze** | this repo | `configs/game_baseline_2025.yaml`: dated Hormuz snapshot (flows, bypass, stocks, Qatar damage, premiums) cross-checked against EIA and IEA releases; pre-crisis and crisis snapshots | every number has a source and an as-of date; the file validates | 1 to 2 weeks |
| **H1 state and clocks** | `ewg` | `CrisisState`, `TeamState`, seed, `add_days`, `start_crisis` / `end_crisis`, `HormuzRules` skeleton behind `RoomManager(rules_factory=...)` | `tests/test_rules_hormuz.py` walks a game into a crisis and back; replay equals live state | 2 weeks |
| **H2 adjudicator** | this repo | `src/game/{mapping,adjudicator,service}.py`, the CLI, tests, golden round on Scenario A | `POST /round` answers under 50 ms with provenance rows; `python -m src.game.adjudicate` matches it byte for byte | 2 weeks |
| **H3 Tier 0 kernel and sealed orders** | `ewg` | `orders.py`, `resolve.py`, `auction.py`, `kernel.py`, the sealed-order partial, the countdown, the fallback badge, `adjudicator_client.py` | a hot-seat four-round crisis resolves end to end with the adjudicator up, and again with it down | 3 weeks |
| **H4 Hormuz scenario and board** | `ewg` + metalsRAG gazetteers | the chokepoint scenario kind, `scenarios/hormuz-2026/`, lanes and chokepoints on the board, per-team dashboard partial | the board draws T, R and bypass per round from the bundle; the manifest states the as-of date | 2 weeks |
| **H5 control-cell tools** | this repo + `ewg` | `/extract`, `/brief`, `/deck`; the control seat's approval actions; verbatim text in the record | a free-text order round-trips extract, approve, apply; a brief with a fabricated number is blocked | 2 weeks |
| **H6 write-back and era run** | both | `writeback.py`; the game-authored baseline YAML; `/era`; region crosswalk into team dashboards | after a crisis the next era starts with damaged capital, drawn stocks and a Tier 2 GDP gap per team | 2 weeks |
| **H7 debrief and shadow run** | `ewg` | replay filter, debrief page, deviation bands, CSV and notebook export | a shadow run differs from the live run only in the filtered seat's effects | 2 weeks |
| **H8 response surface** | this repo (SLURM) | `build_response_surface.py` over the grid; interpolation; Tier 1 versus surface validation | the surface reproduces live Tier 1 within tolerance on held-out grid points | 1 to 2 weeks, mostly cluster time |
| **H9 playtest** | both | the 90-minute MVP with a small group; tune elasticities, timers, the menu | a logged session plus a debrief that the players could follow | ongoing |

H1 and H2 are independent and can run in parallel. H3 depends on both. H8 can wait until the
macro layer matters, because Tier 1 is already fast.

---

## 12. Risks and open questions (updated)

- **Dependency direction.** `ewg` refuses sibling imports. The HTTP-or-subprocess contract in
  section 5 keeps that rule, at the price of a 0.3 s process start on the subprocess path.
  Decision needed: ship the adjudicator as a service by default, with the CLI for laptops.
- **Python versions.** The pipeline needs Python 3.11 or newer and this host ran it on 3.13;
  `ewg` needs 3.11 or newer; SimRLFab needs its own 3.6 venv and stays a Tier 2 subprocess.
- **Team to region.** The unified taxonomy has no Japan-Korea row, so that team's Tier 2
  macro would read `ROW`. Add `JPN` and `KOR` to `configs/region_crosswalk.yaml` and to the
  macro kernel's regional table before H6.
- **Licences.** Tier 0 and Tier 1 never touch GAMS, CPLEX, CONOPT, GTAP, EViews or Octave. The
  timing table shows exactly which adapters that excludes.
- **Determinism and the LLM.** Only the control-cell endpoints call a model, and the approved
  text is stored verbatim. The `/round` path has no LLM by construction.
- **Fidelity versus playability.** Every adjudicator number carries `implementation_mode`,
  and the board should render the dagger the reports already use, so students see which
  numbers come from a reduction.
- **Scope.** Twelve to twenty commodities in the game, seven commodity systems in the
  pipeline. The uncovered commodities stay on the Tier 0 rule; no new adapters before H9.
- **Ongoing crisis.** The 2026 figures are still being revised. H0 freezes a dated snapshot
  and the manifest says so on the board.
- **Sealed orders versus a public record.** The record holds every order the moment it is
  submitted. Hiding is a rendering rule, which is right for a classroom and wrong for an
  adversarial setting; note it in the rules memo.

---

## 13. Immediate next steps

1. Review this plan and the draft mapping (`configs/game_state_to_parameters.yaml`); decide
   the service-versus-CLI default (section 12, first bullet).
2. In `ewg`: open stage H1 in `BUILDOUT_PLAN.md`; add `CrisisState`, the seed and `add_days`.
3. Here: start H2 with `src/game/mapping.py` and a golden-round test built from the
   `swift_contained` row of `docs/game/fast_adapter_timings.md`.
4. Start H0: pick the as-of date and begin the EIA and IEA cross-check for the snapshot.
5. Add `JPN` and `KOR` to the region crosswalk so the Japan-Korea team has a macro row.
