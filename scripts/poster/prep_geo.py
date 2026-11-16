"""Trim Natural Earth country polygons into two small GeoJSON caches for the poster maps.

Usage: python scripts/poster/prep_geo.py <ne_10m_admin_0_countries.geojson> <ne_50m_admin_0_countries.geojson>
Writes data/geo/gulf_10m.geojson (rings touching the Gulf/Red Sea box) and data/geo/world_50m.geojson
(decimated). Natural Earth is public domain (naturalearthdata.com). Pure Python, no shapely.
"""
import json, sys
from pathlib import Path

KEEP = ["ADM0_A3", "ISO_A3", "NAME", "REGION_WB", "CONTINENT"]
out = Path("data/geo"); out.mkdir(parents=True, exist_ok=True)


def polys(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def decimate(ring, tol):
    keep = [ring[0]]
    for x, y in ring[1:-1]:
        px, py = keep[-1]
        if abs(x - px) + abs(y - py) >= tol:
            keep.append([round(x, 4), round(y, 4)])
    keep.append(ring[-1])
    return keep


def build(src, dst, tol, bbox=None, min_pts=4):
    feats = []
    for f in json.load(open(src, encoding="utf-8"))["features"]:
        p = f["properties"]
        if p.get("CONTINENT") == "Antarctica":
            continue
        out_polys = []
        for poly in polys(f["geometry"]):
            outer = poly[0]
            if bbox:
                x0, y0, x1, y1 = bbox
                xs = [c[0] for c in outer]; ys = [c[1] for c in outer]
                if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
                    continue
            rings = [decimate(r, tol) for r in poly]
            if len(rings[0]) >= min_pts:
                out_polys.append([r for r in rings if len(r) >= min_pts])
        if out_polys:
            feats.append({"type": "Feature", "properties": {k: p.get(k) for k in KEEP},
                          "geometry": {"type": "MultiPolygon", "coordinates": out_polys}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(dst, "w"))
    print(dst, len(feats))


build(sys.argv[1], out / "gulf_10m.geojson", tol=0.01, bbox=(28, 6, 66, 37))
build(sys.argv[2], out / "world_50m.geojson", tol=0.12)
