from __future__ import annotations

import json
from pathlib import Path

import ee


def region(bbox: tuple[float, float, float, float]) -> ee.Geometry:
    return ee.Geometry.Rectangle(list(bbox))


def search(asset: str, bbox, name_query: str | None = None, min_area_km2: float = 1.0):
    fc = ee.FeatureCollection(asset).filterBounds(region(bbox))
    fc = fc.filter(ee.Filter.gte("area_km2", min_area_km2))
    # reduceColumns pulls just the three props in one call instead of the full geometries
    props = fc.reduceColumns(
        ee.Reducer.toList(3), ["rgi_id", "glac_name", "area_km2"]
    ).get("list").getInfo()

    rows = [{"rgi_id": r[0], "glac_name": r[1], "area_km2": r[2]} for r in props]
    if name_query:
        # RGI names are inconsistent ("Lothse Glacier", "Changri Shar/Nup Gl"), so substring match
        q = name_query.lower()
        rows = [r for r in rows if r["glac_name"] and q in r["glac_name"].lower()]
    return sorted(rows, key=lambda r: r["area_km2"] or 0, reverse=True)


def fetch(asset: str, rgi_id: str) -> dict:
    match = ee.FeatureCollection(asset).filter(ee.Filter.eq("rgi_id", rgi_id))
    if match.size().getInfo() == 0:
        raise LookupError(f"RGI id not found: {rgi_id}")
    return match.first().getInfo()


def save_geojson(feature: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": [feature]}, f, indent=2)
    return out_path
