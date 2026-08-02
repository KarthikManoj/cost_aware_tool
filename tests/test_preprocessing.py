from __future__ import annotations

from ml.preprocessing import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMNS,
    build_preprocessor,
)


def test_feature_columns_partition_into_categorical_and_numeric() -> None:
    assert set(CATEGORICAL_COLUMNS) | set(NUMERIC_COLUMNS) == set(FEATURE_COLUMNS)
    assert set(CATEGORICAL_COLUMNS).isdisjoint(NUMERIC_COLUMNS)


def test_target_columns_are_not_features() -> None:
    assert set(TARGET_COLUMNS).isdisjoint(FEATURE_COLUMNS)


def test_build_preprocessor_has_expected_transformers() -> None:
    preprocessor = build_preprocessor()
    names = [name for name, _, _ in preprocessor.transformers]
    assert names == ["categorical", "numeric"]
