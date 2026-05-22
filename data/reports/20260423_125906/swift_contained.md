# Scenario swift_contained: Swift Contained

## Short Run — Micro

- **Oil Price**: Not Available _(source: `Not Available`)_
  - No successful model results were obtained for the short-run micro outcome scope.
  - reliability: No quantitative results are available for this outcome variable.
- **LNG Price**: Not Available _(source: `Not Available`)_
  - No successful model results were obtained for the short-run micro outcome scope.
  - reliability: No quantitative results are available for this outcome variable.
- **Oil Supply Disruption**: 21% _(source: `Not Available`)_
  - The Strait of Hormuz is closed due to a military escalation between Iran and the US/Israel coalition, disrupting 21% of global oil supply.
  - reliability: This is a scenario narrative summary, not a model output.
- **LNG Supply Disruption**: 25% _(source: `Not Available`)_
  - The Strait of Hormuz is closed due to a military escalation between Iran and the US/Israel coalition, disrupting 25% of global LNG trade.
  - reliability: This is a scenario narrative summary, not a model output.

## Long Run — Macro

- **Global Oil Price**: Not Available _(source: `Not Available`)_
  - No successful model results were obtained for the long-run macro outcome scope.
  - reliability: No quantitative results are available for this outcome variable.
- **Global LNG Price**: Not Available _(source: `Not Available`)_
  - No successful model results were obtained for the long-run macro outcome scope.
  - reliability: No quantitative results are available for this outcome variable.
- **Global Economic Impact**: Not Available _(source: `Not Available`)_
  - No successful model results were obtained for the long-run macro outcome scope.
  - reliability: No quantitative results are available for this outcome variable.

## Long Run — Strategic

- **Oil Price Stabilization**: 10% _(source: `Not Available`)_
  - Global oil and LNG markets recover, with prices stabilizing within 10% of pre-crisis levels.
  - reliability: This is a scenario narrative summary, not a model output.
- **LNG Price Stabilization**: 10% _(source: `Not Available`)_
  - Global oil and LNG markets recover, with prices stabilizing within 10% of pre-crisis levels.
  - reliability: This is a scenario narrative summary, not a model output.

## Cross-model consistency warnings

- aisdb: Validation failed: 'alternative_routes' contains unrecognized identifiers: ['Bab-el-Mandeb Strait', 'Suez Canal']. Valid options: ['cape_of_good_hope', 'none', 'northern_sea_route', 'suez_canal']; 'vessel_types' contains unrecognized labels: ['LNG']. Valid options: ['bulk_carrier', 'chemical_tanker', 'container', 'general_cargo', 'lng_carrier', 'tanker']
- nems: FileNotFoundError: NEMS output directory not found: data/nems_outputs/Hormuz_ScenarioA
- mam: Validation failed: MAMConfig.aeo_macro_xlsx_path is required for aeo_ingestion mode. Point it at the AEO macro tables XLSX (e.g., 'AEO2025_Tables_19_20.xlsx')
- opencge: ImportError: OpenCGEAdapter.execute() requires the 'ogcore' package. Install with: pip install ogcore ogusa dask[distributed]
- pycge: ImportError: PyCGEAdapter.execute() requires the 'cge_modeling' package. Install with: pip install cge-modeling
- miragrodep: FileNotFoundError: [Errno 2] No such file or directory: 'gams'
- osemosys: FileNotFoundError: OSeMOSYS source dir not found: Models/Energy/OSeMOSYS
- messageix: RuntimeError: MESSAGEix adapter requires the 'message-ix' and 'ixmp' packages. Install with `pip install hormuz-pipeline[energy]`
- temoa: FileNotFoundError: TEMOA baseline DB not found: Models/Energy/TEMOA/data_files/utopia.sqlite
- bornstein_krusell_rebelo: FileNotFoundError: Dynare .mod file not found: Models/Oil/WorldEquilibriumOilModel/Replication Files/Section 5/supply_shocks_to_non_opec/dynare_codes/World_Economy_Cartel_nonopec_shocks.mod
- poles_jrc: Validation failed: 'supply_loss_mbd' value 21.0 is outside plausible range [0, 20] mb/d; 'substitute_energy_availability' must be a numeric value

## Failed / skipped models

- `sahysmod`
- `energy_flux_gas_power`
- `energy_flux_lng_profits`
- `argonne_abm`
- `simrlfab`
- `magpie`
- `aisdb`
- `nems`
- `mam`
- `opencge`
- `pycge`
- `miragrodep`
- `osemosys`
- `messageix`
- `temoa`
- `bornstein_krusell_rebelo`
- `poles_jrc`
