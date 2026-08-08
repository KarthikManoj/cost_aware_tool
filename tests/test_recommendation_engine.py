from __future__ import annotations

import pandas as pd
import pytest

from ml.recommendation_engine import RecommendationEngine


@pytest.fixture
def engine() -> RecommendationEngine:
    # Skip __init__ so we don't need a real model/dataset on disk.
    return object.__new__(RecommendationEngine)


@pytest.fixture
def multi_row_candidates() -> pd.DataFrame:
    """Four candidates with varied runtime/cost/emissions/renewable values."""
    return pd.DataFrame(
        {
            "candidate_id": ["A", "B", "C", "D"],
            "predicted_runtime_minutes": [2.0, 5.0, 1.0, 8.0],
            "predicted_cost_usd": [4.0, 1.0, 6.0, 0.5],
            "predicted_emissions_gco2eq": [3.0, 2.0, 9.0, 1.0],
            "carbon_intensity_mean": [500.0, 300.0, 700.0, 200.0],
            "renewable_percentage_mean": [20.0, 60.0, 5.0, 80.0],
            "cloud": ["aws", "azure", "aws", "azure"],
            "region": ["us-east-1", "central-india", "us-west-2", "southeast-asia"],
            "machine_type": ["m5.large", "d2as", "m5.xlarge", "d4s"],
            "nodes": [2, 4, 1, 4],
        }
    )


@pytest.mark.parametrize(
    "goal, expected_scores, expected_order",
    [
        (
            "cost",
            [0.6363636363636364, 0.09090909090909091, 1.0, 0.0],
            ["D", "B", "A", "C"],
        ),
        (
            "runtime",
            [0.14285714285714285, 0.5714285714285714, 0.0, 1.0],
            ["C", "A", "B", "D"],
        ),
        (
            "carbon",
            [0.45, 0.19166666666666668, 1.25, 0.0],
            ["D", "B", "A", "C"],
        ),
    ],
)
def test_calculate_score_and_sort_unchanged_for_published_goals(
    engine: RecommendationEngine,
    multi_row_candidates: pd.DataFrame,
    goal: str,
    expected_scores: list[float],
    expected_order: list[str],
) -> None:
    """cost/runtime/carbon scores and ordering must never change."""
    score = engine._calculate_score(multi_row_candidates, goal)
    assert list(score) == pytest.approx(expected_scores)

    scored = multi_row_candidates.copy()
    scored["optimization_score"] = score
    ranked = engine._sort_ranked_candidates(scored, goal)
    assert ranked["candidate_id"].tolist() == expected_order


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
            "predicted_emissions_gco2eq": [10.0, 20.0],
            "carbon_intensity_mean": [100.0, 200.0],
            "renewable_percentage_mean": [50.0, 10.0],
        }
    )
    score = engine._calculate_score(candidates, "cost")
    assert list(score) == [0.0, 1.0]


def test_calculate_score_balanced_is_l2_distance_to_ideal(engine: RecommendationEngine) -> None:
    """Balanced score is the L2 distance from the ideal point."""
    candidates = pd.DataFrame(
        {
            "predicted_runtime_minutes": [1.0, 2.0],
            "predicted_cost_usd": [1.0, 2.0],
            "predicted_emissions_gco2eq": [1.0, 2.0],
            "renewable_percentage_mean": [100.0, 0.0],
        }
    )
    score = engine._calculate_score(candidates, "balanced")
    assert score.iloc[0] == pytest.approx(0.0)
    assert score.iloc[1] == pytest.approx((0.35 + 0.35 + 0.20 + 0.10) ** 0.5)


def test_calculate_score_balanced_prefers_compromise_over_single_axis_extreme(
    engine: RecommendationEngine,
) -> None:
    """A middling compromise (row 1) should beat either extreme."""
    candidates = pd.DataFrame(
        {
            "predicted_runtime_minutes": [1.0, 5.0, 10.0],
            "predicted_cost_usd": [10.0, 5.0, 1.0],
            "predicted_emissions_gco2eq": [10.0, 5.0, 1.0],
            "renewable_percentage_mean": [0.0, 50.0, 100.0],
        }
    )
    score = engine._calculate_score(candidates, "balanced")
    assert score.idxmin() == 1


def test_ratio_to_best_scales_proportional_to_the_optimum() -> None:
    scaled = RecommendationEngine._ratio_to_best(pd.Series([10.0, 15.0, 20.0]))
    assert list(scaled) == pytest.approx([0.0, 0.5, 1.0])


def test_ratio_to_best_higher_is_better_scales_shortfall_from_the_optimum() -> None:
    scaled = RecommendationEngine._ratio_to_best(
        pd.Series([100.0, 75.0, 50.0]), higher_is_better=True
    )
    assert list(scaled) == pytest.approx([0.0, 0.25, 0.5])


def test_ratio_to_best_falls_back_to_min_max_when_optimum_is_non_positive() -> None:
    """Falls back to min-max instead of dividing by zero."""
    scaled = RecommendationEngine._ratio_to_best(pd.Series([0.0, 5.0, 10.0]))
    assert list(scaled) == pytest.approx([0.0, 0.5, 1.0])


def test_calculate_score_balanced_uses_ratio_to_best_not_min_max(
    engine: RecommendationEngine,
) -> None:
    """An outlier candidate (O) shouldn't skew the pick between X and Y."""
    candidates = pd.DataFrame(
        {
            "predicted_runtime_minutes": [1.0, 1.5, 5.0],  # X, Y, O (outlier)
            "predicted_cost_usd": [2.0, 1.0, 100.0],
            "predicted_emissions_gco2eq": [1.0, 1.0, 1.0],
            "renewable_percentage_mean": [50.0, 50.0, 50.0],
        }
    )
    score = engine._calculate_score(candidates, "balanced")
    assert score.iloc[0] == pytest.approx(0.5916079783)  # X
    assert score.iloc[1] == pytest.approx(0.2958039892)  # Y
    assert score.idxmin() == 1  # Y (the fair pick), not X (min-max's pick)


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


def test_sort_ranked_candidates_balanced_goal_orders_by_emissions_then_cost_then_runtime(
    engine: RecommendationEngine,
) -> None:
    """On a score tie, balanced breaks ties by lowest emissions first."""
    candidates = pd.DataFrame(
        {
            "optimization_score": [0.0, 0.0],
            "predicted_emissions_gco2eq": [2.0, 1.0],
            "predicted_cost_usd": [1.0, 1.0],
            "predicted_runtime_minutes": [1.0, 1.0],
            "cloud": ["aws", "aws"],
            "region": ["us-east-1", "us-east-1"],
            "machine_type": ["m5.large", "m5.large"],
            "nodes": [2, 2],
        }
    )
    ranked = engine._sort_ranked_candidates(candidates, "balanced")
    assert ranked["predicted_emissions_gco2eq"].tolist() == [1.0, 2.0]


def test_sort_ranked_candidates_balanced_goal_falls_back_to_cost_then_runtime(
    engine: RecommendationEngine,
) -> None:
    candidates = pd.DataFrame(
        {
            "optimization_score": [0.0, 0.0],
            "predicted_emissions_gco2eq": [1.0, 1.0],
            "predicted_cost_usd": [2.0, 1.0],
            "predicted_runtime_minutes": [5.0, 1.0],
            "cloud": ["aws", "aws"],
            "region": ["us-east-1", "us-east-1"],
            "machine_type": ["m5.large", "m5.large"],
            "nodes": [2, 2],
        }
    )
    ranked = engine._sort_ranked_candidates(candidates, "balanced")
    assert ranked["predicted_cost_usd"].tolist() == [1.0, 2.0]


def test_sort_ranked_candidates_balanced_goal_uses_deterministic_key_as_last_resort(
    engine: RecommendationEngine,
) -> None:
    """Full tie falls back to a deterministic key so order is reproducible."""
    candidates = pd.DataFrame(
        {
            "optimization_score": [0.0, 0.0],
            "predicted_emissions_gco2eq": [1.0, 1.0],
            "predicted_cost_usd": [1.0, 1.0],
            "predicted_runtime_minutes": [1.0, 1.0],
            "cloud": ["azure", "aws"],
            "region": ["us-east-1", "us-east-1"],
            "machine_type": ["m5.large", "m5.large"],
            "nodes": [2, 2],
        }
    )
    ranked = engine._sort_ranked_candidates(candidates, "balanced")
    assert ranked["cloud"].tolist() == ["aws", "azure"]
