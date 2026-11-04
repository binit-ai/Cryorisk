"""Sentinel-1/-2 scene counts (ported from scripts/legacy/03_check_sentinel_availability.py).

Unlike the legacy script, per-year counts are computed server-side and fetched in a single
getInfo() call per sensor instead of one round-trip per year.
"""

from __future__ import annotations

import ee

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S1_COLLECTION = "COPERNICUS/S1_GRD"


def s2_collection(geom: ee.Geometry, start: str, end: str, max_cloud: float = 30):
    return (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
    )


def s1_collection(geom: ee.Geometry, start: str, end: str):
    return (
        ee.ImageCollection(S1_COLLECTION)
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )


def counts_by_year(collection: ee.ImageCollection, years: list[int]) -> dict[int, int]:
    """Count images per calendar year with one server round-trip."""
    counts = ee.Dictionary.fromLists(
        [str(y) for y in years],
        [collection.filterDate(f"{y}-01-01", f"{y + 1}-01-01").size() for y in years],
    ).getInfo()
    return {int(k): int(v) for k, v in counts.items()}


def seasonal_counts(collection: ee.ImageCollection, years: list[int], season) -> dict[int, int]:
    """Count images inside the configured seasonal window for each year."""
    counts = ee.Dictionary.fromLists(
        [str(y) for y in years],
        [collection.filterDate(*season.date_range(y)).size() for y in years],
    ).getInfo()
    return {int(k): int(v) for k, v in counts.items()}
