"""Build a model-ready performance + carbon dataset.

The carbon and renewable files are daily, but some performance rows do not
have a run timestamp. For the first model dataset, this script joins regional
carbon features aggregated by cloud and region.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

AWS_PERFORMANCE = ROOT / "data/performance/performance_dataset.csv"
AZURE_PERFORMANCE = ROOT / "data/performance/azure_performance_data.csv"
CARBON_INTENSITY = ROOT / "Carbon_dataset/carbon_intensity_daily.csv"
RENEWABLE_INTENSITY = ROOT / "Carbon_dataset/renewable_intensity_daily.csv"
OUTPUT = ROOT / "data/models/cloud_carbon_model_dataset.csv"


AZURE_REGION_MAP = {
    "centralindia": "Central India",
    "southeastasia": "Southeast Asia",
}



def normalize_workload(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"cpu", "memory", "io"}:
        return f"{text}-heavy"
    return text


def load_aws_performance(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, on_bad_lines="warn")
    if "region" not in data.columns:
        raise ValueError("AWS performance dataset must include a region column.")
    data = data.rename(
        columns={
            "dataset_size_mb": "dataset_size_mb",
            "workload_type": "workload_type",
            "instance_type": "machine_type",
            "nodes": "nodes",
            "runtime_minutes": "runtime_minutes",
            "cost_usd": "cost_usd",
            "cpu_avg_pct": "cpu_avg_pct",
            "memory_avg_pct": "memory_avg_pct",
        }
    )
    data["cloud"] = "AWS"
    data["region"] = data["region"].astype(str).str.strip()
    data["workload_type"] = data["workload_type"].apply(normalize_workload)
    data["run_date"] = pd.NaT
    return data[
        [
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
    ]


def load_azure_performance(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    data = data[data["Exit_Status"].eq("SUCCESS")].copy()
    data["cloud"] = "Azure"
    data["region"] = data["Region"].map(AZURE_REGION_MAP).fillna(data["Region"])
    data["run_date"] = pd.to_datetime(data["Timestamp"], utc=True).dt.date
    data["workload_type"] = data["Workload"].apply(normalize_workload)
    data = data.rename(
        columns={
            "Dataset_Size_MB": "dataset_size_mb",
            "VM_Size": "machine_type",
            "Nodes": "nodes",
            "Runtime_Minutes": "runtime_minutes",
            "Cost_USD": "cost_usd",
            "CPU_Avg_Pct": "cpu_avg_pct",
        }
    )
    data["memory_avg_pct"] = pd.NA
    return data[
        [
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
    ]


def load_carbon_features(carbon_path: Path, renewable_path: Path) -> pd.DataFrame:
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

    return (
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


def build_dataset(output_path: Path) -> pd.DataFrame:
    aws = load_aws_performance(AWS_PERFORMANCE)
    azure = load_azure_performance(AZURE_PERFORMANCE)
    performance = pd.concat([aws, azure], ignore_index=True)

    carbon_features = load_carbon_features(CARBON_INTENSITY, RENEWABLE_INTENSITY)
    merged = performance.merge(carbon_features, on=["cloud", "region"], how="left")

    merged["estimated_emissions_gco2eq"] = (
        merged["runtime_minutes"] / 60
    ) * merged["carbon_intensity_mean"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
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


if __name__ == "__main__":
    main()
