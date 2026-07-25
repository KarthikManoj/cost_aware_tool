#!/usr/bin/env bash
# One-off resume: continues retry_failed.sh's combos_to_retry.csv from a
# given line number, for when the main pass got killed/hung partway through.
# Appends to the EXISTING retry_run_summary.csv rather than overwriting it.
set -e
source ./common.sh
source ./combo_runner.sh

SUMMARY_FILE="retry_run_summary.csv"
[ -f "$SUMMARY_FILE" ] || echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

START_LINE="${1:-10}"

while IFS=',' read -r -u 3 region size nodes retry_list; do
  retry_list="${retry_list%$'\r'}"
  run_combo "$region" "$size" "$nodes" "$retry_list"
done 3< <(tail -n "+${START_LINE}" combos_to_retry.csv)

echo ""
echo "Resume pass complete. See $SUMMARY_FILE."
