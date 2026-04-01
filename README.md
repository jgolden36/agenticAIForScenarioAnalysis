# Agentic AI for Crisis Scenario Analysis

An AI-orchestrated, multi-model pipeline for rapid analysis of chokepoint crises along strategic and economic dimensions. Built with **LangChain** and **LangGraph**, the system coordinates heterogeneous domain models -- written in Python, Julia, GAMS, R, AnyLogic, and Excel -- through a structured scenario analysis framework with mandatory human-in-the-loop checkpoints.

> **Applied case study:** Closure of the Strait of Hormuz (February 2026), as described in *"Agentic AI Modeling for Rapid Analysis of Chokepoint Crises Along Strategic and Economic Dimensions"* (Golden, Indelicato, Varshney, & Thornsbury).

---

## Motivation

Crisis economics suffers from three persistent analytical gaps:

1. **Short-run vs. long-run** -- immediate price shocks vs. structural adjustment
2. **Microeconomic vs. macroeconomic** -- commodity markets vs. GDP, inflation, employment
3. **Economic vs. strategic-military** -- trade flows vs. alliance credibility, deterrence, logistics

No single model spans all three dimensions. This pipeline bridges them by orchestrating dozens of specialized domain models under a unified scenario framework, using LLMs for the operationally intensive but conceptually routine tasks (narrative generation, parameter extraction, output synthesis) while reserving judgment and validation for human analysts.

---

## How It Works

The pipeline implements a five-module architecture (Algorithm 1 from the paper):

```
Crisis Description + Scenario Framework
        |
        v
[Module 1] Scenario Generation -----> Analyst Review (mandatory)
        |
        v
[Module 2] Parameter Extraction -----> Analyst Review (mandatory)
        |
        v
[Module 3] Model Execution (parallel within analytical levels)
   Combat -> Commodity -> Short-run Macro -> Long-run Macro/Strategic
        |
        v
[Module 4] Output Synthesis + Cross-model Consistency Checks
        |
        v
[Module 5] Analyst Interface -----> Analyst Review (mandatory)
        |
        v
    Final Report with Full Provenance
```

### Module 1: Scenario Generation

Generates structured scenario narratives using the Schwartz scenario matrix methodology. For the Hormuz case, two critical uncertainties define a 2x2 matrix:

| | Contained Conflict | Escalated Conflict |
|---|---|---|
| **Swift Resolution (4-6 weeks)** | Scenario A | Scenario C |
| **Prolonged Closure (3-6+ months)** | Scenario B | Scenario D |

### Module 2: Parameter Extraction

Parses each scenario narrative and extracts quantitative parameters (oil supply loss, LNG disruption, fertilizer price shocks, etc.) mapped to each domain model's input specification, with confidence annotations.

### Module 3: Model Execution

Dispatches parameterized runs across the full model portfolio. Models execute in analytical-level order (combat -> commodity -> short-run macro -> long-run macro), with parallelism within each level. A generic adapter pattern supports heterogeneous execution environments.

### Module 4: Output Synthesis

Aggregates results across models and scenarios, performs cross-model consistency checks, and generates narrative summaries. Quantitative results pass through unmodified -- the LLM synthesizes text, not numbers.

### Module 5: Analyst Interface

Presents results with full provenance (every number traces back to a specific model run with specific inputs from a specific scenario). Supports iterative refinement and selective reruns.

---

## Domain Models

The pipeline wraps **30+ domain models** across seven commodity systems:

| Commodity System | Models |
|---|---|
| **Water** | WEAP/WEAP-MENA, SahysMod, WaterGAP2, CWatM |
| **Oil** | Bornstein-Krusell-Rebelo, POLES-JRC, MarketSim (BOEM), Fed Workhorse Oil Model |
| **LNG** | Energy Flux Gas Power, Energy Flux LNG Profits, Global Gas Model (GGM), LNG Spreadsheet Tool |
| **Helium & Semiconductors** | World Helium Model, Argonne Helium ABM, SimRLFab |
| **Fertilizer & Agriculture** | CAPRI, MAgPIE, SIMPLE-G, World Fertilizer Model, GTAP, APSIM, Futures models |
| **Shipping** | AISdb, AIS_project |
| **Macroeconomic** | NEMS, NREL, MPSGE.jl/GTAP, OpenCGE, pycge, MIRAGRODEP |

Each model is accessed through a `ModelAdapter` subclass that handles input translation, execution, and output parsing. Platform-specific adapters are provided for Python, Julia, GAMS, R, AnyLogic, and Excel environments.

---

## Project Structure

```
agenticAIForScenarioAnalysis/
├── src/
│   ├── pipeline/          # Core orchestration (Algorithm 1)
│   ├── scenarios/         # Module 1: Scenario generation (Schwartz framework)
│   ├── parameters/        # Module 2: Parameter extraction + model input specs
│   ├── models/            # Module 3: Model adapters, registry, and executor
│   │   ├── water/         #   Water model adapters
│   │   ├── oil/           #   Oil model adapters
│   │   ├── lng/           #   LNG model adapters
│   │   ├── helium/        #   Helium & semiconductor adapters
│   │   ├── fertilizer/    #   Fertilizer & agriculture adapters
│   │   ├── shipping/      #   Shipping model adapters
│   │   ├── macro/         #   Macroeconomic model adapters
│   │   └── adapters/      #   Platform-specific adapters (Julia, GAMS, R, Excel, AnyLogic)
│   ├── synthesis/         # Module 4: Cross-model synthesis and consistency
│   ├── interface/         # Module 5: Analyst review, provenance, comparison
│   └── common/            # Shared types, LLM config, logging
├── configs/               # YAML configuration (crisis descriptions, scenario frameworks, model configs)
├── tests/                 # Unit and integration tests
├── Model/                 # External model source code and documentation
└── data/                  # Input data, model outputs, generated reports (gitignored)
```

---

## Installation

Requires **Python 3.11+**.

```bash
# Clone the repository
git clone https://github.com/jgolden36/agenticAIForScenarioAnalysis.git
cd agenticAIForScenarioAnalysis

# Install core dependencies
pip install -e .

# Install with development tools
pip install -e ".[dev]"

# Install optional adapter dependencies as needed
pip install -e ".[adapters]"    # pandas, openpyxl
pip install -e ".[julia]"      # juliacall
pip install -e ".[gams]"       # gamsapi
pip install -e ".[r]"          # rpy2
pip install -e ".[excel]"      # openpyxl, xlwings
```

---

## Running Tests

```bash
pytest
```

---

## Configuration

The pipeline is configured through YAML files in `configs/`:

- **`crisis_descriptions/`** -- Structured crisis event descriptions (the input to Module 1)
- **`scenario_frameworks/`** -- Schwartz scenario framework specifications (focal issue, driving forces, critical uncertainties)
- **`model_configs/`** -- Per-model settings (paths, timeouts, convergence thresholds)
- **`consistency_rules.yaml`** -- Cross-model consistency check tolerances

LLM provider settings are configured via `src/common/llm.py` and are not hardcoded to a specific provider.

---

## Design Principles

- **Human-in-the-loop is mandatory.** The pipeline pauses for analyst validation after scenario generation, parameter extraction, and final synthesis. It reorganizes the division of labor between AI and analysts -- it does not replace analysts.
- **Provenance is mandatory.** Every quantitative result traces back through the full chain: synthesis -> model output -> model input -> extracted parameter -> scenario narrative.
- **The LLM does not fabricate numbers.** LLMs generate narratives, extract parameters, and synthesize text summaries. All quantitative results come from domain model runs.
- **Graceful degradation.** Individual model failures are isolated and reported; they do not crash the pipeline.
- **Configuration over hardcoding.** Model paths, LLM settings, parallelism, tolerances, and output directories are configurable via YAML or environment variables.

---

## Citation

If you use this framework, please cite:

> Golden, J., Indelicato, N., Varshney, L. R., & Thornsbury, S. "Agentic AI Modeling for Rapid Analysis of Chokepoint Crises Along Strategic and Economic Dimensions: A Case Study of the Closure of the Strait of Hormuz."

---

## License

See repository for license details.
