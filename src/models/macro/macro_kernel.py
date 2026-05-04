"""Closed-form macroeconomic kernel.

A pure-Python, dependency-free module that translates a vector of
commodity price shocks into the standardized macroeconomic outputs
the synthesizer and consistency layer expect:

    gdp_impact_pct
    gdp_growth_pct
    cpi_inflation_pct
    consumption_impact_pct
    welfare_pct_change
    wage_impact_pct
    interest_rate_impact_pct
    sectoral_output_pct_change

The kernel is the shared backbone of two consumer paths:

1. ``PyCGEAdapter`` analytical-MVP fallback. When the optional
   ``cge_modeling`` package is unavailable or its API does not match
   what the adapter expects, ``execute()`` runs this kernel instead so
   the macro tier always has a runnable CGE on the cluster MVP.

2. ``TEMOAAdapter``, ``OSeMOSYSAdapter``, ``MESSAGEixAdapter`` derived
   macro outputs. Each energy-systems adapter translates the
   *operational* shocks it received (oil_supply_loss_mbd,
   gas_supply_loss_bcfd, lng_export_capacity_loss_pct,
   capital_cost_multiplier) into the same commodity_shocks dict via
   ``derive_macro_from_energy_shocks`` and forwards to
   ``compute_macro_outcomes``. The resulting GDP / CPI / consumption /
   welfare estimates are appended to the adapter's output dict and
   tagged ``_macro_source`` so synthesis can distinguish them from a
   first-class CGE solve.

Calibration constants below are module-level with literature citations
in the docstrings, mirroring the analytical-MVP pattern already used by
``src.models.oil.poles_jrc`` (Hamilton 2009; Baumeister & Peersman 2013)
and ``src.models.helium.world_helium_model`` (Massol & Rifaat 2018).
"""

from __future__ import annotations

from typing import Any, Literal

# ---------------------------------------------------------------------------
# Calibration constants
# ---------------------------------------------------------------------------
# All elasticities are expressed as the *sustained* (annual-equivalent)
# response to a 1 percentage-point change in the named shock variable.
# The duration scaler below converts a sustained response into the
# realised cumulative effect over a finite disruption window.

# --- Oil price -> macro ----------------------------------------------------

# Oil price -> GDP elasticity. Hamilton (2003) "What Is an Oil Shock?"
# and Hamilton (2009 Brookings) find a 100% oil price increase reduces
# US real GDP by roughly 2-3% over the subsequent year. Kilian (2008,
# Review of Economics and Statistics) reports a comparable magnitude.
# We pick the lower end of the range for a conservative MVP calibration.
GDP_ELASTICITY_TO_OIL_PCT: float = -0.025  # pp GDP per 1% oil shock

# Oil price -> CPI pass-through. Blanchard & Galí (2007) "The Macroeconomic
# Effects of Oil Shocks" and Kilian & Zhou (2022) "Oil Prices, Exchange
# Rates and Interest Rates" find a 100% oil shock raises core CPI by
# roughly 4 pp share-weighted in the US.
CPI_ELASTICITY_TO_OIL_PCT: float = 0.04  # pp CPI per 1% oil shock

# --- Gas / LNG -> macro ----------------------------------------------------

# Natural gas / LNG -> CPI pass-through. BLS CPI utilities + housing
# weight approximately 0.07; gas share of household energy approximately
# 0.30; pass-through coefficient approximately 1.0 over a year, yielding
# ~0.02 pp CPI per 1% LNG/gas shock. Lower than oil because LNG enters
# CPI through utilities only, not transport.
CPI_ELASTICITY_TO_LNG_PCT: float = 0.02

# Natural gas -> GDP elasticity. About one third of the oil channel
# because gas is less broadly used in transport.
GDP_ELASTICITY_TO_LNG_PCT: float = -0.008

# --- Fertilizer -> ag prices -> macro --------------------------------------

# Fertilizer -> ag PPI pass-through. Baffes (2007) "Oil Spills on
# Other Commodities" and FAO (2022) Fertilizer Outlook find roughly
# 0.6 pass-through from fertilizer to ag PPI.
AG_PPI_ELASTICITY_TO_FERTILIZER_PCT: float = 0.6
# Ag PPI -> CPI knock-on. Food-at-home share of CPI roughly 0.085;
# pass-through from ag PPI to retail food CPI roughly 0.5 over a year.
CPI_ELASTICITY_TO_FERTILIZER_PCT: float = 0.025
# Fertilizer's GDP channel is narrower than oil: it operates via
# agricultural margins, not the whole economy.
GDP_ELASTICITY_TO_FERTILIZER_PCT: float = -0.005

# --- Helium -> semiconductors -> macro -------------------------------------

# Helium -> GDP. Helium is essential for semiconductor fab utilization
# but the affected value-add is small relative to GDP. Massol & Rifaat
# (2018) "The Helium Market Crisis" implies a 100% helium shock lowers
# US semiconductor output by ~5%; semiconductors are ~0.4% of US GDP,
# so the macro elasticity is about -0.0002 per 1% helium shock.
GDP_ELASTICITY_TO_HELIUM_PCT: float = -0.0002
# Helium has no meaningful direct CPI channel (it does not enter the
# consumer basket).
CPI_ELASTICITY_TO_HELIUM_PCT: float = 0.0

# --- Water (infrastructure_collapse only) -> macro -------------------------

# Water unmet-demand percentage -> GDP. UN-Water (2024) "Water and
# Sanitation Progress Report" estimates that a sustained 10 pp drop in
# regional water availability cuts regional output by roughly 1%. The
# US-equivalent macro impact (the synthesizer integrates over a US
# baseline) is smaller because most US production is not water-stressed,
# but the shock channel matters for the prescribed
# infrastructure_collapse scenario where Persian Gulf desalination
# capacity is destroyed.
GDP_ELASTICITY_TO_WATER_PCT: float = -0.01
# Water -> CPI: small (food and bottled-water sub-baskets only).
CPI_ELASTICITY_TO_WATER_PCT: float = 0.005

# --- Generic / fallback ----------------------------------------------------

# A residual elasticity applied to any commodity shock the table above
# does not recognise, so unknown shocks (e.g. a future ammonia shock)
# still register as something rather than nothing. Calibrated to half
# the magnitude of the LNG channel.
GDP_ELASTICITY_TO_OTHER_PCT: float = -0.004
CPI_ELASTICITY_TO_OTHER_PCT: float = 0.01

# --- Wage / interest-rate channels -----------------------------------------

# Wage response per 1 pp CPI increase (sticky-wage Calvo channel,
# annualised). Blanchard & Galí (2007) imply a partial pass-through of
# roughly 0.6 over a year.
WAGE_PASSTHROUGH_TO_CPI: float = 0.6

# Federal-funds-rate Taylor-rule response per 1 pp CPI increase. Taylor
# (1993) coefficient on inflation is 1.5; we use a conservative 0.5 to
# acknowledge the ZLB / forward-guidance era.
INTEREST_RATE_RESPONSE_TO_CPI: float = 0.5

# --- Sectoral cost shares (4-sector decomposition) -------------------------
#
# Used to allocate the aggregate output impact across the four sectors
# present in the bundled SAM (data/sams/hosoe_2region.json). Shares are
# the fraction of value-added contributed by each sector to GDP and the
# fraction of that sector's intermediate input cost that comes from
# energy / fertilizer / water. Rough US calibration; documented here so
# PyCGE's sectoral_output_pct_change is consistent with its declared SAM.

# Sector value-added share of GDP.
SECTOR_GDP_SHARE: dict[str, float] = {
    "agriculture": 0.011,
    "industry": 0.180,
    "energy": 0.038,
    "services": 0.771,
}
# Sector energy-cost share (intermediate energy / total cost).
SECTOR_ENERGY_COST_SHARE: dict[str, float] = {
    "agriculture": 0.07,
    "industry": 0.05,
    "energy": 0.40,    # energy uses energy intensively
    "services": 0.02,
}
# Sector fertilizer-cost share. Only agriculture has a non-trivial share.
SECTOR_FERTILIZER_COST_SHARE: dict[str, float] = {
    "agriculture": 0.18,
    "industry": 0.0,
    "energy": 0.0,
    "services": 0.0,
}

# --- Operational -> price-shock translation (energy adapters) --------------

# Reference global liquids supply (mb/d), 2024 IEA Oil Market Report
# annual average. Used to convert mb/d losses into percent supply shocks.
GLOBAL_OIL_SUPPLY_MBD: float = 102.0
# Short-run oil supply / demand elasticities (same calibration as
# src/models/oil/poles_jrc.py).
ELASTICITY_DEMAND_OIL: float = -0.06
ELASTICITY_SUPPLY_OIL: float = 0.05

# Reference global natural gas supply (bcfd), 2024 IEA Gas 2024 report.
# Used to convert bcfd losses into percent supply shocks.
GLOBAL_GAS_SUPPLY_BCFD: float = 415.0
# Short-run gas supply / demand elasticities. Hauser et al. (2023)
# "Natural Gas Markets and the Russian-Ukraine War" calibration.
ELASTICITY_DEMAND_GAS: float = -0.05
ELASTICITY_SUPPLY_GAS: float = 0.04

# Capital-cost multiplier -> implied capex inflation pass-through to
# capital goods prices, used by energy adapters that received a
# capital_cost_multiplier shock (e.g. a sustained shipping/steel cost
# spike during the disruption window).
CAPEX_TO_CPI_PASSTHROUGH: float = 0.3


# ---------------------------------------------------------------------------
# Regional disaggregation
# ---------------------------------------------------------------------------
#
# The aggregate kernel above is calibrated against US/OECD-average
# elasticities. Regions differ from that baseline along three axes:
#
#   1. Net-trade position in each commodity (oil, gas, fertilizer).
#      Net exporters (MENA_GCC for oil + LNG, parts of MENA_OTHER and
#      ROW for oil) gain on a positive price shock; net importers
#      (CHN, IND, EU, SSA) lose more than the US baseline.
#   2. Energy + food intensity of the local consumption basket. Lower-
#      and middle-income regions (IND, SSA, parts of LAC) have larger
#      pass-through of commodity price shocks into headline CPI because
#      food + transport are a larger share of the basket.
#   3. Direct exposure to the chokepoint (water destruction in the
#      Persian Gulf, helium concentration in semiconductor producers).
#
# The ``REGIONAL_GDP_MULTIPLIERS`` and ``REGIONAL_CPI_MULTIPLIERS`` dicts
# below encode these differences as multiplicative scaling factors on
# the US-baseline elasticities. A value of 1.0 reproduces the US
# response; values > 1.0 amplify it; values < 0 flip the sign (used to
# make oil exporters benefit from a positive oil price shock).
#
# Calibration sources:
#   * IMF (2022) "Regional Economic Outlook: Middle East" -- net oil
#     exporter / importer cross-country GDP elasticities (Table 1.1).
#   * Choi et al. (2018) "Oil Prices and Inflation Dynamics: Evidence
#     from Advanced and Developing Economies" -- regional CPI pass-
#     through (broadly 2x US in EM, especially India and SSA).
#   * Fueki et al. (2018) IMF WP "The Macroeconomic Impact of Oil Price
#     Shocks: A Global Perspective" -- China and India GDP responses.
#   * IEA (2023) "World Energy Outlook 2023" -- LNG-import dependence
#     by region (EU 2023 is roughly 3x the US share of import-driven
#     gas exposure).
#   * World Bank (2023) "Commodity Markets Outlook -- Africa Special
#     Focus" -- SSA fertilizer pass-through (~3x US ag-PPI sensitivity).
#   * UN-Water (2024) Progress Report -- water-stress concentration in
#     the Persian Gulf / MENA region.

UNIFIED_REGIONS: tuple[str, ...] = (
    "US",
    "CHN",
    "IND",
    "EU",
    "MENA_GCC",
    "MENA_OTHER",
    "SSA",
    "LAC",
    "ROW",
)

# Regional multipliers on the US-baseline GDP elasticities (per commodity).
# Negative values denote a sign flip — i.e. the region's GDP responds in
# the opposite direction (net exporters benefit from a positive price
# shock). Magnitudes scale with import-dependence and trade-share data
# from IMF / IEA / World Bank sources cited above.
REGIONAL_GDP_MULTIPLIERS: dict[str, dict[str, float]] = {
    "US":         {"oil": 1.0,  "lng":  0.5, "fertilizer": 1.0, "helium": 2.0,  "water": 0.2},
    "CHN":        {"oil": 1.4,  "lng":  1.5, "fertilizer": 1.5, "helium": 2.5,  "water": 0.5},
    "IND":        {"oil": 2.0,  "lng":  2.0, "fertilizer": 2.5, "helium": 0.5,  "water": 1.5},
    "EU":         {"oil": 1.5,  "lng":  3.0, "fertilizer": 1.2, "helium": 1.5,  "water": 0.3},
    "MENA_GCC":   {"oil": -3.5, "lng": -3.0, "fertilizer": 0.5, "helium": -1.0, "water": 8.0},
    "MENA_OTHER": {"oil": -1.0, "lng": -0.5, "fertilizer": 1.5, "helium":  0.0, "water": 4.0},
    "SSA":        {"oil": 1.8,  "lng":  0.5, "fertilizer": 3.0, "helium":  0.0, "water": 2.0},
    "LAC":        {"oil": 0.5,  "lng":  0.5, "fertilizer": 1.2, "helium":  0.0, "water": 0.5},
    "ROW":        {"oil": 1.0,  "lng":  1.0, "fertilizer": 1.0, "helium":  0.5, "water": 0.5},
}

# Regional multipliers on the US-baseline CPI elasticities. Higher in
# EM economies because food + energy weights in their CPI baskets are
# larger (Choi et al. 2018). MENA_GCC pass-through is suppressed for
# energy because most GCC states subsidize fuel and utilities.
REGIONAL_CPI_MULTIPLIERS: dict[str, dict[str, float]] = {
    "US":         {"oil": 1.0, "lng": 1.0, "fertilizer": 1.0, "helium": 0.0, "water": 0.5},
    "CHN":        {"oil": 1.2, "lng": 1.2, "fertilizer": 1.5, "helium": 0.0, "water": 0.8},
    "IND":        {"oil": 2.0, "lng": 1.8, "fertilizer": 2.5, "helium": 0.0, "water": 2.5},
    "EU":         {"oil": 1.5, "lng": 2.5, "fertilizer": 1.2, "helium": 0.0, "water": 0.5},
    "MENA_GCC":   {"oil": 0.3, "lng": 0.3, "fertilizer": 0.8, "helium": 0.0, "water": 5.0},
    "MENA_OTHER": {"oil": 1.5, "lng": 1.0, "fertilizer": 2.0, "helium": 0.0, "water": 4.0},
    "SSA":        {"oil": 2.5, "lng": 0.8, "fertilizer": 3.5, "helium": 0.0, "water": 2.5},
    "LAC":        {"oil": 1.2, "lng": 0.8, "fertilizer": 1.5, "helium": 0.0, "water": 0.8},
    "ROW":        {"oil": 1.0, "lng": 1.0, "fertilizer": 1.0, "helium": 0.0, "water": 0.5},
}

# Default multiplier for any commodity not listed in the per-region
# table above. Picks up unrecognised shocks (e.g. ``ammonia``) so they
# still propagate regionally rather than silently zero.
DEFAULT_REGIONAL_MULTIPLIER: float = 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_OutputDict = dict[str, Any]
Regime = Literal["short_run", "long_run"]


def _duration_scaler(duration_months: float, regime: Regime) -> float:
    """Translate a sustained (annual-equivalent) response into the
    realised cumulative effect over a finite disruption window.

    For the short-run regime, the scaler is bounded between 0.25 (very
    short window) and 1.5 (sustained ~18 months), reflecting that
    impacts ramp up faster than they decay (Bernanke 2004, "Inflation
    Expectations and Inflation Forecasting"). For the long-run regime
    we use the duration / 12 directly, since long-run welfare and
    structural-adjustment costs scale roughly linearly with the period
    over which the disruption persists.
    """
    months = max(0.0, float(duration_months))
    if regime == "long_run":
        return months / 12.0
    # Short-run: piecewise smooth, bounded.
    annual_equivalent = months / 12.0
    if annual_equivalent <= 0.25:
        return max(0.1, annual_equivalent * 1.5)
    if annual_equivalent <= 1.0:
        return 0.375 + (annual_equivalent - 0.25) * 0.833
    return min(1.5, 1.0 + (annual_equivalent - 1.0) * 0.25)


def _gdp_elasticity_for(commodity: str) -> float:
    return {
        "oil": GDP_ELASTICITY_TO_OIL_PCT,
        "lng": GDP_ELASTICITY_TO_LNG_PCT,
        "gas": GDP_ELASTICITY_TO_LNG_PCT,
        "fertilizer": GDP_ELASTICITY_TO_FERTILIZER_PCT,
        "helium": GDP_ELASTICITY_TO_HELIUM_PCT,
        "water": GDP_ELASTICITY_TO_WATER_PCT,
    }.get(commodity, GDP_ELASTICITY_TO_OTHER_PCT)


def _cpi_elasticity_for(commodity: str) -> float:
    return {
        "oil": CPI_ELASTICITY_TO_OIL_PCT,
        "lng": CPI_ELASTICITY_TO_LNG_PCT,
        "gas": CPI_ELASTICITY_TO_LNG_PCT,
        "fertilizer": CPI_ELASTICITY_TO_FERTILIZER_PCT,
        "helium": CPI_ELASTICITY_TO_HELIUM_PCT,
        "water": CPI_ELASTICITY_TO_WATER_PCT,
    }.get(commodity, CPI_ELASTICITY_TO_OTHER_PCT)


def _sectoral_response(
    commodity_shocks: dict[str, float],
    aggregate_gdp_pct: float,
    duration_scaler: float,
) -> dict[str, float]:
    """Allocate the aggregate GDP impact across the four SAM sectors.

    Each sector's percent-output change has two terms:

    1. A direct cost-pressure term proportional to the sector's
       intermediate-input share for energy and fertilizer. For
       non-energy sectors this is negative on a positive price shock
       (more expensive inputs => less production). For the energy
       sector itself it is positive, since energy producers' revenues
       rise faster than costs on a price shock.

    2. An aggregate-drag term proportional to the sector's
       value-added share of GDP, so sectors that contribute more
       value-added move proportionally with the broader economy.

    Note that GDP_ELASTICITY_TO_OIL_PCT and
    GDP_ELASTICITY_TO_FERTILIZER_PCT are already signed (negative for
    a positive price shock), so the direct-term sign comes from a
    deliberate flip on the energy sector only.
    """
    energy_shock = (
        commodity_shocks.get("oil", 0.0)
        + commodity_shocks.get("lng", 0.0)
        + commodity_shocks.get("gas", 0.0)
    )
    fert_shock = commodity_shocks.get("fertilizer", 0.0)

    out: dict[str, float] = {}
    for sector, gdp_share in SECTOR_GDP_SHARE.items():
        energy_share = SECTOR_ENERGY_COST_SHARE.get(sector, 0.0)
        fert_share = SECTOR_FERTILIZER_COST_SHARE.get(sector, 0.0)

        energy_direct = energy_share * energy_shock * GDP_ELASTICITY_TO_OIL_PCT
        fert_direct = (
            fert_share * fert_shock * GDP_ELASTICITY_TO_FERTILIZER_PCT
        )
        # Energy producers gain margin on a price shock; flip the
        # direct sign for the energy sector only. Fertilizer inputs
        # to the energy sector are negligible (share = 0), so this
        # only affects the energy_direct term in practice.
        if sector == "energy":
            energy_direct = -energy_direct

        aggregate_drag = aggregate_gdp_pct * gdp_share

        sector_pct = (energy_direct + fert_direct) * duration_scaler + aggregate_drag
        out[sector] = round(sector_pct, 4)
    return out


def compute_macro_outcomes(
    commodity_shocks: dict[str, float],
    duration_months: float,
    *,
    regime: Regime = "short_run",
) -> _OutputDict:
    """Translate commodity shocks into standardized macroeconomic outputs.

    Args:
        commodity_shocks: Mapping ``commodity -> percent shock``. Recognised
            keys: ``oil``, ``lng`` (alias ``gas``), ``fertilizer``, ``helium``,
            ``water``. Unknown commodities fall through to the residual
            elasticity. Sign convention: positive percent = price rise.
        duration_months: Disruption duration in months. Drives the
            ``_duration_scaler`` that converts annual-equivalent
            elasticities into realised cumulative impacts.
        regime: ``"short_run"`` (default) or ``"long_run"``. Long-run
            scaling is simply ``duration_months / 12``; short-run is
            piecewise smooth with a 1.5x cap.

    Returns:
        Dict with the standardized macro schema. All percent values are
        rounded to 4 decimal places. Includes ``_inputs`` block with
        provenance for downstream consistency checks.
    """
    # Defensive shock normalisation: drop non-numeric entries instead
    # of crashing on a bad LLM extraction.
    shocks: dict[str, float] = {}
    for k, v in (commodity_shocks or {}).items():
        if isinstance(v, bool):
            continue
        try:
            shocks[str(k).lower()] = float(v)
        except (TypeError, ValueError):
            continue

    scaler = _duration_scaler(duration_months, regime)

    # GDP impact (cumulative over the disruption window).
    gdp_pct = 0.0
    for commodity, shock in shocks.items():
        gdp_pct += _gdp_elasticity_for(commodity) * shock
    gdp_pct *= scaler

    # CPI inflation (annualised over the window).
    cpi_pct = 0.0
    for commodity, shock in shocks.items():
        cpi_pct += _cpi_elasticity_for(commodity) * shock
    # CPI inflation does not need the same duration scaler as GDP --
    # it is naturally annualised. Apply a milder duration adjustment
    # so longer windows still produce slightly higher cumulative CPI
    # responses without over-stating them.
    cpi_pct *= min(1.2, max(0.5, scaler))

    # Consumption impact: real consumption falls roughly with GDP plus
    # a CPI-driven real-income drag. The 0.4 weight reflects that
    # households smooth ~60% of real-income shocks via savings.
    consumption_pct = gdp_pct - 0.4 * cpi_pct

    # Welfare: Hicksian-equivalent change in real consumption. Using
    # the simple deflated consumption metric here keeps the math
    # transparent; richer EV calculations require a full lifetime path.
    welfare_pct = consumption_pct

    # Wages: sticky-wage Calvo pass-through to CPI minus a labour-
    # productivity drag from the GDP shock.
    wage_pct = WAGE_PASSTHROUGH_TO_CPI * cpi_pct + 0.5 * gdp_pct

    # Interest rate: Taylor-rule response to CPI minus output-gap term.
    interest_rate_pct = INTEREST_RATE_RESPONSE_TO_CPI * cpi_pct + 0.25 * gdp_pct

    # GDP growth (year-1 annualised). Distinct from gdp_impact_pct in
    # that the latter is cumulative over the disruption window; the
    # growth-rate version annualises the cumulative impact and so is
    # smaller in magnitude for short windows.
    months = max(0.001, float(duration_months))
    gdp_growth_pct = gdp_pct * min(1.0, 12.0 / months)

    sectoral = _sectoral_response(shocks, gdp_pct, scaler)
    regional = compute_regional_macro_outcomes(
        shocks, duration_months, regime=regime
    )

    return {
        "gdp_impact_pct": round(gdp_pct, 4),
        "gdp_growth_pct": round(gdp_growth_pct, 4),
        "gdp_growth_pct_year1": round(gdp_growth_pct, 4),
        "cpi_inflation_pct": round(cpi_pct, 4),
        "cpi_inflation_pct_year1": round(cpi_pct, 4),
        "consumption_impact_pct": round(consumption_pct, 4),
        "welfare_pct_change": round(welfare_pct, 4),
        "wage_impact_pct": round(wage_pct, 4),
        "interest_rate_impact_pct": round(interest_rate_pct, 4),
        "sectoral_output_pct_change": sectoral,
        "regional_vars": regional,
        "_inputs": {
            "commodity_shocks": shocks,
            "duration_months": float(duration_months),
            "regime": regime,
            "duration_scaler": round(scaler, 4),
        },
        "_calibration_sources": [
            "Hamilton (2003, 2009 Brookings) -- oil -> GDP elasticity",
            "Kilian (2008 RES) -- oil supply shock GDP response",
            "Blanchard & Galí (2007) -- oil -> CPI pass-through",
            "Kilian & Zhou (2022) -- oil + macro pass-through",
            "Baffes (2007) -- fertilizer pass-through",
            "Massol & Rifaat (2018) -- helium market response",
            "UN-Water (2024) Progress Report -- water shortage GDP impact",
        ],
    }


def compute_regional_macro_outcomes(
    commodity_shocks: dict[str, float],
    duration_months: float,
    *,
    regime: Regime = "short_run",
    regions: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Translate commodity shocks into a per-region macro response table.

    Returns one row per region with the same headline macro fields the
    aggregate kernel produces (``gdp_impact_pct``, ``cpi_inflation_pct``,
    ``consumption_impact_pct``, ``welfare_pct_change``, ``wage_impact_pct``,
    ``interest_rate_impact_pct``), each scaled by the per-region
    elasticity multipliers in ``REGIONAL_GDP_MULTIPLIERS`` and
    ``REGIONAL_CPI_MULTIPLIERS``. The output is shaped for the
    synthesizer's ``regional`` distributional spec
    (``configs/distributional_outputs.yaml``): a list of dicts with a
    ``region`` column and numeric value columns.

    Sign conventions match :func:`compute_macro_outcomes`: positive
    commodity shocks denote price rises; negative GDP impacts denote
    output contraction. Net oil + gas exporters (MENA_GCC, parts of
    MENA_OTHER) flip sign through their negative GDP multipliers, so
    they show GDP gains on a positive oil shock.

    Args:
        commodity_shocks: same shape as :func:`compute_macro_outcomes`.
        duration_months: same as :func:`compute_macro_outcomes`.
        regime: same as :func:`compute_macro_outcomes`.
        regions: subset of ``UNIFIED_REGIONS`` to report. ``None`` (the
            default) reports every region.

    Returns:
        List of dicts in stable region order. Empty list if no
        ``commodity_shocks`` are provided. ``GLOBAL`` is intentionally
        excluded — it is reserved for true world aggregates produced by
        multi-region models like MIRAGRODEP.
    """
    shocks: dict[str, float] = {}
    for k, v in (commodity_shocks or {}).items():
        if isinstance(v, bool):
            continue
        try:
            shocks[str(k).lower()] = float(v)
        except (TypeError, ValueError):
            continue

    target_regions = tuple(regions) if regions else UNIFIED_REGIONS
    scaler = _duration_scaler(duration_months, regime)

    rows: list[dict[str, Any]] = []
    for region in target_regions:
        gdp_mult_table = REGIONAL_GDP_MULTIPLIERS.get(region, {})
        cpi_mult_table = REGIONAL_CPI_MULTIPLIERS.get(region, {})

        gdp_pct = 0.0
        cpi_pct = 0.0
        for commodity, shock in shocks.items():
            gdp_mult = gdp_mult_table.get(commodity, DEFAULT_REGIONAL_MULTIPLIER)
            cpi_mult = cpi_mult_table.get(commodity, DEFAULT_REGIONAL_MULTIPLIER)
            gdp_pct += _gdp_elasticity_for(commodity) * shock * gdp_mult
            cpi_pct += _cpi_elasticity_for(commodity) * shock * cpi_mult
        gdp_pct *= scaler
        cpi_pct *= min(1.2, max(0.5, scaler))

        consumption_pct = gdp_pct - 0.4 * cpi_pct
        welfare_pct = consumption_pct
        wage_pct = WAGE_PASSTHROUGH_TO_CPI * cpi_pct + 0.5 * gdp_pct
        interest_rate_pct = INTEREST_RATE_RESPONSE_TO_CPI * cpi_pct + 0.25 * gdp_pct

        rows.append({
            "region": region,
            "gdp_impact_pct": round(gdp_pct, 4),
            "cpi_inflation_pct": round(cpi_pct, 4),
            "consumption_impact_pct": round(consumption_pct, 4),
            "welfare_pct_change": round(welfare_pct, 4),
            "wage_impact_pct": round(wage_pct, 4),
            "interest_rate_impact_pct": round(interest_rate_pct, 4),
        })
    return rows


def derive_macro_from_energy_shocks(
    applied_shocks: dict[str, Any],
    duration_months: float | None = None,
    *,
    regime: Regime = "short_run",
) -> _OutputDict:
    """Translate energy-adapter operational shocks into macro outcomes.

    Each of TEMOA / OSeMOSYS / MESSAGEix consumes operational shocks
    (mb/d, bcfd, capacity-loss percent, capital-cost multiplier) rather
    than the price-shock vector PyCGE / OpenCGE / MIRAGRODEP receive.
    This helper reconstructs an equivalent ``commodity_shocks`` dict via
    constant-elasticity supply-loss formulas (mirroring
    ``src.models.oil.poles_jrc``) and forwards to
    ``compute_macro_outcomes``.

    Args:
        applied_shocks: The ``_applied_shocks`` dict the energy adapter
            attaches to its outputs after a successful run. Recognised
            keys (any subset is fine):
                - ``oil_supply_loss_mbd``
                - ``gas_supply_loss_bcfd``
                - ``lng_export_capacity_loss_pct``
                - ``capital_cost_multiplier``
                - ``co2_price_baseline_usd_per_t`` (ignored for macro)
                - ``oil_price_path_override_usd`` (used as direct price
                  shock when present, with baseline 80 USD/bbl)
                - ``duration_years`` or ``duration_months``
        duration_months: Override the duration drawn from
            ``applied_shocks``; useful when the caller already has the
            canonical pipeline value.
        regime: Forwarded to ``compute_macro_outcomes``.

    Returns:
        A dict with the standardised macro schema, augmented with
        ``_translation`` describing how each operational shock mapped
        to a price-shock-equivalent. Returns the same shape with
        zeroed values when ``applied_shocks`` is empty / None / all-
        zero, so callers can blindly merge without conditional branches.
    """
    if not isinstance(applied_shocks, dict):
        applied_shocks = {}

    # Resolve duration.
    if duration_months is None:
        if "duration_months" in applied_shocks:
            duration_months = float(applied_shocks["duration_months"])
        elif "duration_years" in applied_shocks:
            duration_months = float(applied_shocks["duration_years"]) * 12.0
        else:
            duration_months = 6.0  # conservative default

    commodity_shocks: dict[str, float] = {}
    translation: dict[str, dict[str, float]] = {}

    # Oil: prefer an explicit price path if provided; else compute
    # the equilibrium price impulse from the supply loss.
    oil_path = applied_shocks.get("oil_price_path_override_usd")
    if isinstance(oil_path, (list, tuple)) and oil_path:
        try:
            peak = max(float(x) for x in oil_path)
            oil_shock = (peak / 80.0 - 1.0) * 100.0
        except (TypeError, ValueError):
            oil_shock = 0.0
    else:
        oil_loss_mbd = float(applied_shocks.get("oil_supply_loss_mbd", 0.0) or 0.0)
        if oil_loss_mbd > 0:
            supply_pct_loss = (oil_loss_mbd / GLOBAL_OIL_SUPPLY_MBD) * 100.0
            # Constant-elasticity equilibrium: -DS/S = (eps_d - eps_s) * dP/P
            denom = ELASTICITY_DEMAND_OIL - ELASTICITY_SUPPLY_OIL
            oil_shock = -supply_pct_loss / denom if denom != 0 else 0.0
        else:
            oil_shock = 0.0
    if abs(oil_shock) > 1e-6:
        commodity_shocks["oil"] = oil_shock
        translation["oil"] = {"price_shock_pct": round(oil_shock, 4)}

    # Gas / LNG: combine supply loss + LNG-export capacity loss.
    gas_loss_bcfd = float(applied_shocks.get("gas_supply_loss_bcfd", 0.0) or 0.0)
    lng_loss_pct = float(applied_shocks.get("lng_export_capacity_loss_pct", 0.0) or 0.0)

    gas_shock = 0.0
    if gas_loss_bcfd > 0:
        supply_pct_loss = (gas_loss_bcfd / GLOBAL_GAS_SUPPLY_BCFD) * 100.0
        denom = ELASTICITY_DEMAND_GAS - ELASTICITY_SUPPLY_GAS
        gas_shock = -supply_pct_loss / denom if denom != 0 else 0.0
    # LNG export-capacity loss adds a regional netback impulse on top.
    if lng_loss_pct > 0:
        # ~0.6 elasticity of LNG netback to global LNG export capacity
        # (Energy Flux LNG profits sensitivity, AEO 2025).
        gas_shock += lng_loss_pct * 0.6
    if abs(gas_shock) > 1e-6:
        commodity_shocks["lng"] = gas_shock
        translation["lng"] = {"price_shock_pct": round(gas_shock, 4)}

    # Capital-cost multiplier -> CPI pass-through. Convert the
    # multiplier to a percent change above 1.0 and add a synthetic
    # "capex" commodity shock that uses the residual elasticity.
    capex_mult = float(applied_shocks.get("capital_cost_multiplier", 1.0) or 1.0)
    if abs(capex_mult - 1.0) > 1e-6:
        capex_shock = (capex_mult - 1.0) * 100.0 * CAPEX_TO_CPI_PASSTHROUGH
        commodity_shocks["capex"] = capex_shock
        translation["capex"] = {
            "capital_cost_multiplier": capex_mult,
            "price_shock_pct_equivalent": round(capex_shock, 4),
        }

    out = compute_macro_outcomes(
        commodity_shocks, duration_months, regime=regime
    )
    out["_translation"] = translation
    out["_source_kind"] = "energy_adapter_derived"
    return out


__all__ = [
    "compute_macro_outcomes",
    "compute_regional_macro_outcomes",
    "derive_macro_from_energy_shocks",
    "GDP_ELASTICITY_TO_OIL_PCT",
    "CPI_ELASTICITY_TO_OIL_PCT",
    "GLOBAL_OIL_SUPPLY_MBD",
    "GLOBAL_GAS_SUPPLY_BCFD",
    "REGIONAL_GDP_MULTIPLIERS",
    "REGIONAL_CPI_MULTIPLIERS",
    "UNIFIED_REGIONS",
]
