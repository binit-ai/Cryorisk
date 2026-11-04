from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import ee
import numpy as np

from cryorisk.data.grid import Grid
from cryorisk.gee.stack import BAND_NAMES, BANDS, NODATA

DRIVE_FOLDER = "cryorisk"
# computePixels caps responses at 48 MB; 512² x 12 bands x int16 is ~6 MB
TILE_PX = 512


def grid_geometry(grid: Grid) -> ee.Geometry:
    minx, miny, maxx, maxy = grid.bounds
    # geodesic=False so EE treats the edges as straight lines in UTM, matching the grid
    return ee.Geometry.Rectangle([minx, miny, maxx, maxy], proj=grid.crs, geodesic=False)


def estimated_bytes(grid: Grid) -> int:
    return grid.width * grid.height * len(BANDS) * 2


def export_to_drive(image: ee.Image, grid: Grid, name: str) -> ee.batch.Task:
    # crsTransform (not scale) pins pixel edges to our grid; scale lets EE pick its own origin
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=name,
        folder=DRIVE_FOLDER,
        fileNamePrefix=name,
        region=grid_geometry(grid),
        crs=grid.crs,
        crsTransform=grid.crs_transform,
        maxPixels=1e10,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True, "noData": NODATA},
    )
    task.start()
    return task


def _compute_tile(image: ee.Image, g: Grid, retries: int = 3) -> np.ndarray:
    request = {
        "expression": image,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": g.width, "height": g.height},
            "affineTransform": {
                "scaleX": g.res,
                "shearX": 0,
                "translateX": g.x0,
                "shearY": 0,
                "scaleY": -g.res,
                "translateY": g.y0,
            },
            "crsCode": g.crs,
        },
    }
    # EE throws intermittent 429/"computation timed out" on busy days; back off and retry
    for attempt in range(retries):
        try:
            arr = ee.data.computePixels(request)
            return np.stack([arr[b] for b in BAND_NAMES]).astype(np.int16)
        except ee.EEException:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt * 5)
    raise RuntimeError("unreachable")


def download_local(image: ee.Image, grid: Grid, out_path: Path, progress=print) -> Path:
    import rasterio

    out = np.full((len(BANDS), grid.height, grid.width), NODATA, dtype=np.int16)
    tiles = [
        (r, c) for r in range(0, grid.height, TILE_PX) for c in range(0, grid.width, TILE_PX)
    ]
    for i, (r, c) in enumerate(tiles, 1):
        sub = grid.subgrid(r, c, TILE_PX, TILE_PX)
        out[:, r : r + sub.height, c : c + sub.width] = _compute_tile(image, sub)
        progress(f"  tile {i}/{len(tiles)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "int16",
        "count": len(BANDS),
        "width": grid.width,
        "height": grid.height,
        "crs": grid.crs,
        "transform": grid.rasterio_transform(),
        "nodata": NODATA,
        "compress": "deflate",
        "predictor": 2,  # horizontal differencing; ~2x smaller on smooth DEM/reflectance
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(out)
        dst.descriptions = tuple(BAND_NAMES)
    return out_path


def write_manifest(path: Path, *, aoi: str, year: int, start: str, end: str, grid: Grid,
                   meta: dict, target: str, task_id: str | None = None) -> Path:
    params = {
        "aoi": aoi,
        "year": year,
        "start": start,
        "end": end,
        "grid": grid.to_dict(),
        "bands": [{"name": b.name, "scale": b.scale, "unit": b.unit} for b in BANDS],
        "nodata": NODATA,
    }
    manifest = {
        **params,
        # hash only the inputs, so a changed band list or grid shows up as a new version
        "params_hash": hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16],
        "scenes": meta,
        "target": target,
        "drive_folder": DRIVE_FOLDER if target == "drive" else None,
        "task_id": task_id,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))
    return path
