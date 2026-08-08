
"""Train and compare cloud performance prediction models."""
 
from __future__ import annotations
 
import argparse
import json
import sys
from pathlib import Path
from typing import Any
 
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeRegressor
 
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
 
from ml.preprocessing import FEATURE_COLUMNS, TARGET_COLUMNS, build_preprocessor
 
 
MODEL_REGISTRY = {
    "linear_regression": {
        "label": "Linear Regression",
        "estimator": LinearRegression,
        "params": {},
    },
    "decision_tree": {
        "label": "Decision Tree",
        "estimator": DecisionTreeRegressor,
        "params": {"random_state": 42},
    },
    "random_forest": {
        "label": "Random Forest",
        "estimator": RandomForestRegressor,
        "params": {
            "n_estimators": 250,
            "random_state": 42,
            "min_samples_leaf": 1,
            "n_jobs": -1,  # parallel fitting, doesn't affect predictions
        },
    },
    "gradient_boosting": {
        "label": "Gradient Boosting",
        "estimator": GradientBoostingRegressor,
        "params": {"random_state": 42},
    },
}
 
PREDICTION_OUTPUT_COLUMNS = [
    "model",
    "cloud",
    "region",
    "dataset_size_mb",
    "workload_type",
    "machine_type",
    "nodes",
    "actual_runtime_minutes",
    "predicted_runtime_minutes",
    "actual_cost_usd",
    "predicted_cost_usd",
]
 
# Identifies one benchmark configuration. Splits must group on this so
# repeated runs of the same config don't leak across train/test.
GROUP_COLUMNS = ["cloud", "region", "dataset_size_mb", "workload_type", "machine_type", "nodes"]
 
 
def build_model(model_type: str) -> Pipeline:
    """Create a model pipeline with shared preprocessing."""
    if model_type == "linear":
        model_type = "linear_regression"
    if model_type not in MODEL_REGISTRY:
        choices = ", ".join(MODEL_REGISTRY)
        raise ValueError(f"Unknown model_type '{model_type}'. Choose from: {choices}.")
 
    config = MODEL_REGISTRY[model_type]
    estimator = config["estimator"](**config["params"])
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            ("model", MultiOutputRegressor(estimator)),
        ]
    )
 
 
def load_training_data(input_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the merged dataset and keep only complete model rows."""
    data = pd.read_csv(input_path).dropna(subset=FEATURE_COLUMNS + TARGET_COLUMNS)
    if len(data) < 6:
        raise ValueError(
            "Need at least 6 performance rows for a useful train/test split."
        )
    return data[FEATURE_COLUMNS], data[TARGET_COLUMNS]
 
 
def build_groups(x: pd.DataFrame) -> pd.Series:
    """Per-row configuration key for grouping repeated runs together."""
    return x[GROUP_COLUMNS].astype(str).agg("|".join, axis=1)
 
 
def grouped_train_test_split(
    x: pd.DataFrame,
    y: pd.DataFrame,
    test_size: float,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Group-aware train/test split; falls back to a plain split if there
    are too few distinct configurations to group on."""
    groups = build_groups(x)
    if groups.nunique() < 2:
        return train_test_split(x, y, test_size=test_size, random_state=random_state)
 
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_idx, test_idx = next(splitter.split(x, y, groups=groups))
    return x.iloc[train_idx], x.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]
 
 
def evaluate(y_true: pd.DataFrame, y_pred: np.ndarray) -> dict[str, dict[str, float]]:
    """Calculate target-level regression metrics."""
    metrics: dict[str, dict[str, float]] = {}
    for index, target in enumerate(TARGET_COLUMNS):
        metrics[target] = {
            "mae": round(
                mean_absolute_error(
                    y_true.iloc[:, index],
                    y_pred[:, index],
                ),
                4,
            ),
            "rmse": round(
                float(
                    np.sqrt(
                        mean_squared_error(
                            y_true.iloc[:, index],
                            y_pred[:, index],
                        )
                    )
                ),
                4,
            ),
            "r2": round(r2_score(y_true.iloc[:, index], y_pred[:, index]), 4),
        }
    return metrics
 
 
def add_average_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Add average R2 and RMSE for best-model selection."""
    average_r2 = float(
        np.mean([target_metrics["r2"] for target_metrics in metrics.values()])
    )
    average_rmse = float(
        np.mean([target_metrics["rmse"] for target_metrics in metrics.values()])
    )
    return {
        **metrics,
        "average_r2": round(average_r2, 4),
        "average_rmse": round(average_rmse, 4),
    }
 
 
def create_prediction_frame(
    model_label: str,
    x_test: pd.DataFrame,
    y_test: pd.DataFrame,
    predictions: np.ndarray,
) -> pd.DataFrame:
    """Build the prediction comparison rows for one model."""
    frame = x_test.reset_index(drop=True).copy()
    frame["model"] = model_label
    frame["actual_runtime_minutes"] = y_test["runtime_minutes"].reset_index(drop=True)
    frame["predicted_runtime_minutes"] = predictions[:, 0]
    frame["actual_cost_usd"] = y_test["cost_usd"].reset_index(drop=True)
    frame["predicted_cost_usd"] = predictions[:, 1]
    return frame[PREDICTION_OUTPUT_COLUMNS]
 
 
def select_best_model(
    comparison: dict[str, dict[str, Any]],
    cv_summary: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Pick the best model by cross-validated average R2 where available,
    since the single holdout split has too much variance to trust alone.
    Falls back to the holdout ranking if no CV summary is given."""
    if cv_summary:
        def cv_average_r2(model_type: str) -> float:
            return float(
                np.mean(
                    [cv_summary[model_type][target]["r2"]["mean"] for target in TARGET_COLUMNS]
                )
            )
 
        def cv_average_rmse(model_type: str) -> float:
            return float(
                np.mean(
                    [cv_summary[model_type][target]["rmse"]["mean"] for target in TARGET_COLUMNS]
                )
            )
 
        return max(
            cv_summary,
            key=lambda model_type: (cv_average_r2(model_type), -cv_average_rmse(model_type)),
        )
 
    return max(
        comparison,
        key=lambda model_type: (
            comparison[model_type]["average_r2"],
            -comparison[model_type]["average_rmse"],
        ),
    )
 
 
def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
 
 
def extract_feature_importance(pipeline: Pipeline) -> dict[str, dict[str, float]] | None:
    """Per-target feature importances, ranked highest first. Only tree
    models expose this; linear regression is skipped."""
    model = pipeline.named_steps["model"]
    estimators = getattr(model, "estimators_", None)
    if not estimators or not hasattr(estimators[0], "feature_importances_"):
        return None
 
    preprocessor = pipeline.named_steps["preprocess"]
    feature_names = preprocessor.get_feature_names_out()
 
    importances: dict[str, dict[str, float]] = {}
    for target, estimator in zip(TARGET_COLUMNS, estimators):
        ranked = sorted(
            zip(feature_names, estimator.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )
        importances[target] = {name: round(float(score), 6) for name, score in ranked}
    return importances
 
 
def format_metric_block(label: str, metrics: dict[str, dict[str, float]]) -> list[str]:
    return [
        label,
        "Runtime:",
        f"MAE: {metrics['runtime_minutes']['mae']}",
        f"RMSE: {metrics['runtime_minutes']['rmse']}",
        f"R2: {metrics['runtime_minutes']['r2']}",
        "",
        "Cost:",
        f"MAE: {metrics['cost_usd']['mae']}",
        f"RMSE: {metrics['cost_usd']['rmse']}",
        f"R2: {metrics['cost_usd']['r2']}",
        "",
    ]
 
 
def print_comparison_summary(
    comparison: dict[str, dict[str, Any]],
    best_model: str,
) -> None:
    """Print a dissertation-friendly comparison summary."""
    print("=" * 52)
    print("Model Comparison")
    print("=" * 52)
    print()
 
    for model_type, config in MODEL_REGISTRY.items():
        for line in format_metric_block(config["label"], comparison[model_type]):
            print(line)
 
    best_metrics = comparison[best_model]
    best_label = MODEL_REGISTRY[best_model]["label"]
    print("Best Model:")
    print(best_label)
    print()
    print("Reason:")
    print(
        "Highest cross-validated average R2 with lowest average RMSE. "
        f"Holdout figures for this model: average R2={best_metrics['average_r2']}, "
        f"average RMSE={best_metrics['average_rmse']}."
    )
    print()
    print("=" * 52)
 
 
def compare_models(
    input_path: str,
    output_dir: str,
    best_model_output: str,
) -> dict[str, dict[str, Any]]:
    """Train, evaluate, compare, and persist all model artifacts. Holdout
    metrics go to model_comparison.json; the best model is picked by
    cross-validation (see select_best_model)."""
    x, y = load_training_data(input_path)
    test_size = 0.25 if len(x) >= 12 else 0.34
    x_train, x_test, y_train, y_test = grouped_train_test_split(x, y, test_size=test_size)
 
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
 
    comparison: dict[str, dict[str, Any]] = {}
    prediction_frames: list[pd.DataFrame] = []
 
    for model_type, config in MODEL_REGISTRY.items():
        pipeline = build_model(model_type)
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)
 
        metrics = evaluate(y_test, predictions)
        comparison[model_type] = add_average_metrics(metrics)
        prediction_frames.append(
            create_prediction_frame(config["label"], x_test, y_test, predictions)
        )
 
    # Best model is picked from cross-validation, not the holdout split above.
    cv_summary = cross_validate_models(
        input_path,
        str(output / "cross_validation_metrics.json"),
    )
    best_model = select_best_model(comparison, cv_summary)
    best_pipeline = build_model(best_model)
    best_pipeline.fit(x, y)
 
    save_json(output / "model_comparison.json", comparison)
    pd.concat(prediction_frames, ignore_index=True).to_csv(
        output / "prediction_comparison.csv",
        index=False,
    )
    Path(best_model_output).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_pipeline, best_model_output)
 
    feature_importance = extract_feature_importance(best_pipeline)
    if feature_importance is not None:
        save_json(output / "feature_importance.json", feature_importance)
 
    print_comparison_summary(comparison, best_model)
    return comparison
 
 
def cross_validate_models(
    input_path: str,
    output_path: str,
    n_splits: int = 5,
) -> dict[str, dict[str, Any]]:
    """Grouped k-fold cross-validation for every model in MODEL_REGISTRY.
    Reports mean/std per metric across folds instead of one holdout estimate."""
    x, y = load_training_data(input_path)
    groups = build_groups(x)
    unique_groups = int(groups.nunique())
    effective_splits = max(2, min(n_splits, unique_groups))
    if effective_splits < n_splits:
        print(
            f"Warning: only {unique_groups} unique configurations available; "
            f"reducing cross-validation folds from {n_splits} to {effective_splits}."
        )
 
    splitter = GroupKFold(n_splits=effective_splits)
    fold_metrics: dict[str, dict[str, dict[str, list[float]]]] = {
        model_type: {target: {"mae": [], "rmse": [], "r2": []} for target in TARGET_COLUMNS}
        for model_type in MODEL_REGISTRY
    }
 
    for train_idx, test_idx in splitter.split(x, y, groups=groups):
        x_train, x_test = x.iloc[train_idx], x.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        for model_type in MODEL_REGISTRY:
            pipeline = build_model(model_type)
            pipeline.fit(x_train, y_train)
            predictions = pipeline.predict(x_test)
            metrics = evaluate(y_test, predictions)
            for target in TARGET_COLUMNS:
                for metric_name in ("mae", "rmse", "r2"):
                    fold_metrics[model_type][target][metric_name].append(metrics[target][metric_name])
 
    summary: dict[str, dict[str, Any]] = {}
    for model_type, target_metrics in fold_metrics.items():
        model_summary: dict[str, Any] = {
            target: {
                metric_name: {
                    "mean": round(float(np.mean(values)), 4),
                    "std": round(float(np.std(values, ddof=1)), 4),  # matches statistical_tests.py
                }
                for metric_name, values in metrics.items()
            }
            for target, metrics in target_metrics.items()
        }
        model_summary["folds"] = effective_splits
        summary[model_type] = model_summary
 
    save_json(Path(output_path), summary)
    return summary
 
 
def train(
    input_path: str,
    model_output: str,
    metrics_output: str,
    model_type: str,
) -> dict[str, dict[str, float]]:
    """Train one selected model and save its metrics and artifact."""
    x, y = load_training_data(input_path)
    test_size = 0.25 if len(x) >= 12 else 0.34
    x_train, x_test, y_train, y_test = grouped_train_test_split(x, y, test_size=test_size)
 
    pipeline = build_model(model_type)
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    metrics = evaluate(y_test, predictions)
 
    pipeline.fit(x, y)
    Path(model_output).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_output)
    save_json(Path(metrics_output), metrics)
    return metrics
 
 
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and compare cloud regression models."
    )
    parser.add_argument(
        "--input",
        default=str(ROOT / "data/models/cloud_carbon_model_dataset.csv"),
    )
    parser.add_argument("--output-dir", default=str(ROOT / "data/models"))
    parser.add_argument("--compare-output-dir", default=None)
    parser.add_argument(
        "--best-model-output",
        default=str(ROOT / "data/models/best_cloud_model.joblib"),
    )
    parser.add_argument(
        "--model-output",
        default=str(ROOT / "data/models/cloud_carbon_performance_model.joblib"),
    )
    parser.add_argument(
        "--metrics-output",
        default=str(ROOT / "data/models/model_metrics.json"),
    )
    parser.add_argument(
        "--model-type",
        choices=["linear", *MODEL_REGISTRY.keys()],
        default="random_forest",
    )
    parser.add_argument(
        "--single-model",
        action="store_true",
        help="Train only --model-type instead of comparing all models.",
    )
    parser.add_argument(
        "--cross-validate",
        action="store_true",
        help="Also run grouped k-fold cross-validation and save cross_validation_metrics.json.",
    )
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument(
        "--cv-output",
        default=str(ROOT / "data/models/cross_validation_metrics.json"),
    )
    args = parser.parse_args()
 
    if args.compare_output_dir:
        args.output_dir = args.compare_output_dir
 
    if args.cross_validate:
        cv_summary = cross_validate_models(args.input, args.cv_output, n_splits=args.cv_folds)
        print(json.dumps(cv_summary, indent=2))
 
    if args.single_model:
        metrics = train(
            args.input,
            args.model_output,
            args.metrics_output,
            args.model_type,
        )
        print(json.dumps(metrics, indent=2))
        return
 
    compare_models(args.input, args.output_dir, args.best_model_output)
 
 
if __name__ == "__main__":
    main()
 