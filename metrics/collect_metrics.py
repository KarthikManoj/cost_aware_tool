"""Build and maintain the performance dataset used for ML training.

The column order below matches the existing data/performance/performance_dataset.csv
header exactly. Do not reorder fields without migrating the CSV.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


PERFORMANCE_COLUMNS = [
    "dataset_size_mb",
    "workload_type",
    "machine_type",
    "nodes",
    "runtime_minutes",
    "cost_usd",
    "region",
    "source",
    "cloud",
    "electricity_zone",
    "cpu_avg_pct",
    "memory_avg_pct",
]

REGION_TO_ZONE = {
    "ap-south-1": "IN",
    "ap-southeast-1": "SG",
}


@dataclass(frozen=True)
class ExperimentMetric:
    dataset_size_mb: float
    workload_type: str
    machine_type: str
    nodes: int
    runtime_minutes: float
    cost_usd: float
    region: str
    source: str = "manual"
    cloud: str = "aws"
    electricity_zone: str = ""
    cpu_avg_pct: float | None = None
    memory_avg_pct: float | None = None


def zone_for_region(region: str) -> str:
    return REGION_TO_ZONE.get(region.strip().lower(), "")


def load_prices(price_path: str) -> pd.DataFrame:
    prices = pd.read_csv(price_path)
    if "instance_type" not in prices or "hourly_price_usd" not in prices:
        raise ValueError("Price file must contain instance_type and hourly_price_usd columns.")
    return prices


def calculate_cost(instance_type: str, nodes: int, runtime_minutes: float, price_path: str) -> float:
    prices = load_prices(price_path)
    row = prices.loc[prices["instance_type"] == instance_type]
    if row.empty:
        raise ValueError(f"No hourly price configured for instance type: {instance_type}")
    hourly_price = float(row.iloc[0]["hourly_price_usd"])
    return round(hourly_price * nodes * (runtime_minutes / 60.0), 6)


def append_metric(metric: ExperimentMetric, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PERFORMANCE_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(metric))


def main() -> None:
    parser = argparse.ArgumentParser(description="Append one experiment result to performance CSV.")
    parser.add_argument("--dataset-size-mb", type=float, required=True)
    parser.add_argument("--workload-type", required=True, choices=["cpu-heavy", "memory-heavy", "io-heavy"])
    parser.add_argument("--machine-type", "--instance-type", dest="machine_type", required=True)
    parser.add_argument("--nodes", type=int, required=True)
    parser.add_argument("--runtime-minutes", type=float, required=True)
    parser.add_argument("--region", required=True, help="Cloud region, e.g. ap-south-1")
    parser.add_argument("--cloud", default="aws")
    parser.add_argument("--electricity-zone", default=None, help="Defaults to the known zone for --region.")
    parser.add_argument("--cpu-avg-pct", type=float, default=None)
    parser.add_argument("--memory-avg-pct", type=float, default=None)
    parser.add_argument("--source", default="manual")
    parser.add_argument("--price-path", default="config/instance_prices.csv")
    parser.add_argument("--output", default="data/performance/performance_dataset.csv")
    args = parser.parse_args()

    cost = calculate_cost(args.machine_type, args.nodes, args.runtime_minutes, args.price_path)
    metric = ExperimentMetric(
        dataset_size_mb=args.dataset_size_mb,
        workload_type=args.workload_type,
        machine_type=args.machine_type,
        nodes=args.nodes,
        runtime_minutes=args.runtime_minutes,
        cost_usd=cost,
        region=args.region,
        source=args.source,
        cloud=args.cloud,
        electricity_zone=args.electricity_zone if args.electricity_zone is not None else zone_for_region(args.region),
        cpu_avg_pct=args.cpu_avg_pct,
        memory_avg_pct=args.memory_avg_pct,
    )
    append_metric(metric, args.output)
    print(f"Appended metric with cost ${cost:.4f} to {args.output}")


if __name__ == "__main__":
    main()
