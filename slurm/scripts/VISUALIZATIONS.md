# Visualizations — Hormuz Pipeline

This document describes the visualization layer of the Agentic AI Crisis Analysis
Pipeline: what figures are produced, what each one shows, the data each consumes,
the files each emits, and how to run them.

The pipeline has **no web/Streamlit dashboard**. All visualization is produced by
two self-contained, matplotlib-based SLURM stage scripts that read the CSVs and
qualitative narratives written by the export stage and emit PNG figures plus a
single self-contained HTML dashboard (`index.html`) per run. Nothing here calls an
LLM — narrative text is taken verbatim from the export stage, so visualization is
fast, deterministic, and reproducible.

## Pipeline position

```
Module 4 synthesis  ─►  Stage 5: export_results.py  ─►  Stage 6: visualize_results.py
(JSON state)            (CSVs + qualitative *.md)        (PNG figures + index.html)

                                                     ┌► visualize_weekly_evolution.py
many weekly runs ───────────────────────────────────┘  (cross-week temporal figures)
```

| Script | Stage | Scope | Output root |
|---|---|---|---|
| `slurm/scripts/export_results.py` | 5 | Flatten one run's results to CSV + qualitative Markdown | `data/reports/<run_id>/csv/`, `.../qualitative/` |
| `slurm/scripts/visualize_results.py` | 6 | Visualize **one** run | `data/reports/<run_id>/figures/` |
| `slurm/scripts/visualize_weekly_evolution.py` | — | Visualize **many** weekly runs together (Module 6 temporal driver) | `data/reports/weekly_evolution/<batch_id>/` |

## Design principles (apply to both scripts)

- **Best-effort and idempotent.** Re-running overwrites the figure set but never
  mutates pipeline state. A run with no data simply produces fewer figures.
- **Graceful dependency degradation.** Each capability is behind an optional-import
  gate and downgrades to a documented fallback instead of failing the stage:
  - **matplotlib** missing → no PNGs; `index.html` still renders with embedded HTML
    tables built from the CSVs.
  - **markdown** missing → narrative blocks use a stdlib HTML fallback renderer.
  - **cartopy** missing → cartographic choropleths are skipped; the schematic
    (matplotlib-only) maps still render.
  - **pandas** is *not* required — CSV parsing uses the stdlib `csv` module.
- **No LLM calls.** All narrative text is taken verbatim from Stage 5 output.
- **Self-contained dashboard.** `index.html` embeds every figure as a base64 PNG, so
  it can be shipped off-cluster as a single file.

---

# Stage 6 — `visualize_results.py` (single run)

Consumes `data/reports/<run_id>/csv/*.csv` and `.../qualitative/*.md` (from Stage 5)
and writes a visualization bundle under `data/reports/<run_id>/figures/`.

### Run it

```bash
# Uses $HORMUZ_RUN_ID or a UTC timestamp when --run-id is omitted
python slurm/scripts/visualize_results.py --run-id 20260423_125906

# Skip the per-CSV time-series PNGs (faster on runs with many series)
python slurm/scripts/visualize_results.py --run-id 20260423_125906 --no-timeseries
```

| Argument | Default | Effect |
|---|---|---|
| `--run-id` | `$HORMUZ_RUN_ID` or current UTC timestamp | Which run under `data/reports/` to visualize |
| `--no-timeseries` | off | Skip per-CSV and cross-scenario time-series PNGs |

### Output layout

```
data/reports/<run_id>/figures/
├── *.png                              run-wide figures (see table below)
├── timeseries/
│   └── <scenario>__<model>__<series>.png    one per long-form CSV
├── crossscenario/
│   └── <model>__<series>.png                one per series shared by 2+ scenarios
└── index.html                         self-contained dashboard
```

### Run-wide figures

| Function | Output file | Chart | Reads | Shows |
|---|---|---|---|---|
| `plot_model_status_by_scenario` | `model_status_by_scenario.png` | Stacked bar | `model_status.csv` | completed / skipped / failed run counts per scenario |
| `plot_model_status_by_system` | `model_status_by_system.png` | Stacked bar | `model_status.csv` + model registry | same counts grouped by commodity system (falls back to `model_id` if the registry can't be built) |
| `plot_synthesis_outcomes_grid` | `synthesis_outcomes_grid.png` | Grid of grouped bars | `synthesis_outcomes.csv` | headline numerics, one panel per `(time_horizon, outcome_scope)`, bars grouped by scenario; panels with no parseable numbers show a "see qualitative narrative" note |
| `plot_quantitative_heatmap` | `quantitative_heatmap.png` | Heatmap | `quantitative_results.csv` | every scalar output across `(model.output_key)` rows × scenario columns, **per-row min-max normalised** so mixed units (USD/bbl, %) coexist; raw values annotated when the matrix is small |
| `plot_consistency_flags` | `consistency_flags.png` | Bar | `consistency_flags.csv` | cross-model consistency-flag counts by severity (only emitted when non-empty) |
| `plot_uncertainty_error_bars` | `uncertainty_error_bars.png` | Forest / error-bar grid | `uncertainty_bands.csv` | per `(model, output_key)` panel: scenario rows with p05–p95 (thin), p25–p75 (thick), median dot; panels ordered by widest band, capped at 24 |
| `plot_synthesis_outcomes_with_bands` | `synthesis_outcomes_with_bands.png` | Bar + whiskers | `quantitative_results.csv` (extended schema with `mean`/`p05`/`p95`) | top-8 widest-band `(model, output)` pairs as bars with asymmetric p05–p95 whiskers, grouped by scenario |

### Distributional & geographic figures

These are built from the regional/sectoral export tables. Native model regions are
rolled up to the fixed 10-bucket unified taxonomy
(`US, CHN, IND, EU, MENA_GCC, MENA_OTHER, SSA, LAC, ROW, GLOBAL`) via
`configs/region_crosswalk.yaml`.

| Function | Output file | Chart | Reads | Shows |
|---|---|---|---|---|
| `plot_regional_impact_heatmap` | `regional_impact_heatmap.png` | Heatmap (per-scenario panels) | `regional_outcomes_unified.csv` | "who is hit hardest": `(model, output, value_label)` rows × unified-region columns, one panel per scenario, per-row normalised on a diverging colormap |
| `plot_regional_distribution_per_scenario` | `regional_distribution_<scenario>.png` | Sorted horizontal bars | `regional_outcomes_unified.csv` | per-scenario signed regional impact for the most-covered series (prefers MIRAGRODEP welfare/GDP); red = negative, green = positive |
| `plot_sectoral_distribution_per_scenario` | `sectoral_distribution_<scenario>.png` | Horizontal bars (≤4 panels) | `sectoral_outcomes.csv` | per-scenario signed sectoral impacts |
| `plot_native_vs_unified_audit` | `regional_crosswalk_audit.png` | Bar w/ contributor labels | `regional_outcomes_native.csv` | sanity check: how many native ids rolled up into each unified region (spots where ROW hides many countries) |
| `plot_world_regional_map` | `world_regional_map.png` | Schematic bubble map | `regional_outcomes_unified.csv` | per-scenario world bubbles at region centroids; bubble area = \|value\|, colour = sign. **matplotlib-only, no GIS dependency** |
| `plot_gulf_chokepoint_map` | `gulf_chokepoint_map.png` | Schematic Gulf map | `regional_outcomes_unified.csv` + `synthesis_outcomes.csv` | Strait of Hormuz, oil/LNG terminals, desalination clusters, and MENA impact bubbles; panel header annotates headline supply-loss magnitudes (oil mb/d, LNG %, He %) |
| `plot_world_choropleth_map` | `world_choropleth_map.png` | Cartographic choropleth | `regional_outcomes_unified.csv` | **cartopy + Natural Earth 110m** world map; country polygons coloured by their unified-region value on a diverging colormap. Skipped if cartopy / the shapefile is unavailable |
| `plot_mena_choropleth_map` | `mena_choropleth_map.png` | Cartographic choropleth (zoom) | `regional_outcomes_unified.csv` | same data zoomed to MENA with per-country labels and the Strait of Hormuz marked — for the country-detail policy audience |

### Time-series figures

| Function | Output | Chart | Reads | Shows |
|---|---|---|---|---|
| `plot_timeseries_csvs` | `timeseries/<scenario>__<model>__<series>.png` | Line (numeric x) or grouped bar (categorical x) | `csv/raw/<scenario>/<model>__<series>.csv` | one figure per long-form series CSV; x-axis auto-detected (`year`/`period`/`step`/…). Bookkeeping series (`_upstream_overrides`, `__scalars`, etc.) are skipped |
| `plot_crossscenario_timeseries` | `crossscenario/<model>__<series>.png` | Multi-line overlay | same `csv/raw/...` tree | the headline "how do scenarios diverge?" view — every scenario's path for a given `(model, series)` overlaid on one chart; emitted only when a series exists in 2+ scenarios |

### The HTML dashboard — `index.html`

`write_index_html` assembles a single self-contained page (figures embedded as
base64; no external image links) with these sections, in order:

1. **Header + status badges** — completed/skipped/failed counts.
2. **Top-of-page synthesis** — `synthesis.md` rendered inline (if present).
3. **Run-wide figures** — status, outcomes grid, quantitative heatmap, consistency flags.
4. **Cross-scenario time series** — the divergence overlays.
5. **Distributional impacts** — choropleths, schematic maps, regional/sectoral
   distributions, and a top-5 gainers / bottom-5 losers ranking table.
6. **Quantitative tables** — collapsible previews of the headline CSVs.
7. **Executive overview** — `qualitative/user_executive_summary.md` (if present).
8. **Per-scenario blocks** — each scenario's narrative plus its time-series and
   regional/sectoral spotlight figures and distributional notes.
9. **Cross-scenario qualitative comparison** — `qualitative/cross_scenario.md` (if present).
10. **Artefact index (TOC)** — links to every generated PNG.

When matplotlib is unavailable the dashboard still renders with a banner and HTML
tables built from the CSVs (no images).

---

# Cross-week — `visualize_weekly_evolution.py` (temporal)

Companion to the Module 6 weekly news-driven re-analysis driver. Scans
`data/reports/` for `weekly_<YYYYMMDD>` runs, aggregates them into long-form CSVs,
and plots how the pipeline's predictions evolve week over week as new information
arrives.

### Run it

```bash
python slurm/scripts/visualize_weekly_evolution.py
python slurm/scripts/visualize_weekly_evolution.py --batch-id 20260504
```

| Argument | Default | Effect |
|---|---|---|
| `--batch-id` | `$HORMUZ_BATCH_ID` or UTC timestamp | Output folder tag |
| `--reports-root` | `data/reports` | Where to scan for `weekly_<YYYYMMDD>` runs |
| `--output-dir` | derived from batch id | Override output directory |
| `--top-quant` | `16` | Number of most-volatile model outputs to plot |
| `--top-divergence` | `6` | Number of highest-spread synthesis variables to plot |

### Output layout

```
data/reports/weekly_evolution/<batch_id>/
├── figures/
│   ├── synthesis_outcome_evolution__<scope>__<horizon>.png
│   ├── quantitative_evolution__top_movers.png
│   ├── model_status_evolution.png
│   ├── consistency_flags_evolution.png
│   ├── scenario_divergence__<variable>.png
│   └── index.html
└── csv/
    ├── synthesis_outcomes_long.csv
    ├── quantitative_long.csv
    ├── model_status_long.csv
    └── consistency_flags_long.csv
```

### Figures

| Function | Output file | Chart | Shows |
|---|---|---|---|
| `plot_synthesis_outcome_evolution` | `synthesis_outcome_evolution__<scope>__<horizon>.png` | Multi-panel line (one panel per outcome variable) | how each headline synthesis outcome moves across weeks, one file per `(scope, horizon)` |
| `plot_quantitative_top_movers` | `quantitative_evolution__top_movers.png` | Multi-panel line | the top-N (default 16) most-volatile model scalar outputs across weeks |
| `plot_model_status_evolution` | `model_status_evolution.png` | Stacked bar | completed/skipped/failed counts per week |
| `plot_consistency_flags_evolution` | `consistency_flags_evolution.png` | Stacked bar | consistency-flag severity counts per week |
| `plot_scenario_divergence` | `scenario_divergence__<variable>.png` | Multi-scenario overlay + spread band | for the highest-spread synthesis variables, each scenario's weekly path plus the per-week cross-scenario spread |
| `write_dashboard` | `index.html` | — | weekly HTML dashboard embedding all figures and linking the long-form CSVs |

---

# Stage 5 — `export_results.py` (the data the figures read)

Stage 6 cannot draw anything Stage 5 didn't export. `export_results.py` flattens one
run's Module 4 synthesis state into the CSVs the visualizers consume:

| CSV (`data/reports/<run_id>/csv/`) | Consumed by |
|---|---|
| `model_status.csv` | status bar charts, dashboard badges |
| `synthesis_outcomes.csv` | outcomes grid, gulf-map headline annotations |
| `quantitative_results.csv` | quantitative heatmap, uncertainty band bars |
| `uncertainty_bands.csv` | uncertainty error-bar grid (only when UQ is enabled) |
| `consistency_flags.csv` | consistency-flag bar (only when non-empty) |
| `regional_outcomes_unified.csv` | regional heatmap, distributions, all maps |
| `regional_outcomes_native.csv` | crosswalk audit |
| `sectoral_outcomes.csv` | sectoral distributions |
| `synthesis_distributions.csv` | per-scenario distributional notes in the dashboard |
| `raw/<scenario>/<model>__<series>.csv` | per-series and cross-scenario time-series PNGs |

It also writes qualitative Markdown under `data/reports/<run_id>/qualitative/`
(`<scenario>.md`, `cross_scenario.md`, `user_executive_summary.md`) and the
top-level `synthesis.md`, all of which the dashboard embeds.

```bash
python slurm/scripts/export_results.py --run-id 20260423_125906
python slurm/scripts/export_results.py --run-id 20260423_125906 --no-llm
```

---

# Optional dependencies

| Feature | Needs | If missing |
|---|---|---|
| All PNG figures | `matplotlib` | Skipped; `index.html` renders text + HTML tables |
| Markdown narrative rendering | `markdown` | Stdlib HTML fallback |
| Cartographic choropleths | `cartopy` + Natural Earth 110m (auto-downloaded, cached under `~/.local/share/cartopy/`) | Skipped; schematic maps still render |

The schematic maps (`world_regional_map.png`, `gulf_chokepoint_map.png`) deliberately
avoid any GIS dependency so the maps remain available on minimal/offline clusters.
