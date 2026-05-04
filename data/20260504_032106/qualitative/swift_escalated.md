# Qualitative model output narratives — Swift Escalated Conflict

_Run ID: `20260504_032106` · scenario: `swift_escalated`_

> February 2026: The Strait of Hormuz is closed due to a military escalation between Iran and a US/Israel coalition. The closure disrupts approximately 21% of global oil supply and 25% of global LNG trade. Qatar, the world's largest LNG exporter, is effectively blockaded. The disruption also threatens Persian Gulf desalination plants serving tens of millions of people and approximately 30% of global helium supply.
> 
> February 20, 2026: The US and Israel launch a series of airstrikes against Iranian military targets in the Strait of Hormuz. Iran responds with missile and drone strikes against Saudi and UAE targets.
> 
> February 25, 2026: The conflict escalates, with both sides suffering significant losses. The Strait of Hormuz remains closed, causing economic disruption to grow.
> 
> March 2026: The conflict spreads to other regional actors, including Saudi Arabia and the UAE. The Strait of Hormuz remains closed, causing significant economic disruption.
> 
> June 2026: The US and Israel announce a ceasefire, and the Strait of Hormuz is reopened to commercial shipping. The closure lasted for 4 months, causing significant economic disruption.

Below: one section per model with at least one completed output (7 model(s) total). Quantitative tables for the same results live under `csv/raw/swift_escalated/`.

## `cwatm`  _(commodity: water)_

The Swift Escalated Conflict scenario model output indicates a significant disruption to the global water supply system. The unmet demand percentage is approximately 9.09%, suggesting that nearly 1 in 11 people globally will not have access to sufficient water. This is likely due to the closure of Persian Gulf desalination plants, which serve tens of millions of people.

The mean discharge deviation percentage is 0.0%, indicating that the model did not detect any changes in water discharge. However, the cumulative water deficit percentage over 36.36 months implies a substantial long-term water shortage. This is consistent with the scenario's assumption of a 4-month closure of the Strait of Hormuz, which would severely impact the supply of desalinated water to the region.

The desalination capacity factor is at 1.0, suggesting that all desalination capacity is utilized, but this is likely due to the model's assumption of a complete closure of the Strait of Hormuz rather than an actual increase in capacity. The demand factor is 1.1, indicating a 10% increase in water demand, which could be due to the disruption of other water sources or increased usage due to the crisis.

There is no regional dispersion summary available for this model, so we cannot identify which regions or sectors are hit hardest by the scenario. However, it is likely that regions reliant on Persian Gulf desalination plants, such as the MENA_GCC region, would be severely impacted. The scenario assumptions drive this pattern by assuming a complete closure of the Strait of Hormuz, which would severely impact the supply of desalinated water to the region.

It is essential to keep in mind that these outputs are likely order-of-magnitude indicators rather than precise predictions. The model is an analytical MVP, and its outputs should be interpreted as rough estimates rather than exact figures.

## `energy_flux_gas_power`  _(commodity: lng)_

The Swift Escalated Conflict scenario has significant implications for the global LNG trade. The model output suggests that the cumulative added capacity for the LNG system will reach 101.35 GW by 2035, with a corresponding increase in incremental production. This implies a substantial increase in the global LNG supply, which could help mitigate the effects of the conflict on the energy market.

However, the model output also highlights the significant disruption caused by the conflict in the short term. In 2026, the cumulative added capacity is only 10.135 GW, with a blended production of 0.913 Bcf per day. This suggests that the conflict will have a significant impact on the global LNG supply in the initial years, leading to shortages and price increases. The model output also suggests that the DC capacity will be significantly affected, with a DC effective capacity of 0.695 in 2026.

The regional dispersion summary is empty, indicating that the model output does not provide any information on regional or sectoral asymmetries. However, based on the scenario description, it is likely that the regions most affected by the conflict will be those with the highest dependence on LNG imports, such as the MENA region. The conflict will likely disrupt the supply of LNG to these regions, leading to shortages and price increases.

It is essential to note that these outputs should be read as order-of-magnitude indicators, as the model is an analytical-MVP. The actual numbers may vary depending on various factors, including the effectiveness of the conflict resolution and the response of the global energy market.

## `futures`  _(commodity: fertilizer_agriculture)_

The model output for the Swift Escalated Conflict scenario indicates significant price shocks for Oil and LNG, with peak price indices of 1.21 for both commodities. This represents a substantial increase in prices, likely driven by the disruption to global supply chains and the closure of the Strait of Hormuz. The initial price shock of 21% for Oil and 25% for LNG suggests a severe and immediate impact on global markets.

The time to normalization for both Oil and LNG is null, indicating that the model does not forecast a return to pre-crisis prices within the forecast horizon of 4 months. This implies that the economic disruption caused by the conflict could be prolonged, with prices remaining elevated for an extended period. The forecast horizon of 4 months suggests that the model is focused on the short-term impact of the crisis, rather than long-term recovery.

The regional dispersion summary indicates that no regional dispersion was detected for this model. This means that the model output does not suggest significant differences in the impact of the crisis across different regions. However, it is worth noting that the scenario assumptions drive a global impact, with the closure of the Strait of Hormuz affecting global supply chains and prices. In a real-world scenario, regional and sectoral asymmetries would likely be present, with some regions or sectors being more insulated from the crisis than others.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model output is likely to be sensitive to the specific assumptions and parameters used, and further analysis would be required to refine the estimates and understand the underlying drivers of the crisis.

## `mam`  _(commodity: macroeconomic)_

The model output for the Swift Escalated Conflict scenario reveals significant economic disruption, particularly in the energy sector. The headline magnitudes indicate a substantial increase in oil prices, with the model projecting a sustained price of $80 per barrel from 2026 onwards. This is a stark increase from the pre-conflict price path, suggesting a severe impact on the global economy.

The likely meaning of these numbers for the corresponding commodity system is a sharp contraction in economic activity, particularly in regions heavily reliant on oil imports. The energy sector is likely to be severely affected, with reduced demand for oil and natural gas leading to a decline in production and supply chain disruptions. The model's output suggests a prolonged period of economic disruption, with the conflict lasting for several months and causing significant losses to the global economy.

The regional dispersion summary indicates that no regional dispersion was detected for this model, suggesting that the economic impact of the conflict is relatively uniform across regions. However, it is worth noting that the scenario assumptions drive a pattern of economic disruption that is likely to be most severe in regions heavily reliant on oil imports, such as the MENA_GCC region. This region is likely to be hit hardest due to its dependence on oil exports and its proximity to the conflict zone.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) and should be read as order-of-magnitude indicators rather than precise predictions. The model's output is based on a simplified representation of the global economy and should be interpreted with caution.

## `poles_jrc`  _(commodity: oil)_

The Swift Escalated Conflict scenario, as modeled by the poles_jrc model, yields significant disruptions to the global oil market. The peak price of Brent crude oil reaches $126.6 per barrel, a 58.25% increase from the baseline price of $80.0 per barrel. This price spike is likely driven by the 4-month closure of the Strait of Hormuz, which accounts for approximately 21% of global oil supply. The model estimates that the supply loss due to the disruption amounts to 4.32 million barrels per day (mbd), which is 4.235% of the global oil supply.

The rerouting of oil shipments and substitution of oil with alternative energy sources are estimated to mitigate some of the supply loss, with 4.32 mbd of oil being rerouted and 0 mbd being substituted. However, these measures are insufficient to fully offset the supply loss, resulting in a significant price increase. The disruption duration of 4 months is consistent with the scenario description, where the conflict escalates in February 2026 and a ceasefire is announced in June 2026.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the disruption to the global oil market is relatively uniform, with all regions experiencing similar price increases and supply losses. However, it is essential to note that this is likely an oversimplification of the actual effects of the scenario, as regional economies and energy markets may respond differently to the disruption.

It is crucial to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications may not capture the full complexity of the scenario, and actual outcomes may differ.

## `pycge`  _(commodity: macroeconomic)_

The Swift Escalated Conflict scenario, which involves a 4-month closure of the Strait of Hormuz, is projected to have significant economic impacts. The model predicts a 0.7361 percentage point contraction in GDP, which is equivalent to a 0.7361 percentage point decline in GDP growth. This suggests that the global economy will experience a substantial downturn as a result of the conflict.

The model also predicts a 1.415 percentage point increase in the Consumer Price Index (CPI) inflation rate, indicating that the conflict will lead to higher prices for consumers. This is likely due to the disruption in oil and LNG supplies, which are critical components of the global energy mix. The model's sectoral output projections suggest that the energy sector will experience a 0.342 percentage point increase, while the services sector will decline by 0.586 percentage points.

The regional dispersion summary does not indicate any significant regional disparities in the economic impacts of the conflict. However, the sectoral output projections suggest that the agriculture and industry sectors will be disproportionately affected, with declines of 0.0728 and 0.1787 percentage points, respectively. The energy sector, on the other hand, will experience a modest increase.

It is essential to note that these projections are based on the analytical-MVP mode of the model, which should be interpreted as order-of-magnitude indicators rather than precise forecasts. The model's outputs are also sensitive to the assumptions made about the duration and intensity of the conflict, as well as the specific commodity price shocks that occur. As such, these projections should be viewed as a rough guide to the potential economic impacts of the Swift Escalated Conflict scenario rather than a precise prediction.

## `world_helium_model`  _(commodity: helium_semiconductors)_

The Swift Escalated Conflict scenario, which involves a closure of the Strait of Hormuz, results in a helium supply disruption that is effectively zero according to the model output. This is likely because the model assumes that the disruption is short-lived, lasting only 4 months, and that the helium supply chain is resilient enough to withstand the closure of the Strait of Hormuz. The equilibrium price of helium, which is the price at which supply and demand are balanced, remains the same as the baseline price, indicating that the disruption has no lasting impact on the helium market.

The sectoral allocation of helium demand is also relatively unchanged, with MRI medical applications, semiconductors, cryogenics research, aerospace defense, and other sectors accounting for 32%, 28%, 20%, 12%, and 8% of total demand, respectively. However, the rationing share by sector suggests that cryogenics research is disproportionately affected by the disruption, accounting for 29.7% of the total rationing, followed closely by semiconductors and MRI medical applications.

The regional dispersion summary indicates that there is no regional dispersion detected for this model, meaning that the model does not predict any significant differences in the impact of the disruption across different regions. This is likely because the model assumes that the disruption is global in nature, affecting all regions equally.

It's worth noting that these outputs should be read as order-of-magnitude indicators, as the model is an analytical MVP and may not capture all the nuances of the scenario. Additionally, the model's assumption of a short-lived disruption may not reflect the actual impact of a prolonged conflict on the helium supply chain.
