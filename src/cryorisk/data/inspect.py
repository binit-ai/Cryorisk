"""Quick quality report for a downloaded stack (band ranges, valid fraction)."""

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
            rows.append(
                {
                    "band": b.name,
                    "unit": b.unit,
                    "valid_pct": 100.0 * valid.mean(),
                    "min": float(phys.min()) if phys.size else float("nan"),
                    "median": float(np.median(phys)) if phys.size else float("nan"),
                    "max": float(phys.max()) if phys.size else float("nan"),
                }
            )
    return rows
