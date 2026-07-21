#!/usr/bin/env bash
# FULL RUN: walks every (region, size, node_count) combo in config.env,
# one at a time. Combos that don't fit your quota are skipped and logged.
set -e
source ./common.sh
source ./combo_runner.sh

az group create --name "$RESOURCE_GROUP" --location "${REGIONS[0]}" --output none

sed \
  -e "s|__JAVA_VERSION__|${JAVA_VERSION}|g" \
  -e "s|__SPARK_VERSION__|${SPARK_VERSION}|g" \
  -e "s|__STORAGE_ACCOUNT__|${STORAGE_ACCOUNT_NAME}|g" \
  -e "s|__STORAGE_KEY__|${STORAGE_ACCOUNT_KEY}|g" \
  -e "s|__SCRIPTS_CONTAINER__|${SCRIPTS_CONTAINER_NAME}|g" \
  -e "s|__ADMIN_USERNAME__|${ADMIN_USERNAME}|g" \
  cloud-init-template.yaml > cloud-init-final.yaml

SUMMARY_FILE="matrix_run_summary.csv"
echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

for region in "${REGIONS[@]}"; do
  for size in "${VM_SIZES[@]}"; do
    for nodes in "${NODE_COUNTS[@]}"; do
      run_combo "$region" "$size" "$nodes"
    done
  done
done

echo ""
echo "All combos processed. See $SUMMARY_FILE for a pass/fail overview."
echo "Next: run 'python3 collect_results.py' to build the detailed pass/fail run list."
