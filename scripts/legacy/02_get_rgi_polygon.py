import argparse
import json
import os
import ee

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RGI_ASSET = "projects/sat-io/open-datasets/RGI/RGI_VECTOR_MERGED_V7"
TARGET_RGI_ID = "RGI2000-v7.0-G-15-08305"  # Confirmed: "Ngojumba" = Ngozumpa Glacier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="Your GEE Cloud Project ID")
    args = parser.parse_args()

    ee.Initialize(project=args.project)

    ngozumpa_bbox = ee.Geometry.Rectangle([86.55, 27.85, 86.85, 28.05])
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Loading RGI v7.0 dataset from Earth Engine...")
    rgi = ee.FeatureCollection(RGI_ASSET)

    print(f"Filtering to the confirmed Ngozumpa polygon (RGI ID: {TARGET_RGI_ID})...")
    match = rgi.filter(ee.Filter.eq("rgi_id", TARGET_RGI_ID))

    count = match.size().getInfo()
    if count == 0:
        print("No exact match found — the RGI ID may differ. Check manually.")
        return

    feature = match.first().getInfo()
    props = feature["properties"]
    print(f"\nConfirmed: RGI ID {props.get('rgi_id')} | Name: {props.get('glac_name')} | Area: {props.get('area_km2')} km2")

    out_path = os.path.join(DATA_DIR, "ngozumpa_polygon.geojson")
    geojson_feature = {"type": "FeatureCollection", "features": [feature]}
    with open(out_path, "w") as f:
        json.dump(geojson_feature, f, indent=2)

    print(f"\nSaved polygon to: {out_path}")


if __name__ == "__main__":
    main()