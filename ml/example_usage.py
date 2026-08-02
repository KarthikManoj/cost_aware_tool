"""Example recommendation scenarios for dissertation evaluation."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.recommendation_engine import RecommendationEngine


OUTPUT_DIR = ROOT / "data/models/recommendation_examples"


def main() -> None:
    engine = RecommendationEngine()

    scenario = {
        "dataset_size_mb": 500,
        "workload_type": "cpu-heavy",
        "sla_runtime_minutes": 6,
        "top_n": 5,
    }

    for goal in ["cost", "runtime", "carbon", "balanced"]:
        print("=" * 80)
        print(f"Optimization Goal: {goal.title()}")
        print("=" * 80)

        recommendations = engine.recommend_top_n(
            optimization_goal=goal,
            **scenario,
        )
        print(recommendations.to_string(index=False))
        print()

        engine.export_recommendations_csv(
            recommendations,
            OUTPUT_DIR / f"top_5_{goal}_recommendations.csv",
        )
        engine.export_recommendations_json(
            recommendations,
            OUTPUT_DIR / f"top_5_{goal}_recommendations.json",
        )

    best_balanced = engine.recommend(
        dataset_size_mb=scenario["dataset_size_mb"],
        workload_type=scenario["workload_type"],
        sla_runtime_minutes=scenario["sla_runtime_minutes"],
        optimization_goal="balanced",
    )
    print("Best Balanced Recommendation")
    print(best_balanced.to_string())

"""
    df = engine.dataset
    print(df["cloud"].value_counts())
    print(df.groupby("cloud")[["runtime_minutes", "cost_usd"]].mean())
"""

if __name__ == "__main__":
    main()

