import pytest
from shapely.geometry import box

from cryorisk.data.grid import Grid, aoi_grid


@pytest.fixture
def poly():
    # ~ Ngozumpa area, lon/lat
    return box(86.66, 27.95, 86.72, 28.08)


def test_grid_snapped_and_covers_buffered_polygon(poly):
    g = aoi_grid(poly, "EPSG:32645", 10, 1500)
    assert g.x0 % 10 == 0 and g.y0 % 10 == 0
    minx, miny, maxx, maxy = g.bounds
    assert maxx - minx == g.width * 10 and maxy - miny == g.height * 10

    import shapely
    from pyproj import Transformer

    to_utm = Transformer.from_crs(4326, 32645, always_xy=True).transform
    utm = shapely.transform(poly, to_utm, interleaved=False)
    bminx, bminy, bmaxx, bmaxy = utm.buffer(1500).bounds
    assert minx <= bminx and miny <= bminy and maxx >= bmaxx and maxy >= bmaxy
    # snapping adds at most one pixel per side
    assert minx > bminx - 10 and maxy < bmaxy + 10


def test_grid_is_deterministic(poly):
    assert aoi_grid(poly, "EPSG:32645", 10, 1500) == aoi_grid(poly, "EPSG:32645", 10, 1500)


def test_subgrid_tiles_cover_grid_exactly():
    g = Grid("EPSG:32645", 400000, 3100000, 10, 1100, 700)
    covered = 0
    for r in range(0, g.height, 512):
        for c in range(0, g.width, 512):
            s = g.subgrid(r, c, 512, 512)
            assert s.x0 == g.x0 + c * 10 and s.y0 == g.y0 - r * 10
            covered += s.width * s.height
    assert covered == g.width * g.height


def test_crs_transform_matches_rasterio():
    g = Grid("EPSG:32645", 400000, 3100000, 10, 5, 5)
    t = g.rasterio_transform()
    assert [t.a, t.b, t.c, t.d, t.e, t.f] == g.crs_transform
