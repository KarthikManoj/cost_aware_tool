"""Carbon, cost and Pareto-front analysis of the benchmark results.

`merge_model_dataset.py` computes a rough `estimated_emissions_gco2eq` as
runtime_hours x carbon_intensity. That expression is dimensionally incomplete:
gCO2eq/kWh multiplied by hours yields gCO2eq only if the cluster draws exactly
1 kW. This module applies the full formula instead:

    energy_kWh   = (instance_power_W x nodes / 1000) x (runtime_minutes / 60)
    emissions_g  = energy_kWh x grid_carbon_intensity_gCO2eq_per_kWh x PUE

Power draw
----------
Per-instance power draw is not something the benchmark measures, so it must
come from a published source (Boavizta or Cloud Carbon Footprint). Run

    python ml/carbon_analysis.py --write-power-template

to emit `config/instance_power_draw.csv` pre-populated with every machine type
in your dataset and PLACEHOLDER wattages. Replace those with real figures and
cite the source in your dissertation. Until you do, the script still runs but
prints a warning and marks the affected rows, so placeholder-derived numbers
can never silently reach the write-up.

Outputs (under data/results/)
-----------------------------
    carbon_per_run.csv              per-configuration emissions
    carbon_by_region.csv            emissions and intensity by cloud and region
    pareto_front.csv                non-dominated configurations per scenario
    tradeoff_by_scenario.csv        cheapest vs greenest vs fastest per scenario
    carbon_analysis_summary.json    headline figures and the assumptions used
    cost_vs_carbon.html             scatter with the Pareto front marked
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DATASET_CANDIDATES = [
    ROOT / "data/models/cloud_carbon_model_dataset.csv",
    ROOT / "data/performance/cloud_carbon_model_dataset.csv",
]
POWER_TABLE = ROOT / "config/instance_power_draw.csv"
PRICE_TABLE = ROOT / "config/instance_prices.csv"

# Power Usage Effectiveness, from the providers' published sustainability
# reports. Update these if you cite a different year.
PUE = {"aws": 1.15, "azure": 1.18}
DEFAULT_PUE = 1.20

# Fallback used only when neither the power table nor a vCPU count is
# available. Deliberately conservative and always reported as a placeholder.
DEFAULT_POWER_W = 60.0
WATTS_PER_VCPU = 12.0

CONFIG_COLUMNS = ["cloud", "region", "machine_type", "nodes"]
SCENARIO_COLUMNS = ["workload_type", "dataset_size_mb"]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def resolve_dataset(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"Dataset not found: {path}")
        return path
    for candidate in DATASET_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "Could not find cloud_carbon_model_dataset.csv. Run "
        "`python ml/merge_model_dataset.py` first."
    )


def load_vcpu_lookup() -> dict[str, float]:
    """vCPU counts from the price table, where available."""
    if not PRICE_TABLE.exists():
        return {}
    prices = pd.read_csv(PRICE_TABLE)
    if not {"instance_type", "vcpus"}.issubset(prices.columns):
        return {}
    return dict(zip(prices["instance_type"], prices["vcpus"].astype(float)))


def infer_vcpus(machine_type: str, lookup: dict[str, float]) -> float | None:
    """Best-effort vCPU count for a machine type.

    Uses the price table first, then falls back to the digit in an Azure size
    name (Standard_D4s_v3 -> 4), then to the AWS size suffix.
    """
    if machine_type in lookup:
        return lookup[machine_type]

    name = str(machine_type).lower()

    # Azure: ..._d4s_v3 / d4asv4 / d2dsv4  -> the digit after the family letter
    azure = re.search(r"_?d(\d+)[a-z]*_?v\d", name)
    if azure:
        return float(azure.group(1))

    # AWS size suffixes
    aws_sizes = {
        "large": 2.0,
        "xlarge": 4.0,
        "2xlarge": 8.0,
        "4xlarge": 16.0,
        "8xlarge": 32.0,
    }
    for suffix, vcpus in sorted(aws_sizes.items(), key=lambda kv: -len(kv[0])):
        if name.endswith(f".{suffix}"):
            return vcpus
    return None


def load_power_table() -> pd.DataFrame | None:
    if not POWER_TABLE.exists():
        return None
    table = pd.read_csv(POWER_TABLE)
    required = {"machine_type", "power_w"}
    missing = required - set(table.columns)
    if missing:
        raise SystemExit(
            f"{POWER_TABLE} is missing columns: {', '.join(sorted(missing))}"
        )
    if "source" not in table.columns:
        table["source"] = "unspecified"
    return table


def write_power_template(machine_types: list[str], vcpu_lookup: dict[str, float]) -> Path:
    rows = []
    for machine_type in sorted(machine_types):
        vcpus = infer_vcpus(machine_type, vcpu_lookup)
        estimate = (vcpus * WATTS_PER_VCPU) if vcpus else DEFAULT_POWER_W
        rows.append(
            {
                "machine_type": machine_type,
                "vcpus": vcpus if vcpus is not None else "",
                "power_w": round(estimate, 1),
                "source": "PLACEHOLDER - replace with Boavizta or Cloud Carbon Footprint figure",
            }
        )
    frame = pd.DataFrame(rows)
    POWER_TABLE.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(POWER_TABLE, index=False)
    return POWER_TABLE


def attach_power(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Add per-instance power draw, recording where each figure came from."""
    vcpu_lookup = load_vcpu_lookup()
    table = load_power_table()
    warnings: list[str] = []

    if table is not None:
        merged = data.merge(
            table[["machine_type", "power_w", "source"]],
            on="machine_type",
            how="left",
        )
        placeholder = merged["source"].astype(str).str.upper().str.contains("PLACEHOLDER")
        if placeholder.any():
            affected = sorted(merged.loc[placeholder, "machine_type"].unique())
            warnings.append(
                "Power draw is still a PLACEHOLDER for: "
                + ", ".join(affected)
                + ". Replace the values in config/instance_power_draw.csv with "
                "published figures before quoting absolute emissions."
            )
    else:
        merged = data.copy()
        merged["power_w"] = np.nan
        merged["source"] = pd.NA
        warnings.append(
            f"{POWER_TABLE.name} not found. Power draw was estimated as "
            f"{WATTS_PER_VCPU} W per vCPU. Run with --write-power-template to "
            "create the table and replace it with published figures."
        )

    unresolved = merged["power_w"].isna()
    if unresolved.any():
        # `inferred` is indexed by the unresolved subset only, so it must not
        # be combined with the full-length `unresolved` mask directly.
        inferred = merged.loc[unresolved, "machine_type"].map(
            lambda machine: infer_vcpus(machine, vcpu_lookup)
        )
        estimated = pd.to_numeric(inferred, errors="coerce") * WATTS_PER_VCPU
        merged.loc[unresolved, "power_w"] = estimated.fillna(DEFAULT_POWER_W).to_numpy()
        merged.loc[unresolved, "source"] = (
            merged.loc[unresolved, "source"].fillna("ESTIMATED from vCPU count").to_numpy()
        )
        unknown = sorted(
            merged.loc[unresolved, "machine_type"].loc[estimated.isna()].unique()
        )
        if unknown:
            warnings.append(
                f"Could not infer vCPU count for: {', '.join(map(str, unknown))}. "
                f"Used the {DEFAULT_POWER_W} W default."
            )

    merged["power_w"] = merged["power_w"].astype(float)
    return merged, warnings


# --------------------------------------------------------------------------
# Emissions
# --------------------------------------------------------------------------


def compute_emissions(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["pue"] = (
        frame["cloud"].astype(str).str.strip().str.lower().map(PUE).fillna(DEFAULT_PUE)
    )
    frame["cluster_power_kw"] = frame["power_w"] * frame["nodes"] / 1000.0
    frame["energy_kwh"] = frame["cluster_power_kw"] * (frame["runtime_minutes"] / 60.0)
    frame["emissions_gco2eq"] = (
        frame["energy_kwh"] * frame["carbon_intensity_mean"] * frame["pue"]
    )
    return frame


def aggregate_configurations(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per scenario and configuration, averaging repeated runs."""
    return (
        frame.groupby(SCENARIO_COLUMNS + CONFIG_COLUMNS + ["electricity_zone"], as_index=False)
        .agg(
            runs=("runtime_minutes", "size"),
            runtime_minutes=("runtime_minutes", "mean"),
            cost_usd=("cost_usd", "mean"),
            energy_kwh=("energy_kwh", "mean"),
            emissions_gco2eq=("emissions_gco2eq", "mean"),
            carbon_intensity_mean=("carbon_intensity_mean", "mean"),
            renewable_percentage_mean=("renewable_percentage_mean", "mean"),
            power_w=("power_w", "mean"),
            pue=("pue", "mean"),
        )
    )


# --------------------------------------------------------------------------
# Pareto front
# --------------------------------------------------------------------------


def pareto_mask(objectives: np.ndarray) -> np.ndarray:
    """Boolean mask of non-dominated rows. All objectives are minimised.

    Row i is dominated when some row j is no worse on every objective and
    strictly better on at least one.
    """
    count = objectives.shape[0]
    non_dominated = np.ones(count, dtype=bool)
    for i in range(count):
        if not non_dominated[i]:
            continue
        no_worse = np.all(objectives <= objectives[i], axis=1)
        strictly_better = np.any(objectives < objectives[i], axis=1)
        if np.any(no_worse & strictly_better):
            non_dominated[i] = False
    return non_dominated


def build_pareto(configurations: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in configurations.groupby(SCENARIO_COLUMNS):
        objectives = group[["cost_usd", "runtime_minutes", "emissions_gco2eq"]].to_numpy(
            dtype=float
        )
        flagged = group.copy()
        flagged["on_pareto_front"] = pareto_mask(objectives)
        frames.append(flagged)
    return pd.concat(frames, ignore_index=True)


def build_tradeoff(configurations: pd.DataFrame) -> pd.DataFrame:
    """Cheapest, greenest and fastest option for each scenario, with the cost
    penalty and carbon saving of choosing green over cheap."""
    rows: list[dict] = []
    for (workload, size), group in configurations.groupby(SCENARIO_COLUMNS):
        cheapest = group.loc[group["cost_usd"].idxmin()]
        greenest = group.loc[group["emissions_gco2eq"].idxmin()]
        fastest = group.loc[group["runtime_minutes"].idxmin()]

        cost_penalty = (
            (greenest["cost_usd"] - cheapest["cost_usd"]) / cheapest["cost_usd"] * 100.0
            if cheapest["cost_usd"] > 0
            else 0.0
        )
        carbon_saving = (
            (cheapest["emissions_gco2eq"] - greenest["emissions_gco2eq"])
            / cheapest["emissions_gco2eq"]
            * 100.0
            if cheapest["emissions_gco2eq"] > 0
            else 0.0
        )

        rows.append(
            {
                "workload_type": workload,
                "dataset_size_mb": size,
                "configurations": int(len(group)),
                "cheapest": f"{cheapest['cloud']} {cheapest['region']} {cheapest['machine_type']} x{int(cheapest['nodes'])}",
                "cheapest_cost_usd": round(float(cheapest["cost_usd"]), 6),
                "cheapest_emissions_gco2eq": round(float(cheapest["emissions_gco2eq"]), 4),
                "greenest": f"{greenest['cloud']} {greenest['region']} {greenest['machine_type']} x{int(greenest['nodes'])}",
                "greenest_cost_usd": round(float(greenest["cost_usd"]), 6),
                "greenest_emissions_gco2eq": round(float(greenest["emissions_gco2eq"]), 4),
                "fastest": f"{fastest['cloud']} {fastest['region']} {fastest['machine_type']} x{int(fastest['nodes'])}",
                "fastest_runtime_minutes": round(float(fastest["runtime_minutes"]), 4),
                "cheapest_is_greenest": bool(
                    cheapest[CONFIG_COLUMNS].tolist() == greenest[CONFIG_COLUMNS].tolist()
                ),
                "cost_penalty_of_greenest_pct": round(float(cost_penalty), 2),
                "carbon_saving_of_greenest_pct": round(float(carbon_saving), 2),
            }
        )
    return pd.DataFrame(rows)


def build_regional_summary(configurations: pd.DataFrame) -> pd.DataFrame:
    summary = (
        configurations.groupby(["cloud", "region", "electricity_zone"], as_index=False)
        .agg(
            configurations=("emissions_gco2eq", "size"),
            mean_carbon_intensity=("carbon_intensity_mean", "mean"),
            mean_renewable_pct=("renewable_percentage_mean", "mean"),
            mean_runtime_minutes=("runtime_minutes", "mean"),
            mean_cost_usd=("cost_usd", "mean"),
            mean_energy_kwh=("energy_kwh", "mean"),
            mean_emissions_gco2eq=("emissions_gco2eq", "mean"),
            total_emissions_gco2eq=("emissions_gco2eq", "sum"),
        )
        .sort_values("mean_emissions_gco2eq")
    )
    numeric = summary.select_dtypes(include="number").columns
    summary[numeric] = summary[numeric].round(6)
    return summary


def write_scatter(pareto: pd.DataFrame, output: Path) -> Path | None:
    try:
        import plotly.express as px
    except ImportError:
        return None

    frame = pareto.copy()
    frame["Front"] = np.where(frame["on_pareto_front"], "Pareto optimal", "Dominated")
    frame["Configuration"] = (
        frame["cloud"] + " " + frame["region"] + " " + frame["machine_type"]
        + " x" + frame["nodes"].astype(int).astype(str)
    )
    figure = px.scatter(
        frame,
        x="cost_usd",
        y="emissions_gco2eq",
        color="Front",
        symbol="cloud",
        size="runtime_minutes",
        hover_data=["Configuration", "workload_type", "dataset_size_mb", "runtime_minutes"],
        labels={
            "cost_usd": "Estimated cost (USD)",
            "emissions_gco2eq": "Estimated emissions (gCO2eq)",
        },
        title="Cost versus carbon emissions, Pareto-optimal configurations highlighted",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(str(output))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Carbon and Pareto analysis.")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--output-dir", default=str(ROOT / "data/results"))
    parser.add_argument(
        "--write-power-template",
        action="store_true",
        help="Write config/instance_power_draw.csv for the machine types in the dataset and exit.",
    )
    args = parser.parse_args()

    dataset_path = resolve_dataset(args.dataset)
    data = pd.read_csv(dataset_path)

    required = {
        "cloud", "region", "machine_type", "nodes", "workload_type",
        "dataset_size_mb", "runtime_minutes", "cost_usd", "carbon_intensity_mean",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise SystemExit(f"Dataset is missing required columns: {', '.join(missing)}")

    data = data.dropna(subset=sorted(required)).copy()
    data["nodes"] = data["nodes"].astype(int)
    if "electricity_zone" not in data.columns:
        data["electricity_zone"] = "unknown"
    if "renewable_percentage_mean" not in data.columns:
        data["renewable_percentage_mean"] = np.nan

    if args.write_power_template:
        path = write_power_template(
            sorted(data["machine_type"].astype(str).unique()), load_vcpu_lookup()
        )
        print(f"Wrote power draw template to {path}")
        print("Replace the PLACEHOLDER wattages with published figures, then re-run.")
        return

    with_power, warnings = attach_power(data)
    with_emissions = compute_emissions(with_power)
    configurations = aggregate_configurations(with_emissions)
    pareto = build_pareto(configurations)
    tradeoff = build_tradeoff(configurations)
    regional = build_regional_summary(configurations)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    configurations.round(6).to_csv(output / "carbon_per_run.csv", index=False)
    regional.to_csv(output / "carbon_by_region.csv", index=False)
    pareto.round(6).to_csv(output / "pareto_front.csv", index=False)
    tradeoff.to_csv(output / "tradeoff_by_scenario.csv", index=False)
    scatter = write_scatter(pareto, output / "cost_vs_carbon.html")

    front_sizes = pareto.groupby(SCENARIO_COLUMNS)["on_pareto_front"].sum()
    payload = {
        "dataset": str(dataset_path),
        "assumptions": {
            "formula": "emissions_g = (power_W x nodes / 1000) x (runtime_min / 60) x carbon_intensity_gCO2eq_per_kWh x PUE",
            "pue": PUE,
            "default_pue": DEFAULT_PUE,
            "watts_per_vcpu_fallback": WATTS_PER_VCPU,
            "default_power_w": DEFAULT_POWER_W,
            "power_table": str(POWER_TABLE) if POWER_TABLE.exists() else "not present",
        },
        "warnings": warnings,
        "configurations_evaluated": int(len(configurations)),
        "scenarios": int(len(front_sizes)),
        "pareto_front_size_mean": round(float(front_sizes.mean()), 2),
        "pareto_front_size_max": int(front_sizes.max()),
        "scenarios_where_cheapest_is_also_greenest": int(
            tradeoff["cheapest_is_greenest"].sum()
        ),
        "mean_cost_penalty_of_greenest_pct": round(
            float(tradeoff["cost_penalty_of_greenest_pct"].mean()), 2
        ),
        "mean_carbon_saving_of_greenest_pct": round(
            float(tradeoff["carbon_saving_of_greenest_pct"].mean()), 2
        ),
        "greenest_region": regional.iloc[0][["cloud", "region"]].to_dict(),
    }
    with open(output / "carbon_analysis_summary.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    for warning in warnings:
        print(f"WARNING: {warning}\n")

    print("Emissions by region (lowest first):")
    print(regional.to_string(index=False))
    print()
    print("Cost/carbon trade-off by scenario:")
    print(tradeoff.to_string(index=False))
    print()
    print(f"Mean cost penalty of the greenest option: {payload['mean_cost_penalty_of_greenest_pct']}%")
    print(f"Mean carbon saving of the greenest option: {payload['mean_carbon_saving_of_greenest_pct']}%")
    print(f"Cheapest option was also greenest in "
          f"{payload['scenarios_where_cheapest_is_also_greenest']} of {payload['scenarios']} scenarios")
    print()
    print(f"Wrote results to {output}")
    if scatter:
        print(f"Scatter plot: {scatter}")


if __name__ == "__main__":
    main()
