"""Run regional EMR experiments with resumable success and failure tracking.

This runner is designed for long experiment batches where some EMR cluster
submissions or Spark steps may fail. Successful runs are appended to the normal
performance dataset. Failed runs are appended to a separate CSV with enough
details to rerun or create them manually.
"""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aws.emr_runner import EmrExperiment, WORKLOAD_TO_SCRIPT, run_experiment
from metrics.collect_metrics import ExperimentMetric, append_metric, calculate_cost


TERMINAL_CLUSTER_STATES = {"TERMINATED", "TERMINATED_WITH_ERRORS"}
TERMINAL_STEP_STATES = {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}


@dataclass(frozen=True)
class FailedExperiment:
    timestamp_utc: str
    region: str
    dataset_size_mb: float
    workload_type: str
    instance_type: str
    nodes: int
    stage: str
    cluster_id: str
    step_id: str
    state: str
    reason: str
    manual_command: str


FAILED_COLUMNS = list(FailedExperiment.__dataclass_fields__)


def parse_csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_sizes(value: str) -> list[float]:
    return [float(item) for item in parse_csv_values(value)]


def parse_workloads(value: str) -> list[str]:
    workloads = parse_csv_values(value)
    invalid = sorted(set(workloads) - set(WORKLOAD_TO_SCRIPT))
    if invalid:
        raise ValueError(f"Invalid workloads: {', '.join(invalid)}")
    return workloads


def normalize_pricing_model(value: str) -> str:
    value = value.strip().lower()
    if value in {"on-demand", "ondemand"}:
        return "on-demand"
    if value == "spot":
        return "spot"
    return value


def lookup_aws_price(price_path: str, region: str, instance_type: str, pricing_model: str) -> float:
    path = Path(price_path)
    if not path.exists():
        raise FileNotFoundError(f"AWS price file not found: {price_path}")

    prices: list[float] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_region = (row.get("region") or "").strip().lower()
            row_instance = (row.get("instance_type") or "").strip()
            row_tier = normalize_pricing_model(row.get("tier") or "")
            price = row.get("price_usd_hr") or row.get("hourly_price_usd")
            if row_region != region.lower():
                continue
            if row_instance != instance_type:
                continue
            if row_tier != normalize_pricing_model(pricing_model):
                continue
            if price in {None, ""}:
                continue
            prices.append(float(price))

    if not prices:
        raise ValueError(
            "No AWS price found for "
            f"region={region}, instance_type={instance_type}, pricing_model={pricing_model} "
            f"in {price_path}"
        )
    return round(min(prices), 6)


def calculate_regional_cost(
    instance_type: str,
    nodes: int,
    runtime_minutes: float,
    price_path: str,
    region: str,
    pricing_model: str,
) -> float:
    if Path(price_path).name == "aws_prices.csv":
        hourly_price = lookup_aws_price(price_path, region, instance_type, pricing_model)
        return round(hourly_price * nodes * (runtime_minutes / 60.0), 6)
    return calculate_cost(instance_type, nodes, runtime_minutes, price_path)


def load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_temp_regional_config(
    base_config_path: str,
    region: str,
    subnet_id: str | None,
    ec2_key_name: str | None,
) -> str:
    config = load_yaml(base_config_path)
    config["aws"]["region"] = region
    if subnet_id is not None:
        if subnet_id:
            config["cluster"]["subnet_id"] = subnet_id
        else:
            config["cluster"].pop("subnet_id", None)
    if ec2_key_name is not None:
        if ec2_key_name:
            config["cluster"]["ec2_key_name"] = ec2_key_name
        else:
            config["cluster"].pop("ec2_key_name", None)
    temp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    with temp:
        yaml.safe_dump(config, temp, sort_keys=False)
    return temp.name


def size_label(dataset_size_mb: float) -> str:
    return f"{int(dataset_size_mb)}mb"


def build_experiment(
    bucket: str,
    prefix: str,
    region: str,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
) -> EmrExperiment:
    label = size_label(dataset_size_mb)
    script_name = WORKLOAD_TO_SCRIPT[workload]
    short_workload = workload.replace("-heavy", "")
    safe_instance = instance_type.replace(".", "")
    return EmrExperiment(
        workload=workload,
        dataset_uri=f"s3://{bucket}/{prefix}/data/events_{label}.csv",
        script_uri=f"s3://{bucket}/{prefix}/scripts/{script_name}",
        output_uri=(
            f"s3://{bucket}/{prefix}/output/{region}/"
            f"{short_workload}_{label}_{safe_instance}_{nodes}_{int(time.time())}"
        ),
        instance_type=instance_type,
        nodes=nodes,
    )


def manual_command(args: argparse.Namespace, dataset_size_mb: float, workload: str, instance_type: str, nodes: int) -> str:
    return (
        "python scripts/run_emr_regional_resumable_batch.py "
        f"--region {args.region} "
        f"--dataset-sizes-mb {int(dataset_size_mb)} "
        f"--workloads {workload} "
        f"--instance-types {instance_type} "
        f"--nodes-list {nodes} "
        f"--ec2-key-name {args.ec2_key_name or ''} "
        f"--pricing-model {args.pricing_model} "
        f"--price-path {args.price_path} "
        f"--step-timeout-minutes {args.step_timeout_minutes:g} "
        "--submit"
    )


def append_failed(path: str, failed: FailedExperiment) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output.exists()
    with open(output, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FAILED_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(failed))


def failure_reason_from_step(step: dict) -> str:
    status = step.get("Status", {})
    failure = status.get("FailureDetails") or {}
    parts = [
        failure.get("Reason", ""),
        failure.get("Message", ""),
        failure.get("LogFile", ""),
    ]
    reason = " | ".join(part for part in parts if part)
    return reason or str(status)


def wait_for_step(emr, cluster_id: str, poll_seconds: int, timeout_minutes: float) -> dict:
    started_waiting = time.monotonic()
    while True:
        response = emr.list_steps(ClusterId=cluster_id)
        step = response["Steps"][0]
        state = step["Status"]["State"]
        print(f"{cluster_id} step {step['Id']} is {state}")
        if state in TERMINAL_STEP_STATES:
            return step
        elapsed_minutes = (time.monotonic() - started_waiting) / 60.0
        if elapsed_minutes >= timeout_minutes:
            print(f"{cluster_id} step timed out after {timeout_minutes:g} minutes; terminating cluster")
            emr.terminate_job_flows(JobFlowIds=[cluster_id])
            step["Status"]["State"] = "TIMED_OUT"
            step["Status"]["FailureDetails"] = {"Reason": "Step timeout", "Message": "Terminated by batch runner"}
            return step
        time.sleep(poll_seconds)


def wait_for_cluster_termination(emr, cluster_id: str, poll_seconds: int) -> dict:
    while True:
        cluster = emr.describe_cluster(ClusterId=cluster_id)["Cluster"]
        state = cluster["Status"]["State"]
        print(f"{cluster_id} cluster is {state}")
        if state in TERMINAL_CLUSTER_STATES:
            return cluster
        time.sleep(poll_seconds)


def runtime_minutes(step: dict) -> float:
    timeline = step["Status"]["Timeline"]
    started: datetime = timeline["StartDateTime"]
    ended: datetime = timeline["EndDateTime"]
    return round((ended - started).total_seconds() / 60.0, 6)


def already_completed(
    output_path: str,
    region: str,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
) -> bool:
    path = Path(output_path)
    if not path.exists():
        return False
    try:
        data = pd.read_csv(path, on_bad_lines="skip")
    except Exception:
        return False
    required = {"dataset_size_mb", "workload_type", "instance_type", "nodes", "source"}
    if not required.issubset(data.columns):
        return False
    matches = data[
        (data["dataset_size_mb"].astype(float) == float(dataset_size_mb))
        & (data["workload_type"] == workload)
        & (data["instance_type"] == instance_type)
        & (data["nodes"].astype(int) == int(nodes))
        & (data["source"].astype(str).str.contains(f"aws-emr:{region}:", regex=False))
    ]
    return not matches.empty


def record_failure(
    args: argparse.Namespace,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
    stage: str,
    cluster_id: str = "",
    step_id: str = "",
    state: str = "",
    reason: str = "",
) -> None:
    append_failed(
        args.failed_output,
        FailedExperiment(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            region=args.region,
            dataset_size_mb=dataset_size_mb,
            workload_type=workload,
            instance_type=instance_type,
            nodes=nodes,
            stage=stage,
            cluster_id=cluster_id,
            step_id=step_id,
            state=state,
            reason=reason[:1500],
            manual_command=manual_command(args, dataset_size_mb, workload, instance_type, nodes),
        ),
    )


def run_one(
    args: argparse.Namespace,
    config_path: str,
    bucket: str,
    prefix: str,
    emr,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
) -> None:
    if args.skip_completed and already_completed(args.output, args.region, dataset_size_mb, workload, instance_type, nodes):
        print(f"Skipping completed {dataset_size_mb:g}MB {workload} {instance_type} x {nodes} in {args.region}")
        return

    experiment = build_experiment(bucket, prefix, args.region, dataset_size_mb, workload, instance_type, nodes)
    print(f"Starting {dataset_size_mb:g}MB {workload} on {instance_type} x {nodes} in {args.region}")

    try:
        response = run_experiment(config_path, experiment, dry_run=not args.submit)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        print(f"SUBMIT FAILED: {reason}")
        record_failure(args, dataset_size_mb, workload, instance_type, nodes, "submit", reason=reason)
        return

    if not args.submit:
        return

    cluster_id = response["JobFlowId"]
    try:
        step = wait_for_step(emr, cluster_id, args.poll_seconds, args.step_timeout_minutes)
        step_id = step.get("Id", "")
        step_state = step["Status"]["State"]
        cluster = wait_for_cluster_termination(emr, cluster_id, args.poll_seconds)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        print(f"MONITOR FAILED: {reason}")
        record_failure(args, dataset_size_mb, workload, instance_type, nodes, "monitor", cluster_id=cluster_id, reason=reason)
        return

    if step_state != "COMPLETED":
        reason = failure_reason_from_step(step)
        cluster_reason = cluster.get("Status", {}).get("StateChangeReason", {})
        error_details = cluster.get("Status", {}).get("ErrorDetails", [])
        if cluster_reason or error_details:
            reason = f"{reason} | cluster_reason={cluster_reason} | error_details={error_details}"
        print(f"STEP FAILED: {cluster_id} {step_id} ended as {step_state}: {reason}")
        record_failure(
            args,
            dataset_size_mb,
            workload,
            instance_type,
            nodes,
            "step",
            cluster_id=cluster_id,
            step_id=step_id,
            state=step_state,
            reason=reason,
        )
        return

    minutes = runtime_minutes(step)
    try:
        cost = calculate_regional_cost(
            instance_type,
            nodes,
            minutes,
            args.price_path,
            args.region,
            args.pricing_model,
        )
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        print(f"COST FAILED: {reason}")
        record_failure(args, dataset_size_mb, workload, instance_type, nodes, "cost", cluster_id=cluster_id, step_id=step_id, reason=reason)
        return

    append_metric(
        ExperimentMetric(
            dataset_size_mb=dataset_size_mb,
            workload_type=workload,
            instance_type=instance_type,
            nodes=nodes,
            runtime_minutes=minutes,
            cost_usd=cost,
            source=f"aws-emr:{args.region}:{cluster_id}:{step_id}",
        ),
        args.output,
    )
    print(
        f"Saved {workload} {dataset_size_mb:g}MB {instance_type} x {nodes} "
        f"runtime={minutes:.4f} min cost=${cost:.4f}; cluster={cluster['Status']['State']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a resumable regional EMR experiment batch.")
    parser.add_argument("--config", default="config/experiment_config.yaml")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--subnet-id", default=None, help="Subnet in the target region. Use empty string to omit subnet.")
    parser.add_argument("--ec2-key-name", default=None, help="EC2 key pair in the target region. Use empty string to omit SSH key.")
    parser.add_argument("--dataset-sizes-mb", default="10,100,500,1024,2048,3072,5120")
    parser.add_argument("--workloads", default="cpu-heavy,memory-heavy,io-heavy")
    parser.add_argument("--instance-types", default="m5.xlarge")
    parser.add_argument("--nodes-list", default="4")
    parser.add_argument("--pricing-model", default="on-demand", choices=["on-demand", "spot"])
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--step-timeout-minutes", type=float, default=45)
    parser.add_argument("--price-path", default="cloud_prices/aws_prices.csv")
    parser.add_argument("--output", default="data/performance/performance_dataset.csv")
    parser.add_argument("--failed-output", default="data/performance/failed_emr_experiments.csv")
    parser.add_argument("--skip-completed", action="store_true", default=True)
    parser.add_argument("--submit", action="store_true", help="Create billable EMR clusters. Default is dry-run.")
    args = parser.parse_args()

    base_config = load_yaml(args.config)
    bucket = base_config["aws"]["s3_bucket"]
    prefix = base_config["aws"]["s3_prefix"].strip("/")
    subnet_id = args.subnet_id
    ec2_key_name = args.ec2_key_name

    config_path = write_temp_regional_config(args.config, args.region, subnet_id, ec2_key_name)
    emr = boto3.client("emr", region_name=args.region)

    for dataset_size_mb in parse_sizes(args.dataset_sizes_mb):
        for workload in parse_workloads(args.workloads):
            for instance_type in parse_csv_values(args.instance_types):
                for nodes in [int(value) for value in parse_csv_values(args.nodes_list)]:
                    run_one(args, config_path, bucket, prefix, emr, dataset_size_mb, workload, instance_type, nodes)

    print(f"Batch finished. Success CSV: {args.output}")
    print(f"Failed experiments CSV: {args.failed_output}")


if __name__ == "__main__":
    main()
