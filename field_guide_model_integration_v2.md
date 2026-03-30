# LangGraph Multi-Model Orchestration: A 2026 Field Guide

**Focused on heterogeneous model integration for the Hormuz crisis pipeline**

---

## 1. The integration problem, concretely

The CLAUDE.md specifies 30+ domain models spanning seven commodity systems plus macroeconomics, written in at least six execution environments: native Python, Julia (MPSGE.jl), GAMS (World Fertilizer Model, POLES-JRC), Excel/spreadsheets (LNGST, MarketSim), AnyLogic (Argonne Helium ABM), and R (various statistical models). Many model inventory entries have platform marked "—", meaning the execution environment is unknown until you actually obtain the model code. The `ModelAdapter` base class in `src/models/base.py` must therefore be designed around a common interface that accommodates each of these environments without assumptions about Python-nativeness.

This guide covers the current (March 2026) state of each integration layer: how LangGraph orchestrates, how each external environment connects, and where the real production gotchas lie.

---

## 2. LangGraph orchestration layer (compact reference)

**LangGraph 1.1.0** (March 10, 2026) is the current stable release. The key APIs relevant to this pipeline:

### State management

`StateGraph` accepts `state_schema` (TypedDict recommended), optional `input_schema`/`output_schema`, and `context_schema` for immutable runtime config. TypedDict is officially recommended over Pydantic BaseModel for internal state — partial updates are natural, no runtime validation overhead per transition. Use Pydantic at system boundaries (input validation, output serialization).

Each state key has an independent **reducer**. Without one, last-write wins. `Annotated[list, operator.add]` accumulates parallel outputs. Custom reducers have signature `(current, new) → merged`. For the `OverallSimulationState`, this means commodity model outputs can accumulate into `Annotated[list[dict], operator.add]` while scalar fields like `synthesis` use last-write-wins.

### Human-in-the-loop

The `interrupt()` function (from `langgraph.types`) is the production HITL primitive. It pauses execution, saves a checkpoint, and surfaces a payload to the caller. Resume with `Command(resume=value)`. The three mandatory HITL checkpoints in Algorithm 1 (post-scenario-generation, post-parameter-extraction, post-synthesis) each become an `interrupt()` call in the corresponding graph node. Critical rules: never wrap in try/except, ensure side effects before the interrupt are idempotent (the node re-executes from the top on resume).

**Checkpointer backends**: PostgresSaver (recommended for multi-instance), RedisSaver (v0.4.0, March 2026, with TTL), SqliteSaver (single-server development).

### Parallel execution (fan-out / fan-in)

The `Send` API handles dynamic fan-out. For the commodity-level modeling phase, where oil, LNG, fertilizer, helium, and water models run concurrently:

```python
from langgraph.constants import Send

def dispatch_commodity_models(state):
    """Fan-out: launch all commodity model adapters in parallel."""
    return [
        Send("run_model", {"scenario_id": state["scenario_id"], "model_id": mid, "params": p})
        for mid, p in state["commodity_params"].items()
    ]

builder.add_conditional_edges("commodity_supervisor", dispatch_commodity_models, ["run_model"])
```

Each `Send` creates an independent execution. Results merge via reducers. Order is non-deterministic — include sort keys if ordering matters. Concurrency controllable via `{"configurable": {"max_concurrency": N}}`.

### Hierarchical supervisors

The `langgraph-supervisor` package (v0.0.31) provides `create_supervisor()`, but the LangGraph team now recommends **manual tool-based supervisors** for production — finer context control. For this pipeline's four-level hierarchy (Scenario Controller → Conflict/Commodity/Macro Supervisors → Worker agents), each sub-team is a compiled subgraph passed as an agent to the level above.

**`Command` objects** (from `langgraph.types`) combine state updates and routing: `Command(goto="next_node", update={"key": "value"})`. For subgraph-to-parent handoffs, use `graph=Command.PARENT`.

### Error recovery

Cyclic edges enable self-correction. The pattern: store `error_count` and `last_error` in state, use try/except in model execution nodes, route via conditional edges back to the supervisor with error context. `RetryPolicy` handles transient failures (network, rate limits) automatically. For solver non-convergence (the GAMS/Julia failure mode), the application-level loop is the right pattern — the supervisor receives the error trace and adjusts parameters before re-invoking.

---

## 3. The ModelAdapter interface and execution patterns

The CLAUDE.md defines a clean adapter contract:

```python
class ModelAdapter(ABC):
    @abstractmethod
    def validate_inputs(self, params: ModelParameterSet) -> ValidationResult: ...
    @abstractmethod
    def translate_inputs(self, params: ModelParameterSet) -> Any: ...
    @abstractmethod
    def execute(self, inputs: Any) -> ModelOutput: ...
    @abstractmethod
    def parse_outputs(self, raw: Any) -> ModelOutput: ...
    
    @property
    @abstractmethod
    def model_id(self) -> str: ...
    @property
    @abstractmethod
    def commodity_system(self) -> CommoditySystem: ...
    @property
    @abstractmethod
    def analytical_level(self) -> AnalyticalLevel: ...
```

The key design decision is how `execute()` dispatches to each runtime. Below is the integration pattern for each execution environment, with current API details and production gotchas.

---

## 4. Python-native models

**Applies to:** OpenCGE, pycge/cge_modeling, SimRLFab, futures forecasting models, the internal agenticAI/models pipeline (TimeSeriesTransformer.py, joint_model.py, SFT.py, etc.)

### Pattern: direct import

The simplest case. The adapter imports the model code and calls it as a Python function. The `execute()` method constructs the model's expected input format (typically NumPy arrays or Pandas DataFrames), calls the computation, and parses outputs.

```python
class OpenCGEAdapter(ModelAdapter):
    def execute(self, inputs: dict) -> ModelOutput:
        from opencge import solve_cge  # or whatever the actual API is
        result = solve_cge(
            shock_vector=inputs["shock_vector"],
            base_year=inputs["base_year"],
            # ...
        )
        return self.parse_outputs(result)
```

### The internal ML pipeline (agenticAI/models)

The orchestration doc describes a sequential sub-pipeline: data prep → semantic embedding (RoBERTa) → time series forecasting (8-layer encoder/decoder transformer) → cascaded reasoning (Llama-2-7b / GPT-2 Medium). The key architectural decisions:

**LoRA-adapted models (Llama-2-7b, Llama-3-8b)**: The orchestration doc correctly identifies that these should be hosted as persistent local endpoints rather than loaded per tool call. The ~8.38M trainable parameters (targeting q_proj and v_proj) are on top of multi-billion-parameter base models — cold-loading is prohibitive. Options:

- **vLLM or text-generation-inference** as a local server, with the adapter calling the HTTP API
- **A dedicated LangChain custom LLM wrapper** that points to the local endpoint
- For the GPT-2 Medium joint model, the model is small enough (~355M params) that direct loading per call is viable, but a persistent server is still preferable if the model runs repeatedly across scenarios

**The joint_model.py dual-output problem**: The joint model produces both a numerical forecast vector and a textual reasoning string in a single forward pass. The adapter's `parse_outputs()` method must implement a deterministic separator — either a structured output format (JSON with `prediction` and `reasoning` keys) or a regex-based split on a known delimiter. This is where validity matters: the numerical vector must pass through to the pipeline state without LLM modification.

### Gotchas for Python-native models

- **Dependency isolation**: Different Python models may require conflicting package versions. If this becomes a problem, use subprocess calls to separate Python environments rather than fighting import conflicts.
- **GPU contention**: The TimeSeriesTransformer and LoRA models compete for GPU memory. The executor should serialize GPU-dependent models within a level, even if other (CPU) models parallelize.
- **Reproducibility**: Set random seeds explicitly in `translate_inputs()` and log them in execution metadata.

---

## 5. Julia integration (MPSGE.jl, CGE models)

**Applies to:** MPSGE.jl / GTAP CGE

### PythonCall.jl / juliacall: current state

**PythonCall.jl v0.9.31** (December 2025) is actively maintained. It requires Python ≥ 3.10 and Julia ≥ 1.10, and is the clear successor to the deprecated PyJulia (which had persistent issues with statically-linked Python builds). Install with `pip install juliacall`; JuliaPkg auto-manages Julia package dependencies.

### Pattern A: in-process via juliacall (recommended for performance)

```python
class MPSGEAdapter(ModelAdapter):
    _jl = None  # class-level Julia runtime (singleton)
    
    @classmethod
    def _ensure_julia(cls):
        if cls._jl is None:
            from juliacall import Main as jl
            jl.seval("using MPSGE")
            cls._jl = jl
        return cls._jl
    
    def execute(self, inputs: dict) -> ModelOutput:
        jl = self._ensure_julia()
        # Pass shock vectors as numpy arrays — juliacall wraps without copying
        result = jl.seval("solve_mpsge")(
            inputs["shock_vector"],     # numpy array → Julia array (zero-copy)
            inputs["elasticities"],
            inputs["config_path"],
        )
        # Convert back to Python
        import numpy as np
        welfare = np.asarray(result.welfare)  # zero-copy view
        return self.parse_outputs({
            "welfare": welfare,
            "prices": np.asarray(result.prices)
        })
```

**Zero-copy array transfer works reliably** for supported numeric types (Bool, IntXX, UIntXX, FloatXX, Complex). `numpy.asarray(julia_array)` yields a view. In reverse, Julia's `PyArray(numpy_array)` wraps without copying.

### Critical juliacall gotchas

1. **Import order is the #1 production issue**: Import juliacall BEFORE torch, matplotlib, or any C-extension library. `libstdc++` version conflicts between Julia and other libraries cause heap corruption that manifests as random segfaults. In the pipeline, this means the Julia adapter module must be imported at startup, before any ML model loading.

2. **First-call JIT latency**: The first call to any Julia function incurs seconds of compilation time. For production, use custom sysimages (`PackageCompiler.jl`) that pre-compile MPSGE.jl. This eliminates JIT latency entirely but requires a build step.

3. **Nested arrays**: `Vector{Vector{Int64}}` produces NumPy object arrays, not numeric dtypes. Always return flat or matrix-shaped results from Julia.

4. **Library boundary conversions**: Many Python libraries check `isinstance(x, np.ndarray)` and reject juliacall's `ArrayValue` wrapper. Always call `.to_numpy()` before passing to Pandas, scikit-learn, etc.

5. **GC is thread-safe** since v0.9.22 (August 2024). The old `PythonCall.GC.disable()` workaround is no longer needed.

6. **Batch work into larger Julia calls**: Per-call marshalling overhead is ~10-15%. For CGE solves that take seconds+, this is negligible. For many small calls, it's significant. Structure the Julia-side API to accept a full scenario parameterization and return a full result set in one call.

### Pattern B: subprocess (fallback)

If juliacall causes environment conflicts (particularly with torch), fall back to subprocess:

```python
def execute(self, inputs: dict) -> ModelOutput:
    import json, subprocess, tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(inputs, f)
        input_path = f.name
    
    result = subprocess.run(
        ["julia", "--project=path/to/mpsge_env", "run_mpsge.jl", input_path],
        capture_output=True, text=True, timeout=self.config.timeout_seconds
    )
    if result.returncode != 0:
        raise ModelExecutionError(f"MPSGE.jl failed: {result.stderr}")
    
    output = json.loads(result.stdout)
    return self.parse_outputs(output)
```

Subprocess avoids all environment conflicts but loses zero-copy transfers and adds process startup + Julia JIT latency per call. Mitigate JIT with custom sysimages or a persistent Julia server process (DaemonMode.jl).

### Decision: juliacall vs subprocess

Use juliacall for the CGE models — they run infrequently (once per scenario), the solve time dominates any marshalling overhead, and zero-copy transfer of large matrices is a real advantage. Fall back to subprocess only if import-order conflicts with the ML pipeline prove intractable.

---

## 6. GAMS integration (optimization and PE models)

**Applies to:** World Fertilizer Model, POLES-JRC, Global Gas Model (GGM), and potentially CAPRI, MAgPIE, SIMPLE-G if implemented in GAMS

### gamsapi: current state

**GAMS 53.3.0** (March 18, 2026) is current. The **gamsapi 52.3.0** Python package provides two complementary APIs. Install with `pip install gamsapi[transfer]` for DataFrame support.

### The two GAMS Python APIs

**Control API** (`gams.control`): Handles execution. Core flow is `GamsWorkspace` → `GamsJob` → `.run()`. Supports creating jobs from `.gms` files, passing data via `GamsDatabase` objects, and parametric solving via `GamsModelInstance`.

**Transfer API** (`gams.transfer`): Handles high-performance data exchange via the `Container` class, centered on Pandas DataFrames. Read/write GDX files, construct sets and parameters programmatically, pass NumPy arrays with auto-generated indices.

### Pattern: Control API with dynamic data injection

```python
class WorldFertilizerAdapter(ModelAdapter):
    def execute(self, inputs: dict) -> ModelOutput:
        from gams import GamsWorkspace
        
        ws = GamsWorkspace(
            working_directory=self._get_run_dir(inputs["scenario_id"]),
            system_directory=self.config.gams_system_dir
        )
        
        # Create in-memory database for shock parameters
        db = ws.add_database()
        
        # Write scenario parameters as GAMS parameters
        shipping_param = db.add_parameter("shipping_reduction", 0)
        shipping_param.add_record().value = inputs["shipping_traffic_reduction_pct"]
        
        fertilizer_demand = db.add_parameter("demand_shock", 1)
        for region, shock in inputs["regional_demand_shocks"].items():
            fertilizer_demand.add_record(region).value = shock
        
        # Execute
        job = ws.add_job_from_file(self.config.model_gms_path)
        opt = ws.add_options()
        opt.defines["solver"] = inputs.get("solver", "CONOPT")
        
        job.run(gams_options=opt, databases=db)
        
        # Extract results
        results = {}
        for rec in job.out_db["equilibrium_price"]:
            results[rec.keys[0]] = rec.level
        
        return self.parse_outputs(results)
```

### Using the Transfer API for complex data exchange

For models with large multi-dimensional parameter sets, the Transfer API is cleaner:

```python
from gams.transfer import Container
import pandas as pd

# Build input data
m = Container()
regions = m.addSet("r", records=["USA", "EU", "MENA", "ASIA"])
commodities = m.addSet("c", records=["urea", "DAP", "potash"])

# Multi-dimensional parameter from DataFrame
shock_df = pd.DataFrame({
    "r": ["USA", "EU", "MENA", "ASIA"],
    "c": ["urea"] * 4,
    "value": [0.05, 0.12, 0.35, 0.28]
})
m.addParameter("supply_shock", ["r", "c"], records=shock_df)

# Write to GDX, pass to solver
m.write("scenario_inputs.gdx")
```

### Critical GAMS gotchas

1. **Version matching**: The `gamsapi` version MUST match the installed GAMS system version. A mismatch produces cryptic errors. Pin both in your dependency management.

2. **Thread safety**: `GamsWorkspace` objects are NOT thread-safe. For parallel execution of GAMS models across scenarios, use separate working directories per instance. The `executor.py` must allocate isolated temp directories.

3. **Solver availability**: Not all solvers ship with all GAMS licenses. CONOPT (nonlinear) and CPLEX (LP/MIP) are the workhorses. The adapter should validate solver availability at `validate_inputs()` time, not at execution time.

4. **Non-convergence detection**: GAMS returns model and solve status codes. A model status of 1 (optimal) or 2 (locally optimal) is acceptable; anything else should be captured and routed to the error recovery loop. The adapter must parse `job.out_db.get_model_status()` programmatically.

5. **No structured compilation error handling**: If the `.gms` file has syntax errors, gamsapi raises a generic exception. The adapter should capture the listing file (`.lst`) from the working directory for diagnostic purposes.

6. **GAMSPy alternative**: For models you're writing from scratch (not wrapping existing `.gms` files), GAMSPy (`pip install gamspy`) lets you define GAMS models entirely in Python syntax. This may be preferable for new commodity models but isn't viable for wrapping existing codebases like the World Fertilizer Model.

---

## 7. Excel/spreadsheet integration (LNGST, MarketSim)

**Applies to:** LNG Spreadsheet Tool (LNGST), MarketSim (BOEM), Energy Flux models if spreadsheet-based

### The two-library decision

| Requirement | openpyxl | xlwings |
|---|---|---|
| Runs without Excel installed | Yes | No |
| Linux/server deployment | Yes | No (Windows/macOS only) |
| Execute VBA macros | No | Yes |
| Trigger native recalculation | No | Yes |
| Formula evaluation | No (reads cached values only) | Yes (Excel engine) |

**This decision is critical for validity.** Many economic spreadsheet models use complex inter-sheet formula chains. If the model uses only cell values and you're injecting new inputs, openpyxl can read/write cell values — but it **cannot recalculate formulas**. It reads whatever value was cached when the file was last saved in Excel. If you change an input cell with openpyxl, the downstream formula results remain stale.

### Pattern A: openpyxl (headless, no recalculation)

Only viable if the model stores precomputed scenario results OR if you rebuild the calculation logic in Python:

```python
class LNGSTAdapter(ModelAdapter):
    def execute(self, inputs: dict) -> ModelOutput:
        from openpyxl import load_workbook
        
        # Work on a copy to preserve the original
        wb = load_workbook(self.config.workbook_path, data_only=False)
        ws = wb["Inputs"]
        
        # Inject scenario parameters into named cells
        ws["B4"] = inputs["lng_export_capacity_bcf_d"]
        ws["B5"] = inputs["war_risk_premium_pct"]
        ws["B6"] = inputs["rerouting_delay_days"]
        
        # WARNING: formulas in other sheets are NOT recalculated.
        # You must either:
        #   (a) reimplement the calculation logic in Python, or
        #   (b) use xlwings instead
        
        # If reading pre-computed outputs (data_only=True on a pre-calculated copy):
        wb_results = load_workbook(self.config.workbook_path, data_only=True)
        ttf_price = wb_results["Outputs"]["C12"].value
        
        return self.parse_outputs({"ttf_benchmark": ttf_price})
```

### Pattern B: xlwings (headless Excel, full recalculation)

Required when the model depends on Excel's calculation engine:

```python
class MarketSimAdapter(ModelAdapter):
    def execute(self, inputs: dict) -> ModelOutput:
        import xlwings as xw
        
        app = xw.App(visible=False)  # headless
        try:
            wb = app.books.open(str(self.config.workbook_path))
            
            # Inject parameters
            ws_in = wb.sheets["Scenario_Inputs"]
            ws_in.range("B4").value = inputs["oil_supply_shock_mbpd"]
            ws_in.range("B5").value = inputs["price_elasticity"]
            
            # Trigger full recalculation
            app.calculate()
            
            # If VBA macros need to run:
            # wb.macro("RunSimulation")()
            
            # Extract results
            ws_out = wb.sheets["Results"]
            consumer_surplus = ws_out.range("D20").value
            price_path = ws_out.range("B30:B42").value  # returns list of lists
            
            return self.parse_outputs({
                "consumer_surplus": consumer_surplus,
                "price_path": [row[0] for row in price_path]
            })
        finally:
            wb.close()
            app.quit()
```

### Critical Excel gotchas

1. **xlwings requires Excel installed**: This means Windows or macOS with a licensed Excel installation. It will NOT work on Linux servers or in Docker containers without significant workarounds (Wine, which is unreliable). If your compute environment is Linux, you must either (a) reimplement the spreadsheet logic in Python, (b) use LibreOffice via subprocess as a partial substitute, or (c) run the Excel adapters on a Windows node.

2. **Concurrent xlwings sessions**: Each `xw.App()` instance launches a separate Excel process. Multiple simultaneous instances work but consume significant memory. For parallel scenario runs, limit concurrency.

3. **Cell reference fragility**: Hardcoded cell references (e.g., `"B4"`) break when the spreadsheet structure changes. Use Excel named ranges where possible, and validate that expected named ranges exist in `validate_inputs()`.

4. **Floating-point comparisons**: Excel and Python may produce slightly different floating-point results for the same formula. The consistency checker should use tolerances, not exact equality, when comparing Excel model outputs to Python model outputs.

5. **File locking**: Excel locks the workbook file while open. The adapter must work on copies and ensure cleanup in `finally` blocks.

---

## 8. AnyLogic integration (Argonne Helium ABM)

**Applies to:** Argonne Helium ABM (agent-based model)

### Pattern: exported standalone Java application via CLI

AnyLogic Professional can export models as standalone Java applications that run without AnyLogic installed. The exported application is a JAR with a startup script (`.bat`/`.sh`). Command-line arguments can be passed, and an `.ini` file (`com.anylogic.engine.ini`) configures execution settings like headless mode and memory allocation.

```python
class ArgonneHeliumABMAdapter(ModelAdapter):
    def execute(self, inputs: dict) -> ModelOutput:
        import subprocess, json, os
        
        # Write inputs to a file the model reads
        run_dir = self._get_run_dir(inputs["scenario_id"])
        input_path = os.path.join(run_dir, "scenario_params.json")
        with open(input_path, 'w') as f:
            json.dump(inputs, f)
        
        # Run the exported Java application
        startup_script = os.path.join(
            self.config.model_dir,
            f"{self.config.model_name}_linux.sh"
        )
        result = subprocess.run(
            [startup_script, input_path],
            capture_output=True, text=True,
            timeout=self.config.timeout_seconds,
            cwd=self.config.model_dir,
            env={**os.environ, "JAVA_OPTS": f"-Xmx{self.config.max_memory_mb}m"}
        )
        
        if result.returncode != 0:
            raise ModelExecutionError(f"AnyLogic model failed: {result.stderr}")
        
        # Parse output file written by the model
        output_path = os.path.join(run_dir, "results.json")
        with open(output_path) as f:
            raw_output = json.load(f)
        
        return self.parse_outputs(raw_output)
```

### Critical AnyLogic gotchas

1. **Export requires AnyLogic Professional license**: The free Personal Learning Edition cannot export standalone applications. This is a hard constraint on who can prepare the model for pipeline use.

2. **The model must be instrumented for headless use**: The exported model needs to accept command-line parameters, run without GUI interaction, and write results to files. This typically requires modifications to the AnyLogic model itself — adding parameter-reading code and file-output code to the experiment's setup/teardown.

3. **AnyLogic Cloud as alternative**: If the model is hosted on AnyLogic Cloud, the adapter can use the Cloud REST API instead of local execution. This avoids the Java/JVM dependency but introduces network latency and requires Cloud access.

4. **Stochastic output**: Agent-based models are inherently stochastic. The adapter should run multiple replications (configurable) and return summary statistics (mean, confidence intervals), not single-run point estimates. This multiplies execution time significantly.

5. **JVM startup overhead**: Each subprocess call launches a JVM. For repeated runs, consider keeping a persistent JVM process or using AnyLogic Cloud's batch API.

---

## 9. R integration (statistical models)

**Applies to:** Various statistical/econometric models where the reference implementation is in R (specific models TBD based on the "—" platform entries in the inventory)

### Pattern: subprocess with rpy2 fallback

```python
class RModelAdapter(ModelAdapter):
    def execute(self, inputs: dict) -> ModelOutput:
        import subprocess, json, tempfile
        
        # Write inputs
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(inputs, f)
            input_path = f.name
        
        result = subprocess.run(
            ["Rscript", "--vanilla", self.config.r_script_path, input_path],
            capture_output=True, text=True,
            timeout=self.config.timeout_seconds
        )
        
        if result.returncode != 0:
            raise ModelExecutionError(f"R model failed: {result.stderr}")
        
        output = json.loads(result.stdout)
        return self.parse_outputs(output)
```

### rpy2 (in-process alternative)

```python
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
pandas2ri.activate()

ro.r.source(self.config.r_script_path)
result = ro.r["run_model"](inputs_df)  # R function, pandas DataFrame auto-converts
```

rpy2 avoids subprocess overhead but has the same kind of environment conflict risks as juliacall. Subprocess is the safer default.

---

## 10. The generic subprocess adapter

For models where the execution environment is unknown or unusual, a generic subprocess adapter handles the common case:

```python
class SubprocessModelAdapter(ModelAdapter):
    """Generic adapter for any model executable via command line."""
    
    def execute(self, inputs: dict) -> ModelOutput:
        import subprocess, json, os
        
        run_dir = self._get_run_dir(inputs.get("scenario_id", "default"))
        input_path = os.path.join(run_dir, "inputs.json")
        output_path = os.path.join(run_dir, "outputs.json")
        
        with open(input_path, 'w') as f:
            json.dump(self.translate_inputs_to_dict(inputs), f)
        
        cmd = self.config.command_template.format(
            input_path=input_path,
            output_path=output_path,
            run_dir=run_dir
        )
        
        result = subprocess.run(
            cmd.split(),
            capture_output=True, text=True,
            timeout=self.config.timeout_seconds,
            cwd=self.config.working_directory,
            env={**os.environ, **self.config.extra_env}
        )
        
        # Capture full execution metadata
        metadata = {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
        }
        
        if result.returncode != 0:
            raise ModelExecutionError(
                f"{self.model_id} failed (rc={result.returncode})",
                metadata=metadata
            )
        
        with open(output_path) as f:
            raw = json.load(f)
        
        return self.parse_outputs(raw, metadata=metadata)
```

The convention is: **inputs are JSON in, outputs are JSON out, communicated via temp files**. Any model can be wrapped in a thin script that reads JSON, runs the model, and writes JSON — regardless of its native language.

---

## 11. LangChain tool wrapping for model adapters

Each `ModelAdapter` becomes a LangChain tool via the `@tool` decorator with a Pydantic args schema. This is how the LangGraph agents invoke models:

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class CGEModelInput(BaseModel):
    scenario_id: str = Field(description="Scenario identifier (A, B, C, or D)")
    energy_price_shock: list[float] = Field(description="Price shock vector by sector")
    capital_destruction: float = Field(description="Fractional capital stock loss")
    trade_shift: list[float] = Field(description="Terms-of-trade shift by region")

@tool(args_schema=CGEModelInput)
def run_mpsge_model(
    scenario_id: str,
    energy_price_shock: list[float],
    capital_destruction: float,
    trade_shift: list[float]
) -> str:
    """Run MPSGE.jl CGE model with the given macroeconomic shock parameters."""
    adapter = model_registry.get("mpsge_jl")
    params = ModelParameterSet(
        scenario_id=scenario_id,
        parameters={
            "energy_price_shock": energy_price_shock,
            "capital_destruction": capital_destruction,
            "trade_shift": trade_shift
        }
    )
    result = adapter.validate_inputs(params)
    if not result.valid:
        return f"Validation failed: {result.errors}"
    
    translated = adapter.translate_inputs(params)
    output = adapter.execute(translated)
    return output.to_json()
```

**`with_structured_output()`** is used in the parameter extraction module (Module 2) to force Pydantic schema compliance from LLM outputs. It accepts a Pydantic BaseModel and returns validated instances. For OpenAI-compatible providers, it uses server-side constrained decoding. Known issue: `with_structured_output()` silently drops previously bound tools (langchain GitHub #35320) — for agents that need both tool calling and structured output, use the agent-level `response_format` parameter.

**`response_format="content_and_artifact"`** on the `@tool` decorator returns both a summary string (sent to the LLM for reasoning) and structured data (stored in `ToolMessage.artifact` for pipeline state). This is the right pattern for model execution tools: the LLM sees a human-readable summary while the full numerical output goes into state without LLM modification.

---

## 12. Cross-model consistency checking

The consistency module (`src/synthesis/consistency.py`) is not a formality. For models that should agree on the same variable:

- Oil price: Bornstein-Krusell-Rebelo (structural GE) vs. POLES-JRC (partial eq.) vs. Fed Workhorse Oil Model → should produce prices within a configurable tolerance band
- Fertilizer supply-demand: World Fertilizer Model vs. GTAP (CGE) → cross-check equilibrium quantities
- LNG trade flows: GGM vs. LNGST → volumes should be in the same range

Implementation should be **declarative**: a YAML config mapping pairs of (model_id, output_variable) to tolerance thresholds. The checker iterates over these pairs, computes deviations, and flags violations. This is deterministic computation — no LLM involvement.

---

## 13. Provenance and the no-fabrication constraint

The CLAUDE.md's constraint #3 ("The LLM must not fabricate quantitative results") requires that every number in the final synthesis traces to a model run. The provenance chain:

```
synthesis_result.value 
  → model_output.output_id 
    → model_execution.run_id (with inputs, metadata, timing)
      → parameter_set.extraction_id (with confidence levels)
        → scenario_narrative.scenario_id
```

The `ModelOutput` Pydantic schema should include a `run_id` (UUID), `model_id`, `scenario_id`, timestamp, and the full input parameters used. The synthesis module receives these and must pass numerical values through unmodified — the LLM generates narrative around the numbers but does not compute, interpolate, or modify them.

---

## 14. Summary: integration pattern decision matrix

| Execution environment | Primary pattern | Fallback | Key constraint |
|---|---|---|---|
| Python (OpenCGE, pycge, ML models) | Direct import | Subprocess to separate venv | GPU contention for ML models |
| Julia (MPSGE.jl) | juliacall (in-process) | Subprocess + sysimage | Import juliacall before torch |
| GAMS (Fertilizer, POLES-JRC, GGM) | gamsapi Control + Transfer | Subprocess CLI | Version-match gamsapi to GAMS; thread isolation |
| Excel (LNGST, MarketSim) | xlwings (if VBA/recalc needed) | openpyxl (read/write only) | Requires Excel installed; no Linux |
| AnyLogic (Argonne Helium ABM) | Subprocess (exported JAR) | AnyLogic Cloud REST API | Must pre-export; stochastic → multiple replications |
| R (various) | Subprocess (Rscript) | rpy2 (in-process) | Subprocess is safer default |
| Unknown ("—" platforms) | Generic subprocess adapter | Case-by-case | JSON in/out convention |
