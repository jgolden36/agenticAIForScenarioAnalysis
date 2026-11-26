# Stage 5 commentary audit for run `rev_20261102_llama8b_r2`

551 numeric tokens across 84 sections: {'exact': 427, 'unmatched': 42, 'multiplier_to_pct': 15, 'x100': 42, 'sign_dropped': 25}.

`x100` is correct for a fraction written as a percent and wrong for a value already in percent, so each row needs reading. `unmatched` means the number equals no output of that model; it may be a scenario assumption rather than an error.

## By model

| model | tokens | exact | sign dropped | multiplier as pct | x100 | unmatched |
|---|---|---|---|---|---|---|
| ais_project | 15 | 11 | 0 | 0 | 0 | 4 |
| aisdb | 33 | 27 | 0 | 1 | 0 | 5 |
| apsim | 33 | 14 | 8 | 9 | 0 | 2 |
| argonne_abm | 25 | 20 | 0 | 0 | 5 | 0 |
| cwatm | 18 | 10 | 0 | 1 | 5 | 2 |
| energy_flux_gas_power | 19 | 17 | 0 | 0 | 0 | 2 |
| fed_oil | 25 | 20 | 0 | 0 | 3 | 2 |
| futures | 23 | 16 | 0 | 0 | 1 | 6 |
| lngst | 37 | 35 | 0 | 0 | 0 | 2 |
| marketsim | 50 | 37 | 7 | 0 | 0 | 6 |
| mpsge_jl | 50 | 40 | 4 | 4 | 0 | 2 |
| nrel | 42 | 30 | 4 | 0 | 5 | 3 |
| poles_jrc | 40 | 36 | 0 | 0 | 0 | 4 |
| pycge | 36 | 34 | 2 | 0 | 0 | 0 |
| weap_mena | 42 | 38 | 0 | 0 | 4 | 0 |
| world_fertilizer | 33 | 30 | 0 | 0 | 1 | 2 |
| world_helium_model | 30 | 12 | 0 | 0 | 18 | 0 |

## Tokens restating a value x100

| scenario | model | token | sentence |
|---|---|---|---|
| infrastructure_collapse | argonne_abm | 9 | The model predicts a 9% effective supply shock, with a 5-month disruption duration. |
| infrastructure_collapse | argonne_abm | 19 | The model also estimates a 19% equilibrium price change, indicating a substantial increase in helium prices. |
| infrastructure_collapse | argonne_abm | 0.6 | This could lead to unmet demand, with an estimated 0.6% of demand going unmet. |
| infrastructure_collapse | argonne_abm | 0.4 | The model further predicts a critical application failure rate of 0.4%, which could have significant consequences for industries that rely on helium. |
| infrastructure_collapse | world_helium_model | 9 | The model output also indicates a 9% effective supply gap, which is likely to lead to rationing in the helium market. |
| infrastructure_collapse | world_helium_model | 31.98 | The sector allocation share of helium demand reveals that MRI medical applications will be disproportionately affected, accounting for approximately 31.98% of the total demand rationing, followed closely by semiconductors at 27.98%. |
| infrastructure_collapse | world_helium_model | 27.98 | The sector allocation share of helium demand reveals that MRI medical applications will be disproportionately affected, accounting for approximately 31.98% of the total demand rationing, followed closely by semiconductors at 27.98%. |
| prolonged_contained | cwatm | 100 | The desalination capacity factor is at 100%, indicating that desalination plants are operating at full capacity, and the demand factor is also at 100%, suggesting that water demand is met without any issues. |
| prolonged_contained | cwatm | 100 | The desalination capacity factor is at 100%, indicating that desalination plants are operating at full capacity, and the demand factor is also at 100%, suggesting that water demand is met without any issues. |
| prolonged_contained | fed_oil | 121 | The Consumer Price Index (CPI) is expected to rise by 121% in the peak quarter, driven by the increased oil prices. |
| prolonged_contained | fed_oil | 34.03 | The unemployment rate is expected to rise by 34.03% in the peak quarter, indicating a significant impact on the labor market. |
| prolonged_contained | world_helium_model | 32 | The sectoral allocation of helium demand remains relatively stable, with the medical imaging (MRI) sector accounting for 32% of demand, followed by semiconductors at 28%. |
| prolonged_contained | world_helium_model | 28 | The sectoral allocation of helium demand remains relatively stable, with the medical imaging (MRI) sector accounting for 32% of demand, followed by semiconductors at 28%. |
| prolonged_contained | world_helium_model | 12 | The aerospace defense sector, which is often sensitive to disruptions in the global helium supply, is allocated only 12% of demand. |
| prolonged_escalated | argonne_abm | 61.9 | The unmet demand for helium is estimated to be around 61.9%, indicating a significant shortage in the market. |
| prolonged_escalated | cwatm | 100 | The desalination capacity factor is at 100%, implying that desalination plants, which are critical for providing drinking water in many regions, are operating at full capacity. |
| prolonged_escalated | cwatm | 100 | The demand factor is also at 100%, indicating that water demand is not reduced due to the conflict. |
| prolonged_escalated | futures | 121 | This implies a substantial price increase, with Oil and LNG prices potentially reaching 121% of their initial values. |
| prolonged_escalated | weap_mena | 42 | This is likely to have severe economic and social consequences, particularly in countries with high desalination dependence, such as the UAE (42% dependence) and Qatar (60% dependence). |
| prolonged_escalated | weap_mena | 60 | This is likely to have severe economic and social consequences, particularly in countries with high desalination dependence, such as the UAE (42% dependence) and Qatar (60% dependence). |
| prolonged_escalated | world_helium_model | 26 | The sectoral allocation of helium demand reveals that the medical imaging (MRI) sector accounts for approximately 30% of total demand, followed by semiconductors at around 26%. |
| prolonged_escalated | world_helium_model | 11 | The aerospace defense sector also accounts for a significant share, at around 11%. |
| prolonged_escalated | world_helium_model | 20 | The rationing share by sector shows that the medical imaging sector is disproportionately affected by the supply shortage, with a rationing share of around 20%. |
| swift_contained | cwatm | 100 | The model also indicates that the desalination capacity factor remains at 100%, implying that these critical facilities continue to operate at full capacity throughout the scenario. |
| swift_contained | fed_oil | 5 | The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in significant economic disruption. |
| swift_contained | nrel | 50 | The retail passthrough coefficient of 0.5 suggests that 50% of the increase in natural gas prices is passed through to consumers in the form of higher electricity prices. |
| swift_contained | nrel | 43 | The generation share of natural gas in the power mix decreases from 43% to 31.8%, while the share of renewables increases from 21% to 26.1%. |
| swift_contained | nrel | 31.8 | The generation share of natural gas in the power mix decreases from 43% to 31.8%, while the share of renewables increases from 21% to 26.1%. |
| swift_contained | nrel | 21 | The generation share of natural gas in the power mix decreases from 43% to 31.8%, while the share of renewables increases from 21% to 26.1%. |
| swift_contained | nrel | 26.1 | The generation share of natural gas in the power mix decreases from 43% to 31.8%, while the share of renewables increases from 21% to 26.1%. |
| swift_contained | weap_mena | 5 | The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in significant disruptions to global water supply. |
| swift_contained | weap_mena | 5 | The cumulative water deficit percentage over the 5-day period is approximately 13.28%, indicating a significant shortage of water in these regions. |
| swift_contained | world_fertilizer | 25 | This implies that the disruption to global oil supply and LNG trade, which affects approximately 21% of global oil supply and 25% of global LNG trade, does not significantly affect the fertilizer market. |
| swift_contained | world_helium_model | 32 | The sector allocation shares indicate that the helium market is primarily driven by the MRI medical sector (32%), followed by semiconductors (28%), cryogenics research (20%), aerospace defense (12%), and other sectors (8%). |
| swift_contained | world_helium_model | 28 | The sector allocation shares indicate that the helium market is primarily driven by the MRI medical sector (32%), followed by semiconductors (28%), cryogenics research (20%), aerospace defense (12%), and other sectors (8%). |
| swift_contained | world_helium_model | 20 | The sector allocation shares indicate that the helium market is primarily driven by the MRI medical sector (32%), followed by semiconductors (28%), cryogenics research (20%), aerospace defense (12%), and other sectors (8%). |
| swift_contained | world_helium_model | 12 | The sector allocation shares indicate that the helium market is primarily driven by the MRI medical sector (32%), followed by semiconductors (28%), cryogenics research (20%), aerospace defense (12%), and other sectors (8%). |
| swift_contained | world_helium_model | 8 | The sector allocation shares indicate that the helium market is primarily driven by the MRI medical sector (32%), followed by semiconductors (28%), cryogenics research (20%), aerospace defense (12%), and other sectors (8%). |
| swift_escalated | world_helium_model | 32 | The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. |
| swift_escalated | world_helium_model | 28 | The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. |
| swift_escalated | world_helium_model | 20 | The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. |
| swift_escalated | world_helium_model | 14.85 | However, the rationing share by sector indicates that the aerospace defense sector is disproportionately affected by the disruption, with a rationing share of 14.85%. |
