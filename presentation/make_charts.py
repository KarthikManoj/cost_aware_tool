"""Generate the custom figures for the viva deck.

Every number here is read from the repository's own result artefacts —
nothing is hand-entered except labels.
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

REPO = "/sessions/modest-exciting-carson/mnt/cost-aware-infrastructure-optimization"
OUT = "/sessions/modest-exciting-carson/mnt/outputs/build/img"

INK = "#16261E"
TEAL = "#3E6B55"
MOSS = "#9DC48A"
AMBER = "#8A7A63"
GREY = "#5F6B64"
LIGHT = "#F1F4F1"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": GREY,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": GREY,
    "ytick.color": GREY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


# ---------------------------------------------------------------- figure 1
# Predicted vs actual runtime, deployed Random Forest, held-out group split.
def predicted_vs_actual():
    df = pd.read_csv(f"{REPO}/data/models/prediction_comparison.csv")
    df = df[df["model"] == "Random Forest"]  # the deployed model
    cols = {c.lower(): c for c in df.columns}
    act = cols.get("actual_runtime_minutes") or cols.get("runtime_minutes_actual")
    pred = cols.get("predicted_runtime_minutes") or cols.get("runtime_minutes_predicted")
    if act is None or pred is None:
        print("prediction_comparison.csv columns:", list(df.columns))
        raise SystemExit("column names not found")

    fig, ax = plt.subplots(figsize=(5.6, 4.4), dpi=200)
    ax.scatter(df[act], df[pred], s=13, alpha=0.34, color=TEAL,
               edgecolors="none", zorder=3)
    lim = [0, max(df[act].max(), df[pred].max()) * 1.04]
    ax.plot(lim, lim, ls="--", lw=1.4, color=INK, zorder=4, label="perfect prediction")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("Measured runtime (minutes)", fontsize=11)
    ax.set_ylabel("Predicted runtime (minutes)", fontsize=11)
    ax.grid(True, color="#E4EAE5", lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=10, loc="upper left")
    fig.tight_layout()
    fig.savefig(f"{OUT}/pred_vs_actual.png", dpi=200)
    plt.close(fig)
    print("wrote pred_vs_actual.png  n =", len(df))


# ---------------------------------------------------------------- figure 2
# The headline finding: ranking by grid intensity vs ranking by measured
# per-run emissions gives opposite answers.
def carbon_reversal():
    d = pd.read_csv(f"{REPO}/data/results/carbon_by_region.csv")
    d["label"] = d["cloud"] + "  " + d["region"]

    by_intensity = d.sort_values(["mean_carbon_intensity", "label"]).reset_index(drop=True)
    by_measured = d.sort_values("mean_emissions_gco2eq").reset_index(drop=True)

    left_pos = {r["label"]: i for i, r in by_intensity.iterrows()}
    right_pos = {r["label"]: i for i, r in by_measured.iterrows()}

    fig, ax = plt.subplots(figsize=(7.6, 4.3), dpi=200)
    x0, x1 = 0.0, 1.0

    for _, row in d.iterrows():
        lab = row["label"]
        y0, y1 = left_pos[lab], right_pos[lab]
        flipped = lab.startswith("Azure  Central India")
        colour = TEAL if flipped else "#A7B3AA"
        ax.plot([x0, x1], [y0, y1], color=colour,
                lw=3.2 if flipped else 1.6,
                alpha=1.0 if flipped else 0.55, zorder=3,
                solid_capstyle="round")
        ax.scatter([x0, x1], [y0, y1], s=58 if flipped else 34,
                   color=colour, zorder=4, edgecolors="white", linewidths=1.2)

    for _, row in by_intensity.iterrows():
        y = left_pos[row["label"]]
        ax.text(x0 - 0.045, y, f"{row['label']}   {row['mean_carbon_intensity']:.0f}",
                ha="right", va="center", fontsize=10.5,
                color=INK if row["label"].startswith("Azure  Central") else GREY,
                fontweight="bold" if row["label"].startswith("Azure  Central") else "normal")
    for _, row in by_measured.iterrows():
        y = right_pos[row["label"]]
        ax.text(x1 + 0.045, y, f"{row['mean_emissions_gco2eq']:.3f}   {row['label']}",
                ha="left", va="center", fontsize=10.5,
                color=INK if row["label"].startswith("Azure  Central") else GREY,
                fontweight="bold" if row["label"].startswith("Azure  Central") else "normal")

    ax.text(x0 - 0.045, -0.85, "RANKED BY GRID INTENSITY\ngCO₂eq / kWh", ha="right",
            va="center", fontsize=10.5, color=INK, fontweight="bold", linespacing=1.6)
    ax.text(x1 + 0.045, -0.85, "RANKED BY MEASURED EMISSIONS\ngCO₂eq per run", ha="left",
            va="center", fontsize=10.5, color=INK, fontweight="bold", linespacing=1.6)

    ax.set_xlim(-1.15, 2.15)
    ax.set_ylim(3.55, -1.55)
    ax.axis("off")
    fig.tight_layout(pad=0.3)
    fig.savefig(f"{OUT}/carbon_reversal.png", dpi=200)
    plt.close(fig)
    print("wrote carbon_reversal.png")
    print(by_measured[["label", "mean_carbon_intensity", "mean_emissions_gco2eq"]])


# ---------------------------------------------------------------- figure 3
# Corpus composition — what the 1,811 runs actually cover.
def corpus():
    df = pd.read_csv(f"{REPO}/data/models/cloud_carbon_model_dataset.csv")

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), dpi=200,
                             gridspec_kw={"width_ratios": [1.0, 1.25]})

    ax = axes[0]
    counts = (df.groupby(["cloud", "region"]).size()
                .sort_values(ascending=True))
    labels = [f"{c}  {r}" for c, r in counts.index]
    colours = [TEAL if c == "AWS" else MOSS for c, _ in counts.index]
    bars = ax.barh(labels, counts.values, color=colours, height=0.62)
    for b, v in zip(bars, counts.values):
        ax.text(b.get_width() + 12, b.get_y() + b.get_height() / 2, f"{v}",
                va="center", fontsize=10.5, color=INK, fontweight="bold")
    ax.set_xlim(0, counts.max() * 1.22)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=10.5)
    ax.set_title("Runs per region", fontsize=11.5, color=INK,
                 fontweight="bold", loc="left", pad=10)

    ax = axes[1]
    piv = (df.groupby(["dataset_size_mb", "workload_type"]).size()
             .unstack(fill_value=0))
    order = ["cpu-heavy", "memory-heavy", "io-heavy"]
    piv = piv[[c for c in order if c in piv.columns]]
    bottom = np.zeros(len(piv))
    palette = {"cpu-heavy": INK, "memory-heavy": TEAL, "io-heavy": MOSS}
    x = np.arange(len(piv))
    for col in piv.columns:
        ax.bar(x, piv[col].values, bottom=bottom, width=0.66,
               color=palette[col], label=col)
        bottom += piv[col].values
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(v)}" for v in piv.index], fontsize=10)
    ax.set_xlabel("Dataset size (MB)", fontsize=10.5)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.legend(frameon=False, fontsize=10, ncol=3, loc="lower center",
              bbox_to_anchor=(0.5, 1.01), handlelength=1.1, columnspacing=1.6)

    fig.tight_layout()
    fig.savefig(f"{OUT}/corpus.png", dpi=200)
    plt.close(fig)
    print("wrote corpus.png  total =", len(df))


if __name__ == "__main__":
    predicted_vs_actual()
    carbon_reversal()
    corpus()


# ------------------------------------------------- figure 2b (dark variant)
def carbon_reversal_dark():
    d = pd.read_csv(f"{REPO}/data/results/carbon_by_region.csv")
    d["label"] = d["cloud"] + "  " + d["region"]
    by_intensity = d.sort_values(["mean_carbon_intensity", "label"]).reset_index(drop=True)
    by_measured = d.sort_values("mean_emissions_gco2eq").reset_index(drop=True)
    left_pos = {r["label"]: i for i, r in by_intensity.iterrows()}
    right_pos = {r["label"]: i for i, r in by_measured.iterrows()}

    BG = "#16261E"
    DIM = "#AEBFB4"
    fig, ax = plt.subplots(figsize=(7.6, 4.3), dpi=200)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    x0, x1 = 0.0, 1.0

    for _, row in d.iterrows():
        lab = row["label"]
        y0, y1 = left_pos[lab], right_pos[lab]
        flipped = lab.startswith("Azure  Central India")
        colour = MOSS if flipped else "#4E6B5A"
        ax.plot([x0, x1], [y0, y1], color=colour, lw=3.4 if flipped else 1.8,
                zorder=3, solid_capstyle="round")
        ax.scatter([x0, x1], [y0, y1], s=62 if flipped else 34, color=colour,
                   zorder=4, edgecolors=BG, linewidths=1.4)

    for _, row in by_intensity.iterrows():
        hot = row["label"].startswith("Azure  Central")
        ax.text(x0 - 0.045, left_pos[row["label"]],
                f"{row['label']}   {row['mean_carbon_intensity']:.0f}",
                ha="right", va="center", fontsize=10.5,
                color="white" if hot else DIM,
                fontweight="bold" if hot else "normal")
    for _, row in by_measured.iterrows():
        hot = row["label"].startswith("Azure  Central")
        ax.text(x1 + 0.045, right_pos[row["label"]],
                f"{row['mean_emissions_gco2eq']:.3f}   {row['label']}",
                ha="left", va="center", fontsize=10.5,
                color="white" if hot else DIM,
                fontweight="bold" if hot else "normal")

    ax.text(x0 - 0.045, -0.85, "RANKED BY GRID INTENSITY\ngCO₂eq / kWh", ha="right",
            va="center", fontsize=10.5, color=MOSS, fontweight="bold", linespacing=1.6)
    ax.text(x1 + 0.045, -0.85, "RANKED BY MEASURED EMISSIONS\ngCO₂eq per run", ha="left",
            va="center", fontsize=10.5, color=MOSS, fontweight="bold", linespacing=1.6)

    ax.set_xlim(-1.15, 2.15)
    ax.set_ylim(3.55, -1.55)
    ax.axis("off")
    fig.tight_layout(pad=0.3)
    fig.savefig(f"{OUT}/carbon_reversal_dark.png", dpi=200, facecolor=BG)
    plt.close(fig)
    print("wrote carbon_reversal_dark.png")


carbon_reversal_dark()
