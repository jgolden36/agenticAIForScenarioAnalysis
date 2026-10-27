# Agentic AI for Scenario Analysis — Hormuz Pipeline

A LangGraph-based agentic AI orchestration framework for multi-model, multi-scenario crisis analysis, built around the case study of the February 2026 closure of the Strait of Hormuz.

This repository implements the framework described in *"Agentic AI Modeling for Rapid Analysis of Chokepoint Crises Along Strategic and Economic Dimensions: A Case Study of the Closure of the Strait of Hormuz"* (Golden, Indelicato, Varshney, & Thornsbury). It coordinates ~30 heterogeneous domain models — written in Python, Julia, GAMS, R, AnyLogic, Octave, EViews, Fortran, and Excel — through a structured Schwartz-style scenario analysis with mandatory human-in-the-loop checkpoints.

> **Status (April 2026):** The orchestration layer is feature-complete. ~14 of ~30 model adapters have real execution paths wired to vendored or external model code; an additional 4 (POLES-JRC, World Helium Model, Futures, CWatM analytical fallback) ship a closed-form analytical-MVP execution path so every commodity system except SHIPPING has at least one runnable model on the cluster MVP; the remaining ~12 are typed stubs awaiting upstream integration. See [Model implementation status](#model-implementation-status) below.

---

## Table of contents

1. [What this framework does](#what-this-framework-does)
2. [Pipeline architecture](#pipeline-architecture)
3. [Model implementation status](#model-implementation-status)
4. [Repository layout](#repository-layout)
5. [Installation](#installation)
6. [Running the pipeline](#running-the-pipeline)
7. [Temporal re-analysis from weekly news](#temporal-re-analysis-from-weekly-news)
8. [Configuration](#configuration)
9. [Further reading](#further-reading)

---

## What this framework does

The pipeline implements **Algorithm 1** from the paper:

1. Generate `N` scenario narratives with an LLM, conditioned on a Schwartz scenario framework.
2. **Analyst checkpoint** — review and validate scenarios.
3. For each scenario, extract structured per-model parameters with the LLM.
4. **Analyst checkpoint** — review and validate extracted parameters.
5. Execute each domain model on each scenario, respecting analytical-level dependencies (combat → commodity → short-run macro → long-run macro / strategic).
6. Run cross-model consistency checks; flag disagreements outside configurable tolerances.
7. Synthesize a structured, scenario-by-scenario report with full provenance.
8. **Analyst checkpoint** — review and finalise the synthesis.

Two non-negotiable design constraints govern the pipeline:

- **No fabricated quantities.** The LLM generates narratives, extracts parameters, and writes prose summaries. Numerical model outputs are passed through unmodified — every number in the synthesis is traceable to a specific model run with specific inputs.
- **Human-in-the-loop is mandatory.** The pipeline pauses (`langgraph.types.interrupt`) at three checkpoints. There is no fully autonomous mode.

The applied case is the 2026 Hormuz closure, but the framework is reusable: swap in a different crisis description (`configs/crisis_descriptions/`) and scenario framework (`configs/scenario_frameworks/`) to apply it to other chokepoint or commodity-disruption crises.

---

## Pipeline architecture

The orchestrator is built on **LangGraph 1.1** (`StateGraph` + `Send` for fan-out + `interrupt` for HITL + reducer-based state accumulation), not raw LangChain runnables. Five logical modules:

| Module | Code | Role |
|---|---|---|
| 1. Scenario generation | `src/scenarios/` | LLM produces structured scenario narratives within a Schwartz framework |
| 2. Parameter extraction | `src/parameters/` | LLM maps each narrative to per-model parameter sets with confidence annotations |
| 3. Model execution | `src/models/` | `ModelExecutor` dispatches model adapters with level-ordered parallelism |
| 4. Synthesis | `src/synthesis/` | Cross-model consistency checks + LLM-generated narrative summary |
| 5. Analyst interface | `src/interface/` | Provenance tracking, cross-scenario comparison, CLI review |

The graph itself lives in `src/pipeline/graph.py`; a thin imperative wrapper in `src/pipeline/orchestrator.py` is retained for tests and scripting.

### The `ModelAdapter` contract

Every domain model is wrapped by a `ModelAdapter` subclass (`src/models/base.py`). Concrete adapters declare `model_id`, `commodity_system`, `analytical_level`, `description`, and `resource_requirements` (CPU/GPU hints), and implement `validate_inputs`, `translate_inputs`, `execute`, and `parse_outputs`. Six platform-specific bases handle the heterogeneous runtime mix:

| Base class | File | Targets |
|---|---|---|
| `SubprocessAdapter` | `src/models/adapters/subprocess_adapter.py` | Generic JSON-in / JSON-out CLI invocation, with SLURM `srun` and CUDA device support |
| `GAMSAdapter` | `src/models/adapters/gams_adapter.py` | GAMS Control + Transfer API |
| `RAdapter` | `src/models/adapters/r_adapter.py` | `Rscript` subprocess (rpy2 optional) |
| `JuliaAdapter` | `src/models/adapters/julia_adapter.py` | `juliacall` in-process; subprocess fallback |
| `ExcelAdapter` | `src/models/adapters/excel_adapter.py` | `openpyxl` (headless) or `xlwings` (Excel COM) |
| `AnyLogicAdapter` | `src/models/adapters/anylogic_adapter.py` | Exported standalone Java (JAR) via subprocess |

The executor (`src/models/executor.py`) respects analytical-level ordering, parallelises within levels, isolates failures, honours per-adapter `ResourceRequirements` for GPU/CPU/SLURM scheduling, and applies the step-11 feed-forward barrier between levels (see below), so the imperative orchestrator path communicates model outputs downstream exactly like the LangGraph and SLURM runtimes.

### Upstream-to-downstream feed-forward (Algorithm 1, step 11)

Module 3 is split in three phases so downstream models (semiconductor / helium-ABM downstream of the helium model, then the macroeconomic CGE / NEMS layer downstream of every commodity result) solve with shocks computed by upstream domain models rather than by the LLM extracting them from the scenario narrative:

1. **Phase A (commodity)** — combat + commodity adapters (POLES-JRC, BKR, GGM, Energy Flux LNG, World Helium Model, futures, ...) execute first and write their outputs to `data/outputs/<scenario>/<model>/output.json`.
2. **Barrier merge #1 → Phase A2 (commodity_downstream)** — `src/pipeline/upstream_forwarding.py` reads the completed commodity outputs and applies the rules in `configs/upstream_forwarding_mapping.yaml` whose targets sit at `AnalyticalLevel.COMMODITY_DOWNSTREAM`. Today this forwards `world_helium_model.effective_supply_gap_pct` into `simrlfab.helium_supply_reduction_pct` and `argonne_abm.supply_shock_pct`, plus `world_helium_model.disruption_duration_months` into both adapters' `disruption_duration_months`. SimRLFab and Argonne ABM then execute with those merged inputs, so the semiconductor-fab and helium-market-ABM simulations consume the helium model's *computed* sectoral shortfall instead of an LLM estimate. Categorical (`neon_supply_status`) and calibration (`fab_utilization_baseline`, `demand_response_elasticity`) parameters stay on whatever the LLM extracted.
3. **Barrier merge #2 → Phase B (macro)** — the same machinery is re-invoked, this time with macro models (NEMS, MAM, OpenCGE, PyCGE, MPSGE.jl, MIRAGRODEP) as the targets. It pulls outputs from BOTH the commodity and commodity_downstream phases, so e.g. `oil_price_shock_pct` ← `poles_jrc.peak_price_change_pct`; `commodity_price_shocks.helium` ← `world_helium_model.price_change_pct`; `commodity_price_shocks.fertilizer` ← mean of `futures.peak_price_index_per_commodity[urea, dap, potash]`. Macro adapters then execute with the merged parameters.

**Multi-source consensus (`combine` policies).** Each forwarding rule may declare `combine: first | mean | median | weighted_mean`. `first` (default) keeps the historical ordered-fallback semantics; the aggregating policies average every upstream source that resolved, so a downstream model consumes a consensus when several upstream models compute the same quantity (today: AISdb + AIS_project rerouting-cost multipliers feed `poles_jrc.rerouting_cost_multiplier` and `mpsge_jl.trade_disruption_spec.trade_cost_multiplier` via `combine: mean`). Per-source `weight:` entries drive `weighted_mean`. Every resolving candidate is recorded on the override audit record (`candidate_sources`), along with the max pairwise deviation between candidates (`cross_source_deviation_pct`).

`src/synthesis/consistency.py` walks each downstream result's `outputs["_upstream_overrides"]` and automatically flags (1) any LLM-vs-upstream divergence above `defaults.llm_vs_upstream_warn_threshold_pct` (default 50%) and (2) any disagreement *between upstream sources of the same rule* above `defaults.cross_source_warn_threshold_pct` (default 30%) as `ConsistencyFlag` entries. The synthesis prompt includes an explicit "Upstream-to-Macro Overrides" section so the report attributes downstream findings to the upstream calculation.

The same merge logic is invoked from all three runtimes: the local LangGraph orchestrator (the `merge_upstream_into_commodity_downstream_params` and `merge_upstream_into_macro_params` nodes between `execute_commodity_model` → `execute_commodity_downstream_model` → `execute_macro_model` in `src/pipeline/graph.py`), the imperative orchestrator (`ModelExecutor.execute_all` applies the barrier between analytical levels; pass `apply_upstream_forwarding=False` for ablation runs), and the SLURM cluster pipeline (`slurm/scripts/dispatch_models.py --tier {commodity_downstream,macro}`, called between Stage 3a, Stage 3a-2, and Stage 3b in `slurm/jobs/*.job` and `slurm/submit_pipeline.sh`). When an upstream model is FAILED / SKIPPED / not in the registry, the LLM-extracted shock is preserved (graceful degradation). The legacy filename `configs/upstream_to_macro_mapping.yaml` and the legacy module `src/pipeline/upstream_to_macro.py` are kept as backwards-compat shims.

---

## Model implementation status

The CLAUDE.md inventory lists ~30 domain models. Each has a typed adapter, a Pydantic input/output schema, and is registered in `build_default_registry()` (`src/models/registry.py`). Adapters fall into three buckets:

- **Real execution path wired** — adapter calls the vendored or external model code and returns model outputs end-to-end. Some additionally accept a YAML config to point at the real binary/data; those run as functional pure-Python implementations or stubs in its absence.
- **Config-aware stub** — full `validate_inputs` / `translate_inputs` / `parse_outputs` plus a real `execute` path that activates when a YAML config is provided. Without config, raises `NotImplementedError` with a precise list of the prerequisites (binary, data, license).
- **Typed stub** — schemas and metadata complete; `execute()` raises `NotImplementedError` because the upstream model code is not yet available in this repository.

The tables between the markers below are generated from `src/models/implementation_info.py` by `python slurm/scripts/build_model_inventory.py --update-readme`; `tests/test_docs/test_readme_inventory_sync.py` fails when they drift. The status vocabulary is defined in that module's docstring. "Analytical MVP" means a closed-form, literature-calibrated reduction of the named model that runs inside the adapter; the run-specific inventory marks every cell that used one.

<!-- inventory:start -->
### Water

| Model | Adapter | Status | Notes |
|---|---|---|---|
| CWatM (IIASA Community Water Model) | `src/models/water/cwatm.py` | Real (analytical MVP) + config-aware full path | Python subprocess (run_cwatm.py + NetCDF forcing) for the full model / pure Python reduction. Reduction has no spatial grid, routing or groundwater; responds only through supply_infrastructure_status and demand change |
| SahysMod (ILRI spatial agro-hydro-salinity model) | `src/models/water/sahysmod.py` | Real (config-aware) | Native Windows console executable (Models/Water/SahysMod/SahysMod.exe) via subprocess. Requires the Windows binary (or Wine) and a baseline .inp deck; no analytical fallback |
| WaterGAP2 (global gridded hydrology, Goethe University Frankfurt) | `src/models/water/watergap2.py` | Config-aware stub | C++ binary (compile from vendored sources) or HTTP API. No compiled binary or climate forcing data vendored; execute() raises NotImplementedError |
| WEAP-MENA (SEI Water Evaluation And Planning, Persian Gulf configuration) | `src/models/water/weap.py` | Real (analytical MVP) + config-aware full path | Windows COM automation of SEI WEAP (full) / pure Python (reduction). No hydrological routing, allocation priorities or storage; country-level dependence weights only |

### Oil

| Model | Adapter | Status | Notes |
|---|---|---|---|
| Bornstein-Krusell-Rebelo World Equilibrium Model of the Oil Market | `src/models/oil/bornstein_krusell_rebelo.py` | Real | GNU Octave + Dynare driving the vendored MATLAB/Dynare replication files. Requires Octave 6+ and Dynare 4.6+ and the replication .mod files; failed on the 2026-05-04 cluster run with a missing .mod path |
| Baumeister-Hamilton oil-shock SVAR (2019 AER), reduced form | `src/models/oil/fed_oil.py` | Real (analytical MVP) | Pure Python (reduction); upstream MATLAB/R SVAR code not run. Not an estimated SVAR: IRFs are geometric decays of kernel peaks with fixed multipliers, so CPI/FFR and GDP/unemployment ratios are identities, not independent results |
| MarketSim (BOEM consumer-surplus and energy-substitution model) | `src/models/oil/marketsim.py` | Real (analytical MVP) | Pure Python (reduction); BOEM Excel/VBA codebase not available. US-only, two carriers, no regional detail; heuristic 60% producer-capture split |
| POLES-JRC (JRC Prospective Outlook on Long-term Energy Systems) | `src/models/oil/poles_jrc.py` | Real (analytical MVP) | Pure Python (reduction); JRC distribution not available. No regional energy balances, fuel substitution across carriers, or inventory dynamics; single global Brent price |

### LNG

| Model | Adapter | Status | Notes |
|---|---|---|---|
| Energy Flux US Gas Power Build-Out Constraint Model v1.0 | `src/models/lng/energy_flux_gas_power.py` | Real | Pure-Python re-implementation of the Excel workbook (default) or xlwings against the workbook. US-only engineering model with no price response; crisis enters only through the build-scenario and LNG inputs |
| Energy Flux US LNG War Profits Model v1.0 | `src/models/lng/energy_flux_lng_profits.py` | Real | Pure-Python re-implementation of the Excel workbook (default) or xlwings against the workbook. Requires a 12-row price schedule or TTF/JKM/HH peak prices; failed input validation on the 2026-05-04 run because the extractor supplied neither |
| Global Gas Model v3.0 (NTNU / DIW Berlin) | `src/models/lng/ggm.py` | Real (config-aware) | GAMS + CPLEX (QCP) via subprocess on a copied model tree. Needs GAMS + CPLEX licence and gamsapi; skipped on the cluster for lack of a GGMConfig / GAMS |
| LNG Spreadsheet Tool (LNGST) | `src/models/lng/lngst.py` | Real (analytical MVP) + config-aware full path | Pure Python (reduction) / Excel workbook via openpyxl or xlwings (full). No trade re-allocation matrix or regional supply gaps in the reduction; single elasticity for all buyers |

### Helium & Semiconductors

| Model | Adapter | Status | Notes |
|---|---|---|---|
| Argonne Helium Agent-Based Model (AnyLogic) | `src/models/helium/argonne_abm.py` | Real (analytical MVP) + config-aware full path | Pure Python (20 stochastic replications) / exported AnyLogic JAR via subprocess (full). No agent heterogeneity, hoarding or contract dynamics; noise is parametric, not emergent |
| SimRLFab (SimPy + Tensorforce semiconductor fab simulator) | `src/models/helium/simrlfab.py` | Real (config-aware) | Python 3.6 virtual environment subprocess driving the vendored SimRLFab repository. Needs the Python 3.6 venv with pinned SimPy/Tensorforce; failed validation on early 2026 runs for out-of-range fab_utilization_baseline |
| World Helium Model (IFP Energies Nouvelles) | `src/models/helium/world_helium_model.py` | Real (analytical MVP) | Pure Python (reduction); IFP EN model not available. No storage, liquefaction or regional trade; effective_supply_gap_pct is zero whenever reserve release covers the Qatar loss |

### Fertilizer & Agriculture

| Model | Adapter | Status | Notes |
|---|---|---|---|
| APSIM Next Generation (crop simulation) | `src/models/fertilizer/apsim.py` | Real (analytical MVP) | Pure Python (reduction); APSIM NG .NET CLI not run. No soil, climate or management detail; crop coefficients are literature-level, not site-calibrated |
| CAPRI (Common Agricultural Policy Regionalised Impact) | `src/models/fertilizer/capri.py` | Stub | GAMS (upstream). No execute path; requires the CAPRI GAMS repository and CAPREG database |
| Commodity futures forward-curve model | `src/models/fertilizer/futures.py` | Real (analytical MVP) | Pure Python (reduction); no statsmodels dependency. Deterministic decay from a single initial shock; no term structure, volatility or regime switching |
| GTAP (Global Trade Analysis Project CGE) | `src/models/fertilizer/gtap.py` | Stub | GEMPACK (RunGTAP / FlexGTAP), upstream. No execute path; requires a licensed GTAP database and GEMPACK |
| MAgPIE (PIK land-use and agricultural production model) | `src/models/fertilizer/magpie.py` | Real (config-aware) | R orchestration (Rscript start.R + bridge script) + GAMS/CONOPT. Needs R >= 4.3, GAMS >= 50 with CONOPT and the MAgPIE input data; skipped on the cluster (source tree not found) |
| SIMPLE-G (global gridded agricultural CGE, Purdue) | `src/models/fertilizer/simple_g.py` | Stub | GAMS (upstream). No execute path; requires the SIMPLE-G GAMS code and base data |
| World Fertilizer Model (global N/P/K market equilibrium) | `src/models/fertilizer/world_fertilizer.py` | Real (analytical MVP) + config-aware full path | Pure Python (reduction) / GAMS via GAMSAdapter (full). No supply response, inventories or regional trade matrix; trade-flow diversion is a heuristic (8% per 10% ME loss) |

### Shipping

| Model | Adapter | Status | Notes |
|---|---|---|---|
| AIS_project / aisstream (transit time and fleet utilisation) | `src/models/shipping/ais_project.py` | Real (analytical MVP) | Pure Python (reduction); aisstream WebSocket feed not wired. Single detour geometry and fleet-average round trip; no vessel-type breakdown |
| AISdb (AIS vessel-track database and rerouting calibration) | `src/models/shipping/aisdb.py` | Real (analytical MVP) | Pure Python (reduction); AISdb PostgreSQL/SQLite backend not wired. No vessel tracks, port congestion or canal capacity; worst-case route is assumed |

### Macroeconomic / General Equilibrium

| Model | Adapter | Status | Notes |
|---|---|---|---|
| MAM (EIA Macroeconomic Activity Module, AEO2025) | `src/models/macro/mam.py` | Real (published-output ingestion) + optional full path | aeo_ingestion (AEO2025 Tables 19/20 XLSX) / eviews_subprocess (EViews 13+ on Windows). In ingestion mode the output does not respond to the scenario shock vector (two outcomes per scenario on the 2026-05-04 run) |
| MIRAGRODEP (multi-region recursive-dynamic agricultural CGE) | `src/models/macro/miragrodep.py` | Real | GAMS + CONOPT/PATH via subprocess (calib, MSD, REF, Simul phases). Needs GAMS with a CONOPT/PATH licence; skipped on the cluster (no gams executable) |
| MPSGE.jl / GTAP long-run CGE | `src/models/macro/mpsge_jl.py` | Real (analytical MVP) + config-aware full path | Pure Python (reduction) / Julia MPSGE.jl + JuMP via juliacall or subprocess (full). Headline gdp_impact_pct is the OECD/US-calibrated reference economy of the kernel, not a world aggregate; gdp_impact_pct_world_weighted is the PPP-share-weighted mean of the regional rows |
| NEMS (EIA National Energy Modeling System, AEO2025) | `src/models/macro/nems.py` | Real (published-output ingestion) + optional full path | output_ingestion (reads a completed NEMS run directory) / subprocess (cycle.py) / remote (SLURM). Ingestion needs a pre-computed run directory per scenario; the infrastructure_collapse scenario had no mapping on the 2026-05-04 run (validation failed) |
| NREL electricity-sector baseline (ReEDS / Cambium) | `src/models/macro/nrel.py` | Real (analytical MVP) | Pure Python (reduction); ReEDS/Cambium not run. No capacity expansion, transmission or regional detail; macro outputs are kernel-derived, not an electricity-sector result |
| OpenCGE (PSL OG-Core / OG-USA overlapping-generations CGE) | `src/models/macro/opencge.py` | Real | Python ogcore/ogusa + dask. Failed on the 2026-05-04 run with an ogcore parameter-validation error (Z / delta_tau_annual list shapes); OG-USA needs Python 3.12 |
| PyCGE (cge_modeling SAM-based CGE) | `src/models/macro/pycge.py` | Real (analytical MVP) + config-aware full path | Pure Python macro kernel (reduction) / cge_modeling package when its API matches (full). Headline gdp_impact_pct is the OECD/US-calibrated reference economy of the kernel, not a world aggregate; gdp_impact_pct_world_weighted is the PPP-share-weighted mean of the regional rows |

### Energy systems (long-run)

| Model | Adapter | Status | Notes |
|---|---|---|---|
| MESSAGEix (IIASA integrated assessment / energy systems) | `src/models/energy/messageix.py` | Real | message-ix + ixmp (Python + Java JDBC + GAMS). Failed on the cluster: no Java runtime for the ixmp JDBC backend |
| OSeMOSYS (open-source energy systems LP) | `src/models/energy/osemosys.py` | Real | GNU MathProg + GLPK/CBC through the otoole CSV pipeline. Skipped on the cluster: no baseline dataset under data/osemosys/baseline |
| TEMOA (Tools for Energy Model Optimization and Analysis) | `src/models/energy/temoa.py` | Real | Pyomo + CBC (or CPLEX/Gurobi) on a SQLite database, vendored clone. Skipped on the cluster: baseline database not vendored |

### Summary

- **Real (analytical MVP) (9):** `ais_project`, `aisdb`, `apsim`, `fed_oil`, `futures`, `marketsim`, `nrel`, `poles_jrc`, `world_helium_model`
- **Real (8):** `bornstein_krusell_rebelo`, `energy_flux_gas_power`, `energy_flux_lng_profits`, `messageix`, `miragrodep`, `opencge`, `osemosys`, `temoa`
- **Real (analytical MVP) + config-aware full path (7):** `argonne_abm`, `cwatm`, `lngst`, `mpsge_jl`, `pycge`, `weap_mena`, `world_fertilizer`
- **Real (config-aware) (4):** `ggm`, `magpie`, `sahysmod`, `simrlfab`
- **Stub (3):** `capri`, `gtap`, `simple_g`
- **Real (published-output ingestion) + optional full path (2):** `mam`, `nems`
- **Config-aware stub (1):** `watergap2`

Stubs do not break the pipeline: the executor catches `NotImplementedError`, marks the run as `SKIPPED`, and continues with the remaining models. The coverage ledger (`slurm/scripts/build_coverage_ledger.py`) records why every (scenario, model) cell did or did not contribute, and the run-specific inventory (`slurm/scripts/build_model_inventory.py --run-id ...`) records which implementation mode each completed cell used.
<!-- inventory:end -->

### MVP commodity-system coverage

After the SLURM driver bootstrap completes (`slurm/jobs/stonybrook_ai_cluster.job`), every `CommoditySystem` except `SHIPPING` has at least one model with a runnable `execute()`:

| CommoditySystem | MVP model | Mode |
|---|---|---|
| WATER | `cwatm` | Analytical fallback (or real CWatM when `cwatm.yaml` is provided) |
| OIL | `poles_jrc` | Analytical MVP |
| LNG | `energy_flux_gas_power`, `energy_flux_lng_profits` | Real (pure Python) |
| HELIUM_SEMICONDUCTORS | `world_helium_model` | Analytical MVP |
| FERTILIZER_AGRICULTURE | `futures` | Analytical MVP |
| SHIPPING | — | All adapters still stubs |
| MACROECONOMIC | `pycge`, `mam` | Real (after `[macro]` extras + auto-vendored AEO XLSX) |
| ENERGY_SYSTEMS | `temoa` | Real (after auto-vendored TEMOA clone + `cbc`) |

---

## Repository layout

```
agenticAIForScenarioAnalysis/
├── CLAUDE.md                      # Design specification (canonical)
├── README.md                      # This file
├── pyproject.toml                 # Dependencies (with optional extras per platform)
├── field_guide_model_integration_v2.md
├── model_integration_plan.md
├── LangChainNextSteps.md
│
├── src/
│   ├── pipeline/                  # LangGraph orchestrator (graph.py + state.py + config.py)
│   ├── scenarios/                 # Module 1
│   ├── parameters/                # Module 2 (extractor + per-system model_specs/)
│   ├── models/
│   │   ├── base.py                # ModelAdapter ABC, ModelOutput, ResourceRequirements
│   │   ├── registry.py            # build_default_registry(config_dir=...)
│   │   ├── executor.py            # Level-ordered async executor
│   │   ├── tools.py               # LangChain @tool wrappers
│   │   ├── adapters/              # SubprocessAdapter, GAMSAdapter, RAdapter,
│   │   │                          # JuliaAdapter, ExcelAdapter, AnyLogicAdapter
│   │   ├── water/  oil/  lng/
│   │   ├── helium/ fertilizer/
│   │   ├── shipping/ macro/
│   │   └── energy/                # OSeMOSYS, MESSAGEix, TEMOA
│   ├── synthesis/                 # consistency.py, synthesizer.py, schemas, prompts
│   ├── interface/                 # review, provenance, comparison
│   ├── news/                      # Temporal re-analysis: news + EIA adapters,
│   │                              # aggregator, weekly LLM summariser
│   └── common/                    # types, llm, logging
│
├── configs/
│   ├── crisis_descriptions/hormuz_2026.yaml
│   ├── crisis_descriptions/hormuz_2026_weekly/  # auto-populated by the
│   │                              # weekly news driver, one YAML per week
│   ├── scenario_frameworks/hormuz_2026.yaml
│   ├── consistency_rules.yaml
│   ├── news_sources.yaml          # Adapters + boolean query for the
│   │                              # temporal weekly driver
│   └── model_configs/             # Per-adapter YAML; pick this dir up via
│                                  # build_default_registry("configs/model_configs")
│
├── Models/                        # Vendored / cloned external model code
│   ├── Oil/WorldEquilibriumOilModel/
│   ├── LNG/GGM-20190509-open-source-final/
│   ├── LNG/NEMS-main/
│   ├── Fertilizer/magpie-master/
│   ├── Helium Market_ Semiconductors/SimRLFab-master/
│   ├── Shipping/aisstream-main/
│   ├── General Equilibrium/MIRAGRODEP_v0-1/
│   ├── General Equilibrium/EIA/   # MAM AEO2025 PDF
│   └── Energy/                    # OSeMOSYS, MESSAGEix, TEMOA (clone with submodules)
│
├── tests/
└── data/                          # Inputs, outputs, reports (gitignored for large files)
```

---

## Installation

The pipeline targets **Python ≥ 3.11**. Install the core orchestration layer:

```bash
pip install -e .
```

Domain-model integrations live behind optional extras so you only pull in what you need:

```bash
pip install -e ".[adapters]"     # openpyxl, pandas
pip install -e ".[julia]"        # juliacall (MPSGE.jl)
pip install -e ".[gams]"         # gamsapi (GGM, MIRAGRODEP, World Fertilizer, ...)
pip install -e ".[excel]"        # openpyxl + xlwings (Energy Flux, LNGST, MarketSim)
pip install -e ".[r]"            # rpy2 (MAgPIE in-process mode)
pip install -e ".[macro]"        # ogcore, dask, cge-modeling (Python 3.11+)
pip install -e ".[macro-us]"     # ogusa (Python 3.12+ ONLY; OpenCGE US calibration)
pip install -e ".[water]"        # netCDF4, xarray (CWatM / WaterGAP2 outputs)
pip install -e ".[energy]"       # otoole, message-ix, ixmp, pyomo (TEMOA via vendored repo)
pip install -e ".[news]"         # requests (NewsData.io / GNews / NewsAPI / EIA adapters)
pip install -e ".[dev]"          # pytest, pytest-asyncio
```

Non-Python prerequisites (GAMS, Octave + Dynare, GLPK/CBC, R, Java/JDK, Excel, AnyLogic Pro) are documented per-model in the linked READMEs (e.g., `Models/Energy/README.md`).

---

## Running the pipeline

A minimal end-to-end run loads the Hormuz crisis description, the scenario framework, and the model registry, then drives the LangGraph pipeline:

```python
from pathlib import Path
from src.pipeline.config import PipelineConfig
from src.pipeline.graph import build_graph
from src.models.registry import build_default_registry

registry = build_default_registry(config_dir=Path("configs/model_configs"))
config = PipelineConfig.from_yaml(Path("configs/model_configs/default.yaml"))

graph = build_graph(registry=registry, config=config)
state = graph.invoke({
    "run_id": "hormuz-001",
    "crisis_description": Path("configs/crisis_descriptions/hormuz_2026.yaml").read_text(),
    "framework": Path("configs/scenario_frameworks/hormuz_2026.yaml").read_text(),
})
```

The graph will pause at each HITL `interrupt()`. Resume with `Command(resume=...)` from the analyst review CLI (`src/interface/review.py`).

Tests live under `tests/`:

```bash
pytest                     # full suite
pytest tests/test_models   # adapter contract tests only
```

### Per-run output artefacts

The SLURM driver (`slurm/jobs/stonybrook_ai_cluster.job`) runs two trailing post-processing stages over the synthesis output of every run, both gated to be best-effort so a missing optional dep can't fail a run:

- **Stage 5 — quantitative + qualitative export** (`slurm/scripts/export_results.py`). Emits `data/reports/<run_id>/csv/{model_status,synthesis_outcomes,quantitative_results,consistency_flags}.csv`, per-(scenario, model) tables under `csv/raw/<scenario>/`, and per-scenario plain-prose narratives under `qualitative/<scenario>.md` plus a cross-scenario index.
- **Stage 6 — visualization suite** (`slurm/scripts/visualize_results.py`). Reads the Stage 5 CSVs + qualitative narratives and emits PNG figures (status by scenario / commodity system, headline-outcomes grid, per-row-normalised cross-model heatmap, consistency-flag bars, per-CSV time-series line/bar plots) plus a single self-contained `data/reports/<run_id>/figures/index.html` dashboard that embeds every figure inline alongside the rendered narrative markdown. Requires the `[viz]` extra (`pip install -e ".[viz]"` — matplotlib + pandas + markdown). The dashboard degrades to a text-only HTML report when any of those are unavailable.

Both stages are also runnable standalone against any historical run id:

```bash
python slurm/scripts/export_results.py    --run-id 20260423_125906
python slurm/scripts/visualize_results.py --run-id 20260423_125906
```

### Revision and audit tooling

The October 2026 revision added a set of audit scripts that read a run's saved state (`data/pipeline_state/<run_id>_*.json`) or, when only the Stage 5 export is available, its report directory (`--from-report-dir`). Their outputs are checked in under `docs/revision/` so the manuscript can cite them; `python scripts/revision/build_all.py --run-id <id> --report-dir <dir> [--baseline configs/baselines/hormuz_2026_analyst.yaml]` regenerates all of them.

| Script | What it produces |
|---|---|
| `slurm/scripts/build_coverage_ledger.py` | Per-cell coverage ledger (scenarios x model specs): parameter-extraction status, execution status, skip class, implementation mode, upstream sources; CSV, Markdown, LaTeX, and the `coverage_map.png` figure. |
| `slurm/scripts/build_model_inventory.py` | Static and run-specific model inventory from `src/models/implementation_info.py` (full upstream model vs analytical reduction vs published-output ingestion, calibration sources, key equations, limitations); `--update-readme` rewrites the tables above. |
| `slurm/scripts/run_fidelity_audit.py` | Numeric fidelity audit of the synthesis: every outcome value and prose number is matched against the cited model's outputs (exact / rounded / unit-scaled / derived / unmatched); source ids are canonicalised. The same audit runs inline during synthesis (`synthesis.fidelity` in the pipeline config). |
| `slurm/scripts/trace_provenance.py` | Full provenance chain for one (scenario, model, variable): narrative sentence, extracted parameter, adapter input, forwarding override record, model output, synthesis outcome. |
| `scripts/revision/anchor_comparison.py` | Cross-scenario table and figure restricted to the models that completed in every scenario. |
| `scripts/revision/checkpoint_report.py` | How the three analyst checkpoints were recorded per run (auto-approved in batch mode). |
| `scripts/revision/backend_comparison.py` | Per-backend weekly comparison (cells attempted and completed, clean-synthesis flag, wall-clock) from cluster copies of the weekly report and state directories. |
| `scripts/revision/coverage_facts.py` | Per-model scenario coverage statements, helium and fertilizer linkage coverage, and the water-linkage status under the tail-risk scenario, derived from the ledger. |
| `slurm/scripts/run_deterministic_baseline.py` | LLM-free comparator: analyst-authored scenarios and parameters (`configs/baselines/hormuz_2026_analyst.yaml`), the shared executor with forwarding, consistency checks, and a templated synthesis (`src/synthesis/templated.py`); writes the standard state and report files. |
| `scripts/revision/compare_runs.py` | Numeric diff of two runs' quantitative CSVs with a determinism check and status pairs. |
| `scripts/revision/effort_metrics.py` | Adapter code and test lines, commit counts, YAML lines per forwarding rule, lines changed by named commits. |
| `scripts/revision/replay_pycge_scenario_a.py` | Replays the macro kernel at past commits with the recorded Scenario A inputs. |
| `scripts/revision/software_versions.py`, `scripts/revision/model_licenses.py` | Package and runtime versions per run; per-model license and upstream references. |
| `scripts/revision/recover_run_from_outputs.py` | Rebuilds a run's per-cell records from `data/outputs/**/metadata.json` filtered by `run_id`. |

Two pipeline changes accompany these tools. Stage 3 state files are now named `<run_id>_model_<tier>_<task>.json` (the three tiers previously overwrote each other's records because their array indices restart at 0), and the forwarding dispatcher only reads `data/outputs/` entries whose `metadata.run_id` matches the current run (`--allow-stale-upstream` restores the old behaviour). A run's `summary.json` carries `clean_synthesis` and the `run_health` block (`src/synthesis/run_health.py`) that defines it.

---

## Temporal re-analysis from weekly news

The single-shot pipeline above answers *"what does our model portfolio say about the crisis given today's information?"*. The temporal driver answers a complementary question central to the framework's value proposition: *"how does the agent's analysis change as new information arrives, week by week?"*

Each iteration of the temporal loop:

1. Pulls a calendar week of news articles and government indicators from a configurable set of sources (NewsData.io, GNews, NewsAPI.org, NewsAPI.ai, EIA Open Data).
2. Runs an LLM summariser that produces a structured `WeeklyBrief` (headline, quantitative summary, key indicators, machine-readable `observed_indicators` with stable names + values + units, per-scenario probability signals, coverage gaps), threading in the previous week's brief as context.
3. Writes a per-week augmented crisis-description YAML into `configs/crisis_descriptions/hormuz_2026_weekly/<date>.yaml` (the baseline file is never mutated; the weekly file appends a `recent_developments` block plus a cumulative `weekly_briefs` history).
4. Re-runs **all of Algorithm 1** (scenarios → parameter extraction → model execution → synthesis) under a unique `HORMUZ_RUN_ID="weekly_<YYYYMMDD>"`, so each week's full set of state files, model outputs, and synthesis report sits side by side under `data/pipeline_state/weekly_*` and `data/reports/weekly_*` for cross-week comparison.

There are two ways to drive the loop: the **SLURM batch backfill** (below), which re-runs every week of a historical window unconditionally, and the **local automatic updater** (`python -m src.news.updater`), which processes one week per invocation and adds a *materiality gate* — the deterministic comparison in `src/news/materiality.py` between this week's and last week's `observed_indicators` (plus new-actor detection) decides whether a full pipeline rerun is actually warranted, so an unattended cron/scheduler entry does not burn an LLM + model-portfolio run on a week where nothing happened. Every decision is written to `data/reports/weekly_<date>/update_summary.{json,md}` with the per-indicator deltas and reasons, and can be overridden with `--force`.

```bash
# Local automatic update: last 7 days, rerun Modules 1-4 only if material.
# --auto-approve is required for unattended runs (checkpoints reviewed post-hoc).
export EIA_API_KEY=...
python -m src.news.updater --auto-approve

# Ad-hoc: specific window, custom materiality threshold, forced rerun
python -m src.news.updater --as-of 2026-04-10 --window-days 7 \
    --indicator-threshold-pct 5 --force --auto-approve

# Brief-only mode (no pipeline rerun; inspect summariser output first)
python -m src.news.updater --skip-pipeline
```

### Components

| Path | Role |
|---|---|
| `src/news/base.py` | `NewsArticle`, `NewsSource` ABC, `NewsSourceError` |
| `src/news/newsdata.py` | NewsData.io (`/archive` with auto-fallback to `/latest`) |
| `src/news/gnews.py` | GNews `/api/v4/search` |
| `src/news/newsapi.py` | NewsAPI.org and NewsAPI.ai (Event Registry) |
| `src/news/eia.py` | EIA Open Data API (WTI, Brent, US crude stocks, Henry Hub gas; series list overridable) |
| `src/news/aggregator.py` | Fan-out across sources with URL+title-date deduplication and per-source success/failure reporting |
| `src/news/summarizer.py` | LLM chain producing `WeeklyBrief` (incl. machine-readable `ObservedIndicator` records) + `write_updated_crisis_yaml` helper |
| `src/news/materiality.py` | Deterministic week-over-week comparison deciding whether a rerun is warranted (indicator deltas, new actors); no LLM call |
| `src/news/updater.py` | Local automatic update driver (`python -m src.news.updater`): fetch → brief → YAML → materiality gate → orchestrator rerun → `update_summary.{json,md}` |
| `configs/news_sources.yaml` | Crisis metadata, boolean query, list of source adapter specs |
| `slurm/scripts/build_weekly_brief.py` | CLI: fetch one week → summarise → write per-week YAML + provenance artefacts |
| `slurm/jobs/weekly_news_pipeline.job` | Generic SLURM driver: enumerate weeks, build briefs, re-run the pipeline for each |
| `slurm/jobs/empire_ai_alpha_weekly.job` | Empire AI Alpha companion to `empire_ai_alpha.job`: same `suny`-partition idioms, scratch detection (`/mnt/lustre/suny/$USER`), per-week W&B run groups, vLLM sidecar shared across all weeks |

`run_scenarios.py` honours the `HORMUZ_CRISIS_DESCRIPTION` environment variable so each weekly rerun feeds its own per-week YAML into Module 1; everything downstream (parameters, executor, synthesis) keys off `HORMUZ_RUN_ID` and so is automatically isolated per week.

### Source coverage notes

Historical search is paywalled on most commercial news APIs:

- **EIA Open Data** — free key, full historical depth. The default and recommended baseline source.
- **NewsData.io** — free tier returns last 48 hours only; `/archive` requires a paid tier (the adapter falls back to `/latest` automatically when archive returns 403/426 so the most recent week still works).
- **GNews** — free tier ≈ last 24 hours; Essential / Pro plans support full ranges.
- **NewsAPI.org** — Developer plan caps history at 30 days; Business plan for older ranges.
- **NewsAPI.ai** (Event Registry) — best historical coverage of the four article sources; tier-based rate limits.

The aggregator records per-source successes and failures into `data/news/<date>/report.json` so a week with degraded coverage is auditable rather than silent.

### Running the temporal driver

There are two SLURM entry points; pick the one that matches your cluster:

- **`slurm/jobs/empire_ai_alpha_weekly.job`** — the production driver for the Empire AI Alpha cluster. Companion to the main `empire_ai_alpha.job`: same `suny`-partition / `--gpus-per-node` directives, same `/mnt/lustre/suny/$USER` scratch detection, same three-tier W&B key resolution, same per-run logging discipline — but wraps the Module 6 weekly loop around Modules 1–4 and writes per-week W&B run groups (`weekly_<YYYYMMDD>`) tagged with the parent batch group so the W&B UI can show them as a single experiment.
- **`slurm/jobs/weekly_news_pipeline.job`** — the portable driver. Same loop logic but with the Empire-AI-specific scratch and W&B blocks stripped out. Useful as a starting template when porting to another cluster.

Both default to the full `2026-02-15` → `2026-04-10` window, weekly cadence, and a shared vLLM sidecar across all weeks (so the 70B model loads once, not nine times).

```bash
# Empire AI Alpha, cheapest path: free EIA indicators + cloud LLM
export EIA_API_KEY=...                    # free, eia.gov/opendata/register.php
export PIPELINE_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export HORMUZ_USE_VLLM=0
sbatch --gpus-per-node=1 slurm/jobs/empire_ai_alpha_weekly.job

# Empire AI Alpha, richer briefs with commercial news + local vLLM
export EIA_API_KEY=...
export NEWSDATA_API_KEY=...
export GNEWS_API_KEY=...
export NEWSAPI_ORG_API_KEY=...
sbatch slurm/jobs/empire_ai_alpha_weekly.job

# Empire AI Alpha, larger model on 4 GPUs with tensor parallelism
export HORMUZ_VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct
export HORMUZ_VLLM_TP_SIZE=4
sbatch --gpus-per-node=4 slurm/jobs/empire_ai_alpha_weekly.job

# Custom backfill window (works on either driver)
export HORMUZ_WEEKLY_START=2026-03-01
export HORMUZ_WEEKLY_END=2026-04-10
sbatch slurm/jobs/empire_ai_alpha_weekly.job

# Brief-only mode: build all weekly briefs but skip pipeline reruns
# (useful for inspecting summariser output before committing GPU time)
export HORMUZ_WEEKLY_SKIP_PIPELINE=1
sbatch --gpus-per-node=1 --time=06:00:00 slurm/jobs/empire_ai_alpha_weekly.job

# Generic / portable variant (different cluster, no Lustre scratch, no W&B):
sbatch slurm/jobs/weekly_news_pipeline.job
```

Either job fails fast at submission time if no news/EIA API key is set in the environment. Both validate conda activation, optionally start a single shared vLLM sidecar across all weeks, then enumerate calendar weeks via an inline Python helper (avoiding `date --iso` portability issues) and execute the brief-builder + full pipeline for each.

You can also drive a single week directly without SLURM, which is the easiest way to iterate on the summariser prompt:

```bash
python slurm/scripts/build_weekly_brief.py \
    --week-start 2026-02-15 --week-end 2026-02-22 \
    --baseline configs/crisis_descriptions/hormuz_2026.yaml \
    --output   configs/crisis_descriptions/hormuz_2026_weekly/2026-02-15.yaml \
    --sources-config configs/news_sources.yaml \
    --brief-out    data/news/2026-02-15/brief.txt \
    --articles-out data/news/2026-02-15/articles.json \
    --report-out   data/news/2026-02-15/report.json
```

### Outputs

After a full nine-week run you have:

- `configs/crisis_descriptions/hormuz_2026_weekly/<date>.yaml` — augmented crisis YAMLs, one per week, each carrying the cumulative `weekly_briefs` history.
- `data/news/<date>/articles.json` — raw fetched articles (full provenance).
- `data/news/<date>/report.json` — aggregator FetchReport (which sources succeeded, which failed, dedup statistics).
- `data/news/<date>/brief.txt` — plain-text rendering of the structured brief, fed as context to the next week.
- `data/pipeline_state/weekly_<date>_*` — Module 1–4 state files for that week.
- `data/reports/weekly_<date>_*` — synthesis reports for that week.
- `slurm/logs/weekly_news_pipeline-<jobid>/<date>/` — per-week stage logs and runtime inventory.

The set is directly comparable across weeks: the same scenario IDs, the same model registry, only the crisis description (and therefore extracted parameters and resulting outputs) shift. This is the artefact that demonstrates *"value of rapidly updated analysis"* in concrete, reviewable form.

---

## Configuration

Three YAML directories drive a run:

- `configs/crisis_descriptions/` — structured event description (timeline, actors, parameters known a priori).
- `configs/scenario_frameworks/` — Schwartz framework: focal issue, key factors, driving forces, predetermined elements, critical uncertainties.
- `configs/model_configs/` — one file per adapter that needs concrete paths, executables, baseline data, or solvers. Adapters whose YAML is **absent** instantiate as stubs (and skip cleanly at execution time); adapters whose YAML is **present and valid** activate their real execution paths.

`configs/consistency_rules.yaml` declares cross-model consistency tolerances (e.g., oil-price agreement bands across BKR, POLES-JRC, and the Fed model) used by `src/synthesis/consistency.py`.

`configs/news_sources.yaml` configures the temporal weekly driver: crisis metadata, the boolean query passed to every source, and an ordered list of source adapter specs (NewsData.io, GNews, NewsAPI.org / .ai, EIA Open Data). Commented-out source entries activate by uncommenting; missing API keys cause a source to be skipped at runtime rather than aborting the week.

---

## Further reading

- **`CLAUDE.md`** — full design specification (Algorithm 1, module contracts, design constraints).
- **`field_guide_model_integration_v2.md`** — practical reference for each execution environment (Julia, GAMS, Excel, AnyLogic, R, generic subprocess) with current 2026 API details.
- **`model_integration_plan.md`** — historical sequencing notes for `Models/` ↔ `src/models/` integration.
- **`LangChainNextSteps.md`** — LangGraph 1.x patterns (state, supervisors, HITL, fan-out) referenced by the orchestrator.
- **`Models/Energy/README.md`** — cloning, solver, and baseline-data instructions for the energy-systems trio.

---

## License & citation

This is a research codebase. If you use it in academic work, please cite the underlying paper (Golden, Indelicato, Varshney, & Thornsbury, *Agentic AI Modeling for Rapid Analysis of Chokepoint Crises ...*) and respect the licenses of each vendored model under `Models/` (NEMS: public domain, GGM: MIT, MAgPIE: AGPL-3.0, OSeMOSYS / MESSAGEix / TEMOA: see upstream repositories, etc.).

Citation metadata lives in `CITATION.cff` and `.zenodo.json` (software record for the Zenodo release); the per-model license table is generated into `docs/revision/model_licenses.md` by `scripts/revision/model_licenses.py`.
