# Qualitative model output narratives — Swift Escalated Conflict

_Run ID: `20260504_222710` · scenario: `swift_escalated`_

> February 2026: The Strait of Hormuz is closed due to a military escalation between Iran and a US/Israel coalition. The closure disrupts approximately 21% of global oil supply and 25% of global LNG trade. Qatar, the world's largest LNG exporter, is effectively blockaded. The disruption also threatens Persian Gulf desalination plants serving tens of millions of people and approximately 30% of global helium supply.
> 
> February 20, 2026: The US and Israel launch a series of airstrikes against Iranian military targets in the Strait of Hormuz. Iran responds with missile and drone strikes against Saudi and UAE targets.
> 
> February 25, 2026: The conflict escalates, with both sides suffering significant losses. The Strait of Hormuz remains closed, causing economic disruption to grow.
> 
> March 2026: The conflict spreads to other regional actors, including Saudi Arabia and the UAE. The Strait of Hormuz remains closed, causing significant economic disruption.
> 
> June 2026: The US and Israel announce a ceasefire, and the Strait of Hormuz is reopened to commercial shipping. The closure lasted for 4 months, causing significant economic disruption.

Below: one section per model with at least one completed output (17 model(s) total). Quantitative tables for the same results live under `csv/raw/swift_escalated/`.

## `ais_project`  _(commodity: shipping)_

The Swift Escalated Conflict scenario, where the Strait of Hormuz is closed for 4 months, has significant implications for the global shipping system. The model output suggests that the closure of the Strait of Hormuz results in minimal disruption to the global shipping system, with the effective fleet capacity loss at 0%. This implies that the global shipping system is able to adapt to the disruption, possibly through rerouting or other measures, and maintain its overall capacity.

However, the model output also indicates that the closure of the Strait of Hormuz leads to a significant increase in voyage days lost, with the disruption duration being 4 months. This suggests that the closure of the Strait of Hormuz has a substantial impact on the global shipping system, particularly in terms of the time it takes for goods to be transported. The lack of regional dispersion detected by the model implies that the disruption is relatively evenly distributed across different regions, with no particular region or sector being hit harder than others.

It is worth noting that the model output should be taken as an order-of-magnitude indicator, rather than a precise prediction. The scenario assumptions drive the pattern of disruption, and the lack of regional dispersion may be due to the model's simplifications or the specific assumptions made about the scenario. Additionally, the model's sparse output suggests that there may be other factors at play that are not captured by the model, and further analysis may be necessary to fully understand the implications of the Swift Escalated Conflict scenario.

## `aisdb`  _(commodity: shipping)_

The model output for the Swift Escalated Conflict scenario reveals significant disruptions to global shipping, particularly in the Strait of Hormuz. The headline magnitudes include a 9.5-day increase in transit time for vessels taking the Cape of Good Hope route, a 31.2% effective fleet capacity loss, and a 35.2% drop in fleet utilization for LNG carriers. These numbers imply a substantial impact on the global shipping system, with LNG carriers being hit particularly hard.

The scenario's assumptions drive these outcomes, as the closure of the Strait of Hormuz would force vessels to take longer routes, such as the Cape of Good Hope, resulting in increased transit times and costs. The model's outputs suggest that the rerouting of vessels would come at a significant cost, with a multiplier of 1.1869 indicating a substantial increase in expenses. Additionally, the war risk insurance premium would surge to 200%, further exacerbating the economic burden on shipping companies.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs, suggesting that the impact of the scenario is relatively uniform across different regions. However, it is essential to note that the model's outputs should be read as order-of-magnitude indicators, and the actual effects may vary depending on various factors, such as the specific routes taken by vessels and the response of shipping companies to the crisis.

## `apsim`  _(commodity: fertilizer_agriculture)_

The Swift Escalated Conflict scenario, as modeled by apsim, yields a relatively benign outcome for the fertilizer_agriculture commodity system. The model predicts no reduction in fertilizer application, irrigation water, or crop yields across the board. This suggests that the conflict's impact on global food production is minimal, with no significant losses in wheat, rice, or maize yields.

The lack of regional dispersion in the model's output implies that the effects of the conflict are evenly distributed across the world, with no particular region or sector being disproportionately affected. This is likely due to the model's assumptions about the conflict's scope and duration, which may not have been severe enough to cause significant disruptions in global food production.

It's worth noting that the model's outputs should be taken as order-of-magnitude indicators rather than precise predictions. The scenario's assumptions, such as the closure of the Strait of Hormuz for 4 months, may not have been fully captured by the model's parameters. As such, the results should be interpreted as a rough estimate of the conflict's potential impact on the fertilizer_agriculture commodity system rather than a precise forecast.

Given the sparse nature of the model's output, it's difficult to draw more nuanced conclusions about the scenario's implications for specific regions or sectors. However, the overall picture suggests that the Swift Escalated Conflict is unlikely to have a significant impact on global food production, at least in the short term.

## `cwatm`  _(commodity: water)_

The Swift Escalated Conflict scenario model output indicates a significant disruption to the global water supply system. The unmet demand percentage is approximately 9.09%, suggesting that nearly 1 in 11 people globally will not have access to sufficient water. This is likely due to the closure of Persian Gulf desalination plants, which serve tens of millions of people.

The mean discharge deviation percentage is 0.0%, indicating that the model did not detect any changes in water discharge patterns. However, the cumulative water deficit percentage over 36.36 months implies a substantial long-term water shortage. This is consistent with the scenario's assumption of a prolonged closure of the Strait of Hormuz, which would disrupt global trade and supply chains.

The desalination capacity factor is at 1.0, suggesting that desalination plants are operating at full capacity to meet the increased demand. However, the supply infrastructure status is "damaged", implying that the plants may be operating at reduced efficiency or capacity. The demand factor is 1.1, indicating a 10% increase in water demand due to the crisis.

The disruption duration of 4 months is consistent with the scenario's assumption of a ceasefire in June 2026, which would allow the Strait of Hormuz to reopen to commercial shipping. However, the long-term cumulative water deficit suggests that the effects of the crisis may be felt for an extended period.

There is no regional dispersion summary available for this model, so we cannot identify which regions or sectors are hit hardest by the crisis. However, it is likely that regions with existing water scarcity issues, such as the Middle East and North Africa, would be disproportionately affected by the closure of desalination plants.

## `energy_flux_gas_power`  _(commodity: lng)_

The Swift Escalated Conflict scenario has significant implications for the global LNG trade. The model output suggests that the cumulative added capacity for the LNG system will reach 101.35 GW by 2035, with a corresponding increase in incremental production. This implies a substantial increase in the global LNG supply, which could help mitigate the effects of the conflict on the energy market.

However, the model output also highlights the significant disruption caused by the conflict in the short term. In 2026, the cumulative added capacity is only 10.135 GW, with a blended production of 0.913 Bcf per day. This suggests that the conflict will have a significant impact on the global LNG supply in the initial years, leading to shortages and price increases. The model output also suggests that the DC capacity will be significantly affected, with a DC effective capacity of 0.695 in 2026.

The regional dispersion summary is empty, indicating that the model output does not provide any information on regional or sectoral asymmetries. However, based on the scenario description, it is likely that the regions most affected by the conflict will be those with the highest dependence on LNG imports, such as the MENA region. The conflict will likely disrupt the supply of LNG to these regions, leading to shortages and price increases.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as the model is an analytical-MVP. The actual numbers may vary depending on various factors, including the effectiveness of the conflict resolution and the response of the global energy market.

## `fed_oil`  _(commodity: oil)_

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in significant economic disruption. The model output indicates that the oil price is expected to increase by 58.25% due to the supply shock. This is a substantial increase, likely to have far-reaching consequences for the global economy.

The disruption is expected to last for one quarter, with the peak impact on GDP occurring at -0.6553% in the same quarter. This suggests that the global economy will experience a significant contraction in the short term. The peak impact on inflation (CPI) is expected to be 1.165% in the same quarter, indicating a moderate increase in prices. The Federal Funds Rate (FFR) is expected to increase by 0.5825% in the same quarter, which is a relatively small increase compared to the other impacts.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. This is likely because the Strait of Hormuz is a critical chokepoint for global oil trade, and the disruption is expected to have a relatively uniform impact on the global economy. However, it is worth noting that the model output is an analytical-MVP (Minimum Viable Product) and should be read as an order-of-magnitude indicator rather than a precise prediction.

It is also worth noting that the model output does not provide any information on the impact of the conflict on specific regions or sectors, such as the Persian Gulf or the global helium supply. This is likely because the model is focused on the global economy as a whole, and the regional dispersion summary is not available for this scenario.

## `futures`  _(commodity: fertilizer_agriculture)_

The model output for the Swift Escalated Conflict scenario indicates significant price shocks for Oil and LNG, with peak price indices of 1.21 for both commodities. This represents a substantial increase in prices, likely driven by the disruption to global supply chains and the closure of the Strait of Hormuz. The initial price shock of 21% for Oil and 25% for LNG suggests a severe and immediate impact on global markets.

The time to normalization for both Oil and LNG is null, indicating that the model does not forecast a return to pre-crisis prices within the forecast horizon of 4 months. This implies that the economic disruption caused by the conflict could be prolonged, with prices remaining elevated for an extended period. The forecast horizon of 4 months suggests that the model is focused on the short-term impact of the crisis, rather than long-term recovery.

The regional dispersion summary indicates that no regional dispersion was detected for this model. This means that the model output does not suggest significant differences in the impact of the crisis across different regions. However, it is worth noting that the scenario assumptions drive a global impact, with the closure of the Strait of Hormuz affecting global supply chains and prices. In a real-world scenario, regional and sectoral asymmetries would likely be present, with some regions or sectors being more insulated from the crisis than others.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model output is likely to be sensitive to the specific assumptions and parameters used, and further analysis would be required to refine the estimates and understand the underlying drivers of the crisis.

## `lngst`  _(commodity: lng)_

The Swift Escalated Conflict scenario, which involves the closure of the Strait of Hormuz, has significant implications for the global LNG market. The model output suggests that Qatar, the world's largest LNG exporter, would experience a complete reduction in exports, while the UAE would not be affected. This is likely due to the blockade imposed on Qatar, effectively cutting off its ability to export LNG.

The model also predicts a substantial increase in the spot price of LNG, with a multiplier of 1.5, indicating a significant price surge. The disruption is expected to last for 4 months, causing a supply shortfall of approximately 36.67 billion cubic meters (bcm) and an annualised supply shortfall of 110 bcm. This represents a global supply shortfall of around 20.37%. The implied price impulse is also substantial, at 50.93%.

The model output does not provide a detailed regional dispersion summary, indicating that the scenario's impact is likely to be felt globally, with no significant regional or sectoral asymmetries. However, it is worth noting that the scenario assumptions drive a complete blockade of Qatar, which is likely to have a disproportionate impact on the global LNG market. The model's outputs should be read as order-of-magnitude indicators, as they are likely to be affected by various assumptions and simplifications inherent in the analytical-MVP model.

## `mam`  _(commodity: macroeconomic)_

The model output for the Swift Escalated Conflict scenario reveals significant economic disruption, particularly in the energy sector. The headline magnitudes indicate a substantial increase in oil prices, with the model projecting a sustained price of $80 per barrel from 2026 onwards. This is a stark increase from the pre-conflict price path, suggesting a severe impact on the global economy.

The likely meaning of these numbers for the corresponding commodity system is a sharp contraction in economic activity, particularly in regions heavily reliant on oil imports. The energy sector is likely to be severely affected, with reduced demand for oil and natural gas leading to a decline in production and supply chain disruptions. The model's output suggests a prolonged period of economic disruption, with the conflict lasting for several months and causing significant losses to the global economy.

The regional dispersion summary indicates that no regional dispersion was detected for this model, suggesting that the economic impact of the conflict is relatively uniform across regions. However, it is worth noting that the scenario assumptions drive a pattern of economic disruption that is likely to be most severe in regions heavily reliant on oil imports, such as the MENA_GCC region. This region is likely to be hit hardest due to its dependence on oil exports and its proximity to the conflict zone.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model's output is based on a simplified representation of the global economy and should be interpreted with caution.

## `marketsim`  _(commodity: oil)_

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in significant economic disruption. The model outputs suggest that the global oil price increases by approximately 50% due to the disruption, while natural gas prices rise by 20%. The closure lasts for 4 months, causing a substantial loss in consumer surplus, estimated at $50.85 billion. This loss is primarily driven by the oil price shock, with the oil consumer surplus loss estimated at $46.93 billion.

The producer surplus change also indicates a significant impact on the oil market, with an increase of $28.16 billion. However, the net welfare impact is negative, at -$20.34 billion, suggesting that the overall economic impact of the scenario is detrimental. The model also estimates that the oil demand destruction is approximately 0.57 million barrels per day, while the gas demand destruction is around 1.76 billion cubic feet per day. Additionally, there is a significant amount of fuel switching from oil to gas, with an estimated 277.57 million MMBTU of oil demand being replaced by gas.

The regional dispersion summary does not indicate any significant regional disparities in the impact of the scenario. However, the sectoral breakdown of the consumer surplus loss suggests that the transport sector is hit the hardest, with an estimated loss of $32.38 billion. The industrial sector also experiences a significant loss, at $10.79 billion. In contrast, the residential and commercial sectors experience relatively smaller losses.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as they are derived from an analytical-MVP model. The actual economic impact of such a scenario may differ significantly. Additionally, the model's sparse outputs for the regional dispersion summary suggest that the regional impact of the scenario is relatively uniform, with no clear regional disparities.

## `mpsge_jl`  _(commodity: macroeconomic)_

The Swift Escalated Conflict scenario, which involves a military escalation between Iran and a US/Israel coalition resulting in the closure of the Strait of Hormuz, has significant implications for the global economy. The model output suggests that the global GDP impact would be around -0.87%, with the US, China, India, and the EU experiencing negative impacts ranging from -0.70% to -1.79%. On the other hand, the MENA_GCC region is expected to experience a positive GDP impact of 2.68%, likely due to the increased demand for their oil and gas exports.

The model also predicts significant price shocks for various commodities, including oil (58.25%), LNG (126.39%), and fertilizer (23.76%). The closure of the Strait of Hormuz would disrupt global trade, leading to increased costs and reduced consumption. The model output suggests that the global consumption impact would be around -1.97%, with the US, China, and the EU experiencing negative impacts ranging from -1.80% to -3.91%. The MENA_GCC region, on the other hand, is expected to experience a positive consumption impact of 2.29%.

Regional and sectoral asymmetries are evident in the model output. The MENA_GCC region is expected to be relatively insulated from the negative impacts of the conflict, likely due to the increased demand for their oil and gas exports. In contrast, the SSA region is expected to experience a significant negative GDP impact of -1.17%, likely due to their reliance on imported oil and gas. The model output also suggests that the energy sector would experience a positive output impact of 0.58%, likely due to the increased demand for oil and gas exports.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as they are based on analytical-MVP models that are subject to various assumptions and uncertainties. The actual impacts of the Swift Escalated Conflict scenario could be significantly different from the model output.

## `nrel`  _(commodity: macroeconomic)_

The Swift Escalated Conflict scenario, as modeled by the nrel system, yields several headline magnitudes that paint a picture of significant economic disruption. The natural gas price increase is projected to be around 126.4%, indicating a substantial spike in the cost of this critical energy commodity. This, in turn, is likely to have a ripple effect on the broader energy system, with the retail electricity price expected to rise by 56.9%. The model also suggests that the generation mix will shift, with renewables increasing their share from 21% to 33.6%, while natural gas-fired generation decreases by 22.6%.

The economic impact of the scenario is substantial, with the model predicting a 4.5% decline in GDP and a 1.26% increase in the Consumer Price Index (CPI) inflation rate. The welfare impact, which captures the overall well-being of the population, is expected to decrease by 0.95%. These numbers imply that the Swift Escalated Conflict scenario would have far-reaching consequences for the global economy, with significant effects on energy markets, economic output, and household welfare.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the scenario's impact is relatively uniform across different regions and sectors, although this may be due to the simplifying assumptions of the model rather than any inherent characteristic of the scenario itself. It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results, which should be read as order-of-magnitude indicators rather than precise predictions. As such, they provide a rough estimate of the potential consequences of the Swift Escalated Conflict scenario rather than a detailed, nuanced analysis.

## `poles_jrc`  _(commodity: oil)_

The Swift Escalated Conflict scenario, as modeled by the poles_jrc model, yields significant disruptions to the global oil market. The peak price of Brent crude oil reaches $126.6 per barrel, a 58.25% increase from the baseline price of $80.0 per barrel. This price spike is likely driven by the 4-month closure of the Strait of Hormuz, which accounts for approximately 21% of global oil supply. The model estimates that the supply loss due to the disruption amounts to 4.32 million barrels per day (mbd), which is 4.235% of the global oil supply.

The rerouting of oil shipments and substitution of oil with alternative energy sources are estimated to mitigate some of the supply loss, with 4.32 mbd of oil being rerouted and 0 mbd being substituted. However, these measures are insufficient to fully offset the supply loss, resulting in a significant price increase. The disruption duration of 4 months is consistent with the scenario description, where the conflict escalates in February 2026 and a ceasefire is announced in June 2026.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the disruption to the global oil market is relatively uniform, with all regions experiencing similar price increases and supply losses. However, it is essential to note that this is likely an oversimplification of the actual effects of the scenario, as regional economies and energy markets may respond differently to the disruption.

It is crucial to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications may not capture the full complexity of the scenario, and actual outcomes may differ.

## `pycge`  _(commodity: macroeconomic)_

The Swift Escalated Conflict scenario, which involves a 4-month closure of the Strait of Hormuz, results in significant economic disruption. The model predicts a global GDP impact of -0.7889%, with a corresponding decline in GDP growth rate. The headline magnitudes suggest a substantial economic contraction, likely driven by the disruption to global oil and LNG trade.

The model's outputs imply that the commodity system will experience significant price shocks, with oil prices increasing by 58.25% and LNG prices by 25%. The fertilizer market is also expected to be affected, with prices increasing by 23.76%. The helium market, however, is expected to remain relatively insulated, with no price shock predicted. The scenario assumptions drive these patterns, as the closure of the Strait of Hormuz would disrupt the global supply of oil and LNG, leading to price increases. The fertilizer market is also affected, as the closure would impact the global supply of fertilizers, which are often transported through the Strait of Hormuz.

Regional and sectoral asymmetries are evident in the model's outputs. The MENA_GCC region is expected to experience a GDP impact of 2.5054%, making it the region most insulated from the economic disruption. In contrast, the SSA region is expected to experience a GDP impact of -1.3677%, making it the region most affected. The SSA region's high inflation rate of 4.1518% is also noteworthy, suggesting that the region will experience significant price pressures. The sectoral output change also reveals that the energy sector is expected to experience a positive impact of 0.34%, while the services sector is expected to experience a negative impact of 0.6267%.

It is essential to keep in mind that these outputs are from an analytical-MVP model, which should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs are based on a simplified representation of the commodity system and should be interpreted with caution.

## `weap_mena`  _(commodity: water)_

The Swift Escalated Conflict scenario, as modeled by weap_mena, yields significant disruptions to the global water supply. The model predicts a 30% loss in desalination capacity, which translates to a 30% effective loss in water supply for the affected regions. This is a substantial blow, considering that the Strait of Hormuz closure affects countries heavily reliant on desalination, such as Qatar, Saudi Arabia, and the UAE.

The model's outputs suggest that the water deficit will be substantial, with a cumulative water deficit of 212.42% over 16 weeks. This implies that the affected regions will experience severe water shortages, with unmet demand reaching 13.28% of total demand. The population affected by this shortage is estimated to be around 30 million people. The model also highlights the varying degrees of dependence on desalination across the region, with countries like the UAE and Qatar being the most affected.

Regional dispersion analysis reveals no significant disparities in the impact of the scenario across different regions. However, it is worth noting that the scenario's assumptions drive a high degree of regional asymmetry in terms of water dependence. Countries in the MENA_GCC region, such as Qatar, Saudi Arabia, and the UAE, are heavily reliant on desalination, making them more vulnerable to disruptions in the Strait of Hormuz. In contrast, regions like the US, China, and the EU are less dependent on desalination and are likely to be relatively insulated from the effects of this scenario.

It is essential to keep in mind that these outputs are analytical-MVP estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs are based on a simplified representation of the complex systems involved and should be used as a starting point for further analysis and refinement.

## `world_fertilizer`  _(commodity: fertilizer_agriculture)_

The Swift Escalated Conflict scenario has significant implications for the global fertilizer market. The model predicts a 25% increase in natural gas prices, which is a key input for fertilizer production. This price hike is likely to lead to a 30% loss in Middle Eastern fertilizer production, as the region is heavily reliant on natural gas for its fertilizer manufacturing.

The model also forecasts a 49.75% increase in nitrogen prices, which is a critical component of fertilizers. This price surge is likely to have a ripple effect on the entire fertilizer market, leading to a 23.76% increase in the overall fertilizer price index. The prices of specific fertilizers, such as urea, DAP, and MOP, are also expected to rise by 49.75%, 2.49%, and 2.49%, respectively.

The scenario assumptions drive a significant disruption in global trade flows, with Middle Eastern exports declining by 30%. In contrast, the US, Russia, and Algeria are expected to see increases in their fertilizer exports, by 6%, 8.4%, and 4.8%, respectively. This regional dispersion is likely due to the fact that the Middle East is heavily reliant on natural gas for its fertilizer production, while other regions have more diversified energy sources and production bases.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as the model is an analytical MVP. The actual impacts of the Swift Escalated Conflict scenario may vary depending on various factors, including the duration and intensity of the conflict, the effectiveness of any subsequent ceasefire, and the responses of governments and industries to the crisis.

## `world_helium_model`  _(commodity: helium_semiconductors)_

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in a helium supply disruption that is effectively zero according to the model output. This is likely because the model assumes that the disruption is short-lived, lasting only 4 months, and that the helium supply chain is resilient enough to withstand the closure of the Strait of Hormuz. The equilibrium price of helium, which is the price at which supply and demand are balanced, remains the same as the baseline price, indicating that the disruption does not have a significant impact on the helium market.

The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. This suggests that the disruption does not have a significant impact on the demand for helium across different sectors. However, the rationing share by sector indicates that the aerospace defense sector is disproportionately affected by the disruption, with a rationing share of 14.85%. This may be because the aerospace defense sector relies heavily on helium for its operations, and the disruption to the supply chain has a significant impact on its ability to access helium.

The regional dispersion summary indicates that there is no regional dispersion detected for this model, meaning that the disruption to the helium supply chain does not have a significant impact on different regions. This is likely because the model assumes that the disruption is short-lived and that the helium supply chain is resilient enough to withstand the closure of the Strait of Hormuz. However, it is worth noting that the model output should be read as order-of-magnitude indicators, and the actual impact of the disruption may be different in reality.

It is also worth noting that the model output is sparse, and there is limited information available about the impact of the disruption on different regions and sectors. Therefore, the reader should be cautious when interpreting the results and consider them as a rough estimate of the potential impact of the disruption rather than a precise prediction.
