"""Recommend the cheapest infrastructure configuration satisfying an SLA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing import FEATURE_COLUMNS


ALLOWED_CATEGORIES_BY_WORKLOAD = {
    "cpu-heavy": {"general", "compute"},
    "memory-heavy": {"general", "memory"},
    "io-heavy": {"general", "storage"},
}


def load_candidates(candidate_path: str, price_path: str) -> pd.DataFrame:
    candidates = pd.read_csv(candidate_path)
    prices = pd.read_csv(price_path)[["instance_type", "hourly_price_usd", "category", "vcpus", "memory_gb"]]
    merged = candidates.merge(prices, on="instance_type", how="left")
    missing = merged.loc[merged["hourly_price_usd"].isna(), "instance_type"].unique()
    if len(missing):
        raise ValueError(f"Missing prices for candidate instances: {', '.join(missing)}")
    return merged


def recommend(
    dataset_size_mb: float,
    workload_type: str,
    sla_minutes: float,
    model_path: str,
    candidate_path: str,
    price_path: str,
) -> dict:
    model = joblib.load(model_path)
    candidates = load_candidates(candidate_path, price_path)
    allowed_categories = ALLOWED_CATEGORIES_BY_WORKLOAD.get(workload_type)
    if allowed_categories:
        candidates = candidates.loc[candidates["category"].isin(allowed_categories)].reset_index(drop=True)
    prediction_frame = candidates[["instance_type", "nodes"]].copy()
    prediction_frame["dataset_size_mb"] = dataset_size_mb
    prediction_frame["workload_type"] = workload_type
    prediction_frame = prediction_frame[FEATURE_COLUMNS]

    predictions = model.predict(prediction_frame)
    scored = candidates.copy()
    scored["predicted_runtime_minutes"] = predictions[:, 0].clip(min=0.01)
    scored["predicted_cost_usd"] = (
        scored["hourly_price_usd"] * scored["nodes"] * (scored["predicted_runtime_minutes"] / 60.0)
    )
    scored["model_predicted_cost_usd"] = predictions[:, 1].clip(min=0.0)
    scored["sla_valid"] = scored["predicted_runtime_minutes"] <= sla_minutes

    valid = scored.loc[scored["sla_valid"]].sort_values(
        ["predicted_cost_usd", "predicted_runtime_minutes", "nodes"]
    )
    if valid.empty:
        fastest = scored.sort_values("predicted_runtime_minutes").iloc[0]
        return {
            "status": "no_valid_configuration",
            "message": "No candidate satisfies the SLA. Returning fastest predicted configuration.",
            "recommendation": fastest.to_dict(),
            "candidates": scored.sort_values("predicted_runtime_minutes").to_dict(orient="records"),
        }

    best = valid.iloc[0]
    return {
        "status": "ok",
        "recommendation": best.to_dict(),
        "candidates": scored.sort_values(["sla_valid", "predicted_cost_usd"], ascending=[False, True]).to_dict(
            orient="records"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend cheapest SLA-valid infrastructure.")
    parser.add_argument("--dataset-size-mb", type=float, required=True)
    parser.add_argument("--workload-type", required=True, choices=["cpu-heavy", "memory-heavy", "io-heavy"])
    parser.add_argument("--sla-minutes", type=float, required=True)
    parser.add_argument("--model-path", default="data/models/performance_model.joblib")
    parser.add_argument("--candidate-path", default="config/candidate_configurations.csv")
    parser.add_argument("--price-path", default="config/instance_prices.csv")
    args = parser.parse_args()

    result = recommend(
        args.dataset_size_mb,
        args.workload_type,
        args.sla_minutes,
        args.model_path,
        args.candidate_path,
        args.price_path,
    )
    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
