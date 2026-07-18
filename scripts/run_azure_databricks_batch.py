"""Run Azure Databricks Spark experiments sequentially.

The script submits one Databricks job run at a time, waits for completion, and
stores successful metrics in a separate Azure performance CSV. Failed runs are
stored in a failure CSV so they can be rerun manually.

Authentication:
  export DATABRICKS_HOST="https://adb-....azuredatabricks.net"
  export DATABRICKS_TOKEN="..."
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


WORKLOAD_TO_SCRIPT = {
    "cpu-heavy": "cpu_heavy.py",
    "memory-heavy": "memory_heavy.py",
    "io-heavy": "io_heavy.py",
}

SUCCESS_COLUMNS = [
    "cloud_provider",
    "region",
    "pricing_model",
    "dataset_size_mb",
    "workload_type",
    "instance_type",
    "nodes",
    "runtime_minutes",
    "cost_usd",
    "cpu_avg_pct",
    "memory_avg_pct",
    "source",
]

FAILED_COLUMNS = [
    "timestamp_utc",
    "region",
    "dataset_size_mb",
    "workload_type",
    "instance_type",
    "nodes",
    "stage",
    "run_id",
    "state",
    "reason",
    "manual_command",
]


@dataclass(frozen=True)
class AzureMetric:
    cloud_provider: str
    region: str
    pricing_model: str
    dataset_size_mb: float
    workload_type: str
    instance_type: str
    nodes: int
    runtime_minutes: float
    cost_usd: float
    cpu_avg_pct: float | None = None
    memory_avg_pct: float | None = None
    source: str = "azure-databricks"


@dataclass(frozen=True)
class FailedExperiment:
    timestamp_utc: str
    region: str
    dataset_size_mb: float
    workload_type: str
    instance_type: str
    nodes: int
    stage: str
    run_id: str
    state: str
    reason: str
    manual_command: str


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
    if value in {"on-demand", "ondemand", "consumption"}:
        return "on-demand"
    if value in {"spot", "low priority", "low-priority"}:
        return "spot"
    return value


def tier_matches_pricing_model(tier: str, pricing_model: str) -> bool:
    tier_lower = tier.lower()
    pricing_model = normalize_pricing_model(pricing_model)
    if pricing_model == "spot":
        return "spot" in tier_lower or "low priority" in tier_lower
    return "spot" not in tier_lower and "low priority" not in tier_lower


def lookup_azure_price(price_path: str, region: str, instance_type: str, pricing_model: str) -> float:
    path = Path(price_path)
    if not path.exists():
        raise FileNotFoundError(f"Azure price file not found: {price_path}")

    matches: list[float] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_region = (row.get("region") or "").strip().lower()
            row_vm_size = (row.get("vm_size") or row.get("instance_type") or "").strip()
            row_tier = (row.get("tier") or "").strip()
            price = row.get("price_usd_hr") or row.get("hourly_price_usd") or row.get("price_usd_per_hr")
            if row_region != region.lower():
                continue
            if row_vm_size != instance_type:
                continue
            if not tier_matches_pricing_model(row_tier, pricing_model):
                continue
            if price in {None, ""}:
                continue
            matches.append(float(price))

    if not matches:
        raise ValueError(
            "No Azure price found for "
            f"region={region}, vm_size={instance_type}, pricing_model={pricing_model} "
            f"in {price_path}"
        )
    return round(min(matches), 6)


def size_label(dataset_size_mb: float) -> str:
    return f"{int(dataset_size_mb)}mb"


def safe_name(value: str) -> str:
    return value.replace(".", "").replace("_", "").replace("-", "")


def format_template(template: str, region: str, dataset_size_mb: float, workload: str, instance_type: str, nodes: int) -> str:
    script_name = WORKLOAD_TO_SCRIPT[workload]
    return template.format(
        region=region,
        size_mb=int(dataset_size_mb),
        size_label=size_label(dataset_size_mb),
        workload=workload,
        short_workload=workload.replace("-heavy", ""),
        script_name=script_name,
        instance_type=instance_type,
        safe_instance=safe_name(instance_type),
        nodes=nodes,
        timestamp=int(time.time()),
    )


def storage_account_from_uri(uri: str) -> str | None:
    marker = "@"
    if marker not in uri:
        return None
    after_at = uri.split(marker, 1)[1]
    return after_at.split(".", 1)[0] or None


class DatabricksClient:
    def __init__(self, host: str, token: str, verify_tls: bool = True):
        self.host = host.rstrip("/")
        self.token = token
        if verify_tls:
            try:
                import certifi

                self.ssl_context = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                self.ssl_context = ssl.create_default_context()
        else:
            self.ssl_context = ssl._create_unverified_context()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"{self.host}{path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60, context=self.ssl_context) as response:
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Databricks API {method} {path} failed: HTTP {exc.code}: {error_body}") from exc
        if not data:
            return {}
        return json.loads(data)

    def submit_run(self, payload: dict[str, Any]) -> int:
        response = self.request("POST", "/api/2.1/jobs/runs/submit", payload)
        return int(response["run_id"])

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self.request("GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")

    def get_run_output(self, run_id: int) -> dict[str, Any]:
        return self.request("GET", f"/api/2.1/jobs/runs/get-output?run_id={run_id}")


def build_run_payload(
    args: argparse.Namespace,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
) -> dict[str, Any]:
    dataset_uri = format_template(args.dataset_uri_template, args.region, dataset_size_mb, workload, instance_type, nodes)
    script_uri = format_template(args.script_uri_template, args.region, dataset_size_mb, workload, instance_type, nodes)
    output_uri = format_template(args.output_uri_template, args.region, dataset_size_mb, workload, instance_type, nodes)

    task = {
        "task_key": "spark_workload",
        "spark_python_task": {
            "python_file": script_uri,
            "parameters": ["--input", dataset_uri, "--output", output_uri],
        },
    }

    if args.existing_cluster_id:
        task["existing_cluster_id"] = args.existing_cluster_id
    else:
        spark_conf = {
            "spark.dynamicAllocation.enabled": "false",
            "spark.dynamicAllocation.preallocateExecutors": "false",
        }
        storage_key = os.environ.get("AZURE_STORAGE_KEY", "").strip()
        storage_account = args.azure_storage_account or storage_account_from_uri(dataset_uri)
        if storage_key and storage_account:
            spark_conf[f"fs.azure.account.key.{storage_account}.dfs.core.windows.net"] = storage_key

        new_cluster = {
            "spark_version": args.spark_version,
            "node_type_id": instance_type,
            "driver_node_type_id": instance_type,
            "spark_conf": spark_conf,
        }
        if nodes <= 1:
            new_cluster["num_workers"] = 0
            new_cluster["spark_conf"]["spark.master"] = "local[*]"
            new_cluster["spark_conf"]["spark.databricks.cluster.profile"] = "singleNode"
            new_cluster["custom_tags"] = {"ResourceClass": "SingleNode"}
        else:
            new_cluster["num_workers"] = nodes - 1
        task["new_cluster"] = new_cluster

    return {
        "run_name": f"cost-aware-{args.region}-{workload}-{int(dataset_size_mb)}mb-{safe_name(instance_type)}-{nodes}",
        "tasks": [task],
        "timeout_seconds": int(args.step_timeout_minutes * 60),
    }


def append_success(path: str, metric: AzureMetric) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output.exists()
    with open(output, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUCCESS_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(metric))


def append_failed(path: str, failed: FailedExperiment) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output.exists()
    with open(output, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FAILED_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(failed))


def manual_command(args: argparse.Namespace, dataset_size_mb: float, workload: str, instance_type: str, nodes: int) -> str:
    return (
        "python scripts/run_azure_databricks_batch.py "
        f"--region {args.region} "
        f"--dataset-sizes-mb {int(dataset_size_mb)} "
        f"--workloads {workload} "
        f"--instance-types {instance_type} "
        f"--nodes-list {nodes} "
        f"--dataset-uri-template '{args.dataset_uri_template}' "
        f"--script-uri-template '{args.script_uri_template}' "
        f"--output-uri-template '{args.output_uri_template}' "
        f"--price-path {args.price_path} "
        f"--step-timeout-minutes {args.step_timeout_minutes:g} "
        "--submit"
    )


def record_failure(
    args: argparse.Namespace,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
    stage: str,
    run_id: str = "",
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
            run_id=run_id,
            state=state,
            reason=reason[:1500],
            manual_command=manual_command(args, dataset_size_mb, workload, instance_type, nodes),
        ),
    )


def run_finished(run: dict[str, Any]) -> bool:
    life_cycle = run.get("state", {}).get("life_cycle_state", "")
    return life_cycle in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}


def run_success(run: dict[str, Any]) -> bool:
    state = run.get("state", {})
    return state.get("life_cycle_state") == "TERMINATED" and state.get("result_state") == "SUCCESS"


def run_state_text(run: dict[str, Any]) -> str:
    state = run.get("state", {})
    return f"{state.get('life_cycle_state', '')}/{state.get('result_state', '')}".strip("/")


def run_failure_reason(run: dict[str, Any]) -> str:
    state = run.get("state", {})
    return state.get("state_message") or json.dumps(state, default=str)


def task_run_id(run: dict[str, Any], fallback_run_id: int) -> int:
    tasks = run.get("tasks") or []
    if tasks and tasks[0].get("run_id"):
        return int(tasks[0]["run_id"])
    return fallback_run_id


def detailed_failure_reason(client: DatabricksClient, run: dict[str, Any], fallback_run_id: int) -> str:
    reason = run_failure_reason(run)
    try:
        output = client.get_run_output(task_run_id(run, fallback_run_id))
    except Exception as exc:
        return f"{reason} | Could not fetch run output: {type(exc).__name__}: {exc}"

    parts = [reason]
    if output.get("error"):
        parts.append(str(output["error"]))
    if output.get("error_trace"):
        parts.append(str(output["error_trace"]))
    if output.get("logs"):
        parts.append(str(output["logs"])[-3000:])
    return " | ".join(part for part in parts if part)


def runtime_minutes_from_run(run: dict[str, Any]) -> float:
    execution_ms = run.get("execution_duration") or 0
    setup_ms = run.get("setup_duration") or 0
    cleanup_ms = run.get("cleanup_duration") or 0
    total_ms = execution_ms + setup_ms + cleanup_ms
    if total_ms <= 0:
        start = run.get("start_time") or 0
        end = run.get("end_time") or 0
        total_ms = max(end - start, 0)
    return round(total_ms / 60000.0, 6)


def calculate_cost(hourly_price_usd: float, nodes: int, runtime_minutes: float) -> float:
    return round(hourly_price_usd * nodes * (runtime_minutes / 60.0), 6)


def wait_for_run(client: DatabricksClient, run_id: int, poll_seconds: int) -> dict[str, Any]:
    while True:
        run = client.get_run(run_id)
        print(f"Databricks run {run_id} is {run_state_text(run)}")
        if run_finished(run):
            return run
        time.sleep(poll_seconds)


def run_one(
    args: argparse.Namespace,
    client: DatabricksClient,
    dataset_size_mb: float,
    workload: str,
    instance_type: str,
    nodes: int,
) -> None:
    print(f"Starting Azure {args.region} {dataset_size_mb:g}MB {workload} on {instance_type} x {nodes}")
    payload = build_run_payload(args, dataset_size_mb, workload, instance_type, nodes)

    if not args.submit:
        print(json.dumps(payload, indent=2))
        return

    try:
        run_id = client.submit_run(payload)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        print(f"SUBMIT FAILED: {reason}")
        record_failure(args, dataset_size_mb, workload, instance_type, nodes, "submit", reason=reason)
        return

    try:
        run = wait_for_run(client, run_id, args.poll_seconds)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        print(f"MONITOR FAILED: {reason}")
        record_failure(args, dataset_size_mb, workload, instance_type, nodes, "monitor", run_id=str(run_id), reason=reason)
        return

    if not run_success(run):
        reason = detailed_failure_reason(client, run, run_id)
        state = run_state_text(run)
        print(f"RUN FAILED: {run_id} ended as {state}: {reason}")
        record_failure(
            args,
            dataset_size_mb,
            workload,
            instance_type,
            nodes,
            "run",
            run_id=str(run_id),
            state=state,
            reason=reason,
        )
        return

    runtime_minutes = runtime_minutes_from_run(run)
    try:
        hourly_price_usd = (
            args.hourly_price_usd
            if args.hourly_price_usd > 0
            else lookup_azure_price(args.price_path, args.region, instance_type, args.pricing_model)
        )
        cost_usd = calculate_cost(hourly_price_usd, nodes, runtime_minutes)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        print(f"COST FAILED: {reason}")
        record_failure(args, dataset_size_mb, workload, instance_type, nodes, "cost", run_id=str(run_id), reason=reason)
        return
    append_success(
        args.output,
        AzureMetric(
            cloud_provider="Azure",
            region=args.region,
            pricing_model=args.pricing_model,
            dataset_size_mb=dataset_size_mb,
            workload_type=workload,
            instance_type=instance_type,
            nodes=nodes,
            runtime_minutes=runtime_minutes,
            cost_usd=cost_usd,
            source=f"azure-databricks:{args.region}:{run_id}",
        ),
    )
    print(f"Saved Azure run {run_id}: runtime={runtime_minutes:.4f} min cost=${cost_usd:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Azure Databricks Spark experiments sequentially.")
    parser.add_argument("--region", default="centralindia", choices=["centralindia", "southeastasia"])
    parser.add_argument("--dataset-sizes-mb", default="10,100,500,1024,5120")
    parser.add_argument("--workloads", default="cpu-heavy,memory-heavy,io-heavy")
    parser.add_argument("--instance-types", default="Standard_D4s_v5")
    parser.add_argument("--nodes-list", default="2")
    parser.add_argument("--pricing-model", default="on-demand", choices=["on-demand", "spot"])
    parser.add_argument("--price-path", default="cloud_prices/azure_prices.csv")
    parser.add_argument("--hourly-price-usd", type=float, default=0.0, help="Optional fallback/manual override.")
    parser.add_argument("--spark-version", default="14.3.x-scala2.12")
    parser.add_argument("--existing-cluster-id", default="")
    parser.add_argument("--azure-storage-account", default="")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--step-timeout-minutes", type=float, default=45)
    parser.add_argument(
        "--dataset-uri-template",
        required=True,
        help="Example: abfss://container@account.dfs.core.windows.net/data/events_{size_mb}mb.csv",
    )
    parser.add_argument(
        "--script-uri-template",
        required=True,
        help="Example: dbfs:/FileStore/spark_jobs/{script_name}",
    )
    parser.add_argument(
        "--output-uri-template",
        required=True,
        help="Example: abfss://container@account.dfs.core.windows.net/output/{region}/{workload}_{size_mb}mb_{safe_instance}_{nodes}_{timestamp}",
    )
    parser.add_argument("--output", default="data/performance/azure_databricks_performance_dataset.csv")
    parser.add_argument("--failed-output", default="data/performance/failed_azure_databricks_experiments.csv")
    parser.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Emergency workaround for local SSL certificate issues. Not recommended for final production use.",
    )
    parser.add_argument("--submit", action="store_true", help="Submit billable Databricks runs. Default is dry-run.")
    args = parser.parse_args()

    host = os.environ.get("DATABRICKS_HOST", "").strip()
    token = os.environ.get("DATABRICKS_TOKEN", "").strip()
    if args.submit and (not host or not token):
        raise SystemExit("Set DATABRICKS_HOST and DATABRICKS_TOKEN before using --submit.")

    client = (
        DatabricksClient(host, token, verify_tls=not args.insecure_skip_tls_verify)
        if args.submit
        else DatabricksClient("https://dry-run.local", "dry-run")
    )

    for dataset_size_mb in parse_sizes(args.dataset_sizes_mb):
        for workload in parse_workloads(args.workloads):
            for instance_type in parse_csv_values(args.instance_types):
                for nodes in [int(value) for value in parse_csv_values(args.nodes_list)]:
                    run_one(args, client, dataset_size_mb, workload, instance_type, nodes)

    print(f"Batch finished. Success CSV: {args.output}")
    print(f"Failed experiments CSV: {args.failed_output}")


if __name__ == "__main__":
    main()
