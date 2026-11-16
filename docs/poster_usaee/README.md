# USAEE poster figures

Ten figures for the USAEE poster, each as a 300 dpi PNG and a vector PDF (use the PDF for print). All share one style: Segoe UI, scenario colours A blue, B orange, C aqua, D yellow, E pink, and the paper's markers († closed-form stand-in, ‡ published-output ingestion).

Regenerate with `python scripts/poster/make_poster_figures.py` (or `--only fig05 fig08`). The maps read `data/geo/*.geojson`, built once from Natural Earth by `scripts/poster/prep_geo.py`.

| File | What it shows | Data | Suggested poster spot |
|---|---|---|---|
| `fig01_hormuz_map` | The strait, oil and LNG terminals, desalination plants, bypass pipelines, Bab el-Mandeb | Natural Earth; EIA Today in Energy (2024 flows) | Hero image, top left |
| `fig02_scenario_matrix` | 2 × 2 matrix + tail-risk E with oil impulse, US GDP trough, US CPI peak | May run, `fed_oil` (oil forwarded from POLES slot) | Scenarios panel |
| `fig03_pipeline_architecture` | Algorithm 1: LLM vs deterministic steps, three analyst checkpoints, forwarding tiers | Design (CLAUDE.md) | Methods panel |
| `fig04_model_network` | 35 adapters by tier, 51 cross-tier forwarding links, shade = implementation mode | `configs/upstream_forwarding_mapping.yaml`, `docs/revision/model_inventory.json` | Methods panel |
| `fig05_gdp_by_scenario` | GDP by scenario from three macro reductions, plus the Scenario E water replay | May run; `scenario_e_input_replay.json` | Results |
| `fig06_us_macro_irf` | US GDP, CPI, fed funds and unemployment impulse responses, 5 scenarios | May run, `fed_oil` series | Results |
| `fig07_regional_gdp_map` | World choropleth, Scenario D regional GDP | May run, `pycge` regional rows | Results (eye-catching) |
| `fig07b_regional_gdp_heatmap` | Regions × scenarios, values printed | Same | Results, or handout |
| `fig08_observed_vs_model` | Observed 2026 prices vs modelled peaks: Brent, TTF, Henry Hub, urea | World Bank Pink Sheet; May run | Validation / limitations |
| `fig09_provenance_chain` | Scenario C: LLM extracted 0, POLES-slot value 58.25 replaced it, flag kept | `REVIEWER_RESPONSE_RESULTS.md` R1.3 | Methods or "how it works" strip |
| `fig10_key_numbers` | Headline tiles: 35 adapters, 5 scenarios, 40 rules, 24/24 reproduced, 100% value match | Inventory, YAML, revision results | Banner under the title |

## Check before printing

These follow from `docs/revision/REVIEWER_RESPONSE_RESULTS.md`, which is still open on four "decide before citing" items.

- **Fig 5 and Scenario E.** The run shows E milder than D. The figure also plots the kernel replay with the framework's water damage (−1.26, below D's −1.06), labelled as a replay. If the authors decide not to show the replay, delete those lines in `fig05_gdp`; the footnote still says why E is understated.
- **Every quantitative panel uses closed-form stand-ins (†)**, not the named upstream models. Footnotes say so. Do not caption them as "POLES-JRC results" or "MPSGE.jl results".
- **Fig 4 shades show each adapter's default mode, not what ran in May.** In May only Energy Flux gas power ran as a full model, and MAM's cells held no macro data. Update after the supplementary full-model runs if they finish before the poster deadline.
- **Fig 10's "100%"** comes from the revision run with the fidelity validator on (Run A). May, without the validator, was 95.85%. The tile says "revision run".
- **Fig 8 is deliberately unflattering**: the stand-ins understate oil and TTF, and the LNGST reduction raises Henry Hub while it actually fell 35%. It is a plausibility check, not a forecast test.
- **Fig 2's B and C stats** come out close because B and C ran on similar extracted inputs (C's narrative ran 4 months against a "swift" 4–6 weeks). Disclosed in the revision document.
- Facility and pipeline positions on Fig 1 are approximate.
