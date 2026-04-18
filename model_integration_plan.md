# Model Integration Plan: `Models/` → `src/models/`

**Date:** March 31, 2026
**Status:** Draft — for analyst review before implementation

---

## 1. Current State Summary

### What exists in `Models/`

Three model codebases and one API pointer are physically present in the repository:

| Model | Location | Language/Platform | Size | License |
|---|---|---|---|---|
| **GGM** (Global Gas Model v3.0) | `Models/LNG/GGM-20190509-open-source-final/GGM/` | GAMS (CPLEX) + R (geo mapping) | ~43 files | MIT |
| **MAgPIE** (Model of Agricultural Production & Environment) | `Models/Fertilizer/magpie-master/magpie-master/` | GAMS (CONOPT) + R (orchestration, reporting) | ~850 files | AGPL-3.0 |
| **NEMS** (National Energy Modeling System, AEO2025) | `Models/LNG/NEMS-main/NEMS-main/` | Fortran + AIMMS + Python + GAMS (LFMM) | ~2,400 files | Public domain (EIA) |
| **aisstream** | `Models/Shipping/aisstream-main/aisstream-main/` | N/A (README only) | 1 file | — |

### What exists in `src/models/`

- **`base.py`**: `ModelAdapter` ABC with `validate_inputs`, `translate_inputs`, `execute`, `parse_outputs`
- **`adapters/`**: Six platform-specific base classes — `GAMSAdapter`, `RAdapter`, `SubprocessAdapter`, `ExcelAdapter`, `JuliaAdapter`, `AnyLogicAdapter` — all with working `execute()` implementations
- **30 domain adapter stubs** across 7 commodity subdirectories, all with `execute() → NotImplementedError`
- **`registry.py`**: `build_default_registry()` instantiating all 30+ adapters
- **`executor.py`**: Async execution manager with level-ordered parallelism
- **`tools.py`**: LangChain tool wrappers

### The gap

The domain adapter stubs are disconnected from both the platform-specific bases and the actual model codebases. Specifically:

1. **`GGMAdapter`** inherits from `ModelAdapter` directly, not `GAMSAdapter` — despite GGM being a GAMS model with CPLEX
2. **`MAgPIEAdapter`** inherits from `ModelAdapter` directly — despite MAgPIE using R as its orchestration layer and GAMS for optimization
3. **`NEMSAdapter`** inherits from `ModelAdapter` directly — despite NEMS being a complex multi-binary system best wrapped via subprocess
4. No adapter references the actual model files in `Models/`
5. Input/output translation is passthrough (`return params`) in all stubs

---

## 2. Integration Priority & Sequencing

Models are prioritized by: (a) integration feasibility, (b) relevance to the Hormuz scenario, and (c) complexity.

### Priority 1: GGM (Global Gas Model) — **Start here**

**Why first:** Smallest GAMS model (~43 files), clean structure, MIT license, directly relevant to LNG trade disruption under Hormuz closure. The `GAMSAdapter` base class already implements the full GAMS Control API execution flow. This is the lowest-risk integration with the highest learning value for subsequent GAMS models.

### Priority 2: MAgPIE — **Second pass**

**Why second:** High relevance (fertilizer price shocks → agricultural production impacts), but significantly more complex. MAgPIE's R-based orchestration layer wrapping GAMS optimization requires a hybrid adapter approach. The integration pattern developed here applies to any model with an R entry point.

### Priority 3: NEMS — **Third pass (partial integration)**

**Why third:** Highest complexity by far. Full NEMS runs take 20+ hours and require ~30 GB storage, Intel Fortran, AIMMS, and Windows. A full integration is impractical for pipeline iteration. The strategy is to integrate specific NEMS submodules (LFMM, NGMM, MAM) rather than the monolithic system, or to ingest pre-computed NEMS outputs as scenario baselines.

### Not prioritized: aisstream

No model code exists in the repository. The adapter would be an API client to the aisstream.io WebSocket service — orthogonal to the GAMS/R/Fortran integration pattern. Defer to a later phase.

---

## 3. GGM Integration Plan

### 3.1 Model Architecture (as-is)

GGM is a quadratic complementarity program (QCP) that minimizes total gas system cost subject to mass balance, capacity, and investment constraints. Key structure:

```
main.gms                    ← Entry point: sets scenario globals, includes all files
├── data/all_input_data.gms ← Loads data from Excel via GDXXRW
│   ├── data/in_sets_parms.gms  ← Sets (arcs, countries, nodes, regions, seasons)
│   ├── data/in_prod.gms        ← Production costs and capacities
│   ├── data/in_cons.gms        ← Consumption/demand data
│   ├── data/in_arcs.gms        ← Network arc definitions and capacities
│   ├── data/in_stor.gms        ← Storage parameters
│   ├── data/in_market.gms      ← Market structure (Cournot parameters)
│   └── data/in_period.gms      ← Time period definitions
├── model/all_eq_and_var.gms    ← Variables and equations (objective, mass balance, capacity)
├── model/solve.gms             ← Solve statement
└── report/reports.gms          ← Output reporting
```

**Key variables (decision):**
- `Q_P(cn,n,r,d,y)` — Quantity produced by resource (mcm/yr)
- `Q_S(cn,n,d,y)` — Quantity sold (mcm/yr)
- `F_A(cn,a,d,y)` — Arc flow / trade flow (mcm/yr)
- `F_I`, `F_X` — Storage injection/extraction
- `D_A`, `D_X`, `D_W` — Capacity expansion decisions

**Key parameters (input):**
- Production costs (`cost_pl`, `cost_pq`), arc costs (`cost_a`), investment costs (`inv_a`, `inv_x`, `inv_w`)
- Demand curves (`int`, `slp` — intercept and slope of linear demand)
- Capacity limits (`cap_a`, `cap_p`, `cap_x`, `cap_w`)
- Cournot parameters (`cour`)

**Data pipeline:** GGM reads from Excel files (`data/SET-Nav/data.xlsx`, `data_proj.xlsx`, `data_calib_*.xlsx`) via the GAMS GDXXRW utility, converting to GDX intermediate files. This is a critical integration point — we can either:
- (a) Modify the Excel files before execution (inject shocks into demand/capacity sheets), or
- (b) Override GAMS parameters programmatically after data loading via a GamsDatabase, or
- (c) Create a modified `.gms` include file that applies percentage shocks on top of baseline values

**Solver:** CPLEX (QCP). The model sets `option QCP = CPLEX` and uses `SGGM.optfile = 1` pointing to `cplex.opt`.

**Scenarios:** The model uses `$SETGLOBAL` for scenario/case selection: `WEO` (NPS or SDS), `SETNav` (Ref or Vision), `last_yr` (2015, 2025, 2060).

### 3.2 Data Dependency Issue

The git status shows many Excel files under `GGM/data/set-nav/` and `GGM/excel/` as **deleted**. These are the input data files GGM requires. Before integration can proceed:

- [ ] **Restore the GGM data files** from the upstream distribution or git history
- [ ] Verify the Excel files are readable and contain expected sheets
- [ ] Confirm GAMS + CPLEX license availability on the target machine

### 3.3 Integration Steps

#### Step 1: Rebase `GGMAdapter` onto `GAMSAdapter`

Change `GGMAdapter` to inherit from `GAMSAdapter` instead of `ModelAdapter`. This gives us the full GAMS Control API execution flow (workspace creation, job execution, convergence checking, listing file capture) for free.

```python
from src.models.adapters.gams_adapter import GAMSAdapter, GAMSConfig

class GGMAdapter(GAMSAdapter):
    ...
```

The `GAMSAdapter` base class already handles:
- Isolated working directories (thread safety)
- `GamsWorkspace` → `GamsJob` → `.run()` flow
- Model status / solve status convergence checking
- Listing file capture on failure
- `ModelOutput` construction with convergence metadata

The subclass must implement:
- `populate_database(db, params)` — inject Hormuz scenario parameters
- `extract_results(out_db)` — read solution variables from output database

#### Step 2: Map scenario parameters to GGM's data layer

The Hormuz closure scenarios affect GGM through:

| Scenario parameter | GGM impact | Implementation approach |
|---|---|---|
| `strait_closure_flag` | Zeroes or reduces capacity on Persian Gulf → Asia arcs | Set `cap_a(a,y) = 0` for affected arcs |
| `qatar_lng_export_loss_pct` | Reduces Qatar production capacity | Scale `cap_p(n,r,y)` for Qatar nodes |
| `disruption_duration_months` | Determines which time periods are affected | Map to GGM's seasonal/yearly periods |
| `rerouting_available` | Whether alternative arcs remain open | Conditionally keep/close secondary routes |

The `populate_database()` method will:
1. Load the baseline GDX (from the solved baseline case)
2. Identify the arc and node IDs corresponding to Persian Gulf infrastructure
3. Apply percentage reductions to capacity parameters
4. Write modified parameters into the `GamsDatabase`

This requires a **mapping file** that identifies which GGM node/arc IDs correspond to Qatar, UAE, and Strait of Hormuz chokepoints. This must be built by inspecting `data/SET-Nav/data.xlsx`.

#### Step 3: Implement `extract_results()`

Read the solved GGM output database and extract:

| Output variable | GGM source | Unit |
|---|---|---|
| Regional LNG prices | Dual values on `eq_mass_bal` | $/mcm → convert to $/MMBtu |
| Bilateral trade flows | `F_A.l(cn,a,d,y)` (arc flow levels) | mcm/yr |
| Capacity utilization | `F_A.l / cap_a` ratios | fraction |
| Unmet demand | Slack on demand constraints | mcm/yr |
| Rerouting costs | Delta in `MinObj` vs. baseline | $ |
| Investment decisions | `D_A.l`, `D_X.l`, `D_W.l` | mcm/yr capacity |

#### Step 4: Handle the Excel data pipeline

GGM's `in_sets_parms.gms` calls `GDXXRW` to convert Excel → GDX. Two approaches:

**Option A (recommended): Pre-convert Excel to GDX, inject shocks via GamsDatabase.**
Run GGM once in baseline mode, save the GDX. At runtime, load the baseline GDX into a `GamsDatabase`, modify parameters, and pass to the solver. This avoids Excel dependency at runtime.

**Option B: Modify Excel files before each run.**
Use `openpyxl` to modify `data.xlsx` cells, then let GGM's native `GDXXRW` pipeline handle conversion. Fragile (cell reference sensitivity) but preserves the original data pipeline.

#### Step 5: Create a GGM runner script

Write a thin GAMS include file (`hormuz_shock.gms`) that:
1. Loads baseline parameters from GDX
2. Applies shock multipliers passed via `$SETGLOBAL` defines
3. Replaces capacity/cost parameters before the solve statement

This can be injected between the data loading and solve phases via `GAMSConfig.extra_defines`.

#### Step 6: Validation and testing

- [ ] Run GGM baseline (NPS-Ref, 2025) and verify convergence
- [ ] Run with 100% Qatar export loss and verify prices increase
- [ ] Compare baseline vs. shock output for consistency
- [ ] Verify `extract_results()` produces correct units
- [ ] Test through the `ModelExecutor` async pipeline

### 3.4 Deliverables

1. Refactored `src/models/lng/ggm.py` inheriting from `GAMSAdapter`
2. GGM node/arc mapping file (`configs/model_configs/ggm_topology.yaml`)
3. Hormuz shock include file (`Models/LNG/GGM.../GGM/hormuz_shock.gms`)
4. Updated `validate_inputs()` with GGM-specific parameter ranges
5. Integration test with mock GDX outputs

---

## 4. MAgPIE Integration Plan

### 4.1 Model Architecture (as-is)

MAgPIE is a recursive-dynamic partial equilibrium model with **46 GAMS modules** organized around land-use cost minimization. The execution flow is:

```
Rscript start.R
  → scripts/start/default.R       ← R: reads config, downloads data, sets up run
    → cfg from config/default.cfg  ← R: scenario configuration
    → gams main.gms               ← GAMS: 46 modules, CONOPT solver
      → core/sets.gms, declarations.gms, calculations.gms
      → modules/*/module.gms (each with realization variants)
    → output processing            ← R: reads fulldata.gdx → report.mif
```

**Key characteristics:**
- **R is the orchestration layer**: `start.R` handles configuration, data preparation, GAMS invocation, and output processing. GAMS is called as a subprocess from R.
- **madrat data system**: Input data is preprocessed by the `madrat` R package framework. Raw data → processed GDX inputs. This is a substantial dependency.
- **46 modular components**: Each module has multiple "realizations" (implementation variants). The scenario config selects which realization to use for each module.
- **LPJmL coupling**: Biophysical constraints (crop yields, water availability) come from the LPJmL vegetation model. For crisis scenarios, these are typically held fixed while economic parameters are shocked.

### 4.2 Adapter Architecture Decision

MAgPIE does not fit cleanly into either `GAMSAdapter` or `RAdapter` alone. It requires a **hybrid approach**:

**Recommended: RAdapter as the base, with GAMS executed as a subprocess within the R orchestration.**

Rationale:
- The canonical entry point is `Rscript start.R`, not `gams main.gms`
- Configuration, data preparation, and output processing are all in R
- Calling GAMS directly would bypass critical setup steps (data downloads, configuration resolution, renv package management)
- The `RAdapter` base class already handles subprocess Rscript invocation with JSON I/O

The adapter would:
1. Write a scenario-specific `cfg` configuration in R format
2. Invoke a custom R script that sources MAgPIE's start infrastructure, applies the cfg, runs GAMS, and returns results as JSON
3. Parse the JSON output (derived from `fulldata.gdx` → `report.mif`)

### 4.3 Scenario Parameter Mapping

Hormuz closure scenarios affect MAgPIE through:

| Scenario parameter | MAgPIE impact | Where it enters |
|---|---|---|
| `fertilizer_price_shock_pct` | Increases production costs for fertilizer-intensive crops | Module `38_factor_costs` — cost multiplier on nitrogen/phosphorus inputs |
| `crop_yield_impact_pct` | Reduces crop yields (via reduced fertilizer application) | Module `14_yields` — yield reduction factor |
| `water_availability_change_pct` | Reduces irrigation water (desalination disruption in MENA) | Module `43_water_availability` — regional water constraint tightening |

Additional parameters to consider:
- `energy_price_shock_pct` — affects transport costs (module `40_transport`)
- `trade_restriction_flag` — affects trade module behavior (module `21_trade`)
- Regional scope of disruption (MENA vs. global)

### 4.4 Prerequisites

- [ ] **GAMS installation with CONOPT solver** (GAMS ≥ 50.1.0 per MAgPIE README)
- [ ] **R installation** (R ≥ 4.3 with Rtools on Windows)
- [ ] **MAgPIE R package dependencies** (installed via renv on first run)
- [ ] **MAgPIE input data** — downloaded via `scripts/start/download_data.R` (requires internet access; data hosted by PIK)
- [ ] **Successful baseline run** — `Rscript start.R` with default config must complete before any shock scenario

### 4.5 Integration Steps

#### Step 1: Rebase `MAgPIEAdapter` onto `RAdapter`

```python
from src.models.adapters.r_adapter import RAdapter, RConfig

class MAgPIEAdapter(RAdapter):
    ...
```

#### Step 2: Write a MAgPIE bridge R script

Create `src/models/fertilizer/magpie_bridge.R` — an R script that:
1. Accepts a JSON input file with scenario parameters
2. Sources MAgPIE's configuration infrastructure
3. Modifies the `cfg` object to apply fertilizer/yield/water shocks
4. Invokes MAgPIE's run function
5. Reads `fulldata.gdx` and `report.mif` from the output directory
6. Writes key results as JSON to stdout

This bridge script isolates the adapter from MAgPIE's internal R ecosystem.

#### Step 3: Map parameters to MAgPIE cfg

MAgPIE configuration is controlled by `config/default.cfg` (an R source file defining a `cfg` list). The bridge script must:
- Set `cfg$gms$factor_costs` realization to one that supports cost multipliers
- Inject fertilizer price shocks as scenario-specific parameter overrides
- Set regional water constraints for MENA regions
- Configure output reporting to include the variables we need

#### Step 4: Implement `extract_results()`

Parse MAgPIE outputs:

| Output variable | MAgPIE source | Unit |
|---|---|---|
| Agricultural production by crop | `report.mif` → `Production|*` | Mt/yr |
| Food prices | `report.mif` → `Prices|*` | $/t |
| Land use change | `report.mif` → `Land Cover|*` | Mha |
| Fertilizer demand | `fulldata.gdx` → relevant variable | Mt N/yr |
| Water use | `report.mif` → `Water|*` | km³/yr |

#### Step 5: Validation

- [ ] Run MAgPIE baseline and verify convergence
- [ ] Run with 50% fertilizer price shock, verify production decreases
- [ ] Run with 30% MENA water reduction, verify irrigation land decreases
- [ ] Verify output parsing matches expected magnitudes from MAgPIE documentation

### 4.6 Deliverables

1. Refactored `src/models/fertilizer/magpie.py` inheriting from `RAdapter`
2. Bridge R script (`src/models/fertilizer/magpie_bridge.R`)
3. MAgPIE scenario configuration template (`configs/model_configs/magpie_hormuz.cfg`)
4. Parameter mapping documentation
5. Integration test with mock R subprocess output

---

## 5. NEMS Integration Plan

### 5.1 Model Architecture (as-is)

NEMS is a massive integrated energy-economy model with 16 modules that iterate to convergence. A single run takes ~20 hours and produces ~30 GB of output. The codebase spans Fortran, AIMMS, Python, GAMS, and batch scripts.

**This model cannot be run on-demand within the LangChain pipeline in its monolithic form.**

### 5.2 Integration Strategy: Submodule Extraction or Output Ingestion

Three viable approaches, in order of preference:

#### Option A: Pre-computed baseline ingestion (lowest effort, most practical)

Run NEMS independently for each scenario (outside the pipeline), then have the adapter ingest the pre-computed output tables. The adapter becomes a **data reader**, not a model runner.

- The adapter reads NEMS output files (FTables, CSV exports, `validator_report.xlsx`)
- Scenario-specific NEMS runs are prepared and executed by energy analysts separately
- The pipeline consumes results but does not control execution

This aligns with the paper's framework: NEMS provides baseline projections that other models perturb.

#### Option B: LFMM submodule integration (medium effort)

The Liquid Fuels Market Module (LFMM) is the most relevant NEMS component for Hormuz scenarios. It is implemented in GAMS and could potentially be extracted and run standalone:

- `Models/LNG/NEMS-main/NEMS-main/models/lfmm/source/*.gms` — GAMS model files
- `Models/LNG/NEMS-main/NEMS-main/models/lfmm/input/*.gdx` — input data

If LFMM can be run standalone (feeding it price paths rather than receiving them from the NEMS integrating module), it could be wrapped with `GAMSAdapter`.

**This requires analysis of LFMM's data dependencies** — does it read from the NEMS central database, or can it operate independently?

#### Option C: Full NEMS via SubprocessAdapter (highest effort)

Wrap the full NEMS execution via `SubprocessAdapter`:
1. Write scenario input overrides to NEMS's case configuration
2. Invoke `RunNEMS.bat` via subprocess
3. Monitor for convergence (poll output files)
4. Read results after completion

**Constraints:**
- 20+ hours per run — incompatible with interactive pipeline use
- Requires Windows with Intel Fortran, AIMMS, and full NEMS setup
- ~30 GB disk per run
- Must be run as a background/batch job, not inline

### 5.3 Recommended Approach

**Start with Option A** (output ingestion). This gets NEMS results into the pipeline immediately without the infrastructure overhead. Implement Option B (LFMM extraction) as a follow-up if standalone LFMM execution proves feasible.

### 5.4 Integration Steps (Option A)

#### Step 1: Define NEMS output schema

Identify the specific NEMS output variables needed by the pipeline:

| Output variable | NEMS source | Use in pipeline |
|---|---|---|
| Oil price path (WTI) | Output tables | Feed to commodity models as baseline |
| Natural gas price (Henry Hub) | Output tables | Feed to GGM, LNG models |
| GDP growth trajectory | MAM output | Short-run macro synthesis |
| Sectoral energy demand | Demand module outputs | Cross-model consistency |
| Electricity prices | EMM output | Infrastructure cost analysis |
| Refinery utilization | LFMM output | Oil supply disruption analysis |

#### Step 2: Implement output reader

The adapter reads pre-computed NEMS outputs from a configured directory:

```python
class NEMSAdapter(SubprocessAdapter):
    def execute(self, inputs: Any) -> ModelOutput:
        output_dir = Path(inputs["nems_output_dir"])
        if not output_dir.exists():
            raise FileNotFoundError(
                f"NEMS output directory not found: {output_dir}. "
                "Run NEMS externally and point to the output directory."
            )
        return self.parse_outputs(self._read_nems_outputs(output_dir))
```

#### Step 3: Build NEMS output parser

Parse NEMS's output formats:
- FTables (fixed-format Fortran output)
- CSV exports (if available)
- `validator_report.xlsx` (summary validation report)
- Python reporter outputs (`models/reporter/`)

#### Step 4: Validation

- [ ] Obtain at least one completed NEMS run output set
- [ ] Verify parser extracts correct values for all required variables
- [ ] Compare extracted values against known AEO2025 reference projections

### 5.5 Deliverables

1. Refactored `src/models/macro/nems.py` with output ingestion mode
2. NEMS output parser utilities
3. NEMS output schema documentation
4. Sample output data for testing (anonymized if needed)

---

## 6. Cross-Cutting Integration Tasks

These tasks apply to all model integrations and should be addressed in parallel.

### 6.1 Align adapter inheritance hierarchy

| Adapter | Current base | Target base | Rationale |
|---|---|---|---|
| `GGMAdapter` | `ModelAdapter` | `GAMSAdapter` | GAMS/CPLEX model |
| `MAgPIEAdapter` | `ModelAdapter` | `RAdapter` | R orchestration entry point |
| `NEMSAdapter` | `ModelAdapter` | `SubprocessAdapter` | External execution / output ingestion |
| `WorldFertilizerAdapter` | `GAMSAdapter` | `GAMSAdapter` | Already correct |
| `LNGSTAdapter` | `ExcelAdapter` | `ExcelAdapter` | Already correct |

Other adapters without model code in `Models/` remain as stubs with `ModelAdapter` base until their codebases are obtained.

### 6.2 Configuration infrastructure

Create `configs/model_configs/` entries for each integrated model:

```yaml
# configs/model_configs/ggm.yaml
gams_system_dir: "C:/GAMS/46"
model_gms_path: "Models/LNG/GGM-20190509-open-source-final/GGM/main.gms"
solver: "CPLEX"
timeout_seconds: 7200
extra_defines:
  data: "SET-Nav"
  WEO: "NPS"
  SETNav: "Ref"
  last_yr: "2025"
```

```yaml
# configs/model_configs/magpie.yaml
r_script_path: "src/models/fertilizer/magpie_bridge.R"
r_executable: "Rscript"
timeout_seconds: 14400  # MAgPIE runs can take hours
r_libs_path: "Models/Fertilizer/magpie-master/magpie-master/renv/library"
```

```yaml
# configs/model_configs/nems.yaml
mode: "output_ingestion"
output_base_dir: "data/nems_outputs"
scenario_dirs:
  baseline: "AEO2025_Reference"
  scenario_a: "Hormuz_ScenarioA"
  scenario_b: "Hormuz_ScenarioB"
  scenario_c: "Hormuz_ScenarioC"
  scenario_d: "Hormuz_ScenarioD"
```

### 6.3 Registry updates

Update `build_default_registry()` in `registry.py` to:
1. Read model configs from `configs/model_configs/*.yaml`
2. Instantiate adapters with configs when available
3. Fall back to config-less stub instantiation for models without configs

### 6.4 Input parameter schema refinement

Each integration will reveal the actual parameters each model needs. Update the corresponding files in `src/parameters/model_specs/` (e.g., `lng.py`, `fertilizer.py`, `macro.py`) to match the real model input schemas discovered during integration.

### 6.5 Cross-model consistency definitions

As models are integrated, define specific consistency checks in `src/synthesis/consistency.py`:

| Check | Model A output | Model B output | Tolerance |
|---|---|---|---|
| LNG price | GGM regional prices | NEMS Henry Hub price | ±15% |
| Fertilizer demand | MAgPIE fertilizer use | World Fertilizer Model demand | ±20% |
| Oil price | NEMS WTI path | Fed Workhorse Oil Model | ±10% |

---

## 7. Implementation Sequence

### Phase 1: GGM (Weeks 1–3)

| Week | Task | Deliverable |
|---|---|---|
| 1 | Restore GGM data files; verify baseline GAMS run | Working GGM baseline |
| 1 | Rebase `GGMAdapter` onto `GAMSAdapter` | Refactored adapter |
| 2 | Build node/arc topology mapping for Persian Gulf | `ggm_topology.yaml` |
| 2 | Implement `populate_database()` with shock injection | Shock parameterization |
| 3 | Implement `extract_results()` with unit conversion | Output parsing |
| 3 | Integration tests through `ModelExecutor` | End-to-end test |

### Phase 2: MAgPIE (Weeks 3–6)

| Week | Task | Deliverable |
|---|---|---|
| 3–4 | Install MAgPIE dependencies; run baseline | Working MAgPIE baseline |
| 4 | Write bridge R script | `magpie_bridge.R` |
| 4–5 | Rebase `MAgPIEAdapter` onto `RAdapter` | Refactored adapter |
| 5 | Map scenario parameters to MAgPIE cfg | Parameter mapping |
| 5–6 | Implement output parsing (report.mif → JSON) | Output parsing |
| 6 | Integration tests | End-to-end test |

### Phase 3: NEMS Output Ingestion (Weeks 5–7)

| Week | Task | Deliverable |
|---|---|---|
| 5 | Obtain NEMS baseline output from AEO2025 run | Output dataset |
| 5–6 | Implement NEMS output parser | Parser utilities |
| 6 | Rebase `NEMSAdapter` with output ingestion mode | Refactored adapter |
| 7 | Integration tests; cross-model consistency checks with GGM | Consistency validation |

### Phase 4: Pipeline Integration (Week 7–8)

| Week | Task | Deliverable |
|---|---|---|
| 7 | Update registry to load configs and instantiate real adapters | Updated registry |
| 7 | Update parameter extraction specs to match real model inputs | Updated model_specs |
| 8 | End-to-end pipeline test: scenario → parameters → model runs → synthesis | Pipeline test |
| 8 | Define cross-model consistency checks | Consistency config |

---

## 8. Prerequisites & Blockers

### Software dependencies

| Dependency | Required for | Status |
|---|---|---|
| GAMS ≥ 50.1.0 | GGM, MAgPIE | **Needs license verification** |
| CPLEX solver | GGM | **Needs license verification** |
| CONOPT solver | MAgPIE | **Needs license verification** |
| `gamsapi` Python package | GGM, MAgPIE (if using GAMS API directly) | Install with `pip install gamsapi[transfer]` |
| R ≥ 4.3 + Rtools | MAgPIE | **Needs installation verification** |
| `renv` R package | MAgPIE dependency management | Included in MAgPIE repo |
| Intel Fortran Compiler | NEMS (full runs only) | Not needed for Option A |
| AIMMS | NEMS (full runs only) | Not needed for Option A |

### Data dependencies

| Data | Required for | Status |
|---|---|---|
| GGM Excel data files (`data/SET-Nav/*.xlsx`) | GGM | **Deleted from git — must restore** |
| MAgPIE input data (via `download_data.R`) | MAgPIE | Download from PIK servers |
| LPJmL biophysical data | MAgPIE | Bundled with MAgPIE data download |
| NEMS AEO2025 baseline outputs | NEMS | **Requires completed NEMS run** |

### Knowledge gaps

| Gap | Needed for | Resolution |
|---|---|---|
| GGM node/arc IDs for Persian Gulf infrastructure | GGM shock injection | Inspect `data.xlsx` network topology sheets |
| MAgPIE cfg structure for cost multipliers | MAgPIE shock injection | Read MAgPIE documentation + `config/default.cfg` |
| LFMM standalone feasibility | NEMS Option B | Analyze LFMM data dependencies in GAMS source |
| NEMS output file formats | NEMS output parsing | Analyze `scripts/Validator/` and reporter code |

---

## 9. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GAMS/CPLEX license unavailable | Medium | Blocks GGM and MAgPIE | Use GAMS Community Edition (limited size); or run on licensed server |
| GGM data files unrecoverable | Low | Blocks GGM | Data is from published 2019 open-source release; re-download from NTNU/DIW |
| MAgPIE data download fails | Low | Blocks MAgPIE | PIK maintains public data servers; contact magpie@pik-potsdam.de |
| MAgPIE baseline doesn't converge | Medium | Delays MAgPIE | Use known-good scenario config from `config/scenario_config.csv` |
| NEMS outputs unavailable | Medium | Blocks NEMS | Use AEO2025 published tables as proxy until real runs are available |
| `gamsapi` version mismatch | Medium | Runtime errors | Pin `gamsapi` version to match installed GAMS system version exactly |

---

## 10. Success Criteria

Integration is complete for each model when:

1. **The adapter runs end-to-end** through the `ModelExecutor` for at least one scenario
2. **Inputs are validated** with model-specific range checks (not just passthrough)
3. **Inputs are translated** into the model's native format (not passthrough)
4. **Outputs are parsed** into `ModelOutput` with correct units and variable names
5. **Convergence is checked** and non-convergence is properly reported
6. **Provenance is tracked** — every output links back to the specific inputs and run metadata
7. **The adapter works with the LangChain tool wrapping** in `tools.py`
8. **At least one cross-model consistency check** is defined and tested
