# PyCGE replay for `swift_contained`

Recorded inputs from `data/20260504_222710`: applied shocks {'oil': 54.79, 'lng': 25.0, 'fertilizer': 0.0, 'helium': 0.0}, duration 0.4166666666666667 months, regime short_run. Recorded outputs: {'gdp_impact_pct': -0.157, 'cpi_inflation_pct': 1.3458, 'consumption_impact_pct': -0.6953, 'welfare_pct_change': -0.6953}.

Manuscript value under test: **-15.7** (gdp_impact_pct).

| code state | sha | date | gdp_impact_pct | cpi_inflation_pct | duration scaler | matches recorded run | matches manuscript | x100 reproduces manuscript | error |
|---|---|---|---|---|---|---|---|---|---|
| 4abd05b | 4abd05b | 2026-05-04 | -0.157 | 1.3458 | 0.1 | True | False | True |  |
| dae4dcd | dae4dcd | 2026-05-04 | -0.157 | 1.3458 | 0.1 | True | False | True |  |
| ded97cb | ded97cb | 2026-05-04 | -0.157 | 1.3458 | 0.1 | True | False | True |  |
| working_tree |  |  | -0.157 | 1.3458 | 0.1 | True | False | True |  |

## Conclusion

Recorded run value: -0.157. Manuscript value: -15.7. No replayed code state produces the manuscript value directly from the recorded inputs. Code states whose output times 100 equals the manuscript value: 4abd05b, dae4dcd, ded97cb, working_tree (fraction-vs-percent rescaling hypothesis supported).

The real `cge_modeling` execution path standardises outputs as `(reform - base) / base * 100`; the analytical kernel already returns percent. A percent value treated as a fraction once therefore appears 100 times too large, which is the only transformation that links the two reported figures.
