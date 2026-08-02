"""Rank cost-aware and carbon-aware cloud infrastructure recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing import FEATURE_COLUMNS


OptimizationGoal = Literal["cost", "runtime", "carbon", "balanced"]

DEFAULT_MODEL_PATH = ROOT / "data/models/best_cloud_model.joblib"
DEFAULT_DATASET_PATH = ROOT / "data/models/cloud_carbon_model_dataset.csv"

CANDIDATE_COLUMNS = [
    "cloud",
    "region",
    "electricity_zone",
    "machine_type",
    "nodes",
    "carbon_intensity_mean",
    "renewable_percentage_mean",
]

OUTPUT_COLUMNS = [
    "Rank",
    "Cloud",
    "Region",
    "Machine Type",
    "Nodes",
    "Predicted Runtime (minutes)",
    "Predicted Cost (USD)",
    "Carbon Intensity",
    "Renewable Percentage",
    "Optimization Score",
    "Recommendation Reason",
]

GOAL_ALIASES = {
    "cost": "cost",
    "lowest_cost": "cost",
    "lowest cost": "cost",
    "runtime": "runtime",
    "fastest": "runtime",
    "fastest_runtime": "runtime",
    "fastest runtime": "runtime",
    "carbon": "carbon",
    "lowest_carbon": "carbon",
    "lowest carbon": "carbon",
    "balanced": "balanced",
    "balance": "balanced",
}


class RecommendationEngine:
    """Generate ranked infrastructure recommendations from a trained model."""

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        dataset_path: str | Path = DEFAULT_DATASET_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.dataset_path = Path(dataset_path)
        self.model: Pipeline = joblib.load(self.model_path)
        self.dataset = pd.read_csv(self.dataset_path)
        self._validate_dataset()

    def recommend(
        self,
        dataset_size_mb: float,
        workload_type: str,
        sla_runtime_minutes: float,
        optimization_goal: str,
    ) -> pd.Series:
        """Return the first-ranked infrastructure recommendation."""
        recommendations = self.recommend_top_n(
            dataset_size_mb=dataset_size_mb,
            workload_type=workload_type,
            sla_runtime_minutes=sla_runtime_minutes,
            optimization_goal=optimization_goal,
            top_n=1,
        )
        return recommendations.iloc[0]

    def recommend_top_n(
        self,
        dataset_size_mb: float,
        workload_type: str,
        sla_runtime_minutes: float,
        optimization_goal: str,
        top_n: int = 5,
    ) -> pd.DataFrame:
        """Return the best N ranked infrastructure configurations."""
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")

        ranked = self._rank_configurations(
            dataset_size_mb=dataset_size_mb,
            workload_type=workload_type,
            sla_runtime_minutes=sla_runtime_minutes,
            optimization_goal=optimization_goal,
        )
        return ranked.head(top_n).reset_index(drop=True)

    def compare_recommendations(
        self,
        dataset_size_mb: float,
        workload_type: str,
        sla_runtime_minutes: float,
        optimization_goal: str,
        top_n: int = 5,
    ) -> pd.DataFrame:
        """Return a formatted comparison table for the top recommendations."""
        recommendations = self.recommend_top_n(
            dataset_size_mb=dataset_size_mb,
            workload_type=workload_type,
            sla_runtime_minutes=sla_runtime_minutes,
            optimization_goal=optimization_goal,
            top_n=top_n,
        )
        formatted = recommendations.copy()
        numeric_columns = [
            "Predicted Runtime (minutes)",
            "Predicted Cost (USD)",
            "Carbon Intensity",
            "Renewable Percentage",
            "Optimization Score",
        ]
        formatted[numeric_columns] = formatted[numeric_columns].round(4)
        return formatted

    def export_recommendations_csv(
        self,
        recommendations: pd.DataFrame,
        output_path: str | Path,
    ) -> Path:
        """Export ranked recommendations to a CSV file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        recommendations.to_csv(path, index=False)
        return path

    def export_recommendations_json(
        self,
        recommendations: pd.DataFrame,
        output_path: str | Path,
    ) -> Path:
        """Export ranked recommendations to a JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        recommendations.to_json(path, orient="records", indent=2)
        return path

    def _validate_dataset(self) -> None:
        missing = sorted(set(FEATURE_COLUMNS) - set(self.dataset.columns))
        if missing:
            raise ValueError(
                "Recommendation dataset is missing feature columns: "
                f"{', '.join(missing)}"
            )

    def _rank_configurations(
        self,
        dataset_size_mb: float,
        workload_type: str,
        sla_runtime_minutes: float,
        optimization_goal: str,
    ) -> pd.DataFrame:
        goal = self._normalize_goal(optimization_goal)
        candidates = self._build_candidate_frame(dataset_size_mb, workload_type)
        predictions = self.model.predict(candidates[FEATURE_COLUMNS])

        scored = candidates.copy()
        scored["predicted_runtime_minutes"] = np.clip(predictions[:, 0], 0.01, None)
        scored["predicted_cost_usd"] = np.clip(predictions[:, 1], 0.0, None)
        scored["sla_valid"] = scored["predicted_runtime_minutes"] <= sla_runtime_minutes

        score_source = scored.loc[scored["sla_valid"]].copy()
        if score_source.empty:
            score_source = scored.copy()
            no_sla_match = True
        else:
            no_sla_match = False

        score_source["optimization_score"] = self._calculate_score(score_source, goal)
        score_source["recommendation_reason"] = score_source.apply(
            lambda row: self._build_reason(row, goal, no_sla_match),
            axis=1,
        )

        ranked = self._sort_ranked_candidates(score_source, goal)
        ranked["Rank"] = range(1, len(ranked) + 1)
        return self._format_output(ranked)

    def _build_candidate_frame(
        self,
        dataset_size_mb: float,
        workload_type: str,
    ) -> pd.DataFrame:
        workload_rows = self.dataset.loc[self.dataset["workload_type"] == workload_type]
        if workload_rows.empty:
            valid_workloads = sorted(self.dataset["workload_type"].dropna().unique())
            raise ValueError(
                f"Unknown workload_type '{workload_type}'. "
                f"Choose from: {', '.join(valid_workloads)}."
            )

        candidates = workload_rows[CANDIDATE_COLUMNS].drop_duplicates().copy()
        candidates["dataset_size_mb"] = dataset_size_mb
        candidates["workload_type"] = workload_type
        return candidates[FEATURE_COLUMNS].reset_index(drop=True)

    def _calculate_score(
        self,
        candidates: pd.DataFrame,
        goal: OptimizationGoal,
    ) -> pd.Series:
        runtime_score = self._min_max(candidates["predicted_runtime_minutes"])
        cost_score = self._min_max(candidates["predicted_cost_usd"])
        carbon_score = self._min_max(candidates["carbon_intensity_mean"])
        renewable_score = self._min_max(candidates["renewable_percentage_mean"])
        renewable_penalty = 1.0 - renewable_score

        if goal == "cost":
            return cost_score
        if goal == "runtime":
            return runtime_score
        if goal == "carbon":
            return carbon_score + (0.25 * renewable_penalty)
        # Balanced weights as specified in the dissertation methodology:
        # 0.35 runtime + 0.35 cost + 0.20 carbon + 0.10 renewable penalty.
        return (
            (0.35 * runtime_score)
            + (0.35 * cost_score)
            + (0.20 * carbon_score)
            + (0.10 * renewable_penalty)
        )

    def _sort_ranked_candidates(
        self,
        candidates: pd.DataFrame,
        goal: OptimizationGoal,
    ) -> pd.DataFrame:
        tie_breakers = {
            "cost": [
                "optimization_score",
                "predicted_cost_usd",
                "predicted_runtime_minutes",
                "carbon_intensity_mean",
                "renewable_percentage_mean",
            ],
            "runtime": [
                "optimization_score",
                "predicted_runtime_minutes",
                "predicted_cost_usd",
                "carbon_intensity_mean",
                "renewable_percentage_mean",
            ],
            "carbon": [
                "optimization_score",
                "carbon_intensity_mean",
                "renewable_percentage_mean",
                "predicted_cost_usd",
                "predicted_runtime_minutes",
            ],
            "balanced": [
                "optimization_score",
                "predicted_cost_usd",
                "predicted_runtime_minutes",
                "carbon_intensity_mean",
                "renewable_percentage_mean",
            ],
        }
        ascending = [True] * len(tie_breakers[goal])
        if "renewable_percentage_mean" in tie_breakers[goal]:
            renewable_index = tie_breakers[goal].index("renewable_percentage_mean")
            ascending[renewable_index] = False
        sorted_candidates = candidates.sort_values(
            tie_breakers[goal],
            ascending=ascending,
        )
        return sorted_candidates.reset_index(drop=True)

    def _format_output(self, ranked: pd.DataFrame) -> pd.DataFrame:
        output = ranked.rename(
            columns={
                "cloud": "Cloud",
                "region": "Region",
                "machine_type": "Machine Type",
                "nodes": "Nodes",
                "predicted_runtime_minutes": "Predicted Runtime (minutes)",
                "predicted_cost_usd": "Predicted Cost (USD)",
                "carbon_intensity_mean": "Carbon Intensity",
                "renewable_percentage_mean": "Renewable Percentage",
                "optimization_score": "Optimization Score",
                "recommendation_reason": "Recommendation Reason",
            }
        )
        return output[OUTPUT_COLUMNS]

    @staticmethod
    def _normalize_goal(goal: str) -> OptimizationGoal:
        normalized = goal.strip().lower().replace("-", "_")
        normalized = GOAL_ALIASES.get(normalized, normalized)
        if normalized not in {"cost", "runtime", "carbon", "balanced"}:
            raise ValueError(
                "optimization_goal must be one of: cost, runtime, carbon, balanced."
            )
        return normalized  # type: ignore[return-value]

    @staticmethod
    def _min_max(values: pd.Series) -> pd.Series:
        minimum = values.min()
        maximum = values.max()
        if maximum == minimum:
            return pd.Series(0.0, index=values.index)
        return (values - minimum) / (maximum - minimum)

    @staticmethod
    def _build_reason(
        row: pd.Series,
        goal: OptimizationGoal,
        no_sla_match: bool,
    ) -> str:
        sla_note = "No configuration satisfied the SLA; " if no_sla_match else ""
        if goal == "cost":
            reason = "ranked by lowest predicted cost"
        elif goal == "runtime":
            reason = "ranked by fastest predicted runtime"
        elif goal == "carbon":
            reason = "ranked by lowest carbon intensity and higher renewable percentage"
        else:
            reason = (
                "ranked by best trade-off between runtime, cost, carbon, "
                "and renewable energy"
            )
        return f"{sla_note}{reason}."


def compare_recommendations(
    dataset_size_mb: float,
    workload_type: str,
    sla_runtime_minutes: float,
    optimization_goal: str,
    top_n: int = 5,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
) -> pd.DataFrame:
    """Convenience wrapper returning a formatted Top N comparison table."""
    engine = RecommendationEngine(model_path=model_path, dataset_path=dataset_path)
    return engine.compare_recommendations(
        dataset_size_mb=dataset_size_mb,
        workload_type=workload_type,
        sla_runtime_minutes=sla_runtime_minutes,
        optimization_goal=optimization_goal,
        top_n=top_n,
    )


def export_recommendations_csv(
    recommendations: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Export a recommendation DataFrame to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    recommendations.to_csv(path, index=False)
    return path


def export_recommendations_json(
    recommendations: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Export a recommendation DataFrame to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    recommendations.to_json(path, orient="records", indent=2)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rank cloud infrastructure recommendations."
    )
    parser.add_argument("--dataset-size-mb", type=float, required=True)
    parser.add_argument("--workload-type", required=True)
    parser.add_argument("--sla-runtime-minutes", type=float, required=True)
    parser.add_argument(
        "--optimization-goal",
        required=True,
        choices=["cost", "runtime", "carbon", "balanced"],
    )
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--dataset-path", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--csv-output", default=None)
    parser.add_argument("--json-output", default=None)
    args = parser.parse_args()

    engine = RecommendationEngine(args.model_path, args.dataset_path)
    recommendations = engine.recommend_top_n(
        dataset_size_mb=args.dataset_size_mb,
        workload_type=args.workload_type,
        sla_runtime_minutes=args.sla_runtime_minutes,
        optimization_goal=args.optimization_goal,
        top_n=args.top_n,
    )
    print(recommendations.to_string(index=False))

    if args.csv_output:
        engine.export_recommendations_csv(recommendations, args.csv_output)
    if args.json_output:
        engine.export_recommendations_json(recommendations, args.json_output)


if __name__ == "__main__":
    main()
