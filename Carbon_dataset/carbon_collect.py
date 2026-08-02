"""Fetch daily carbon-intensity data from ElectricityMaps for each cloud region.

Requires an ElectricityMaps API key. Set it as an environment variable
rather than hardcoding it in this file:

    export ELECTRICITYMAPS_API_KEY="your-key-here"
    python Carbon_dataset/carbon_collect.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from zones import REGIONS, validate_regions

BASE_URL = "https://api.electricitymaps.com/v4/carbon-intensity/past-range"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "carbon_intensity_daily.csv"


def fetch(start_date: str, end_date: str, api_key: str) -> pd.DataFrame:
    headers = {"auth-token": api_key}
    zone_cache: dict[str, list[dict]] = {}
    rows: list[dict] = []

    for cloud, region, zone in REGIONS:
        if zone not in zone_cache:
            params = {
                "zone": zone,
                "start": start_date,
                "end": end_date,
                "temporalGranularity": "daily",
            }
            print(f"\nFetching data for zone: {zone}")

            response = requests.get(BASE_URL, headers=headers, params=params)
            print("Status Code:", response.status_code)
            response.raise_for_status()

            json_data = response.json()
            if "data" not in json_data:
                raise RuntimeError(f"No data returned for zone '{zone}'.\nResponse:\n{json_data}")

            zone_cache[zone] = json_data["data"]
            print(f"Retrieved {len(zone_cache[zone])} daily records.")

        for item in zone_cache[zone]:
            rows.append(
                {
                    "Date": item["datetime"],
                    "Cloud": cloud,
                    "Region": region,
                    "Electricity_Zone": zone,
                    "Carbon_Intensity_gCO2eq_per_kWh": item["carbonIntensity"],
                    "Emission_Factor_Type": item.get("emissionFactorType"),
                    "Is_Estimated": item.get("isEstimated"),
                    "Estimation_Method": item.get("estimationMethod"),
                    "Created_At": item.get("createdAt"),
                    "Updated_At": item.get("updatedAt"),
                }
            )

    return pd.DataFrame(rows).sort_values(by=["Cloud", "Region", "Date"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily carbon intensity from ElectricityMaps.")
    parser.add_argument("--start", default="2025-11-01T00:00:00Z")
    parser.add_argument("--end", default="2026-07-15T00:00:00Z")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    api_key = os.environ.get("ELECTRICITYMAPS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Set ELECTRICITYMAPS_API_KEY before running this script "
            "(never hardcode API keys in source files)."
        )

    validate_regions()
    df = fetch(args.start, args.end, api_key)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print("\n====================================")
    print("Carbon dataset successfully created!")
    print("====================================")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Output File: {output_path}")
    print("\nPreview:")
    print(df.head())


if __name__ == "__main__":
    main()
