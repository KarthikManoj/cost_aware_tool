import requests
import pandas as pd

# ==========================
# Configuration
# ==========================

API_KEY = "em_SCn8DHnATtKKQsDGAssm4qzYD2WrE69j"

HEADERS = {
    "auth-token": API_KEY
}

START_DATE = "2025-11-01T00:00:00Z"
END_DATE = "2026-07-15T00:00:00Z"

REGIONS = [
    ("AWS", "ap-south-1", "IN"),
    ("AWS", "ap-southeast-1", "SG"),
    ("Azure", "Central India", "IN"),
    ("Azure", "Southeast Asia", "SG")
]

BASE_URL = "https://api.electricitymaps.com/v3/renewable-energy/past-range"

# ==========================
# Fetch data
# ==========================

zone_cache = {}
rows = []

for cloud, region, zone in REGIONS:

    # Fetch each electricity zone only once
    if zone not in zone_cache:

        params = {
            "zone": zone,
            "start": START_DATE,
            "end": END_DATE,
            "temporalGranularity": "daily"
        }

        print(f"\nFetching data for zone: {zone}")

        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            params=params
        )

        print("Status Code:", response.status_code)

        response.raise_for_status()

        json_data = response.json()

        if "data" not in json_data:
            raise Exception(
                f"No data returned for zone '{zone}'.\nResponse:\n{json_data}"
            )

        zone_cache[zone] = json_data["data"]
        print(json_data["data"][0])

        print(f"Retrieved {len(zone_cache[zone])} daily records.")

    # Map the zone data to each cloud region
    for item in zone_cache[zone]:

        rows.append({
    "Date": item["datetime"],
    "Cloud": cloud,
    "Region": region,
    "Electricity_Zone": zone,
    "Renewable_Percentage": item["value"],
    "Unit": item["unit"],
    "Is_Estimated": item["isEstimated"],
    "Estimation_Method": item.get("estimationMethod"),
    "Created_At": item["createdAt"],
    "Updated_At": item["updatedAt"]
})

# ==========================
# Save CSV
# ==========================

df = pd.DataFrame(rows)

df.sort_values(
    by=["Cloud", "Region", "Date"],
    inplace=True
)

output_file = "renewable_intensity_daily.csv"

df.to_csv(output_file, index=False)

print("\n====================================")
print("Carbon dataset successfully created!")
print("====================================")
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")
print(f"Output File: {output_file}")
print("\nPreview:")
print(df.head())