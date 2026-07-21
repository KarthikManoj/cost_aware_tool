#!/bin/bash
# Shared helpers. Source this from other scripts: source ./common.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.env"

# Region -> short code used in VM names
region_abbr() {
  case "$1" in
    centralindia) echo "cin" ;;
    southeastasia) echo "sea" ;;
    *) echo "$1" | tr -d '-' | cut -c1-4 ;;
  esac
}

# Standard_D4as_v4 -> d4asv4  (used in VM names)
size_short() {
  echo "$1" | sed 's/Standard_//' | tr '[:upper:]' '[:lower:]'
}

# Deterministic VM name: bench-<region>-<size>-<index>
vm_name() {
  local region="$1" size="$2" idx="$3"
  echo "bench-$(region_abbr "$region")-$(size_short "$size")-${idx}"
}

# vCPU / RAM lookup for the CSV metadata columns (all sizes in this study
# are 1:4 vCPU:RAM ratio, but keep this explicit rather than computed)
vm_specs() {
  case "$1" in
    Standard_D2s_v3|Standard_D2as_v4|Standard_D2s_v5|Standard_D2as_v5|Standard_D2ds_v4)
      echo "2 8" ;;
    Standard_D4s_v3|Standard_D4as_v4|Standard_D4s_v5|Standard_D4as_v5|Standard_D4ds_v4)
      echo "4 16" ;;
    *) echo "0 0" ;;
  esac
}

max_node_count() {
  local max=0
  for n in "${NODE_COUNTS[@]}"; do
    if [ "$n" -gt "$max" ]; then max=$n; fi
  done
  echo "$max"
}

# Returns "yes" if node_count VMs of this size fit under the region's total
# vCPU cap, "no" otherwise. Prevents submitting combos that will just fail.
fits_quota() {
  local region="$1" size="$2" nodes="$3"
  read -r vcpu ram <<< "$(vm_specs "$size")"
  local needed=$((vcpu * nodes))
  local cap="${REGION_VCPU_CAP[$region]}"
  if [ "$needed" -gt "$cap" ]; then
    echo "no"
  else
    echo "yes"
  fi
}

# Polls a VM over SSH until /opt/benchmark/INSTALL_DONE exists (cloud-init finished).
wait_for_install() {
  local ip="$1"
  local tries=0
  while [ "$tries" -lt "$INSTALL_POLL_MAX_TRIES" ]; do
    if sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        "$ADMIN_USERNAME@$ip" "test -f /opt/benchmark/INSTALL_DONE" 2>/dev/null; then
      echo "  install finished on $ip"
      return 0
    fi
    tries=$((tries + 1))
    echo "  waiting for install on $ip (${tries}/${INSTALL_POLL_MAX_TRIES})..."
    sleep "$INSTALL_POLL_INTERVAL"
  done

  echo "  install marker was not found on $ip"
  echo "  last cloud-init status/log lines from $ip:"
  sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
      "$ADMIN_USERNAME@$ip" \
      "cloud-init status --long || true; sudo tail -80 /var/log/cloud-init-output.log || true" || true
  return 1
}

# Maps a VM's public IP to its private IP within the VNet. Spark's inter-node
# traffic (port 7077 + block manager/executor ports) must use private IPs -
# the auto-created NSGs only allow inbound port 22 from the internet, but
# AllowVnetInBound (default rule) permits all traffic between private IPs.
private_ip_for() {
  local public_ip="$1"
  az vm list-ip-addresses -g "$RESOURCE_GROUP" \
    --query "[?virtualMachine.network.publicIpAddresses[0].ipAddress=='${public_ip}'].virtualMachine.network.privateIpAddresses[0]" \
    -o tsv
}

# Kills any leftover run_benchmark.py (and its spawned spark-submit/JVM
# children) from a prior invocation on this VM. Needed before reusing a VM -
# an old process left running (e.g. from an interrupted local session) will
# silently steal cores from the new run's Spark cluster and cause every job
# to fail/hang on registration, with no obvious error pointing at the cause.
kill_stale_benchmark_processes() {
  local ip="$1"
  # The [x] trick avoids pkill -f matching its own invoking shell: the
  # remote command line literally contains the search pattern, so a plain
  # 'run_benchmark.py' pattern matches itself and kills the SSH session
  # before it finishes (silently, as a 255 SSH-level failure).
  sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    "$ADMIN_USERNAME@$ip" \
    "pkill -9 -f '[r]un_benchmark.py' 2>/dev/null; pkill -9 -f 'org.apache.spark.deploy.[S]parkSubmit' 2>/dev/null; true"
}

# Ensures the benchmark user can write datasets, outputs, logs, and results.
repair_benchmark_permissions() {
  local ip="$1"
  sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10       "$ADMIN_USERNAME@$ip"       "sudo mkdir -p /opt/benchmark/datasets /opt/benchmark/output /opt/benchmark/results /opt/benchmark/spark_jobs && sudo chown -R $ADMIN_USERNAME:$ADMIN_USERNAME /opt/benchmark && sudo chmod -R u+rwX /opt/benchmark"
}
