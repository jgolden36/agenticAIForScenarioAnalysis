# CLAUDE.md — Agentic AI Crisis Analysis Pipeline

## Project Overview

This repository implements the agentic AI orchestration framework described in "Agentic AI Modeling for Rapid Analysis of Chokepoint Crises Along Strategic and Economic Dimensions: A Case Study of the Closure of the Strait of Hormuz" (Golden, Indelicato, Varshney, & Thornsbury).

The system uses **LangChain** to orchestrate a multi-model, multi-scenario analytical pipeline that bridges three persistent gaps in crisis economics: (1) short-run vs. long-run analysis, (2) microeconomic vs. macroeconomic scope, and (3) economic vs. strategic-military assessment. The pipeline coordinates heterogeneous domain models—written in Python, Julia, GAMS, R, AnyLogic, and spreadsheets—through a structured scenario analysis framework.

**The applied case is the February 2026 closure of the Strait of Hormuz.** The framework is designed to be reusable for future chokepoint crises and comparable geopolitical disruptions.

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

---

## Domain Model Inventory

The following table lists all domain models referenced in the paper, grouped by commodity system. **When building the scaffolding, create a model wrapper/adapter interface for each entry.** Actual model implementations will be integrated later; the scaffolding should define the interface contracts (input schema, output schema, execution method).

### Water Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| WEAP / WEAP–MENA | Simulation | — | Integrated water resource planning; Persian Gulf regional config |
| SahysMod | Simulation | — | Spatially distributed agro-hydro-salinity modeling |
| WaterGAP2 | Gridded global | — | Global gridded hydrological modeling of infrastructure disruption |
| CWatM | Gridded global | — | Community-scale water availability under disruption |

### Oil Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| World Equilibrium Model of the Oil Market (Bornstein-Krusell-Rebelo) | Structural GE | — | Supply disruption analysis in general equilibrium |
| POLES-JRC | Partial equilibrium | — | Detailed global energy supply and demand dynamics |
| MarketSim (BOEM) | Partial equilibrium | — | Consumer surplus and energy substitution for disruption scenarios |
| Fed Workhorse Oil Model (Baumeister-Hamilton) | Macro-energy | — | US monetary transmission of oil price shocks |

### LNG Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| Energy Flux US Gas Power Build-Out Constraint Model v1.0 | Proprietary | — | US gas-to-power capacity constraints |
| Energy Flux US LNG War Profits Model v1.0 | Proprietary | — | LNG export revenue under conflict scenarios |
| Global Gas Model (GGM) | Optimization | — | Global gas trade flow optimization |
| LNG Spreadsheet Tool (LNGST) | Spreadsheet | Excel | Scenario-level LNG trade flow simulation |

### Helium & Semiconductor Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| World Helium Model (IFP Énergies Nouvelles) | Market equilibrium | — | Global helium supply-demand equilibrium |
| Argonne Helium ABM | Agent-based | AnyLogic | Contemporary helium market dynamics |
| SimRLFab | RL simulation | — | Semiconductor fabrication disruption impacts |

### Fertilizer & Agricultural Trade Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| CAPRI | Partial equilibrium | — | Regional agricultural policy impact modeling |
| MAgPIE | Optimization | — | Land-use and agricultural production modeling |
| SIMPLE-G | CGE | — | General equilibrium agricultural trade |
| World Fertilizer Model | Market equilibrium | — | Global fertilizer supply-demand dynamics |
| GTAP | CGE | — | Global agricultural and commodity trade flows |
| APSIM | Crop simulation | — | Physical crop yield response to input disruption |
| Futures forecasting models | Time series | — | Commodity futures price trajectory forecasting |

### Shipping Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| AISdb | Spatial database | — | AIS vessel tracking data processing and rerouting calibration |
| AIS_project | Spatial analysis | — | Transit time and fleet utilization under Strait closure |

### Macroeconomic / General Equilibrium Models
| Model | Type | Platform/Language | Role |
|---|---|---|---|
| NEMS (EIA baseline) | Systems model | — | National energy-economy baseline projections |
| NREL baseline | Sectoral | — | Electricity sector baseline and disruption impacts |
| MPSGE.jl / GTAP | CGE | Julia | General equilibrium trade and welfare analysis |
| OpenCGE | CGE | Python | Open-source CGE cross-validation |
| pycge / cge_modeling | CGE | Python | Additional CGE implementation for sensitivity analysis |
| MIRAGRODEP | CGE | — | Multi-region CGE with agricultural-trade linkages |

**Note on platforms:** Many platform/language entries are marked "—" because the paper does not specify them for all models. When building wrappers, use a generic `ModelAdapter` base class that can be subclassed for each specific execution environment (Python subprocess, Julia subprocess, GAMS CLI, Excel COM/openpyxl, AnyLogic CLI, etc.).

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

## Recommended Project Structure

```
hormuz-pipeline/
├── CLAUDE.md                          # This file
├── README.md                          # Public-facing project description
├── pyproject.toml                     # Project dependencies and metadata
│
├── src/
│   ├── __init__.py
│   │
│   ├── pipeline/                      # Core pipeline orchestration
│   │   ├── __init__.py
│   │   ├── orchestrator.py            # Main LangChain pipeline (Algorithm 1)
│   │   ├── config.py                  # Pipeline configuration and constants
│   │   └── state.py                   # Pipeline state management (scenario params, model outputs)
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
│   │   ├── base.py                    # Abstract ModelAdapter base class
│   │   ├── registry.py                # Model registry (maps model IDs to adapters)
│   │   ├── executor.py                # Parallel/sequential execution manager
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
│   │   └── macro/                     # Macroeconomic model adapters
│   │       ├── __init__.py
│   │       ├── nems.py
│   │       ├── nrel.py
│   │       ├── mpsge_jl.py
│   │       ├── opencge.py
│   │       ├── pycge.py
│   │       └── miragrodep.py
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
│   ├── crisis_descriptions/           # Structured crisis descriptions (input to Module 1)
│   │   └── hormuz_2026.yaml
│   ├── scenario_frameworks/           # Schwartz framework specifications
│   │   └── hormuz_2026.yaml
│   └── model_configs/                 # Per-model configuration (paths, timeouts, etc.)
│       └── default.yaml
│
└── data/                              # Data directory (gitignored for large files)
    ├── inputs/                        # Raw input data for models
    ├── outputs/                       # Model run outputs
    └── reports/                       # Generated synthesis reports
```

---

## Implementation Guidance for Claude Code

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

19. **`src/pipeline/orchestrator.py`** — The main pipeline that chains Modules 1–5 together following Algorithm 1. This should be a LangChain `RunnableSequence` or equivalent composable structure. It must:
    - Enforce the mandatory analyst checkpoints (after scenario generation, after parameter extraction, after synthesis)
    - Support partial reruns (e.g., rerun only Scenario B with modified parameters, without regenerating all scenarios)
    - Log every step with timestamps and provenance metadata

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

Core dependencies (do not add unnecessary packages):
- `langchain` and `langchain-core` — Pipeline orchestration and LLM interface
- `pydantic` — Schema definitions and validation
- `pyyaml` — Configuration files
- `asyncio` — Parallel model execution

Likely needed for model adapters (add as specific models are integrated):
- `openpyxl` — Excel model interface (LNGST)
- `juliacall` or `subprocess` — Julia model interface (MPSGE.jl)
- `subprocess` — Generic CLI model execution (GAMS, R, AnyLogic)
- `pandas` — Data interchange between models

---

## Testing Strategy

- **Unit tests** for each module in isolation (schema validation, prompt construction, parameter extraction from known narratives)
- **Integration tests** using mock model adapters that return known outputs, verifying that the full pipeline correctly threads data from scenarios through to synthesis
- **Consistency check tests** using deliberately contradictory mock outputs to verify that the consistency module catches them
- **Provenance tests** verifying that every result in a mock synthesis traces back to a specific model run

---

## What This Document Does NOT Cover

- The actual implementation of any domain model. This pipeline is the orchestration layer. Domain models are external and are accessed through the adapter interface.
- The specific prompt engineering for scenario generation and parameter extraction. The `prompts.py` files should contain initial templates, but these will be refined iteratively based on output quality.
- The web-based analyst interface. The initial implementation uses CLI-based review. A web UI is a future extension.
- Deployment, CI/CD, or cloud infrastructure. This is a research codebase.
