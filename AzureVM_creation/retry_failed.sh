#!/usr/bin/env bash
# Run after ./collect_results.sh has produced combos_to_retry.csv.
# Recreates VMs only for combos with gaps, and only redoes the specific
# missing/failed (dataset, workload, run_number) tuples - not the whole combo.
set -e
source ./common.sh
source ./combo_runner.sh

if [ ! -f combos_to_retry.csv ]; then
  echo "combos_to_retry.csv not found. Run ./collect_results.sh first."
  exit 1
fi

az group create --name "$RESOURCE_GROUP" --location "${REGIONS[0]}" --output none

# Reuse the same cloud-init file from the original run if present, else rebuild it
if [ ! -f cloud-init-final.yaml ]; then
  sed \
    -e "s/__JAVA_VERSION__/${JAVA_VERSION}/g" \
    -e "s/__SPARK_VERSION__/${SPARK_VERSION}/g" \
    -e "s/__STORAGE_ACCOUNT__/${STORAGE_ACCOUNT_NAME}/g" \
    -e "s/__STORAGE_KEY__/${STORAGE_ACCOUNT_KEY}/g" \
    -e "s/__SCRIPTS_CONTAINER__/${SCRIPTS_CONTAINER_NAME}/g" \
    -e "s/__ADMIN_USERNAME__/${ADMIN_USERNAME}/g" \
    cloud-init-template.yaml > cloud-init-final.yaml
fi

SUMMARY_FILE="retry_run_summary.csv"
echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

while IFS=',' read -r -u 3 region size nodes retry_list; do
  retry_list="${retry_list%$'\r'}"
  run_combo "$region" "$size" "$nodes" "$retry_list"
done 3< <(tail -n +2 combos_to_retry.csv)

echo ""
echo "Retry pass complete. See $SUMMARY_FILE."
echo "Run ./collect_results.sh again to confirm everything now shows PASSED."
