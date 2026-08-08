"""Paired significance tests between models, using matched cross-validation
folds instead of just comparing mean/std metrics.

Produces:
    per_fold_metrics.csv           one row per model, fold and target
    model_significance.csv         pairwise paired tests between models
    repeatability.csv              variance across repeated identical runs
    statistical_tests_summary.json headline findings

With 5 folds, Wilcoxon can't reach p < 0.05 -- use the paired t-test and
effect size instead.

Usage:
    python ml/statistical_tests.py
    python ml/statistical_tests.py --cv-folds 5 --target runtime_minutes
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing import FEATURE_COLUMNS, TARGET_COLUMNS
from ml.train_model import GROUP_COLUMNS, MODEL_REGISTRY, build_model


DATASET_CANDIDATES = [
    ROOT / "data/models/cloud_carbon_model_dataset.csv",
    ROOT / "data/performance/cloud_carbon_model_dataset.csv",
]

CONFIG_COLUMNS = ["cloud", "region", "machine_type", "nodes"]
SCENARIO_COLUMNS = ["workload_type", "dataset_size_mb"]


def resolve_dataset(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"Dataset not found: {path}")
        return path
    for candidate in DATASET_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "Could not find cloud_carbon_model_dataset.csv. Run "
        "`python ml/merge_model_dataset.py` first."
    )


def load_dataset(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    missing = sorted(set(FEATURE_COLUMNS + TARGET_COLUMNS) - set(data.columns))
    if missing:
        raise SystemExit(f"Dataset is missing required columns: {', '.join(missing)}")
    return data.dropna(subset=FEATURE_COLUMNS + TARGET_COLUMNS).copy()


# --------------------------------------------------------------------------
# Per-fold cross-validation
# --------------------------------------------------------------------------


def collect_per_fold_metrics(data: pd.DataFrame, n_splits: int) -> pd.DataFrame:
    """Run grouped k-fold once, scoring every model on identical folds."""
    x = data[FEATURE_COLUMNS]
    y = data[TARGET_COLUMNS]
    groups = data[GROUP_COLUMNS].astype(str).agg("|".join, axis=1)

    unique_groups = int(groups.nunique())
    effective = max(2, min(n_splits, unique_groups))
    if effective < n_splits:
        print(
            f"Warning: only {unique_groups} unique configurations; "
            f"reducing folds from {n_splits} to {effective}."
        )

    splitter = GroupKFold(n_splits=effective)
    rows: list[dict] = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(x, y, groups=groups), start=1):
        x_train, x_test = x.iloc[train_idx], x.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        for model_type, config in MODEL_REGISTRY.items():
            pipeline = build_model(model_type)
            pipeline.fit(x_train, y_train)
            predictions = pipeline.predict(x_test)

            for index, target in enumerate(TARGET_COLUMNS):
                actual = y_test.iloc[:, index]
                predicted = predictions[:, index]
                rows.append(
                    {
                        "model": model_type,
                        "model_label": config["label"],
                        "fold": fold,
                        "target": target,
                        "n_test": int(len(actual)),
                        "mae": float(mean_absolute_error(actual, predicted)),
                        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
                        "r2": float(r2_score(actual, predicted)),
                    }
                )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Confidence intervals and paired tests
# --------------------------------------------------------------------------


def confidence_interval(values: np.ndarray, confidence: float = 0.95) -> tuple[float, float, float]:
    """Mean and t-based confidence interval (t, not z -- too few folds)."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    mean = float(np.mean(values))
    if n < 2:
        return mean, mean, mean
    sem = float(stats.sem(values))
    if sem == 0:
        return mean, mean, mean
    critical = float(stats.t.ppf(0.5 + confidence / 2, df=n - 1))
    margin = critical * sem
    return mean, mean - margin, mean + margin


def paired_tests(per_fold: pd.DataFrame, target: str, metric: str) -> pd.DataFrame:
    """Every pairwise model comparison on matched folds."""
    subset = per_fold.loc[per_fold["target"] == target]
    pivot = subset.pivot(index="fold", columns="model", values=metric).dropna()
    models = list(pivot.columns)
    rows: list[dict] = []

    for left, right in combinations(models, 2):
        a = pivot[left].to_numpy(dtype=float)
        b = pivot[right].to_numpy(dtype=float)
        difference = a - b

        t_stat, t_p = stats.ttest_rel(a, b)

        if np.allclose(difference, 0):
            w_stat, w_p = np.nan, 1.0
        else:
            try:
                w_stat, w_p = stats.wilcoxon(a, b)
            except ValueError:
                w_stat, w_p = np.nan, np.nan

        mean_difference, lower, upper = confidence_interval(difference)
        pooled = np.std(difference, ddof=1)
        cohens_d = float(mean_difference / pooled) if pooled > 0 else 0.0

        rows.append(
            {
                "target": target,
                "metric": metric,
                "model_a": left,
                "model_b": right,
                "folds": int(len(difference)),
                "mean_a": round(float(np.mean(a)), 6),
                "mean_b": round(float(np.mean(b)), 6),
                "mean_difference": round(mean_difference, 6),
                "ci95_lower": round(lower, 6),
                "ci95_upper": round(upper, 6),
                "paired_t_statistic": round(float(t_stat), 4),
                "paired_t_p_value": round(float(t_p), 4),
                "wilcoxon_statistic": (None if np.isnan(w_stat) else round(float(w_stat), 4)),
                "wilcoxon_p_value": (None if np.isnan(w_p) else round(float(w_p), 4)),
                "cohens_d": round(cohens_d, 4),
                "significant_at_0_05": bool(t_p < 0.05),
                "ci_excludes_zero": bool(lower > 0 or upper < 0),
            }
        )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Repeatability of the benchmark itself
# --------------------------------------------------------------------------


def repeatability(data: pd.DataFrame) -> pd.DataFrame:
    """Variance across repeated runs of the same configuration -- sets a
    floor on how accurate any predictor could be."""
    grouped = data.groupby(SCENARIO_COLUMNS + CONFIG_COLUMNS)
    rows: list[dict] = []

    for key, group in grouped:
        if len(group) < 2:
            continue
        runtimes = group["runtime_minutes"].to_numpy(dtype=float)
        mean, lower, upper = confidence_interval(runtimes)
        std = float(np.std(runtimes, ddof=1))
        rows.append(
            {
                "workload_type": key[0],
                "dataset_size_mb": key[1],
                "cloud": key[2],
                "region": key[3],
                "machine_type": key[4],
                "nodes": key[5],
                "runs": int(len(runtimes)),
                "mean_runtime_minutes": round(mean, 4),
                "std_runtime_minutes": round(std, 4),
                "coefficient_of_variation_pct": round(
                    float(std / mean * 100.0) if mean > 0 else 0.0, 2
                ),
                "ci95_lower": round(lower, 4),
                "ci95_upper": round(upper, 4),
                "min_runtime_minutes": round(float(runtimes.min()), 4),
                "max_runtime_minutes": round(float(runtimes.max()), 4),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paired significance tests and confidence intervals."
    )
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--metric", default="mae", choices=["mae", "rmse", "r2"])
    parser.add_argument("--output-dir", default=str(ROOT / "data/results"))
    args = parser.parse_args()

    dataset_path = resolve_dataset(args.dataset)
    data = load_dataset(dataset_path)

    print(f"Dataset: {dataset_path}  ({len(data)} rows)")
    print("Running grouped cross-validation and retaining per-fold errors...")
    per_fold = collect_per_fold_metrics(data, args.cv_folds)

    fold_summary = (
        per_fold.groupby(["model", "model_label", "target"], as_index=False)
        .agg(
            folds=("fold", "nunique"),
            mae_mean=("mae", "mean"),
            mae_std=("mae", "std"),
            rmse_mean=("rmse", "mean"),
            rmse_std=("rmse", "std"),
            r2_mean=("r2", "mean"),
            r2_std=("r2", "std"),
        )
    )
    numeric = fold_summary.select_dtypes(include="number").columns
    fold_summary[numeric] = fold_summary[numeric].round(6)

    tests = pd.concat(
        [paired_tests(per_fold, target, args.metric) for target in TARGET_COLUMNS],
        ignore_index=True,
    )
    repeats = repeatability(data)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    per_fold.round(6).to_csv(output / "per_fold_metrics.csv", index=False)
    fold_summary.to_csv(output / "per_fold_summary.csv", index=False)
    tests.to_csv(output / "model_significance.csv", index=False)
    repeats.to_csv(output / "repeatability.csv", index=False)

    significant = tests.loc[tests["significant_at_0_05"]]
    payload = {
        "dataset": str(dataset_path),
        "folds": int(per_fold["fold"].nunique()),
        "metric_tested": args.metric,
        "models_compared": sorted(per_fold["model"].unique().tolist()),
        "significant_pairs": int(len(significant)),
        "total_pairs": int(len(tests)),
        "repeatability": (
            {
                "configurations_with_repeats": int(len(repeats)),
                "median_coefficient_of_variation_pct": round(
                    float(repeats["coefficient_of_variation_pct"].median()), 2
                ),
                "max_coefficient_of_variation_pct": round(
                    float(repeats["coefficient_of_variation_pct"].max()), 2
                ),
            }
            if not repeats.empty
            else "no configuration was run more than once"
        ),
        "caveat": (
            f"With {int(per_fold['fold'].nunique())} folds the Wilcoxon test cannot reach "
            "p < 0.05; quote the paired t-test and the effect size instead."
        ),
    }
    with open(output / "statistical_tests_summary.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print()
    print("Per-fold summary:")
    print(fold_summary.to_string(index=False))
    print()
    print(f"Paired comparisons on {args.metric}:")
    columns = [
        "target", "model_a", "model_b", "mean_difference",
        "ci95_lower", "ci95_upper", "paired_t_p_value", "significant_at_0_05",
    ]
    print(tests[columns].to_string(index=False))
    print()
    if not repeats.empty:
        print(
            "Benchmark repeatability: median CV "
            f"{payload['repeatability']['median_coefficient_of_variation_pct']}%, "
            f"max {payload['repeatability']['max_coefficient_of_variation_pct']}% "
            f"across {payload['repeatability']['configurations_with_repeats']} configurations."
        )
    else:
        print("No configuration was run more than once, so repeatability cannot be measured.")
    print()
    print(f"Wrote results to {output}")


if __name__ == "__main__":
    main()
