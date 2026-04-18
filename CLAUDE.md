# CLAUDE.md — Agentic AI Crisis Analysis Pipeline

## Project Overview

This repository implements the agentic AI orchestration framework described in "Agentic AI Modeling for Rapid Analysis of Chokepoint Crises Along Strategic and Economic Dimensions: A Case Study of the Closure of the Strait of Hormuz" (Golden, Indelicato, Varshney, & Thornsbury).

The system uses **LangGraph** (built on LangChain) to orchestrate a multi-model, multi-scenario analytical pipeline that bridges three persistent gaps in crisis economics: (1) short-run vs. long-run analysis, (2) microeconomic vs. macroeconomic scope, and (3) economic vs. strategic-military assessment. The pipeline coordinates heterogeneous domain models—written in Python, Julia, GAMS, R, AnyLogic, GNU Octave (with Dynare), EViews, Fortran, and Excel—through a structured scenario analysis framework.

**The applied case is the February 2026 closure of the Strait of Hormuz.** The framework is designed to be reusable for future chokepoint crises and comparable geopolitical disruptions.

> **Status (April 2026):** The orchestration scaffolding is feature-complete (LangGraph state graph with `interrupt`-based HITL, `Send`-based parallel fan-out, reducer-based state accumulation, level-ordered execution, cross-model consistency checks, provenance tracking). Roughly **half** of the ~30 domain adapters listed in the inventory below have real execution paths wired to vendored or external model code; the remaining adapters are typed stubs awaiting upstream model integration. The implementation status of each model is annotated in the [Domain Model Inventory](#domain-model-inventory) tables.
>
> **Temporal extension (April 2026):** A second driver, `slurm/jobs/weekly_news_pipeline.job`, demonstrates the framework's value for *rapid re-analysis as new information arrives*. It enumerates calendar weeks across a date range, fetches news + EIA indicators per week, has the LLM rewrite the crisis description, and reruns the full Algorithm 1 pipeline once per week under a unique `HORMUZ_RUN_ID`. See [Module 6: Temporal news-driven re-analysis](#module-6-temporal-news-driven-re-analysis-extension) below.

---

## Core Architectural Principle

The pipeline implements Algorithm 1 from the paper. The pseudocode is:

```
REQUIRE: Crisis description C, domain models {M_1, ..., M_K}, scenario framework F
ENSURE: Synthesized multi-scenario, multi-scale analysis report R

1. Scenario Generation:  {S_1, ..., S_N} ← LLM(C, F)
2. Analyst Review:       {S_1, ..., S_N} ← Validate({S_1, ..., S_N})
3. FOR each scenario S_i:
4.     Parameter Extraction:   θ_i ← LLM(S_i, {M_1, ..., M_K})
5.     Analyst Validation:     θ_i ← Validate(θ_i)
6.     FOR each domain model M_k:
7.         Input Translation:  x_{i,k} ← Translate(θ_i, M_k)
8.         Model Execution:    y_{i,k} ← M_k(x_{i,k})
9.     END FOR
10.    Cross-Model Consistency Check: Flag({y_{i,1}, ..., y_{i,K}})
11.    Macro Aggregation: Feed commodity outputs into macroeconomic models
12.    y_{i,macro} ← M_CGE({y_{i,1}, ..., y_{i,K}})
13. END FOR
14. Synthesis: R ← LLM({y_{i,k}}_{i,k}, {S_i}_i, θ)
15. Analyst Review: Present R with full provenance
```

**Key design constraint:** The framework does NOT replace human analysts. It reorganizes the division of labor. The agent handles operationally intensive but conceptually routine tasks (data formatting, model execution, output collection). The human analyst handles judgment, contextual knowledge, and strategic synthesis. Analyst validation checkpoints are mandatory at steps 2, 5, and 15.

---

## Pipeline Modules

The LangChain pipeline consists of five modules. Each module should be implemented as a self-contained component with clear interfaces.

### Module 1: Scenario Generation

**Purpose:** Generate detailed scenario narratives within a structured scenario framework (Schwartz methodology).

**Inputs:**
- Crisis description (structured text describing the event, timeline, and key actors)
- Scenario framework specification, including:
  - Focal issue
  - Key factors in the local environment
  - Driving forces (STEEP dimensions: Social, Technological, Economic, Environmental, Political)
  - Predetermined elements (locked-in factors that appear in all scenarios)
  - Critical uncertainties (the axes of the scenario matrix)

**Outputs:**
- N scenario narratives (the paper uses N=4), each with:
  - A descriptive label
  - A detailed narrative timeline
  - Explicit statements of all quantitative assumptions
  - Internal consistency verification

**Scenario Matrix for the Hormuz case (2×2):**
The two critical uncertainties are:
1. **Duration and resolution of the Strait closure** (swift 4–6 weeks vs. prolonged 3–6+ months)
2. **Scope of conflict escalation** (contained to Iran–US/Israel axis vs. escalated with broader regional actors/infrastructure destruction)

This yields four scenarios:
- **Scenario A — Swift Resolution, Contained Conflict:** Strait reopened in 4–6 weeks via naval escort + ceasefire. Sharp but transient market disruption.
- **Scenario B — Prolonged Closure, Contained Conflict:** Strait closed 3–6+ months. Iran maintains closure as strategic bargaining chip. Structural adjustment costs.
- **Scenario C — Swift Resolution, Escalated Conflict:** Strait reopened quickly, but broader conflict escalates (desalination attacks, additional Gulf states, other chokepoints like Bab el-Mandeb). Severe humanitarian and infrastructure costs.
- **Scenario D — Prolonged Closure, Escalated Conflict:** Worst case. Sustained closure + broad regional conflict + infrastructure destruction + potential humanitarian catastrophe from desalination loss.

**Implementation notes:**
- The LLM prompt must enforce internal consistency within each narrative.
- Scenarios must be structurally distinct from each other—they are not perturbations around a baseline.
- Output format must be machine-parseable for Module 2 (parameter extraction).
- **Analyst review is mandatory before proceeding.** Build a human-in-the-loop checkpoint here.

### Module 2: Parameter Extraction

**Purpose:** Parse each scenario narrative and extract quantitative assumptions in a structured format compatible with each domain model's input specification.

**Inputs:**
- Validated scenario narratives from Module 1
- Domain model input specifications (schemas defining what each model needs)

**Outputs:**
- For each (scenario, model) pair: a structured parameter set θ_{i,k} containing the quantitative values needed to run that model under that scenario
- Confidence levels for each extracted parameter
- Flags for parameters that required substantial inference (vs. being directly stated in the narrative)

**Parameter categories (from the paper's TODO notes):**
- Disruption duration (weeks/months)
- Oil supply loss (mb/d)
- LNG supply loss (volume and % of global trade)
- Fertilizer price shock (%)
- Helium supply disruption (% of global supply)
- Desalination risk index (scenario-dependent)
- Rerouting cost multiplier
- Insurance premium assumptions
- Infrastructure damage assessments
- Production loss by commodity

**Implementation notes:**
- Each domain model has its own input schema. The extraction module must know what each model requires. This means maintaining a registry of model input specifications.
- Extracted parameters must be presented to the analyst with confidence annotations before being passed to Module 3. **This is a mandatory human-in-the-loop checkpoint.**
- Consider using structured output (e.g., JSON schemas or Pydantic models) to enforce format compliance.

### Module 3: Model Execution

**Purpose:** Dispatch parameterized model runs across the full portfolio of domain models, managing input/output translation between heterogeneous formats.

**Inputs:**
- Validated parameter sets θ_{i,k} from Module 2

**Outputs:**
- Raw model outputs y_{i,k} for each (scenario, model) pair
- Execution metadata (runtime, convergence status, error logs)

**The pipeline processes four analytical levels in sequence:**

1. **Combat-level modeling** → physical disruption parameters
2. **Commodity-level modeling** → price paths, supply shortfalls, rerouting costs
3. **Short-run macroeconomic modeling** → inflation, GDP, interest rates, employment
4. **Long-run macroeconomic/strategic modeling** → structural shifts, trade, investment, strategic balance

Information flows downward: combat outputs feed commodity models, commodity outputs feed short-run macro models, short-run outputs inform long-run CGE calibration. The strategic assessment layer draws from all levels in parallel.

**Implementation notes:**
- Models are heterogeneous: Python, Julia, GAMS, R, AnyLogic, Excel/spreadsheets. The agent must handle input/output translation between these formats.
- Model runs should be parallelized where dependencies allow. Within each analytical level, models can run in parallel. Across levels, they are sequential.
- Each model wrapper must capture stdout/stderr, convergence diagnostics, and timing information.
- Failures in individual model runs should be isolated—a single model failure should not crash the pipeline.

### Module 4: Output Synthesis

**Purpose:** Collect results from all model runs, check for cross-model consistency, and produce a structured summary.

**Inputs:**
- All model outputs y_{i,k}
- All scenario narratives and parameter sets

**Outputs:**
- Structured synthesis organized by: scenario → time horizon → outcome variable
- Cross-model consistency report (flagging cases where models disagree beyond tolerance)
- Anomaly flags for results outside plausible ranges

**Implementation notes:**
- The consistency check is not a formality. Models operating at different scales can produce contradictory implications. The synthesis module must detect and flag these.
- Results should be traceable: every number in the synthesis must link back to a specific model run with specific inputs.
- The LLM is used here to generate narrative summaries, but the underlying quantitative results must not be modified or interpolated by the LLM.

### Module 5: Analyst Interface

**Purpose:** Present synthesized results with full provenance for human review, and support iterative refinement.

**Inputs:**
- Synthesis report from Module 4
- Full provenance chain (scenarios → parameters → model inputs → model outputs → synthesis)

**Outputs:**
- Presentation-ready results
- Analyst modification requests (which feed back into Modules 1–4)

**Required capabilities:**
- Drill-down from any synthesized result to underlying model output
- Ability to modify assumptions and trigger selective model reruns (not full pipeline reruns)
- Side-by-side comparison across scenarios
- Cross-scenario comparison highlighting which outcomes are robust vs. scenario-dependent

### Module 6: Temporal news-driven re-analysis (extension)

**Purpose:** Demonstrate the framework's *value of rapid update* by repeatedly re-running Modules 1–4 as new information arrives. Each iteration treats one calendar week as a "decision point": fetch the past week's news + government indicators, summarise them into an updated crisis brief, and rerun the full pipeline so analysts can compare scenario probabilities and model outputs week over week.

This module is a thin orchestration layer over the existing Modules 1–5; it adds *no* new constraints on the per-model adapters. It is therefore optional — running it requires only a news/EIA API key and the `[news]` extra.

**Inputs:**
- Baseline crisis description (`configs/crisis_descriptions/hormuz_2026.yaml`).
- Source configuration (`configs/news_sources.yaml`) — boolean query and an ordered list of source adapter specs.
- A calendar window (e.g., `2026-02-15` → `2026-04-10`) and a step (default 7 days).

**Outputs (per week):**
- `configs/crisis_descriptions/hormuz_2026_weekly/<date>.yaml` — augmented crisis YAML with a `recent_developments` block plus a cumulative `weekly_briefs` history. The baseline file is never mutated.
- `data/news/<date>/articles.json` — raw articles (provenance).
- `data/news/<date>/report.json` — aggregator FetchReport (per-source success/failure, dedup statistics).
- `data/news/<date>/brief.txt` — plain-text rendering of the structured `WeeklyBrief`, threaded as context into the next week's summariser prompt.
- `data/pipeline_state/weekly_<date>_*` — Module 1–4 state files for that week, isolated by `HORMUZ_RUN_ID="weekly_<YYYYMMDD>"`.
- `data/reports/weekly_<date>_*` — synthesis reports for that week.

**Implementation:**

| Path | Role |
|---|---|
| `src/news/base.py` | `NewsArticle`, `NewsSource` ABC, `NewsSourceError` |
| `src/news/newsdata.py` | NewsData.io adapter (`/archive` with `/latest` fallback) |
| `src/news/gnews.py` | GNews `/api/v4/search` adapter |
| `src/news/newsapi.py` | NewsAPI.org and NewsAPI.ai (Event Registry) adapters |
| `src/news/eia.py` | EIA Open Data API adapter (default series: WTI, Brent, US crude stocks, Henry Hub gas; overridable) |
| `src/news/aggregator.py` | Source registry, fan-out, URL+title-date dedup, FetchReport |
| `src/news/summarizer.py` | LLM chain producing structured `WeeklyBrief` + `write_updated_crisis_yaml` helper |
| `configs/news_sources.yaml` | Crisis metadata, query, source adapter specs |
| `slurm/scripts/build_weekly_brief.py` | CLI: fetch one week → summarise → write per-week YAML |
| `slurm/jobs/weekly_news_pipeline.job` | Generic SLURM driver: enumerate weeks, build briefs, rerun Modules 1–4 |
| `slurm/jobs/empire_ai_alpha_weekly.job` | Production Empire AI Alpha companion to `empire_ai_alpha.job`: same `suny`-partition / `--gpus-per-node` directives, scratch detection, three-tier W&B key resolution, per-week W&B run groups (`weekly_<YYYYMMDD>`) tagged with the parent batch group, vLLM sidecar shared across all weeks |

**Wiring into the existing pipeline:**

The temporal driver re-uses the existing SLURM stage scripts (`run_scenarios.py`, `dispatch_models.py`, `run_parameters.py`, `run_model.py`, `run_synthesis.py`) verbatim. The only change to the existing stages is that `run_scenarios.py` now honours an `HORMUZ_CRISIS_DESCRIPTION` environment variable so each weekly rerun can point Module 1 at its own per-week YAML; everything downstream (parameters, executor, synthesis) is keyed off `HORMUZ_RUN_ID` and is therefore automatically isolated per week.

**Source coverage caveats (documented in `configs/news_sources.yaml`):**
- EIA Open Data: free, full historical depth — the recommended baseline.
- NewsData.io free tier: last 48 hours only; archive endpoint requires paid tier.
- GNews free tier: last 24 hours only; full ranges on Essential / Pro.
- NewsAPI.org Developer plan: 30-day window cap; Business plan for older.
- NewsAPI.ai (Event Registry): best historical coverage of the four article sources; tier-based rate limits.

The aggregator records per-source failures into the FetchReport rather than failing the week, so degraded coverage is auditable rather than silent.

---

## Domain Model Inventory

The following tables list every domain model referenced in the paper, grouped by commodity system. Each model has a typed adapter under `src/models/<system>/` and is registered in `build_default_registry()` (`src/models/registry.py`). The **Status** column reflects what is wired today:

- **Real** — `execute()` runs the actual model end-to-end (no `NotImplementedError`). May be a fully self-contained implementation or a config-aware driver that activates when a YAML config is present in `configs/model_configs/`.
- **Real (config-aware)** — full subprocess / library driver implemented; activates when the matching `<model>.yaml` is present and points at a real binary, dataset, or license. Without config, raises `NotImplementedError` with explicit prerequisites.
- **Config-aware stub** — schemas, validation, translation, and dispatch glue (`GAMSAdapter` / `RAdapter` / `ExcelAdapter` / `JuliaAdapter` / `AnyLogicAdapter` / `SubprocessAdapter`) all wired. Real `execute()` not yet implemented; awaits upstream code or licensed binary.
- **Stub** — typed adapter with input/output schemas only. `execute()` raises `NotImplementedError`; awaits upstream model code.

### Water Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| WEAP / WEAP–MENA | Simulation | Windows COM (SEI WEAP) | `src/models/water/weap.py` | Config-aware stub | Integrated water resource planning; Persian Gulf regional config |
| SahysMod | Simulation | Native CLI (executable) | `src/models/water/sahysmod.py` | **Real** (config-aware) | Spatially distributed agro-hydro-salinity modeling |
| WaterGAP2 | Gridded global | Native binary or HTTP API | `src/models/water/watergap2.py` | Config-aware stub | Global gridded hydrological modeling of infrastructure disruption |
| CWatM | Gridded global | Python subprocess | `src/models/water/cwatm.py` | **Real** (config-aware) | Community-scale water availability under disruption |

### Oil Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| World Equilibrium Model of the Oil Market (Bornstein-Krusell-Rebelo) | Structural GE | GNU Octave + Dynare | `src/models/oil/bornstein_krusell_rebelo.py` | **Real** (config-aware) | Supply disruption analysis in general equilibrium; replication files vendored at `Models/Oil/WorldEquilibriumOilModel/` |
| POLES-JRC | Partial equilibrium | TBD (JRC distribution) | `src/models/oil/poles_jrc.py` | Stub | Detailed global energy supply and demand dynamics |
| MarketSim (BOEM) | Partial equilibrium | Excel/VBA (BOEM) | `src/models/oil/marketsim.py` | Stub | Consumer surplus and energy substitution for disruption scenarios |
| Fed Workhorse Oil Model (Baumeister-Hamilton) | Macro-energy | MATLAB/R (upstream) | `src/models/oil/fed_oil.py` | Stub | US monetary transmission of oil price shocks |

### LNG Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| Energy Flux US Gas Power Build-Out Constraint Model v1.0 | Proprietary calc | Pure Python (default) + Excel via xlwings | `src/models/lng/energy_flux_gas_power.py` | **Real** | US gas-to-power capacity constraints |
| Energy Flux US LNG War Profits Model v1.0 | Proprietary calc | Pure Python (default) + Excel via xlwings | `src/models/lng/energy_flux_lng_profits.py` | **Real** | LNG export revenue under conflict scenarios |
| Global Gas Model (GGM v3.0) | Optimization | GAMS + CPLEX | `src/models/lng/ggm.py` | **Real** (config-aware) | Global gas trade flow optimization; vendored at `Models/LNG/GGM-20190509-open-source-final/` |
| LNG Spreadsheet Tool (LNGST) | Spreadsheet | Excel (openpyxl/xlwings) | `src/models/lng/lngst.py` | Config-aware stub | Scenario-level LNG trade flow simulation |

### Helium & Semiconductor Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| World Helium Model (IFP Énergies Nouvelles) | Market equilibrium | TBD | `src/models/helium/world_helium_model.py` | Stub | Global helium supply-demand equilibrium |
| Argonne Helium ABM | Agent-based | AnyLogic Pro (exported JAR) | `src/models/helium/argonne_abm.py` | Config-aware stub | Contemporary helium market dynamics |
| SimRLFab | RL / SimPy simulation | Python 3.6 venv (SimPy + Tensorforce) | `src/models/helium/simrlfab.py` + `simrlfab_driver.py` | **Real** (config-aware) | Semiconductor fab disruption impacts; vendored at `Models/Helium Market_ Semiconductors/SimRLFab-master/` |

### Fertilizer & Agricultural Trade Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| CAPRI | Partial equilibrium | GAMS (upstream) | `src/models/fertilizer/capri.py` | Stub | Regional agricultural policy impact modeling |
| MAgPIE | Optimization | R orchestration + GAMS (CONOPT) | `src/models/fertilizer/magpie.py` | **Real** (config-aware) | Land-use and agricultural production modeling; vendored at `Models/Fertilizer/magpie-master/` |
| SIMPLE-G | CGE | TBD | `src/models/fertilizer/simple_g.py` | Stub | General equilibrium agricultural trade |
| World Fertilizer Model | Market equilibrium | GAMS | `src/models/fertilizer/world_fertilizer.py` | Stub (`GAMSAdapter` base wired) | Global fertilizer supply-demand dynamics |
| GTAP | CGE | GEMPACK (upstream) | `src/models/fertilizer/gtap.py` | Stub | Global agricultural and commodity trade flows |
| APSIM | Crop simulation | Native (.NET / CLI) | `src/models/fertilizer/apsim.py` | Stub | Physical crop yield response to input disruption |
| Futures forecasting models | Time series | Python (pandas / statsmodels) | `src/models/fertilizer/futures.py` | Stub | Commodity futures price trajectory forecasting |

### Shipping Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| AISdb | Spatial database | Python (sqlite/PostGIS) | `src/models/shipping/aisdb.py` | Stub | AIS vessel tracking data processing and rerouting calibration |
| AIS_project / aisstream | Spatial analysis | Python + WebSocket API | `src/models/shipping/ais_project.py` | Stub | Transit time and fleet utilization under Strait closure (aisstream README at `Models/Shipping/aisstream-main/`) |

### Macroeconomic / General Equilibrium Models
| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| NEMS (EIA AEO2025) | Systems model | Fortran + AIMMS + GAMS + Python | `src/models/macro/nems.py` | **Real** | National energy-economy projections; three modes: `output_ingestion` (default, no install), `subprocess` (full NEMS), `remote` (SLURM). Vendored at `Models/LNG/NEMS-main/` |
| MAM (EIA Macroeconomic Activity Module) | Macro econometric | EViews | `src/models/macro/mam.py` | **Real** | AEO ingestion mode (default) + optional EViews subprocess; AEO2025 docs under `Models/General Equilibrium/EIA/` |
| NREL baseline | Sectoral | TBD | `src/models/macro/nrel.py` | Stub | Electricity sector baseline and disruption impacts |
| MPSGE.jl / GTAP | CGE | Julia (juliacall) | `src/models/macro/mpsge_jl.py` | Config-aware stub | General equilibrium trade and welfare analysis |
| OpenCGE (PSL OG-Core / OG-USA) | CGE | Python (`ogcore`/`ogusa` + Dask) | `src/models/macro/opencge.py` | **Real** | Open-source dynamic OLG CGE; commodity shocks mapped to productivity / capital-quality reforms |
| pycge / cge\_modeling | CGE | Python (`cge-modeling`) | `src/models/macro/pycge.py` | **Real** | SAM-driven Python CGE for sensitivity analysis |
| MIRAGRODEP | CGE | GAMS (CONOPT) | `src/models/macro/miragrodep.py` | **Real** | Multi-region CGE with agricultural-trade linkages; vendored at `Models/General Equilibrium/MIRAGRODEP_v0-1/` |

### Energy Systems Models (long-run electricity / energy mix)

This block extends the original paper inventory. A new commodity system, `CommoditySystem.ENERGY_SYSTEMS`, was introduced to host long-run energy-systems optimisation alongside the macro CGE layer. All three are real and config-aware. See `Models/Energy/README.md` for cloning and solver instructions.

| Model | Type | Platform/Language | Adapter | Status | Role |
|---|---|---|---|---|---|
| OSeMOSYS | LP optimisation | GNU MathProg + GLPK / CBC; otoole CSV pipeline | `src/models/energy/osemosys.py` | **Real** (config-aware) | Open-source long-run energy systems optimisation |
| MESSAGEix | MIP optimisation | IIASA `message-ix` + `ixmp` (Python + Java + GAMS) | `src/models/energy/messageix.py` | **Real** (config-aware) | IIASA integrated assessment / energy-systems framework |
| TEMOA | LP optimisation | Pyomo + CBC (or CPLEX/Gurobi) | `src/models/energy/temoa.py` | **Real** (config-aware) | Tools for Energy Model Optimization & Analysis |

### Implementation status summary

- **Fully wired (real `execute`) — 11 adapters:** Bornstein-Krusell-Rebelo, Energy Flux Gas Power, Energy Flux LNG Profits, NEMS, MAM, OpenCGE, pycge, MIRAGRODEP, OSeMOSYS, MESSAGEix, TEMOA.
- **Real config-aware (activate when YAML is provided) — 5 adapters:** SahysMod, CWatM, GGM, SimRLFab, MAgPIE.
- **Config-aware stubs (dispatch wired, real `execute` pending) — 5 adapters:** WEAP–MENA, WaterGAP2, LNGST, Argonne Helium ABM, MPSGE.jl.
- **Typed stubs (awaiting upstream code) — 13 adapters:** POLES-JRC, MarketSim, Fed Workhorse Oil, World Helium Model, World Fertilizer Model, CAPRI, SIMPLE-G, GTAP, APSIM, Futures, AISdb, AIS\_project, NREL.

The executor (`src/models/executor.py`) catches `NotImplementedError` from stub `execute()` calls, marks the run as `SKIPPED`, and continues — a single missing adapter does **not** halt the pipeline. The synthesis report records which models contributed and which were unavailable for each scenario.

**Note on platforms:** Where the paper left platform/language entries as "—", the columns above record what the integrated or planned implementation actually uses. The platform-specific base classes (`SubprocessAdapter`, `GAMSAdapter`, `RAdapter`, `JuliaAdapter`, `ExcelAdapter`, `AnyLogicAdapter` under `src/models/adapters/`) provide the concrete `execute()` machinery so each domain adapter only has to declare metadata, validate inputs, translate parameters, and parse outputs.

---

## Outcome Variables

The pipeline tracks outcomes along two dimensions: time horizon (short-run vs. long-run) and scope (micro, macro, strategic). All output schemas should accommodate this structure.

### Micro-level outcomes
**Short-run:** Oil, LNG, fertilizer, helium prices; wheat and soybean yields and prices; desalination capacity adequacy
**Long-run:** Regional water sustainability; LNG and electricity market health; US semiconductor industry growth; food security; Arab partner investment (UAE)

### Macro-level outcomes
**Short-run:** Inflation; GDP growth; interest rates and debt service; AI investment
**Long-run:** Structural employment continuity; US fiscal sustainability; unemployment; trade deficit; recession probability

### Strategic-level outcomes
**Short-run:** Combat objective attainment; alliance maintenance; logistics and industrial support; domestic political support; critical infrastructure protection; regional credibility
**Long-run:** Dollar reserve currency status; weapons stockpile adequacy; industrial base health; freedom of navigation; ally rearmament dynamics; nuclear nonproliferation

---

## Project Structure (current)

The repository follows the structure originally proposed in this document, with two notable additions made during implementation:

1. A platform-base layer under `src/models/adapters/` (subprocess, GAMS, R, Julia, Excel, AnyLogic) that the domain adapters inherit from.
2. A new `src/models/energy/` subpackage for the long-run energy-systems optimisation models (OSeMOSYS, MESSAGEix, TEMOA), backed by `CommoditySystem.ENERGY_SYSTEMS`.

The orchestrator is implemented as a **LangGraph `StateGraph`** in `src/pipeline/graph.py`; the original imperative `orchestrator.py` is retained for tests and scripting.

```
hormuz-pipeline/
├── CLAUDE.md                          # This file (design specification)
├── README.md                          # Public-facing project description
├── pyproject.toml                     # Project dependencies and optional extras
├── field_guide_model_integration_v2.md
├── model_integration_plan.md
├── LangChainNextSteps.md
│
├── src/
│   ├── __init__.py
│   │
│   ├── pipeline/                      # Core pipeline orchestration
│   │   ├── __init__.py
│   │   ├── graph.py                   # LangGraph StateGraph implementation of Algorithm 1
│   │   ├── orchestrator.py            # Imperative wrapper retained for tests
│   │   ├── config.py                  # PipelineConfig (LLM, parallelism, timeouts, dirs)
│   │   └── state.py                   # PipelineState container + Pydantic substates
│   │
│   ├── scenarios/                     # Module 1: Scenario Generation
│   │   ├── __init__.py
│   │   ├── generator.py               # LLM-based scenario narrative generation
│   │   ├── framework.py               # Schwartz scenario framework data structures
│   │   ├── prompts.py                 # Prompt templates for scenario generation
│   │   └── schemas.py                 # Pydantic schemas for scenario narratives
│   │
│   ├── parameters/                    # Module 2: Parameter Extraction
│   │   ├── __init__.py
│   │   ├── extractor.py               # LLM-based parameter extraction from narratives
│   │   ├── prompts.py                 # Prompt templates for parameter extraction
│   │   ├── schemas.py                 # Pydantic schemas for extracted parameters
│   │   └── model_specs/               # Input specifications for each domain model
│   │       ├── __init__.py
│   │       ├── water.py
│   │       ├── oil.py
│   │       ├── lng.py
│   │       ├── helium.py
│   │       ├── fertilizer.py
│   │       ├── shipping.py
│   │       └── macro.py
│   │
│   ├── models/                        # Module 3: Model Execution
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract ModelAdapter base + ModelOutput, ResourceRequirements
│   │   ├── registry.py                # build_default_registry(config_dir=...) — reads YAML configs
│   │   ├── executor.py                # Async, level-ordered parallel execution manager
│   │   ├── tools.py                   # LangChain @tool wrappers for adapters
│   │   ├── adapters/                  # Platform-specific base classes (NEW)
│   │   │   ├── __init__.py
│   │   │   ├── subprocess_adapter.py  # Generic JSON-in / JSON-out CLI; SLURM + CUDA support
│   │   │   ├── gams_adapter.py        # GAMS Control + Transfer API
│   │   │   ├── r_adapter.py           # Rscript subprocess (rpy2 optional)
│   │   │   ├── julia_adapter.py       # juliacall in-process; subprocess fallback
│   │   │   ├── excel_adapter.py       # openpyxl headless or xlwings
│   │   │   └── anylogic_adapter.py    # Exported standalone Java JAR via subprocess
│   │   ├── water/                     # Water model adapters
│   │   │   ├── __init__.py
│   │   │   ├── weap.py
│   │   │   ├── sahysmod.py
│   │   │   ├── watergap2.py
│   │   │   └── cwatm.py
│   │   ├── oil/                       # Oil model adapters
│   │   │   ├── __init__.py
│   │   │   ├── bornstein_krusell_rebelo.py
│   │   │   ├── poles_jrc.py
│   │   │   ├── marketsim.py
│   │   │   └── fed_oil.py
│   │   ├── lng/                       # LNG model adapters
│   │   │   ├── __init__.py
│   │   │   ├── energy_flux_gas_power.py
│   │   │   ├── energy_flux_lng_profits.py
│   │   │   ├── ggm.py
│   │   │   └── lngst.py
│   │   ├── helium/                    # Helium & semiconductor model adapters
│   │   │   ├── __init__.py
│   │   │   ├── world_helium_model.py
│   │   │   ├── argonne_abm.py
│   │   │   └── simrlfab.py
│   │   ├── fertilizer/                # Fertilizer & ag trade model adapters
│   │   │   ├── __init__.py
│   │   │   ├── capri.py
│   │   │   ├── magpie.py
│   │   │   ├── simple_g.py
│   │   │   ├── world_fertilizer.py
│   │   │   ├── gtap.py
│   │   │   ├── apsim.py
│   │   │   └── futures.py
│   │   ├── shipping/                  # Shipping model adapters
│   │   │   ├── __init__.py
│   │   │   ├── aisdb.py
│   │   │   └── ais_project.py
│   │   ├── macro/                     # Macroeconomic model adapters
│   │   │   ├── __init__.py
│   │   │   ├── nems.py
│   │   │   ├── nems_shocks.py         # NEMS shock-injection helpers
│   │   │   ├── mam.py                 # EIA Macroeconomic Activity Module (NEW)
│   │   │   ├── nrel.py
│   │   │   ├── mpsge_jl.py
│   │   │   ├── opencge.py
│   │   │   ├── pycge.py
│   │   │   └── miragrodep.py
│   │   └── energy/                    # Energy-systems adapters (NEW)
│   │       ├── __init__.py
│   │       ├── osemosys.py
│   │       ├── messageix.py
│   │       └── temoa.py
│   │
│   ├── synthesis/                     # Module 4: Output Synthesis
│   │   ├── __init__.py
│   │   ├── synthesizer.py             # Cross-model synthesis and consistency checking
│   │   ├── consistency.py             # Cross-model consistency checks and anomaly detection
│   │   ├── prompts.py                 # Prompt templates for narrative synthesis
│   │   └── schemas.py                 # Pydantic schemas for synthesis output
│   │
│   ├── interface/                     # Module 5: Analyst Interface
│   │   ├── __init__.py
│   │   ├── review.py                  # Human-in-the-loop review and validation
│   │   ├── provenance.py              # Full provenance tracking (scenario → params → outputs)
│   │   └── comparison.py              # Cross-scenario comparison utilities
│   │
│   ├── news/                          # Module 6: Temporal news-driven re-analysis (NEW)
│   │   ├── __init__.py
│   │   ├── base.py                    # NewsArticle, NewsSource ABC, NewsSourceError
│   │   ├── aggregator.py              # Source registry, fan-out, URL+title-date dedup
│   │   ├── summarizer.py              # LLM WeeklyBrief chain + write_updated_crisis_yaml
│   │   ├── newsdata.py                # NewsData.io adapter (/archive with /latest fallback)
│   │   ├── gnews.py                   # GNews /api/v4/search adapter
│   │   ├── newsapi.py                 # NewsAPI.org and NewsAPI.ai adapters
│   │   └── eia.py                     # EIA Open Data API adapter
│   │
│   └── common/                        # Shared utilities
│       ├── __init__.py
│       ├── llm.py                     # LLM client configuration (LangChain)
│       ├── types.py                   # Shared type definitions and enums
│       └── logging.py                 # Structured logging
│
├── tests/
│   ├── __init__.py
│   ├── test_scenarios/
│   ├── test_parameters/
│   ├── test_models/
│   ├── test_synthesis/
│   └── test_pipeline/
│
├── configs/                           # Configuration files
│   ├── crisis_descriptions/
│   │   ├── hormuz_2026.yaml           # Structured crisis description (input to Module 1)
│   │   └── hormuz_2026_weekly/        # Auto-populated by Module 6 weekly driver
│   ├── scenario_frameworks/
│   │   └── hormuz_2026.yaml           # Schwartz framework
│   ├── consistency_rules.yaml         # Cross-model tolerance bands for Module 4
│   ├── news_sources.yaml              # Sources + boolean query for Module 6
│   └── model_configs/                 # Per-adapter YAML; presence activates real execute()
│       ├── default.yaml               # Pipeline-wide defaults
│       ├── bornstein_krusell_rebelo.yaml
│       ├── ggm.yaml, ggm_topology.yaml
│       ├── magpie.yaml
│       ├── nems.yaml, mam.yaml
│       ├── miragrodep.yaml, opencge.yaml, pycge.yaml
│       ├── osemosys.yaml, messageix.yaml, temoa.yaml
│       ├── sahysmod.yaml
│       ├── cwatm.yaml.example, watergap2.yaml.example, weap_mena.yaml.example
│
├── Models/                            # Vendored / cloned external model code
│   ├── Oil/WorldEquilibriumOilModel/
│   ├── LNG/GGM-20190509-open-source-final/
│   ├── LNG/NEMS-main/
│   ├── Fertilizer/magpie-master/
│   ├── Helium Market_ Semiconductors/SimRLFab-master/
│   ├── Shipping/aisstream-main/
│   ├── General Equilibrium/MIRAGRODEP_v0-1/
│   ├── General Equilibrium/EIA/       # MAM AEO2025 documentation
│   └── Energy/                        # OSeMOSYS, MESSAGEix, TEMOA (clone via README)
│
└── data/                              # Data directory (gitignored for large files)
    ├── inputs/                        # Raw input data for models
    ├── outputs/                       # Model run outputs
    ├── reports/                       # Generated synthesis reports
    └── news/                          # Module 6 per-week artefacts:
                                       #   <date>/articles.json, report.json, brief.txt
```

The Module 6 SLURM driver lives at `slurm/jobs/weekly_news_pipeline.job` with a per-week CLI helper at `slurm/scripts/build_weekly_brief.py`. Both reuse the existing Module 1–4 stage scripts; the only existing-stage change is that `slurm/scripts/run_scenarios.py` now honours the `HORMUZ_CRISIS_DESCRIPTION` environment variable so each weekly rerun feeds Module 1 its own per-week YAML.

---

## Implementation Guidance for Claude Code

> **Status note:** Phases 1–4 (foundation, scenarios/parameters, model execution layer, synthesis/interface) and Phase 5 (orchestrator) are **complete in scaffolding terms**. The remaining work is per-model: progressively replacing typed stubs with real `execute()` paths as upstream model code becomes available. See the [Implementation status summary](#implementation-status-summary) above.

### Phase 1: Foundation (Build First)

1. **`src/common/types.py`** — Define the core enums and type definitions:
   - `Scenario` enum (A, B, C, D)
   - `AnalyticalLevel` enum (COMBAT, COMMODITY, SHORT_RUN_MACRO, LONG_RUN_MACRO_STRATEGIC)
   - `CommoditySystem` enum (WATER, OIL, LNG, HELIUM_SEMICONDUCTORS, FERTILIZER_AGRICULTURE, SHIPPING, MACROECONOMIC)
   - `TimeHorizon` enum (SHORT_RUN, LONG_RUN)
   - `OutcomeScope` enum (MICRO, MACRO, STRATEGIC)
   - `ConfidenceLevel` enum (HIGH, MEDIUM, LOW) for parameter extraction confidence annotations

2. **`src/common/llm.py`** — LangChain LLM client setup. Use `langchain` with configurable model backend. Do not hardcode a specific provider.

3. **`src/pipeline/state.py`** — Pipeline state container. This object is passed through the pipeline and accumulates results. It must track:
   - Current scenario narratives (with analyst-validated flag)
   - Extracted parameters per (scenario, model) pair (with confidence levels and analyst-validated flag)
   - Model execution results per (scenario, model) pair (with execution metadata)
   - Consistency check results
   - Synthesis outputs
   - Full provenance chain

4. **`src/pipeline/config.py`** — Pipeline configuration: model registry paths, LLM settings, parallelism settings, timeout defaults, output directories.

### Phase 2: Scenario and Parameter Modules

5. **`src/scenarios/framework.py`** — Data structures for the Schwartz scenario framework. Implement `FocalIssue`, `KeyFactor`, `DrivingForce`, `PredeterminedElement`, `CriticalUncertainty`, and `ScenarioMatrix` classes.

6. **`src/scenarios/schemas.py`** — Pydantic models for scenario narratives. A `ScenarioNarrative` must include: label, description, narrative timeline, quantitative assumptions (as structured key-value pairs), and internal consistency notes.

7. **`src/scenarios/generator.py`** — LangChain chain that takes a crisis description + scenario framework and produces N scenario narratives. Use structured output parsing.

8. **`src/parameters/schemas.py`** — Pydantic models for extracted parameters. A `ModelParameterSet` must include: scenario ID, model ID, parameter dict (name → value with units), confidence level per parameter, and extraction notes.

9. **`src/parameters/model_specs/`** — One file per commodity system, each defining the input schema that models in that domain expect. These are the "contracts" that the parameter extraction module must satisfy.

10. **`src/parameters/extractor.py`** — LangChain chain that takes a scenario narrative + a model input specification and extracts the relevant quantitative parameters.

### Phase 3: Model Execution Layer

11. **`src/models/base.py`** — Abstract base class `ModelAdapter` with methods:
    - `validate_inputs(params: ModelParameterSet) -> ValidationResult`
    - `translate_inputs(params: ModelParameterSet) -> Any` (model-native format)
    - `execute(inputs: Any) -> ModelOutput`
    - `parse_outputs(raw: Any) -> ModelOutput`
    - Properties: `model_id`, `commodity_system`, `analytical_level`, `input_schema`, `output_schema`

12. **`src/models/registry.py`** — A registry that maps model IDs to adapter classes. Supports querying by commodity system and analytical level.

13. **`src/models/executor.py`** — Execution manager that:
    - Takes a list of (scenario, model, params) triples
    - Respects analytical-level ordering (combat → commodity → short-run macro → long-run macro)
    - Parallelizes within each level where possible
    - Captures execution metadata and handles failures gracefully (individual model failure does not crash the pipeline)

14. **Model adapter stubs** — Create one stub adapter per model in the inventory. Each stub should:
    - Define its input and output Pydantic schemas
    - Implement `validate_inputs` with real validation logic
    - Implement `execute` as a placeholder that raises `NotImplementedError` with a descriptive message
    - Document what the real implementation will need (binary path, data files, API endpoints, etc.)

### Phase 4: Synthesis and Interface

15. **`src/synthesis/consistency.py`** — Cross-model consistency checking. Define what "consistency" means for each pair of models that should agree (e.g., oil price from POLES-JRC vs. Bornstein-Krusell-Rebelo should be in the same range). Flag contradictions.

16. **`src/synthesis/synthesizer.py`** — LangChain chain that takes all model outputs + scenario narratives and produces a structured synthesis organized by scenario → time horizon → outcome variable. The LLM generates narrative summaries, but quantitative results must pass through unmodified.

17. **`src/interface/provenance.py`** — Provenance tracker that can trace any synthesized result back through: synthesis → model output → model input → extracted parameter → scenario narrative.

18. **`src/interface/review.py`** — Human-in-the-loop review interface. At minimum, this should support CLI-based review with approve/reject/modify actions. Design the interface contract so a web UI can be swapped in later.

### Phase 5: Orchestrator

19. **`src/pipeline/graph.py`** (and the imperative wrapper `orchestrator.py`) — The main pipeline that chains Modules 1–5 together following Algorithm 1. Implemented as a **LangGraph `StateGraph`** (chosen over a plain `RunnableSequence` for native HITL, partial rerun, and parallel fan-out support). The graph:
    - Uses `langgraph.types.interrupt()` for the three mandatory analyst checkpoints (post-scenario generation, post-parameter extraction, post-synthesis), with `Command(resume=...)` to continue.
    - Uses the `Send` API for dynamic fan-out across (scenario × model) pairs at each analytical level.
    - Uses TypedDict reducers (`Annotated[list, operator.add]`) to accumulate parallel model outputs without losing entries.
    - Honors per-adapter `ResourceRequirements` (GPU, CPU, process isolation, SLURM) for cluster scheduling.
    - Supports partial reruns (e.g., rerun only Scenario B with modified parameters) via the LangGraph checkpointer (SqliteSaver for development; PostgresSaver/RedisSaver in production).
    - Logs every step with timestamps and provenance metadata via `src/interface/provenance.py`.

---

## Critical Design Constraints

1. **Human-in-the-loop is not optional.** The pipeline must pause for analyst validation at three points: after scenario generation (step 2), after parameter extraction (step 5), and after synthesis (step 15). Do not design a fully autonomous pipeline.

2. **Provenance is mandatory.** Every quantitative result in the final synthesis must be traceable to a specific model run with specific inputs derived from a specific scenario. No "orphan" numbers.

3. **The LLM must not fabricate quantitative results.** The LLM generates narratives, extracts parameters, and synthesizes text summaries. It does NOT generate, interpolate, or modify quantitative model outputs. All numbers in the final report come from domain model runs.

4. **Graceful degradation.** If a model fails, the pipeline continues with remaining models. The synthesis must note which models succeeded and which failed. No silent omissions.

5. **Heterogeneous model support.** The adapter pattern must accommodate models in Python, Julia (via subprocess or PyJulia), GAMS (via CLI), R (via subprocess or rpy2), AnyLogic (via CLI export), and Excel (via openpyxl or COM automation). Do not assume all models are Python-native.

6. **Cross-model consistency checking is substantive.** This is not a logging step. The consistency module must implement real checks: e.g., if POLES-JRC predicts oil at $X and Bornstein-Krusell-Rebelo predicts $Y, and |X-Y| exceeds a configurable tolerance, this is flagged.

7. **Configuration over hardcoding.** Model paths, LLM settings, parallelism levels, output directories, and tolerance thresholds should all be configurable via YAML files or environment variables.

---

## Dependencies

Core dependencies (declared in `pyproject.toml`):
- `langchain` and `langchain-core` — LLM interface and tooling
- `langgraph` — Stateful graph orchestration (the pipeline backbone)
- `pydantic` — Schema definitions and validation
- `pyyaml` — Configuration files
- `asyncio` (stdlib) — Parallel model execution

Domain-model integrations are gated behind **optional extras** so users only install what they need (`pip install -e ".[<extra>]"`):
- `[adapters]` — `openpyxl`, `pandas` (baseline data interchange)
- `[julia]` — `juliacall` (MPSGE.jl)
- `[gams]` — `gamsapi[transfer]` (GGM, MIRAGRODEP, World Fertilizer, ...)
- `[excel]` — `openpyxl` + `xlwings` (Energy Flux models, LNGST, MarketSim)
- `[r]` — `rpy2` (MAgPIE in-process mode; subprocess fallback always available)
- `[macro]` — `ogcore`, `ogusa`, `dask[distributed]`, `cge-modeling` (OpenCGE, pycge)
- `[water]` — `netCDF4`, `xarray` (CWatM / WaterGAP2 outputs)
- `[energy]` — `otoole`, `message-ix`, `ixmp`, `temoa-energysystem`, `pyomo` (OSeMOSYS, MESSAGEix, TEMOA)
- `[news]` — `requests` (NewsData.io / GNews / NewsAPI / EIA adapters used by Module 6)
- `[dev]` — `pytest`, `pytest-asyncio`

Non-Python prerequisites required by specific adapters (not pip-installable): GAMS + CPLEX/CONOPT, GNU Octave + Dynare, GLPK / CBC, R, JDK 8+, Microsoft Excel, AnyLogic Professional, EViews 13+. These are documented per-model under `Models/*/README.md` (notably `Models/Energy/README.md`) and in the `configs/model_configs/*.yaml` files.

---

## Testing Strategy

- **Unit tests** for each module in isolation (schema validation, prompt construction, parameter extraction from known narratives)
- **Integration tests** using mock model adapters that return known outputs, verifying that the full pipeline correctly threads data from scenarios through to synthesis
- **Consistency check tests** using deliberately contradictory mock outputs to verify that the consistency module catches them
- **Provenance tests** verifying that every result in a mock synthesis traces back to a specific model run

---

## What This Document Does NOT Cover

- The actual implementation of any domain model. This pipeline is the orchestration layer. Domain models are external and are accessed through the adapter interface. Vendored models live under `Models/`; see the per-system READMEs (e.g., `Models/Energy/README.md`) for cloning, solver, and license details.
- The specific prompt engineering for scenario generation and parameter extraction. The `prompts.py` files contain initial templates that are refined iteratively based on output quality.
- The web-based analyst interface. The initial implementation uses CLI-based review (`src/interface/review.py`). A web UI is a future extension.
- Deployment, CI/CD, or cloud infrastructure. This is a research codebase.

## Companion documents

- **`README.md`** — public-facing project overview, quick install, current model implementation status (kept in sync with the inventory tables above), and end-user documentation for the Module 6 temporal weekly driver.
- **`field_guide_model_integration_v2.md`** — practical 2026 reference for each execution environment (Julia, GAMS, Excel, AnyLogic, R, generic subprocess) with current API details and gotchas.
- **`model_integration_plan.md`** — historical sequencing notes for the `Models/` ↔ `src/models/` integration (GGM first, then MAgPIE, then NEMS).
- **`LangChainNextSteps.md`** — LangGraph 1.x patterns referenced by the orchestrator (state schemas, supervisors, HITL, Send API, error recovery).
