# Anchor-only comparison for run `rev_20261102_llama8b_r2`

Anchors (completed in all 5 scenarios): `ais_project`, `aisdb`, `apsim`, `argonne_abm`, `cwatm`, `fed_oil`, `futures`, `lngst`, `marketsim`, `mpsge_jl`, `nrel`, `poles_jrc`, `pycge`, `weap_mena`, `world_fertilizer`, `world_helium_model`

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
| A (swift_contained) | -0.0248 | -0.0407 | -0.157 |
| B (prolonged_contained) | -0.8845 | -0.4494 | -0.8139 |
| C (swift_escalated) | -0.8658 | -0.4494 | -0.7889 |
| D (prolonged_escalated) | -1.425 | -0.6599 | -1.058 |
| E (infrastructure_collapse) | -1.031 | -0.5196 | -0.8636 |

## `cpi_inflation_pct`

| scenario | `mpsge_jl` | `nrel` | `pycge` |
|---|---|---|---|
| A (swift_contained) | 1.619 | 0.5093 | 1.346 |
| B (prolonged_contained) | 2.785 | 1.264 | 1.757 |
| C (swift_escalated) | 2.74 | 1.264 | 1.712 |
| D (prolonged_escalated) | 3.046 | 1.65 | 2.067 |
| E (infrastructure_collapse) | 2.647 | 1.299 | 1.794 |

## `natural_gas_price_change_pct`

| scenario | `marketsim` | `nrel` | `world_fertilizer` |
|---|---|---|---|
| A (swift_contained) | 5 | 50.93 | 0 |
| B (prolonged_contained) | 20 | 126.4 | 25 |
| C (swift_escalated) | 20 | 126.4 | 25 |
| D (prolonged_escalated) | 20 | 126.4 | 25 |
| E (infrastructure_collapse) | 30 | 126.4 | 50 |

## `welfare_pct_change`

| scenario | `mpsge_jl` | `nrel` | `pycge` |
|---|---|---|---|
| A (swift_contained) | -0.6725 | -0.2445 | -0.6953 |
| B (prolonged_contained) | -1.998 | -0.9549 | -1.517 |
| C (swift_escalated) | -1.962 | -0.9549 | -1.474 |
| D (prolonged_escalated) | -2.643 | -1.32 | -1.884 |
| E (infrastructure_collapse) | -2.09 | -1.039 | -1.581 |

## Portfolio: scenarios in which each model completed

| model | anchor | scenarios |
|---|---|---|
| `ais_project` | yes | A, B, C, D, E |
| `aisdb` | yes | A, B, C, D, E |
| `apsim` | yes | A, B, C, D, E |
| `argonne_abm` | yes | A, B, C, D, E |
| `cwatm` | yes | A, B, C, D, E |
| `energy_flux_gas_power` |  | A, B, C, D |
| `fed_oil` | yes | A, B, C, D, E |
| `futures` | yes | A, B, C, D, E |
| `lngst` | yes | A, B, C, D, E |
| `marketsim` | yes | A, B, C, D, E |
| `mpsge_jl` | yes | A, B, C, D, E |
| `nrel` | yes | A, B, C, D, E |
| `poles_jrc` | yes | A, B, C, D, E |
| `pycge` | yes | A, B, C, D, E |
| `weap_mena` | yes | A, B, C, D, E |
| `world_fertilizer` | yes | A, B, C, D, E |
| `world_helium_model` | yes | A, B, C, D, E |
