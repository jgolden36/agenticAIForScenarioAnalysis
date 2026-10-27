# Anchor-only comparison for run `20260504_222710`

Anchors (completed in all 5 scenarios): `fed_oil`, `mam`, `mpsge_jl`, `nrel`, `pycge`

## `oil_price_change_pct`

| scenario | `fed_oil` |
|---|---|
| A (swift_contained) | 54.79 |
| B (prolonged_contained) | 60.5 |
| C (swift_escalated) | 58.25 |
| D (prolonged_escalated) | 51.82 |
| E (infrastructure_collapse) | 48.36 |

## `peak_gdp_impact_pct`

| scenario | `fed_oil` |
|---|---|
| A (swift_contained) | -0.6164 |
| B (prolonged_contained) | -0.6806 |
| C (swift_escalated) | -0.6553 |
| D (prolonged_escalated) | -0.8258 |
| E (infrastructure_collapse) | -1.542 |

## `peak_cpi_impact_pp`

| scenario | `fed_oil` |
|---|---|
| A (swift_contained) | 1.096 |
| B (prolonged_contained) | 1.21 |
| C (swift_escalated) | 1.165 |
| D (prolonged_escalated) | 1.101 |
| E (infrastructure_collapse) | 2.055 |

## `gdp_impact_pct`

| scenario | `mpsge_jl` | `nrel` | `pycge` |
|---|---|---|---|
| A (swift_contained) | -0.025 | -0.0407 | -0.157 |
| B (prolonged_contained) | -0.8883 | -0.4494 | -0.8139 |
| C (swift_escalated) | -0.8695 | -0.4494 | -0.7889 |
| D (prolonged_escalated) | -1.431 | -0.6599 | -1.058 |
| E (infrastructure_collapse) | -1.036 | -0.5196 | -0.8636 |

## `cpi_inflation_pct`

| scenario | `mpsge_jl` | `nrel` | `pycge` |
|---|---|---|---|
| A (swift_contained) | 1.633 | 0.5093 | 1.346 |
| B (prolonged_contained) | 2.799 | 1.264 | 1.757 |
| C (swift_escalated) | 2.754 | 1.264 | 1.712 |
| D (prolonged_escalated) | 3.063 | 1.65 | 2.067 |
| E (infrastructure_collapse) | 2.661 | 1.299 | 1.794 |

## `natural_gas_price_change_pct`

| scenario | `nrel` |
|---|---|
| A (swift_contained) | 50.93 |
| B (prolonged_contained) | 126.4 |
| C (swift_escalated) | 126.4 |
| D (prolonged_escalated) | 126.4 |
| E (infrastructure_collapse) | 126.4 |

## `welfare_pct_change`

| scenario | `mpsge_jl` | `nrel` | `pycge` |
|---|---|---|---|
| A (swift_contained) | -0.6782 | -0.2445 | -0.6953 |
| B (prolonged_contained) | -2.008 | -0.9549 | -1.517 |
| C (swift_escalated) | -1.971 | -0.9549 | -1.474 |
| D (prolonged_escalated) | -2.656 | -1.32 | -1.884 |
| E (infrastructure_collapse) | -2.1 | -1.039 | -1.581 |

## Portfolio: scenarios in which each model completed

| model | anchor | scenarios |
|---|---|---|
| `ais_project` |  | B, C |
| `aisdb` |  | B, C |
| `apsim` |  | B, C |
| `cwatm` |  | C |
| `energy_flux_gas_power` |  | A, B, C |
| `fed_oil` | yes | A, B, C, D, E |
| `futures` |  | B, C |
| `lngst` |  | B, C |
| `mam` | yes | A, B, C, D, E |
| `marketsim` |  | A, B, C |
| `mpsge_jl` | yes | A, B, C, D, E |
| `nrel` | yes | A, B, C, D, E |
| `poles_jrc` |  | A, C |
| `pycge` | yes | A, B, C, D, E |
| `weap_mena` |  | C |
| `world_fertilizer` |  | B, C |
| `world_helium_model` |  | B, C |
