"""Observed commodity-market data for calibrating the closed-form adapters.

The analytical-reduction adapters (POLES-JRC, LNGST, World Fertilizer,
futures, Energy Flux LNG Profits' schedule start) ship with hardcoded
baseline prices and decay half-lives taken from the literature. This
module replaces those constants with values computed from observed
monthly prices when market calibration is switched on.

Data flow
---------
1. ``scripts/revision/fetch_market_data.py`` downloads the World Bank
   Commodity Price Data ("Pink Sheet", monthly, public) and, if an
   ``EIA_API_KEY`` is set, EIA weekly spot series. It writes
   ``data/market/monthly_prices.csv`` (long format) and
   ``data/market/provenance.json``.
2. The same script calls :func:`build_calibration` and writes the frozen,
   reviewable ``data/market/calibration.json``: pre-crisis baselines and
   AR(1) half-lives with standard errors.
3. Adapters call :func:`active_calibration`. It returns ``None`` unless
   calibration is enabled, so default runs are bit-identical to before.

Enabling
--------
``HORMUZ_MARKET_CALIBRATION=1`` (environment, wins) or
``market_calibration.enabled: true`` in ``configs/model_configs/default.yaml``.
When enabled and the calibration file is missing, adapters raise: a run
that asked for market calibration must not silently fall back to the
literature constants.

Pure standard library (csv, json, math), so it runs in every adapter
environment.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PRICES_CSV = Path("data/market/monthly_prices.csv")
DEFAULT_CALIBRATION_JSON = Path("data/market/calibration.json")
DEFAULT_CONFIG_YAML = Path("configs/model_configs/default.yaml")

# Pipeline series id -> World Bank Pink Sheet "Monthly Prices" column header.
PINK_SHEET_SERIES: dict[str, str] = {
    "brent": "Crude oil, Brent",
    "dubai": "Crude oil, Dubai",
    "wti": "Crude oil, WTI",
    "henry_hub": "Natural gas, US",
    "ttf": "Natural gas, Europe",
    "lng_japan": "Liquefied natural gas, Japan",
    "urea": "Urea",
    "dap": "DAP",
    "potash": "Potassium chloride",
    "phosphate_rock": "Phosphate rock",
    "wheat": "Wheat, US HRW",
    "maize": "Maize",
    "soybeans": "Soybeans",
    "rice": "Rice, Thai 5%",
}

UNITS: dict[str, str] = {
    "brent": "USD/bbl", "dubai": "USD/bbl", "wti": "USD/bbl",
    "henry_hub": "USD/MMBtu", "ttf": "USD/MMBtu", "lng_japan": "USD/MMBtu",
    "urea": "USD/mt", "dap": "USD/mt", "potash": "USD/mt", "phosphate_rock": "USD/mt",
    "wheat": "USD/mt", "maize": "USD/mt", "soybeans": "USD/mt", "rice": "USD/mt",
}

# Windows. The crisis began in February 2026 (configs/crisis_descriptions/
# hormuz_2026.yaml), so the pre-crisis baseline is the three full months
# before it, and half-lives are estimated on data that ends before it.
PRE_CRISIS_WINDOW = ("2025-11", "2026-01")
HALF_LIFE_WINDOW = ("2000-01", "2025-12")
HALF_LIFE_MA_MONTHS = 36

# Which estimated half-life feeds which adapter commodity key.
FUTURES_HALF_LIFE_SERIES: dict[str, str] = {
    "wheat": "wheat", "maize": "maize", "corn": "maize", "soybeans": "soybeans",
    "rice": "rice", "urea": "urea", "dap": "dap", "potash": "potash",
    "ammonia": "urea", "natural_gas": "henry_hub",
}


@dataclass(frozen=True)
class MarketCalibration:
    """Frozen calibration read from ``calibration.json``."""

    baselines: dict[str, float]
    half_lives_months: dict[str, float]
    half_life_se_months: dict[str, float | None]
    retrieved_at: str
    source: str
    path: str
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def tag(self) -> str:
        """Short provenance label recorded in adapter outputs."""
        return f"market_data@{self.retrieved_at[:10]}"

    def baseline(self, series: str, default: float) -> float:
        v = self.baselines.get(series)
        return float(v) if v is not None else float(default)

    def half_life(self, series: str, default: float) -> float:
        v = self.half_lives_months.get(series)
        return float(v) if v is not None and v > 0 else float(default)

    def provenance(self, used: dict[str, Any]) -> dict[str, Any]:
        """Block adapters attach as ``_calibration`` in their outputs."""
        return {
            "source": self.tag,
            "data": self.source,
            "calibration_file": self.path,
            "pre_crisis_window": self.raw.get("pre_crisis_window"),
            "half_life_window": self.raw.get("half_life_window"),
            "values_used": used,
        }


# ---------------------------------------------------------------------------
# Enabling
# ---------------------------------------------------------------------------

def _yaml_settings(config_yaml: Path = DEFAULT_CONFIG_YAML) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return {}
    try:
        raw = yaml.safe_load(Path(config_yaml).read_text(encoding="utf-8")) or {}
    except OSError:
        return {}
    return raw.get("market_calibration") or {}


def calibration_enabled() -> bool:
    env = os.environ.get("HORMUZ_MARKET_CALIBRATION")
    if env is not None and env.strip() != "":
        return env.strip().lower() in ("1", "true", "yes", "on")
    return bool(_yaml_settings().get("enabled", False))


def half_lives_enabled() -> bool:
    """Whether estimated half-lives replace the literature decay rates.

    Separate from the baseline switch because the two measure different
    things: the AR(1) estimate is the average persistence of deviations
    from a 3-year trend (2000-2025), while the adapters' literature values
    describe how fast a crisis spike decays.
    """
    env = os.environ.get("HORMUZ_MARKET_CALIBRATION_HALF_LIVES")
    if env is not None and env.strip() != "":
        return env.strip().lower() in ("1", "true", "yes", "on")
    return bool(_yaml_settings().get("apply_half_lives", False))


def calibration_path() -> Path:
    env = os.environ.get("HORMUZ_MARKET_CALIBRATION_FILE")
    if env:
        return Path(env)
    return Path(_yaml_settings().get("calibration_file") or DEFAULT_CALIBRATION_JSON)


@lru_cache(maxsize=4)
def _load(path_str: str) -> MarketCalibration:
    raw = json.loads(Path(path_str).read_text(encoding="utf-8"))
    hl = raw.get("half_lives") or {}
    return MarketCalibration(
        baselines={k: float(v["value"]) for k, v in (raw.get("baselines") or {}).items()
                   if v.get("value") is not None},
        half_lives_months={k: float(v["half_life_months"]) for k, v in hl.items()
                           if v.get("half_life_months") is not None},
        half_life_se_months={k: v.get("half_life_se_months") for k, v in hl.items()},
        retrieved_at=str(raw.get("retrieved_at", "")),
        source=str(raw.get("source", "")),
        path=path_str,
        raw=raw,
    )


def active_calibration() -> MarketCalibration | None:
    """The calibration to apply, or ``None`` when calibration is off."""
    if not calibration_enabled():
        return None
    path = calibration_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Market calibration is enabled but {path} does not exist. Run "
            "`python scripts/revision/fetch_market_data.py` or unset "
            "HORMUZ_MARKET_CALIBRATION."
        )
    cal = _load(str(path))
    if not half_lives_enabled():
        from dataclasses import replace

        cal = replace(cal, half_lives_months={}, half_life_se_months={})
    return cal


def clear_cache() -> None:
    _load.cache_clear()


# ---------------------------------------------------------------------------
# Price data and estimation
# ---------------------------------------------------------------------------

def load_monthly_prices(path: Path | str = DEFAULT_PRICES_CSV) -> dict[str, list[tuple[str, float]]]:
    """Read the long-format CSV into ``{series: [(YYYY-MM, value), ...]}`` sorted by month."""
    out: dict[str, list[tuple[str, float]]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                v = float(row["value"])
            except (TypeError, ValueError):
                continue
            out.setdefault(row["series"], []).append((row["month"], v))
    for s in out:
        out[s].sort()
    return out


def _window(points: list[tuple[str, float]], start: str, end: str) -> list[tuple[str, float]]:
    return [(m, v) for m, v in points if start <= m <= end]


def window_mean(points: list[tuple[str, float]], start: str, end: str) -> float | None:
    vals = [v for _, v in _window(points, start, end)]
    return sum(vals) / len(vals) if vals else None


def window_median(points: list[tuple[str, float]], start: str, end: str) -> float | None:
    """Median of monthly values in the window.

    Used for pre-crisis baselines: one weather month can dominate a
    three-month mean (Henry Hub averaged 7.6 USD/MMBtu in January 2026
    against about 4 in November and December).
    """
    vals = sorted(v for _, v in _window(points, start, end))
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def estimate_ar1_half_life(
    points: list[tuple[str, float]],
    start: str = HALF_LIFE_WINDOW[0],
    end: str = HALF_LIFE_WINDOW[1],
    ma_months: int = HALF_LIFE_MA_MONTHS,
) -> dict[str, Any]:
    """Half-life of price shocks from an AR(1) on log deviations from a moving average.

    ``d_t = ln P_t - mean(ln P_{t-ma..t-1})`` (trailing mean, so the trend
    proxy uses only past data); OLS without intercept
    ``d_t = rho * d_{t-1} + e_t``; ``half_life = ln 0.5 / ln rho`` months,
    with a delta-method standard error. Returns ``half_life_months=None``
    when ``rho`` is not in (0, 1).
    """
    series = [(m, v) for m, v in points if v > 0 and m <= end]
    logs = [math.log(v) for _, v in series]
    months = [m for m, _ in series]
    dev: list[tuple[str, float]] = []
    for i in range(ma_months, len(logs)):
        if months[i] < start:
            continue
        ma = sum(logs[i - ma_months:i]) / ma_months
        dev.append((months[i], logs[i] - ma))
    x = [d for _, d in dev[:-1]]
    y = [d for _, d in dev[1:]]
    n = len(x)
    result: dict[str, Any] = {
        "method": f"OLS AR(1), no intercept, on ln(P) minus trailing {ma_months}-month mean of ln(P)",
        "start": dev[0][0] if dev else None,
        "end": dev[-1][0] if dev else None,
        "n": n,
        "rho": None, "rho_se": None, "half_life_months": None, "half_life_se_months": None,
    }
    sxx = sum(a * a for a in x)
    if n < 24 or sxx == 0:
        return result
    rho = sum(a * b for a, b in zip(x, y)) / sxx
    resid = [b - rho * a for a, b in zip(x, y)]
    sigma2 = sum(r * r for r in resid) / (n - 1)
    rho_se = math.sqrt(sigma2 / sxx)
    result.update(rho=round(rho, 6), rho_se=round(rho_se, 6))
    if 0.0 < rho < 1.0:
        hl = math.log(0.5) / math.log(rho)
        dhl = -math.log(0.5) / (rho * math.log(rho) ** 2)
        result.update(half_life_months=round(hl, 4), half_life_se_months=round(abs(dhl) * rho_se, 4))
    return result


def build_calibration(
    prices: dict[str, list[tuple[str, float]]],
    *,
    retrieved_at: str,
    source: str,
    pre_crisis_window: tuple[str, str] = PRE_CRISIS_WINDOW,
    half_life_window: tuple[str, str] = HALF_LIFE_WINDOW,
) -> dict[str, Any]:
    """Compute the frozen calibration document written to ``calibration.json``."""
    baselines: dict[str, Any] = {}
    half_lives: dict[str, Any] = {}
    for s, pts in sorted(prices.items()):
        med = window_median(pts, *pre_crisis_window)
        mean = window_mean(pts, *pre_crisis_window)
        baselines[s] = {
            "value": round(med, 4) if med is not None else None,
            "statistic": "median of monthly averages",
            "mean": round(mean, 4) if mean is not None else None,
            "unit": UNITS.get(s),
            "months": [m for m, _ in _window(pts, *pre_crisis_window)],
        }
        half_lives[s] = estimate_ar1_half_life(pts, *half_life_window)
    return {
        "retrieved_at": retrieved_at,
        "source": source,
        "pre_crisis_window": list(pre_crisis_window),
        "half_life_window": list(half_life_window),
        "baselines": baselines,
        "half_lives": half_lives,
        "notes": [
            "Baselines are medians of the monthly averages over the pre-crisis window "
            "(robust to one weather month, e.g. Henry Hub in January 2026); the mean is kept for reference.",
            "JKM spot is not public; 'lng_japan' (World Bank, Japan LNG import price) is "
            "used as the JKM proxy and is a contract-weighted price, slower to move than spot.",
        ],
    }
