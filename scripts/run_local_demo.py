"""Run the local demo: train/compare models and print recommendations.

Uses the merged carbon-aware dataset and the RecommendationEngine — the same
path the Streamlit dashboard uses. No cloud access required.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.recommendation_engine import RecommendationEngine
from ml.train_model import compare_models


DATASET_PATH = ROOT / "data" / "models" / "cloud_carbon_model_dataset.csv"
MODELS_DIR = ROOT / "data" / "models"
MODEL_PATH = MODELS_DIR / "best_cloud_model.joblib"


def main() -> None:
    if not DATASET_PATH.exists():
        raise SystemExit(
            f"Merged dataset not found: {DATASET_PATH}\n"
            "Run `python ml/merge_model_dataset.py` first."
        )

    compare_models(str(DATASET_PATH), str(MODELS_DIR), str(MODEL_PATH))

    engine = RecommendationEngine(model_path=MODEL_PATH, dataset_path=DATASET_PATH)
    for goal in ["cost", "runtime", "carbon", "balanced"]:
        print()
        print(f"Top 3 — optimization goal: {goal}")
        recommendations = engine.recommend_top_n(
            dataset_size_mb=500,
            workload_type="cpu-heavy",
            sla_runtime_minutes=6,
            optimization_goal=goal,
            top_n=3,
        )
        print(recommendations.to_string(index=False))


if __name__ == "__main__":
    main()
