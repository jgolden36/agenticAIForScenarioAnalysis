"""observed_vs_scenario.py reads each run's own hub baselines.

Stage 5 flattens dict outputs to ``key.sub``. The script looked only for a
nested dict, so under market calibration it measured LNGST's hub levels
against the literature constants (Henry Hub 3.0, TTF 11.0, JKM 13.0) instead
of the run's observed baselines (4.25, 10.42, 11.32): Henry Hub showed
+145% where the run's own change was +73% (supp_full_mkt_20260504_222710).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.revision.observed_vs_scenario import build_rows  # noqa: E402


def test_flattened_calibrated_baseline_is_used():
    sid = "prolonged_contained"
    run = {
        (sid, "lngst", "henry_hub_price"): 7.349,
        (sid, "lngst", "hub_baseline_prices.henry_hub"): 4.25,
        (sid, "lngst", "ttf_price"): 23.59,
        (sid, "lngst", "hub_baseline_prices.ttf"): 10.42,
    }
    rows = build_rows({"supp": run}, prices={})
    by = {r["series"]: r for r in rows}
    assert by["henry_hub"]["model_pct"] == 72.9
    assert by["ttf"]["model_pct"] == 126.4


def test_literature_constant_is_the_fallback():
    sid = "prolonged_contained"
    rows = build_rows({"may": {(sid, "lngst", "ttf_price"): 24.903}}, prices={})
    assert rows[0]["model_pct"] == 126.4  # 24.903 / 11.0
