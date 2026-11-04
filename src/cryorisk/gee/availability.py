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


def _counts(windows: dict[int, tuple[str, str]], collection: ee.ImageCollection) -> dict[int, int]:
    # Build every count server-side and fetch once; the old script did a getInfo per year.
    counts = ee.Dictionary.fromLists(
        [str(y) for y in windows],
        [collection.filterDate(s, e).size() for s, e in windows.values()],
    ).getInfo()
    return {int(k): int(v) for k, v in counts.items()}


def counts_by_year(collection: ee.ImageCollection, years: list[int]) -> dict[int, int]:
    return _counts({y: (f"{y}-01-01", f"{y + 1}-01-01") for y in years}, collection)


def seasonal_counts(collection: ee.ImageCollection, years: list[int], season) -> dict[int, int]:
    return _counts({y: season.date_range(y) for y in years}, collection)
