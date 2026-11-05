from __future__ import annotations

from pathlib import Path

import numpy as np

from cryorisk.gee.stack import BANDS, NODATA


def stack_report(path: Path) -> list[dict]:
    import rasterio

    rows = []
    with rasterio.open(path) as src:
        data = src.read()
        for b, arr in zip(BANDS, data, strict=True):
            valid = arr != NODATA
            phys = arr[valid].astype(np.float32) / b.scale
            empty = phys.size == 0
            rows.append(
                {
                    "band": b.name,
                    "unit": b.unit,
                    "valid_pct": 100.0 * valid.mean(),
                    "min": float("nan") if empty else float(phys.min()),
                    "median": float("nan") if empty else float(np.median(phys)),
                    "max": float("nan") if empty else float(phys.max()),
                }
            )
    return rows
