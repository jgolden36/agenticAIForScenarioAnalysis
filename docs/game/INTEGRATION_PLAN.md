# Integrating the Hormuz Agentic Scenario Pipeline into the Economic War Game

**Working plan, v0.1, 8 November 2026**

## 1. Purpose

This document plans how the existing Hormuz agentic AI codebase and paper (Golden, Indelicato, Varshney, Thornsbury; arXiv 2607.23313) become the adjudication backend for the Hormuz scenario in the economic war game. It covers what to reuse as-is, what to wrap, what to build new, and in what order.

The short version: the pipeline becomes the game's **deep adjudicator**. The game needs a fast, transparent market-clearing engine for every weekly round. The pipeline supplies the calibrated, multi-model, provenance-tracked numbers that engine is anchored to, and it runs in full between sessions and at era boundaries where latency does not matter.

## 2. The two assets and where they overlap

### 2.1 What the pipeline already provides

- A LangGraph orchestrator (`src/pipeline/graph.py`) implementing Algorithm 1: scenario generation, parameter extraction, level-ordered model execution, consistency checks, synthesis, with three mandatory human checkpoints.
- About 30 typed `ModelAdapter` subclasses across water, oil, LNG, helium and semiconductors, fertilizer and agriculture, shipping, and macro. Roughly 14 have real execution paths, 4 ship closed-form analytical MVPs, and the rest are typed stubs.
- A registry (`src/models/registry.py`) and executor that respect analytical-level ordering: combat, commodity, commodity downstream, macro.
- The upstream-to-downstream forwarding layer (`configs/upstream_forwarding_mapping.yaml`, `src/pipeline/upstream_forwarding.py`) that passes computed shocks between models with audit records, `combine` policies, and divergence flags.
- Provenance tracking and cross-scenario comparison (`src/interface/`).
- A crisis description and Schwartz-framework config system (`configs/crisis_descriptions/`, `configs/scenario_frameworks/`) that makes the pipeline portable to other chokepoints.
- Saved reference runs (for example run `20260525_193731` and the backend-comparison batch `20260701_020011`) that can serve as frozen baseline datasets.
- Two design constraints the game should inherit outright: no fabricated quantities, and no fully autonomous mode.

### 2.2 What the game design asks for

From the design report, the Hormuz crisis subgame needs:

- A weekly clock, 4 to 8 rounds, each resolved in about 7 to 8 minutes of wall time.
- State variables: strait transit capacity, mine density, war-risk premium per lane, bypass utilization, stocks per team with drawdown caps, LNG availability, escalation rung.
- Sealed simultaneous orders resolved in a published priority order, with sealed-bid auctions for scarce reroute capacity.
- Market clearing for 12 to 20 commodities, with time-varying elasticities.
- Macro and legitimacy updates per team.
- A control cell that plays Iran, Russia, shipping, and insurers.
- Write-back to the long-run state at crisis end.
- A seeded, replayable log and a counterfactual shadow run for debrief.

### 2.3 Where they fit together

| Game need | Pipeline component | Fit |
|---|---|---|
| Hormuz baseline (flows, bypass, Qatar damage) | Crisis description configs, saved runs | Direct reuse |
| Oil price response to shortfall | POLES-JRC, BKR, Fed oil SVAR, MarketSim | Deep models; analytical MVPs fast enough for in-round use |
| LNG availability and price | LNGST, Energy Flux LNG, GGM | Same |
| Rerouting cost and fleet tie-up | AISdb, AIS_project | Feeds the lane cost and effective-capacity mechanics |
| Second-order effects (fertilizer, helium, chips) | World Fertilizer, futures, World Helium, SimRLFab, Argonne ABM | Becomes the "hidden dependency" and second-order cards |
| Macro indicators per team | MPSGE.jl, NEMS, MAM, OpenCGE, PyCGE | Era-boundary runs; too slow for weekly rounds |
| Control cell adjudication of novel actions | Scenario generation + parameter extraction LLM modules | Reuse the extraction schema to map free-text orders to parameters |
| Debrief provenance | `src/interface/` provenance, override audit records | Direct reuse |
| Confidence display | `src/synthesis/consistency.py` flags | Show model disagreement as uncertainty bands |

Gaps the pipeline does not cover and the game must own: war-risk insurance pricing, critical minerals and chips as traded goods, grain, mine and escort dynamics, auctions, legitimacy, and the escalation ladder. These belong in the game engine, not the pipeline.

## 3. Target architecture

Three layers, each with a clear contract.

### 3.1 Layer A: Game UI (existing)

The map UI Dana has already built. It gains:

- A sealed-order panel per team with a countdown timer.
- A crisis-mode toggle that switches the displayed clock from years to weeks.
- Flow lines, Sankeys, and per-team dashboards driven from a single `GameState` JSON.
- A debrief view that replays rounds and shows the shadow run.

The UI never calls models directly. It reads `GameState` and posts `OrderSet` objects.

### 3.2 Layer B: Game engine (new, thin)

A new service, suggested location `src/game/` inside the pipeline repo or a sibling package that imports it. Responsibilities:

- Hold `GameState`: map, teams, commodity nodes, chokepoint edges, stocks, builds, escalation rung, insurance rates, trust scores.
- Resolve orders in the published priority order.
- Clear sealed-bid auctions.
- Run the **fast market-clearing kernel** each round (Section 4).
- Update macro proxies and legitimacy using simple published formulas.
- Write an append-only, seeded event log.
- Call Layer C when a round or era boundary requires deeper numbers.

### 3.3 Layer C: Hormuz pipeline as adjudicator (existing, wrapped)

The pipeline is invoked in two modes:

- **Fast mode**: individual analytical-MVP adapters called directly through the `ModelAdapter` contract (`validate_inputs`, `translate_inputs`, `execute`, `parse_outputs`). No LLM, no LangGraph graph, sub-second to a few seconds each.
- **Full mode**: the complete Algorithm 1 run, with the control cell occupying the three analyst checkpoints. Used between sessions, at era boundaries, and for the debrief shadow run.

## 4. Solving the latency problem

The pipeline is built for analyst-paced work on a cluster. A classroom round is 7 to 8 minutes, with order entry taking the last 1 to 2. Four approaches, used together.

### 4.1 Tiered adjudication

| Tier | When | What runs | Latency budget |
|---|---|---|---|
| 0 | Every round | Game-side kernel: shortfall accounting, elasticity price rule, auctions, insurance, legitimacy | Under 1 second |
| 1 | Every round | Analytical-MVP adapters for oil, LNG, shipping, fertilizer, helium | Under 30 seconds total |
| 2 | Era boundary or between classes | Full pipeline including macro CGE and real execution paths | Minutes to hours |
| 3 | After session | Debrief shadow run, counterfactual branches | Offline |

Tier 0 is the game's own logic and is always authoritative for playability. Tier 1 adjusts Tier 0 parameters (price multipliers, rerouting cost, effective supply gaps). Tier 2 recalibrates the Tier 0 kernel for the next era.

### 4.2 Precomputed response surfaces

Before the semester, run the full pipeline across a grid of scenario parameters: transit capacity in steps of 10 percent, Qatar damage share, stock release volume, bypass utilization, duration. Store outputs under the existing `data/outputs/<scenario>/<model>/output.json` layout.

At play time, the engine interpolates on that grid. This gives full-model fidelity at lookup speed, and the grid itself is an artifact students can inspect in the debrief.

### 4.3 Reuse the forwarding layer, not the LLM, in-round

The `upstream_forwarding_mapping.yaml` rules already define which upstream outputs feed which downstream inputs. The game engine can apply the same rules with `combine: mean` across whichever Tier 1 adapters ran. The LLM parameter extraction step is skipped in-round because player orders arrive as structured `OrderSet` fields, not prose.

### 4.4 Graceful degradation

The pipeline already preserves the extracted shock when an upstream model fails or is skipped. The game inherits this: if a Tier 1 adapter times out, Tier 0 proceeds with the last known multiplier and logs the fallback. The UI shows a small "model unavailable, using baseline" badge so students never see a stalled round.

## 5. Mapping game state to pipeline inputs and outputs

### 5.1 From `GameState` to crisis parameters

Each round, the engine serializes the state into the same parameter schema the LLM extractor would produce. A draft mapping:

| Game state variable | Pipeline parameter (illustrative) |
|---|---|
| Strait transit capacity T | Hormuz oil and LNG throughput fraction |
| Bypass utilization (East-West, ADCOP) | Bypass volume available |
| Sum of stock releases this round | Reserve release volume and timing |
| Demand restraint orders | Demand reduction percentage |
| Escalation rung | Disruption duration expectation, infrastructure damage flag |
| Mine density M | Per-transit loss probability, feeds AIS rerouting share |
| Qatar damaged share | `world_helium_model` Qatar loss, LNG capacity loss |

This is a new file, suggested `configs/game_state_to_parameters.yaml`, in the same style as the forwarding mapping.

### 5.2 From model outputs to `GameState`

| Pipeline output | Game state update |
|---|---|
| `poles_jrc.peak_price_change_pct` and BKR equivalent | Oil price index (combined via `mean`) |
| LNGST and Energy Flux price outputs | LNG price index, Asian vs European spread |
| AISdb and AIS_project rerouting cost multiplier | Lane cost and effective fleet capacity |
| `world_helium_model.effective_supply_gap_pct` | Helium and chips second-order card trigger |
| Futures fertilizer index | Next-era food output penalty |
| MPSGE.jl regional GDP rows | Per-team GDP gap at era boundary |

Every update carries the pipeline's provenance record so the debrief can show which model produced each number.

### 5.3 Team-to-region mapping

The macro adapters report by region. The game's six teams (US, China, EU, GCC, India, Japan-Korea) need a region crosswalk per adapter. MPSGE.jl regional rows map cleanly; NEMS and MAM are US-only and should feed only the US team's dashboard.

## 6. Reusing the LLM modules for the control cell

The pipeline's LLM modules are useful outside the weekly loop.

- **Scenario generation becomes the event deck.** Run the Schwartz-framework generator against the current `GameState` to produce the next era's crisis candidates. The instructor picks at the analyst checkpoint. This replaces a hand-written deck with a state-conditioned one, and it stays under the no-autonomy rule.
- **Parameter extraction becomes the matrix-game adjudicator.** When a team submits a free-text novel action, the extractor maps it to parameter deltas with confidence annotations. The control cell approves, edits, or rejects at the checkpoint. This is the same human-in-the-loop interrupt the pipeline already uses.
- **Synthesis becomes the news brief.** The synthesis module writes the round's news injection from model outputs, constrained to numbers that exist in the logs. This directly enforces "no fabricated quantities" in the one place a classroom LLM would most tempt them.
- **NPC Iran statements.** Drafted by the same synthesis prompt with an escalation-ladder context, approved by the control cell before release.

The three checkpoints map onto control-cell powers one to one: scenario review is crisis triggering, parameter review is adjudication of orders, synthesis review is news approval.

## 7. Provenance, replay, and the counterfactual shadow run

The design report calls the counterfactual view the single most valuable debrief artifact. The pipeline's provenance layer makes it cheap.

- The engine writes every `OrderSet`, every adapter call, and every RNG draw to the event log with the pipeline's provenance IDs.
- The shadow run replays the log with one team's orders replaced by "hold" (or by the instructor's alternative), reusing the same seed. Differences in price paths and shortages are the counterfactual.
- Consistency flags from `src/synthesis/consistency.py` are rendered as uncertainty bands on price charts. Students see when models disagreed and by how much.
- After the session, export flows, prices, overrides, and the Tier 0 coefficients to CSV and a notebook so students can audit the model.

## 8. Write-back to the long-run game

At crisis end, the engine commits:

- Capital damage (Ras Laffan-style) into the build queue as a multi-year repair.
- Stock drawdowns with refill cost at post-crisis prices.
- Insurance baseline reset to a higher floor.
- Trust and credibility updates for free-riding on escorts or IEA action.
- Lead-time discounts on bypass builds funded during the crisis.

The full pipeline then runs in Tier 2 mode with the post-crisis state as the new baseline, and the macro adapters' outputs set each team's starting GDP gap and fiscal space for the next era.

## 9. Proposed repository changes

Keep the pipeline repo intact and add a game package that depends on it.

```
src/game/
  state.py            GameState, Team, CommodityNode, ChokepointEdge schemas (Pydantic)
  orders.py           OrderSet schema and validation
  resolve.py          priority-order resolution and auction clearing
  kernel.py           Tier 0 market-clearing and legitimacy formulas
  adjudicator.py      wrappers for Tier 1 adapter calls and response-surface lookup
  writeback.py        crisis to era state transfer
  log.py              seeded event log and replay
  api.py              FastAPI or similar endpoints for the UI
configs/
  game_state_to_parameters.yaml
  game_baseline_2025.yaml       frozen EIA/IEA/Comtrade baseline
  response_surface_grid.yaml    grid definition for precomputation
slurm/scripts/
  build_response_surface.py     runs the grid in Tier 2 and stores outputs
tests/test_game/
```

Dependencies to confirm: the UI's current stack and how it consumes JSON, and whether the pipeline's Python environment can host a web service alongside the Python 3.6 SimRLFab venv.

## 10. Phased roadmap

**Phase 0: Freeze the scenario (1 to 2 weeks).**
Pick a dated Hormuz dataset (as of November 2026). Cross-check flows, bypass capacity, stock releases, and Qatar damage against EIA and IEA primary releases. Store as `game_baseline_2025.yaml` plus a pre-crisis and a crisis snapshot.

**Phase 1: Tier 0 kernel and state schema (2 to 3 weeks).**
Build `GameState`, `OrderSet`, resolution order, auctions, insurance, and the elasticity price rule. Wire the existing UI to read `GameState`. Hot-seat play is enough. No pipeline calls yet.

**Phase 2: Tier 1 fast adapters (2 weeks).**
Call the analytical-MVP adapters for oil, LNG, shipping, fertilizer, and helium directly through the adapter contract. Apply forwarding rules with `combine: mean`. Add timeout and fallback badges.

**Phase 3: Response surface (1 to 2 weeks, mostly cluster time).**
Define the grid, run Tier 2 on SLURM, store outputs, implement interpolation. Compare Tier 1 live results against the surface for validation.

**Phase 4: Control-cell LLM tools (2 weeks).**
Wire scenario generation to the event deck, parameter extraction to free-text orders, and synthesis to news briefs, each behind the existing interrupt checkpoints. Add NPC Iran statement drafting.

**Phase 5: Write-back and era loop (2 weeks).**
Implement crisis-to-era transfer and the Tier 2 era-boundary run with macro adapters feeding team dashboards.

**Phase 6: Debrief tooling (2 weeks).**
Replay, shadow run, consistency-flag uncertainty bands, CSV and notebook export.

**Phase 7: Playtest and calibrate.**
Run the 90-minute MVP with a small group. Tune elasticities, timers, and the order menu. Then run the semester version.

## 11. Research tie-ins

- **Paper revision.** The Communications Engineering major revision could note the game as an applied deployment of the framework and a human-in-the-loop evaluation setting. A pedagogy paper on the game is a separate output.
- **Evaluation of the pipeline.** Classroom play generates many human-authored scenario perturbations. That is a natural stress test for the extractor and the consistency checks, and a source of qualitative data on how analysts interpret model disagreement.
- **Quantum equilibrium LDRD.** The escalation ladder and control-cell Iran are placeholders for a strategic solver. Once the game produces logged payoffs across rungs, the equilibrium-set work has a concrete extensive-form game to characterize, and the game can later swap the control cell's Iran for a solver-recommended policy with human override.
- **Portability.** Because the pipeline takes a crisis description config, each added scenario (Red Sea, Taiwan, minerals, data-center grid) becomes a new config plus adapters, not a new engine. The data-center grid scenario can draw on the Energy Flux gas-power model already in the repo.

## 12. Risks and open questions

- **Licensing on the cluster.** GAMS, CPLEX, CONOPT, GTAP, and EViews gate many real execution paths. The game should be designed so that Tier 0 and Tier 1 never depend on licensed software. Tier 2 can use whatever the cluster has that week.
- **Determinism.** Seeded RNG covers dice and adapters. LLM calls are not deterministic. Keep LLM outputs out of the weekly resolution path and log them verbatim where they are used, so replay uses the logged text rather than regenerating it.
- **Fidelity versus playability.** Analytical MVPs are reductions with known limits (for example, Fed oil IRFs are geometric decays, MAM in ingestion mode does not respond to shocks). Document which models are live in each tier so students are not misled about what the numbers mean.
- **Scope creep.** The pipeline covers roughly seven commodity systems. The game design lists 12 to 20 commodities. Keep the uncovered ones on the simple Tier 0 rule and resist adding adapters before playtesting.
- **Ongoing crisis.** The 2026 figures are still being revised. Freeze a dated snapshot and label it as such in the UI.
- **UI stack.** Confirm what the existing map UI is built in and whether it can consume a streamed `GameState` or needs polling.

## 13. Immediate next steps

1. Confirm the UI stack and how it currently loads data.
2. Write `GameState` and `OrderSet` Pydantic schemas and get the UI reading a hand-built `GameState` JSON.
3. List which analytical-MVP adapters run without any external binary or license, and time each one.
4. Draft `game_state_to_parameters.yaml` for oil and LNG only.
5. Pick the frozen dataset date and begin the EIA and IEA cross-check.

## 14. Status (9 November 2026)

This plan is checked in alongside the first implementation pass, which covers Phases 0 to 2:

- **Phase 0, frozen scenario.** `configs/game/hormuz_2026_baseline.yaml` is the dated snapshot
  (as of 8 November 2026). Every value carries a source and a `primary | secondary | designer` tag.
- **Phase 1, Tier 0 kernel.** Lives in the `EconomicWarGames` repo as the `hormuz` ruleset
  (`ewg/engine/hormuz/`) with the scenario folder `scenarios/hormuz-2026/`.
- **Phase 2, Tier 1 fast adapters.** `src/game/` in this repo: `Adjudicator` calls the
  analytical-MVP adapters directly through the adapter contract, applies the forwarding rules in
  stages (shipping first, then oil, LNG, helium, fertilizer, then macro), and serves the result
  over HTTP (`python -m src.game.api`). See `docs/game/ADJUDICATOR.md`.

The game calls the adjudicator once per crisis round from its request handler and records the
answer in the action payload, so a restart replays the game without the service. When the service
is unreachable the game resolves on its Tier 0 rule and shows a fallback badge (Section 4.4).

Phases 3 to 7 are not started.
