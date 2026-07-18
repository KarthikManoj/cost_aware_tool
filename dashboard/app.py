"""Streamlit dashboard for cost-aware Spark infrastructure recommendations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.optimizer import recommend
from ml.train_model import train


CLEANED_PERFORMANCE_PATH = ROOT / "data" / "performance" / "cleaned_data" / "cleaned_dataset.csv"
PERFORMANCE_PATH = ROOT / "data" / "performance" / "performance_dataset.csv"
SAMPLE_PERFORMANCE_PATH = ROOT / "data" / "performance" / "sample_performance_dataset.csv"
MODEL_PATH = ROOT / "data" / "models" / "performance_model.joblib"
METRICS_PATH = ROOT / "data" / "models" / "model_metrics.json"
MODEL_COMPARISON_PATH = ROOT / "data" / "models" / "model_comparison.json"
CANDIDATE_PATH = ROOT / "config" / "candidate_configurations.csv"
PRICE_PATH = ROOT / "config" / "instance_prices.csv"


st.set_page_config(page_title="Cost-Aware Spark Infrastructure Advisor", layout="wide")


@st.cache_data
def load_performance_data() -> pd.DataFrame:
    if CLEANED_PERFORMANCE_PATH.exists():
        path = CLEANED_PERFORMANCE_PATH
    elif PERFORMANCE_PATH.exists():
        path = PERFORMANCE_PATH
    else:
        path = SAMPLE_PERFORMANCE_PATH
    return pd.read_csv(path)


def ensure_model(data_path: Path) -> None:
    if not MODEL_PATH.exists():
        train(str(data_path), str(MODEL_PATH), str(METRICS_PATH), "random_forest")


data_path = CLEANED_PERFORMANCE_PATH if CLEANED_PERFORMANCE_PATH.exists() else PERFORMANCE_PATH if PERFORMANCE_PATH.exists() else SAMPLE_PERFORMANCE_PATH
data = load_performance_data()
ensure_model(data_path)

st.title("Cost-Aware Spark Infrastructure Advisor")

controls, recommendation_panel = st.columns([0.32, 0.68], gap="large")

with controls:
    st.subheader("Workload Input")
    dataset_size_mb = st.number_input("Dataset size (MB)", min_value=10.0, max_value=20000.0, value=1024.0, step=100.0)
    workload_type = st.selectbox("Workload type", ["cpu-heavy", "memory-heavy", "io-heavy"])
    sla_minutes = st.number_input("SLA target (minutes)", min_value=0.5, max_value=240.0, value=15.0, step=0.5)

    if st.button("Retrain model", use_container_width=True):
        metrics = train(str(data_path), str(MODEL_PATH), str(METRICS_PATH), "random_forest")
        st.success("Model retrained")
        st.json(metrics)

with recommendation_panel:
    result = recommend(
        dataset_size_mb=dataset_size_mb,
        workload_type=workload_type,
        sla_minutes=sla_minutes,
        model_path=str(MODEL_PATH),
        candidate_path=str(CANDIDATE_PATH),
        price_path=str(PRICE_PATH),
    )
    rec = result["recommendation"]
    status_text = "Cheapest SLA-valid configuration" if result["status"] == "ok" else "Fastest available configuration"
    st.subheader(status_text)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Instance type", rec["instance_type"])
    metric_cols[1].metric("Nodes", int(rec["nodes"]))
    metric_cols[2].metric("Runtime", f"{rec['predicted_runtime_minutes']:.2f} min")
    metric_cols[3].metric("Cost", f"${rec['predicted_cost_usd']:.4f}")

    if result["status"] != "ok":
        st.warning(result["message"])

    candidates = pd.DataFrame(result["candidates"])
    candidates["configuration"] = candidates["instance_type"] + " x " + candidates["nodes"].astype(str)

    chart_cols = st.columns(2)
    with chart_cols[0]:
        fig = px.scatter(
            candidates,
            x="predicted_cost_usd",
            y="predicted_runtime_minutes",
            color="sla_valid",
            hover_data=["instance_type", "nodes", "category"],
            labels={
                "predicted_cost_usd": "Predicted cost (USD)",
                "predicted_runtime_minutes": "Predicted runtime (minutes)",
                "sla_valid": "SLA valid",
            },
        )
        fig.add_hline(y=sla_minutes, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)

    with chart_cols[1]:
        top = candidates.sort_values("predicted_cost_usd").head(10)
        fig = px.bar(
            top,
            x="configuration",
            y="predicted_cost_usd",
            color="predicted_runtime_minutes",
            labels={"configuration": "Configuration", "predicted_cost_usd": "Cost (USD)"},
        )
        st.plotly_chart(fig, use_container_width=True)

tabs = st.tabs(["Experiment Data", "EDA", "Model Metrics", "Candidate Predictions"])

with tabs[0]:
    st.dataframe(data, use_container_width=True)
    st.plotly_chart(
        px.scatter(
            data,
            x="nodes",
            y="runtime_minutes",
            color="instance_type",
            facet_col="workload_type",
            size="dataset_size_mb",
            labels={"runtime_minutes": "Runtime (minutes)", "nodes": "Nodes"},
        ),
        use_container_width=True,
    )

with tabs[1]:
    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(
            px.line(
                data.sort_values("dataset_size_mb"),
                x="dataset_size_mb",
                y="runtime_minutes",
                color="workload_type",
                line_dash="instance_type",
                markers=True,
                facet_col="nodes",
                labels={"dataset_size_mb": "Dataset size (MB)", "runtime_minutes": "Runtime (minutes)"},
            ),
            use_container_width=True,
        )
    with chart_cols[1]:
        st.plotly_chart(
            px.scatter(
                data,
                x="runtime_minutes",
                y="cost_usd",
                color="workload_type",
                symbol="instance_type",
                size="dataset_size_mb",
                hover_data=["nodes"],
                labels={"runtime_minutes": "Runtime (minutes)", "cost_usd": "Cost (USD)"},
            ),
            use_container_width=True,
        )

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(
            px.box(
                data,
                x="workload_type",
                y="runtime_minutes",
                color="instance_type",
                labels={"workload_type": "Workload", "runtime_minutes": "Runtime (minutes)"},
            ),
            use_container_width=True,
        )
    with chart_cols[1]:
        st.plotly_chart(
            px.bar(
                data.groupby(["workload_type", "instance_type"], as_index=False)["cost_usd"].mean(),
                x="workload_type",
                y="cost_usd",
                color="instance_type",
                barmode="group",
                labels={"workload_type": "Workload", "cost_usd": "Average cost (USD)"},
            ),
            use_container_width=True,
        )

with tabs[2]:
    if METRICS_PATH.exists():
        st.json(json.loads(METRICS_PATH.read_text(encoding="utf-8")))
    else:
        st.info("Train the model to generate metrics.")
    if MODEL_COMPARISON_PATH.exists():
        st.subheader("Model Comparison")
        st.json(json.loads(MODEL_COMPARISON_PATH.read_text(encoding="utf-8")))

with tabs[3]:
    display_cols = [
        "instance_type",
        "nodes",
        "category",
        "predicted_runtime_minutes",
        "predicted_cost_usd",
        "sla_valid",
    ]
    st.dataframe(candidates[display_cols], use_container_width=True)
