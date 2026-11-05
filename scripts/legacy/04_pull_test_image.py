import argparse
import os
import ee
import geemap
import numpy as np
import rasterio
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="Your GEE Cloud Project ID")
    parser.add_argument("--year", default="2023", help="Year to pull a test image from")
    args = parser.parse_args()

    ee.Initialize(project=args.project)

    ngozumpa_bbox = ee.Geometry.Rectangle([86.55, 27.85, 86.85, 28.05])
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(output_dir, exist_ok=True)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(ngozumpa_bbox)
        .filterDate(f"{args.year}-01-01", f"{args.year}-12-31")
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    count = collection.size().getInfo()
    if count == 0:
        print(f"No images found for {args.year}. Try a different year.")
        return

    print(f"Found {count} candidate images for {args.year}. Using the clearest one.")

    image = collection.first()
    date = image.date().format("YYYY-MM-dd").getInfo()
    cloud_pct = image.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    print(f"Selected image date: {date}, cloud cover: {cloud_pct:.1f}%")

    vis_params = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
    clipped = image.clip(ngozumpa_bbox)

    tif_path = os.path.join(output_dir, f"ngozumpa_test_{date}.tif")
    print(f"Downloading GeoTIFF to: {tif_path}")

    geemap.ee_export_image(
        clipped.visualize(**vis_params),
        filename=tif_path,
        scale=10,
        region=ngozumpa_bbox,
        file_per_band=False,
    )

    # Convert to a normal viewable PNG
    print("Converting to PNG for easy viewing...")
    with rasterio.open(tif_path) as src:
        arr = src.read()  # shape: (bands, height, width)
        arr = np.transpose(arr, (1, 2, 0))  # -> (height, width, bands)
        arr = arr[:, :, :3]  # keep RGB only
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    png_path = os.path.join(output_dir, f"ngozumpa_test_{date}.png")
    Image.fromarray(arr).save(png_path)

    print(f"\nDone. Open this PNG to see the glacier: {png_path}")


if __name__ == "__main__":
    main()