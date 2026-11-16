# Synthesis fidelity audit for run `rev_20261102_llama8b_r2`

- Synthesized outcomes: **296** (259 numeric)
- Value match rate (any category): **1.0**; strict (exact / rounded / unit-scaled): **0.9305**
- Provenance-complete outcomes (sources ran, value strictly matched): **241** (0.9305)
- Prose numeric tokens matched: **367 / 371** (0.9892); how they restate the model value: {'exact': 308, 'sign_dropped': 48, 'x100': 11}
- Source ids repaired by canonicalisation: **0**; unresolved: **0**

## Outcomes by category

| category | count | meaning |
|---|---|---|
| non_numeric | 37 | value carries no number |
| exact | 241 | value equals the model output for the named variable |
| matched_other_key | 18 | equals a different output of the cited model |

## By scenario

| scenario | outcomes | numeric | matched | strict | categories |
|---|---|---|---|---|---|
| infrastructure_collapse | 56 | 52 | 52 | 52 | exact: 52, non_numeric: 4 |
| prolonged_contained | 50 | 47 | 47 | 47 | exact: 47, non_numeric: 3 |
| prolonged_escalated | 38 | 37 | 37 | 22 | exact: 22, matched_other_key: 15, non_numeric: 1 |
| swift_contained | 43 | 41 | 41 | 41 | exact: 41, non_numeric: 2 |
| swift_escalated | 109 | 82 | 82 | 79 | exact: 79, matched_other_key: 3, non_numeric: 27 |

## Numeric tokens in prose with no matching model output (first 100)

- prolonged_contained / `strait_closure_flag` (aisdb): `4`
- prolonged_escalated / `oil_price_shock_pct` (poles_jrc): `-1.5971`
- infrastructure_collapse / `gdp_growth_pct` (pycge): `0.63`
- infrastructure_collapse / `interest_rate_impact_pct` (pycge): `1.10`
