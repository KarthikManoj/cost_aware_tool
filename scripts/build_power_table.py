"""Generate config/instance_power_draw.csv from Cloud Carbon Footprint coefficients.

Rather than hand-typing wattages, this script encodes the published Cloud
Carbon Footprint (CCF) coefficients and the instance -> microarchitecture
mapping, then derives per-node power draw. Re-run it to regenerate the table,
and cite it in the dissertation as the provenance of every figure.

Model
-----
CCF estimates processor power with a linear interpolation between the idle and
fully-loaded draw of the microarchitecture, measured from the SPECpower
database:

    watts_per_vCPU = min_watts + utilisation * (max_watts - min_watts)
    power_W        = watts_per_vCPU * vCPUs

`utilisation` defaults to 0.5, which is CCF's own fallback when a provider API
does not report actual CPU utilisation. A fixed value is used for every row on
purpose: measured CPU utilisation exists for the Azure runs in this project but
not the AWS ones, so using measured values where available would reintroduce
exactly the AWS/Azure asymmetry that ml/merge_model_dataset.py was changed to
remove.

Where an instance family spans several microarchitectures (AWS and Azure both
schedule the same instance type onto different processor generations), the
per-vCPU figure is the unweighted mean across those architectures. This is
CCF's approach and it is the reason a D2s_v3 draws more per vCPU than a
D2ds_v4: the v3 family still includes older, less efficient Haswell parts.

Scope and limitations
---------------------
CCF's use-phase coefficients cover the processor only. Memory, storage and
network energy are excluded, so these figures understate whole-node draw.
They are nevertheless the right input for `ml/carbon_analysis.py`, which
compares configurations against each other rather than reporting an absolute
facility footprint.

Sources
-------
Coefficients: cloud-carbon-footprint/cloud-carbon-coefficients,
    output/coefficients-aws-use.csv and output/coefficients-azure-use.csv
Method:       https://www.cloudcarbonfootprint.org/docs/methodology/
Azure mapping: cloud-carbon-coefficients, data/azure-instances.csv
AWS mapping:   AWS EC2 instance-type documentation (processor per family)

Usage
-----
    python scripts/build_power_table.py
    python scripts/build_power_table.py --utilisation 0.35
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "config" / "instance_power_draw.csv"

DEFAULT_UTILISATION = 0.5

# CCF min/max watts per vCPU, by provider and microarchitecture.
# Verbatim from output/coefficients-{aws,azure}-use.csv.
COEFFICIENTS: dict[str, dict[str, tuple[float, float]]] = {
    "AWS": {
        "Sky Lake": (0.6446044454253452, 4.193436438541878),
        "Cascade Lake": (0.6389493581523519, 3.9673047343937564),
        "EPYC 1st Gen": (0.82265625, 2.553125),
        "EPYC 2nd Gen": (0.4742621527777778, 1.6929615162037037),
    },
    "Azure": {
        "Haswell": (1.9005681818181814, 6.012910353535353),
        "Broadwell": (0.7128342245989304, 3.6853275401069516),
        "Skylake": (0.6446044454253452, 4.193436438541878),
        "Cascade Lake": (0.6389493581523519, 3.9673047343937564),
        "EPYC 2nd Gen": (0.4742621527777778, 1.6929615162037037),
    },
}

# machine_type -> (provider, vCPUs, [microarchitectures], provenance note)
#
# Azure architectures are taken directly from cloud-carbon-coefficients
# data/azure-instances.csv. AWS architectures come from the processor AWS
# publishes for each instance family.
INSTANCES: list[tuple[str, str, int, list[str], str]] = [
    # --- AWS -------------------------------------------------------------
    ("m5.xlarge", "AWS", 4, ["Sky Lake", "Cascade Lake"],
     "Xeon Platinum 8175M / 8259CL"),
    ("m5a.xlarge", "AWS", 4, ["EPYC 1st Gen"],
     "AMD EPYC 7571 (Naples)"),
    ("m6i.xlarge", "AWS", 4, ["Cascade Lake"],
     "Xeon Ice Lake 8375C; CCF has no Ice Lake coefficient, "
     "nearest generation substituted"),
    ("c5.xlarge", "AWS", 4, ["Sky Lake", "Cascade Lake"],
     "Xeon Platinum 8124M / 8275CL"),
    ("c5a.xlarge", "AWS", 4, ["EPYC 2nd Gen"],
     "AMD EPYC 7R32 (Rome)"),
    ("c6i.xlarge", "AWS", 4, ["Cascade Lake"],
     "Xeon Ice Lake 8375C; not present in CCF data, "
     "nearest generation substituted"),
    # --- Azure -----------------------------------------------------------
    ("Standard_D2s_v3", "Azure", 2,
     ["Haswell", "Cascade Lake", "Skylake", "Broadwell"],
     "Dsv3 spans four processor generations"),
    ("Standard_D4s_v3", "Azure", 4,
     ["Haswell", "Cascade Lake", "Skylake", "Broadwell"],
     "Dsv3 spans four processor generations"),
    ("Standard_D2as_v4", "Azure", 2, ["EPYC 2nd Gen"],
     "AMD EPYC 7452 (Rome)"),
    ("Standard_D4as_v4", "Azure", 4, ["EPYC 2nd Gen"],
     "AMD EPYC 7452 (Rome)"),
    ("Standard_D2ds_v4", "Azure", 2, ["Cascade Lake"],
     "Ddsv4 is Cascade Lake"),
    ("Standard_D4ds_v4", "Azure", 4, ["Cascade Lake"],
     "Ddsv4 is Cascade Lake"),
]


def watts_per_vcpu(provider: str, architectures: list[str], utilisation: float) -> float:
    """Mean interpolated per-vCPU draw across the given architectures."""
    table = COEFFICIENTS[provider]
    values = []
    for architecture in architectures:
        minimum, maximum = table[architecture]
        values.append(minimum + utilisation * (maximum - minimum))
    return sum(values) / len(values)


def build(utilisation: float) -> pd.DataFrame:
    rows = []
    for machine_type, provider, vcpus, architectures, note in INSTANCES:
        per_vcpu = watts_per_vcpu(provider, architectures, utilisation)
        rows.append(
            {
                "machine_type": machine_type,
                "vcpus": vcpus,
                "power_w": round(per_vcpu * vcpus, 2),
                "source": (
                    f"Cloud Carbon Footprint coefficients ({provider}, "
                    f"{' + '.join(architectures)}) at {utilisation:.0%} vCPU "
                    f"utilisation; {note}"
                ),
                "watts_per_vcpu": round(per_vcpu, 4),
                "microarchitecture": " + ".join(architectures),
                "utilisation_assumed": utilisation,
            }
        )
    return pd.DataFrame(rows).sort_values("machine_type").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build config/instance_power_draw.csv from CCF coefficients."
    )
    parser.add_argument("--utilisation", type=float, default=DEFAULT_UTILISATION)
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    if not 0.0 <= args.utilisation <= 1.0:
        raise SystemExit("--utilisation must be between 0 and 1.")

    table = build(args.utilisation)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)

    print(table[["machine_type", "vcpus", "watts_per_vcpu", "power_w",
                 "microarchitecture"]].to_string(index=False))
    print()
    print(f"Wrote {len(table)} rows to {path}")
    print(f"Utilisation assumed: {args.utilisation:.0%}")


if __name__ == "__main__":
    main()
