"""Download observed commodity prices and build the market calibration.

Sources (all public):

* World Bank Commodity Price Data ("Pink Sheet"), monthly, nominal USD.
  No key. The download link changes each month; the default below is the
  November 2026 release, override with ``--pink-sheet-url`` (the current
  link is on https://www.worldbank.org/en/research/commodity-markets).
* EIA Open Data v2, weekly spot prices (Brent, WTI, Henry Hub), averaged
  to months. Optional; needs ``EIA_API_KEY``. Skipped (and recorded as
  skipped) without a key.
* EIA AEO2025 reference-case Table 20 (Macroeconomic Indicators) for the
  MAM adapter, saved to ``data/eia/AEO2025_Table20_ref2025.xlsx``.

Outputs (``--out-dir``, default ``data/market``):

* ``monthly_prices.csv`` -- long format: month, series, value, unit, source.
* ``calibration.json`` -- pre-crisis baselines and AR(1) half-lives
  (``src/models/market_calibration.py :: build_calibration``).
* ``provenance.json`` -- URLs, retrieval time, SHA-256 of each download,
  per-source status.

Usage::

    python scripts/revision/fetch_market_data.py
    python scripts/revision/fetch_market_data.py --pink-sheet-file CMO-Historical-Data-Monthly.xlsx

Downloads go through ``urllib``; on machines whose Python lacks the
right CA bundle, download the files by hand and pass ``--pink-sheet-file``
/ ``--aeo-file``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.market_calibration import (  # noqa: E402
    PINK_SHEET_SERIES,
    UNITS,
    build_calibration,
)

PINK_SHEET_URL = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)
AEO_TABLE20_URL = "https://www.eia.gov/outlooks/archive/aeo25/excel/aeotab20.xlsx"
EIA_WEEKLY_SERIES = {
    "brent_eia": "PET.RBRTE.W",
    "wti_eia": "PET.RWTC.W",
    "henry_hub_eia": "NG.RNGWHHD.W",
}
USER_AGENT = "hormuz-pipeline-market-data/1.0"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())


def _norm_header(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("*", "")).strip().lower()


def parse_pink_sheet(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Return long-format rows for PINK_SHEET_SERIES and the 'Updated on' line."""
    from openpyxl import load_workbook

    wb = load_workbook(str(path), data_only=True, read_only=True)
    ws = wb["Monthly Prices"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()

    updated = next(
        (str(r[0]) for r in rows[:10] if r and isinstance(r[0], str) and r[0].lower().startswith("updated")),
        None,
    )
    header_idx = next(i for i, r in enumerate(rows[:20]) if any(_norm_header(c) == "crude oil, brent" for c in r))
    header = [_norm_header(c) for c in rows[header_idx]]
    wanted = {sid: _norm_header(h) for sid, h in PINK_SHEET_SERIES.items()}
    col_of = {}
    for sid, h in wanted.items():
        if h not in header:
            raise KeyError(f"Pink Sheet column {PINK_SHEET_SERIES[sid]!r} not found")
        col_of[sid] = header.index(h)

    out: list[dict[str, Any]] = []
    for r in rows[header_idx + 1:]:
        m = re.match(r"^(\d{4})M(\d{2})$", str(r[0] or "").strip())
        if not m:
            continue
        month = f"{m.group(1)}-{m.group(2)}"
        for sid, j in col_of.items():
            v = r[j] if j < len(r) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append({"month": month, "series": sid, "value": float(v),
                            "unit": UNITS.get(sid), "source": "world_bank_pink_sheet"})
    return out, updated


def fetch_eia_weekly(api_key: str) -> list[dict[str, Any]]:
    """Weekly EIA spot prices averaged to calendar months."""
    out: list[dict[str, Any]] = []
    for sid, series_id in EIA_WEEKLY_SERIES.items():
        url = f"https://api.eia.gov/v2/seriesid/{series_id}?api_key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        data = (payload.get("response") or {}).get("data") or []
        by_month: dict[str, list[float]] = {}
        for d in data:
            period, value = str(d.get("period", "")), d.get("value")
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            by_month.setdefault(period[:7], []).append(v)
        base = sid.replace("_eia", "")
        for month, vals in sorted(by_month.items()):
            out.append({"month": month, "series": sid, "value": sum(vals) / len(vals),
                        "unit": UNITS.get(base), "source": f"eia_{series_id}_weekly_mean"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-dir", default="data/market")
    ap.add_argument("--raw-dir", default=None, help="Where downloads are kept (default <out-dir>/raw)")
    ap.add_argument("--pink-sheet-url", default=PINK_SHEET_URL)
    ap.add_argument("--pink-sheet-file", default=None, help="Use a local Pink Sheet XLSX instead of downloading")
    ap.add_argument("--aeo-url", default=AEO_TABLE20_URL)
    ap.add_argument("--aeo-file", default=None, help="Use a local AEO Table 20 XLSX instead of downloading")
    ap.add_argument("--aeo-dest", default="data/eia/AEO2025_Table20_ref2025.xlsx")
    ap.add_argument("--skip-aeo", action="store_true")
    ap.add_argument("--skip-eia", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    raw_dir = Path(args.raw_dir) if args.raw_dir else out_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    prov: dict[str, Any] = {"retrieved_at": retrieved_at, "sources": {}}

    # --- World Bank Pink Sheet (required) ---
    if args.pink_sheet_file:
        pink = Path(args.pink_sheet_file)
        pink_url = None
    else:
        pink = raw_dir / "CMO-Historical-Data-Monthly.xlsx"
        pink_url = args.pink_sheet_url
        _download(pink_url, pink)
    rows, updated = parse_pink_sheet(pink)
    prov["sources"]["world_bank_pink_sheet"] = {
        "status": "ok", "url": pink_url, "file": str(pink), "sha256": _sha256(pink),
        "updated_line": updated, "series": PINK_SHEET_SERIES,
        "last_month": max(r["month"] for r in rows),
    }

    # --- EIA weekly (optional) ---
    key = os.environ.get("EIA_API_KEY")
    if args.skip_eia:
        prov["sources"]["eia_weekly"] = {"status": "skipped", "reason": "--skip-eia"}
    elif not key:
        prov["sources"]["eia_weekly"] = {"status": "skipped", "reason": "EIA_API_KEY not set"}
    else:
        try:
            eia_rows = fetch_eia_weekly(key)
            rows.extend(eia_rows)
            prov["sources"]["eia_weekly"] = {"status": "ok", "series": EIA_WEEKLY_SERIES,
                                             "n_rows": len(eia_rows)}
        except Exception as exc:  # noqa: BLE001 - recorded, not fatal
            prov["sources"]["eia_weekly"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    # --- AEO2025 Table 20 for MAM ---
    if args.skip_aeo:
        prov["sources"]["aeo2025_table20"] = {"status": "skipped", "reason": "--skip-aeo"}
    else:
        dest = Path(args.aeo_dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if args.aeo_file:
            dest.write_bytes(Path(args.aeo_file).read_bytes())
            aeo_url = None
        else:
            aeo_url = args.aeo_url
            _download(aeo_url, dest)
        prov["sources"]["aeo2025_table20"] = {"status": "ok", "url": aeo_url, "file": str(dest),
                                              "sha256": _sha256(dest)}

    # --- write prices ---
    prices_csv = out_dir / "monthly_prices.csv"
    with open(prices_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["month", "series", "value", "unit", "source"])
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["series"], r["month"])):
            w.writerow(r)

    # --- calibration (World Bank series only, so it is reproducible without a key) ---
    wb_prices: dict[str, list[tuple[str, float]]] = {}
    for r in rows:
        if r["source"] == "world_bank_pink_sheet":
            wb_prices.setdefault(r["series"], []).append((r["month"], r["value"]))
    for s in wb_prices:
        wb_prices[s].sort()
    cal = build_calibration(
        wb_prices, retrieved_at=retrieved_at,
        source=f"World Bank Pink Sheet ({updated or 'monthly'})",
    )
    (out_dir / "calibration.json").write_text(json.dumps(cal, indent=2), encoding="utf-8")
    prov["outputs"] = {"monthly_prices_csv": str(prices_csv), "sha256": _sha256(prices_csv),
                       "calibration_json": str(out_dir / "calibration.json")}
    (out_dir / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")

    print(f"wrote {prices_csv} ({len(rows)} rows), {out_dir / 'calibration.json'}")
    print("pre-crisis baselines:", {k: v["value"] for k, v in cal["baselines"].items()})
    print("half-lives (months):", {k: v["half_life_months"] for k, v in cal["half_lives"].items()})
    for name, s in prov["sources"].items():
        print(f"  {name}: {s['status']}" + (f" ({s.get('reason') or s.get('error')})" if s["status"] != "ok" else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
