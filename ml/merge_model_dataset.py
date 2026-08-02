"""Build a model-ready performance + carbon dataset.

Joins the AWS EMR performance dataset and the cleaned Azure Databricks results
with regional carbon-intensity and renewable-energy features, producing
data/models/cloud_carbon_model_dataset.csv used for model training and by the
recommendation engine.

Carbon features are matched per-row where possible: rows with a real run
timestamp (currently only Azure Databricks runs) are matched to that
region's nearest daily carbon/renewable reading via `pd.merge_asof`. Rows
without a timestamp (AWS EMR runs -- this dataset never recorded one) fall
back to the region's all-time mean, which is the best available estimate
without a date to anchor to. A `carbon_feature_source` column on the output
records which path each row took.

The join is done on case-normalized cloud names because the carbon files mix
"aws" and "Azure" spellings.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

AWS_PERFORMANCE = ROOT / "data/performance/performance_dataset.csv"
AZURE_PERFORMANCE = ROOT / "data/performance/merged_azure_results_clean.csv"
CARBON_INTENSITY = ROOT / "Carbon_dataset/carbon_intensity_daily.csv"
RENEWABLE_INTENSITY = ROOT / "Carbon_dataset/renewable_intensity_daily.csv"
OUTPUT = ROOT / "data/models/cloud_carbon_model_dataset.csv"

OUTPUT_COLUMNS = [
    "cloud",
    "region",
    "run_date",
    "dataset_size_mb",
    "workload_type",
    "machine_type",
    "nodes",
    "runtime_minutes",
    "cost_usd",
    "cpu_avg_pct",
    "memory_avg_pct",
]

AZURE_REGION_MAP = {
    "centralindia": "Central India",
    "southeastasia": "Southeast Asia",
}

# Zones that are coarser than the deployment region. If these appear in the
# carbon files it means the data was collected before the zone fix in
# Carbon_dataset/zones.py and every emission figure derived from it will be
# wrong. See Carbon_dataset/zones.py for the reasoning.
COARSE_ZONES = {"IN": "IN-WE"}


def check_zone_granularity(merged: pd.DataFrame) -> None:
    """Warn loudly if the carbon data still uses a national-average zone."""
    if "electricity_zone" not in merged.columns:
        return
    present = set(merged["electricity_zone"].dropna().astype(str).unique())
    stale = present & COARSE_ZONES.keys()
    if not stale:
        return
    for zone in sorted(stale):
        affected = int(merged["electricity_zone"].eq(zone).sum())
        print(
            f"\nWARNING: {affected} rows use electricity zone '{zone}', which is a "
            f"national average. Re-run Carbon_dataset/carbon_collect.py and "
            f"renewable_collect.py to collect '{COARSE_ZONES[zone]}' instead, then "
            f"re-run this merge. Carbon results from this dataset are not "
            f"publishable until that is done.\n"
        )


def normalize_workload(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"cpu", "memory", "io"}:
        return f"{text}-heavy"
    return text


def load_aws_performance(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, on_bad_lines="warn")
    # Accept the legacy column name in case older rows/files use it.
    if "machine_type" not in data.columns and "instance_type" in data.columns:
        data = data.rename(columns={"instance_type": "machine_type"})
    if "region" not in data.columns:
        raise ValueError("AWS performance dataset must include a region column.")

    data["cloud"] = "AWS"
    data["region"] = data["region"].astype(str).str.strip()
    data["workload_type"] = data["workload_type"].apply(normalize_workload)
    data["run_date"] = pd.NaT
    for optional in ("cpu_avg_pct", "memory_avg_pct"):
        if optional not in data.columns:
            data[optional] = pd.NA
    return data[OUTPUT_COLUMNS]


def load_azure_performance(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    if "Exit_Status" in data.columns:
        data = data[data["Exit_Status"].eq("SUCCESS")].copy()

    data["cloud"] = "Azure"
    region = data["region"].astype(str).str.strip().str.lower()
    data["region"] = region.map(AZURE_REGION_MAP).fillna(data["region"])
    data["run_date"] = pd.to_datetime(data["Timestamp"], utc=True, errors="coerce").dt.date
    data["workload_type"] = data["workload_type"].apply(normalize_workload)
    if "memory_avg_pct" not in data.columns:
        data["memory_avg_pct"] = pd.NA
    return data[OUTPUT_COLUMNS]


def load_daily_carbon(carbon_path: Path, renewable_path: Path) -> pd.DataFrame:
    """Return the raw daily carbon+renewable table (not aggregated), sorted
    by timestamp, for nearest-date matching against rows with a real
    run_date."""
    carbon = pd.read_csv(carbon_path)
    renewable = pd.read_csv(renewable_path)

    # Pin both to the same datetime64 resolution: pandas >= 2.x can infer
    # different resolutions (e.g. seconds vs microseconds) for columns
    # parsed from different-looking date strings, and pd.merge_asof requires
    # its "on" key to match exactly, not just be tz-aware, on both sides.
    carbon["timestamp"] = pd.to_datetime(carbon["Date"], utc=True).astype("datetime64[ns, UTC]")
    renewable["timestamp"] = pd.to_datetime(renewable["Date"], utc=True).astype("datetime64[ns, UTC]")

    daily = carbon.merge(
        renewable,
        on=["timestamp", "Cloud", "Region", "Electricity_Zone"],
        how="inner",
        suffixes=("_carbon", "_renewable"),
    ).rename(
        columns={
            "Carbon_Intensity_gCO2eq_per_kWh": "carbon_intensity",
            "Renewable_Percentage": "renewable_percentage",
            "Electricity_Zone": "electricity_zone",
        }
    )
    daily["cloud_key"] = daily["Cloud"].astype(str).str.strip().str.lower()
    daily["region_key"] = daily["Region"].astype(str).str.strip().str.lower()
    return daily[
        ["timestamp", "cloud_key", "region_key", "electricity_zone", "carbon_intensity", "renewable_percentage"]
    ].sort_values("timestamp")


def load_carbon_features(carbon_path: Path, renewable_path: Path) -> pd.DataFrame:
    """Region-level mean/min/max carbon and renewable features, used as the
    fallback for rows that have no run_date to match against."""
    carbon = pd.read_csv(carbon_path)
    renewable = pd.read_csv(renewable_path)

    carbon["date"] = pd.to_datetime(carbon["Date"], utc=True).dt.date
    renewable["date"] = pd.to_datetime(renewable["Date"], utc=True).dt.date

    daily = carbon.merge(
        renewable,
        on=["date", "Cloud", "Region", "Electricity_Zone"],
        how="inner",
        suffixes=("_carbon", "_renewable"),
    )

    features = (
        daily.groupby(["Cloud", "Region", "Electricity_Zone"], as_index=False)
        .agg(
            carbon_intensity_mean=("Carbon_Intensity_gCO2eq_per_kWh", "mean"),
            carbon_intensity_min=("Carbon_Intensity_gCO2eq_per_kWh", "min"),
            carbon_intensity_max=("Carbon_Intensity_gCO2eq_per_kWh", "max"),
            renewable_percentage_mean=("Renewable_Percentage", "mean"),
            renewable_percentage_min=("Renewable_Percentage", "min"),
            renewable_percentage_max=("Renewable_Percentage", "max"),
            carbon_days_available=("date", "nunique"),
        )
        .rename(
            columns={
                "Cloud": "cloud",
                "Region": "region",
                "Electricity_Zone": "electricity_zone",
            }
        )
    )
    # The carbon files mix cloud spellings ("aws" vs "Azure"), so build
    # case-insensitive join keys instead of merging on the raw values.
    features["cloud_key"] = features["cloud"].astype(str).str.strip().str.lower()
    features["region_key"] = features["region"].astype(str).str.strip().str.lower()
    return features.drop(columns=["cloud", "region"])


def attach_carbon_features(
    performance: pd.DataFrame,
    daily: pd.DataFrame,
    regional_means: pd.DataFrame,
) -> pd.DataFrame:
    """Attach carbon/renewable features to each performance row.

    Rows with a real run_date are matched to that region's nearest daily
    carbon reading via `pd.merge_asof`. Rows without one fall back to the
    region's all-time mean.
    """
    performance = performance.reset_index(drop=True)
    # Must match `daily["timestamp"]`'s resolution exactly (see the comment
    # in load_daily_carbon) or pd.merge_asof raises a MergeError.
    performance["run_timestamp"] = (
        pd.to_datetime(performance["run_date"], utc=True, errors="coerce").astype("datetime64[ns, UTC]")
    )

    has_date = performance["run_timestamp"].notna()
    dated = performance.loc[has_date].sort_values("run_timestamp").copy()
    undated = performance.loc[~has_date].copy()

    placeholder_columns = [
        "carbon_intensity_min",
        "carbon_intensity_max",
        "renewable_percentage_min",
        "renewable_percentage_max",
    ]

    if not dated.empty:
        matched = pd.merge_asof(
            dated,
            daily,
            left_on="run_timestamp",
            right_on="timestamp",
            by=["cloud_key", "region_key"],
            direction="nearest",
        )
        matched["carbon_intensity_mean"] = matched["carbon_intensity"]
        matched["renewable_percentage_mean"] = matched["renewable_percentage"]
        for column in placeholder_columns:
            matched[column] = pd.NA
        matched["carbon_days_available"] = 1
        matched["carbon_feature_source"] = "nearest_daily_reading"
        matched = matched.drop(columns=["timestamp", "carbon_intensity", "renewable_percentage"])
    else:
        matched = dated
        for column in ["electricity_zone", "carbon_intensity_mean", "renewable_percentage_mean", *placeholder_columns, "carbon_days_available"]:
            matched[column] = pd.NA
        matched["carbon_feature_source"] = "nearest_daily_reading"

    undated = undated.merge(regional_means, on=["cloud_key", "region_key"], how="left")
    undated["carbon_feature_source"] = "regional_mean"

    combined = pd.concat([matched, undated], ignore_index=True)
    return combined.drop(columns=["run_timestamp"], errors="ignore")


def build_dataset(output_path: Path) -> pd.DataFrame:
    aws = load_aws_performance(AWS_PERFORMANCE)
    azure = load_azure_performance(AZURE_PERFORMANCE)
    performance = pd.concat([aws, azure], ignore_index=True)
    performance["cloud_key"] = performance["cloud"].str.lower()
    performance["region_key"] = performance["region"].astype(str).str.strip().str.lower()

    regional_means = load_carbon_features(CARBON_INTENSITY, RENEWABLE_INTENSITY)
    daily = load_daily_carbon(CARBON_INTENSITY, RENEWABLE_INTENSITY)
    merged = attach_carbon_features(performance, daily, regional_means)
    merged = merged.drop(columns=["cloud_key", "region_key"], errors="ignore")

    merged["estimated_emissions_gco2eq"] = (
        merged["runtime_minutes"] / 60
    ) * merged["carbon_intensity_mean"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    check_zone_granularity(merged)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge performance, carbon, and renewable datasets.")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    merged = build_dataset(Path(args.output))
    print(f"Wrote {len(merged)} rows to {args.output}")
    print("Missing carbon rows:", int(merged["carbon_intensity_mean"].isna().sum()))
    print("Rows by cloud:")
    print(merged["cloud"].value_counts().to_string())
    print("Rows by carbon feature source:")
    print(merged["carbon_feature_source"].value_counts().to_string())


if __name__ == "__main__":
    main()
