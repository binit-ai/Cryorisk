from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import shapely
from pyproj import Transformer
from shapely.geometry import shape


# One fixed grid per AOI. Stacks, labels, predictions and velocity all share it,
# so IoU and image pairs never need resampling.
@dataclass(frozen=True)
class Grid:
    crs: str
    x0: float  # upper-left corner
    y0: float
    res: float
    width: int
    height: int

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.x0, self.y0 - self.height * self.res, self.x0 + self.width * self.res, self.y0

    @property
    def crs_transform(self) -> list[float]:
        # EE order: [xScale, xShear, xOff, yShear, yScale, yOff]
        return [self.res, 0, self.x0, 0, -self.res, self.y0]

    def rasterio_transform(self):
        from rasterio.transform import from_origin

        return from_origin(self.x0, self.y0, self.res, self.res)

    def subgrid(self, row: int, col: int, h: int, w: int) -> Grid:
        h = min(h, self.height - row)
        w = min(w, self.width - col)
        return Grid(self.crs, self.x0 + col * self.res, self.y0 - row * self.res, self.res, w, h)

    def to_dict(self) -> dict:
        return asdict(self)


def load_polygon(geojson_path: Path):
    with open(geojson_path) as f:
        fc = json.load(f)
    return shape(fc["features"][0]["geometry"])


def aoi_grid(polygon_wgs84, crs: str, res: float, buffer_m: float) -> Grid:
    # Buffer in metres (UTM), not degrees, then snap outward to whole pixels so every
    # year lands on exactly the same pixel edges.
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    poly = shapely.transform(polygon_wgs84, to_utm, interleaved=False).buffer(buffer_m)
    minx, miny, maxx, maxy = poly.bounds
    x0 = math.floor(minx / res) * res
    x1 = math.ceil(maxx / res) * res
    y0 = math.floor(miny / res) * res
    y1 = math.ceil(maxy / res) * res
    return Grid(
        crs=crs,
        x0=x0,
        y0=y1,
        res=res,
        width=round((x1 - x0) / res),
        height=round((y1 - y0) / res),
    )
