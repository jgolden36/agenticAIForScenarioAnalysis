# Qualitative model output narratives — Prolonged Contained Conflict

_Run ID: `20260504_032106` · scenario: `prolonged_contained`_

> February 2026: The Strait of Hormuz is closed due to a military escalation between Iran and a US/Israel coalition. The closure disrupts approximately 21% of global oil supply and 25% of global LNG trade. Qatar, the world's largest LNG exporter, is effectively blockaded. The disruption also threatens Persian Gulf desalination plants serving tens of millions of people and approximately 30% of global helium supply.
> 
> February 20, 2026: The US and Israel launch a series of airstrikes against Iranian military targets in the Strait of Hormuz. Iran responds with missile and drone strikes against Saudi and UAE targets.
> 
> March 2026: The conflict escalates, with both sides suffering significant losses. The Strait of Hormuz remains closed, causing economic disruption to grow.
> 
> June 2026: The US and Israel announce a ceasefire, and the Strait of Hormuz is reopened to commercial shipping. The closure lasted for 4 months, causing significant economic disruption.

Below: one section per model with at least one completed output (5 model(s) total). Quantitative tables for the same results live under `csv/raw/prolonged_contained/`.

## `energy_flux_gas_power`  _(commodity: lng)_

The model output for the Prolonged Contained Conflict scenario reveals significant disruptions to the global LNG trade. By 2035, the cumulative added capacity for the LNG system is projected to reach 101.35 GW, with a corresponding increase in incremental production of 7.6 Bcf per day at the mid-point estimate. This suggests a substantial increase in global LNG supply, but one that is likely to be insufficient to meet the growing demand for the commodity.

The model's output also highlights the importance of direct current (DC) and non-DC capacity in the LNG system. By 2035, DC capacity is projected to reach 37.5 GW, while non-DC capacity is expected to reach 63.85 GW. This suggests that non-DC capacity will continue to play a significant role in the LNG system, particularly in regions with limited access to DC infrastructure.

Unfortunately, the regional dispersion summary does not provide any insights into the regional or sectoral impacts of the Prolonged Contained Conflict scenario. This suggests that the model's output is not sensitive to regional or sectoral differences, or that the scenario assumptions do not drive significant regional or sectoral asymmetries.

It is essential to keep in mind that these outputs are analytical-MVP (Minimum Viable Product) estimates and should be read as order-of-magnitude indicators rather than precise predictions. The model's output is likely to be subject to significant uncertainty and should be treated with caution.

## `futures`  _(commodity: fertilizer_agriculture)_

The model output for the Prolonged Contained Conflict scenario indicates significant price shocks for oil and LNG. The forward price curves for both commodities show a steady increase over the forecast horizon, with peak price indices of 1.21 for both oil and LNG. This implies a substantial increase in prices, with oil and LNG prices potentially doubling or more over the course of the scenario.

The initial price shock of 21% for oil and 25% for LNG suggests a severe disruption to global energy markets. The closure of the Strait of Hormuz, a critical chokepoint for oil and LNG trade, would likely lead to a sharp increase in prices as demand outstrips supply. The model's output suggests that this price shock would persist for at least 4 months, with no indication of normalization in sight.

The regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model's output. This suggests that the price shock is global in nature, with all regions and sectors potentially feeling the effects of the disruption. However, it is worth noting that the model's output should be read as order-of-magnitude indicators, rather than precise predictions. The actual impact of the scenario would depend on a range of factors, including the specifics of the conflict, the response of global markets, and the effectiveness of any mitigation efforts.

It is also worth noting that the model's output does not provide any information on the time to normalization for either oil or LNG. This suggests that the model is not able to predict when prices would return to normal, or if they would at all. This is likely due to the complexity of the scenario and the many variables that would influence the outcome.

## `mam`  _(commodity: macroeconomic)_

The model output for the Prolonged Contained Conflict scenario reveals significant economic disruption. The headline magnitudes indicate a substantial impact on global oil supply and LNG trade, with the closure of the Strait of Hormuz disrupting approximately 21% of global oil supply and 25% of global LNG trade. This likely means a sharp increase in oil and gas prices, as well as a significant reduction in global energy availability.

The model output also suggests a substantial impact on the global economy, with the disruption causing economic disruption to grow over the course of the conflict. However, the regional dispersion summary indicates that there are no significant regional or sectoral asymmetries in the model output. This suggests that the impact of the conflict is relatively uniform across different regions and sectors.

It's worth noting that the model output is likely an order-of-magnitude indicator, rather than a precise prediction. The scenario assumptions drive the pattern of disruption, with the closure of the Strait of Hormuz being the primary driver of economic disruption. The model output should be read as a rough estimate of the potential impact of the conflict, rather than a precise prediction.

One caveat to keep in mind is that the model output is based on a simplified representation of the global economy and energy system. The actual impact of the conflict may be more complex and nuanced, with different regions and sectors being affected in different ways.

## `pycge`  _(commodity: macroeconomic)_

The Prolonged Contained Conflict scenario, where the Strait of Hormuz is closed for 4 months, results in significant economic disruption. The model outputs suggest a substantial impact on the global economy, with a 7.6% decline in GDP, a 7.6% reduction in GDP growth, and a 1.4% increase in CPI inflation. The consumption impact is even more pronounced, with a 13.5% decline, indicating a significant reduction in household spending.

The sectoral output change reveals a mixed picture, with the energy sector experiencing a 35.1% increase, likely due to the increased demand for alternative energy sources. In contrast, the services sector suffers a 6.0% decline, while the industry and agriculture sectors experience declines of 18.4% and 7.4%, respectively. The interest rate impact is a 0.5% increase, which may be a response to the economic disruption.

The regional dispersion summary does not reveal any significant regional disparities in the impact of the scenario. However, the sectoral output change suggests that the energy sector is likely to be a beneficiary of the increased demand for alternative energy sources, while the services sector is likely to be disproportionately affected.

It is essential to note that these outputs are from an analytical-MVP model, which should be read as order-of-magnitude indicators rather than precise predictions. The model's assumptions and simplifications may not capture the full complexity of the scenario, and the actual outcomes may differ.

## `world_helium_model`  _(commodity: helium_semiconductors)_

The model output for the Prolonged Contained Conflict scenario suggests that the helium market experiences minimal disruption, with the equilibrium price remaining at $280.0 per million standard cubic feet (mscf), the same as the baseline price. This implies that the helium supply chain is resilient to the closure of the Strait of Hormuz and the blockade of Qatar, the world's largest LNG exporter. The effective supply gap is zero, and there is no demand rationing, indicating that the helium market is able to absorb the disruption without significant shortages.

The sectoral allocation of helium demand remains relatively stable, with the medical imaging (MRI) sector accounting for 32% of demand, followed by semiconductors at 28%. The aerospace defense sector, which is often sensitive to disruptions in the global helium supply, is allocated only 12% of demand. This suggests that the scenario assumptions do not drive significant sectoral asymmetries in the helium market. The inventory drawdown is zero, indicating that there are no stockpiles of helium being depleted during the disruption.

The regional dispersion summary is empty, indicating that the model does not detect any significant regional disparities in the helium market's response to the scenario. This is consistent with the model's output, which suggests that the helium market is able to absorb the disruption without significant shortages or price changes.

It is essential to keep in mind that these outputs are likely order-of-magnitude indicators, given the analytical-MVP nature of the model. The actual effects of the Prolonged Contained Conflict scenario on the helium market may differ from these projections.
