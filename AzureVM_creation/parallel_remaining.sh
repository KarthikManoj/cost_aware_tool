#!/usr/bin/env bash
# One-off speed-up: run specific remaining (size, nodes) combos in the
# background IN PARALLEL with whatever run_sequential_matrix.sh is already
# doing, instead of waiting for it to reach them sequentially. Only safe
# because the combos passed in here are picked so that their combined vCPU
# usage plus whatever the sequential script is/will be using stays under
# the region's per-family quota cap (checked manually before invoking this,
# not enforced here beyond the normal fits_quota() pre-check per combo).
#
# Usage: ./parallel_remaining.sh <region> "<size1> <nodes1>" "<size2> <nodes2>" ...
set -e
source ./common.sh
source ./combo_runner.sh

region="$1"; shift
SUMMARY_FILE="matrix_run_summary_${region}.csv"
[ -f "$SUMMARY_FILE" ] || echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

pids=()
for combo in "$@"; do
  read -r size nodes <<< "$combo"
  ( run_combo "$region" "$size" "$nodes" ) &
  pids+=($!)
  echo "Launched $size x$nodes as PID $!"
done

for pid in "${pids[@]}"; do
  wait "$pid"
done
echo "All parallel combos finished."
