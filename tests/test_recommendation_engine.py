from __future__ import annotations

import pandas as pd
import pytest

from ml.recommendation_engine import RecommendationEngine


@pytest.fixture
def engine() -> RecommendationEngine:
    # Bypass __init__ (which loads a joblib model + CSV dataset from disk)
    # since these tests only exercise the pure ranking/scoring logic, none of
    # which touches self.model or self.dataset.
    return object.__new__(RecommendationEngine)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("cost", "cost"),
        ("Lowest Cost", "cost"),
        ("fastest", "runtime"),
        ("lowest_carbon", "carbon"),
        ("balance", "balanced"),
        ("BALANCED", "balanced"),
    ],
)
def test_normalize_goal_accepts_aliases(raw: str, expected: str) -> None:
    assert RecommendationEngine._normalize_goal(raw) == expected


def test_normalize_goal_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        RecommendationEngine._normalize_goal("cheapest-ever")


def test_min_max_scales_between_zero_and_one() -> None:
    scaled = RecommendationEngine._min_max(pd.Series([10, 20, 30]))
    assert list(scaled) == [0.0, 0.5, 1.0]


def test_min_max_constant_series_returns_zero() -> None:
    scaled = RecommendationEngine._min_max(pd.Series([5, 5, 5]))
    assert list(scaled) == [0.0, 0.0, 0.0]


def test_calculate_score_cost_goal_equals_cost_score(engine: RecommendationEngine) -> None:
    candidates = pd.DataFrame(
        {
            "predicted_runtime_minutes": [5.0, 10.0],
            "predicted_cost_usd": [1.0, 2.0],
            "carbon_intensity_mean": [100.0, 200.0],
            "renewable_percentage_mean": [50.0, 10.0],
        }
    )
    score = engine._calculate_score(candidates, "cost")
    assert list(score) == [0.0, 1.0]


def test_calculate_score_balanced_matches_documented_weights(engine: RecommendationEngine) -> None:
    """Regression test for the balanced-score weight fix: the dissertation
    specifies 0.35 runtime + 0.35 cost + 0.20 carbon + 0.10 renewable
    penalty. Rows are chosen so every normalized sub-score is exactly 0 or 1,
    making the weighted sum trivial to hand-verify."""
    candidates = pd.DataFrame(
        {
            "predicted_runtime_minutes": [1.0, 2.0],
            "predicted_cost_usd": [1.0, 2.0],
            "carbon_intensity_mean": [1.0, 2.0],
            "renewable_percentage_mean": [100.0, 0.0],
        }
    )
    score = engine._calculate_score(candidates, "balanced")
    assert score.iloc[0] == pytest.approx(0.0)
    assert score.iloc[1] == pytest.approx(0.35 + 0.35 + 0.20 + 0.10)


def test_build_reason_notes_missing_sla_match(engine: RecommendationEngine) -> None:
    row = pd.Series({"predicted_cost_usd": 1.0})
    reason = engine._build_reason(row, "cost", no_sla_match=True)
    assert reason.startswith("No configuration satisfied the SLA")


def test_sort_ranked_candidates_cost_goal_orders_by_score_then_cost(engine: RecommendationEngine) -> None:
    candidates = pd.DataFrame(
        {
            "optimization_score": [0.0, 0.0],
            "predicted_cost_usd": [2.0, 1.0],
            "predicted_runtime_minutes": [1.0, 1.0],
            "carbon_intensity_mean": [1.0, 1.0],
            "renewable_percentage_mean": [50.0, 50.0],
        }
    )
    ranked = engine._sort_ranked_candidates(candidates, "cost")
    assert ranked["predicted_cost_usd"].tolist() == [1.0, 2.0]
