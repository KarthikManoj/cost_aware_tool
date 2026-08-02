from __future__ import annotations

import pandas as pd
import pytest

from ml.merge_model_dataset import attach_carbon_features, normalize_workload


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("cpu", "cpu-heavy"),
        ("CPU", "cpu-heavy"),
        ("memory", "memory-heavy"),
        ("io", "io-heavy"),
        ("cpu-heavy", "cpu-heavy"),
    ],
)
def test_normalize_workload(raw: str, expected: str) -> None:
    assert normalize_workload(raw) == expected


def _performance_row(**overrides) -> dict:
    row = {
        "cloud": "AWS",
        "region": "ap-south-1",
        "run_date": pd.NaT,
        "dataset_size_mb": 100,
        "workload_type": "cpu-heavy",
        "machine_type": "m5.xlarge",
        "nodes": 2,
        "runtime_minutes": 1.0,
        "cost_usd": 0.01,
        "cpu_avg_pct": None,
        "memory_avg_pct": None,
        "cloud_key": "aws",
        "region_key": "ap-south-1",
    }
    row.update(overrides)
    return row


def test_dated_row_uses_nearest_daily_reading_not_flat_mean() -> None:
    """Regression test for the carbon-join fix: a row with a real run_date
    should pick up that day's actual carbon reading, not the all-time
    regional mean (which is deliberately set far away here to make a bug
    obvious if the fallback path is used by mistake)."""
    performance = pd.DataFrame(
        [
            _performance_row(
                cloud="Azure",
                region="Central India",
                cloud_key="azure",
                region_key="central india",
                run_date=pd.Timestamp("2025-11-05", tz="UTC").date(),
            )
        ]
    )
    daily = pd.DataFrame(
        {
            # Must match the datetime64 resolution attach_carbon_features casts
            # run_timestamp to, or pd.merge_asof raises a MergeError (this is
            # what load_daily_carbon does for real in production).
            "timestamp": pd.to_datetime(
                ["2025-11-01", "2025-11-05", "2025-11-10"], utc=True
            ).astype("datetime64[ns, UTC]"),
            "cloud_key": ["azure"] * 3,
            "region_key": ["central india"] * 3,
            "electricity_zone": ["IN"] * 3,
            "carbon_intensity": [400.0, 450.0, 500.0],
            "renewable_percentage": [20.0, 25.0, 30.0],
        }
    )
    regional_means = pd.DataFrame(
        {
            "electricity_zone": ["IN"],
            "carbon_intensity_mean": [1000.0],  # deliberately far from any daily value
            "carbon_intensity_min": [400.0],
            "carbon_intensity_max": [500.0],
            "renewable_percentage_mean": [25.0],
            "renewable_percentage_min": [20.0],
            "renewable_percentage_max": [30.0],
            "carbon_days_available": [3],
            "cloud_key": ["azure"],
            "region_key": ["central india"],
        }
    )

    result = attach_carbon_features(performance, daily, regional_means)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["carbon_intensity_mean"] == pytest.approx(450.0)
    assert row["renewable_percentage_mean"] == pytest.approx(25.0)
    assert row["carbon_feature_source"] == "nearest_daily_reading"


def test_dated_row_picks_nearest_when_no_exact_match() -> None:
    performance = pd.DataFrame(
        [
            _performance_row(
                cloud="Azure",
                region="Central India",
                cloud_key="azure",
                region_key="central india",
                run_date=pd.Timestamp("2025-11-04", tz="UTC").date(),  # 3 days from 11-01, 1 day from 11-05
            )
        ]
    )
    daily = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2025-11-01", "2025-11-05"], utc=True).astype(
                "datetime64[ns, UTC]"
            ),
            "cloud_key": ["azure"] * 2,
            "region_key": ["central india"] * 2,
            "electricity_zone": ["IN"] * 2,
            "carbon_intensity": [400.0, 450.0],
            "renewable_percentage": [20.0, 25.0],
        }
    )
    regional_means = pd.DataFrame(
        {
            "electricity_zone": ["IN"],
            "carbon_intensity_mean": [1000.0],
            "carbon_intensity_min": [400.0],
            "carbon_intensity_max": [450.0],
            "renewable_percentage_mean": [22.5],
            "renewable_percentage_min": [20.0],
            "renewable_percentage_max": [25.0],
            "carbon_days_available": [2],
            "cloud_key": ["azure"],
            "region_key": ["central india"],
        }
    )

    result = attach_carbon_features(performance, daily, regional_means)

    assert result.iloc[0]["carbon_intensity_mean"] == pytest.approx(450.0)


def test_undated_row_falls_back_to_regional_mean() -> None:
    """AWS rows have no run_date in this dataset, so they must keep using
    the region's all-time mean carbon intensity."""
    performance = pd.DataFrame([_performance_row()])  # run_date is NaT
    daily = pd.DataFrame(
        columns=[
            "timestamp",
            "cloud_key",
            "region_key",
            "electricity_zone",
            "carbon_intensity",
            "renewable_percentage",
        ]
    )
    regional_means = pd.DataFrame(
        {
            "electricity_zone": ["IN"],
            "carbon_intensity_mean": [605.2],
            "carbon_intensity_min": [521.0],
            "carbon_intensity_max": [660.0],
            "renewable_percentage_mean": [23.9],
            "renewable_percentage_min": [17.0],
            "renewable_percentage_max": [35.0],
            "carbon_days_available": [256],
            "cloud_key": ["aws"],
            "region_key": ["ap-south-1"],
        }
    )

    result = attach_carbon_features(performance, daily, regional_means)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["carbon_intensity_mean"] == pytest.approx(605.2)
    assert row["carbon_feature_source"] == "regional_mean"
