"""Run EMR Spark experiments sequentially and append results to performance CSV.

This script intentionally runs one cluster at a time. It defaults to dry-run mode;
pass --submit to create billable EMR clusters.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aws.emr_runner import EmrExperiment, WORKLOAD_TO_SCRIPT, run_experiment
from metrics.collect_metrics import ExperimentMetric, append_metric, calculate_cost, zone_for_region


TERMINAL_CLUSTER_STATES = {"TERMINATED", "TERMINATED_WITH_ERRORS"}
TERMINAL_STEP_STATES = {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}


def parse_sizes(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_workloads(value: str) -> list[str]:
    workloads = [item.strip() for item in value.split(",") if item.strip()]
    invalid = sorted(set(workloads) - set(WORKLOAD_TO_SCRIPT))
    if invalid:
        raise ValueError(f"Invalid workloads: {', '.join(invalid)}")
    return workloads


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


def build_experiment(bucket: str, prefix: str, dataset_size_mb: float, workload: str, instance_type: str, nodes: int):
    size_label = f"{int(dataset_size_mb)}mb"
    script_name = WORKLOAD_TO_SCRIPT[workload]
    short_workload = workload.replace("-heavy", "")
    return EmrExperiment(
        workload=workload,
        dataset_uri=f"s3://{bucket}/{prefix}/data/events_{size_label}.csv",
        script_uri=f"s3://{bucket}/{prefix}/scripts/{script_name}",
        output_uri=f"s3://{bucket}/{prefix}/output/{short_workload}_{size_label}_{instance_type.replace('.', '')}_{nodes}",
        instance_type=instance_type,
        nodes=nodes,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a sequential EMR experiment batch.")
    parser.add_argument("--config", default="config/experiment_config.yaml")
    parser.add_argument("--dataset-sizes-mb", default="100,500,1024,2048,3072,5120")
    parser.add_argument("--workloads", default="cpu-heavy,memory-heavy,io-heavy")
    parser.add_argument("--instance-type", default="m5.xlarge")
    parser.add_argument("--nodes", type=int, default=2)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--step-timeout-minutes", type=float, default=30)
    parser.add_argument("--price-path", default="config/instance_prices.csv")
    parser.add_argument("--output", default="data/performance/performance_dataset.csv")
    parser.add_argument("--submit", action="store_true", help="Create billable EMR clusters. Default is dry-run.")
    args = parser.parse_args()

    from aws.emr_runner import load_config

    config = load_config(args.config)
    region = config["aws"]["region"]
    bucket = config["aws"]["s3_bucket"]
    prefix = config["aws"]["s3_prefix"].strip("/")
    emr = boto3.client("emr", region_name=region)

    for dataset_size_mb in parse_sizes(args.dataset_sizes_mb):
        for workload in parse_workloads(args.workloads):
            experiment = build_experiment(bucket, prefix, dataset_size_mb, workload, args.instance_type, args.nodes)
            print(f"Starting {dataset_size_mb:g}MB {workload} on {args.instance_type} x {args.nodes}")
            response = run_experiment(args.config, experiment, dry_run=not args.submit)
            if not args.submit:
                continue

            cluster_id = response["JobFlowId"]
            step = wait_for_step(emr, cluster_id, args.poll_seconds, args.step_timeout_minutes)
            cluster = wait_for_cluster_termination(emr, cluster_id, args.poll_seconds)
            if step["Status"]["State"] != "COMPLETED":
                print(f"Skipping CSV append because step ended as {step['Status']['State']}: {cluster_id}")
                continue

            minutes = runtime_minutes(step)
            cost = calculate_cost(args.instance_type, args.nodes, minutes, args.price_path)
            append_metric(
                ExperimentMetric(
                    dataset_size_mb=dataset_size_mb,
                    workload_type=workload,
                    machine_type=args.instance_type,
                    nodes=args.nodes,
                    runtime_minutes=minutes,
                    cost_usd=cost,
                    region=region,
                    source=f"aws-emr:{cluster_id}:{step['Id']}",
                    cloud="aws",
                    electricity_zone=zone_for_region(region),
                ),
                args.output,
            )
            print(f"Saved {workload} {dataset_size_mb:g}MB runtime={minutes:.4f} min cost=${cost:.4f}")
            print(f"Cluster ended as {cluster['Status']['State']}")


if __name__ == "__main__":
    main()
