# Stage 5 commentary audit for run `20260504_222710`

338 numeric tokens across 49 sections: {'exact': 270, 'unmatched': 26, 'multiplier_to_pct': 5, 'sign_dropped': 23, 'x100': 14}.

`x100` is correct for a fraction written as a percent and wrong for a value already in percent, so each row needs reading. `unmatched` means the number equals no output of that model; it may be a scenario assumption rather than an error.

## By model

| model | tokens | exact | sign dropped | multiplier as pct | x100 | unmatched |
|---|---|---|---|---|---|---|
| ais_project | 5 | 5 | 0 | 0 | 0 | 0 |
| aisdb | 14 | 12 | 0 | 1 | 0 | 1 |
| apsim | 4 | 3 | 0 | 0 | 0 | 1 |
| cwatm | 9 | 7 | 0 | 1 | 0 | 1 |
| energy_flux_gas_power | 17 | 15 | 0 | 0 | 0 | 2 |
| fed_oil | 24 | 23 | 0 | 0 | 1 | 0 |
| futures | 8 | 6 | 0 | 0 | 0 | 2 |
| lngst | 16 | 16 | 0 | 0 | 0 | 0 |
| mam | 8 | 2 | 0 | 0 | 0 | 6 |
| marketsim | 26 | 17 | 3 | 0 | 0 | 6 |
| mpsge_jl | 66 | 54 | 10 | 2 | 0 | 0 |
| nrel | 35 | 25 | 5 | 0 | 4 | 1 |
| poles_jrc | 18 | 16 | 0 | 0 | 0 | 2 |
| pycge | 56 | 44 | 5 | 1 | 2 | 4 |
| weap_mena | 6 | 6 | 0 | 0 | 0 | 0 |
| world_fertilizer | 17 | 17 | 0 | 0 | 0 | 0 |
| world_helium_model | 9 | 2 | 0 | 0 | 7 | 0 |

## Tokens restating a value x100

| scenario | model | token | sentence |
|---|---|---|---|
| prolonged_contained | nrel | 50 | This increase in natural gas prices is expected to lead to a 56.88% rise in retail electricity prices, assuming a 50% retail passthrough coefficient. |
| prolonged_contained | world_helium_model | 32 | The sectoral allocation of helium demand remains relatively stable, with the medical imaging (MRI) sector accounting for 32% of demand, followed by semiconductors at 28%. |
| prolonged_contained | world_helium_model | 28 | The sectoral allocation of helium demand remains relatively stable, with the medical imaging (MRI) sector accounting for 32% of demand, followed by semiconductors at 28%. |
| prolonged_contained | world_helium_model | 12 | The aerospace defense sector, which is often sensitive to disruptions in the global helium supply, is allocated only 12% of demand. |
| prolonged_escalated | nrel | 50 | This, in turn, is likely to have far-reaching implications for the macroeconomic system, including a 56.88% increase in retail electricity prices, assuming a 50% retail passthrough coefficient. |
| swift_contained | fed_oil | 5 | The Swift Contained Conflict scenario, where the Strait of Hormuz is closed for 5 days, results in significant economic disruption. |
| swift_contained | pycge | 15.7 | The model predicts a 15.7% decline in global GDP, with a corresponding 15.7% reduction in GDP growth rate. |
| swift_contained | pycge | 15.7 | The model predicts a 15.7% decline in global GDP, with a corresponding 15.7% reduction in GDP growth rate. |
| swift_escalated | nrel | 21 | The model also suggests that the generation mix will shift, with renewables increasing their share from 21% to 33.6%, while natural gas-fired generation decreases by 22.6%. |
| swift_escalated | nrel | 33.6 | The model also suggests that the generation mix will shift, with renewables increasing their share from 21% to 33.6%, while natural gas-fired generation decreases by 22.6%. |
| swift_escalated | world_helium_model | 32 | The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. |
| swift_escalated | world_helium_model | 28 | The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. |
| swift_escalated | world_helium_model | 20 | The sectoral allocation of helium demand is also relatively unchanged, with the medical imaging (MRI) sector accounting for 32% of demand, semiconductors for 28%, and cryogenics research for 20%. |
| swift_escalated | world_helium_model | 14.85 | However, the rationing share by sector indicates that the aerospace defense sector is disproportionately affected by the disruption, with a rationing share of 14.85%. |
