# Scenario swift_escalated: Swift Escalated

## Short Run — Micro

- **oil_price**: null USD/bbl _(source: `null`)_
  - No successful model results were obtained for the short-run micro outcome of oil price.
  - reliability: No quantitative result available.
- **lng_price**: null USD/MMBtu _(source: `null`)_
  - No successful model results were obtained for the short-run micro outcome of LNG price.
  - reliability: No quantitative result available.
- **oil_supply_loss**: 21.0 % _(source: `null`)_
  - No successful model results were obtained for the short-run micro outcome of oil supply loss.
  - reliability: No quantitative result available.
- **lng_supply_loss**: 25.0 % _(source: `null`)_
  - No successful model results were obtained for the short-run micro outcome of LNG supply loss.
  - reliability: No quantitative result available.

## Long Run — Macro

- **gdp_growth**: null % _(source: `null`)_
  - No successful model results were obtained for the long-run macro outcome of GDP growth.
  - reliability: No quantitative result available.
- **inflation_rate**: null % _(source: `null`)_
  - No successful model results were obtained for the long-run macro outcome of inflation rate.
  - reliability: No quantitative result available.
- **unemployment_rate**: null % _(source: `null`)_
  - No successful model results were obtained for the long-run macro outcome of unemployment rate.
  - reliability: No quantitative result available.

## Long Run — Strategic

- **oil_price_volatility**: null USD/bbl _(source: `null`)_
  - No successful model results were obtained for the long-run strategic outcome of oil price volatility.
  - reliability: No quantitative result available.
- **lng_price_volatility**: null USD/MMBtu _(source: `null`)_
  - No successful model results were obtained for the long-run strategic outcome of LNG price volatility.
  - reliability: No quantitative result available.

## Cross-model consistency warnings

- poles_jrc: 'supply_loss_mbd' value 21.0 is outside plausible range [0, 20] mb/d
- poles_jrc: 'substitute_energy_availability' must be a numeric value
- argonne_abm: Parameter 'demand_response_elasticity' = 0.5 is outside the valid range [-2.0, 0.0]
- simrlfab: Parameter 'fab_utilization_baseline' = 80.0 is outside the valid range [0.0, 1.0]
- simrlfab: Parameter 'neon_supply_status' = 'unknown' is not a recognized value
- aisdb: 'alternative_routes' contains unrecognized identifiers: ['alternative_route_1', 'alternative_route_2', 'alternative_route_3']. Valid options: ['cape_of_good_hope', 'none', 'northern_sea_route', 'suez_canal']; 'vessel_types' contains unrecognized labels: ['LNG']. Valid options: ['bulk_carrier', 'chemical_tanker', 'container', 'general_cargo', 'lng_carrier', 'tanker']
- nems: FileNotFoundError: NEMS output directory not found: data/nems_outputs/Hormuz_ScenarioC
- mam: Validation failed: MAMConfig.aeo_macro_xlsx_path is required for aeo_ingestion mode. Point it at the AEO macro tables XLSX (e.g., 'AEO2025_Tables_19_20.xlsx')
- opencge: ImportError: OpenCGEAdapter.execute() requires the 'ogcore' package. Install with: pip install ogcore ogusa dask[distributed]
- pycge: ImportError: PyCGEAdapter.execute() requires the 'cge_modeling' package. Install with: pip install cge-modeling
- miragrodep: FileNotFoundError: [Errno 2] No such file or directory: 'gams'
- osemosys: FileNotFoundError: OSeMOSYS source dir not found: Models/Energy/OSeMOSYS
- messageix: RuntimeError: MESSAGEix adapter requires the 'message-ix' and 'ixmp' packages. Install with `pip install hormuz-pipeline[energy]`
- temoa: FileNotFoundError: TEMOA baseline DB not found: Models/Energy/TEMOA/data_files/utopia.sqlite

## Failed / skipped models

- `sahysmod`
- `bornstein_krusell_rebelo`
- `poles_jrc`
- `argonne_abm`
- `simrlfab`
- `aisdb`
- `nems`
- `mam`
- `opencge`
- `pycge`
- `miragrodep`
- `osemosys`
- `messageix`
- `temoa`
