#!/usr/bin/env bash
# Resume a single benchmark combo using VMs that were already created and kept.
# Usage:
#   ./resume_existing_combo.sh <region> <vm_size> <nodes> <master_ip> [worker_ip...]
#   DATASET_SIZES=1024,5120 ./resume_existing_combo.sh ...   # override sizes (default: config.env's DATASET_SIZES_MB)
set -euo pipefail

source ./common.sh

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <region> <vm_size> <nodes> <master_ip> [worker_ip...]"
  echo "Example: $0 centralindia Standard_D2s_v3 2 20.198.72.239 4.224.34.228"
  exit 2
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "ERROR: sshpass is not installed locally or is not in PATH."
  exit 1
fi

region="$1"
size="$2"
nodes="$3"
shift 3
VM_IPS=("$@")

if [ "${#VM_IPS[@]}" -ne "$nodes" ]; then
  echo "ERROR: expected $nodes IPs, got ${#VM_IPS[@]}"
  exit 1
fi

read -r vcpu ram <<< "$(vm_specs "$size")"
master_ip="${VM_IPS[0]}"
worker_ips=("${VM_IPS[@]:1}")
ssh_base=(sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
scp_base=(sshpass -p "$ADMIN_PASSWORD" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

echo "Killing any stale benchmark processes from a prior run on these VMs..."
for ip in "${VM_IPS[@]}"; do
  kill_stale_benchmark_processes "$ip"
done

echo "Checking install markers on existing VMs..."
for ip in "${VM_IPS[@]}"; do
  wait_for_install "$ip"
done

echo "Repairing /opt/benchmark permissions on existing VMs..."
for ip in "${VM_IPS[@]}"; do
  repair_benchmark_permissions "$ip"
done

master_private_ip=$(private_ip_for "$master_ip")

echo "Starting Spark master on $master_ip..."
"${ssh_base[@]}" "$ADMIN_USERNAME@$master_ip"   "source /etc/profile.d/spark.sh && \$SPARK_HOME/sbin/stop-master.sh >/dev/null 2>&1 || true; source /etc/profile.d/spark.sh && \$SPARK_HOME/sbin/start-master.sh"

for wip in "${worker_ips[@]}"; do
  echo "Starting Spark worker on $wip..."
  "${ssh_base[@]}" "$ADMIN_USERNAME@$wip"     "source /etc/profile.d/spark.sh && \$SPARK_HOME/sbin/stop-worker.sh >/dev/null 2>&1 || true; source /etc/profile.d/spark.sh && \$SPARK_HOME/sbin/start-worker.sh spark://${master_private_ip}:7077"
done

echo "Cluster up: spark://${master_private_ip}:7077 ($nodes nodes)"

"${scp_base[@]}" run_benchmark.py "$ADMIN_USERNAME@$master_ip:/tmp/run_benchmark.py"
"${ssh_base[@]}" "$ADMIN_USERNAME@$master_ip"   "sudo mkdir -p /opt/benchmark && sudo mv /tmp/run_benchmark.py /opt/benchmark/run_benchmark.py && sudo chown $ADMIN_USERNAME:$ADMIN_USERNAME /opt/benchmark/run_benchmark.py"

worker_ips_csv=$(IFS=,; echo "${worker_ips[*]}")
dataset_sizes_csv="${DATASET_SIZES:-$(IFS=,; echo "${DATASET_SIZES_MB[*]}")}"
workloads_csv=$(IFS=,; echo "${WORKLOAD_TYPES[*]}")

remote_cmd="python3 /opt/benchmark/run_benchmark.py   --region $region --vm-size $size --vcpu $vcpu --ram-gb $ram --nodes $nodes   --master-url spark://${master_private_ip}:7077 --worker-ips "$worker_ips_csv"   --admin-username $ADMIN_USERNAME --admin-password '$ADMIN_PASSWORD'   --storage-account $STORAGE_ACCOUNT_NAME --storage-key '$STORAGE_ACCOUNT_KEY'   --dataset-container $DATASET_CONTAINER_NAME --results-container $RESULTS_CONTAINER_NAME   --dataset-sizes $dataset_sizes_csv --workloads $workloads_csv   --repetitions $REPETITIONS"

"${ssh_base[@]}" "$ADMIN_USERNAME@$master_ip" "$remote_cmd"
