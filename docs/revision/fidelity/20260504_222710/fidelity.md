# Synthesis fidelity audit for run `20260504_222710`

- Synthesized outcomes: **271** (265 numeric)
- Value match rate (any category): **0.9585**; strict (exact / rounded / unit-scaled): **0.9434**
- Provenance-complete outcomes (sources ran, value strictly matched): **248** (0.9358)
- Prose numeric tokens matched: **376 / 387** (0.9716); how they restate the model value: {'exact': 289, 'sign_dropped': 48, 'x100': 30, 'multiplier_to_pct': 9}
- Source ids repaired by canonicalisation: **22**; unresolved: **0**

## Outcomes by category

| category | count | meaning |
|---|---|---|
| non_numeric | 6 | value carries no number |
| exact | 250 | value equals the model output for the named variable |
| matched_other_key | 4 | equals a different output of the cited model |
| source_not_run | 4 | the cited model did not complete in this scenario |
| unmatched | 7 | no model output matches the value |

## By scenario

| scenario | outcomes | numeric | matched | strict | categories |
|---|---|---|---|---|---|
| infrastructure_collapse | 46 | 46 | 45 | 45 | exact: 45, unmatched: 1 |
| prolonged_contained | 29 | 29 | 29 | 28 | exact: 28, matched_other_key: 1 |
| prolonged_escalated | 52 | 52 | 48 | 48 | exact: 48, source_not_run: 4 |
| swift_contained | 96 | 93 | 92 | 92 | exact: 92, non_numeric: 3, unmatched: 1 |
| swift_escalated | 48 | 45 | 40 | 37 | exact: 37, matched_other_key: 3, non_numeric: 3, unmatched: 5 |

## Outcomes needing attention

| scenario | variable | source (raw) | value | category | detail |
|---|---|---|---|---|---|
| swift_contained | `mam` | `mam` | {'oil_price_path': [123.83, 80.0, 80.0,  | unmatched | 123.83: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched |
| prolonged_contained | `oil_price_shock_pct` | `mpsgel, pycge` | [60.5 (mpsgel), 60.5 (pycge)] | exact | source id repaired: mpsgel->mpsge_jl |
| prolonged_contained | `trade_cost_multiplier` | `mpsgel` | [1.1869 (mpsgel)] | exact | source id repaired: mpsgel->mpsge_jl |
| prolonged_contained | `oil_price_shock_pct` | `mpsg_jl, pycge` | [60.5, 60.5] | exact | source id repaired: mpsg_jl->mpsge_jl |
| prolonged_contained | `trade_cost_multiplier` | `mpsg_jl, ais_project` | [1.1869, 1.0] | matched_other_key | source id repaired: mpsg_jl->mpsge_jl |
| swift_escalated | `consumption_impact_pct_by_region` | `pycge` | {pycge: {'US': -1.8026, 'CHN': -2.6073,  | unmatched | -1.8026: unmatched; -2.6073: unmatched; -3.9016: unmatched; -3.9109: unmatched; 2.2851: unmatched; -0.8663: unmatched; -1.6193: unmatched; -1.9711: unmatched |
| swift_escalated | `welfare_pct_change_by_region` | `pycge` | {pycge: {'US': -1.8026, 'CHN': -2.6073,  | unmatched | -1.8026: unmatched; -2.6073: unmatched; -3.9016: unmatched; -3.9109: unmatched; 2.2851: unmatched; -0.8663: unmatched; -1.6193: unmatched; -1.9711: unmatched |
| swift_escalated | `equivalent_variation_pct_by_region` | `pycge` | {pycge: {'US': -1.8026, 'CHN': -2.6073,  | unmatched | -1.8026: unmatched; -2.6073: unmatched; -3.9016: unmatched; -3.9109: unmatched; 2.2851: unmatched; -0.8663: unmatched; -1.6193: unmatched; -1.9711: unmatched |
| swift_escalated | `terms_of_trade_pct_change_by_region` | `pycge` | {pycge: {'US': -0.0291, 'CHN': -0.1748,  | unmatched | -0.0291: unmatched; -0.1748: unmatched; -0.2913: unmatched; -0.233: unmatched; 0.5242: unmatched; 0.1748: unmatched; -0.2039: unmatched; -0.0583: unmatched; -0.0583: unmatched |
| swift_escalated | `bilateral_trade_flow_change_pct` | `pycge` | {pycge: {'MENA_GCC': {'CHN': -6.355, 'IN | unmatched | -6.355: unmatched; -5.607: unmatched; -4.112: unmatched; -3.738: unmatched |
| prolonged_escalated | `oil_price_shock_pct` | `poles_jrc` | 51.82 | source_not_run | 51.82: source_not_run |
| prolonged_escalated | `trade_cost_multiplier` | `aisdb` | 1.1869 | source_not_run | 1.1869: source_not_run |
| prolonged_escalated | `commodity_price_shocks` | `mpse_jl` | {'oil': 51.82, 'lng': 126.39090909090909 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `disruption_duration_months` | `mpse_jl` | 7.0 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `gdp_impact_pct` | `mpse_jl` | -1.4314 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `cpi_inflation_pct` | `mpse_jl` | 3.0628 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `consumption_impact_pct` | `mpse_jl` | -2.6565 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `welfare_pct_change` | `mpse_jl` | -2.6565 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `wage_impact_pct` | `mpse_jl` | 1.122 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `interest_rate_impact_pct` | `mpse_jl` | 1.1736 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `sectoral_output_pct_change` | `mpse_jl` | {'agriculture': -0.2101, 'industry': -0. | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `oil_price_shock_pct` | `poles_jrc` | 51.82 | source_not_run | 51.82: source_not_run |
| prolonged_escalated | `trade_cost_multiplier` | `aisdb` | 1.1869 | source_not_run | 1.1869: source_not_run |
| prolonged_escalated | `commodity_price_shocks` | `mpse_jl` | {'oil': 51.82, 'lng': 126.39090909090909 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `disruption_duration_months` | `mpse_jl` | 7.0 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `gdp_impact_pct` | `mpse_jl` | -1.4314 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `cpi_inflation_pct` | `mpse_jl` | 3.0628 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `consumption_impact_pct` | `mpse_jl` | -2.6565 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `welfare_pct_change` | `mpse_jl` | -2.6565 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `wage_impact_pct` | `mpse_jl` | 1.122 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `interest_rate_impact_pct` | `mpse_jl` | 1.1736 | exact | source id repaired: mpse_jl->mpsge_jl |
| prolonged_escalated | `sectoral_output_pct_change` | `mpse_jl` | {'agriculture': -0.2101, 'industry': -0. | exact | source id repaired: mpse_jl->mpsge_jl |
| infrastructure_collapse | `oil_price_path` | `mam` | [118.69, 113.16, 107.63, 102.11, 96.58,  | unmatched | 118.69: unmatched; 113.16: unmatched; 107.63: unmatched; 102.11: unmatched; 96.58: unmatched; 91.05: unmatched; 85.53: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched; 80.0: unmatched |

## Numeric tokens in prose with no matching model output (first 100)

- prolonged_contained / `gdp_impact_pct` (pycge, mpsge_jl): `8.139`
- prolonged_contained / `gdp_impact_pct` (pycge, mpsge_jl): `8.883`
- prolonged_contained / `gdp_impact_pct` (pycge, mpsge_jl, aisdb, ais_project): `8.139`
- prolonged_contained / `gdp_impact_pct` (pycge, mpsge_jl, aisdb, ais_project): `8.139`
- prolonged_contained / `gdp_impact_pct` (pycge, mpsge_jl, aisdb, ais_project): `8.883`
- prolonged_contained / `gdp_impact_pct` (pycge, mpsge_jl, aisdb, ais_project): `8.139`
- prolonged_contained / `cpi_inflation_pct` (pycge, mpsge_jl, aisdb, ais_project): `2.789`
- prolonged_contained / `consumption_impact_pct` (pycge, mpsge_jl, aisdb, ais_project): `2.078`
- prolonged_contained / `consumption_impact_pct` (pycge, mpsge_jl, aisdb, ais_project): `2.078`
- prolonged_contained / `welfare_pct_change` (pycge, mpsge_jl, aisdb, ais_project): `2.078`
- prolonged_contained / `welfare_pct_change` (pycge, mpsge_jl, aisdb, ais_project): `2.078`
