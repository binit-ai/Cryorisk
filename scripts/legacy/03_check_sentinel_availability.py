import argparse
import ee

MAX_CLOUD_PERCENT = 30
START_DATE = "2016-01-01"
END_DATE = "2026-01-01"


def check_sentinel2(region):
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT))
    )
    count = s2.size().getInfo()
    print(f"Sentinel-2 (optical) images with <{MAX_CLOUD_PERCENT}% cloud cover: {count}")

    print("\nYear-by-year breakdown (Sentinel-2):")
    for year in range(2016, 2026):
        yearly = s2.filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        n = yearly.size().getInfo()
        print(f"  {year}: {n} images")

    return count


def check_sentinel1(region):
    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(START_DATE, END_DATE)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )
    count = s1.size().getInfo()
    print(f"\nSentinel-1 (SAR) images available: {count}")

    print("\nYear-by-year breakdown (Sentinel-1):")
    for year in range(2016, 2026):
        yearly = s1.filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        n = yearly.size().getInfo()
        print(f"  {year}: {n} images")

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="Your GEE Cloud Project ID")
    args = parser.parse_args()

    ee.Initialize(project=args.project)

    # Created AFTER Initialize — this was the bug
    ngozumpa_bbox = ee.Geometry.Rectangle([86.55, 27.85, 86.85, 28.05])

    print("Checking imagery availability for Ngozumpa Glacier area")
    print(f"Date range: {START_DATE} to {END_DATE}\n")

    s2_count = check_sentinel2(ngozumpa_bbox)
    s1_count = check_sentinel1(ngozumpa_bbox)

    print("\n--- Summary ---")
    print(f"Total usable Sentinel-2 images: {s2_count}")
    print(f"Total Sentinel-1 images: {s1_count}")


if __name__ == "__main__":
    main()