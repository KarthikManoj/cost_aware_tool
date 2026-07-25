#!/usr/bin/env bash
# Run after run_sequential_matrix.sh finishes (or was interrupted) to build
# the pass/fail/missing lists. Safe to run multiple times.
set -e
source ./common.sh

DATASET_SIZES_CSV=$(IFS=,; echo "${DATASET_SIZES_MB[*]}")
WORKLOADS_CSV=$(IFS=,; echo "${WORKLOAD_TYPES[*]}")
REGIONS_CSV=$(IFS=,; echo "${REGIONS[*]}")
VM_SIZES_CSV=$(IFS=,; echo "${VM_SIZES[*]}")
NODE_COUNTS_CSV=$(IFS=,; echo "${NODE_COUNTS[*]}")

python3 collect_results.py \
  --storage-account "$STORAGE_ACCOUNT_NAME" \
  --storage-key "$STORAGE_ACCOUNT_KEY" \
  --results-container "$RESULTS_CONTAINER_NAME" \
  --summary-csv "matrix_run_summary.csv" \
  --regions "$REGIONS_CSV" \
  --vm-sizes "$VM_SIZES_CSV" \
  --node-counts "$NODE_COUNTS_CSV" \
  --dataset-sizes "$DATASET_SIZES_CSV" \
  --workloads "$WORKLOADS_CSV" \
  --repetitions "$REPETITIONS"
