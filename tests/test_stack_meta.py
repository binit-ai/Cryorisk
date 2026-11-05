from cryorisk.cli import _parse_years
from cryorisk.gee.stack import BAND_NAMES, BANDS, NODATA


def test_twelve_unique_bands_in_design_order():
    assert BAND_NAMES == [
        "B2", "B3", "B4", "B8", "B11", "B12", "NDSI", "NDWI", "VV", "VH", "elevation", "slope",
    ]


def test_scaled_physical_ranges_fit_int16():
    # worst-case physical ranges per unit -> must fit int16 without hitting NODATA
    ranges = {"reflectance": 2.0, "index": 1.0, "dB": 30.0, "m": 9000.0, "deg": 90.0}
    for b in BANDS:
        assert ranges[b.unit] * b.scale < 32767
        assert -ranges[b.unit] * b.scale > NODATA


def test_parse_years():
    assert _parse_years("2023", [1]) == [2023]
    assert _parse_years("2016-2018", [1]) == [2016, 2017, 2018]
    assert _parse_years("2018,2020", [1]) == [2018, 2020]
    assert _parse_years(None, [7]) == [7]
