#!/usr/bin/env python3
"""Run after run_sequential_matrix.sh (or a retry) finishes or is
interrupted. Combines matrix_run_summary.csv (skipped/failed combos) with
every results_*.csv in Blob to work out what actually succeeded, failed,
or never ran.

Outputs:
  combined_results.csv       every individual run row collected from Blob
  passed_runs.csv             runs with Exit_Status=SUCCESS
  failed_or_missing_runs.csv  runs that failed or never ran
  combos_to_retry.csv         unique (region, vm_size, nodes) needing a retry
  retry_lists/<region>_<size>_n<nodes>.csv  exact runs to redo per combo
"""

import argparse
import csv
import os
from azure.storage.blob import BlobServiceClient


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--storage-account", required=True)
    p.add_argument("--storage-key", required=True)
    p.add_argument("--results-container", default="datasets")
    p.add_argument("--summary-csv", default="matrix_run_summary.csv")
    p.add_argument("--regions", required=True, help="comma-separated")
    p.add_argument("--vm-sizes", required=True, help="comma-separated")
    p.add_argument("--node-counts", required=True, help="comma-separated")
    p.add_argument("--dataset-sizes", required=True, help="comma-separated MB values")
    p.add_argument("--workloads", required=True, help="comma-separated")
    p.add_argument("--repetitions", type=int, required=True)
    args = p.parse_args()

    regions = args.regions.split(",")
    vm_sizes = args.vm_sizes.split(",")
    node_counts = [int(x) for x in args.node_counts.split(",")]
    dataset_sizes = [int(x) for x in args.dataset_sizes.split(",")]
    workloads = args.workloads.split(",")

    # Combos skipped (quota) or failed entirely
    skipped_or_failed_combos = {}  # (region, size, nodes) -> reason
    if os.path.isfile(args.summary_csv):
        with open(args.summary_csv, newline="") as f:
            for row in csv.DictReader(f):
                if row["status"] in ("SKIPPED", "FAILED"):
                    key = (row["region"], row["vm_size"], int(row["nodes"]))
                    skipped_or_failed_combos[key] = row["status"] + ": " + row.get("note", "")

    # Download every results_*.csv from Blob
    conn_str = (
        f"DefaultEndpointsProtocol=https;AccountName={args.storage_account};"
        f"AccountKey={args.storage_key};EndpointSuffix=core.windows.net"
    )
    client = BlobServiceClient.from_connection_string(conn_str)
    container = client.get_container_client(args.results_container)

    combined_rows = []
    for blob in container.list_blobs(name_starts_with="results/"):
        content = container.download_blob(blob.name).readall().decode()
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            combined_rows.append(row)

    with open("combined_results.csv", "w", newline="") as f:
        if combined_rows:
            writer = csv.DictWriter(f, fieldnames=combined_rows[0].keys())
            writer.writeheader()
            writer.writerows(combined_rows)
    print(f"Pulled {len(combined_rows)} individual run rows from Blob into combined_results.csv")

    # actual: (region, vm_size, nodes, dataset_size_mb, workload, run_number) -> Exit_Status
    actual = {}
    for row in combined_rows:
        key = (
            row["Region"], row["VM_Size"], int(row["Nodes"]),
            int(row["Dataset_Size_MB"]), row["Workload"], int(row["Run_Number"]),
        )
        actual[key] = row["Exit_Status"]

    # Build the expected full matrix and diff against actual
    passed_rows = []
    failed_or_missing = []
    retry_combo_lists = {}  # (region, size, nodes) -> list of (size_mb, workload, run_num)

    for region in regions:
        for size in vm_sizes:
            for nodes in node_counts:
                combo_key = (region, size, nodes)
                combo_note = skipped_or_failed_combos.get(combo_key)

                for size_mb in dataset_sizes:
                    for workload in workloads:
                        for run_num in range(1, args.repetitions + 1):
                            key = (region, size, nodes, size_mb, workload, run_num)
                            status = actual.get(key)

                            if status == "SUCCESS":
                                passed_rows.append({
                                    "Region": region, "VM_Size": size, "Nodes": nodes,
                                    "Dataset_Size_MB": size_mb, "Workload": workload,
                                    "Run_Number": run_num,
                                })
                            else:
                                if combo_note:
                                    reason = combo_note
                                elif status == "FAILED":
                                    reason = "run FAILED"
                                else:
                                    reason = "never ran / missing"

                                failed_or_missing.append({
                                    "Region": region, "VM_Size": size, "Nodes": nodes,
                                    "Dataset_Size_MB": size_mb, "Workload": workload,
                                    "Run_Number": run_num, "Reason": reason,
                                })

                                # Don't retry combos that are permanently unrunnable (quota SKIP)
                                if not (combo_note and combo_note.startswith("SKIPPED")):
                                    retry_combo_lists.setdefault(combo_key, []).append(
                                        (size_mb, workload, run_num)
                                    )

    with open("passed_runs.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Region", "VM_Size", "Nodes", "Dataset_Size_MB", "Workload", "Run_Number"])
        writer.writeheader()
        writer.writerows(passed_rows)

    with open("failed_or_missing_runs.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Region", "VM_Size", "Nodes", "Dataset_Size_MB", "Workload", "Run_Number", "Reason"])
        writer.writeheader()
        writer.writerows(failed_or_missing)

    os.makedirs("retry_lists", exist_ok=True)
    with open("combos_to_retry.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["region", "vm_size", "nodes", "retry_list_path"])
        for (region, size, nodes), tuples in retry_combo_lists.items():
            fname = f"retry_lists/{region}_{size}_n{nodes}.csv"
            with open(fname, "w", newline="") as rf:
                rw = csv.writer(rf)
                rw.writerow(["Dataset_Size_MB", "Workload", "Run_Number"])
                rw.writerows(tuples)
            writer.writerow([region, size, nodes, fname])

    print(f"\nPassed:          {len(passed_rows)}")
    print(f"Failed/missing:  {len(failed_or_missing)}")
    print(f"Combos to retry: {len(retry_combo_lists)}  -> see combos_to_retry.csv")
    print("Per-combo retry lists written to retry_lists/")
    print("\nNext: ./retry_failed.sh")


if __name__ == "__main__":
    main()
