"""Streamlit dashboard for the cost/carbon-aware multi-cloud Spark advisor.
Wraps RecommendationEngine directly -- no hardcoded machine list."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.preprocessing import TARGET_COLUMNS
from ml.recommendation_engine import RecommendationEngine
from ml.train_model import MODEL_REGISTRY, compare_models, cross_validate_models


DATASET_PATH = ROOT / "data" / "models" / "cloud_carbon_model_dataset.csv"
MODELS_DIR = ROOT / "data" / "models"
MODEL_PATH = ROOT / "data" / "models" / "best_cloud_model.joblib"
MODEL_COMPARISON_PATH = ROOT / "data" / "models" / "model_comparison.json"
FEATURE_IMPORTANCE_PATH = ROOT / "data" / "models" / "feature_importance.json"
CROSS_VALIDATION_PATH = ROOT / "data" / "models" / "cross_validation_metrics.json"

OPTIMIZATION_GOALS = ["balanced", "cost", "runtime", "carbon"]
NO_SLA_MATCH_PREFIX = "No configuration satisfied the SLA"


st.set_page_config(page_title="Cost & Carbon-Aware Multi-Cloud Spark Advisor", layout="wide")


@st.cache_resource
def load_engine(version: int) -> RecommendationEngine:
    """version is part of the cache key so retraining forces a reload."""
    return RecommendationEngine(model_path=MODEL_PATH, dataset_path=DATASET_PATH)


def load_comparison_table() -> dict | None:
    comparison = st.session_state.get("last_comparison")
    if comparison is not None:
        return comparison
    if MODEL_COMPARISON_PATH.exists():
        return json.loads(MODEL_COMPARISON_PATH.read_text(encoding="utf-8"))
    return None


if "model_version" not in st.session_state:
    st.session_state.model_version = 0

st.title("Cost & Carbon-Aware Multi-Cloud Spark Infrastructure Advisor")
st.caption(
    "Predicts Apache Spark runtime and cost across AWS and Azure, then ranks "
    "infrastructure configurations by cost, runtime, carbon intensity, or a "
    "balanced trade-off between all four factors."
)

if not DATASET_PATH.exists():
    st.error(
        f"Training dataset not found at {DATASET_PATH}. "
        "Run `python ml/merge_model_dataset.py` first."
    )
    st.stop()

if not MODEL_PATH.exists():
    st.warning(f"No trained model found at {MODEL_PATH}. Training one now...")
    with st.spinner("Training and comparing linear regression, decision tree, random forest, gradient boosting..."):
        st.session_state.last_comparison = compare_models(str(DATASET_PATH), str(MODELS_DIR), str(MODEL_PATH))
    st.session_state.model_version += 1

engine = load_engine(st.session_state.model_version)

controls, results = st.columns([0.30, 0.70], gap="large")

with controls:
    st.subheader("Workload")
    workload_options = sorted(engine.dataset["workload_type"].dropna().unique().tolist())
    default_workload_index = workload_options.index("cpu-heavy") if "cpu-heavy" in workload_options else 0

    dataset_size_mb = st.number_input("Dataset size (MB)", min_value=10.0, max_value=20000.0, value=500.0, step=50.0)
    workload_type = st.selectbox("Workload type", workload_options, index=default_workload_index)
    sla_minutes = st.number_input("SLA target (minutes)", min_value=0.1, max_value=240.0, value=6.0, step=0.5)
    optimization_goal = st.selectbox("Optimization goal", OPTIMIZATION_GOALS, format_func=str.title)
    top_n = st.slider("Top N recommendations", min_value=3, max_value=15, value=5)

    st.divider()
    st.subheader("Model")
    st.caption("Retrains and compares all four models, then keeps the highest-R2 / lowest-RMSE model as the active predictor.")
    if st.button("Retrain & compare all models", use_container_width=True):
        with st.spinner("Training linear regression, decision tree, random forest, gradient boosting..."):
            st.session_state.last_comparison = compare_models(str(DATASET_PATH), str(MODELS_DIR), str(MODEL_PATH))
        st.session_state.model_version += 1
        st.success("Retrained. Best model saved to best_cloud_model.joblib.")
        st.rerun()

    st.caption(
        "Cross-validation gives mean +/- std R2/RMSE across grouped folds "
        "instead of a single holdout split — more defensible for reporting."
    )
    if st.button("Run cross-validation", use_container_width=True):
        with st.spinner("Running grouped 5-fold cross-validation for all four models..."):
            st.session_state.last_cv = cross_validate_models(str(DATASET_PATH), str(CROSS_VALIDATION_PATH))
        st.success("Cross-validation complete.")

try:
    recommendations = engine.recommend_top_n(
        dataset_size_mb=dataset_size_mb,
        workload_type=workload_type,
        sla_runtime_minutes=sla_minutes,
        optimization_goal=optimization_goal,
        top_n=top_n,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

no_sla_match = recommendations["Recommendation Reason"].str.startswith(NO_SLA_MATCH_PREFIX).any()

with results:
    st.subheader(f"Top {len(recommendations)} recommendations — optimizing for {optimization_goal.title()}")
    if no_sla_match:
        st.warning("No candidate configuration satisfies the SLA. Showing the fastest available configurations instead.")

    best = recommendations.iloc[0]
    metric_cols = st.columns(5)
    metric_cols[0].metric("Cloud", best["Cloud"])
    metric_cols[1].metric("Region", best["Region"])
    metric_cols[2].metric("Machine x Nodes", f"{best['Machine Type']} x {int(best['Nodes'])}")
    metric_cols[3].metric("Runtime", f"{best['Predicted Runtime (minutes)']:.2f} min")
    metric_cols[4].metric("Cost", f"${best['Predicted Cost (USD)']:.4f}")
    st.caption(f"Rank 1 reason: {best['Recommendation Reason']}")

    st.dataframe(recommendations, use_container_width=True, hide_index=True)

    export_cols = st.columns(2)
    with export_cols[0]:
        st.download_button(
            "Download recommendations (CSV)",
            recommendations.to_csv(index=False),
            file_name=f"recommendations_{workload_type}_{optimization_goal}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with export_cols[1]:
        st.download_button(
            "Download recommendations (JSON)",
            recommendations.to_json(orient="records", indent=2),
            file_name=f"recommendations_{workload_type}_{optimization_goal}.json",
            mime="application/json",
            use_container_width=True,
        )

    chart_cols = st.columns(2)
    with chart_cols[0]:
        fig = px.scatter(
            recommendations,
            x="Predicted Cost (USD)",
            y="Predicted Runtime (minutes)",
            color="Cloud",
            size="Optimization Score",
            hover_data=["Region", "Machine Type", "Nodes", "Recommendation Reason"],
            labels={
                "Predicted Cost (USD)": "Predicted cost (USD)",
                "Predicted Runtime (minutes)": "Predicted runtime (minutes)",
            },
        )
        fig.add_hline(y=sla_minutes, line_dash="dash", line_color="red", annotation_text="SLA")
        st.plotly_chart(fig, use_container_width=True)

    with chart_cols[1]:
        fig = px.bar(
            recommendations.sort_values("Rank"),
            x="Rank",
            y="Optimization Score",
            color="Cloud",
            hover_data=["Region", "Machine Type", "Nodes"],
            labels={"Optimization Score": "Optimization score (lower is better)"},
        )
        st.plotly_chart(fig, use_container_width=True)

    chart_cols2 = st.columns(2)
    with chart_cols2[0]:
        fig = px.scatter(
            recommendations,
            x="Carbon Intensity",
            y="Renewable Percentage",
            color="Cloud",
            size="Predicted Cost (USD)",
            hover_data=["Region", "Machine Type", "Nodes"],
        )
        st.plotly_chart(fig, use_container_width=True)
    with chart_cols2[1]:
        fig = px.bar(
            recommendations.sort_values("Rank"),
            x="Rank",
            y="Predicted Cost (USD)",
            color="Predicted Runtime (minutes)",
            hover_data=["Cloud", "Region", "Machine Type", "Nodes"],
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Model Comparison")

comparison = load_comparison_table()
if comparison:
    rows = []
    for model_key, metrics in comparison.items():
        rows.append(
            {
                "Model": MODEL_REGISTRY[model_key]["label"],
                "Runtime R2": metrics["runtime_minutes"]["r2"],
                "Runtime RMSE": metrics["runtime_minutes"]["rmse"],
                "Cost R2": metrics["cost_usd"]["r2"],
                "Cost RMSE": metrics["cost_usd"]["rmse"],
                "Average R2": metrics["average_r2"],
                "Average RMSE": metrics["average_rmse"],
            }
        )
    comparison_df = pd.DataFrame(rows).sort_values("Average R2", ascending=False).reset_index(drop=True)
    st.success(f"Best model: {comparison_df.iloc[0]['Model']} (highest average R2, lowest average RMSE)")
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
    st.plotly_chart(
        px.bar(
            comparison_df,
            x="Model",
            y="Average R2",
            color="Model",
            title="Model comparison — average R2 across runtime and cost targets",
        ),
        use_container_width=True,
    )
else:
    st.info("No model comparison found yet. Click 'Retrain & compare all models'.")

st.divider()
st.subheader("Cross-Validation")

cv_summary = st.session_state.get("last_cv")
if cv_summary is None and CROSS_VALIDATION_PATH.exists():
    cv_summary = json.loads(CROSS_VALIDATION_PATH.read_text(encoding="utf-8"))

if cv_summary:
    cv_rows = []
    for model_key, target_metrics in cv_summary.items():
        row = {"Model": MODEL_REGISTRY[model_key]["label"], "Folds": target_metrics.get("folds")}
        for target in TARGET_COLUMNS:
            label = "Runtime" if target == "runtime_minutes" else "Cost"
            row[f"{label} R2 (mean +/- std)"] = (
                f"{target_metrics[target]['r2']['mean']:.4f} +/- {target_metrics[target]['r2']['std']:.4f}"
            )
            row[f"{label} RMSE (mean +/- std)"] = (
                f"{target_metrics[target]['rmse']['mean']:.4f} +/- {target_metrics[target]['rmse']['std']:.4f}"
            )
        cv_rows.append(row)
    st.dataframe(pd.DataFrame(cv_rows), use_container_width=True, hide_index=True)
else:
    st.info("No cross-validation results yet. Click 'Run cross-validation'.")

st.divider()
st.subheader("Feature Importance")

feature_importance = None
if FEATURE_IMPORTANCE_PATH.exists():
    feature_importance = json.loads(FEATURE_IMPORTANCE_PATH.read_text(encoding="utf-8"))

if feature_importance:
    importance_target = st.selectbox(
        "Target",
        list(feature_importance.keys()),
        format_func=lambda t: "Runtime (minutes)" if t == "runtime_minutes" else "Cost (USD)",
    )
    importance_df = (
        pd.DataFrame(
            {
                "Feature": list(feature_importance[importance_target].keys()),
                "Importance": list(feature_importance[importance_target].values()),
            }
        )
        .head(15)
        .sort_values("Importance", ascending=True)
    )
    st.plotly_chart(
        px.bar(
            importance_df,
            x="Importance",
            y="Feature",
            orientation="h",
            title=f"Top features driving predicted {importance_target.replace('_', ' ')} (best model, from last retrain)",
        ),
        use_container_width=True,
    )
else:
    st.info(
        "No feature importance available yet — it's saved automatically the next time "
        "'Retrain & compare all models' picks a tree-based best model."
    )
