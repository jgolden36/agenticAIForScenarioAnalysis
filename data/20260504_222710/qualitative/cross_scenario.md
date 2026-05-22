# Cross-scenario qualitative comparison — run `20260504_222710`

Each section below collects one model's qualitative narrative across every scenario in which it produced output. Use this to spot models whose behaviour is robust to scenario assumptions versus those that swing widely.

## `ais_project`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario suggests significant economic disruption to the global shipping system. The Strait of Hormuz remains closed for 4 months, with no rerouting of ships via the Cape of Good Hope. This implies that the global oil supply and LNG trade are severely impacted, with no notable adjustments to shipping routes or capacity utilization.

The model output indicates that the global shipping system is able to maintain its baseline capacity and tanker rates, with no notable losses in fleet capacity or changes in tanker rates. However, the disruption duration of 4 months is likely to have significant economic implications, particularly for regions that rely heavily on oil and LNG imports. The lack of regional dispersion in the model output suggests that the disruption is relatively evenly distributed across the globe, with no notable regional or sectoral asymmetries.

It is worth noting that the model output should be read as order-of-magnitude indicators, given that this is an analytical-MVP output. The actual economic impacts of the Prolonged Contained Conflict scenario may be more complex and nuanced, and may depend on various factors such as the specific trade relationships and supply chains affected by the disruption.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, where the Strait of Hormuz is closed for 4 months, has significant implications for the global shipping system. The model output suggests that the closure of the Strait of Hormuz results in minimal disruption to the global shipping system, with the effective fleet capacity loss at 0%. This implies that the global shipping system is able to adapt to the disruption, possibly through rerouting or other measures, and maintain its overall capacity.

However, the model output also indicates that the closure of the Strait of Hormuz leads to a significant increase in voyage days lost, with the disruption duration being 4 months. This suggests that the closure of the Strait of Hormuz has a substantial impact on the global shipping system, particularly in terms of the time it takes for goods to be transported. The lack of regional dispersion detected by the model implies that the disruption is relatively evenly distributed across different regions, with no particular region or sector being hit harder than others.

It is worth noting that the model output should be taken as an order-of-magnitude indicator, rather than a precise prediction. The scenario assumptions drive the pattern of disruption, and the lack of regional dispersion may be due to the model's simplifications or the specific assumptions made about the scenario. Additionally, the model's sparse output suggests that there may be other factors at play that are not captured by the model, and further analysis may be necessary to fully understand the implications of the Swift Escalated Conflict scenario.


## `aisdb`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario reveals significant disruptions to global shipping, particularly in the Strait of Hormuz. The closure of the Strait, which lasted for 4 months, resulted in a 9.5-day increase in transit time for vessels taking the Cape of Good Hope route, with a maximum additional transit time of 9.5 days. This implies a substantial delay in the delivery of oil and liquefied natural gas (LNG) to global markets.

The model estimates that the fleet utilization drop for LNG carriers and tankers would be around 35.2% and 29.7%, respectively, indicating a significant reduction in the capacity of these vessels to transport goods. The effective fleet capacity loss is estimated to be around 31.2%, further exacerbating the disruption to global shipping. The rerouting cost multiplier of 1.1869 suggests that the cost of transporting goods via alternative routes would be approximately 18.7% higher than usual.

The regional dispersion summary indicates that there is no significant regional dispersion in the model output, implying that the disruptions to global shipping are relatively uniform across different regions. However, it is worth noting that the scenario assumptions drive a significant impact on the MENA_GCC region, which is heavily reliant on the Strait of Hormuz for trade. The war risk insurance premium increase of 200% suggests that the risk of conflict in the region would significantly increase, making it more expensive for companies to insure their vessels.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's sparse outputs for regional dispersion and sectoral asymmetries suggest that further analysis is required to fully understand the implications of this scenario.

### Swift Escalated Conflict (`swift_escalated`)

The model output for the Swift Escalated Conflict scenario reveals significant disruptions to global shipping, particularly in the Strait of Hormuz. The headline magnitudes include a 9.5-day increase in transit time for vessels taking the Cape of Good Hope route, a 31.2% effective fleet capacity loss, and a 35.2% drop in fleet utilization for LNG carriers. These numbers imply a substantial impact on the global shipping system, with LNG carriers being hit particularly hard.

The scenario's assumptions drive these outcomes, as the closure of the Strait of Hormuz would force vessels to take longer routes, such as the Cape of Good Hope, resulting in increased transit times and costs. The model's outputs suggest that the rerouting of vessels would come at a significant cost, with a multiplier of 1.1869 indicating a substantial increase in expenses. Additionally, the war risk insurance premium would surge to 200%, further exacerbating the economic burden on shipping companies.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs, suggesting that the impact of the scenario is relatively uniform across different regions. However, it is essential to note that the model's outputs should be read as order-of-magnitude indicators, and the actual effects may vary depending on various factors, such as the specific routes taken by vessels and the response of shipping companies to the crisis.


## `apsim`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario suggests that the fertilizer application and irrigation water reduction are negligible, with fertilizer application reduction at 0% and irrigation water reduction at 0%. This implies that the agricultural sector is not significantly impacted by the conflict, at least in terms of fertilizer and water usage. The growing season is predicted to be winter, which is consistent with the scenario's geographical location in the Middle East.

The crop yield changes are also minimal, with no yield loss predicted for wheat, rice, and maize. This is surprising given the disruption to global trade and supply chains caused by the conflict. However, the model's outputs should be taken as order-of-magnitude indicators, and the actual impact may be more significant. The nitrogen use efficiency, which measures the effectiveness of nitrogen application in crops, remains unchanged at 25%.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs. This means that the impact of the conflict is not disproportionately felt in any particular region. However, it is worth noting that the scenario assumes a closure of the Strait of Hormuz, which would have a significant impact on global trade and supply chains. The lack of regional dispersion in the model's outputs may be due to the simplifying assumptions made in the scenario or the model's inability to capture the full complexity of the situation.

It is essential to keep in mind that these outputs are from an analytical-MVP model, and the results should be read as order-of-magnitude indicators rather than precise predictions. The actual impact of the conflict may be more significant, and further analysis is needed to fully understand the effects of the scenario.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, as modeled by apsim, yields a relatively benign outcome for the fertilizer_agriculture commodity system. The model predicts no reduction in fertilizer application, irrigation water, or crop yields across the board. This suggests that the conflict's impact on global food production is minimal, with no significant losses in wheat, rice, or maize yields.

The lack of regional dispersion in the model's output implies that the effects of the conflict are evenly distributed across the world, with no particular region or sector being disproportionately affected. This is likely due to the model's assumptions about the conflict's scope and duration, which may not have been severe enough to cause significant disruptions in global food production.

It's worth noting that the model's outputs should be taken as order-of-magnitude indicators rather than precise predictions. The scenario's assumptions, such as the closure of the Strait of Hormuz for 4 months, may not have been fully captured by the model's parameters. As such, the results should be interpreted as a rough estimate of the conflict's potential impact on the fertilizer_agriculture commodity system rather than a precise forecast.

Given the sparse nature of the model's output, it's difficult to draw more nuanced conclusions about the scenario's implications for specific regions or sectors. However, the overall picture suggests that the Swift Escalated Conflict is unlikely to have a significant impact on global food production, at least in the short term.


## `cwatm`

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario model output indicates a significant disruption to the global water supply system. The unmet demand percentage is approximately 9.09%, suggesting that nearly 1 in 11 people globally will not have access to sufficient water. This is likely due to the closure of Persian Gulf desalination plants, which serve tens of millions of people.

The mean discharge deviation percentage is 0.0%, indicating that the model did not detect any changes in water discharge patterns. However, the cumulative water deficit percentage over 36.36 months implies a substantial long-term water shortage. This is consistent with the scenario's assumption of a prolonged closure of the Strait of Hormuz, which would disrupt global trade and supply chains.

The desalination capacity factor is at 1.0, suggesting that desalination plants are operating at full capacity to meet the increased demand. However, the supply infrastructure status is "damaged", implying that the plants may be operating at reduced efficiency or capacity. The demand factor is 1.1, indicating a 10% increase in water demand due to the crisis.

The disruption duration of 4 months is consistent with the scenario's assumption of a ceasefire in June 2026, which would allow the Strait of Hormuz to reopen to commercial shipping. However, the long-term cumulative water deficit suggests that the effects of the crisis may be felt for an extended period.

There is no regional dispersion summary available for this model, so we cannot identify which regions or sectors are hit hardest by the crisis. However, it is likely that regions with existing water scarcity issues, such as the Middle East and North Africa, would be disproportionately affected by the closure of desalination plants.


## `energy_flux_gas_power`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario reveals significant disruptions to the global LNG trade. By 2035, the cumulative added capacity for the LNG system is projected to reach 101.35 GW, with a corresponding increase in incremental production of 7.6 Bcf per day at the mid-point estimate. This suggests a substantial increase in global LNG supply, but one that is likely to be insufficient to meet the growing demand for the commodity.

The model's output also highlights the importance of direct current (DC) and non-DC capacity in the LNG system. By 2035, DC capacity is projected to reach 37.5 GW, while non-DC capacity is expected to reach 63.85 GW. This suggests that non-DC capacity will continue to play a significant role in the LNG system, particularly in regions with limited access to DC infrastructure.

Unfortunately, the regional dispersion summary does not provide any insights into the regional or sectoral impacts of the Prolonged Contained Conflict scenario. This suggests that the model's output is likely to be a global average, rather than a detailed breakdown of regional or sectoral impacts.

It is worth noting that these outputs should be read as order-of-magnitude indicators, rather than precise predictions. The model's assumptions and limitations should be taken into account when interpreting these results. Additionally, the scenario's assumptions drive the pattern of regional or sectoral impacts, but the exact nature of these impacts is not specified in the output.

### Swift Contained Conflict (`swift_contained`)

The model output for the Swift Contained Conflict scenario reveals significant implications for the global LNG trade. The total pipeline capacity is projected to reach 252,000 MW by 2035, with a cumulative added capacity of 101.35 GW by 2030 and 101.35 GW by 2035. This suggests a substantial increase in LNG supply, which could help mitigate the effects of the Strait of Hormuz closure.

The model's yearly results indicate that the added construction capacity will be around 10,135 MW in 2026, with a cumulative added capacity of 10.135 GW. This capacity will continue to increase, reaching 101.35 GW by 2035. The incremental BCF per day is projected to increase from 0.558 to 10.695 by 2035, indicating a significant increase in LNG supply. The blended BCF per day is also projected to increase, reaching 9.130 by 2035.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. However, it is worth noting that the Strait of Hormuz closure primarily affects the MENA region, which is a major LNG producer and exporter. The scenario assumptions drive this pattern, as the closure of the Strait of Hormuz would have a direct impact on the LNG trade in the region.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators. The actual numbers may vary depending on various factors, including changes in global demand, supply chain disruptions, and technological advancements.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario has significant implications for the global LNG trade. The model output suggests that the cumulative added capacity for the LNG system will reach 101.35 GW by 2035, with a corresponding increase in incremental production. This implies a substantial increase in the global LNG supply, which could help mitigate the effects of the conflict on the energy market.

However, the model output also highlights the significant disruption caused by the conflict in the short term. In 2026, the cumulative added capacity is only 10.135 GW, with a blended production of 0.913 Bcf per day. This suggests that the conflict will have a significant impact on the global LNG supply in the initial years, leading to shortages and price increases. The model output also suggests that the DC capacity will be significantly affected, with a DC effective capacity of 0.695 in 2026.

The regional dispersion summary is empty, indicating that the model output does not provide any information on regional or sectoral asymmetries. However, based on the scenario description, it is likely that the regions most affected by the conflict will be those with the highest dependence on LNG imports, such as the MENA region. The conflict will likely disrupt the supply of LNG to these regions, leading to shortages and price increases.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as the model is an analytical-MVP. The actual numbers may vary depending on various factors, including the effectiveness of the conflict resolution and the response of the global energy market.


## `fed_oil`

### Infrastructure Collapse (Tail Risk) (`infrastructure_collapse`)

The model output for the Infrastructure Collapse (Tail Risk) scenario suggests a severe disruption to the global oil market. The peak oil price increase is estimated to be around 48.36%, which is a significant jump from the baseline. This likely means that the global economy will experience a substantial shock, with far-reaching consequences for industries that rely heavily on oil.

The model also projects a prolonged disruption to the oil market, with the Strait of Hormuz remaining closed for approximately 5 quarters. This prolonged disruption will likely have a lasting impact on the global economy, with the GDP impact peaking at around -1.54% in the second quarter of 2026. The inflation rate is also expected to rise, with the peak CPI impact projected to be around 2.06% in the second quarter of 2026.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. However, it is worth noting that the scenario assumptions drive a global impact, with no specific regions or sectors being explicitly mentioned as being hit hardest or relatively insulated. This suggests that the model is treating the scenario as a global event with far-reaching consequences.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results, which should be read as order-of-magnitude indicators rather than precise predictions. The model is likely to be sensitive to various assumptions and parameters, and the actual outcomes may differ from these projections.

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario suggests significant economic disruption. The oil price is expected to increase by 60.5% due to the supply shock caused by the closure of the Strait of Hormuz. This price hike is likely to have a ripple effect on the global economy, with the GDP impact peaking at -0.6806% in the first quarter after the conflict. The Consumer Price Index (CPI) is expected to rise by 1.21% in the same quarter, while the unemployment rate is expected to increase by 0.3403% points.

The model also projects a decline in the Federal Funds Rate (FFR) by 0.605% points in the first quarter, which is likely a response to the economic downturn. The FFR is expected to continue declining over the next few quarters, reaching a low of -0.0584% points by the eighth quarter. The disruption is expected to last for one quarter, with the economy slowly recovering over the subsequent quarters.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. This is likely because the model assumes a global supply shock, which affects all regions equally. However, it is worth noting that the scenario assumptions drive a relatively uniform impact across regions, which may not reflect real-world complexities.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results, which should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications may not capture all the nuances of a real-world crisis, and the actual outcomes may differ from these projections.

### Prolonged Escalated Conflict (`prolonged_escalated`)

The model output for the Prolonged Escalated Conflict scenario suggests significant disruptions to the global economy. The oil price is expected to increase by 51.82% due to the supply shock caused by the closure of the Strait of Hormuz. This price hike is likely to have far-reaching consequences for the global economy, including a peak GDP impact of -0.8258% and a peak CPI impact of 1.101%.

The prolonged conflict is expected to have a lasting impact on the global economy, with the GDP impact persisting for several quarters. The model output suggests that the economy will take around 1.75 quarters to recover from the shock, with the GDP impact gradually decreasing over time. The peak unemployment impact is expected to be 0.4129%, indicating a moderate increase in unemployment rates.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. However, it is worth noting that the Strait of Hormuz is a critical chokepoint for global oil trade, and the closure is likely to have a disproportionate impact on regions that rely heavily on oil imports. The MENA_GCC region, which includes countries such as Saudi Arabia and the UAE, may be particularly affected due to its proximity to the conflict zone and its reliance on oil exports.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results and should be read as order-of-magnitude indicators rather than precise predictions. The model output is based on a simplified representation of the global economy and should be interpreted in the context of the scenario assumptions.

### Swift Contained Conflict (`swift_contained`)

The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in significant economic disruption. The model output indicates that the oil price increases by 54.79% due to the supply shock. This substantial price hike likely means that oil demand will be severely impacted, leading to a ripple effect throughout the global economy.

The model projects a peak GDP impact of -0.6164% and a peak CPI impact of 1.0958% in the first quarter after the crisis. This suggests that the global economy will experience a moderate recession, with inflation rising due to the increased oil prices. The unemployment rate is expected to increase by 0.3082% in the first quarter, indicating a slight rise in joblessness.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. This is likely because the Strait of Hormuz is a critical chokepoint for global oil trade, and the disruption is expected to be felt globally. However, it is essential to note that the model output is an analytical-MVP (Minimum Viable Product) and should be read as an order-of-magnitude indicator rather than a precise prediction.

It is also worth noting that the model output assumes a contained conflict, where the crisis is resolved within a short period. In reality, the situation could be more complex, and the actual economic impact may be more severe. Therefore, these numbers should be taken as a rough estimate rather than a definitive prediction.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in significant economic disruption. The model output indicates that the oil price is expected to increase by 58.25% due to the supply shock. This is a substantial increase, likely to have far-reaching consequences for the global economy.

The disruption is expected to last for one quarter, with the peak impact on GDP occurring at -0.6553% in the same quarter. This suggests that the global economy will experience a significant contraction in the short term. The peak impact on inflation (CPI) is expected to be 1.165% in the same quarter, indicating a moderate increase in prices. The Federal Funds Rate (FFR) is expected to increase by 0.5825% in the same quarter, which is a relatively small increase compared to the other impacts.

The regional dispersion summary does not indicate any significant regional or sectoral asymmetries in this scenario. This is likely because the Strait of Hormuz is a critical chokepoint for global oil trade, and the disruption is expected to have a relatively uniform impact on the global economy. However, it is worth noting that the model output is an analytical-MVP (Minimum Viable Product) and should be read as an order-of-magnitude indicator rather than a precise prediction.

It is also worth noting that the model output does not provide any information on the impact of the conflict on specific regions or sectors, such as the Persian Gulf or the global helium supply. This is likely because the model is focused on the global economy as a whole, and the regional dispersion summary is not available for this scenario.


## `futures`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario indicates significant price shocks for oil and LNG. The forward price curves for both commodities show a steady increase over the forecast horizon, with peak price indices of 1.21 for both oil and LNG. This implies a substantial increase in prices, with oil and LNG prices potentially doubling or more over the course of the scenario.

The initial price shock of 21% for oil and 25% for LNG suggests a severe disruption to global supply chains, with the Strait of Hormuz closure having a major impact on global trade. The fact that the model does not provide a time to normalization for either commodity suggests that the price shock may be long-lasting, with prices potentially remaining elevated for an extended period.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model output. This suggests that the price shock is global in nature, with all regions and sectors potentially feeling the impact of the Strait of Hormuz closure. However, it is worth noting that the model output should be read as order-of-magnitude indicators, and the actual impact may vary depending on a range of factors, including the specific assumptions made about the scenario and the model's underlying parameters.

It is also worth noting that the model output does not provide any information on the impact of the scenario on other commodities or sectors, such as fertilizer or agriculture. This is likely due to the fact that the model is focused on the fertilizer_agriculture commodity system, and the output is limited to oil and LNG prices.

### Swift Escalated Conflict (`swift_escalated`)

The model output for the Swift Escalated Conflict scenario indicates significant price shocks for Oil and LNG, with peak price indices of 1.21 for both commodities. This represents a substantial increase in prices, likely driven by the disruption to global supply chains and the closure of the Strait of Hormuz. The initial price shock of 21% for Oil and 25% for LNG suggests a severe and immediate impact on global markets.

The time to normalization for both Oil and LNG is null, indicating that the model does not forecast a return to pre-crisis prices within the forecast horizon of 4 months. This implies that the economic disruption caused by the conflict could be prolonged, with prices remaining elevated for an extended period. The forecast horizon of 4 months suggests that the model is focused on the short-term impact of the crisis, rather than long-term recovery.

The regional dispersion summary indicates that no regional dispersion was detected for this model. This means that the model output does not suggest significant differences in the impact of the crisis across different regions. However, it is worth noting that the scenario assumptions drive a global impact, with the closure of the Strait of Hormuz affecting global supply chains and prices. In a real-world scenario, regional and sectoral asymmetries would likely be present, with some regions or sectors being more insulated from the crisis than others.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model output is likely to be sensitive to the specific assumptions and parameters used, and further analysis would be required to refine the estimates and understand the underlying drivers of the crisis.


## `lngst`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario suggests significant disruptions to the global LNG market. The Qatar export reduction is estimated at 100%, implying that Qatar, the world's largest LNG exporter, is effectively blockaded. This is consistent with the scenario description, where Qatar is blockaded due to the conflict in the Strait of Hormuz. The UAE export reduction is estimated at 0%, indicating that the UAE is relatively insulated from the disruption.

The model also estimates a global supply shortfall of 20.37% and a supply shortfall of 36.667 billion cubic meters (bcm) over the 4-month disruption period. This translates to an annualised supply shortfall of 110 bcm. The implied price impulse is estimated at 50.926%, suggesting a significant increase in LNG prices. The model also estimates the Henry Hub price to be $5.188 per million British thermal units (mmbtu), the TTF price to be $24.903 per mmbtu, and the JKM price to be $28.438 per mmbtu.

The regional dispersion summary indicates that there is no regional dispersion detected for this model. This means that the model output does not suggest any significant regional or sectoral asymmetries in the impact of the Prolonged Contained Conflict scenario. However, it is worth noting that the scenario description implies that the disruption will have significant regional implications, particularly for the Persian Gulf region and the countries that rely on desalination plants for water supply.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model output should be used as a starting point for further analysis and refinement.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, which involves the closure of the Strait of Hormuz, has significant implications for the global LNG market. The model output suggests that Qatar, the world's largest LNG exporter, would experience a complete reduction in exports, while the UAE would not be affected. This is likely due to the blockade imposed on Qatar, effectively cutting off its ability to export LNG.

The model also predicts a substantial increase in the spot price of LNG, with a multiplier of 1.5, indicating a significant price surge. The disruption is expected to last for 4 months, causing a supply shortfall of approximately 36.67 billion cubic meters (bcm) and an annualised supply shortfall of 110 bcm. This represents a global supply shortfall of around 20.37%. The implied price impulse is also substantial, at 50.93%.

The model output does not provide a detailed regional dispersion summary, indicating that the scenario's impact is likely to be felt globally, with no significant regional or sectoral asymmetries. However, it is worth noting that the scenario assumptions drive a complete blockade of Qatar, which is likely to have a disproportionate impact on the global LNG market. The model's outputs should be read as order-of-magnitude indicators, as they are likely to be affected by various assumptions and simplifications inherent in the analytical-MVP model.


## `mam`

### Infrastructure Collapse (Tail Risk) (`infrastructure_collapse`)

The Infrastructure Collapse (Tail Risk) scenario model output reveals significant economic disruption and commodity price shocks. The model projects a substantial decline in global oil supply, with the Strait of Hormuz closure causing a 21% reduction in global oil supply. This is likely to lead to a sharp increase in oil prices, with the model suggesting a sustained price of around $80 per barrel from 2026 onwards.

The model's output also implies a severe impact on the global economy, with significant economic disruption and potential recession. The closure of the Strait of Hormuz and the blockade of Qatar's LNG exports are likely to lead to shortages and price increases in the global energy market. The model's output suggests that the global economy will experience a significant downturn, with potential recessionary pressures building from 2026 onwards.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's output. This suggests that the scenario assumptions drive a relatively uniform impact across regions, with no clear regional or sectoral asymmetries emerging from the model's output. However, it is worth noting that the model's output is likely to be an order-of-magnitude indicator, rather than a precise prediction. The actual impact of the scenario will depend on a range of factors, including the effectiveness of emergency response measures and the resilience of different economies.

It is also worth noting that the model's output is based on a relatively simple scenario assumption, with no explicit consideration of potential secondary effects or feedback loops. As such, the model's output should be read as a rough order-of-magnitude indicator, rather than a precise prediction.

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario reveals significant economic disruption. The headline magnitudes indicate a substantial impact on global oil supply and LNG trade, with the closure of the Strait of Hormuz disrupting approximately 21% of global oil supply and 25% of global LNG trade. This likely means a sharp increase in oil and gas prices, as well as a significant reduction in global energy availability.

The model output also suggests a substantial impact on the global economy, with the disruption causing economic disruption to grow over the course of the conflict. However, the regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model output. This suggests that the impact of the conflict is relatively uniform across different regions and sectors.

It's worth noting that the model output is likely an order-of-magnitude indicator, rather than a precise prediction. The scenario assumptions drive the pattern of disruption, with the closure of the Strait of Hormuz being the primary driver of economic disruption. The model output should be read as a rough estimate of the potential impact of the conflict, rather than a precise prediction.

One caveat to keep in mind is that the model output is based on a simplified representation of the global economy and energy system. The actual impact of the conflict may be more complex and nuanced, with different regions and sectors being affected in different ways.

### Prolonged Escalated Conflict (`prolonged_escalated`)

The model output for the Prolonged Escalated Conflict scenario reveals significant economic disruption. The headline magnitudes indicate a substantial decline in global economic activity, with the model projecting a 7-month closure of the Strait of Hormuz causing significant economic disruption. The output suggests a prolonged period of economic hardship, with the global economy experiencing a prolonged downturn.

The model's commodity system is macroeconomic, implying that the output reflects the broader economic impacts of the conflict. The scenario's assumptions, such as the closure of the Strait of Hormuz and the blockade of Qatar, likely drive the model's projections of economic disruption. The output suggests that the global economy is severely impacted, with the model projecting a significant decline in economic activity.

The regional dispersion summary indicates that there is no regional dispersion detected for this model. This means that the model does not provide information on which regions or sectors are hit hardest by the conflict. However, given the scenario's assumptions, it is likely that the regions most affected would be those with significant trade and economic ties to the Middle East, such as the US, EU, and MENA_GCC.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators. The model's projections are likely to be subject to significant uncertainty and should be interpreted with caution. Additionally, the output's sparse nature in certain areas, such as the regional dispersion summary, highlights the need for further analysis and refinement to better understand the implications of the Prolonged Escalated Conflict scenario.

### Swift Contained Conflict (`swift_contained`)

The model output for the Swift Contained Conflict scenario reveals significant economic disruption, particularly in the energy sector. The headline magnitudes indicate a substantial impact on global oil supply, with the Strait of Hormuz closure disrupting approximately 21% of global oil supply. This is likely to have a ripple effect on the global economy, with potential shortages and price increases in the oil market.

The model output also suggests a significant impact on the global LNG trade, with the closure disrupting approximately 25% of global LNG trade. This is likely to have a major impact on countries that rely heavily on imported LNG, such as Japan and South Korea. The disruption to Qatar's LNG exports, which accounts for a significant portion of global LNG trade, is likely to be particularly severe.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model output. This suggests that the disruption to global oil and LNG supply is relatively evenly distributed across regions and sectors. However, it is worth noting that the model output is likely to be an order-of-magnitude indicator, rather than a precise prediction. The actual impact of the Swift Contained Conflict scenario may vary depending on a range of factors, including the duration of the closure and the effectiveness of any mitigation measures.

It is also worth noting that the model output does not provide any information on the impact of the scenario on other sectors, such as the global helium supply or the Persian Gulf desalination plants. This is likely due to the limited scope of the model, which is focused on the macroeconomic impacts of the scenario.

### Swift Escalated Conflict (`swift_escalated`)

The model output for the Swift Escalated Conflict scenario reveals significant economic disruption, particularly in the energy sector. The headline magnitudes indicate a substantial increase in oil prices, with the model projecting a sustained price of $80 per barrel from 2026 onwards. This is a stark increase from the pre-conflict price path, suggesting a severe impact on the global economy.

The likely meaning of these numbers for the corresponding commodity system is a sharp contraction in economic activity, particularly in regions heavily reliant on oil imports. The energy sector is likely to be severely affected, with reduced demand for oil and natural gas leading to a decline in production and supply chain disruptions. The model's output suggests a prolonged period of economic disruption, with the conflict lasting for several months and causing significant losses to the global economy.

The regional dispersion summary indicates that no regional dispersion was detected for this model, suggesting that the economic impact of the conflict is relatively uniform across regions. However, it is worth noting that the scenario assumptions drive a pattern of economic disruption that is likely to be most severe in regions heavily reliant on oil imports, such as the MENA_GCC region. This region is likely to be hit hardest due to its dependence on oil exports and its proximity to the conflict zone.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model's output is based on a simplified representation of the global economy and should be interpreted with caution.


## `marketsim`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario reveals significant economic disruption to the global oil and natural gas markets. The oil price shock is estimated to be around 50%, indicating a substantial increase in the cost of oil. This is likely to have a ripple effect on the global economy, impacting various sectors that rely heavily on oil.

The disruption to the natural gas market is less severe, with a price change of around 20%. However, the closure of the Strait of Hormuz also affects the global helium supply, which is not explicitly quantified in the model output. The disruption duration is estimated to be around 4 months, which is consistent with the scenario description. The economic impact of the disruption is substantial, with a total consumer surplus loss of around $50.9 billion. This loss is primarily driven by the oil sector, with the transport sector being the hardest hit, accounting for around $32.4 billion of the loss.

The regional dispersion summary indicates that there is no significant regional dispersion in the model output. This suggests that the economic impact of the disruption is relatively uniform across different regions. However, it is worth noting that the scenario assumptions drive the closure of the Strait of Hormuz, which is a critical chokepoint for global oil trade. This may lead to a more uniform impact across regions, as the disruption affects a critical component of the global energy supply chain.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model output provides a useful starting point for further analysis and should be refined and validated with additional data and assumptions.

### Swift Contained Conflict (`swift_contained`)

The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in a 10% price shock for oil, a 5% price increase for natural gas, and a minimal economic disruption. The oil price shock is likely to have a significant impact on the global economy, as oil is a critical component of many industries and transportation systems. The price increase for natural gas, while smaller, may still have noticeable effects on industries that rely heavily on gas, such as power generation and industrial processes.

The model estimates that the consumer surplus loss, which measures the total welfare loss to consumers, is approximately $436 billion. This loss is primarily driven by the oil price shock, with the transport sector bearing the brunt of the loss, accounting for $272 billion of the total. The producer surplus change, which measures the total welfare gain to producers, is estimated to be $236 billion for oil and $25 billion for gas. The net welfare impact, which takes into account both consumer and producer surplus changes, is estimated to be a loss of $174 billion.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs. This suggests that the scenario assumptions do not drive significant differences in the impact of the Strait of Hormuz closure across different regions. However, it is worth noting that the model's outputs are likely to be order-of-magnitude indicators, rather than precise estimates, given the analytical-MVP nature of the model.

It is also worth noting that the model's outputs do not capture the potential long-term effects of the scenario, such as changes in investment patterns or shifts in global supply chains. Additionally, the model's assumption of a contained conflict, where the closure is limited to 5 days, may not accurately reflect the potential consequences of a more prolonged or escalated conflict.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in significant economic disruption. The model outputs suggest that the global oil price increases by approximately 50% due to the disruption, while natural gas prices rise by 20%. The closure lasts for 4 months, causing a substantial loss in consumer surplus, estimated at $50.85 billion. This loss is primarily driven by the oil price shock, with the oil consumer surplus loss estimated at $46.93 billion.

The producer surplus change also indicates a significant impact on the oil market, with an increase of $28.16 billion. However, the net welfare impact is negative, at -$20.34 billion, suggesting that the overall economic impact of the scenario is detrimental. The model also estimates that the oil demand destruction is approximately 0.57 million barrels per day, while the gas demand destruction is around 1.76 billion cubic feet per day. Additionally, there is a significant amount of fuel switching from oil to gas, with an estimated 277.57 million MMBTU of oil demand being replaced by gas.

The regional dispersion summary does not indicate any significant regional disparities in the impact of the scenario. However, the sectoral breakdown of the consumer surplus loss suggests that the transport sector is hit the hardest, with an estimated loss of $32.38 billion. The industrial sector also experiences a significant loss, at $10.79 billion. In contrast, the residential and commercial sectors experience relatively smaller losses.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as they are derived from an analytical-MVP model. The actual economic impact of such a scenario may differ significantly. Additionally, the model's sparse outputs for the regional dispersion summary suggest that the regional impact of the scenario is relatively uniform, with no clear regional disparities.


## `mpsge_jl`

### Infrastructure Collapse (Tail Risk) (`infrastructure_collapse`)

The Infrastructure Collapse (Tail Risk) scenario, which involves a military escalation between Iran and a US/Israel coalition resulting in the closure of the Strait of Hormuz, yields significant economic disruption. The model predicts a 48.36% shock to oil prices, a 126.39% shock to LNG prices, and a 30.32% shock to fertilizer prices. The trade cost multiplier increases by 18.69%, indicating a significant increase in trade costs due to rerouting and other disruptions.

These price shocks and trade disruptions have far-reaching consequences for the global economy. The model predicts a 1.04% decline in global GDP, a 2.66% increase in the Consumer Price Index (CPI) inflation rate, and a 2.10% decline in consumption. The welfare of households is expected to decline by 2.10%. The energy sector is expected to experience a 0.69% increase in output, while the services sector is expected to decline by 0.83%.

Regional and sectoral asymmetries are evident in the model's output. The MENA_GCC region is expected to experience a 2.68% increase in GDP, a 1.11% increase in CPI inflation, and a 2.24% increase in consumption. This is likely due to the region's significant oil and gas reserves, which would be less affected by the disruption to global trade. In contrast, the IND region is expected to experience a 2.07% decline in GDP, a 5.24% increase in CPI inflation, and a 4.17% decline in consumption. This is likely due to the region's high dependence on imported energy and other commodities.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results, which should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and limitations should be carefully considered when interpreting these results.

### Prolonged Contained Conflict (`prolonged_contained`)

The Prolonged Contained Conflict scenario, where the Strait of Hormuz is closed for 4 months, results in significant economic disruption. The model predicts a 60.5% price shock for oil, a 126.4% price shock for LNG, and a 23.8% price shock for fertilizer. The trade cost multiplier increases by 18.7%, indicating a significant increase in the cost of trade due to rerouting and other disruptions. These price shocks and trade disruptions have a ripple effect on the global economy, leading to a 0.9% decline in GDP, a 2.8% increase in CPI inflation, and a 2.0% decline in consumption.

The regional impact of the scenario varies significantly. The MENA_GCC region, which includes countries such as Saudi Arabia and the UAE, experiences a 2.7% increase in GDP, a 1.0% increase in CPI inflation, and a 2.3% increase in consumption. This is likely due to the region's relatively high dependence on oil exports, which are not significantly affected by the closure of the Strait of Hormuz. In contrast, the ROW region, which includes countries such as the US and China, experiences a 0.9% decline in GDP, a 2.8% increase in CPI inflation, and a 2.0% decline in consumption.

The sectoral impact of the scenario also varies. The energy sector experiences a 0.6% increase in output, likely due to the increased demand for oil and other energy products. In contrast, the agriculture and services sectors experience declines in output, likely due to the increased cost of trade and the decline in consumption.

It is essential to note that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs are based on a simplified representation of the global economy and should be interpreted with caution.

### Prolonged Escalated Conflict (`prolonged_escalated`)

The Prolonged Escalated Conflict scenario, where the Strait of Hormuz is closed for 7 months, has significant implications for the global economy. The model predicts a 51.82% shock to oil prices, a 126.39% shock to LNG prices, and a 23.76% shock to fertilizer prices. These price shocks are likely to have a ripple effect throughout the commodity system, impacting various sectors and regions.

The model also predicts a 1.43% decline in global GDP, a 3.06% increase in global CPI inflation, and a 2.66% decline in global consumption. These numbers suggest that the prolonged conflict will have a significant impact on the global economy, leading to reduced economic activity and increased prices. The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs, suggesting that the impact of the conflict is relatively uniform across regions.

However, the sectoral output change suggests that the energy sector will experience a 0.99% increase, while the agriculture, industry, and services sectors will experience declines of 0.21%, 0.39%, and 1.16% respectively. This pattern may be driven by the fact that the conflict is centered in the Middle East, a region that is heavily reliant on oil exports. The energy sector may benefit from the increased demand for oil, while other sectors may be impacted by the reduced economic activity and increased prices.

It's worth noting that these outputs should be read as order-of-magnitude indicators, as the model is an analytical-MVP and may not capture all the nuances of the scenario. Additionally, the model's outputs are based on a number of assumptions, including the duration and intensity of the conflict, which may not reflect the actual outcome.

### Swift Contained Conflict (`swift_contained`)

The model output for the Swift Contained Conflict scenario reveals significant economic disruption, with a 54.79% oil price shock and a 50.93% LNG price shock. These price shocks are likely to have far-reaching consequences for the global commodity system, particularly in regions heavily reliant on oil and gas imports. The model also predicts a 1.63% increase in the Consumer Price Index (CPI) globally, indicating a broad-based inflationary impact.

Regional and sectoral impacts vary significantly. The US, China, and India are expected to experience the most severe economic contractions, with GDP impacts of -0.0222%, -0.0354%, and -0.0497%, respectively. In contrast, the MENA_GCC region is expected to experience a GDP growth of 0.0832%, likely due to its relatively low dependence on imported oil and gas. The energy sector is expected to experience a 0.0137% increase in output, while the services sector is expected to contract by 0.02%.

The model output also highlights significant regional disparities in terms of trade flows. The MENA_GCC region is expected to experience a decline in trade flows with China, India, the EU, and the US, ranging from -6.355% to -1.495%. This is likely due to the region's reliance on oil exports, which are expected to be disrupted by the conflict. In contrast, the MENA_GCC region is expected to experience an increase in trade flows with ROW, likely due to its relatively low dependence on imported goods.

It is essential to note that these outputs should be read as order-of-magnitude indicators, given the analytical-MVP nature of the model. The actual impacts may vary depending on various factors, including the duration and intensity of the conflict, as well as the effectiveness of any subsequent economic responses.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, which involves a military escalation between Iran and a US/Israel coalition resulting in the closure of the Strait of Hormuz, has significant implications for the global economy. The model output suggests that the global GDP impact would be around -0.87%, with the US, China, India, and the EU experiencing negative impacts ranging from -0.70% to -1.79%. On the other hand, the MENA_GCC region is expected to experience a positive GDP impact of 2.68%, likely due to the increased demand for their oil and gas exports.

The model also predicts significant price shocks for various commodities, including oil (58.25%), LNG (126.39%), and fertilizer (23.76%). The closure of the Strait of Hormuz would disrupt global trade, leading to increased costs and reduced consumption. The model output suggests that the global consumption impact would be around -1.97%, with the US, China, and the EU experiencing negative impacts ranging from -1.80% to -3.91%. The MENA_GCC region, on the other hand, is expected to experience a positive consumption impact of 2.29%.

Regional and sectoral asymmetries are evident in the model output. The MENA_GCC region is expected to be relatively insulated from the negative impacts of the conflict, likely due to the increased demand for their oil and gas exports. In contrast, the SSA region is expected to experience a significant negative GDP impact of -1.17%, likely due to their reliance on imported oil and gas. The model output also suggests that the energy sector would experience a positive output impact of 0.58%, likely due to the increased demand for oil and gas exports.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as they are based on analytical-MVP models that are subject to various assumptions and uncertainties. The actual impacts of the Swift Escalated Conflict scenario could be significantly different from the model output.


## `nrel`

### Infrastructure Collapse (Tail Risk) (`infrastructure_collapse`)

The Infrastructure Collapse (Tail Risk) scenario model output suggests significant economic disruption and commodity price increases. The model predicts a 126.39% increase in natural gas prices, a 56.88% increase in retail electricity prices, and a 1.32% increase in CO2 emissions. These price increases are likely to have a substantial impact on the macroeconomic commodity system, with potential effects on inflation, GDP, and consumer welfare.

The model also suggests a shift in the generation mix, with natural gas and coal increasing their share of electricity generation, while renewables and nuclear remain relatively stable. This shift is likely driven by the increased cost of natural gas and the resulting need to rely more heavily on other fuels. The model predicts a 22.64% decrease in natural gas generation, a 10% increase in coal generation, and a 12.64% increase in renewables generation.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model output. This suggests that the scenario assumptions have a relatively uniform impact across different regions and sectors. However, it is worth noting that the scenario assumptions drive a significant increase in natural gas prices, which may have a disproportionate impact on regions that rely heavily on natural gas for electricity generation.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results and should be read as order-of-magnitude indicators rather than precise predictions. The model output should be interpreted as a rough estimate of the potential impacts of the Infrastructure Collapse (Tail Risk) scenario rather than a precise forecast.

### Prolonged Contained Conflict (`prolonged_contained`)

The Prolonged Contained Conflict scenario, where the Strait of Hormuz is closed for 4 months, has significant economic implications. The model predicts a 126.39% increase in natural gas prices, which is likely to have a ripple effect on the global economy. This increase in natural gas prices is expected to lead to a 56.88% rise in retail electricity prices, assuming a 50% retail passthrough coefficient.

The model also suggests that the prolonged conflict will lead to a shift in the global energy mix. The share of natural gas in electricity generation is expected to decrease by 22.64%, while the share of coal is expected to increase by 10%. Renewables, on the other hand, are expected to gain 12.64% in dispatch share. This shift is likely driven by the increased cost of natural gas and the resulting shift towards cheaper alternatives.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the impact of the Prolonged Contained Conflict scenario is relatively uniform across different regions and sectors. However, it is worth noting that the model's output should be read as order-of-magnitude indicators, rather than precise predictions. The analytical-MVP nature of the model means that the outputs should be taken as rough estimates rather than exact figures.

The model predicts a 1.32% increase in CO2 emissions, a 1.26% increase in CPI inflation, and a 0.95% decrease in consumption and welfare. The GDP impact is expected to be -0.45%, indicating a moderate economic contraction. These outputs suggest that the Prolonged Contained Conflict scenario will have a significant impact on the global economy, but the effects will be relatively contained and not catastrophic.

### Prolonged Escalated Conflict (`prolonged_escalated`)

The Prolonged Escalated Conflict scenario, as modeled by the nrel system, yields several headline magnitudes that paint a picture of significant economic disruption. The natural gas price increase is projected to be a staggering 126.39%, indicating a substantial spike in the cost of this critical energy commodity. This, in turn, is likely to have far-reaching implications for the macroeconomic system, including a 56.88% increase in retail electricity prices, assuming a 50% retail passthrough coefficient.

The model also suggests that the prolonged conflict will lead to a 1.32% increase in CO2 emissions, a 12.64% gain in renewables dispatch, and a 10% gain in coal dispatch. These changes are likely driven by the increased reliance on coal and renewables as natural gas becomes scarcer and more expensive. The model projects a 7-month duration of the disruption, which is consistent with the scenario description.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs. This suggests that the impacts of the Prolonged Escalated Conflict scenario are relatively uniform across regions, at least in terms of the macroeconomic indicators modeled by the nrel system. However, it is essential to note that this may not be the case in reality, as regional economies and energy systems may respond differently to the disruption.

It is also essential to keep in mind that these outputs should be read as order-of-magnitude indicators rather than precise predictions. The model is an analytical MVP, and its outputs should be used to inform high-level strategic decisions rather than to make precise forecasts.

### Swift Contained Conflict (`swift_contained`)

The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in significant economic and commodity system impacts. The model predicts a 50.9% increase in natural gas prices, which is likely driven by the disruption to global LNG trade, particularly the blockage of Qatar, the world's largest LNG exporter. This price increase will have far-reaching effects on various sectors, including electricity generation and consumption.

The model also forecasts a 22.9% increase in retail electricity prices, which is partly due to the natural gas price increase. However, the electricity demand itself is expected to remain unchanged. This suggests that the electricity sector will be able to absorb the increased costs without significant changes in consumption patterns. The generation mix is also expected to shift, with natural gas-fired power plants seeing a decrease in dispatch, while coal-fired power plants see an increase. Renewables, on the other hand, see a moderate increase in dispatch.

The scenario assumptions drive regional and sectoral asymmetries, but the regional dispersion summary is empty, indicating that the model does not detect any significant regional differences in the impacts. However, it is worth noting that the scenario specifically targets the Persian Gulf region, which is likely to be disproportionately affected by the closure of the Strait of Hormuz. The lack of regional dispersion in the model output may be due to the relatively short duration of the disruption, which may not have allowed for significant regional differences to emerge.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results, which should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs should be used as a starting point for further analysis and refinement.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, as modeled by the nrel system, yields several headline magnitudes that paint a picture of significant economic disruption. The natural gas price increase is projected to be around 126.4%, indicating a substantial spike in the cost of this critical energy commodity. This, in turn, is likely to have a ripple effect on the broader energy system, with the retail electricity price expected to rise by 56.9%. The model also suggests that the generation mix will shift, with renewables increasing their share from 21% to 33.6%, while natural gas-fired generation decreases by 22.6%.

The economic impact of the scenario is substantial, with the model predicting a 4.5% decline in GDP and a 1.26% increase in the Consumer Price Index (CPI) inflation rate. The welfare impact, which captures the overall well-being of the population, is expected to decrease by 0.95%. These numbers imply that the Swift Escalated Conflict scenario would have far-reaching consequences for the global economy, with significant effects on energy markets, economic output, and household welfare.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the scenario's impact is relatively uniform across different regions and sectors, although this may be due to the simplifying assumptions of the model rather than any inherent characteristic of the scenario itself. It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) results, which should be read as order-of-magnitude indicators rather than precise predictions. As such, they provide a rough estimate of the potential consequences of the Swift Escalated Conflict scenario rather than a detailed, nuanced analysis.


## `poles_jrc`

### Swift Contained Conflict (`swift_contained`)

The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in a significant spike in oil prices. The model predicts a peak price of $123.83 per barrel, a 54.79% increase from the baseline price of $80.00 per barrel. This price surge is likely driven by the disruption to global oil supply, with the model estimating a supply loss of 4.38 million barrels per day (mbd), accounting for 4.29% of the global oil supply.

The rerouting of oil shipments and substitution of oil with alternative energy sources are minimal in this scenario, with the model predicting a rerouting volume of 4.38 mbd and no substitution volume. This suggests that the disruption is contained and does not lead to a significant shift in global energy markets. The disruption duration is relatively short, lasting only 0.42 months, which is likely due to the swift containment of the conflict.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in this scenario. This is likely due to the contained nature of the conflict, which does not lead to a significant disruption in global energy markets. However, it is worth noting that the scenario assumptions drive a relatively minor impact on global energy markets, which may not accurately reflect the potential consequences of a prolonged or more severe conflict.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model's sparse outputs and lack of regional dispersion suggest that the scenario is relatively minor, and the results should be interpreted with caution.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, as modeled by the poles_jrc model, yields significant disruptions to the global oil market. The peak price of Brent crude oil reaches $126.6 per barrel, a 58.25% increase from the baseline price of $80.0 per barrel. This price spike is likely driven by the 4-month closure of the Strait of Hormuz, which accounts for approximately 21% of global oil supply. The model estimates that the supply loss due to the disruption amounts to 4.32 million barrels per day (mbd), which is 4.235% of the global oil supply.

The rerouting of oil shipments and substitution of oil with alternative energy sources are estimated to mitigate some of the supply loss, with 4.32 mbd of oil being rerouted and 0 mbd being substituted. However, these measures are insufficient to fully offset the supply loss, resulting in a significant price increase. The disruption duration of 4 months is consistent with the scenario description, where the conflict escalates in February 2026 and a ceasefire is announced in June 2026.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the disruption to the global oil market is relatively uniform, with all regions experiencing similar price increases and supply losses. However, it is essential to note that this is likely an oversimplification of the actual effects of the scenario, as regional economies and energy markets may respond differently to the disruption.

It is crucial to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications may not capture the full complexity of the scenario, and actual outcomes may differ.


## `pycge`

### Infrastructure Collapse (Tail Risk) (`infrastructure_collapse`)

The Infrastructure Collapse (Tail Risk) scenario, which involves a military escalation in the Strait of Hormuz, results in significant economic disruption. The model outputs suggest a substantial impact on the global economy, with a predicted GDP impact of -0.8636% and a corresponding GDP growth rate of -0.8636%. This implies a severe contraction in economic activity, likely driven by the disruption to oil and LNG trade, as well as the blockade of Qatar's LNG exports.

The model also predicts a significant increase in inflation, with a CPI inflation rate of 1.7945%. This is likely due to the supply chain disruptions and the resulting shortages of essential commodities. The predicted impact on consumption is even more severe, with a consumption impact of -1.5814%, indicating a sharp decline in household spending.

Regional dispersion summary reveals significant disparities in the impact of the scenario across different regions. The MENA_GCC region is expected to experience a GDP impact of 2.6286%, a stark contrast to the -1.7661% impact predicted for India (IND). This is likely due to the region's reliance on oil exports and its proximity to the conflict zone. The SSA region is also expected to experience a significant increase in inflation, with a CPI inflation rate of 4.177%, driven by the region's heavy reliance on imported goods and the resulting shortages.

The sectoral output also reveals significant disparities, with the energy sector experiencing a 0.4212% increase in output, while the services sector is expected to decline by 0.6885%. This is likely due to the increased demand for energy-related goods and services, as well as the disruption to global supply chains.

It is essential to note that these outputs are from an analytical-MVP model, which should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and limitations should be carefully considered when interpreting these results.

### Prolonged Contained Conflict (`prolonged_contained`)

The Prolonged Contained Conflict scenario, characterized by a 4-month closure of the Strait of Hormuz, yields significant economic impacts. The model predicts a global GDP impact of -0.8139%, with consumption and welfare experiencing even more pronounced declines of -1.5166% and -1.5166%, respectively. Inflation, as measured by the Consumer Price Index (CPI), is expected to rise by 1.757%. These headline magnitudes suggest a substantial disruption to the global economy, particularly in the energy and commodity sectors.

The regional dispersion summary reveals significant disparities in the impact of the scenario across different regions. The MENA_GCC region, comprising countries such as Saudi Arabia and the UAE, is expected to experience a GDP impact of 2.5929%, with consumption and welfare increasing by 2.3227%. This is likely due to the region's significant oil and gas reserves, which would be less affected by the closure of the Strait of Hormuz. In contrast, the SSA (Sub-Saharan Africa) region is expected to experience a GDP impact of -1.4127%, with consumption and welfare declining by -3.1185%. This is likely due to the region's reliance on imported energy and commodities, which would be disrupted by the closure of the Strait.

The sectoral output change also highlights the impact of the scenario on different sectors. The energy sector is expected to experience a positive impact of 0.349%, while the services sector is expected to decline by -0.6465%. This is likely due to the increased demand for energy and the reduced demand for services as a result of the economic disruption.

It is essential to note that these outputs are from an analytical-MVP model, which should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications should be taken into account when interpreting the results. Additionally, the regional dispersion summary is based on a limited number of regions, and further analysis would be necessary to understand the impact on other regions and sectors.

### Prolonged Escalated Conflict (`prolonged_escalated`)

The Prolonged Escalated Conflict scenario, where the Strait of Hormuz is closed for 7 months, results in significant economic disruption. The model predicts a global GDP impact of -1.06%, with consumption and welfare declining by 1.88% and 1.88%, respectively. The headline magnitudes suggest a substantial economic contraction, likely driven by the closure of the Strait of Hormuz, which disrupts approximately 21% of global oil supply and 25% of global LNG trade.

The model's outputs imply that the commodity system is severely impacted, with oil and LNG prices likely to surge. The predicted inflation rate of 2.07% suggests that the economic disruption is not limited to the energy sector, but has broader implications for the overall economy. The sectoral output change suggests that the energy sector is one of the few sectors that may experience growth, possibly due to increased demand for alternative energy sources.

Regional dispersion summary reveals significant asymmetries in the impact of the scenario. The MENA_GCC region is expected to experience a GDP impact of 3.32%, with consumption and welfare increasing by 2.99%. This is likely due to the region's reliance on oil exports, which may increase in value due to the global shortage. In contrast, the IND region is expected to experience a GDP impact of -2.15%, with consumption and welfare declining by 3.85%. This is likely due to the region's dependence on imported energy and its vulnerability to global economic shocks.

The regional dispersion summary also highlights significant differences in inflation rates, with SSA experiencing an inflation rate of 4.99% and MENA_GCC experiencing an inflation rate of 0.81%. This is likely due to the SSA region's reliance on imported energy and its limited ability to absorb price shocks. The interest rate impact is also asymmetric, with SSA experiencing an interest rate impact of 2.05% and ROW experiencing an interest rate impact of 0.77%. This is likely due to the SSA region's limited access to capital markets and its reliance on external financing.

It is essential to note that the analytical-MVP outputs should be read as order-of-magnitude indicators, rather than precise predictions. The model's assumptions and simplifications may not capture the full complexity of the scenario, and the outputs should be interpreted with caution.

### Swift Contained Conflict (`swift_contained`)

The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in a significant impact on the global economy. The model predicts a 15.7% decline in global GDP, with a corresponding 15.7% reduction in GDP growth rate. This is a substantial hit, indicating that the disruption to oil and LNG trade has far-reaching consequences.

The model also predicts a 1.3% increase in the Consumer Price Index (CPI) inflation rate, which is likely driven by the price shock of oil and LNG. This increase in inflation will have a ripple effect throughout the economy, affecting consumption patterns and household welfare. The model estimates a 6.9% decline in consumption, which is a significant reduction in economic activity.

Regional dispersion summary reveals interesting patterns in the impact of the scenario. The regions that are hit hardest are SSA (Sub-Saharan Africa) with a 2.9% increase in CPI inflation, a 14.3% decline in consumption, and a 1.6% increase in wage impact. This is likely due to SSA's high dependence on imported oil and LNG, as well as its limited ability to diversify its energy sources. On the other hand, MENA_GCC (Middle East and North Africa, Gulf Cooperation Council) is relatively insulated, with a 0.4% increase in CPI inflation, a 0.4% increase in consumption, and a 0.5% increase in wage impact. This is because MENA_GCC is a major oil and gas producer and exporter, and the disruption to its trade is likely to be mitigated by its own production.

It is essential to note that these outputs are from an analytical-MVP model, which should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications should be taken into account when interpreting the results.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, which involves a 4-month closure of the Strait of Hormuz, results in significant economic disruption. The model predicts a global GDP impact of -0.7889%, with a corresponding decline in GDP growth rate. The headline magnitudes suggest a substantial economic contraction, likely driven by the disruption to global oil and LNG trade.

The model's outputs imply that the commodity system will experience significant price shocks, with oil prices increasing by 58.25% and LNG prices by 25%. The fertilizer market is also expected to be affected, with prices increasing by 23.76%. The helium market, however, is expected to remain relatively insulated, with no price shock predicted. The scenario assumptions drive these patterns, as the closure of the Strait of Hormuz would disrupt the global supply of oil and LNG, leading to price increases. The fertilizer market is also affected, as the closure would impact the global supply of fertilizers, which are often transported through the Strait of Hormuz.

Regional and sectoral asymmetries are evident in the model's outputs. The MENA_GCC region is expected to experience a GDP impact of 2.5054%, making it the region most insulated from the economic disruption. In contrast, the SSA region is expected to experience a GDP impact of -1.3677%, making it the region most affected. The SSA region's high inflation rate of 4.1518% is also noteworthy, suggesting that the region will experience significant price pressures. The sectoral output change also reveals that the energy sector is expected to experience a positive impact of 0.34%, while the services sector is expected to experience a negative impact of 0.6267%.

It is essential to keep in mind that these outputs are from an analytical-MVP model, which should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs are based on a simplified representation of the commodity system and should be interpreted with caution.


## `weap_mena`

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, as modeled by weap_mena, yields significant disruptions to the global water supply. The model predicts a 30% loss in desalination capacity, which translates to a 30% effective loss in water supply for the affected regions. This is a substantial blow, considering that the Strait of Hormuz closure affects countries heavily reliant on desalination, such as Qatar, Saudi Arabia, and the UAE.

The model's outputs suggest that the water deficit will be substantial, with a cumulative water deficit of 212.42% over 16 weeks. This implies that the affected regions will experience severe water shortages, with unmet demand reaching 13.28% of total demand. The population affected by this shortage is estimated to be around 30 million people. The model also highlights the varying degrees of dependence on desalination across the region, with countries like the UAE and Qatar being the most affected.

Regional dispersion analysis reveals no significant disparities in the impact of the scenario across different regions. However, it is worth noting that the scenario's assumptions drive a high degree of regional asymmetry in terms of water dependence. Countries in the MENA_GCC region, such as Qatar, Saudi Arabia, and the UAE, are heavily reliant on desalination, making them more vulnerable to disruptions in the Strait of Hormuz. In contrast, regions like the US, China, and the EU are less dependent on desalination and are likely to be relatively insulated from the effects of this scenario.

It is essential to keep in mind that these outputs are analytical-MVP estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs are based on a simplified representation of the complex systems involved and should be used as a starting point for further analysis and refinement.


## `world_fertilizer`

### Prolonged Contained Conflict (`prolonged_contained`)

The prolonged contained conflict scenario has significant implications for the fertilizer market. The model predicts a 25% increase in natural gas prices, which is a key input for fertilizer production. This increase is likely to drive up fertilizer prices, with the model suggesting a 49.75% increase in nitrogen prices, a 2.488% increase in phosphate prices, and a 2.488% increase in potash prices. The fertilizer price index is expected to rise by 23.756%.

The disruption to the Middle East, which accounts for a significant portion of global fertilizer production, is a key driver of these price increases. The model predicts a 30% loss in Middle East production, which would exacerbate the supply shortage and drive up prices. The trade flows also suggest that the US, Russia, and Algeria will see increases in their fertilizer exports, while the Middle East will experience a decline in exports.

The regional dispersion summary indicates that there is no significant regional dispersion in the model's outputs. This suggests that the impact of the prolonged contained conflict is relatively uniform across different regions. However, it is worth noting that the scenario assumptions drive a significant disruption to the Middle East, which is likely to have a disproportionate impact on global fertilizer markets.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model's outputs are based on a simplified representation of the fertilizer market and do not capture all the complexities and nuances of the real-world market. As such, the actual impacts of the prolonged contained conflict may differ from the model's predictions.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario has significant implications for the global fertilizer market. The model predicts a 25% increase in natural gas prices, which is a key input for fertilizer production. This price hike is likely to lead to a 30% loss in Middle Eastern fertilizer production, as the region is heavily reliant on natural gas for its fertilizer manufacturing.

The model also forecasts a 49.75% increase in nitrogen prices, which is a critical component of fertilizers. This price surge is likely to have a ripple effect on the entire fertilizer market, leading to a 23.76% increase in the overall fertilizer price index. The prices of specific fertilizers, such as urea, DAP, and MOP, are also expected to rise by 49.75%, 2.49%, and 2.49%, respectively.

The scenario assumptions drive a significant disruption in global trade flows, with Middle Eastern exports declining by 30%. In contrast, the US, Russia, and Algeria are expected to see increases in their fertilizer exports, by 6%, 8.4%, and 4.8%, respectively. This regional dispersion is likely due to the fact that the Middle East is heavily reliant on natural gas for its fertilizer production, while other regions have more diversified energy sources and production bases.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as the model is an analytical MVP. The actual impacts of the Swift Escalated Conflict scenario may vary depending on various factors, including the duration and intensity of the conflict, the effectiveness of any subsequent ceasefire, and the responses of governments and industries to the crisis.


## `world_helium_model`

### Prolonged Contained Conflict (`prolonged_contained`)

The model output for the Prolonged Contained Conflict scenario suggests that the helium market experiences minimal disruption, with the equilibrium price remaining at $280.0 per million standard cubic feet (mscf), the same as the baseline price. This implies that the helium supply chain is resilient to the closure of the Strait of Hormuz and the blockade of Qatar, the world's largest LNG exporter. The effective supply gap is zero, and there is no demand rationing, indicating that the helium market is able to absorb the disruption without significant shortages.

The sectoral allocation of helium demand remains relatively stable, with the medical imaging (MRI) sector accounting for 32% of demand, followed by semiconductors at 28%. The aerospace defense sector, which is often sensitive to disruptions in the global helium supply, is allocated only 12% of demand. This suggests that the scenario assumptions do not drive significant sectoral asymmetries in the helium market. The inventory drawdown is zero, indicating that there are no stockpiles of helium being depleted during the disruption.

The regional dispersion summary is empty, indicating that the model does not detect any significant regional disparities in the helium market's response to the scenario. This is consistent with the model's output, which suggests that the helium market is able to absorb the disruption without significant shortages or price changes.

It is essential to keep in mind that these outputs are likely order-of-magnitude indicators, given the analytical-MVP nature of the model. The actual effects of the Prolonged Contained Conflict scenario on the helium market may differ from these projections.

### Swift Escalated Conflict (`swift_escalated`)

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in a helium supply disruption that is effectively zero according to the model output. This is likely because the model assumes that the disruption is short-lived, lasting only 4 months, and that the helium supply chain is resilient enough to withstand the closure of the Strait of Hormuz. The equilibrium price of helium, which is the price at which supply and demand are balanced, remains the same as the baseline price, indicating that the disruption does not have a significant impact on the helium market.

The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. This suggests that the disruption does not have a significant impact on the demand for helium across different sectors. However, the rationing share by sector indicates that the aerospace defense sector is disproportionately affected by the disruption, with a rationing share of 14.85%. This may be because the aerospace defense sector relies heavily on helium for its operations, and the disruption to the supply chain has a significant impact on its ability to access helium.

The regional dispersion summary indicates that there is no regional dispersion detected for this model, meaning that the disruption to the helium supply chain does not have a significant impact on different regions. This is likely because the model assumes that the disruption is short-lived and that the helium supply chain is resilient enough to withstand the closure of the Strait of Hormuz. However, it is worth noting that the model output should be read as order-of-magnitude indicators, and the actual impact of the disruption may be different in reality.

It is also worth noting that the model output is sparse, and there is limited information available about the impact of the disruption on different regions and sectors. Therefore, the reader should be cautious when interpreting the results and consider them as a rough estimate of the potential impact of the disruption rather than a precise prediction.

