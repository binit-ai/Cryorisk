from __future__ import annotations

from dataclasses import dataclass

import ee

NODATA = -32768
CS_PLUS = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S2 = "COPERNICUS/S2_SR_HARMONIZED"
S1 = "COPERNICUS/S1_GRD"  # EE already ships this in dB
DEM = "COPERNICUS/DEM/GLO30_2024_1"  # plain GLO30 is deprecated

# Google's suggested clear cutoff for cs_cdf; revisit if snow gets masked as cloud
CLEAR_THRESHOLD = 0.6


@dataclass(frozen=True)
class Band:
    name: str
    scale: float  # stored = round(physical * scale)
    unit: str


# Everything goes out as int16 to halve file size vs float32; scales keep enough precision.
BANDS: list[Band] = [
    Band("B2", 1e4, "reflectance"),
    Band("B3", 1e4, "reflectance"),
    Band("B4", 1e4, "reflectance"),
    Band("B8", 1e4, "reflectance"),
    Band("B11", 1e4, "reflectance"),
    Band("B12", 1e4, "reflectance"),
    Band("NDSI", 1e4, "index"),
    Band("NDWI", 1e4, "index"),
    Band("VV", 100, "dB"),
    Band("VH", 100, "dB"),
    Band("elevation", 1, "m"),
    Band("slope", 100, "deg"),
]
BAND_NAMES = [b.name for b in BANDS]


def s2_composite(geom: ee.Geometry, start: str, end: str) -> tuple[ee.Image, ee.Number]:
    cs = ee.ImageCollection(CS_PLUS)
    col = (
        ee.ImageCollection(S2)
        .filterBounds(geom)
        .filterDate(start, end)
        .linkCollection(cs, ["cs_cdf"])
    )

    def prep(img):
        clear = img.select("cs_cdf").gte(CLEAR_THRESHOLD)
        refl = img.select(["B2", "B3", "B4", "B8", "B11", "B12"]).divide(1e4)
        # B11/B12 are 20 m; nearest would give blocky edges on the 10 m grid
        return refl.resample("bilinear").updateMask(clear)

    comp = col.map(prep).median()
    ndsi = comp.normalizedDifference(["B3", "B11"]).rename("NDSI")
    ndwi = comp.normalizedDifference(["B3", "B8"]).rename("NDWI")
    return comp.addBands([ndsi, ndwi]), col.size()


def s1_composite(geom: ee.Geometry, start: str, end: str) -> tuple[ee.Image, ee.Dictionary]:
    base = (
        ee.ImageCollection(S1)
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )
    # Mixing passes blends two different layover/shadow geometries in steep terrain,
    # so stick to whichever pass has more scenes.
    asc = base.filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
    desc = base.filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
    use_asc = asc.size().gte(desc.size())
    chosen = ee.ImageCollection(ee.Algorithms.If(use_asc, asc, desc))
    # median knocks down speckle; clamp drops shadow (-inf-ish) and layover spikes
    img = chosen.select(["VV", "VH"]).median().clamp(-30, 5)
    info = ee.Dictionary(
        {
            "orbit": ee.Algorithms.If(use_asc, "ASCENDING", "DESCENDING"),
            "count": chosen.size(),
            "ascending": asc.size(),
            "descending": desc.size(),
        }
    )
    return img, info


def dem_bands() -> ee.Image:
    col = ee.ImageCollection(DEM).select("DEM")
    # mosaic() drops the native projection; Terrain.slope needs it or it computes at 1 deg
    dem = col.mosaic().setDefaultProjection(col.first().projection()).rename("elevation")
    slope = ee.Terrain.slope(dem).rename("slope")
    return dem.resample("bilinear").addBands(slope.resample("bilinear"))


def build_stack(geom: ee.Geometry, start: str, end: str) -> tuple[ee.Image, ee.Dictionary]:
    s2, s2_count = s2_composite(geom, start, end)
    s1, s1_info = s1_composite(geom, start, end)
    phys = s2.addBands(s1).addBands(dem_bands()).select(BAND_NAMES)

    scaled = ee.Image.cat(
        [phys.select(b.name).multiply(b.scale).round() for b in BANDS]
    ).rename(BAND_NAMES)
    # clamp first, or a real value could wrap into NODATA on the int16 cast
    stack = scaled.clamp(NODATA + 1, 32767).unmask(NODATA).toInt16()
    meta = ee.Dictionary({"s2_scenes": s2_count, "s1": s1_info})
    return stack, meta
