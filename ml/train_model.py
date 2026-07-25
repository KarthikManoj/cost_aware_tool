"""Train runtime and cost prediction models from the performance dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing import FEATURE_COLUMNS, TARGET_COLUMNS, build_preprocessor


def build_model(model_type: str) -> Pipeline:
    if model_type == "linear":
        estimator = LinearRegression()
    else:
        estimator = RandomForestRegressor(n_estimators=250, random_state=42, min_samples_leaf=1)
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            ("model", MultiOutputRegressor(estimator)),
        ]
    )


def evaluate(y_true, y_pred) -> dict[str, dict[str, float]]:
    metrics = {}
    for index, target in enumerate(TARGET_COLUMNS):
        metrics[target] = {
            "mae": round(mean_absolute_error(y_true.iloc[:, index], y_pred[:, index]), 4),
            "rmse": round(float(np.sqrt(mean_squared_error(y_true.iloc[:, index], y_pred[:, index]))), 4),
            "r2": round(r2_score(y_true.iloc[:, index], y_pred[:, index]), 4),
        }
    return metrics


def train(input_path: str, model_output: str, metrics_output: str, model_type: str) -> dict[str, dict[str, float]]:
    data = pd.read_csv(input_path).dropna(subset=FEATURE_COLUMNS + TARGET_COLUMNS)
    if len(data) < 6:
        raise ValueError("Need at least 6 performance rows for a useful train/test split.")

    x = data[FEATURE_COLUMNS]
    y = data[TARGET_COLUMNS]
    test_size = 0.25 if len(data) >= 12 else 0.34
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_size, random_state=42)

    pipeline = build_model(model_type)
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    metrics = evaluate(y_test, predictions)

    pipeline.fit(x, y)
    Path(model_output).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_output)
    Path(metrics_output).parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_output, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
    return metrics


def compare_models(input_path: str, output_dir: str) -> dict[str, dict[str, dict[str, float]]]:
    data = pd.read_csv(input_path).dropna(subset=FEATURE_COLUMNS + TARGET_COLUMNS)
    if len(data) < 6:
        raise ValueError("Need at least 6 performance rows for model comparison.")

    x = data[FEATURE_COLUMNS]
    y = data[TARGET_COLUMNS]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.25 if len(data) >= 12 else 0.34,
        random_state=42,
    )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    comparison: dict[str, dict[str, dict[str, float]]] = {}
    predictions_frames = []

    for model_type in ["linear", "random_forest"]:
        pipeline = build_model(model_type)
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)
        comparison[model_type] = evaluate(y_test, predictions)

        frame = x_test.reset_index(drop=True).copy()
        frame["model"] = model_type
        frame["actual_runtime_minutes"] = y_test["runtime_minutes"].reset_index(drop=True)
        frame["predicted_runtime_minutes"] = predictions[:, 0]
        frame["actual_cost_usd"] = y_test["cost_usd"].reset_index(drop=True)
        frame["predicted_cost_usd"] = predictions[:, 1]
        predictions_frames.append(frame)

    with open(output / "model_comparison.json", "w", encoding="utf-8") as handle:
        json.dump(comparison, handle, indent=2)
    pd.concat(predictions_frames, ignore_index=True).to_csv(output / "prediction_comparison.csv", index=False)
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Train runtime and cost prediction model.")
    parser.add_argument("--input", default="data/models/cloud_carbon_model_dataset.csv")
    parser.add_argument("--model-output", default="data/models/cloud_carbon_performance_model.joblib")
    parser.add_argument("--metrics-output", default="data/models/model_metrics.json")
    parser.add_argument("--model-type", choices=["random_forest", "linear"], default="random_forest")
    parser.add_argument("--compare-output-dir", default=None)
    args = parser.parse_args()

    if args.compare_output_dir:
        comparison = compare_models(args.input, args.compare_output_dir)
        print(json.dumps(comparison, indent=2))

    metrics = train(args.input, args.model_output, args.metrics_output, args.model_type)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
