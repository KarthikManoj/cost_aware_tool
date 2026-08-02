"""Preprocessing utilities for performance prediction models."""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = [
    "cloud",
    "region",
    "electricity_zone",
    "dataset_size_mb",
    "workload_type",
    "machine_type",
    "nodes",
    "carbon_intensity_mean",
    "renewable_percentage_mean",
]
TARGET_COLUMNS = ["runtime_minutes", "cost_usd"]
CATEGORICAL_COLUMNS = [
    "cloud",
    "region",
    "electricity_zone",
    "workload_type",
    "machine_type",
]
NUMERIC_COLUMNS = [
    "dataset_size_mb",
    "nodes",
    "carbon_intensity_mean",
    "renewable_percentage_mean",
]


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_COLUMNS,
            ),
            ("numeric", StandardScaler(), NUMERIC_COLUMNS),
        ]
    )

