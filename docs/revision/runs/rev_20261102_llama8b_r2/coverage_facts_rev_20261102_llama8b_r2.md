# Coverage facts for run `rev_20261102_llama8b_r2`

Every cell in this ledger carries an execution record.

Scenario letters: A = swift_contained, B = prolonged_contained, C = swift_escalated, D = prolonged_escalated, E = infrastructure_collapse.

## Per model

- `world_helium_model` completed in ABCDE (analytical_reduction).
- `argonne_abm` completed in ABCDE (analytical_reduction).
- `simrlfab` completed in -; failed in ABCDE.
- `world_fertilizer` completed in ABCDE (analytical_reduction).
- `apsim` completed in ABCDE (analytical_reduction).
- `cwatm` completed in ABCDE (analytical_reduction).
- `weap_mena` completed in ABCDE (analytical_reduction).
- `sahysmod` completed in -; failed in ABCDE.
- `lngst` completed in ABCDE (analytical_reduction).
- `energy_flux_lng_profits` completed in -; failed in ABCDE.
- `nems` completed in -; skipped in ABCD; failed in E.
- `mam` completed in -; skipped in ABCDE.
- `poles_jrc` completed in ABCDE (analytical_reduction).
- `fed_oil` completed in ABCDE (analytical_reduction).
- `pycge` completed in ABCDE (analytical_reduction).
- `mpsge_jl` completed in ABCDE (analytical_reduction).
- `nrel` completed in ABCDE (analytical_reduction).

## Helium and fertilizer linkages

- The helium linkage (world_helium_model -> argonne_abm / simrlfab / macro) was model-computed in scenarios ABCDE.
- The fertilizer linkage (world_fertilizer -> apsim / macro) was model-computed in scenarios ABCDE.

## Water linkage under the tail-risk scenario

Under the infrastructure-collapse scenario the macro CGEs that list a water model among their upstream sources are: pycge, mpsge_jl; their water shock was model-computed.

| model | status under E | upstream sources |
|---|---|---|
| cwatm | completed | |
| weap_mena | completed | |
| sahysmod | failed | |
| pycge | completed | poles_jrc, world_helium_model, world_fertilizer, cwatm |
| mpsge_jl | completed | poles_jrc, lngst, world_helium_model, world_fertilizer, cwatm, aisdb+ais_project (not run) |
| opencge | failed | - |
