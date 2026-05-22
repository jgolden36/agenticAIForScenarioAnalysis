# Scenario infrastructure_collapse: Infrastructure Collapse (Tail Risk)

## Short Run — Micro

_No outcomes synthesized for this section._

## Short Run — Macro

- **oil_price_change_pct**: 48.36 % _(source: `fed_oil`)_
  - The oil price is expected to increase by 48.36% due to the disruption in global oil supply.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The Strait of Hormuz closure will disproportionately affect oil-importing countries in Asia and Europe, while oil-producing countries in the Middle East may experience a temporary increase in revenue.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global oil markets and regional economies.
- **peak_gdp_impact_pct**: -1.5415 % _(source: `fed_oil`)_
  - The global GDP is expected to decline by 1.54% in the short run due to the disruption in global oil supply.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized decline in economic activity, with the most-affected sectors being transportation, manufacturing, and energy.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **peak_cpi_impact_pp**: 2.0553 pp _(source: `fed_oil`)_
  - The global CPI is expected to increase by 2.06 pp in the short run due to the disruption in global oil supply.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in inflation, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **peak_ffr_impact_pp**: 1.0276 pp _(source: `fed_oil`)_
  - The federal funds rate is expected to increase by 1.03 pp in the short run due to the disruption in global oil supply.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in interest rates, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **peak_unemployment_impact_pp**: 0.7708 pp _(source: `fed_oil`)_
  - The global unemployment rate is expected to increase by 0.77 pp in the short run due to the disruption in global oil supply.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in unemployment, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **gdp_irf_pct_quarterly**: [-1.5415, -1.3103, -1.1137, -0.9467, -0.8047, -0.684, -0.5814, -0.4942, -0.42] % _(source: `fed_oil`)_
  - The global GDP is expected to decline by 1.54% in the short run due to the disruption in global oil supply, with a gradual recovery over the next 9 quarters.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized decline in economic activity, with the most-affected sectors being transportation, manufacturing, and energy.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **cpi_irf_pp_quarterly**: [2.0553, 1.5415, 1.1561, 0.8671, 0.6503, 0.4877, 0.3658, 0.2743, 0.2058] pp _(source: `fed_oil`)_
  - The global CPI is expected to increase by 2.06 pp in the short run due to the disruption in global oil supply, with a gradual decline over the next 9 quarters.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in inflation, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **fed_funds_rate_irf_pp_quarterly**: [1.0276, 0.6679, 0.4084, 0.223, 0.0923, 0.0018, -0.0593, -0.0991, -0.1235] pp _(source: `fed_oil`)_
  - The federal funds rate is expected to increase by 1.03 pp in the short run due to the disruption in global oil supply, with a gradual decline over the next 9 quarters.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in interest rates, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **fed_funds_rate_path_pct_quarterly**: [3.5276, 3.1679, 2.9084, 2.723, 2.5923, 2.5018, 2.4407, 2.4009, 2.3765] % _(source: `fed_oil`)_
  - The federal funds rate is expected to increase by 3.53% in the short run due to the disruption in global oil supply, with a gradual decline over the next 9 quarters.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in interest rates, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **unemployment_irf_pp_quarterly**: [0.7708, 0.6551, 0.5569, 0.4733, 0.4023, 0.342, 0.2907, 0.2471, 0.21] pp _(source: `fed_oil`)_
  - The global unemployment rate is expected to increase by 0.77 pp in the short run due to the disruption in global oil supply, with a gradual decline over the next 9 quarters.
  - reliability: The model output is consistent with the upstream override from the poles_jrc model.
  - distributional note: The global economy will experience a synchronized increase in unemployment, with the most-affected sectors being energy, transportation, and manufacturing.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **natural_gas_price_change_pct**: 126.39090909090909 % _(source: `nrel`)_
  - The natural gas price is expected to increase by 126.39% due to the disruption in global natural gas supply.
  - reliability: The model output is consistent with the upstream override from the lngst model.
  - distributional note: The global economy will experience a synchronized increase in natural gas prices, with the most-affected sectors being energy, manufacturing, and transportation.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global natural gas markets and regional economies.
- **retail_electricity_price_change_pct**: 56.876 % _(source: `nrel`)_
  - The retail electricity price is expected to increase by 56.88% due to the disruption in global natural gas supply.
  - reliability: The model output is consistent with the upstream override from the lngst model.
  - distributional note: The global economy will experience a synchronized increase in retail electricity prices, with the most-affected sectors being energy, manufacturing, and transportation.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global electricity markets and regional economies.
- **gdp_impact_pct**: -0.5196 % _(source: `nrel`)_
  - The global GDP is expected to decline by 0.52% in the short run due to the disruption in global natural gas supply.
  - reliability: The model output is consistent with the upstream override from the lngst model.
  - distributional note: The global economy will experience a synchronized decline in economic activity, with the most-affected sectors being energy, manufacturing, and transportation.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **cpi_inflation_pct**: 1.2989 % _(source: `nrel`)_
  - The global CPI is expected to increase by 1.30% in the short run due to the disruption in global natural gas supply.
  - reliability: The model output is consistent with the upstream override from the lngst model.
  - distributional note: The global economy will experience a synchronized increase in inflation, with the most-affected sectors being energy, manufacturing, and transportation.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **consumption_impact_pct**: -1.0391 % _(source: `nrel`)_
  - The global consumption is expected to decline by 1.04% in the short run due to the disruption in global natural gas supply.
  - reliability: The model output is consistent with the upstream override from the lngst model.
  - distributional note: The global economy will experience a synchronized decline in consumption, with the most-affected sectors being energy, manufacturing, and transportation.
  - uncertainty interpretation: The model output has a moderate level of uncertainty due to the complex interactions between global economic systems and regional economies.
- **welfare_pct_change**: -1.0391 % _(source: `nrel`)_
  - The global welfare is expected to decline by 1.04% in the short run due to the disruption in global natural gas supply.
  - reliability: The model output is consistent with the upstream override from the lngst model.
  - distributional note: The global economy will experience a synchronized decline in welfare, with the most-affected sectors being energy, manufacturing, and transportation.
  - uncertainty interpretation: The model output has a high level of uncertainty due to the complex interactions between global economic systems and regional economies.

## Short Run — Strategic

- **gdp_impact_pct**: -0.5196 % _(source: `nrel`)_
  - The global GDP is expected to experience a 0.52% decline due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **cpi_inflation_pct**: 1.2989 % _(source: `nrel`)_
  - The global CPI inflation rate is expected to increase by 1.30% due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **consumption_impact_pct**: -1.0391 % _(source: `nrel`)_
  - The global consumption is expected to experience a 1.04% decline due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **welfare_pct_change**: -1.0391 % _(source: `nrel`)_
  - The global welfare is expected to experience a 1.04% decline due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **natural_gas_price_change_pct**: 126.39090909090909 % _(source: `nrel`)_
  - The natural gas price is expected to increase by 126.39% due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **retail_electricity_price_change_pct**: 56.876 % _(source: `nrel`)_
  - The retail electricity price is expected to increase by 56.88% due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **coal_dispatch_gain_pp**: 10.0 pp _(source: `nrel`)_
  - The coal dispatch gain is expected to increase by 10.0 pp due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **renewables_dispatch_gain_pp**: 12.639 pp _(source: `nrel`)_
  - The renewables dispatch gain is expected to increase by 12.64 pp due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **co2_emissions_pct_change**: 1.321 % _(source: `nrel`)_
  - The global CO2 emissions are expected to increase by 1.32% due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **capacity_utilization_pct_change**: -8.847 % _(source: `nrel`)_
  - The capacity utilization is expected to decrease by 8.85% due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **generation_dispatch_pct_change**: -22.639 % _(source: `nrel`)_
  - The generation dispatch is expected to decrease by 22.64% due to the infrastructure collapse scenario.
  - reliability: The nrel model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.
- **oil_price_path**: [118.69, 113.16, 107.63, 102.11, 96.58, 91.05, 85.53, 80.0, 80.0, 80.0, 80.0, 80.0] USD/bbl _(source: `mam`)_
  - The oil price path is expected to decrease over time due to the infrastructure collapse scenario.
  - reliability: The mam model successfully completed with no issues.
  - distributional note: The impact of the infrastructure collapse is expected to be felt globally, with no specific regions or sectors being highlighted as most or least affected.

## Long Run — Micro

_No outcomes synthesized for this section._

## Long Run — Macro

- **gdp_impact_pct**: -1.0355 % _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 1.04% contraction in GDP due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The MENA_GCC region is expected to be the most resilient, with a 2.68% increase in GDP, while the IND region is expected to be the most severely impacted, with a 2.07% contraction.
- **cpi_inflation_pct**: 2.6609 % _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 2.66% increase in CPI inflation due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The IND region is expected to experience the highest inflation rate, at 5.24%, while the MENA_GCC region is expected to experience the lowest, at 1.11%.
- **consumption_impact_pct**: -2.0998 % _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 2.10% contraction in consumption due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The IND region is expected to experience the largest contraction in consumption, at 4.17%, while the MENA_GCC region is expected to experience the largest increase, at 2.24%.
- **welfare_pct_change**: -2.0998 % _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 2.10% decrease in welfare due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The IND region is expected to experience the largest decrease in welfare, at 4.17%, while the MENA_GCC region is expected to experience the largest increase, at 2.24%.
- **sectoral_output_pct_change**: -0.2774 % _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 0.28% contraction in industry output due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The energy sector is expected to be the most resilient, with a 0.69% increase in output, while the services sector is expected to be the most severely impacted, with a 0.69% contraction.
- **oil_price_shock_pct**: 48.36 % _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 48.36% increase in oil prices due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The global economy is expected to experience a 48.36% increase in oil prices, with no regional or sectoral variation.
- **trade_cost_multiplier**: 1.1869 _(source: `mpsge_jl`)_
  - The global economy is expected to experience a 18.69% increase in trade costs due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - distributional note: The global economy is expected to experience an 18.69% increase in trade costs, with no regional or sectoral variation.
- **gdp_growth_pct**: -0.8636 % _(source: `pycge`)_
  - The global economy is expected to experience a 0.86% contraction in GDP growth due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - regional distribution: IND=-1.7661, EU=-1.5186, SSA=-1.4341, CHN=-1.2333, ROW=-0.8636, US=-0.7814, LAC=-0.4863, MENA_OTHER=0.5866, MENA_GCC=2.6286
  - sectoral distribution: services=-0.6885, industry=-0.2122, agriculture=-0.103, energy=0.4212
  - distributional note: The global economy is expected to experience a 0.86% contraction in GDP growth, with no regional or sectoral variation.
- **cpi_inflation_pct**: 1.7945 % _(source: `pycge`)_
  - The global economy is expected to experience a 1.79% increase in CPI inflation due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - regional distribution: IND=-1.7661, EU=-1.5186, SSA=-1.4341, CHN=-1.2333, ROW=-0.8636, US=-0.7814, LAC=-0.4863, MENA_OTHER=0.5866, MENA_GCC=2.6286
  - sectoral distribution: services=-0.6885, industry=-0.2122, agriculture=-0.103, energy=0.4212
  - distributional note: The global economy is expected to experience a 1.79% increase in CPI inflation, with no regional or sectoral variation.
- **consumption_impact_pct**: -1.5814 % _(source: `pycge`)_
  - The global economy is expected to experience a 1.58% contraction in consumption due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - regional distribution: IND=-1.7661, EU=-1.5186, SSA=-1.4341, CHN=-1.2333, ROW=-0.8636, US=-0.7814, LAC=-0.4863, MENA_OTHER=0.5866, MENA_GCC=2.6286
  - sectoral distribution: services=-0.6885, industry=-0.2122, agriculture=-0.103, energy=0.4212
  - distributional note: The global economy is expected to experience a 1.58% contraction in consumption, with no regional or sectoral variation.
- **welfare_pct_change**: -1.5814 % _(source: `pycge`)_
  - The global economy is expected to experience a 1.58% decrease in welfare due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - regional distribution: IND=-1.7661, EU=-1.5186, SSA=-1.4341, CHN=-1.2333, ROW=-0.8636, US=-0.7814, LAC=-0.4863, MENA_OTHER=0.5866, MENA_GCC=2.6286
  - sectoral distribution: services=-0.6885, industry=-0.2122, agriculture=-0.103, energy=0.4212
  - distributional note: The global economy is expected to experience a 1.58% decrease in welfare, with no regional or sectoral variation.
- **sectoral_output_pct_change**: -0.2122 % _(source: `pycge`)_
  - The global economy is expected to experience a 0.21% contraction in industry output due to the infrastructure collapse scenario.
  - reliability: Both mpsge_jl and pycge models agree on the direction of the impact, but the magnitude differs.
  - regional distribution: IND=-1.7661, EU=-1.5186, SSA=-1.4341, CHN=-1.2333, ROW=-0.8636, US=-0.7814, LAC=-0.4863, MENA_OTHER=0.5866, MENA_GCC=2.6286
  - sectoral distribution: services=-0.6885, industry=-0.2122, agriculture=-0.103, energy=0.4212
  - distributional note: The energy sector is expected to be the most resilient, with a 0.42% increase in output, while the services sector is expected to be the most severely impacted, with a 0.69% contraction.

## Long Run — Strategic

- **oil_price_shock_pct**: {mpsge_jl: 48.36, pycge: 48.36} percent _(source: `mpsge_jl, pycge`)_
  - The oil price shock is expected to be around 48.36% due to the infrastructure collapse.
  - reliability: Both mpsge_jl and pycge models produced consistent results.
  - distributional note: The oil price shock is expected to be most pronounced in regions with high oil import dependence, such as the US and EU, and least in regions with low oil import dependence, such as MENA_GCC.
- **gdp_impact_pct**: {mpsge_jl: -1.0355, pycge: -0.8636} percent _(source: `mpsge_jl, pycge`)_
  - The GDP impact is expected to be around -1.0355% due to the infrastructure collapse.
  - reliability: Both mpsge_jl and pycge models produced consistent results.
  - distributional note: The GDP impact is expected to be most pronounced in regions with high oil import dependence, such as the US and EU, and least in regions with low oil import dependence, such as MENA_GCC.
- **cpi_inflation_pct**: {mpsge_jl: 2.6609, pycge: 1.7945} percent _(source: `mpsge_jl, pycge`)_
  - The CPI inflation is expected to be around 2.6609% due to the infrastructure collapse.
  - reliability: Both mpsge_jl and pycge models produced consistent results.
  - distributional note: The CPI inflation is expected to be most pronounced in regions with high oil import dependence, such as the US and EU, and least in regions with low oil import dependence, such as MENA_GCC.
- **consumption_impact_pct**: {mpsge_jl: -2.0998, pycge: -1.5814} percent _(source: `mpsge_jl, pycge`)_
  - The consumption impact is expected to be around -2.0998% due to the infrastructure collapse.
  - reliability: Both mpsge_jl and pycge models produced consistent results.
  - distributional note: The consumption impact is expected to be most pronounced in regions with high oil import dependence, such as the US and EU, and least in regions with low oil import dependence, such as MENA_GCC.
- **welfare_pct_change**: {mpsge_jl: -2.0998, pycge: -1.5814} percent _(source: `mpsge_jl, pycge`)_
  - The welfare impact is expected to be around -2.0998% due to the infrastructure collapse.
  - reliability: Both mpsge_jl and pycge models produced consistent results.
  - distributional note: The welfare impact is expected to be most pronounced in regions with high oil import dependence, such as the US and EU, and least in regions with low oil import dependence, such as MENA_GCC.
- **sectoral_output_pct_change**: {mpsge_jl: {'agriculture': -0.1502, 'industry': -0.2774, 'energy': 0.6888, 'services': -0.8348}, pycge: {'agriculture': -0.103, 'industry': -0.2122, 'energy': 0.4212, 'services': -0.6885}} percent _(source: `mpsge_jl, pycge`)_
  - The sectoral output impact is expected to be around -0.1502% for agriculture, -0.2774% for industry, 0.6888% for energy, and -0.8348% for services due to the infrastructure collapse.
  - reliability: Both mpsge_jl and pycge models produced consistent results.
  - distributional note: The sectoral output impact is expected to be most pronounced in the energy sector, which is expected to experience a 0.6888% increase, and least in the agriculture sector, which is expected to experience a -0.1502% decrease.

## Cross-model consistency warnings

- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[fertilizer]: LLM=0.0, world_fertilizer=30.321 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[helium]: LLM=30.0, world_helium_model=0.3 (deviation: 196.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[lng]: LLM=25.0, lngst=126.39090909090909 (deviation: 133.9%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[water]: LLM=0.0, cwatm=9.091 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input oil_price_shock_pct: LLM=100.0, poles_jrc=48.36 (deviation: 69.6%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on nrel input natural_gas_price_change_pct: LLM=50.0, lngst=126.39090909090909 (deviation: 86.6%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on pycge input commodity_price_shocks[helium]: LLM=30.0, world_helium_model=0.3 (deviation: 196.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on pycge input commodity_price_shocks[water]: LLM=0.0, cwatm=9.091 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on pycge input oil_price_shock_pct: LLM=500.0, poles_jrc=48.36 (deviation: 164.7%, threshold: 50.0%)

## Failed / skipped models

- `gtap`
- `messageix`
- `miragrodep`
- `nems`
- `opencge`
- `osemosys`
- `temoa`
