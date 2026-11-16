"""Poster figures for USAEE: Agentic AI for chokepoint-crisis analysis (Strait of Hormuz, 2026).

Every number drawn comes from a file in this repository:
  - May main run 20260504_222710 (basis of the manuscript): data/20260504_222710/csv/
  - Revision evidence: docs/revision/REVIEWER_RESPONSE_RESULTS.md and
    docs/revision/runs/20260504_222710_filled/scenario_e_input_replay.json
  - Observed prices: data/market/monthly_prices.csv (World Bank Pink Sheet)
  - Forwarding rules: configs/upstream_forwarding_mapping.yaml
  - Model inventory: docs/revision/model_inventory.json
  - Basemaps: data/geo/*.geojson (Natural Earth, trimmed by scripts/poster/prep_geo.py)
Context facts on the map (20 mb/d, ~20% of liquids use, ~1/5 of LNG trade) are EIA, 2024.

Usage:  python scripts/poster/make_poster_figures.py [--only fig01 fig05 ...]
Output: docs/poster_usaee/<name>.png (300 dpi) and .pdf (vector)
"""
from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle, Circle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "data" / "20260504_222710"
OUT = ROOT / "docs" / "poster_usaee"

# ---------------------------------------------------------------- style tokens
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
NAVY, NAVY_MID, BLUE_LIGHT, BLUE_250 = "#104281", "#256abf", "#cde2fb", "#86b6ef"
CRITICAL = "#d03b3b"

SCEN = ["swift_contained", "prolonged_contained", "swift_escalated",
        "prolonged_escalated", "infrastructure_collapse"]
LETTER = dict(zip(SCEN, "ABCDE"))
NAME = {
    "swift_contained": "Swift resolution, contained conflict",
    "prolonged_contained": "Prolonged closure, contained conflict",
    "swift_escalated": "Swift resolution, escalated conflict",
    "prolonged_escalated": "Prolonged closure, escalated conflict",
    "infrastructure_collapse": "Infrastructure collapse (tail risk)",
}
SHORT = {
    "swift_contained": "Swift · contained",
    "prolonged_contained": "Prolonged · contained",
    "swift_escalated": "Swift · escalated",
    "prolonged_escalated": "Prolonged · escalated",
    "infrastructure_collapse": "Infrastructure collapse",
}
# Reference categorical palette, slots 1-5 in validated order (adjacent pairs pass CVD + normal-vision
# floors on the light surface). Magenta / yellow / aqua sit below 3:1 contrast on white, so every
# scenario mark here also carries a direct letter label (relief rule).
COLOR = dict(zip(SCEN, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
# Darker text-safe companions for labels drawn in scenario colour beside marks are NOT used:
# text stays in ink tokens; colour sits on the mark.

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 15,
    "axes.titlesize": 18,
    "axes.labelsize": 15,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "axes.linewidth": 1.0,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
})

DAGGER = "†"
DDAGGER = "‡"


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.25)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", name)


def header(fig, title, subtitle=None, x=0.015, y=0.985):
    fig.text(x, y, title, fontsize=24, fontweight="bold", color=INK, va="top", ha="left")
    if subtitle:
        fig.text(x, y - 0.055, subtitle, fontsize=15, color=INK2, va="top", ha="left")


def footnote(fig, text, y=0.005):
    fig.text(0.015, y, text, fontsize=11, color=MUTED, va="bottom", ha="left", wrap=True)


# ---------------------------------------------------------------- data access
_Q = None


def q():
    global _Q
    if _Q is None:
        _Q = pd.read_csv(RUN / "csv" / "quantitative_results.csv")
    return _Q


def val(model, key, scen):
    d = q()
    r = d[(d.model_id == model) & (d.output_key == key) & (d.scenario_id == scen)]
    if r.empty:
        raise KeyError((model, key, scen))
    return float(r.value_numeric.iloc[0])


def raw(scen, fname):
    return pd.read_csv(RUN / "csv" / "raw" / scen / fname)


# ---------------------------------------------------------------- geo helpers
def load_geo(name):
    return json.load(open(ROOT / "data" / "geo" / name, encoding="utf-8"))["features"]


def poly_path(polys, proj=None):
    verts, codes = [], []
    for poly in polys:
        for ring in poly:
            pts = np.asarray(ring, dtype=float)
            if proj is not None:
                pts = np.column_stack(proj(pts[:, 0], pts[:, 1]))
            verts.extend(pts.tolist())
            codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 2) + [MPath.CLOSEPOLY])
    return MPath(verts, codes)


def equal_earth(lon, lat):
    A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
    M = math.sqrt(3) / 2
    lam = np.radians(lon)
    th = np.arcsin(M * np.sin(np.radians(lat)))
    x = 2 * math.sqrt(3) * lam * np.cos(th) / (3 * (9 * A4 * th**8 + 7 * A3 * th**6 + 3 * A2 * th**2 + A1))
    y = A4 * th**9 + A3 * th**7 + A2 * th**3 + A1 * th
    return x, y


EU27 = set("AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE".split())
GCC = set("SAU ARE QAT KWT BHR OMN".split())


def kernel_region(props):
    a3 = props.get("ADM0_A3")
    wb = props.get("REGION_WB") or ""
    if a3 == "USA":
        return "US"
    if a3 == "CHN":
        return "CHN"
    if a3 == "IND":
        return "IND"
    if a3 in EU27:
        return "EU"
    if a3 in GCC:
        return "MENA_GCC"
    if wb == "Middle East & North Africa":
        return "MENA_OTHER"
    if wb == "Sub-Saharan Africa":
        return "SSA"
    if wb == "Latin America & Caribbean":
        return "LAC"
    return "ROW"


# ============================================================== FIG 01 · hero map
def fig01_map():
    fig = plt.figure(figsize=(14.5, 11.6))
    ax = fig.add_axes([0.01, 0.05, 0.98, 0.84])
    sea = "#e3edf7"
    ax.set_facecolor(sea)
    lon0, lon1, lat0, lat1 = 34.2, 62.5, 11.0, 32.6
    patches = [PathPatch(poly_path(f["geometry"]["coordinates"])) for f in load_geo("gulf_10m.geojson")]
    ax.add_collection(PatchCollection(patches, facecolor="#f2f0eb", edgecolor="#b9b5aa", linewidth=0.6, zorder=1))
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect(1 / math.cos(math.radians(22)))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True); s.set_color(AXIS)

    # country & sea labels
    for txt, x, y in [("IRAN", 54.2, 30.3), ("IRAQ", 44.2, 31.6), ("SAUDI ARABIA", 44.8, 22.4), ("KUWAIT", 47.1, 29.75),
                      ("UAE", 53.1, 23.2), ("OMAN", 56.6, 20.6), ("YEMEN", 47.5, 15.6),
                      ("SUDAN", 35.6, 17.5), ("JORDAN", 36.9, 30.9), ("ERITREA", 38.1, 15.3)]:
        ax.text(x, y, txt, fontsize=12, color="#8a857a", ha="center", va="center", fontweight="bold", zorder=3)
    for txt, x, y, rot in [("Persian Gulf", 50.75, 27.05, -36), ("Gulf of Oman", 60.0, 24.2, -36),
                           ("Arabian Sea", 60.0, 17.5, 0), ("Red Sea", 38.9, 20.0, -58)]:
        ax.text(x, y, txt, fontsize=14, color="#4f7fae", style="italic", ha="center", va="center", rotation=rot, zorder=3)

    # tanker lane through the strait (hugs the Iranian side so the sea labels stay clear)
    lane = np.array([(49.9, 29.15), (51.2, 28.05), (52.6, 27.05), (54.5, 26.6), (55.6, 26.5), (56.45, 26.55),
                     (57.2, 25.75), (58.6, 24.3), (60.5, 22.6), (62.5, 21.4)])
    ax.plot(lane[:, 0], lane[:, 1], color=CRITICAL, lw=9, alpha=0.18, solid_capstyle="round", zorder=4)
    ax.plot(lane[:, 0], lane[:, 1], color=CRITICAL, lw=1.6, ls=(0, (6, 4)), alpha=0.8, zorder=4)

    # bypass pipelines
    ew = np.array([(49.67, 25.94), (47.2, 25.2), (44.0, 24.7), (41.0, 24.3), (38.06, 24.09)])
    ad = np.array([(53.6, 23.85), (54.9, 24.3), (55.9, 24.8), (56.36, 25.12)])
    for line in (ew, ad):
        ax.plot(line[:, 0], line[:, 1], color=NAVY, lw=3.0, zorder=5, solid_capstyle="round")
        ax.annotate("", xy=line[-1], xytext=line[-2], arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=3, mutation_scale=22), zorder=5)
    ax.text(43.6, 25.15, "East–West pipeline (bypass to Yanbu)", fontsize=12.5, color=NAVY, ha="center", va="bottom",
            rotation=2, zorder=6, fontweight="semibold")
    ax.text(55.25, 23.95, "Habshan–Fujairah\nbypass", fontsize=12, color=NAVY, ha="left", va="top", zorder=6,
            fontweight="semibold", linespacing=1.0)

    oil = [("Ras Tanura", 50.16, 26.64, (-0.3, -0.2), "right"), ("Kharg Is.", 50.32, 29.23, (0.3, 0.15), "left"),
           ("Basrah", 48.8, 29.68, (0.25, 0.25), "left"), ("Mina al-Ahmadi", 48.15, 29.07, (-0.3, -0.05), "right"),
           ("Ruwais", 52.6, 24.19, (-0.15, -0.45), "center"), ("Fujairah", 56.36, 25.12, (0.3, -0.05), "left"),
           ("Yanbu", 38.06, 24.09, (-0.3, 0.0), "right")]
    lng = [("Ras Laffan", 51.55, 25.92, (0.3, 0.3), "left"), ("Das Is.", 52.87, 25.15, (0.0, 0.4), "center")]
    desal = [("Ras Al-Khair", 49.25, 27.48, (-0.3, 0.15), "right"), ("Jubail", 49.62, 27.0, (-0.3, 0.05), "right"),
             ("Ras Abu Fontas", 51.62, 25.2, (0.3, -0.35), "left"), ("Taweelah", 54.69, 24.77, (0.0, -0.42), "center")]
    OILC, LNGC, DESC = INK, "#eb6834", "#2a78d6"
    for items, marker, c, size in [(oil, "o", OILC, 120), (lng, "s", LNGC, 130), (desal, "D", DESC, 110)]:
        for name, x, y, (dx, dy), ha in items:
            ax.scatter([x], [y], s=size, marker=marker, color=c, edgecolor="white", linewidth=1.8, zorder=8)
            ax.text(x + dx, y + dy, name, fontsize=11.5, color=INK, ha=ha, va="center", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.12", fc=(1, 1, 1, 0.65), ec="none"))

    # chokepoints
    for x, y, s in [(56.45, 26.55, 900), (43.35, 12.62, 520)]:
        ax.scatter([x], [y], s=s * 2.2, marker="o", color=CRITICAL, alpha=0.15, zorder=9, linewidth=0)
        ax.scatter([x], [y], s=s, marker="X", color=CRITICAL, edgecolor="white", linewidth=2, zorder=10)
    ax.annotate("Bab el-Mandeb\nat risk in escalated scenarios", xy=(43.35, 12.62), xytext=(46.2, 13.25),
                fontsize=12.5, color=INK, va="center", ha="left", zorder=11,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=1.2))

    # callout for Hormuz
    cx, cy = 55.7, 32.15
    ax.annotate("", xy=(56.55, 26.85), xytext=(58.4, 28.55),
                arrowprops=dict(arrowstyle="-", color=INK, lw=1.6), zorder=11)
    ax.text(cx, cy, "STRAIT OF HORMUZ", fontsize=17, fontweight="bold", color=CRITICAL, ha="left", va="top", zorder=12)
    ax.text(cx, cy - 0.68, "closed February 2026", fontsize=14, color=INK, ha="left", va="top", zorder=12)
    ax.text(cx, cy - 1.4, "20 mb/d of oil, about 20%\nof world liquids use\nabout 1/5 of global LNG trade",
            fontsize=13, color=INK2, ha="left", va="top", zorder=12, linespacing=1.2)
    ax.add_patch(FancyBboxPatch((cx - 0.3, cy - 3.55), 6.55, 3.8, boxstyle="round,pad=0,rounding_size=0.25",
                                fc="white", ec=AXIS, lw=1.2, zorder=11, alpha=0.96))

    handles = [
        Line2D([], [], marker="o", ls="", color=OILC, mec="white", ms=12, label="Oil export terminal"),
        Line2D([], [], marker="s", ls="", color=LNGC, mec="white", ms=12, label="LNG export terminal"),
        Line2D([], [], marker="D", ls="", color=DESC, mec="white", ms=11, label="Desalination plant"),
        Line2D([], [], marker="X", ls="", color=CRITICAL, mec="white", ms=15, label="Chokepoint"),
        Line2D([], [], color=CRITICAL, lw=2, ls=(0, (6, 4)), label="Tanker lane through Hormuz"),
        Line2D([], [], color=NAVY, lw=3, label="Bypass pipeline"),
    ]
    leg = ax.legend(handles=handles, loc="lower right", frameon=True, fontsize=13, borderpad=0.9, labelspacing=0.7,
                    bbox_to_anchor=(0.995, 0.01))
    leg.get_frame().set_edgecolor(AXIS)

    header(fig, "One strait, five commodity systems",
           "Oil, LNG, helium, fertilizer feedstock and Gulf drinking water all depend on Hormuz staying open")
    footnote(fig, "Flows: U.S. EIA, Today in Energy (2024 data). Basemap: Natural Earth. Facility and pipeline positions approximate.")
    save(fig, "fig01_hormuz_map")


# ============================================================== FIG 02 · scenario matrix
SCEN_BLURB = {
    "swift_contained": "Naval escort and ceasefire reopen the strait in 4–6 weeks. Sharp, transient price spike.",
    "prolonged_contained": "Iran holds the closure 3–6+ months as a bargaining chip. Structural adjustment costs.",
    "swift_escalated": "Strait reopens quickly, but strikes spread to desalination, Gulf states and Bab el-Mandeb.",
    "prolonged_escalated": "Sustained closure plus regional war and infrastructure damage.",
    "infrastructure_collapse": "Combat destroys desalination, Ras Laffan LNG and Saudi/UAE terminals; throughput capped "
                               "at 50–60% through year 2.",
}


def fig02_matrix():
    fig = plt.figure(figsize=(17, 10.5))
    header(fig, "Five structurally distinct futures, not perturbations of one baseline",
           "2 × 2 Schwartz matrix on closure duration and conflict scope, plus a prescribed tail-risk scenario")
    ax = fig.add_axes([0.0, 0.07, 1.0, 0.79])
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")

    pos = {"swift_contained": (8, 30), "prolonged_contained": (37, 30),
           "swift_escalated": (8, 1.5), "prolonged_escalated": (37, 1.5), "infrastructure_collapse": (70, 15.75)}
    W, H = 28, 27
    for s in SCEN:
        x, y = pos[s]
        dashed = s == "infrastructure_collapse"
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0,rounding_size=1.2", fc="white",
                                    ec=INK2 if dashed else AXIS, lw=1.6, ls=(0, (5, 3)) if dashed else "-"))
        ax.add_patch(Rectangle((x, y + H - 1.3), W, 1.3, color=COLOR[s], lw=0))
        ax.add_patch(Circle((x + 3.2, y + H - 4.6), 2.2, color=COLOR[s], zorder=3))
        ax.text(x + 3.2, y + H - 4.65, LETTER[s], color=INK if s == "prolonged_escalated" else "white",
                fontsize=19, fontweight="bold", ha="center", va="center", zorder=4)
        ax.text(x + 6.4, y + H - 4.6, NAME[s].replace(", ", ",\n").replace(" (", "\n("), fontsize=14.5,
                fontweight="bold", color=INK, va="center", ha="left", linespacing=1.05)
        ax.text(x + 1.8, y + H - 8.4, textwrap.fill(SCEN_BLURB[s], 44, break_on_hyphens=False), fontsize=12.5, color=INK2, va="top", ha="left",
                linespacing=1.2)
        oil = val("fed_oil", "oil_price_change_pct", s)
        gdp = val("fed_oil", "peak_gdp_impact_pct", s)
        cpi = val("fed_oil", "peak_cpi_impact_pp", s)
        for i, (big, lab) in enumerate([(f"+{oil:.0f}%", "oil price\nimpulse"), (f"{gdp:+.2f}%", "US GDP\ntrough"),
                                        (f"+{cpi:.2f} pp", "US CPI\npeak")]):
            bx = x + 1.8 + i * 8.9
            ax.text(bx, y + 6.6, big.replace("-", "−"), fontsize=21, fontweight="bold", color=INK, ha="left", va="bottom")
            ax.text(bx, y + 5.9, lab, fontsize=11.5, color=INK2, ha="left", va="top", linespacing=1.0)

    # axes of the matrix
    ax.annotate("", xy=(66, 58.8), xytext=(8, 58.8), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.6, mutation_scale=18))
    ax.text(8, 59.6, "SWIFT  (4–6 weeks)", fontsize=12.5, color=INK2, ha="left", va="bottom", fontweight="bold")
    ax.text(65, 59.6, "PROLONGED  (3–6+ months)", fontsize=12.5, color=INK2, ha="right", va="bottom", fontweight="bold")
    ax.text(37, 59.6, "Closure duration", fontsize=13, color=INK, ha="center", va="bottom")
    ax.annotate("", xy=(5.5, 1.5), xytext=(5.5, 57), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.6, mutation_scale=18))
    ax.text(4.4, 56.8, "CONTAINED", fontsize=12.5, color=INK2, rotation=90, ha="right", va="top", fontweight="bold")
    ax.text(4.4, 1.5, "ESCALATED", fontsize=12.5, color=INK2, rotation=90, ha="right", va="bottom", fontweight="bold")
    ax.text(4.4, 29.5, "Conflict scope", fontsize=13, color=INK, rotation=90, ha="right", va="center")
    ax.text(84, 44.3, "Prescribed outside the matrix", fontsize=12.5, color=INK2, ha="center", va="bottom", style="italic")

    footnote(fig, f"Oil impulse: POLES-JRC-slot reduction{DAGGER} forwarded into the Baumeister–Hamilton-calibrated SVAR "
                  f"reduction{DAGGER}, which supplies the US GDP and CPI responses. May 2026 run 20260504_222710. "
                  f"{DAGGER} closed-form stand-in calibrated to published elasticities, not the named upstream model. "
                  "E's water damage is under-registered in this run (see GDP figure).")
    save(fig, "fig02_scenario_matrix")


# ============================================================== FIG 03 · pipeline architecture
def _box(ax, x, y, w, h, title, body=None, fc="white", ec=AXIS, lw=1.4, tcolor=INK, title_size=15, body_size=12, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.9", fc=fc, ec=ec, lw=lw, ls=ls, zorder=2))
    ax.text(x + w / 2, y + h - 1.4, title, ha="center", va="top", fontsize=title_size, fontweight="bold", color=tcolor, zorder=3,
            linespacing=1.05)
    if body:
        ax.text(x + w / 2, y + h - 1.4 - (4.0 if "\n" not in title else 7.2), body, ha="center", va="top",
                fontsize=body_size, color=INK2, zorder=3, linespacing=1.2)


def _arrow(ax, p0, p1, color=INK2, lw=1.8, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=18, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=4, shrinkA=2, shrinkB=2))


def _person(ax, x, y, c, r=0.9):
    ax.add_patch(Circle((x, y + 0.9), r * 0.55, color=c, zorder=6))
    ax.add_patch(FancyBboxPatch((x - r * 0.85, y - 0.75), r * 1.7, r * 1.0, boxstyle="round,pad=0,rounding_size=0.6",
                                color=c, zorder=6))


def fig03_pipeline():
    fig = plt.figure(figsize=(20, 8.4))
    header(fig, "Algorithm 1: the LLM writes and reads; deterministic code computes; analysts approve",
           "LangGraph pipeline with three mandatory analyst checkpoints and provenance on every number")
    ax = fig.add_axes([0.0, 0.05, 1.0, 0.78])
    ax.set_xlim(0, 200); ax.set_ylim(-6, 68); ax.axis("off")

    LLM_FC, LLM_EC = "#efecfc", "#6250d6"
    DET_FC, DET_EC = "#e8f1fc", NAVY_MID
    HUM = "#c98500"
    ROW = 33.5  # centre line of the main flow

    _box(ax, 0.5, ROW - 13, 21, 26, "Inputs", "Crisis brief\n\nSchwartz scenario\nframework (STEEP)\n\nWeekly news +\nEIA indicators",
         fc="#f6f5f1", ec=AXIS, body_size=12.5)
    _box(ax, 26, ROW - 11, 23, 22, "① Scenario\ngeneration", "5 narratives with\nexplicit quantitative\nassumptions",
         fc=LLM_FC, ec=LLM_EC)
    _box(ax, 59, ROW - 11, 24, 22, "② Parameter\nextraction", "Typed inputs per model,\nwith confidence and\ninference flags",
         fc=LLM_FC, ec=LLM_EC)
    # model execution
    ax.add_patch(FancyBboxPatch((93, 0.5), 54, 66, boxstyle="round,pad=0,rounding_size=1.2", fc=DET_FC, ec=DET_EC, lw=1.8,
                                zorder=1))
    ax.text(120, 65.0, "③ Model execution", ha="center", va="top", fontsize=16, fontweight="bold", color=INK)
    ax.text(120, 61.4, "35 adapters · Python, Julia, GAMS, R, Octave, Excel, AnyLogic",
            ha="center", va="top", fontsize=11.5, color=INK2)
    tiers = [
        ("Commodity", "water · oil · LNG · helium · fertilizer · shipping", 45.0),
        ("Commodity-downstream", "fab simulation · helium ABM · crop yields · LNG profits", 27.25),
        ("Macro (short- & long-run)", "oil-shock SVAR · electricity · CGE · energy systems", 9.5),
    ]
    for t, body, y in tiers:
        ax.add_patch(FancyBboxPatch((97, y), 46, 11.5, boxstyle="round,pad=0,rounding_size=0.7", fc="white", ec=DET_EC,
                                    lw=1.2, zorder=2))
        ax.text(120, y + 8.4, t, ha="center", va="center", fontsize=14, fontweight="bold", color=INK, zorder=3)
        ax.text(120, y + 3.6, body, ha="center", va="center", fontsize=11.5, color=INK2, zorder=3)
    for y0, y1 in [(45.0, 38.75), (27.25, 21.0)]:
        _arrow(ax, (120, y0), (120, y1), color=DET_EC, lw=2.2)
        ax.text(122, (y0 + y1) / 2, "forward computed shocks,\nreplace LLM guesses", fontsize=10.5, color=NAVY,
                va="center", ha="left", style="italic", zorder=5, linespacing=1.0)
    ax.text(120, 5.0, "consistency checks across models", ha="center", va="center", fontsize=11.5, color=NAVY,
            style="italic")

    _box(ax, 153, ROW - 11, 21, 22, "④ Synthesis", "LLM prose; numbers\npass through and are\naudited for fidelity",
         fc=LLM_FC, ec=LLM_EC)
    _box(ax, 183, ROW - 11, 16.5, 22, "⑤ Report", "Every number\ntraced to a\nmodel run", fc="#f6f5f1", ec=AXIS)

    # checkpoints
    for x, label in [(54, "Review\nscenarios"), (88, "Validate\nparameters"), (178.5, "Review\nreport")]:
        ax.add_patch(Circle((x, ROW), 3.0, fc="#fff3d6", ec=HUM, lw=1.8, zorder=5))
        _person(ax, x, ROW - 0.5, HUM, r=1.6)
        ax.text(x, ROW - 4.2, label, ha="center", va="top", fontsize=11, color=INK, fontweight="semibold", zorder=6,
                linespacing=1.0)

    for x0, x1 in [(21.5, 26), (49, 51), (57, 59), (83, 85), (91, 97), (147, 153), (174, 175.5), (181.5, 183)]:
        _arrow(ax, (x0, ROW), (x1, ROW))

    # analyst feedback loop, routed under everything
    fb = [(191, ROW - 11), (191, -3.5), (71, -3.5), (71, ROW - 11)]
    ax.plot([p[0] for p in fb[:-1]], [p[1] for p in fb[:-1]], color=HUM, lw=1.8, ls=(0, (5, 3)), zorder=0)
    _arrow(ax, fb[-2], fb[-1], color=HUM, lw=1.8, ls=(0, (5, 3)))
    ax.text(160, -2.6, "analyst edits → selective rerun of the affected scenarios and models", fontsize=12,
            color="#8a5a00", ha="center", va="bottom", style="italic",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    _arrow(ax, (11, ROW - 13), (11, ROW - 18), color=MUTED, lw=1.4)
    ax.text(11, ROW - 19, "Module 6: weekly news\nre-runs the whole chain", ha="center", va="top", fontsize=11.5,
            color=INK2, style="italic", linespacing=1.05)

    handles = [
        Rectangle((0, 0), 1, 1, fc=LLM_FC, ec=LLM_EC, lw=1.4, label="LLM step"),
        Rectangle((0, 0), 1, 1, fc=DET_FC, ec=DET_EC, lw=1.4, label="Deterministic code"),
        Line2D([], [], marker="o", ls="", ms=16, mfc="#fff3d6", mec=HUM, mew=1.8, label="Analyst checkpoint"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=13, frameon=False, ncol=1,
              handlelength=1.6, handleheight=1.2)
    footnote(fig, "In the batch runs reported in the paper, checkpoints were auto-approved; interactive runs pause for the analyst.")
    save(fig, "fig03_pipeline_architecture")


# ============================================================== FIG 04 · forwarding network
NICE = {
    "weap_mena": "WEAP-MENA", "cwatm": "CWatM", "sahysmod": "SahysMod", "watergap2": "WaterGAP2",
    "poles_jrc": "POLES-JRC", "bornstein_krusell_rebelo": "Bornstein–Krusell–Rebelo", "marketsim": "MarketSim",
    "lngst": "LNGST", "ggm": "Global Gas Model", "energy_flux_gas_power": "Energy Flux gas power",
    "world_helium_model": "World Helium Model", "world_fertilizer": "World Fertilizer Model", "futures": "Futures curves",
    "magpie": "MAgPIE", "capri": "CAPRI", "simple_g": "SIMPLE-G", "aisdb": "AISdb", "ais_project": "AIS_project",
    "argonne_abm": "Argonne helium ABM", "simrlfab": "SimRLFab", "apsim": "APSIM",
    "energy_flux_lng_profits": "Energy Flux LNG profits", "fed_oil": "Fed oil SVAR", "nems": "NEMS", "mam": "MAM",
    "nrel": "NREL electricity", "pycge": "PyCGE", "mpsge_jl": "MPSGE.jl", "opencge": "OpenCGE (OG-Core)",
    "miragrodep": "MIRAGRODEP", "apsim_gtap": "APSIM–GTAP", "gtap": "GTAP", "osemosys": "OSeMOSYS",
    "messageix": "MESSAGEix", "temoa": "TEMOA",
}
SYS_LABEL = {"shipping": "Shipping", "oil": "Oil", "lng": "LNG", "helium_semiconductors": "Helium & chips",
             "fertilizer_agriculture": "Fertilizer & food", "water": "Water", "macroeconomic": "Macro",
             "energy_systems": "Energy systems"}


def _model_rows():
    inv = {m["model_id"]: m for m in json.load(open(ROOT / "docs" / "revision" / "model_inventory.json"))}
    inv.setdefault("apsim_gtap", {"model_id": "apsim_gtap", "commodity_system": "fertilizer_agriculture",
                                  "analytical_level": "long_run_macro_strategic", "mode_when_executed": "full_upstream"})
    inv["energy_flux_lng_profits"]["analytical_level"] = "commodity_downstream"  # current adapter (Nov 2026)
    return inv


def fig04_network():
    inv = _model_rows()
    rules = yaml.safe_load(open(ROOT / "configs" / "upstream_forwarding_mapping.yaml"))["models"]
    edges = {}
    for ds, rs in rules.items():
        for r in rs.values():
            for s in r.get("sources") or []:
                edges[(s["source_model"], ds)] = edges.get((s["source_model"], ds), 0) + 1

    col_of = {"commodity": 0, "commodity_downstream": 1, "short_run_macro": 2, "long_run_macro_strategic": 2}
    sys_order = ["shipping", "oil", "lng", "helium_semiconductors", "fertilizer_agriculture", "water"]
    cols = {0: [], 1: [], 2: []}
    for mid, m in inv.items():
        cols[col_of[m["analytical_level"]]].append(mid)
    cols[0].sort(key=lambda m: (sys_order.index(inv[m]["commodity_system"]), NICE[m]))
    cols[1].sort(key=lambda m: (sys_order.index(inv[m]["commodity_system"]), NICE[m]))
    macro_order = ["fed_oil", "nrel", "nems", "mam", "pycge", "mpsge_jl", "opencge", "miragrodep", "apsim_gtap", "gtap",
                   "osemosys", "messageix", "temoa"]
    cols[2].sort(key=lambda m: macro_order.index(m))
    cross = {(a, b): n for (a, b), n in edges.items()
             if a in inv and b in inv and col_of[inv[a]["analytical_level"]] < col_of[inv[b]["analytical_level"]]}

    fig = plt.figure(figsize=(18, 13.5))
    n_edges = len(cross)
    header(fig, "Models talk to models: computed shocks replace LLM estimates",
           f"{n_edges} cross-tier forwarding links declared in YAML (Algorithm 1, step 11); "
           f"node shade shows what each adapter runs")
    ax = fig.add_axes([0.0, 0.06, 1.0, 0.82])
    ax.set_xlim(-2, 102); ax.set_ylim(0, 100); ax.axis("off")
    X = {0: 4, 1: 41, 2: 76}
    NW = 21
    pos = {}
    tops = {0: 94, 1: 82, 2: 94}
    gaps = {0: 3.05, 1: 5.0, 2: 5.7}
    for c, ids in cols.items():
        y = tops[c]
        prev = None
        for mid in ids:
            sysk = inv[mid]["commodity_system"]
            if c == 0 and sysk != prev:
                y -= 1.1 if prev else 0
                ax.text(X[c] - 1.0, y - 0.2, SYS_LABEL[sysk].upper(), fontsize=10.5, color=MUTED, ha="right", va="center",
                        fontweight="bold")
                prev = sysk
            if c == 1 and sysk != prev:
                y -= 2.4 if prev else 0
                ax.text(X[c] + 0.3, y + 1.9, SYS_LABEL[sysk].upper(), fontsize=10.5, color=MUTED, ha="left",
                        va="center", fontweight="bold")
                prev = sysk
            if c == 2 and mid == "pycge":
                y -= 1.6
            pos[mid] = (X[c], y)
            y -= gaps[c] if c != 0 else 2.9
    for c, label, sub in [(0, "COMMODITY", "run first, in parallel"), (1, "COMMODITY-DOWNSTREAM", "read commodity outputs"),
                          (2, "MACRO", "read everything upstream")]:
        ax.text(X[c] + NW / 2, 99.5, label, fontsize=14, fontweight="bold", color=INK, ha="center", va="bottom")
        ax.text(X[c] + NW / 2, 99.3, sub, fontsize=11.5, color=INK2, ha="center", va="top")
    ax.text(X[2] - 1.0, pos["fed_oil"][1] + 1.9, "SHORT-RUN", fontsize=10.5, color=MUTED, ha="left", va="center",
            fontweight="bold")
    ax.text(X[2] - 1.0, pos["pycge"][1] + 1.9, "LONG-RUN", fontsize=10.5, color=MUTED, ha="left", va="center",
            fontweight="bold")

    # edges
    for (a, b), n in sorted(cross.items(), key=lambda kv: kv[1]):
        x0, y0 = pos[a][0] + NW, pos[a][1]
        x1, y1 = pos[b]
        verts = [(x0, y0), (x0 + (x1 - x0) * 0.45, y0), (x1 - (x1 - x0) * 0.45, y1), (x1, y1)]
        p = MPath(verts, [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4])
        ax.add_patch(PathPatch(p, fc="none", ec="#5a6f8c", lw=0.9 + 0.7 * n, alpha=0.32, zorder=1))

    style = {
        "full_upstream": dict(fc=NAVY, ec=NAVY, tc="white", ls="-", suffix=""),
        "published_output_ingestion": dict(fc="white", ec=NAVY, tc=NAVY, ls="-", suffix=DDAGGER),
        "analytical_reduction": dict(fc=BLUE_LIGHT, ec=BLUE_250, tc=INK, ls="-", suffix=DAGGER),
        "stub": dict(fc="white", ec=AXIS, tc=MUTED, ls=(0, (3, 2)), suffix=""),
    }
    for mid, (x, y) in pos.items():
        st = style[inv[mid]["mode_when_executed"]]
        ax.add_patch(FancyBboxPatch((x, y - 1.15), NW, 2.3, boxstyle="round,pad=0,rounding_size=0.6", fc=st["fc"],
                                    ec=st["ec"], lw=1.4, ls=st["ls"], zorder=3))
        ax.text(x + 0.8, y, NICE[mid] + st["suffix"], fontsize=12, color=st["tc"], va="center", ha="left", zorder=4,
                fontweight="semibold" if inv[mid]["mode_when_executed"] == "full_upstream" else "normal")

    counts = pd.Series([m["mode_when_executed"] for m in inv.values()]).value_counts()
    handles = [
        Rectangle((0, 0), 1, 1, fc=NAVY, ec=NAVY, label=f"Full upstream model ({counts.get('full_upstream', 0)})"),
        Rectangle((0, 0), 1, 1, fc="white", ec=NAVY, lw=1.4,
                  label=f"Published-output ingestion{DDAGGER} ({counts.get('published_output_ingestion', 0)})"),
        Rectangle((0, 0), 1, 1, fc=BLUE_LIGHT, ec=BLUE_250, lw=1.4,
                  label=f"Calibrated closed-form stand-in{DAGGER} ({counts.get('analytical_reduction', 0)})"),
        Rectangle((0, 0), 1, 1, fc="white", ec=AXIS, ls=(0, (3, 2)), lw=1.4, label=f"Typed stub ({counts.get('stub', 0)})"),
    ]
    leg = ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.045), ncol=4, fontsize=13, frameon=False,
                    handlelength=1.8, handleheight=1.1, columnspacing=2.2)
    footnote(fig, "Shade = default mode with no extra configuration; full models need licences, binaries or data that "
                  "were not all present on the cluster. Line width = number of forwarded fields.")
    save(fig, "fig04_model_network")


# ============================================================== FIG 05 · GDP across scenarios
def fig05_gdp():
    replay = json.load(open(ROOT / "docs" / "revision" / "runs" / "20260504_222710_filled" / "scenario_e_input_replay.json"))
    # 'water severely_damaged' case of the PyCGE kernel replay (helium left as recorded)
    e_fix = next(c["gdp_impact_pct"] for c in replay
                 if c["case"].startswith("water severely_damaged"))

    models = [("pycge", "o", f"PyCGE kernel{DAGGER} (short-run)"),
              ("mpsge_jl", "s", f"MPSGE.jl kernel{DAGGER} (long-run)"),
              ("nrel", "^", f"NREL electricity block{DAGGER}")]
    fig = plt.figure(figsize=(14, 7.6))
    header(fig, "Duration and escalation drive GDP losses; one input fix reorders the tail",
           "Reference-economy GDP impact (%) by scenario, three macro reductions")
    ax = fig.add_axes([0.25, 0.17, 0.72, 0.62])
    ys = {s: i for i, s in enumerate(reversed(SCEN))}
    for s in SCEN:
        y = ys[s]
        vals = [val(m, "gdp_impact_pct", s) for m, _, _ in models]
        ax.plot([min(vals), max(vals)], [y, y], color=COLOR[s], lw=2, alpha=0.5, zorder=1)
        for (m, mk, _), v in zip(models, vals):
            ax.scatter([v], [y], marker=mk, s=170, color=COLOR[s], edgecolor="white", linewidth=2, zorder=3)
        ax.text(-1.67, y, f"{LETTER[s]}", fontsize=17, fontweight="bold", color=INK, ha="left", va="center")
    ax.set_yticks(list(ys.values()))
    ax.set_yticklabels([SHORT[s] for s in ys], fontsize=14, color=INK)
    ax.tick_params(axis="y", length=0, pad=10)
    for s in SCEN:
        ax.get_yticklabels()[ys[s]].set_color(INK)
    ax.set_xlim(-1.72, 0.08)
    ax.axvline(0, color=AXIS, lw=1.2)
    ax.grid(axis="x"); ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("GDP impact, % vs. no-crisis baseline", fontsize=14)
    ax.set_xticks([-1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0])
    ax.set_xticklabels([f"{t:.2f}".replace("-", "−") for t in ax.get_xticks()])

    yE = ys["infrastructure_collapse"]
    ax.scatter([e_fix], [yE], marker="o", s=170, facecolor="white", edgecolor=COLOR["infrastructure_collapse"],
               linewidth=2.5, zorder=4)
    ax.annotate("", xy=(e_fix + 0.03, yE), xytext=(val("pycge", "gdp_impact_pct", "infrastructure_collapse") - 0.03, yE),
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.4, ls=(0, (3, 2))), zorder=2)
    ax.text(e_fix - 0.02, yE + 0.3, f"{e_fix:.2f}".replace("-", "−") + " with the framework's water damage "
            "(PyCGE kernel replay, not a run result)", fontsize=11.5, color=INK2, ha="left", va="bottom")
    # D's PyCGE value as a reference tick on the E row: the replay lands below it
    d_py = val("pycge", "gdp_impact_pct", "prolonged_escalated")
    ax.plot([d_py, d_py], [yE - 0.22, yE + 0.22], color=COLOR["prolonged_escalated"], lw=3, zorder=2,
            solid_capstyle="round")
    ax.text(d_py, yE - 0.3, f"D, PyCGE {d_py:.2f}".replace("-", "−"), fontsize=11.5, color=INK2,
            ha="center", va="top")
    ax.set_ylim(-0.8, len(SCEN) - 0.5)

    handles = [Line2D([], [], marker=mk, ls="", color=INK2, mec="white", ms=12, label=lab) for _, mk, lab in models]
    handles.append(Line2D([], [], marker="o", ls="", mfc="white", mec=INK2, mew=2, ms=12, label="Sensitivity replay"))
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=4, frameon=False, fontsize=12.5,
              handletextpad=0.3, columnspacing=1.4)
    footnote(fig, f"May 2026 run 20260504_222710. {DAGGER} closed-form kernels calibrated to published elasticities "
                  "(Hamilton 2003/2009; Kilian 2008; Blanchard–Galí 2007); headline is an OECD/US-calibrated reference economy, "
                  "not a world aggregate. In E the LLM wrote water status 'damaged', which the water model read as intact.")
    save(fig, "fig05_gdp_by_scenario")


# ============================================================== FIG 06 · US macro IRFs
def fig06_irf():
    panels = [("gdp_irf_pct", "Real GDP", "% deviation"), ("cpi_irf_pp", "CPI inflation", "pp"),
              ("fed_funds_rate_irf_pp", "Federal funds rate", "pp"), ("unemployment_irf_pp", "Unemployment rate", "pp")]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True)
    fig.subplots_adjust(left=0.07, right=0.86, top=0.80, bottom=0.12, hspace=0.35, wspace=0.25)
    header(fig, "US transmission: a supply shock that fades over two years",
           f"Quarterly impulse responses by scenario, Baumeister–Hamilton-calibrated oil-shock SVAR reduction{DAGGER}")
    for ax, (key, title, unit) in zip(axes.flat, panels):
        ends = []
        for s in SCEN:
            d = raw(s, f"fed_oil__{key}_quarterly__series.csv")
            ax.plot(d.period, d.value, color=COLOR[s], lw=2.6, marker="o", ms=6, mec="white", mew=1.2,
                    zorder=3 if s != "infrastructure_collapse" else 4)
            ends.append((s, d.period.iloc[-1], d.value.iloc[-1], d.value.iloc[0]))
        ax.axhline(0, color=AXIS, lw=1.1, zorder=1)
        ax.grid(axis="y"); ax.set_axisbelow(True)
        ax.set_title(f"{title}", loc="left", fontsize=17, fontweight="bold", color=INK, pad=8)
        ax.text(1.0, 1.02, unit, transform=ax.transAxes, ha="right", va="bottom", fontsize=12, color=INK2)
        ax.set_xticks(range(0, 9))
        ax.set_xticklabels([f"Q{i}" for i in range(0, 9)])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.1f}".replace("-", "−")))
        e = [t for t in ends if t[0] == "infrastructure_collapse"][0]
        ax.text(e[1] + 0.25, e[2], "E", fontsize=13, fontweight="bold", color=INK, va="center", ha="left")
        ax.set_xlim(-0.4, 8.7)
    handles = [Line2D([], [], color=COLOR[s], lw=3, marker="o", ms=7, mec="white", label=f"{LETTER[s]}  {SHORT[s]}")
               for s in SCEN]
    fig.legend(handles=handles, loc="center left", bbox_to_anchor=(0.865, 0.47), frameon=False, fontsize=13.5,
               labelspacing=1.1, handlelength=2.0)
    for ax in axes[1]:
        ax.set_xlabel("Quarters after the shock")
    footnote(fig, f"Oil price impulse forwarded from the POLES-JRC-slot reduction{DAGGER}: A +54.8%, B +60.5%, C +58.3%, "
                  "D +51.8%, E +48.4%; E lasts 5 quarters, the others 1–1.75. May 2026 run 20260504_222710.")
    save(fig, "fig06_us_macro_irf")


# ============================================================== FIG 07 · regional GDP map + heatmap
REG_NAME = {"US": "United States", "CHN": "China", "IND": "India", "EU": "EU-27", "MENA_GCC": "Gulf (GCC)",
            "MENA_OTHER": "Other MENA", "SSA": "Sub-Saharan Africa", "LAC": "Latin America", "ROW": "Rest of world"}
BINS = [-2.5, -1.5, -1.0, -0.5, -0.1, 0.1, 0.5, 1.0, 2.0, 3.5]
DIV = ["#b2302e", "#d9625e", "#eb9a95", "#f6cfcb", "#f0efec", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"]


def _bin_color(v):
    for i in range(len(BINS) - 1):
        if v < BINS[i + 1]:
            return DIV[i]
    return DIV[-1]


def _pycge_regions():
    return {s: raw(s, "pycge__regional_vars.csv").set_index("region").gdp_impact_pct for s in SCEN}


def fig07_regional():
    data = _pycge_regions()
    s = "prolonged_escalated"
    feats = load_geo("world_50m.geojson")
    fig = plt.figure(figsize=(18, 10.4))
    header(fig, "Importers lose, Gulf exporters gain: the burden falls on Asia, Europe and Africa",
           f"GDP impact by region (%), Scenario D — prolonged closure, escalated conflict · PyCGE kernel{DAGGER}")
    ax = fig.add_axes([0.0, 0.10, 0.80, 0.78])
    patches, colors = [], []
    for f in feats:
        r = kernel_region(f["properties"])
        patches.append(PathPatch(poly_path(f["geometry"]["coordinates"], equal_earth)))
        colors.append(_bin_color(data[s][r]))
    ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor="white", linewidth=0.35))
    ax.set_xlim(-2.75, 2.75); ax.set_ylim(-0.92, 1.36); ax.set_aspect("equal"); ax.axis("off")
    lab = {"US": (-98, 39), "CHN": (103, 34), "IND": (78.5, 21), "EU": (12, 49), "MENA_GCC": (49, 21.5),
           "MENA_OTHER": (14, 27.5), "SSA": (22, 0), "LAC": (-60, -12), "ROW": (92, 61)}
    for r, (lo, la) in lab.items():
        x, y = equal_earth(np.array([lo]), np.array([la]))
        v = data[s][r]
        ax.text(x[0], y[0] + 0.035, REG_NAME[r], fontsize=12, color=INK, ha="center", va="bottom", fontweight="semibold",
                bbox=dict(boxstyle="round,pad=0.15", fc=(1, 1, 1, 0.75), ec="none"))
        ax.text(x[0], y[0] + 0.03, f"{v:+.2f}%".replace("-", "−"), fontsize=15, color=INK, ha="center", va="top",
                fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc=(1, 1, 1, 0.75), ec="none"))
    # legend: binned diverging scale
    lax = fig.add_axes([0.83, 0.22, 0.025, 0.56])
    for i, c in enumerate(DIV):
        lax.add_patch(Rectangle((0, i), 1, 0.92, color=c))
    lax.set_xlim(0, 1); lax.set_ylim(0, len(DIV)); lax.axis("off")
    for i, b in enumerate(BINS[1:-1]):
        lax.text(1.35, i + 0.96, f"{b:+.1f}".replace("-", "−").replace("+0.1", "+0.1"), fontsize=12, color=INK2,
                 va="center", ha="left")
    lax.text(0, len(DIV) + 0.35, "GDP impact, %", fontsize=13, color=INK, ha="left", va="bottom", fontweight="bold")
    lax.text(2.6, 1.8, "losses", fontsize=12, color=INK2, rotation=90, va="center")
    lax.text(2.6, 7.0, "gains", fontsize=12, color=INK2, rotation=90, va="center")
    footnote(fig, f"{DAGGER} Regional rows scale the reference-economy response by literature multipliers per region and commodity "
                  "(net oil/gas exporters flip sign). Regions follow the kernel taxonomy; Taiwan, Japan, Russia etc. are in "
                  "Rest of world. May 2026 run 20260504_222710.")
    save(fig, "fig07_regional_gdp_map")

    # heatmap companion: regions x scenarios with values
    order = ["IND", "SSA", "EU", "CHN", "ROW", "US", "LAC", "MENA_OTHER", "MENA_GCC"]
    fig = plt.figure(figsize=(13, 9))
    header(fig, "Who bears the shock, scenario by scenario",
           f"GDP impact by region (%), PyCGE kernel{DAGGER}")
    ax = fig.add_axes([0.2, 0.08, 0.76, 0.70])
    for j, sc in enumerate(SCEN):
        for i, r in enumerate(order):
            v = data[sc][r]
            c = _bin_color(v)
            ax.add_patch(Rectangle((j + 0.03, i + 0.04), 0.94, 0.92, color=c, lw=0))
            dark = c in ("#b2302e", "#d9625e", "#3987e5", "#1c5cab")
            ax.text(j + 0.5, i + 0.5, f"{v:+.2f}".replace("-", "−"), ha="center", va="center", fontsize=15,
                    color="white" if dark else INK, fontweight="semibold")
    ax.set_xlim(0, len(SCEN)); ax.set_ylim(len(order), 0)
    ax.set_xticks([j + 0.5 for j in range(len(SCEN))])
    ax.set_xticklabels([f"{LETTER[s]}\n{SHORT[s].replace(' · ', chr(10))}" for s in SCEN], fontsize=12.5, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(order))])
    ax.set_yticklabels([REG_NAME[r] for r in order], fontsize=14, color=INK)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    footnote(fig, "Same binned scale as the map: red = loss, blue = gain, gray = within ±0.1%. May 2026 run 20260504_222710.")
    save(fig, "fig07b_regional_gdp_heatmap")


# ============================================================== FIG 08 · observed vs model
def fig08_observed():
    m = pd.read_csv(ROOT / "data" / "market" / "monthly_prices.csv")
    m = m[(m.month >= "2025-06") & (m.month <= "2026-10")]
    piv = m.pivot(index="month", columns="series", values="value")
    base_months = ["2025-11", "2025-12", "2026-01"]
    lngst_base = {"ttf": val("lngst", "hub_baseline_prices.ttf", "prolonged_contained"),
                  "henry_hub": val("lngst", "hub_baseline_prices.henry_hub", "prolonged_contained")}
    model = {
        "brent": [(f"POLES-JRC slot{DAGGER}", ["swift_contained", "swift_escalated"],
                   [val("poles_jrc", "peak_price_change_pct", s) for s in ("swift_contained", "swift_escalated")])],
        "ttf": [(f"LNGST slot{DAGGER}", ["prolonged_contained", "swift_escalated"],
                 [(val("lngst", "ttf_price", s) / lngst_base["ttf"] - 1) * 100 for s in ("prolonged_contained", "swift_escalated")])],
        "henry_hub": [(f"LNGST slot{DAGGER}", ["prolonged_contained", "swift_escalated"],
                       [(val("lngst", "henry_hub_price", s) / lngst_base["henry_hub"] - 1) * 100
                        for s in ("prolonged_contained", "swift_escalated")])],
        "urea": [(f"World Fertilizer slot{DAGGER}", ["prolonged_contained", "swift_escalated"],
                  [val("world_fertilizer", "price_urea_pct", s) for s in ("prolonged_contained", "swift_escalated")])],
    }
    titles = {"brent": "Brent crude", "ttf": "TTF gas (Europe)", "henry_hub": "Henry Hub gas (US)", "urea": "Urea fertilizer"}
    fig, axes = plt.subplots(2, 2, figsize=(16, 10.5), sharex=True)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.80, bottom=0.13, hspace=0.38, wspace=0.18)
    header(fig, "Reality check: the stand-ins understate oil and gas, and miss the US gas decoupling",
           "Observed monthly price, % change from pre-crisis baseline (median Nov 2025–Jan 2026), vs. modelled peak")
    months = list(piv.index)
    xi = np.arange(len(months))
    onset = months.index("2026-02")
    for ax, ser in zip(axes.flat, ["brent", "ttf", "henry_hub", "urea"]):
        base = float(np.median(piv.loc[base_months, ser]))
        pct = (piv[ser] / base - 1) * 100
        ax.axvspan(onset - 0.5, len(months) - 0.5, color="#fbeceb", lw=0, zorder=0)
        ax.axhline(0, color=AXIS, lw=1.1)
        ax.plot(xi, pct.values, color=INK, lw=2.8, zorder=3)
        ax.scatter(xi, pct.values, s=26, color=INK, zorder=3)
        # extreme move inside the closure window only (the baseline window can hold its own spikes)
        win = pct.values[onset:]
        k = onset + int(np.argmax(np.abs(win)))
        up = pct.values[k] > 0
        ax.annotate(f"observed {pct.values[k]:+.0f}%".replace("-", "−"), xy=(xi[k], pct.values[k]),
                    xytext=(xi[k] - 0.5, pct.values[k] + 14) if up else (xi[k] + 0.3, pct.values[k] - 11),
                    fontsize=13.5, fontweight="bold", color=INK, ha="right" if up else "left", va="center", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
        for lab, scs, vals in model[ser]:
            for j, (s, v) in enumerate(zip(scs, vals)):
                ax.scatter([len(months) + 0.25 + 0.6 * j], [v], s=170, color=COLOR[s], edgecolor="white", linewidth=1.8,
                           zorder=4, clip_on=False)
            lo, hi = min(vals), max(vals)
            ax.plot([onset - 0.5, len(months) - 0.5], [hi, hi], color=INK2, lw=1.4, ls=(0, (4, 3)), zorder=2)
            scen_txt = " = ".join(LETTER[s] for s in scs) if abs(hi - lo) < 0.05 else ", ".join(
                f"{LETTER[s]} {v:+.0f}%" for s, v in zip(scs, vals))
            ax.text(-0.2, hi, f"{lab} peak {hi:+.0f}% ({scen_txt})".replace("-", "−"),
                    fontsize=11.5, color=INK2, ha="left", va="center", zorder=5,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))
        ax.set_title(titles[ser], loc="left", fontsize=17, fontweight="bold", color=INK, pad=8)
        ax.grid(axis="y"); ax.set_axisbelow(True)
        ax.set_xlim(-0.5, len(months) + 1.3)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%".replace("-", "−")
                                                                     if v else "0%"))
        lo_y, hi_y = ax.get_ylim()
        ax.set_ylim(min(lo_y, -45, float(pct.values[k]) - 22), max(hi_y, 60) * 1.18)
    ticks = [i for i, mth in enumerate(months) if mth[5:] in ("06", "09", "12", "03")] + [len(months) - 1]
    for ax in axes[1]:
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(months[i] + "-01").strftime("%b\n%Y") for i in ticks])
    for ax in axes[0]:
        ax.text(onset - 0.3, 0.98, "closure", transform=ax.get_xaxis_transform(), fontsize=11.5, color=CRITICAL,
                va="top", ha="left", fontweight="semibold")
    handles = [Line2D([], [], color=INK, lw=2.8, label="Observed (World Bank Pink Sheet, monthly)")] + \
              [Line2D([], [], marker="o", ls="", color=COLOR[s], mec="white", ms=12, label=f"Model peak, scenario {LETTER[s]}")
               for s in ("swift_contained", "prolonged_contained", "swift_escalated")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=13, bbox_to_anchor=(0.5, 0.005))
    footnote(fig, "Plausibility check, not a forecast test: scenarios are conditional paths, observations are monthly means. "
                  "Dots show scenarios whose records survive in the May run.", y=0.055)
    save(fig, "fig08_observed_vs_model")


# ============================================================== FIG 09 · provenance chain
def fig09_provenance():
    fig = plt.figure(figsize=(20, 6.6))
    header(fig, "Provenance in action: a model overrules the LLM, and the flag is kept",
           "Scenario C oil shock as seen by MPSGE.jl, May 2026 run, traced end to end")
    ax = fig.add_axes([0.0, 0.09, 1.0, 0.70])
    ax.set_xlim(0, 200); ax.set_ylim(4, 60); ax.axis("off")
    steps = [
        ("1  Narrative", "LLM", "“The closure disrupts approximately\n21% of global oil supply and 25%\nof global LNG trade.”", None),
        ("2  Extracted parameter", "LLM", "oil_price_shock_pct", "0  (confidence: low)"),
        ("3  Forwarding override", "code", "replaced by POLES-JRC slot" + DAGGER + "\npeak_price_change_pct", "58.25"),
        ("4  Model output", "code", "MPSGE.jl kernel" + DAGGER + "\noil_price_shock_pct", "58.25"),
        ("5  Synthesis", "LLM", "“The oil price shock is expected to\nbe 58.25% due to the Strait of\nHormuz closure.”", None),
    ]
    W, gap = 34.6, 5.2
    for i, (t, who, body, num) in enumerate(steps):
        x = 1 + i * (W + gap)
        fc, ec = ("#efecfc", "#6250d6") if who == "LLM" else ("#e8f1fc", NAVY_MID)
        ax.add_patch(FancyBboxPatch((x, 8), W, 42, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=1.6))
        ax.text(x + 2, 47.5, t, fontsize=15.5, fontweight="bold", color=INK, va="top")
        ax.text(x + 2, 42.3, "LLM" if who == "LLM" else "deterministic code", fontsize=11.5, color=ec, va="top",
                fontweight="semibold")
        if num is None:
            ax.text(x + 2, 35.5, body, fontsize=13.5, color=INK, va="top", style="italic", linespacing=1.3)
        else:
            ax.text(x + 2, 35.5, body, fontsize=13.5, color=INK2, va="top", family="monospace" if i == 1 else None,
                    linespacing=1.3)
            ax.text(x + 2, 12, num, fontsize=30 if len(num) < 8 else 22, fontweight="bold",
                    color=CRITICAL if i == 1 else INK, va="bottom")
        if i < 4:
            ax.annotate("", xy=(x + W + gap - 0.6, 30), xytext=(x + W + 0.6, 30),
                        arrowprops=dict(arrowstyle="-|>", color=INK2, lw=2, mutation_scale=20))
    # flag badge
    fx = 1 + 2 * (W + gap) + W / 2
    ax.add_patch(FancyBboxPatch((fx - 25, 51.5), 50, 6.0, boxstyle="round,pad=0,rounding_size=1.0",
                                fc="#fde9e9", ec=CRITICAL, lw=1.4))
    ax.text(fx, 54.5, "Flagged: 200% deviation from the LLM value", fontsize=12.5, color="#8f1f1f", ha="center",
            va="center", fontweight="bold")
    footnote(fig, f"Source: docs/revision (R1.3 worked example), May 2026 run 20260504_222710. {DAGGER} closed-form stand-in. "
                  "Consistency flags fire above 50% LLM-vs-model deviation. Batch checkpoints were auto-approved, so in this run "
                  "the flag was recorded but not read by an analyst.")
    save(fig, "fig09_provenance_chain")


# ============================================================== FIG 10 · key numbers strip
def fig10_numbers():
    inv = _model_rows()
    rules = yaml.safe_load(open(ROOT / "configs" / "upstream_forwarding_mapping.yaml"))["models"]
    n_rules = sum(len(r) for r in rules.values())
    systems = len({m["commodity_system"] for m in inv.values()})
    tiles = [
        (f"{len(inv)}", "model adapters", f"across {systems} commodity systems"),
        ("5", "scenarios", "2 × 2 matrix + tail risk"),
        (f"{n_rules}", "forwarding rules", "computed shocks replace LLM guesses"),
        ("24 / 24", "re-executed cells", "reproduce every shared number\n(May run, saved parameters)"),
        ("100%", "value match", "synthesis outcomes vs. model outputs\n(revision run, fidelity validator on)"),
    ]
    fig = plt.figure(figsize=(20, 2.9))
    n = len(tiles)
    for i, (big, lab, sub) in enumerate(tiles):
        x = 0.01 + i / n
        fig.patches.append(FancyBboxPatch((x, 0.06), 1 / n - 0.015, 0.88, boxstyle="round,pad=0,rounding_size=0.02",
                                          transform=fig.transFigure, fc="#f6f5f1", ec="none"))
        fig.text(x + 0.018, 0.86, big, fontsize=46, fontweight="bold", color=NAVY, va="top")
        fig.text(x + 0.018, 0.46, lab, fontsize=18, fontweight="bold", color=INK, va="top")
        fig.text(x + 0.018, 0.30, sub, fontsize=13, color=INK2, va="top", linespacing=1.1)
    save(fig, "fig10_key_numbers")


FIGS = {"fig01": fig01_map, "fig02": fig02_matrix, "fig03": fig03_pipeline, "fig04": fig04_network,
        "fig05": fig05_gdp, "fig06": fig06_irf, "fig07": fig07_regional, "fig08": fig08_observed,
        "fig09": fig09_provenance, "fig10": fig10_numbers}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    for k, fn in FIGS.items():
        if a.only and k not in a.only:
            continue
        fn()
