# Coverage ledger for run `20260504_222710`

Grid: 34 models x 5 scenarios = 170 cells; 49 completed. Record source: `csv`; upstream evidence: `flags_only`.
Implementation-mode evidence for completed cells: adapter_declared: 44, output_marker: 5 (`adapter_declared` means the run record carried no marker and the adapter's declared default mode was used).

## Matrix

| model | system | A | B | C | D | E |
|---|---|---|---|---|---|---|
| `messageix` | energy_systems | `l` | `l` | `l` | `l` | `l` |
| `osemosys` | energy_systems | `d` | `d` | `d` | `d` | `d` |
| `temoa` | energy_systems | `d` | `d` | `d` | `d` | `d` |
| `apsim` | fertilizer_agriculture | `-` | `R` | `R` | `-` | `-` |
| `capri` | fertilizer_agriculture | `-` | `s` | `s` | `-` | `-` |
| `futures` | fertilizer_agriculture | `-` | `R` | `R` | `-` | `-` |
| `gtap` | fertilizer_agriculture | `s` | `s` | `s` | `s` | `s` |
| `magpie` | fertilizer_agriculture | `-` | `d` | `d` | `-` | `-` |
| `simple_g` | fertilizer_agriculture | `-` | `v` | `s` | `-` | `-` |
| `world_fertilizer` | fertilizer_agriculture | `-` | `R` | `R` | `-` | `-` |
| `argonne_abm` | helium_semiconductors | `-` | `-` | `-` | `-` | `-` |
| `simrlfab` | helium_semiconductors | `-` | `-` | `-` | `-` | `-` |
| `world_helium_model` | helium_semiconductors | `-` | `R` | `R` | `-` | `-` |
| `energy_flux_gas_power` | lng | `F` | `F` | `F` | `-` | `-` |
| `energy_flux_lng_profits` | lng | `v` | `v` | `v` | `-` | `-` |
| `ggm` | lng | `-` | `c` | `c` | `-` | `-` |
| `lngst` | lng | `-` | `R` | `R` | `-` | `-` |
| `mam` | macroeconomic | `I` | `I` | `I` | `I` | `I` |
| `miragrodep` | macroeconomic | `l` | `l` | `l` | `l` | `l` |
| `mpsge_jl` | macroeconomic | `R` | `R` | `R` | `R` | `R` |
| `nems` | macroeconomic | `d` | `d` | `d` | `d` | `v` |
| `nrel` | macroeconomic | `R` | `R` | `R` | `R` | `R` |
| `opencge` | macroeconomic | `x` | `x` | `x` | `x` | `x` |
| `pycge` | macroeconomic | `R` | `R` | `R` | `R` | `R` |
| `bornstein_krusell_rebelo` | oil | `d` | `-` | `d` | `-` | `-` |
| `fed_oil` | oil | `R` | `R` | `R` | `R` | `R` |
| `marketsim` | oil | `R` | `R` | `R` | `-` | `-` |
| `poles_jrc` | oil | `R` | `-` | `R` | `-` | `-` |
| `ais_project` | shipping | `-` | `R` | `R` | `-` | `-` |
| `aisdb` | shipping | `-` | `R` | `R` | `-` | `-` |
| `cwatm` | water | `-` | `-` | `R` | `-` | `-` |
| `sahysmod` | water | `-` | `-` | `d` | `-` | `-` |
| `watergap2` | water | `-` | `-` | `c` | `-` | `-` |
| `weap_mena` | water | `-` | `-` | `R` | `-` | `-` |

Legend: `F` = completed, full upstream model; `I` = completed, published-output ingestion; `R` = completed, analytical reduction; `U` = completed, implementation mode not recorded; `v` = failed: input validation; `t` = failed: timeout; `x` = failed: runtime error; `l` = runtime or licence missing (JVM, GAMS, ...); `d` = data, binary or model tree missing; `c` = adapter config (YAML) not provided; `s` = typed stub (no execute path); `n` = not implemented (other); `g` = model not in registry; `p` = parameter extraction failed; `q` = no parameter-extraction record; `m` = parameters extracted but cell not in any manifest; `o` = executed, but record overwritten before synthesis (tier collision); `-` = no record anywhere

## Per scenario

| scenario | cells | completed | skip classes |
|---|---|---|---|
| swift_contained | 34 | 8 | missing_data_or_binary: 4, record_missing: 17, runtime_error: 1, runtime_or_license_missing: 2, stub: 1, validation_failed: 1 |
| prolonged_contained | 34 | 14 | missing_config: 1, missing_data_or_binary: 4, record_missing: 8, runtime_error: 1, runtime_or_license_missing: 2, stub: 2, validation_failed: 2 |
| swift_escalated | 34 | 17 | missing_config: 2, missing_data_or_binary: 6, record_missing: 2, runtime_error: 1, runtime_or_license_missing: 2, stub: 3, validation_failed: 1 |
| prolonged_escalated | 34 | 5 | missing_data_or_binary: 3, record_missing: 22, runtime_error: 1, runtime_or_license_missing: 2, stub: 1 |
| infrastructure_collapse | 34 | 5 | missing_data_or_binary: 2, record_missing: 22, runtime_error: 1, runtime_or_license_missing: 2, stub: 1, validation_failed: 1 |

## Models completed in every scenario

`fed_oil`, `mam`, `nrel`, `mpsge_jl`, `pycge`

## Scenarios completed per model

| model | scenarios |
|---|---|
| `weap_mena` | C |
| `sahysmod` | - |
| `watergap2` | - |
| `cwatm` | C |
| `bornstein_krusell_rebelo` | - |
| `poles_jrc` | A, C |
| `marketsim` | A, B, C |
| `fed_oil` | A, B, C, D, E |
| `energy_flux_gas_power` | A, B, C |
| `energy_flux_lng_profits` | - |
| `ggm` | - |
| `lngst` | B, C |
| `world_helium_model` | B, C |
| `argonne_abm` | - |
| `simrlfab` | - |
| `capri` | - |
| `magpie` | - |
| `simple_g` | - |
| `world_fertilizer` | B, C |
| `gtap` | - |
| `apsim` | B, C |
| `futures` | B, C |
| `aisdb` | B, C |
| `ais_project` | B, C |
| `nems` | - |
| `mam` | A, B, C, D, E |
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
| swift_contained | `nrel` | lngst |
| swift_contained | `mpsge_jl` | lngst, world_helium_model |
| swift_contained | `pycge` | world_helium_model |
| prolonged_contained | `fed_oil` | poles_jrc |
| prolonged_contained | `mpsge_jl` | poles_jrc |
| prolonged_contained | `pycge` | poles_jrc |
| prolonged_escalated | `nrel` | lngst |
| prolonged_escalated | `mpsge_jl` | poles_jrc, lngst, world_fertilizer |
| prolonged_escalated | `pycge` | poles_jrc, world_fertilizer |
| infrastructure_collapse | `nrel` | lngst |
| infrastructure_collapse | `mpsge_jl` | poles_jrc, lngst, world_helium_model, world_fertilizer, cwatm |
| infrastructure_collapse | `pycge` | poles_jrc, world_helium_model, cwatm |

_Evidence limited to flagged overrides (consistency_flags.csv); unflagged forwarding is not visible from CSVs._
