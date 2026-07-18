"""Run the local non-AWS demo: train a model and print one recommendation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.optimizer import recommend
from ml.train_model import train


def main() -> None:
    performance_path = ROOT / "data" / "performance" / "sample_performance_dataset.csv"
    model_path = ROOT / "data" / "models" / "performance_model.joblib"
    metrics_path = ROOT / "data" / "models" / "model_metrics.json"

    metrics = train(str(performance_path), str(model_path), str(metrics_path), "random_forest")
    print("Model metrics:")
    print(json.dumps(metrics, indent=2))

    result = recommend(
        dataset_size_mb=1024,
        workload_type="cpu-heavy",
        sla_minutes=12,
        model_path=str(model_path),
        candidate_path=str(ROOT / "config" / "candidate_configurations.csv"),
        price_path=str(ROOT / "config" / "instance_prices.csv"),
    )
    print("Recommendation:")
    print(json.dumps(result["recommendation"], indent=2, default=float))


if __name__ == "__main__":
    main()
