
import argparse
import ee


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        required=True,
        help="Your GEE Cloud Project ID",
    )
    args = parser.parse_args()

    print("Starting Earth Engine authentication...")
    print("A browser window should open. Log in and approve access.")
    ee.Authenticate()

    print(f"Initializing Earth Engine with project: {args.project}")
    ee.Initialize(project=args.project)

    print("Earth Engine authenticated and initialized successfully.")


if __name__ == "__main__":
    main()