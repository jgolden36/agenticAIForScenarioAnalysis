# Scenario swift_escalated: Swift Escalated Conflict

## Short Run — Micro

_No outcomes synthesized for this section._

## Short Run — Macro

- **oil_price_change_pct**: 58.25 % _(source: `fed_oil`)_
  - The oil price is expected to increase by 58.25% due to the disruption in the Strait of Hormuz.
  - reliability: The upstream model 'poles_jrc' produced a value of 58.25, which is significantly higher than the LLM-extracted value of 25.0 (deviation: 79.9%).
  - distributional note: The Strait of Hormuz closure is expected to have a disproportionate impact on oil-importing countries in Asia, particularly China and Japan, which rely heavily on Middle Eastern oil. In contrast, oil-exporting countries in the region, such as Saudi Arabia and the UAE, may experience a decline in oil revenues.
  - uncertainty interpretation: The high deviation between the LLM-extracted and upstream-computed values for oil_price_change_pct indicates a high level of uncertainty in this outcome.
- **peak_gdp_impact_pct**: -0.6553 % _(source: `fed_oil`)_
  - The global GDP is expected to decline by 0.6553% due to the disruption in the Strait of Hormuz.
  - reliability: The upstream model 'fed_oil' produced a value of -0.6553, which is consistent with the LLM-extracted value.
  - distributional note: The Strait of Hormuz closure is expected to have a significant impact on the global economy, particularly in countries with high oil import dependence, such as the United States and the European Union.
  - uncertainty interpretation: The high deviation between the LLM-extracted and upstream-computed values for oil_price_change_pct indicates a high level of uncertainty in this outcome.
- **natural_gas_price_change_pct**: 126.39090909090909 % _(source: `nrel`)_
  - The natural gas price is expected to increase by 126.39% due to the disruption in the Strait of Hormuz.
  - reliability: The upstream model 'lngst' produced a value of 126.39090909090909, which is significantly higher than the LLM-extracted value of 0.0 (deviation: 200.0%).
  - distributional note: The Strait of Hormuz closure is expected to have a disproportionate impact on natural gas-importing countries in Asia, particularly Japan and South Korea, which rely heavily on Middle Eastern natural gas. In contrast, natural gas-exporting countries in the region, such as Qatar and the UAE, may experience a decline in natural gas revenues.
  - uncertainty interpretation: The high deviation between the LLM-extracted and upstream-computed values for natural_gas_price_change_pct indicates a high level of uncertainty in this outcome.
- **gdp_impact_pct**: -0.4494 % _(source: `nrel`)_
  - The global GDP is expected to decline by 0.4494% due to the disruption in the Strait of Hormuz.
  - reliability: The upstream model 'nrel' produced a value of -0.4494, which is consistent with the LLM-extracted value.
  - distributional note: The Strait of Hormuz closure is expected to have a significant impact on the global economy, particularly in countries with high oil import dependence, such as the United States and the European Union.
  - uncertainty interpretation: The high deviation between the LLM-extracted and upstream-computed values for natural_gas_price_change_pct indicates a high level of uncertainty in this outcome.

## Short Run — Strategic

- **disruption_duration_months**: {nrel: 4.0} months _(source: `nrel`)_
  - The Strait of Hormuz remains closed for 4 months, causing significant economic disruption.
  - reliability: All models in this section completed successfully.
  - distributional note: The disruption affects global oil supply and LNG trade, with no specific regional or sectoral data available.
- **natural_gas_price_change_pct**: {nrel: 126.39090909090909} % _(source: `nrel`)_
  - Natural gas prices increase by 126.39% due to the Strait of Hormuz closure.
  - reliability: Note: LLM-extracted value and upstream value disagree materially (deviation: 200.0%).
  - distributional note: The price increase affects global natural gas markets, with no specific regional or sectoral data available.
- **gdp_impact_pct**: {nrel: -0.4494} % _(source: `nrel`)_
  - The Strait of Hormuz closure causes a 0.45% decrease in global GDP.
  - reliability: All models in this section completed successfully.
  - distributional note: The economic impact affects global GDP, with no specific regional or sectoral data available.
- **cpi_inflation_pct**: {nrel: 1.2639} % _(source: `nrel`)_
  - The Strait of Hormuz closure causes a 1.26% increase in global CPI inflation.
  - reliability: All models in this section completed successfully.
  - distributional note: The inflation impact affects global CPI, with no specific regional or sectoral data available.
- **consumption_impact_pct**: {nrel: -0.9549} % _(source: `nrel`)_
  - The Strait of Hormuz closure causes a 0.95% decrease in global consumption.
  - reliability: All models in this section completed successfully.
  - distributional note: The consumption impact affects global markets, with no specific regional or sectoral data available.
- **welfare_pct_change**: {nrel: -0.9549} % _(source: `nrel`)_
  - The Strait of Hormuz closure causes a 0.95% decrease in global welfare.
  - reliability: All models in this section completed successfully.
  - distributional note: The welfare impact affects global populations, with no specific regional or sectoral data available.
- **co2_emissions_pct_change**: {nrel: 1.321} % _(source: `nrel`)_
  - The Strait of Hormuz closure causes a 1.32% increase in global CO2 emissions.
  - reliability: All models in this section completed successfully.
  - distributional note: The emissions impact affects global energy systems, with no specific regional or sectoral data available.
- **coal_dispatch_gain_pp**: {nrel: 10.0} pp _(source: `nrel`)_
  - Coal dispatch increases by 10 pp due to the Strait of Hormuz closure.
  - reliability: All models in this section completed successfully.
  - distributional note: The coal dispatch impact affects global energy markets, with no specific regional or sectoral data available.
- **renewables_dispatch_gain_pp**: {nrel: 12.639} pp _(source: `nrel`)_
  - Renewables dispatch increases by 12.64 pp due to the Strait of Hormuz closure.
  - reliability: All models in this section completed successfully.
  - distributional note: The renewables dispatch impact affects global energy markets, with no specific regional or sectoral data available.
- **fleet_utilization_drop_pct_by_vessel**: {aisdb: {'lng_carrier': 35.185, 'tanker': 29.688}} % _(source: `aisdb`)_
  - The Strait of Hormuz closure causes a 35.19% drop in lng carrier fleet utilization and a 29.69% drop in tanker fleet utilization.
  - reliability: All models in this section completed successfully.
  - distributional note: The fleet utilization impact affects global shipping, with lng carriers and tankers being the most affected.
- **effective_fleet_capacity_loss_pct**: {aisdb: 31.154, ais_project: 0.0} % _(source: `aisdb`)_
  - The Strait of Hormuz closure causes a 31.15% loss in effective fleet capacity, according to AISDB, and no loss, according to AIS Project.
  - reliability: Note: AISDB and AIS Project disagree on this outcome.
  - distributional note: The fleet capacity impact affects global shipping, with AISDB and AIS Project disagreeing on the magnitude of the impact.
- **rerouting_cost_multiplier**: {aisdb: 1.1869, ais_project: 1.0} _(source: `aisdb`)_
  - The Strait of Hormuz closure causes a 18.69% increase in rerouting costs, according to AISDB, and no increase, according to AIS Project.
  - reliability: Note: AISDB and AIS Project disagree on this outcome.
  - distributional note: The rerouting cost impact affects global shipping, with AISDB and AIS Project disagreeing on the magnitude of the impact.
- **war_risk_insurance_premium_pct**: {aisdb: 200.0} % _(source: `aisdb`)_
  - The Strait of Hormuz closure causes a 200% increase in war risk insurance premiums.
  - reliability: All models in this section completed successfully.
  - distributional note: The war risk insurance premium impact affects global shipping, with no specific regional or sectoral data available.
- **strait_closure_flag**: {aisdb: True, ais_project: True} _(source: `aisdb`)_
  - The Strait of Hormuz is closed due to the conflict.
  - reliability: All models in this section completed successfully.
  - distributional note: The Strait of Hormuz closure affects global shipping, with no specific regional or sectoral data available.
- **alternative_routes**: {aisdb: ['cape_of_good_hope']} _(source: `aisdb`)_
  - The Strait of Hormuz closure causes ships to reroute via the Cape of Good Hope.
  - reliability: All models in this section completed successfully.
  - distributional note: The rerouting impact affects global shipping, with the Cape of Good Hope being the most affected route.
- **vessel_types**: {aisdb: ['lng_carrier', 'tanker']} _(source: `aisdb`)_
  - The Strait of Hormuz closure affects lng carriers and tankers.
  - reliability: All models in this section completed successfully.
  - distributional note: The vessel type impact affects global shipping, with lng carriers and tankers being the most affected.
- **additional_transit_days_by_route**: {aisdb: {'cape_of_good_hope': 9.5}} days _(source: `aisdb`)_
  - The Strait of Hormuz closure causes a 9.5-day increase in transit time via the Cape of Good Hope.
  - reliability: All models in this section completed successfully.
  - distributional note: The transit time impact affects global shipping, with the Cape of Good Hope being the most affected route.
- **max_additional_transit_days**: {aisdb: 9.5} days _(source: `aisdb`)_
  - The Strait of Hormuz closure causes a maximum 9.5-day increase in transit time.
  - reliability: All models in this section completed successfully.
  - distributional note: The transit time impact affects global shipping, with no specific regional or sectoral data available.
- **fleet_utilization_multiplier**: {ais_project: 1.0} _(source: `ais_project`)_
  - The Strait of Hormuz closure causes no change in fleet utilization, according to AIS Project.
  - reliability: All models in this section completed successfully.
  - distributional note: The fleet utilization impact affects global shipping, with no specific regional or sectoral data available.
- **effective_fleet_capacity_loss_pct**: {ais_project: 0.0} % _(source: `ais_project`)_
  - The Strait of Hormuz closure causes no loss in effective fleet capacity, according to AIS Project.
  - reliability: All models in this section completed successfully.
  - distributional note: The fleet capacity impact affects global shipping, with no specific regional or sectoral data available.
- **tanker_rate_change_pct**: {ais_project: 0.0} % _(source: `ais_project`)_
  - The Strait of Hormuz closure causes no change in tanker rates, according to AIS Project.
  - reliability: All models in this section completed successfully.
  - distributional note: The tanker rate impact affects global shipping, with no specific regional or sectoral data available.
- **rerouting_cost_multiplier**: {ais_project: 1.0} _(source: `ais_project`)_
  - The Strait of Hormuz closure causes no increase in rerouting costs, according to AIS Project.
  - reliability: All models in this section completed successfully.
  - distributional note: The rerouting cost impact affects global shipping, with no specific regional or sectoral data available.
- **voyage_days_lost_per_baseline_voyage**: {ais_project: 0.0} days _(source: `ais_project`)_
  - The Strait of Hormuz closure causes no loss in voyage days, according to AIS Project.
  - reliability: All models in this section completed successfully.
  - distributional note: The voyage day impact affects global shipping, with no specific regional or sectoral data available.
- **disruption_duration_months**: {ais_project: 4.0} months _(source: `ais_project`)_
  - The Strait of Hormuz remains closed for 4 months, according to AIS Project.
  - reliability: All models in this section completed successfully.
  - distributional note: The disruption duration impact affects global shipping, with no specific regional or sectoral data available.

## Long Run — Micro

_No outcomes synthesized for this section._

## Long Run — Macro

- **oil_price_shock_pct**: {mpsge_jl: 58.25, pycge: 58.25} percent _(source: `mpsge_jl, pycge`)_
  - The oil price shock is expected to be 58.25% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The oil price shock is expected to be most pronounced in regions with high oil import dependence, such as the US and EU, and least in regions with low oil import dependence, such as MENA_GCC.
- **trade_cost_multiplier**: {mpsge_jl: 1.1869} percent _(source: `mpsge_jl`)_
  - The trade cost multiplier is expected to increase by 18.69% due to the Strait of Hormuz closure.
  - reliability: mpsge_jl model produced this outcome.
  - distributional note: The trade cost multiplier is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **commodity_price_shocks**: {mpsge_jl: {'oil': 58.25, 'lng': 126.39090909090909, 'fertilizer': 23.756, 'helium': 0.0}, pycge: {'oil': 58.25, 'lng': 25.0, 'fertilizer': 23.756, 'helium': 0.0}} percent _(source: `mpsge_jl, pycge`)_
  - The commodity price shocks are expected to be 58.25% for oil, 126.39% for LNG, 23.76% for fertilizer, and 0% for helium due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The commodity price shocks are expected to be most pronounced in regions with high commodity import dependence, such as the US and EU, and least in regions with low commodity import dependence, such as MENA_GCC.
- **disruption_duration_months**: {mpsge_jl: 4.0} months _(source: `mpsge_jl`)_
  - The disruption duration is expected to be 4 months due to the Strait of Hormuz closure.
  - reliability: mpsge_jl model produced this outcome.
  - distributional note: The disruption duration is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **gdp_impact_pct**: {mpsge_jl: -0.8695, pycge: -0.7889} percent _(source: `mpsge_jl, pycge`)_
  - The GDP impact is expected to be -0.8695% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The GDP impact is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **cpi_inflation_pct**: {mpsge_jl: 2.7539, pycge: 1.712} percent _(source: `mpsge_jl, pycge`)_
  - The CPI inflation is expected to be 2.7539% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The CPI inflation is expected to be most pronounced in regions with high commodity import dependence, such as the US and EU, and least in regions with low commodity import dependence, such as MENA_GCC.
- **consumption_impact_pct**: {mpsge_jl: -1.9711, pycge: -1.4736} percent _(source: `mpsge_jl, pycge`)_
  - The consumption impact is expected to be -1.9711% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The consumption impact is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **welfare_pct_change**: {mpsge_jl: -1.9711, pycge: -1.4736} percent _(source: `mpsge_jl, pycge`)_
  - The welfare impact is expected to be -1.9711% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The welfare impact is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **wage_impact_pct**: {mpsge_jl: 1.2176, pycge: 0.6327} percent _(source: `mpsge_jl, pycge`)_
  - The wage impact is expected to be 1.2176% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The wage impact is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **interest_rate_impact_pct**: {mpsge_jl: 1.1596, pycge: 0.6588} percent _(source: `mpsge_jl, pycge`)_
  - The interest rate impact is expected to be 1.1596% due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The interest rate impact is expected to be most pronounced in regions with high trade dependence, such as the US and EU, and least in regions with low trade dependence, such as MENA_GCC.
- **sectoral_output_pct_change**: {mpsge_jl: {'agriculture': -0.1244, 'industry': -0.2334, 'energy': 0.5824, 'services': -0.7012}, pycge: {'agriculture': -0.0829, 'industry': -0.1882, 'energy': 0.34, 'services': -0.6267}} percent _(source: `mpsge_jl, pycge`)_
  - The sectoral output impact is expected to be -0.1244% for agriculture, -0.2334% for industry, 0.5824% for energy, and -0.7012% for services due to the Strait of Hormuz closure.
  - reliability: Both mpsge_jl and pycge models agree on this outcome.
  - distributional note: The sectoral output impact is expected to be most pronounced in the energy sector, which is expected to benefit from the increased demand for oil and gas, and least in the services sector, which is expected to be negatively impacted by the economic disruption.
- **regional_vars**: {pycge: [{'region': 'US', 'gdp_impact_pct': -0.7444, 'cpi_inflation_pct': 1.712, 'consumption_impact_pct': -1.4292, 'welfare_pct_change': -1.4292, 'wage_impact_pct': 0.655, 'interest_rate_impact_pct': 0.6699}, {'region': 'CHN', 'gdp_impact_pct': -1.1186, 'cpi_inflation_pct': 2.1434, 'consumption_impact_pct': -1.9759, 'welfare_pct_change': -1.9759, 'wage_impact_pct': 0.7268, 'interest_rate_impact_pct': 0.7921}, {'region': 'IND', 'gdp_impact_pct': -1.6041, 'cpi_inflation_pct': 3.5224, 'consumption_impact_pct': -3.013, 'welfare_pct_change': -3.013, 'wage_impact_pct': 1.3114, 'interest_rate_impact_pct': 1.3602}, {'region': 'EU', 'gdp_impact_pct': -1.3008, 'cpi_inflation_pct': 2.7288, 'consumption_impact_pct': -2.3923, 'welfare_pct_change': -2.3923, 'wage_impact_pct': 0.9869, 'interest_rate_impact_pct': 1.0392}, {'region': 'MENA_GCC', 'gdp_impact_pct': 2.5054, 'cpi_inflation_pct': 0.6621, 'consumption_impact_pct': 2.2406, 'welfare_pct_change': 2.2406, 'wage_impact_pct': 1.6499, 'interest_rate_impact_pct': 0.9574}, {'region': 'MENA_OTHER', 'gdp_impact_pct': 0.6124, 'cpi_inflation_pct': 2.5914, 'consumption_impact_pct': -0.4241, 'welfare_pct_change': -0.4241, 'wage_impact_pct': 1.8611, 'interest_rate_impact_pct': 1.4488}, {'region': 'SSA', 'gdp_impact_pct': -1.3677, 'cpi_inflation_pct': 4.1518, 'consumption_impact_pct': -3.0285, 'welfare_pct_change': -3.0285, 'wage_impact_pct': 1.8072, 'interest_rate_impact_pct': 1.734}, {'region': 'LAC', 'gdp_impact_pct': -0.4314, 'cpi_inflation_pct': 2.0434, 'consumption_impact_pct': -1.2487, 'welfare_pct_change': -1.2487, 'wage_impact_pct': 1.0104, 'interest_rate_impact_pct': 0.9139}, {'region': 'ROW', 'gdp_impact_pct': -0.7889, 'cpi_inflation_pct': 1.712, 'consumption_impact_pct': -1.4736, 'welfare_pct_change': -1.4736, 'wage_impact_pct': 0.6327, 'interest_rate_impact_pct': 0.6588}]} percent _(source: `pycge`)_
  - The regional output impact is expected to be -0.7444% for the US, -1.1186% for China, -1.6041% for India, -1.3008% for the EU, 2.5054% for MENA_GCC, 0.6124% for MENA_OTHER, -1.3677% for SSA, -0.4314% for LAC, and -0.7889% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional output impact is expected to be most pronounced in MENA_GCC, which is expected to benefit from the increased demand for oil and gas, and least in SSA, which is expected to be negatively impacted by the economic disruption.
- **gdp_impact_pct_by_region**: {pycge: {'US': -0.7444, 'CHN': -1.1186, 'IND': -1.6041, 'EU': -1.3008, 'MENA_GCC': 2.5054, 'MENA_OTHER': 0.6124, 'SSA': -1.3677, 'LAC': -0.4314, 'ROW': -0.7889}} percent _(source: `pycge`)_
  - The regional GDP impact is expected to be -0.7444% for the US, -1.1186% for China, -1.6041% for India, -1.3008% for the EU, 2.5054% for MENA_GCC, 0.6124% for MENA_OTHER, -1.3677% for SSA, -0.4314% for LAC, and -0.7889% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional GDP impact is expected to be most pronounced in MENA_GCC, which is expected to benefit from the increased demand for oil and gas, and least in SSA, which is expected to be negatively impacted by the economic disruption.
- **cpi_inflation_pct_by_region**: {pycge: {'US': 1.712, 'CHN': 2.1434, 'IND': 3.5224, 'EU': 2.7288, 'MENA_GCC': 0.6621, 'MENA_OTHER': 2.5914, 'SSA': 4.1518, 'LAC': 2.0434, 'ROW': 1.712}} percent _(source: `pycge`)_
  - The regional CPI inflation is expected to be 1.712% for the US, 2.1434% for China, 3.5224% for India, 2.7288% for the EU, 0.6621% for MENA_GCC, 2.5914% for MENA_OTHER, 4.1518% for SSA, 2.0434% for LAC, and 1.712% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional CPI inflation is expected to be most pronounced in SSA, which is expected to be negatively impacted by the economic disruption, and least in MENA_GCC, which is expected to benefit from the increased demand for oil and gas.
- **consumption_impact_pct_by_region**: {pycge: {'US': -1.8026, 'CHN': -2.6073, 'IND': -3.9016, 'EU': -3.9109, 'MENA_GCC': 2.2851, 'MENA_OTHER': -0.8663, 'SSA': -3.1649, 'LAC': -1.6193, 'ROW': -1.9711}} percent _(source: `pycge`)_
  - The regional consumption impact is expected to be -1.8026% for the US, -2.6073% for China, -3.9016% for India, -3.9109% for the EU, 2.2851% for MENA_GCC, -0.8663% for MENA_OTHER, -3.1649% for SSA, -1.6193% for LAC, and -1.9711% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional consumption impact is expected to be most pronounced in SSA, which is expected to be negatively impacted by the economic disruption, and least in MENA_GCC, which is expected to benefit from the increased demand for oil and gas.
- **welfare_pct_change_by_region**: {pycge: {'US': -1.8026, 'CHN': -2.6073, 'IND': -3.9016, 'EU': -3.9109, 'MENA_GCC': 2.2851, 'MENA_OTHER': -0.8663, 'SSA': -3.1649, 'LAC': -1.6193, 'ROW': -1.9711}} percent _(source: `pycge`)_
  - The regional welfare impact is expected to be -1.8026% for the US, -2.6073% for China, -3.9016% for India, -3.9109% for the EU, 2.2851% for MENA_GCC, -0.8663% for MENA_OTHER, -3.1649% for SSA, -1.6193% for LAC, and -1.9711% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional welfare impact is expected to be most pronounced in SSA, which is expected to be negatively impacted by the economic disruption, and least in MENA_GCC, which is expected to benefit from the increased demand for oil and gas.
- **equivalent_variation_pct_by_region**: {pycge: {'US': -1.8026, 'CHN': -2.6073, 'IND': -3.9016, 'EU': -3.9109, 'MENA_GCC': 2.2851, 'MENA_OTHER': -0.8663, 'SSA': -3.1649, 'LAC': -1.6193, 'ROW': -1.9711}} percent _(source: `pycge`)_
  - The regional equivalent variation impact is expected to be -1.8026% for the US, -2.6073% for China, -3.9016% for India, -3.9109% for the EU, 2.2851% for MENA_GCC, -0.8663% for MENA_OTHER, -3.1649% for SSA, -1.6193% for LAC, and -1.9711% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional equivalent variation impact is expected to be most pronounced in SSA, which is expected to be negatively impacted by the economic disruption, and least in MENA_GCC, which is expected to benefit from the increased demand for oil and gas.
- **terms_of_trade_pct_change_by_region**: {pycge: {'US': -0.0291, 'CHN': -0.1748, 'IND': -0.2913, 'EU': -0.233, 'MENA_GCC': 0.5242, 'MENA_OTHER': 0.1748, 'SSA': -0.2039, 'LAC': -0.0583, 'ROW': -0.0583}} percent _(source: `pycge`)_
  - The regional terms of trade impact is expected to be -0.0291% for the US, -0.1748% for China, -0.2913% for India, -0.233% for the EU, 0.5242% for MENA_GCC, 0.1748% for MENA_OTHER, -0.2039% for SSA, -0.0583% for LAC, and -0.0583% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The regional terms of trade impact is expected to be most pronounced in MENA_GCC, which is expected to benefit from the increased demand for oil and gas, and least in SSA, which is expected to be negatively impacted by the economic disruption.
- **bilateral_trade_flow_change_pct**: {pycge: {'MENA_GCC': {'CHN': -6.355, 'IND': -5.607, 'EU': -4.112, 'US': -1.495, 'ROW': -3.738}}} percent _(source: `pycge`)_
  - The bilateral trade flow impact is expected to be -6.355% for China, -5.607% for India, -4.112% for the EU, -1.495% for the US, and -3.738% for ROW due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The bilateral trade flow impact is expected to be most pronounced in China, which is expected to be negatively impacted by the economic disruption, and least in the US, which is expected to benefit from the increased demand for oil and gas.
- **sectoral_output_pct_change**: {pycge: {'services': -0.6267, 'industry': -0.1882, 'agriculture': -0.0829, 'energy': 0.34}} percent _(source: `pycge`)_
  - The sectoral output impact is expected to be -0.6267% for services, -0.1882% for industry, -0.0829% for agriculture, and 0.34% for energy due to the Strait of Hormuz closure.
  - reliability: pycge model produced this outcome.
  - regional distribution: IND=-1.6041, SSA=-1.3677, EU=-1.3008, CHN=-1.1186, ROW=-0.7889, US=-0.7444, LAC=-0.4314, MENA_OTHER=0.6124, MENA_GCC=2.5054
  - sectoral distribution: services=-0.6267, industry=-0.1882, agriculture=-0.0829, energy=0.34
  - distributional note: The sectoral output impact is expected to be most pronounced in the services sector, which is expected to be negatively impacted by the economic disruption, and least in the energy sector, which is expected to benefit from the increased demand for oil and gas.

## Long Run — Strategic

_No outcomes synthesized for this section._

## Cross-model consistency warnings

- LLM-extracted vs upstream-computed disagreement on fed_oil input oil_price_change_pct: LLM=25.0, poles_jrc=58.25 (deviation: 79.9%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[fertilizer]: LLM=0, world_fertilizer=23.756 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[helium]: LLM=30, world_helium_model=0.0 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input commodity_price_shocks[lng]: LLM=25, lngst=126.39090909090909 (deviation: 133.9%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on mpsge_jl input oil_price_shock_pct: LLM=0.0, poles_jrc=58.25 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on nrel input natural_gas_price_change_pct: LLM=0.0, lngst=126.39090909090909 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on pycge input commodity_price_shocks[fertilizer]: LLM=0, world_fertilizer=23.756 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on pycge input commodity_price_shocks[helium]: LLM=30, world_helium_model=0.0 (deviation: 200.0%, threshold: 50.0%)
- LLM-extracted vs upstream-computed disagreement on pycge input oil_price_shock_pct: LLM=0.0, poles_jrc=58.25 (deviation: 200.0%, threshold: 50.0%)
- Section long_run/micro synthesis failed: LengthFinishReasonError
- Section long_run/strategic synthesis failed: LengthFinishReasonError
- Section short_run/micro synthesis failed: LengthFinishReasonError

## Failed / skipped models

- `bornstein_krusell_rebelo`
- `capri`
- `energy_flux_lng_profits`
- `ggm`
- `gtap`
- `magpie`
- `messageix`
- `miragrodep`
- `nems`
- `opencge`
- `osemosys`
- `sahysmod`
- `simple_g`
- `temoa`
- `watergap2`
