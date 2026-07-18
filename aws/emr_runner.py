"""Create EMR clusters and submit Spark workload steps.

The module supports a dry-run mode so experiment configurations can be reviewed
before launching billable infrastructure.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
import yaml


WORKLOAD_TO_SCRIPT = {
    "cpu-heavy": "cpu_heavy.py",
    "memory-heavy": "memory_heavy.py",
    "io-heavy": "io_heavy.py",
}


@dataclass(frozen=True)
class EmrExperiment:
    workload: str
    dataset_uri: str
    script_uri: str
    output_uri: str
    instance_type: str
    nodes: int


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_cluster_request(config: dict[str, Any], experiment: EmrExperiment) -> dict[str, Any]:
    cluster_config = config["cluster"]
    core_nodes = max(experiment.nodes - 1, 1)
    instances = {
        "InstanceGroups": [
            {
                "Name": "Primary",
                "Market": "ON_DEMAND",
                "InstanceRole": "MASTER",
                "InstanceType": experiment.instance_type,
                "InstanceCount": 1,
            },
            {
                "Name": "Core",
                "Market": "ON_DEMAND",
                "InstanceRole": "CORE",
                "InstanceType": experiment.instance_type,
                "InstanceCount": core_nodes,
            },
        ],
        "KeepJobFlowAliveWhenNoSteps": False,
        "TerminationProtected": False,
    }
    if cluster_config.get("subnet_id"):
        instances["Ec2SubnetId"] = cluster_config["subnet_id"]
    if cluster_config.get("ec2_key_name"):
        instances["Ec2KeyName"] = cluster_config["ec2_key_name"]

    return {
        "Name": f"cost-aware-{experiment.workload}-{experiment.instance_type}-{experiment.nodes}",
        "ReleaseLabel": config["aws"]["emr_release_label"],
        "Applications": [{"Name": name} for name in cluster_config.get("applications", ["Spark"])],
        "Instances": instances,
        "VisibleToAllUsers": True,
        "JobFlowRole": cluster_config["job_flow_role"],
        "ServiceRole": cluster_config["service_role"],
        "LogUri": config["aws"]["log_uri"],
    }


def build_step(config: dict[str, Any], experiment: EmrExperiment) -> dict[str, Any]:
    executor_count = max(experiment.nodes - 1, 1)
    args = [
        "spark-submit",
        "--deploy-mode",
        "cluster",
        "--conf",
        "spark.dynamicAllocation.enabled=false",
        "--conf",
        "spark.dynamicAllocation.preallocateExecutors=false",
        "--num-executors",
        str(executor_count),
        "--executor-cores",
        "2",
        "--executor-memory",
        "4g",
    ]
    py_files_uri = config["aws"].get("spark_py_files_uri")
    if py_files_uri:
        args.extend(["--py-files", py_files_uri])

    args.extend(
        [
        experiment.script_uri,
        "--input",
        experiment.dataset_uri,
        "--output",
        experiment.output_uri,
        ]
    )
    return {
        "Name": f"{experiment.workload}-step",
        "ActionOnFailure": "TERMINATE_CLUSTER",
        "HadoopJarStep": {"Jar": "command-runner.jar", "Args": args},
    }


def run_experiment(config_path: str, experiment: EmrExperiment, dry_run: bool) -> dict[str, Any]:
    config = load_config(config_path)
    request = build_cluster_request(config, experiment)
    request["Steps"] = [build_step(config, experiment)]

    if dry_run:
        print(json.dumps(request, indent=2))
        return {"dry_run": True, "request": request}

    emr = boto3.client("emr", region_name=config["aws"]["region"])
    response = emr.run_job_flow(**request)
    print(json.dumps(response, indent=2, default=str))
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch or dry-run an EMR Spark workload.")
    parser.add_argument("--config", default="config/experiment_config.yaml")
    parser.add_argument("--workload", required=True, choices=sorted(WORKLOAD_TO_SCRIPT))
    parser.add_argument("--dataset-uri", required=True)
    parser.add_argument("--script-uri", required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--instance-type", required=True)
    parser.add_argument("--nodes", type=int, required=True)
    parser.add_argument("--submit", action="store_true", help="Actually launch EMR. Default is dry-run.")
    args = parser.parse_args()

    experiment = EmrExperiment(
        workload=args.workload,
        dataset_uri=args.dataset_uri,
        script_uri=args.script_uri,
        output_uri=args.output_uri,
        instance_type=args.instance_type,
        nodes=args.nodes,
    )
    run_experiment(args.config, experiment, dry_run=not args.submit)


if __name__ == "__main__":
    main()
