"""Generate EDA tables and charts for the EMR performance dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.express as px


REQUIRED_COLUMNS = [
    "dataset_size_mb",
    "workload_type",
    "instance_type",
    "nodes",
    "runtime_minutes",
    "cost_usd",
]


def validate(data: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def write_chart(fig, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")


def generate_eda(input_path: str, output_dir: str) -> dict:
    data = pd.read_csv(input_path)
    validate(data)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    summary = {
        "rows": int(len(data)),
        "dataset_sizes_mb": sorted(data["dataset_size_mb"].dropna().unique().tolist()),
        "workloads": sorted(data["workload_type"].dropna().unique().tolist()),
        "instance_types": sorted(data["instance_type"].dropna().unique().tolist()),
        "node_counts": sorted(data["nodes"].dropna().unique().tolist()),
        "runtime_minutes": {
            "min": round(float(data["runtime_minutes"].min()), 4),
            "mean": round(float(data["runtime_minutes"].mean()), 4),
            "max": round(float(data["runtime_minutes"].max()), 4),
        },
        "cost_usd": {
            "min": round(float(data["cost_usd"].min()), 6),
            "mean": round(float(data["cost_usd"].mean()), 6),
            "max": round(float(data["cost_usd"].max()), 6),
        },
    }

    data.describe(include="all").to_csv(output / "descriptive_statistics.csv")
    (
        data.groupby(["dataset_size_mb", "workload_type", "instance_type", "nodes"], as_index=False)
        .agg(runtime_mean=("runtime_minutes", "mean"), cost_mean=("cost_usd", "mean"), runs=("runtime_minutes", "count"))
        .to_csv(output / "grouped_summary.csv", index=False)
    )

    with open(output / "eda_summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    write_chart(
        px.line(
            data.sort_values("dataset_size_mb"),
            x="dataset_size_mb",
            y="runtime_minutes",
            color="workload_type",
            line_dash="instance_type",
            markers=True,
            facet_col="nodes",
            labels={"dataset_size_mb": "Dataset size (MB)", "runtime_minutes": "Runtime (minutes)"},
        ),
        output / "runtime_vs_dataset_size.html",
    )
    write_chart(
        px.scatter(
            data,
            x="runtime_minutes",
            y="cost_usd",
            color="workload_type",
            symbol="instance_type",
            size="dataset_size_mb",
            hover_data=["nodes"],
            labels={"runtime_minutes": "Runtime (minutes)", "cost_usd": "Cost (USD)"},
        ),
        output / "cost_vs_runtime.html",
    )
    write_chart(
        px.box(
            data,
            x="workload_type",
            y="runtime_minutes",
            color="instance_type",
            labels={"workload_type": "Workload", "runtime_minutes": "Runtime (minutes)"},
        ),
        output / "runtime_distribution_by_workload.html",
    )
    write_chart(
        px.bar(
            data.groupby(["workload_type", "instance_type"], as_index=False)["cost_usd"].mean(),
            x="workload_type",
            y="cost_usd",
            color="instance_type",
            barmode="group",
            labels={"workload_type": "Workload", "cost_usd": "Average cost (USD)"},
        ),
        output / "average_cost_by_workload.html",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate EDA tables and HTML charts.")
    parser.add_argument("--input", default="data/performance/cleaned_data/cleaned_dataset.csv")
    parser.add_argument("--output-dir", default="data/eda")
    args = parser.parse_args()
    print(json.dumps(generate_eda(args.input, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
