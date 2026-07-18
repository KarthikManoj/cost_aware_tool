"""Preprocessing utilities for performance prediction models."""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = ["dataset_size_mb", "workload_type", "instance_type", "nodes"]
TARGET_COLUMNS = ["runtime_minutes", "cost_usd"]
CATEGORICAL_COLUMNS = ["workload_type", "instance_type"]
NUMERIC_COLUMNS = ["dataset_size_mb", "nodes"]


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
            ("numeric", StandardScaler(), NUMERIC_COLUMNS),
        ]
    )

