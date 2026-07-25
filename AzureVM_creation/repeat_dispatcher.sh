#!/usr/bin/env bash
# One-off: run repeat passes of the ONLY combos that actually work in
# southeastasia (D2s_v3/D4s_v3 - the v4-family hits genuine SkuNotAvailable
# regional capacity shortage every time, not a quota issue) to add more
# successful data rows. Self-manages concurrency against the region's real
# 32-vCPU DSv3 family cap: never runs two jobs of the SAME (size,nodes) at
# once (would collide on deterministic VM names), and never lets total
# active vCPU exceed the cap.
set -e
source ./common.sh
source ./combo_runner.sh

REGION="southeastasia"
SUMMARY_FILE="repeat_run_summary.csv"
[ -f "$SUMMARY_FILE" ] || echo "region,vm_size,nodes,status,note" > "$SUMMARY_FILE"

# job queue: "size nodes vcpu" - 2 repeats each of the 4 known-good combos,
# ordered cheapest-first so parallelism ramps up fast without wasted idle cap
QUEUE=(
  "Standard_D2s_v3 2 4"
  "Standard_D2s_v3 4 8"
  "Standard_D4s_v3 2 8"
  "Standard_D2s_v3 2 4"
  "Standard_D4s_v3 4 16"
  "Standard_D2s_v3 4 8"
  "Standard_D4s_v3 2 8"
  "Standard_D4s_v3 4 16"
)

CAP=32
declare -a ACTIVE_PIDS=()
declare -a ACTIVE_KEYS=()
declare -a ACTIVE_VCPU=()

used_vcpu() {
  local total=0
  for v in "${ACTIVE_VCPU[@]}"; do total=$((total + v)); done
  echo "$total"
}

reap_finished() {
  local new_pids=() new_keys=() new_vcpu=()
  for i in "${!ACTIVE_PIDS[@]}"; do
    if kill -0 "${ACTIVE_PIDS[$i]}" 2>/dev/null; then
      new_pids+=("${ACTIVE_PIDS[$i]}")
      new_keys+=("${ACTIVE_KEYS[$i]}")
      new_vcpu+=("${ACTIVE_VCPU[$i]}")
    else
      echo "$(date '+%H:%M:%S') job finished: ${ACTIVE_KEYS[$i]}"
    fi
  done
  ACTIVE_PIDS=("${new_pids[@]}")
  ACTIVE_KEYS=("${new_keys[@]}")
  ACTIVE_VCPU=("${new_vcpu[@]}")
}

key_active() {
  local key="$1"
  for k in "${ACTIVE_KEYS[@]}"; do
    [ "$k" == "$key" ] && return 0
  done
  return 1
}

while [ "${#QUEUE[@]}" -gt 0 ] || [ "${#ACTIVE_PIDS[@]}" -gt 0 ]; do
  reap_finished

  # try to launch as many queued jobs as currently fit
  remaining_queue=()
  for job in "${QUEUE[@]}"; do
    read -r size nodes vcpu <<< "$job"
    key="${size}_${nodes}"
    current_used=$(used_vcpu)
    if ! key_active "$key" && [ $((current_used + vcpu)) -le "$CAP" ]; then
      echo "$(date '+%H:%M:%S') launching $size x$nodes (${vcpu}vCPU, used ${current_used}->$((current_used+vcpu))/$CAP)"
      ( run_combo "$REGION" "$size" "$nodes" ) &
      pid=$!
      ACTIVE_PIDS+=("$pid")
      ACTIVE_KEYS+=("$key")
      ACTIVE_VCPU+=("$vcpu")
    else
      remaining_queue+=("$job")
    fi
  done
  QUEUE=("${remaining_queue[@]}")

  if [ "${#QUEUE[@]}" -gt 0 ] || [ "${#ACTIVE_PIDS[@]}" -gt 0 ]; then
    sleep 30
  fi
done

echo "All repeat jobs finished. See $SUMMARY_FILE."
