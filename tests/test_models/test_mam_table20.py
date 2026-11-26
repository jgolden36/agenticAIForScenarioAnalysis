"""MAM ingests AEO Table 20 and rejects the wrong table or edition.

The fixtures reproduce the layout of the real AEO2025 workbook
(https://www.eia.gov/outlooks/archive/aeo25/excel/aeotab20.xlsx): series
key in column A, label in column B, one column per year, then a compound
growth column. Before November 2026 the cluster ingested AEO2021 Table 19
(CO2 emissions) and MAM "completed" with no macro data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from src.models.macro.mam import MAMAdapter, MAMConfig  # noqa: E402

YEARS = [2024, 2025, 2026, 2027, 2028, 2029]


def _workbook(path: Path, *, table: str = "20. Macroeconomic Indicators",
              report: str = "Annual Energy Outlook 2025") -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ref2025.d032025a"
    ws.append([None, "ref2025.d032025a"])
    ws.append([])
    ws.append([None, None, "Report", report])
    ws.append([None, None, "Scenario", "ref2025"])
    ws.append([None, None, "Datekey", "d032025a"])
    ws.append([None, table])
    ws.append([None, "(billion 2012 chain-weighted dollars, unless otherwise noted)"])
    ws.append([])
    ws.append([None, " Indicators", *YEARS, "2024-2050"])
    ws.append([])
    ws.append(["MEI000:ba_RealGrossDome", "Real Gross Domestic Product", 100.0, 102.0, 104.04, 106.0, 108.0, 110.0, 0.0176])
    ws.append([None, "Components of Real Gross Domestic Product"])
    ws.append(["MEI000:ba_RealConsumpti", "  Real Consumption", 70.0, 71.0, 72.42, 73.0, 74.0, 75.0, 0.02])
    ws.append([None, "  Consumer Price Index (1982-84=1.00)"])
    ws.append(["MEI000:da_ConsumerPrice", "    All-urban", 3.0, 3.1, 3.162, 3.2, 3.3, 3.4, 0.02])
    ws.append(["MEI000:ea_FederalFundsR", "  Federal Funds Rate", 5.1, 3.8, 3.1, 2.9, 2.7, 2.6, -0.02])
    ws.append(["MEI000:fa_UnemploymentR", "  Unemployment Rate (percentage)", 4.0, 4.3, 4.5, 4.4, 4.3, 4.3, 0.002])
    ws.append(["MEI000:ka_Populationwit", "  Population, with Armed Forces Overseas", 342.0, 344.8, 347.0, 349.0, 351.0, 353.0, 0.003])
    wb.save(path)
    return path


def _run(path: Path, **cfg):
    a = MAMAdapter(MAMConfig(aeo_macro_xlsx_path=path, **cfg))
    return a.execute(a.translate_inputs({"scenario_id": "swift_contained", "oil_price_path": [120.0, 80.0]}))


def test_table20_is_parsed_by_year_column(tmp_path):
    out = _run(_workbook(tmp_path / "t20.xlsx")).outputs
    assert out["_years"] == YEARS
    # The compound-growth column must not enter the path.
    assert out["real_gdp_bn_2012usd"] == [100.0, 102.0, 104.04, 106.0, 108.0, 110.0]
    assert out["real_gdp_bn_2012usd_by_year"]["2026"] == 104.04
    assert out["real_gdp_bn_usd"] == 104.04
    assert out["gdp_growth_pct"] == pytest.approx(2.0, abs=1e-6)
    assert out["cpi_inflation_pct"] == pytest.approx(2.0, abs=1e-6)
    assert out["unemployment_rate_pct"] == 4.5
    assert out["federal_funds_rate_pct"] == 3.1
    assert out["_aeo_report"] == "Annual Energy Outlook 2025"


def test_shocks_are_recorded_as_ignored(tmp_path):
    out = _run(_workbook(tmp_path / "t20.xlsx")).outputs
    assert out["_baseline_only"] is True
    assert out["_ignored_shock_inputs"] == ["oil_price_path"]
    assert "oil_price_path" not in out


def test_reference_year_is_configurable(tmp_path):
    out = _run(_workbook(tmp_path / "t20.xlsx"), reference_year=2025).outputs
    assert out["real_gdp_bn_usd"] == 102.0


def test_wrong_table_is_rejected(tmp_path):
    p = _workbook(tmp_path / "t19.xlsx", table="19. Energy-Related Carbon Dioxide Emissions by End Use")
    with pytest.raises(ValueError, match="not AEO Table 20"):
        _run(p)


def test_wrong_edition_is_rejected(tmp_path):
    p = _workbook(tmp_path / "t20_2021.xlsx", report="Annual Energy Outlook 2021")
    with pytest.raises(ValueError, match="Annual Energy Outlook 2021"):
        _run(p)
