#!/usr/bin/env python3
"""
Run this ON THE MASTER VM after setup_cluster.sh has started the cluster.

Loops: for each dataset size -> download once (untimed) -> replicate to all
worker nodes (untimed) -> for each workload type -> for each repetition ->
time ONLY the spark-submit call -> record full metadata row -> delete
local dataset copy before moving to the next size -> upload results.csv to Blob.

Usage:
  python3 run_benchmark.py \
      --region centralindia \
      --vm-size Standard_D4s_v3 \
      --vcpu 4 --ram-gb 16 \
      --nodes 4 \
      --master-url spark://10.0.0.4:7077 \
      --worker-ips 10.0.0.5,10.0.0.6,10.0.0.7 \
      --storage-account CHANGE_ME --storage-key CHANGE_ME \
      --dataset-container datasets --results-container datasets \
      --dataset-sizes 10,100,500,1024,2048,3072,5120 \
      --workloads cpu,memory,io \
      --repetitions 3
"""

import argparse
import subprocess
import time
import threading
import statistics
import csv
import os
import shlex
import shutil
import socket
import requests
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient

SPARK_HOME = os.environ.get("SPARK_HOME", "/opt/spark")
LOCAL_DATASET_DIR = "/opt/benchmark/datasets"
LOCAL_JOBS_DIR = "/opt/benchmark/spark_jobs"
LOCAL_OUTPUT_DIR = "/opt/benchmark/output"
RESULTS_CSV = "/opt/benchmark/results.csv"

CSV_FIELDS = [
    "Region", "VM_Size", "vCPU", "RAM_GB", "Nodes",
    "Spark_Version", "Java_Version",
    "Dataset", "Dataset_Size_MB", "Workload", "Run_Number",
    "Timestamp", "Runtime_Minutes", "CPU_Avg_Pct", "Cost_USD", "Exit_Status",
]

cpu_samples = []
sampling = False


def sample_cpu():
    global sampling
    while sampling:
        try:
            out = subprocess.check_output(["mpstat", "1", "1"], text=True)
            last_line = [l for l in out.strip().split("\n") if l][-1]
            idle = float(last_line.split()[-1])
            cpu_samples.append(round(100 - idle, 2))
        except Exception:
            pass
        time.sleep(5)


def get_spark_version():
    out = subprocess.check_output([f"{SPARK_HOME}/bin/spark-submit", "--version"],
                                   stderr=subprocess.STDOUT, text=True)
    for line in out.splitlines():
        if "version" in line.lower():
            return line.strip().split()[-1]
    return "unknown"


def get_java_version():
    out = subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT, text=True)
    return out.splitlines()[0].split('"')[1]


def get_hourly_price(vm_size, region):
    filt = (
        f"armRegionName eq '{region}' and armSkuName eq '{vm_size}' "
        f"and priceType eq 'Consumption' and serviceName eq 'Virtual Machines'"
    )
    url = "https://prices.azure.com/api/retail/prices"
    resp = requests.get(url, params={"api-version": "2023-01-01-preview", "$filter": filt})
    items = [
        i for i in resp.json().get("Items", [])
        if "Windows" not in i.get("productName", "")
        and "Spot" not in i.get("meterName", "")
        and "Low Priority" not in i.get("meterName", "")
    ]
    if not items:
        return None
    return items[0]["retailPrice"]


def download_dataset(blob_client, container, size_mb, dest_dir):
    """Untimed. Downloads once to master's local disk.

    Blob naming in the datasets container isn't fully consistent
    (e.g. events_1024mb.csv but events_2048.csv with no "mb"), so try
    both forms rather than assuming one pattern.
    """
    container_client = blob_client.get_container_client(container)
    candidates = [f"events_{size_mb}mb.csv", f"events_{size_mb}.csv"]
    blob_name = next(
        (name for name in candidates if container_client.get_blob_client(name).exists()),
        None,
    )
    if blob_name is None:
        raise FileNotFoundError(
            f"No blob found for {size_mb}MB in container '{container}' (tried {candidates})"
        )

    local_path = os.path.join(dest_dir, f"{size_mb}MB.csv")
    os.makedirs(dest_dir, exist_ok=True)
    print(f"Downloading {blob_name} (excluded from timer)...")
    with open(local_path, "wb") as f:
        f.write(container_client.download_blob(blob_name).readall())
    return local_path


def replicate_to_workers(local_path, worker_ips, admin_user, admin_password):
    """Untimed. Copies the dataset to every worker node's local disk."""
    remote_dir = "/opt/benchmark/datasets/"
    for ip in worker_ips:
        print(f"Replicating dataset to worker {ip} (excluded from timer)...")
        cmd = (
            f"sshpass -p {shlex.quote(admin_password)} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"{admin_user}@{ip} 'mkdir -p {remote_dir}' && "
            f"sshpass -p {shlex.quote(admin_password)} scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"{local_path} {admin_user}@{ip}:{remote_dir}"
        )
        subprocess.run(cmd, shell=True, check=True)


def cleanup_dataset(local_path, worker_ips, admin_user, admin_password):
    """Removes the dataset from master + all workers before moving to next size."""
    if os.path.exists(local_path):
        os.remove(local_path)
    fname = os.path.basename(local_path)
    for ip in worker_ips:
        cmd = (
            f"sshpass -p {shlex.quote(admin_password)} ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"{admin_user}@{ip} 'rm -f /opt/benchmark/datasets/{fname}'"
        )
        subprocess.run(cmd, shell=True)


def run_one_job(master_url, job_script, dataset_local_path, workload, vcpu):
    """TIMED. Only the spark-submit call is inside the timer.

    Job scripts take --input/--output (argparse), not positional args.
    io_heavy requires --output (it reads back its own write), which needs
    the write and the read-back to land on the same local filesystem. In
    the real cluster the write happens on the worker's executor while the
    driver (which plans the read) is on the master, so a plain local path
    doesn't work there, and Azure Blob output hits a Hadoop-client jar
    version mismatch in this Spark build (hadoop-azure needs internal
    hadoop-common classes not present in Spark's trimmed client jars).
    So io runs with --master local[N] instead of the cluster URL: driver
    and "executors" share one JVM/filesystem, sidestepping the mismatch
    entirely. Tradeoff: io numbers reflect single-node I/O, not the
    cluster's combined disk throughput - node count won't move them the
    way it moves cpu/memory.
    """
    global sampling, cpu_samples
    cpu_samples = []
    sampling = True
    t = threading.Thread(target=sample_cpu, daemon=True)
    t.start()

    submit_master = f"local[{vcpu}]" if workload == "io" else master_url
    cmd = [
        f"{SPARK_HOME}/bin/spark-submit",
        "--master", submit_master,
        job_script,
        "--input", dataset_local_path,
    ]
    output_dir = None
    if workload == "io":
        output_dir = os.path.join(LOCAL_OUTPUT_DIR, f"io_{int(time.time())}")
        cmd += ["--output", output_dir]

    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end = time.time()

    sampling = False
    t.join(timeout=10)

    if output_dir:
        shutil.rmtree(output_dir, ignore_errors=True)
        shutil.rmtree(f"{output_dir}_summary", ignore_errors=True)

    runtime_minutes = round((end - start) / 60, 4)
    cpu_avg = round(statistics.mean(cpu_samples), 2) if cpu_samples else 0.0
    exit_status = "SUCCESS" if result.returncode == 0 else "FAILED"
    if exit_status == "FAILED":
        print("Job failed:", result.stderr[-1500:])

    return runtime_minutes, cpu_avg, exit_status


def upload_results(blob_client, container, local_csv):
    container_client = blob_client.get_container_client(container)
    # HOSTNAME isn't reliably exported to child processes (e.g. missing
    # entirely when launched via nohup over a non-interactive SSH command,
    # which silently collapsed every such run onto the same overwritten
    # "results_unknown.csv" blob). socket.gethostname() asks the OS directly.
    # The timestamp suffix is required too: a retry recreates a VM with the
    # SAME hostname and starts from an empty local results.csv, so without
    # it a retry's (smaller, partial) upload would overwrite - not add to -
    # the original full-matrix results already sitting at that blob path.
    blob_name = f"results/results_{socket.gethostname()}_{int(time.time())}.csv"
    with open(local_csv, "rb") as f:
        container_client.upload_blob(name=blob_name, data=f, overwrite=True)
    print(f"Uploaded results to {blob_name}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    p.add_argument("--vm-size", required=True)
    p.add_argument("--vcpu", required=True, type=int)
    p.add_argument("--ram-gb", required=True, type=int)
    p.add_argument("--nodes", required=True, type=int)
    p.add_argument("--master-url", required=True, help="e.g. spark://10.0.0.4:7077")
    p.add_argument("--worker-ips", default="", help="comma-separated, empty if nodes=1")
    p.add_argument("--admin-username", required=True)
    p.add_argument("--admin-password", required=True)
    p.add_argument("--storage-account", required=True)
    p.add_argument("--storage-key", required=True)
    p.add_argument("--dataset-container", default="datasets")
    p.add_argument("--results-container", default="datasets")
    p.add_argument("--dataset-sizes", default="10,100,500,1000,5000")
    p.add_argument("--workloads", default="cpu,memory,io")
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--retry-list", default=None,
                    help="Path to CSV with columns Dataset_Size_MB,Workload,Run_Number - "
                         "if given, only these specific runs are executed instead of the full matrix.")
    args = p.parse_args()

    retry_tuples = None
    if args.retry_list:
        retry_tuples = []
        with open(args.retry_list, newline="") as f:
            for row in csv.DictReader(f):
                retry_tuples.append((int(row["Dataset_Size_MB"]), row["Workload"], int(row["Run_Number"])))
        print(f"Retry mode: {len(retry_tuples)} specific runs to redo.")

    worker_ips = [ip for ip in args.worker_ips.split(",") if ip]
    if retry_tuples:
        dataset_sizes = sorted(set(t[0] for t in retry_tuples))
    else:
        dataset_sizes = [int(x) for x in args.dataset_sizes.split(",")]
    workloads = args.workloads.split(",")

    conn_str = (
        f"DefaultEndpointsProtocol=https;AccountName={args.storage_account};"
        f"AccountKey={args.storage_key};EndpointSuffix=core.windows.net"
    )
    blob_client = BlobServiceClient.from_connection_string(conn_str)

    spark_version = get_spark_version()
    java_version = get_java_version()

    file_exists = os.path.isfile(RESULTS_CSV)
    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
    csv_file = open(RESULTS_CSV, "a", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    if not file_exists:
        writer.writeheader()

    for size_mb in dataset_sizes:
        local_path = download_dataset(blob_client, args.dataset_container, size_mb, LOCAL_DATASET_DIR)
        if worker_ips:
            replicate_to_workers(local_path, worker_ips, args.admin_username, args.admin_password)

        for workload in workloads:
            job_script = os.path.join(LOCAL_JOBS_DIR, f"{workload}_heavy.py")
            run_numbers = range(1, args.repetitions + 1)
            if retry_tuples:
                run_numbers = [t[2] for t in retry_tuples if t[0] == size_mb and t[1] == workload]
                if not run_numbers:
                    continue

            for run_num in run_numbers:
                print(f"\n=== {args.vm_size} | {args.nodes} nodes | {size_mb}MB | {workload} | run {run_num} ===")
                runtime_min, cpu_avg, exit_status = run_one_job(args.master_url, job_script, local_path, workload, args.vcpu)

                hourly_price = get_hourly_price(args.vm_size, args.region)
                # cost = hourly rate x number of nodes x hours consumed by this run
                cost_usd = (
                    round(hourly_price * args.nodes * (runtime_min / 60), 4)
                    if hourly_price else ""
                )

                row = {
                    "Region": args.region,
                    "VM_Size": args.vm_size,
                    "vCPU": args.vcpu,
                    "RAM_GB": args.ram_gb,
                    "Nodes": args.nodes,
                    "Spark_Version": spark_version,
                    "Java_Version": java_version,
                    "Dataset": f"{size_mb}MB.csv",
                    "Dataset_Size_MB": size_mb,
                    "Workload": workload,
                    "Run_Number": run_num,
                    "Timestamp": datetime.now(timezone.utc).isoformat(),
                    "Runtime_Minutes": runtime_min,
                    "CPU_Avg_Pct": cpu_avg,
                    "Cost_USD": cost_usd,
                    "Exit_Status": exit_status,
                }
                writer.writerow(row)
                csv_file.flush()
                print(row)
                try:
                    upload_results(blob_client, args.results_container, RESULTS_CSV)
                except Exception as exc:
                    print(f"Warning: could not upload partial results yet: {exc}")

        cleanup_dataset(local_path, worker_ips, args.admin_username, args.admin_password)

    csv_file.close()
    upload_results(blob_client, args.results_container, RESULTS_CSV)
    print("\nAll runs complete for this cluster configuration.")


if __name__ == "__main__":
    main()
