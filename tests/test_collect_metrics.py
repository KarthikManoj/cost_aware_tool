from __future__ import annotations

import csv
from pathlib import Path

import pytest

from metrics.collect_metrics import (
    ExperimentMetric,
    append_metric,
    calculate_cost,
    zone_for_region,
)


@pytest.fixture
def price_csv(tmp_path: Path) -> Path:
    path = tmp_path / "instance_prices.csv"
    path.write_text(
        "instance_type,hourly_price_usd,category,vcpus,memory_gb\n"
        "m5.xlarge,0.192,general,4,16\n"
    )
    return path


def test_calculate_cost_matches_hand_computation(price_csv: Path) -> None:
    # 2 nodes * $0.192/hr * (30 min / 60) = $0.192
    cost = calculate_cost("m5.xlarge", nodes=2, runtime_minutes=30, price_path=str(price_csv))
    assert cost == pytest.approx(0.192, abs=1e-6)


def test_calculate_cost_missing_instance_raises(price_csv: Path) -> None:
    with pytest.raises(ValueError, match="No hourly price configured"):
        calculate_cost("c5.xlarge", nodes=2, runtime_minutes=30, price_path=str(price_csv))


@pytest.mark.parametrize(
    "region, expected_zone",
    [
        ("ap-south-1", "IN"),
        ("AP-SOUTH-1", "IN"),
        ("ap-southeast-1", "SG"),
        ("eu-west-1", ""),
    ],
)
def test_zone_for_region(region: str, expected_zone: str) -> None:
    assert zone_for_region(region) == expected_zone


def test_append_metric_writes_header_once_and_matches_live_schema(tmp_path: Path) -> None:
    """Written rows must match the live CSV schema, not drift from it."""
    output = tmp_path / "performance_dataset.csv"
    metric = ExperimentMetric(
        dataset_size_mb=100,
        workload_type="cpu-heavy",
        machine_type="m5.xlarge",
        nodes=2,
        runtime_minutes=1.5,
        cost_usd=0.01,
        region="ap-south-1",
        source="unit-test",
        cloud="aws",
        electricity_zone="IN",
    )
    append_metric(metric, str(output))
    append_metric(metric, str(output))

    with open(output, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == [
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
    assert len(rows) == 3  # header + 2 appended rows
