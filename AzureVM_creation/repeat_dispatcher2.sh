#!/usr/bin/env bash
# Faster follow-on to repeat_dispatcher.sh: uses RUN_TAG-based unique VM
# naming so it can run MULTIPLE concurrent instances of the SAME
# (size,nodes) combo (the first dispatcher could only ever run one of each
# of the 4 valid types at once, leaving real vCPU headroom idle). Checks
# ACTUAL live Azure vCPU usage in the region (not just its own tracking)
# before every launch, so it coexists safely with any other process still
# creating/deleting VMs in the same resource group.
set -e
source ./common.sh
source ./combo_runner.sh

REGION="southeastasia"
SUMMARY_FILE="repeat_run_summary.csv"
[ -f "$SUMMARY_FILE" ] || echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

CAP=32

# job queue: "size nodes vcpu tag" - enough repeats to comfortably clear
# the remaining row target, biased toward cheaper combos, true parallel
# repeats now allowed via unique tags
QUEUE=(
  "Standard_D2s_v3 2 4 r1"
  "Standard_D2s_v3 2 4 r2"
  "Standard_D2s_v3 4 8 r1"
  "Standard_D4s_v3 2 8 r1"
  "Standard_D2s_v3 4 8 r2"
  "Standard_D4s_v3 4 16 r1"
  "Standard_D2s_v3 2 4 r3"
  "Standard_D4s_v3 2 8 r2"
)

declare -a ACTIVE_PIDS=()
declare -a ACTIVE_VCPU=()

# real, live vCPU-per-node for the only two families in play here
vcpu_for_size() {
  case "$1" in
    Standard_D2s_v3) echo 2 ;;
    Standard_D4s_v3) echo 4 ;;
    *) echo 0 ;;
  esac
}

live_used_vcpu() {
  local total=0
  while read -r size; do
    [ -z "$size" ] && continue
    local per
    per=$(vcpu_for_size "$size")
    total=$((total + per))
  done < <(az vm list -g "$RESOURCE_GROUP" --query "[].hardwareProfile.vmSize" -o tsv 2>/dev/null)
  echo "$total"
}

reap_finished() {
  local new_pids=() new_vcpu=()
  for i in "${!ACTIVE_PIDS[@]}"; do
    if kill -0 "${ACTIVE_PIDS[$i]}" 2>/dev/null; then
      new_pids+=("${ACTIVE_PIDS[$i]}")
      new_vcpu+=("${ACTIVE_VCPU[$i]}")
    else
      echo "$(date '+%H:%M:%S') job finished (self-tracked slot freed)"
    fi
  done
  ACTIVE_PIDS=("${new_pids[@]}")
  ACTIVE_VCPU=("${new_vcpu[@]}")
}

while [ "${#QUEUE[@]}" -gt 0 ] || [ "${#ACTIVE_PIDS[@]}" -gt 0 ]; do
  reap_finished
  live_used=$(live_used_vcpu)

  remaining_queue=()
  for job in "${QUEUE[@]}"; do
    read -r size nodes vcpu tag <<< "$job"
    if [ $((live_used + vcpu)) -le "$CAP" ]; then
      echo "$(date '+%H:%M:%S') launching $size x$nodes tag=$tag (${vcpu}vCPU, live_used ${live_used}->$((live_used+vcpu))/$CAP)"
      ( RUN_TAG="$tag" run_combo "$REGION" "$size" "$nodes" ) &
      pid=$!
      ACTIVE_PIDS+=("$pid")
      ACTIVE_VCPU+=("$vcpu")
      live_used=$((live_used + vcpu))
    else
      remaining_queue+=("$job")
    fi
  done
  QUEUE=("${remaining_queue[@]}")

  if [ "${#QUEUE[@]}" -gt 0 ] || [ "${#ACTIVE_PIDS[@]}" -gt 0 ]; then
    sleep 30
  fi
done

echo "All repeat jobs (batch 2) finished. See $SUMMARY_FILE."
