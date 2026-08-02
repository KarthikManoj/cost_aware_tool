"""Evaluate recommendation quality against measured ground truth.

Regression accuracy (MAE/RMSE/R2) measures whether the model predicts runtime
well. It does not measure whether the *tool* recommends good configurations,
which is the actual research claim. This module answers the second question.

Protocol -- leave-one-scenario-out
----------------------------------
A "scenario" is a (workload_type, dataset_size_mb) pair. For each scenario the
model is trained on every row that does NOT belong to it, then asked to
recommend a configuration for it. Because the scenario itself is held out
entirely, the benchmark data contains measured runtime and cost for *every*
candidate configuration in that scenario, so the true optimum is known exactly
and the recommendation can be scored against it.

SLA levels are derived per scenario from the distribution of measured runtimes
(tight = 25th percentile, medium = median, loose = 75th percentile) so that a
"tight" deadline means the same thing for a 10 MB job as for a 5 GB one.

Metrics reported per method and SLA level
-----------------------------------------
  top1_accuracy      recommended configuration is the true cost-optimal one
  top3_hit_rate      true optimum appears in the top 3 recommendations
  cost_regret_pct    how much more the recommendation costs than the optimum
  runtime_regret_pct how much slower than the fastest feasible configuration
  carbon_regret_pct  how much more carbon than the greenest feasible option
  sla_violation_rate recommendations predicted feasible whose MEASURED runtime
                     exceeded the SLA -- the most important safety metric
  infeasible_rate    scenarios where the method found no configuration it
                     believed satisfied the SLA

Baseline methods
----------------
  model             the trained regressor (see --model-type)
  historical_mean   per-configuration mean runtime/cost from the training rows
  nearest_size      measured values from the nearest dataset size for the same
                    workload and configuration
  largest_cluster   always choose the feasible configuration with most nodes
  random            uniformly random feasible configuration (the floor)

Usage
-----
    python ml/evaluate_recommendations.py
    python ml/evaluate_recommendations.py --model-type gradient_boosting
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing import FEATURE_COLUMNS, TARGET_COLUMNS
from ml.train_model import MODEL_REGISTRY, build_model


DATASET_CANDIDATES = [
    ROOT / "data/models/cloud_carbon_model_dataset.csv",
    ROOT / "data/performance/cloud_carbon_model_dataset.csv",
]

CONFIG_COLUMNS = ["cloud", "region", "machine_type", "nodes"]
SCENARIO_COLUMNS = ["workload_type", "dataset_size_mb"]
CARBON_COLUMNS = ["electricity_zone", "carbon_intensity_mean", "renewable_percentage_mean"]

SLA_LEVELS = {"tight": 0.25, "medium": 0.50, "loose": 0.75}

# Non-learned reference methods, always evaluated. Learned methods are named
# "model_<model_type>" and added per --model-type / --all-models.
BASELINE_METHODS = ["historical_mean", "nearest_size", "largest_cluster", "random"]


def method_names(model_types: list[str]) -> list[str]:
    return [f"model_{model_type}" for model_type in model_types] + BASELINE_METHODS


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def resolve_dataset(explicit: str | None) -> Path:
    """Find the merged dataset, tolerating either of the two paths it has
    historically been written to."""
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
    required = set(FEATURE_COLUMNS + TARGET_COLUMNS)
    missing = sorted(required - set(data.columns))
    if missing:
        raise SystemExit(f"Dataset is missing required columns: {', '.join(missing)}")
    data = data.dropna(subset=FEATURE_COLUMNS + TARGET_COLUMNS).copy()
    data["nodes"] = data["nodes"].astype(int)
    return data


def emissions_gco2eq(runtime_minutes: pd.Series, carbon_intensity: pd.Series) -> pd.Series:
    """Relative emissions proxy used for carbon regret.

    This deliberately omits instance power draw and PUE: those are constants
    per configuration and per provider, and carbon *regret* is a ratio between
    two configurations within the same scenario. For absolute emission figures
    use ml/carbon_analysis.py, which applies power draw and PUE properly.
    """
    return (runtime_minutes / 60.0) * carbon_intensity


def build_ground_truth(data: pd.DataFrame) -> pd.DataFrame:
    """Collapse repeated runs into one measured row per scenario+configuration."""
    grouped = (
        data.groupby(SCENARIO_COLUMNS + CONFIG_COLUMNS + ["electricity_zone"], as_index=False)
        .agg(
            measured_runtime_minutes=("runtime_minutes", "mean"),
            measured_cost_usd=("cost_usd", "mean"),
            carbon_intensity_mean=("carbon_intensity_mean", "mean"),
            renewable_percentage_mean=("renewable_percentage_mean", "mean"),
            runs=("runtime_minutes", "size"),
        )
    )
    grouped["measured_emissions"] = emissions_gco2eq(
        grouped["measured_runtime_minutes"], grouped["carbon_intensity_mean"]
    )
    return grouped


# --------------------------------------------------------------------------
# Predictors
# --------------------------------------------------------------------------


def predict_with_model(
    train: pd.DataFrame,
    candidates: pd.DataFrame,
    model_type: str,
) -> tuple[np.ndarray, np.ndarray]:
    pipeline = build_model(model_type)
    pipeline.fit(train[FEATURE_COLUMNS], train[TARGET_COLUMNS])
    predictions = pipeline.predict(candidates[FEATURE_COLUMNS])
    runtime = np.clip(predictions[:, 0], 0.01, None)
    cost = np.clip(predictions[:, 1], 0.0, None)
    return runtime, cost


def predict_historical_mean(
    train: pd.DataFrame,
    candidates: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Mean measured runtime/cost for that configuration across other scenarios."""
    lookup = (
        train.groupby(CONFIG_COLUMNS, as_index=False)
        .agg(
            runtime_hat=("runtime_minutes", "mean"),
            cost_hat=("cost_usd", "mean"),
        )
    )
    merged = candidates.merge(lookup, on=CONFIG_COLUMNS, how="left")
    runtime = merged["runtime_hat"].fillna(train["runtime_minutes"].mean()).to_numpy()
    cost = merged["cost_hat"].fillna(train["cost_usd"].mean()).to_numpy()
    return np.clip(runtime, 0.01, None), np.clip(cost, 0.0, None)


def predict_nearest_size(
    train: pd.DataFrame,
    candidates: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Measured values from the nearest dataset size, same workload and config.

    A deliberately simple non-ML heuristic: no scaling is applied, because
    Spark runtime is dominated by fixed overhead at small dataset sizes and
    linear extrapolation overshoots badly there.
    """
    runtimes: list[float] = []
    costs: list[float] = []
    fallback_runtime = float(train["runtime_minutes"].mean())
    fallback_cost = float(train["cost_usd"].mean())

    for _, row in candidates.iterrows():
        mask = np.ones(len(train), dtype=bool)
        for column in CONFIG_COLUMNS + ["workload_type"]:
            mask &= (train[column] == row[column]).to_numpy()
        subset = train.loc[mask]
        if subset.empty:
            subset = train.loc[train["workload_type"] == row["workload_type"]]
        if subset.empty:
            runtimes.append(fallback_runtime)
            costs.append(fallback_cost)
            continue
        distance = (subset["dataset_size_mb"] - row["dataset_size_mb"]).abs()
        nearest = subset.loc[distance.idxmin()]
        runtimes.append(float(nearest["runtime_minutes"]))
        costs.append(float(nearest["cost_usd"]))

    return (
        np.clip(np.asarray(runtimes, dtype=float), 0.01, None),
        np.clip(np.asarray(costs, dtype=float), 0.0, None),
    )


# --------------------------------------------------------------------------
# Selection rules
# --------------------------------------------------------------------------


def select_by_cost(scored: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    return scored.sort_values(
        ["predicted_cost_usd", "predicted_runtime_minutes"], kind="mergesort"
    )


def select_largest_cluster(scored: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    return scored.sort_values(
        ["nodes", "predicted_cost_usd"], ascending=[False, True], kind="mergesort"
    )


def select_random(scored: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    order = rng.permutation(len(scored))
    return scored.iloc[order]


SELECTORS: dict[str, Callable[[pd.DataFrame, np.random.Generator], pd.DataFrame]] = {
    "largest_cluster": select_largest_cluster,
    "random": select_random,
}


def selector_for(method: str) -> Callable[[pd.DataFrame, np.random.Generator], pd.DataFrame]:
    """Rule-based methods have their own ranking; everything else ranks by
    predicted cost, which is what the production engine does for goal=cost."""
    return SELECTORS.get(method, select_by_cost)


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------


def regret_pct(chosen: float, best: float) -> float:
    """Percentage by which `chosen` exceeds `best`. Zero when best is zero."""
    if best <= 0:
        return 0.0
    return float((chosen - best) / best * 100.0)


def evaluate_scenario(
    scenario: tuple[str, float],
    truth: pd.DataFrame,
    train: pd.DataFrame,
    model_types: list[str],
    rng: np.random.Generator,
) -> list[dict]:
    """Score every method on one held-out scenario at every SLA level."""
    workload, size = scenario
    # One row per configuration. Duplicates would break the ground-truth
    # lookup below, which indexes on the configuration key.
    truth = truth.drop_duplicates(subset=CONFIG_COLUMNS).reset_index(drop=True)
    candidates = truth[CONFIG_COLUMNS + CARBON_COLUMNS].copy()
    candidates["workload_type"] = workload
    candidates["dataset_size_mb"] = size
    candidates = candidates.reset_index(drop=True)

    predictions: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for model_type in model_types:
        predictions[f"model_{model_type}"] = predict_with_model(
            train, candidates, model_type
        )
    hist = predict_historical_mean(train, candidates)
    predictions["historical_mean"] = hist
    predictions["nearest_size"] = predict_nearest_size(train, candidates)
    # The rule-based methods still need runtime estimates to judge SLA
    # feasibility; they differ from historical_mean only in how they rank.
    predictions["largest_cluster"] = hist
    predictions["random"] = hist

    methods = method_names(model_types)

    truth_indexed = truth.set_index(CONFIG_COLUMNS)
    rows: list[dict] = []

    for level, quantile in SLA_LEVELS.items():
        sla = float(truth["measured_runtime_minutes"].quantile(quantile))
        feasible_truth = truth.loc[truth["measured_runtime_minutes"] <= sla]
        if feasible_truth.empty:
            continue

        best_cost = float(feasible_truth["measured_cost_usd"].min())
        best_runtime = float(feasible_truth["measured_runtime_minutes"].min())
        best_emissions = float(feasible_truth["measured_emissions"].min())
        optimal_key = tuple(
            feasible_truth.loc[feasible_truth["measured_cost_usd"].idxmin(), CONFIG_COLUMNS]
        )

        for method in methods:
            runtime_hat, cost_hat = predictions[method]
            scored = candidates.copy()
            scored["predicted_runtime_minutes"] = runtime_hat
            scored["predicted_cost_usd"] = cost_hat

            believed_feasible = scored.loc[scored["predicted_runtime_minutes"] <= sla]
            infeasible = believed_feasible.empty
            if infeasible:
                # Mirror the production engine: fall back to the fastest option.
                believed_feasible = scored.nsmallest(
                    len(scored), "predicted_runtime_minutes"
                )

            ranked = selector_for(method)(believed_feasible, rng).reset_index(drop=True)
            chosen_key = tuple(ranked.loc[0, CONFIG_COLUMNS])
            measured = truth_indexed.loc[chosen_key]

            top3_keys = {
                tuple(ranked.loc[i, CONFIG_COLUMNS])
                for i in range(min(3, len(ranked)))
            }

            rows.append(
                {
                    "workload_type": workload,
                    "dataset_size_mb": size,
                    "sla_level": level,
                    "sla_minutes": round(sla, 4),
                    "method": method,
                    "candidates": int(len(candidates)),
                    "feasible_candidates": int(len(feasible_truth)),
                    "chosen_cloud": chosen_key[0],
                    "chosen_region": chosen_key[1],
                    "chosen_machine_type": chosen_key[2],
                    "chosen_nodes": chosen_key[3],
                    "top1_correct": int(chosen_key == optimal_key),
                    "top3_correct": int(optimal_key in top3_keys),
                    "cost_regret_pct": round(
                        regret_pct(float(measured["measured_cost_usd"]), best_cost), 4
                    ),
                    "runtime_regret_pct": round(
                        regret_pct(float(measured["measured_runtime_minutes"]), best_runtime), 4
                    ),
                    "carbon_regret_pct": round(
                        regret_pct(float(measured["measured_emissions"]), best_emissions), 4
                    ),
                    "sla_violation": int(
                        float(measured["measured_runtime_minutes"]) > sla and not infeasible
                    ),
                    "no_feasible_prediction": int(infeasible),
                    "measured_runtime_minutes": round(
                        float(measured["measured_runtime_minutes"]), 4
                    ),
                    "measured_cost_usd": round(float(measured["measured_cost_usd"]), 6),
                }
            )

    return rows


def summarise(detail: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    summary = (
        detail.groupby(["method", "sla_level"], as_index=False)
        .agg(
            scenarios=("top1_correct", "size"),
            top1_accuracy=("top1_correct", "mean"),
            top3_hit_rate=("top3_correct", "mean"),
            mean_cost_regret_pct=("cost_regret_pct", "mean"),
            median_cost_regret_pct=("cost_regret_pct", "median"),
            max_cost_regret_pct=("cost_regret_pct", "max"),
            mean_runtime_regret_pct=("runtime_regret_pct", "mean"),
            mean_carbon_regret_pct=("carbon_regret_pct", "mean"),
            sla_violation_rate=("sla_violation", "mean"),
            infeasible_rate=("no_feasible_prediction", "mean"),
        )
    )
    numeric = summary.select_dtypes(include="number").columns
    summary[numeric] = summary[numeric].round(4)
    order = {level: index for index, level in enumerate(SLA_LEVELS)}
    summary["_order"] = summary["sla_level"].map(order)
    method_order = {method: index for index, method in enumerate(methods)}
    summary["_method"] = summary["method"].map(method_order)
    return summary.sort_values(["_method", "_order"]).drop(columns=["_order", "_method"])


def search_space_summary(truth: pd.DataFrame) -> dict:
    per_scenario = truth.groupby(SCENARIO_COLUMNS).size()
    total_runs = int(truth["runs"].sum())
    return {
        "scenarios": int(len(per_scenario)),
        "configurations_per_scenario_mean": round(float(per_scenario.mean()), 2),
        "configurations_per_scenario_max": int(per_scenario.max()),
        "benchmark_runs_in_dataset": total_runs,
        "runs_required_by_recommender_at_inference": 0,
        "note": (
            "The recommender scores every candidate configuration from the trained "
            "model alone, requiring no new benchmark runs for an unseen scenario. "
            "Exhaustive search would require one run per candidate configuration."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate recommendation quality against measured ground truth."
    )
    parser.add_argument("--dataset", default=None)
    parser.add_argument(
        "--model-type",
        default="random_forest",
        choices=list(MODEL_REGISTRY.keys()),
        help="Which regressor to evaluate. Ignored when --all-models is set.",
    )
    parser.add_argument(
        "--all-models",
        action="store_true",
        help="Evaluate every model in MODEL_REGISTRY as a separate method, "
             "so recommendation quality can be compared across models.",
    )
    parser.add_argument("--output-dir", default=str(ROOT / "data/results"))
    parser.add_argument("--min-candidates", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset_path = resolve_dataset(args.dataset)
    data = load_dataset(dataset_path)
    truth = build_ground_truth(data)
    rng = np.random.default_rng(args.seed)

    model_types = list(MODEL_REGISTRY.keys()) if args.all_models else [args.model_type]
    methods = method_names(model_types)

    print(f"Dataset: {dataset_path}")
    print(f"Rows: {len(data)}  Scenarios: {truth.groupby(SCENARIO_COLUMNS).ngroups}")
    print(
        "Models: "
        + ", ".join(MODEL_REGISTRY[model_type]["label"] for model_type in model_types)
    )
    print()

    all_rows: list[dict] = []
    skipped: list[str] = []

    for scenario, scenario_truth in truth.groupby(SCENARIO_COLUMNS):
        workload, size = scenario
        if len(scenario_truth) < args.min_candidates:
            skipped.append(f"{workload} @ {size} MB (only {len(scenario_truth)} configs)")
            continue

        mask = (data["workload_type"] == workload) & (data["dataset_size_mb"] == size)
        train = data.loc[~mask]
        if len(train) < 10:
            skipped.append(f"{workload} @ {size} MB (only {len(train)} training rows)")
            continue

        all_rows.extend(
            evaluate_scenario(
                scenario, scenario_truth.reset_index(drop=True), train, model_types, rng
            )
        )

    if not all_rows:
        raise SystemExit(
            "No scenario had enough candidate configurations to evaluate. "
            "Check that the merged dataset contains multiple configurations "
            "per workload and dataset size."
        )

    detail = pd.DataFrame(all_rows)
    summary = summarise(detail, methods)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output / "recommendation_quality_detail.csv", index=False)
    summary.to_csv(output / "recommendation_quality_summary.csv", index=False)

    payload = {
        "dataset": str(dataset_path),
        "model_types": model_types,
        "methods": methods,
        "protocol": "leave-one-scenario-out (workload_type x dataset_size_mb)",
        "sla_levels": {k: f"{int(v * 100)}th percentile of measured runtime" for k, v in SLA_LEVELS.items()},
        "search_space": search_space_summary(truth),
        "skipped_scenarios": skipped,
        "summary": summary.to_dict(orient="records"),
    }
    with open(output / "recommendation_quality_summary.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print(summary.to_string(index=False))
    print()
    if skipped:
        print("Skipped scenarios:")
        for item in skipped:
            print(f"  - {item}")
        print()
    print(f"Wrote results to {output}")


if __name__ == "__main__":
    main()
