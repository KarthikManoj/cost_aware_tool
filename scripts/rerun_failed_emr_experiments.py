#!/usr/bin/env python3
"""Rerun failed EMR experiments from data/performance/failed_emr_experiments.csv.

Default mode is dry-run: it prints the exact commands. Pass --submit to create
billable EMR clusters. Each failed tuple is run individually so we do not expand
into extra dataset/workload/instance/node combinations that were not in the CSV.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]

REGION_OVERRIDES = {
    # cost-aware-emr-key does not exist in ap-south-1, so omit Ec2KeyName there.
    "ap-south-1": ["--ec2-key-name", ""],
    # Region-specific default subnet in ap-southeast-1; avoids inheriting the ap-south-1 subnet.
    "ap-southeast-1": ["--subnet-id", "subnet-REPLACE_ME_AP_SOUTHEAST_1", "--ec2-key-name", "cost-aware-emr-key"],
}

REGION_KEY_REQUIREMENTS = {
    "ap-southeast-1": "cost-aware-emr-key",
}


def size_arg(value: str) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def load_failed(path: Path) -> list[tuple[str, str, str, str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"region", "dataset_size_mb", "workload_type", "instance_type", "nodes"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(sorted(missing))}")

        seen: set[tuple[str, str, str, str, str]] = set()
        failed: list[tuple[str, str, str, str, str]] = []
        for row in reader:
            key = (
                row["region"].strip(),
                size_arg(row["dataset_size_mb"].strip()),
                row["workload_type"].strip(),
                row["instance_type"].strip(),
                str(int(float(row["nodes"].strip()))),
            )
            if key not in seen:
                seen.add(key)
                failed.append(key)
        return failed


def ensure_required_key_pairs(regions: set[str]) -> None:
    for region in sorted(regions):
        required_key = REGION_KEY_REQUIREMENTS.get(region)
        if not required_key:
            continue
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_key_pairs(KeyNames=[required_key])
        names = {item["KeyName"] for item in response.get("KeyPairs", [])}
        if required_key not in names:
            raise RuntimeError(f"Required EC2 key pair {required_key!r} is missing in {region}")


def ensure_region_overrides_build_valid_requests(args: argparse.Namespace) -> None:
    checks = {
        "ap-south-1": ("subnet-REPLACE_ME_AP_SOUTH_1", None),
        "ap-southeast-1": ("subnet-REPLACE_ME_AP_SOUTHEAST_1", "cost-aware-emr-key"),
    }
    for region, (expected_subnet, expected_key) in checks.items():
        cmd = [
            sys.executable,
            "scripts/run_emr_regional_resumable_batch.py",
            "--region",
            region,
            "--dataset-sizes-mb",
            "9999",
            "--workloads",
            "cpu-heavy",
            "--instance-types",
            "m5.xlarge",
            "--nodes-list",
            "2",
        ]
        cmd.extend(REGION_OVERRIDES[region])
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
        if f'"Ec2SubnetId": "{expected_subnet}"' not in result.stdout:
            raise RuntimeError(f"{region} dry-run did not contain expected subnet {expected_subnet}")
        if expected_key and f'"Ec2KeyName": "{expected_key}"' not in result.stdout:
            raise RuntimeError(f"{region} dry-run did not contain expected key {expected_key}")
        if expected_key is None and "Ec2KeyName" in result.stdout:
            raise RuntimeError(f"{region} dry-run unexpectedly contains an EC2 key name")


def build_command(args: argparse.Namespace, failed: tuple[str, str, str, str, str]) -> list[str]:
    region, dataset_size, workload, instance_type, nodes = failed
    cmd = [
        sys.executable,
        "scripts/run_emr_regional_resumable_batch.py",
        "--region",
        region,
        "--dataset-sizes-mb",
        dataset_size,
        "--workloads",
        workload,
        "--instance-types",
        instance_type,
        "--nodes-list",
        nodes,
        "--pricing-model",
        args.pricing_model,
        "--price-path",
        args.price_path,
        "--output",
        args.output,
        "--failed-output",
        args.retry_failed_output,
        "--step-timeout-minutes",
        str(args.step_timeout_minutes),
    ]
    cmd.extend(REGION_OVERRIDES.get(region, []))
    if args.submit:
        cmd.append("--submit")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun failed AWS EMR experiments from the failed CSV.")
    parser.add_argument("--failed-csv", default="data/performance/failed_emr_experiments.csv")
    parser.add_argument("--retry-failed-output", default="data/performance/failed_emr_retry_experiments.csv")
    parser.add_argument("--output", default="data/performance/performance_dataset.csv")
    parser.add_argument("--price-path", default="cloud_prices/aws_prices.csv")
    parser.add_argument("--pricing-model", default="on-demand", choices=["on-demand", "spot"])
    parser.add_argument("--step-timeout-minutes", type=float, default=90)
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N failed tuples; 0 means all.")
    parser.add_argument("--submit", action="store_true", help="Create billable EMR clusters. Default is dry-run.")
    args = parser.parse_args()

    failed_csv = ROOT / args.failed_csv
    if not failed_csv.exists():
        raise FileNotFoundError(f"Failed CSV not found: {failed_csv}")

    failed = load_failed(failed_csv)
    if args.limit:
        failed = failed[: args.limit]

    print(f"Loaded {len(failed)} unique failed EMR experiment tuple(s) from {args.failed_csv}")
    if not args.submit:
        print("Dry-run mode. Add --submit to create EMR clusters.\n")
    else:
        regions = {item[0] for item in failed}
        print("Running preflight checks before submitting billable EMR clusters...")
        ensure_required_key_pairs(regions)
        ensure_region_overrides_build_valid_requests(args)
        print("Preflight checks passed.\n")

    for idx, item in enumerate(failed, 1):
        region, dataset_size, workload, instance_type, nodes = item
        print(f"[{idx}/{len(failed)}] {region} {dataset_size}MB {workload} {instance_type} x {nodes}")
        cmd = build_command(args, item)
        print("  " + " ".join(repr(part) if " " in part else part for part in cmd))
        if args.submit:
            subprocess.run(cmd, cwd=ROOT, check=False)

    print("Done.")
    if args.submit:
        print(f"New retry failures, if any, were written to {args.retry_failed_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
