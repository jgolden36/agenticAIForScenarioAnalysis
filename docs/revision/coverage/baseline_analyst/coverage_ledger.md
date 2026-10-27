# Coverage ledger for run `baseline_analyst`

Grid: 34 models x 5 scenarios = 170 cells; 90 completed. Record source: `state`; upstream evidence: `full`.
Implementation-mode evidence for completed cells: recorded: 90 (`adapter_declared` means the run record carried no marker and the adapter's declared default mode was used).

## Matrix

| model | system | A | B | C | D | E |
|---|---|---|---|---|---|---|
| `messageix` | energy_systems | `n` | `n` | `n` | `n` | `n` |
| `osemosys` | energy_systems | `d` | `d` | `d` | `d` | `d` |
| `temoa` | energy_systems | `d` | `d` | `d` | `d` | `d` |
| `apsim` | fertilizer_agriculture | `R` | `R` | `R` | `R` | `R` |
| `capri` | fertilizer_agriculture | `s` | `s` | `s` | `s` | `s` |
| `futures` | fertilizer_agriculture | `R` | `R` | `R` | `R` | `R` |
| `gtap` | fertilizer_agriculture | `s` | `s` | `s` | `s` | `s` |
| `magpie` | fertilizer_agriculture | `d` | `d` | `d` | `d` | `d` |
| `simple_g` | fertilizer_agriculture | `s` | `s` | `s` | `s` | `s` |
| `world_fertilizer` | fertilizer_agriculture | `R` | `R` | `R` | `R` | `R` |
| `argonne_abm` | helium_semiconductors | `R` | `R` | `R` | `R` | `R` |
| `simrlfab` | helium_semiconductors | `x` | `x` | `x` | `x` | `x` |
| `world_helium_model` | helium_semiconductors | `R` | `R` | `R` | `R` | `R` |
| `energy_flux_gas_power` | lng | `F` | `F` | `F` | `F` | `F` |
| `energy_flux_lng_profits` | lng | `F` | `F` | `F` | `F` | `F` |
| `ggm` | lng | `c` | `c` | `c` | `c` | `c` |
| `lngst` | lng | `R` | `R` | `R` | `R` | `R` |
| `mam` | macroeconomic | `d` | `d` | `d` | `d` | `d` |
| `miragrodep` | macroeconomic | `l` | `l` | `l` | `l` | `l` |
| `mpsge_jl` | macroeconomic | `R` | `R` | `R` | `R` | `R` |
| `nems` | macroeconomic | `d` | `d` | `d` | `d` | `v` |
| `nrel` | macroeconomic | `R` | `R` | `R` | `R` | `R` |
| `opencge` | macroeconomic | `l` | `l` | `l` | `l` | `l` |
| `pycge` | macroeconomic | `R` | `R` | `R` | `R` | `R` |
| `bornstein_krusell_rebelo` | oil | `d` | `d` | `d` | `d` | `d` |
| `fed_oil` | oil | `R` | `R` | `R` | `R` | `R` |
| `marketsim` | oil | `R` | `R` | `R` | `R` | `R` |
| `poles_jrc` | oil | `R` | `R` | `R` | `R` | `R` |
| `ais_project` | shipping | `R` | `R` | `R` | `R` | `R` |
| `aisdb` | shipping | `R` | `R` | `R` | `R` | `R` |
| `cwatm` | water | `R` | `R` | `R` | `R` | `R` |
| `sahysmod` | water | `d` | `d` | `d` | `d` | `d` |
| `watergap2` | water | `c` | `c` | `c` | `c` | `c` |
| `weap_mena` | water | `R` | `R` | `R` | `R` | `R` |

Legend: `F` = completed, full upstream model; `I` = completed, published-output ingestion; `R` = completed, analytical reduction; `U` = completed, implementation mode not recorded; `v` = failed: input validation; `t` = failed: timeout; `x` = failed: runtime error; `l` = runtime or licence missing (JVM, GAMS, ...); `d` = data, binary or model tree missing; `c` = adapter config (YAML) not provided; `s` = typed stub (no execute path); `n` = not implemented (other); `g` = model not in registry; `p` = parameter extraction failed; `q` = no parameter-extraction record; `m` = parameters extracted but cell not in any manifest; `o` = executed, but record overwritten before synthesis (tier collision); `-` = no record anywhere

## Per scenario

| scenario | cells | completed | skip classes |
|---|---|---|---|
| swift_contained | 34 | 18 | missing_config: 2, missing_data_or_binary: 7, not_implemented_other: 1, runtime_error: 1, runtime_or_license_missing: 2, stub: 3 |
| prolonged_contained | 34 | 18 | missing_config: 2, missing_data_or_binary: 7, not_implemented_other: 1, runtime_error: 1, runtime_or_license_missing: 2, stub: 3 |
| swift_escalated | 34 | 18 | missing_config: 2, missing_data_or_binary: 7, not_implemented_other: 1, runtime_error: 1, runtime_or_license_missing: 2, stub: 3 |
| prolonged_escalated | 34 | 18 | missing_config: 2, missing_data_or_binary: 7, not_implemented_other: 1, runtime_error: 1, runtime_or_license_missing: 2, stub: 3 |
| infrastructure_collapse | 34 | 18 | missing_config: 2, missing_data_or_binary: 6, not_implemented_other: 1, runtime_error: 1, runtime_or_license_missing: 2, stub: 3, validation_failed: 1 |

## Models completed in every scenario

`weap_mena`, `cwatm`, `poles_jrc`, `marketsim`, `fed_oil`, `energy_flux_gas_power`, `energy_flux_lng_profits`, `lngst`, `world_helium_model`, `argonne_abm`, `world_fertilizer`, `apsim`, `futures`, `aisdb`, `ais_project`, `nrel`, `mpsge_jl`, `pycge`

## Scenarios completed per model

| model | scenarios |
|---|---|
| `weap_mena` | A, B, C, D, E |
| `sahysmod` | - |
| `watergap2` | - |
| `cwatm` | A, B, C, D, E |
| `bornstein_krusell_rebelo` | - |
| `poles_jrc` | A, B, C, D, E |
| `marketsim` | A, B, C, D, E |
| `fed_oil` | A, B, C, D, E |
| `energy_flux_gas_power` | A, B, C, D, E |
| `energy_flux_lng_profits` | A, B, C, D, E |
| `ggm` | - |
| `lngst` | A, B, C, D, E |
| `world_helium_model` | A, B, C, D, E |
| `argonne_abm` | A, B, C, D, E |
| `simrlfab` | - |
| `capri` | - |
| `magpie` | - |
| `simple_g` | - |
| `world_fertilizer` | A, B, C, D, E |
| `gtap` | - |
| `apsim` | A, B, C, D, E |
| `futures` | A, B, C, D, E |
| `aisdb` | A, B, C, D, E |
| `ais_project` | A, B, C, D, E |
| `nems` | - |
| `mam` | - |
| `nrel` | A, B, C, D, E |
| `mpsge_jl` | A, B, C, D, E |
| `opencge` | - |
| `pycge` | A, B, C, D, E |
| `miragrodep` | - |
| `osemosys` | - |
| `messageix` | - |
| `temoa` | - |

## Cells whose forwarded inputs cite an upstream model that did not complete in this run

| scenario | model | sources not run |
|---|---|---|
| swift_contained | `mpsge_jl` | aisdb+ais_project |
| prolonged_contained | `mpsge_jl` | aisdb+ais_project |
| swift_escalated | `mpsge_jl` | aisdb+ais_project |
| prolonged_escalated | `mpsge_jl` | aisdb+ais_project |
| infrastructure_collapse | `mpsge_jl` | aisdb+ais_project |
