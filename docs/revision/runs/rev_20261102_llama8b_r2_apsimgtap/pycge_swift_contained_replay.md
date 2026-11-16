# PyCGE replay for `swift_contained`

Recorded inputs from `/home/dagolden/agenticAIForScenarioAnalysis/data/reports/rev_20261102_llama8b_r2`: applied shocks {'oil': 54.79, 'lng': 25.0, 'fertilizer': 0.0, 'helium': 0.0}, duration 0.4166666666666667 months, regime short_run. Recorded outputs: {'gdp_impact_pct': -0.157, 'cpi_inflation_pct': 1.3458, 'consumption_impact_pct': -0.6953, 'welfare_pct_change': -0.6953}.

Manuscript value under test: **-15.7** (gdp_impact_pct).

| code state | sha | date | gdp_impact_pct | cpi_inflation_pct | duration scaler | matches recorded run | matches manuscript | x100 reproduces manuscript | error |
|---|---|---|---|---|---|---|---|---|---|
| 4abd05b |  |  | None | None | None | None | None | None | fatal: not a git repository (or any parent up to mount point /)
Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set). |
| dae4dcd |  |  | None | None | None | None | None | None | fatal: not a git repository (or any parent up to mount point /)
Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set). |
| ded97cb |  |  | None | None | None | None | None | None | fatal: not a git repository (or any parent up to mount point /)
Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set). |
| working_tree |  |  | -0.157 | 1.3458 | 0.1 | True | False | True |  |

## Conclusion

Recorded run value: -0.157. Manuscript value: -15.7. No replayed code state produces the manuscript value directly from the recorded inputs. Code states whose output times 100 equals the manuscript value: working_tree (fraction-vs-percent rescaling hypothesis supported).

The real `cge_modeling` execution path standardises outputs as `(reform - base) / base * 100`; the analytical kernel already returns percent. A percent value treated as a fraction once therefore appears 100 times too large, which is the only transformation that links the two reported figures.
