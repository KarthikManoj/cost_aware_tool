#!/usr/bin/env bash
# FULL RUN: walks every (region, size, node_count) combo in config.env,
# one at a time. Combos that don't fit your quota are skipped and logged.
# Usage:
#   ./run_sequential_matrix.sh                 # all regions in config.env
#   ./run_sequential_matrix.sh southeastasia    # just this one region
set -e
source ./common.sh
source ./combo_runner.sh

if [ -n "${1:-}" ]; then
  RUN_REGIONS=("$1")
else
  RUN_REGIONS=("${REGIONS[@]}")
fi

# A resource group's --location is just where its own metadata lives - it
# does not restrict which region VMs inside it deploy to. Re-creating an
# existing group with a different location fails, so only create it if it
# doesn't exist yet (matches create_vms.sh).
if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az group create --name "$RESOURCE_GROUP" --location "${RUN_REGIONS[0]}" --output none
fi

sed \
  -e "s|__JAVA_VERSION__|${JAVA_VERSION}|g" \
  -e "s|__SPARK_VERSION__|${SPARK_VERSION}|g" \
  -e "s|__STORAGE_ACCOUNT__|${STORAGE_ACCOUNT_NAME}|g" \
  -e "s|__STORAGE_KEY__|${STORAGE_ACCOUNT_KEY}|g" \
  -e "s|__SCRIPTS_CONTAINER__|${SCRIPTS_CONTAINER_NAME}|g" \
  -e "s|__ADMIN_USERNAME__|${ADMIN_USERNAME}|g" \
  cloud-init-template.yaml > cloud-init-final.yaml

# Scoped to the region when one is given, so two invocations targeting
# different regions (e.g. one already running southeastasia, another for
# centralindia) don't race on the same file - each only truncates/appends
# its own.
if [ -n "${1:-}" ]; then
  SUMMARY_FILE="matrix_run_summary_${1}.csv"
else
  SUMMARY_FILE="matrix_run_summary.csv"
fi
echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

for region in "${RUN_REGIONS[@]}"; do
  for size in "${VM_SIZES[@]}"; do
    for nodes in "${NODE_COUNTS[@]}"; do
      run_combo "$region" "$size" "$nodes"
    done
  done
done

echo ""
echo "All combos processed. See $SUMMARY_FILE for a pass/fail overview."
echo "Next: run 'python3 collect_results.py' to build the detailed pass/fail run list."
