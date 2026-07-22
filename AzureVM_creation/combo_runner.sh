#!/bin/bash
# Shared per-combo logic: create VMs for one (region, size, nodes) combo,
# wait for install, form the Spark cluster, run the benchmark, delete VMs.
# Sourced by both run_sequential_matrix.sh (full run) and retry_failed.sh.
#
# Writes one line to $SUMMARY_FILE per combo: region,vm_size,nodes,status,note
#
# run_combo <region> <size> <nodes> [retry_list_csv]
#   retry_list_csv (optional): path to a CSV with columns
#   Dataset_Size_MB,Workload,Run_Number - if given, only those specific
#   runs are executed instead of the full dataset x workload x repetition set.

run_combo() {
  local region="$1" size="$2" nodes="$3" retry_list="${4:-}"
  read -r vcpu ram <<< "$(vm_specs "$size")"

  echo ""
  echo "############################################################"
  echo "# $region | $size | $nodes nodes $([ -n "$retry_list" ] && echo "(RETRY: $retry_list)")"
  echo "############################################################"

  if ! command -v sshpass >/dev/null 2>&1; then
    echo "ERROR: sshpass is not installed locally or is not in PATH. Install it before creating VMs."
    echo "$region,$size,$nodes,FAILED,missing local sshpass" >> "$SUMMARY_FILE"
    return
  fi

  if [ "$(fits_quota "$region" "$size" "$nodes")" == "no" ]; then
    local needed=$((vcpu * nodes))
    local family
    family="$(vm_family "$size")"
    local cap="${REGION_FAMILY_VCPU_CAP[${region}:${family}]:-0}"
    echo "SKIP: needs ${needed} vCPUs, ${family} family cap in ${region} is ${cap}."
    echo "$region,$size,$nodes,SKIPPED,needs ${needed} vCPU > ${family} cap ${cap}" >> "$SUMMARY_FILE"
    return
  fi

  VM_NAMES=()
  VM_IPS=()
  for idx in $(seq 1 "$nodes"); do
    name="bench-$(region_abbr "$region")-$(size_short "$size")-n${nodes}-${idx}"
    VM_NAMES+=("$name")
    echo "Creating $name..."
    az vm create \
      --resource-group "$RESOURCE_GROUP" \
      --name "$name" \
      --image "Ubuntu2204" \
      --size "$size" \
      --location "$region" \
      --admin-username "$ADMIN_USERNAME" \
      --admin-password "$ADMIN_PASSWORD" \
      --authentication-type password \
      --custom-data cloud-init-final.yaml \
      --public-ip-sku Standard \
      --no-wait \
      --output none
  done

  for name in "${VM_NAMES[@]}"; do
    echo "Waiting for $name to finish provisioning..."
    az vm wait --resource-group "$RESOURCE_GROUP" --name "$name" --created --output none
    ip=$(az vm show -d -g "$RESOURCE_GROUP" -n "$name" --query publicIps -o tsv)
    VM_IPS+=("$ip")
    echo "  $name -> $ip"
  done

  local install_ok=true
  for ip in "${VM_IPS[@]}"; do
    if ! wait_for_install "$ip"; then
      echo "ERROR: install did not finish on $ip within timeout"
      install_ok=false
    fi
  done

  if [ "$install_ok" != "true" ]; then
    echo "$region,$size,$nodes,FAILED,install timeout" >> "$SUMMARY_FILE"

    if [ "${KEEP_FAILED_VMS:-1}" = "1" ]; then
      echo "Install failed. Keeping partially-broken VMs for debugging."
      echo "VMs kept: ${VM_NAMES[*]}"
      echo "VM IPs: ${VM_IPS[*]}"
      echo "After you inspect them, run ./delete_all_vms.sh or rerun with KEEP_FAILED_VMS=0 to auto-delete."
      return
    fi

    echo "Deleting partially-broken VMs..."
    for name in "${VM_NAMES[@]}"; do
      az vm delete --resource-group "$RESOURCE_GROUP" --name "$name" --yes --output none &
    done
    wait
    return
  fi

  echo "Repairing /opt/benchmark permissions on all VMs..."
  for ip in "${VM_IPS[@]}"; do
    repair_benchmark_permissions "$ip"
  done

  local master_ip="${VM_IPS[0]}"
  local worker_ips=("${VM_IPS[@]:1}")
  local ssh_prefix="sshpass -p $ADMIN_PASSWORD ssh -o StrictHostKeyChecking=no $ADMIN_USERNAME@"

  local master_private_ip
  master_private_ip=$(private_ip_for "$master_ip")

  ${ssh_prefix}${master_ip} "source /etc/profile.d/spark.sh && \$SPARK_HOME/sbin/start-master.sh"
  for wip in "${worker_ips[@]}"; do
    ${ssh_prefix}${wip} "source /etc/profile.d/spark.sh && \$SPARK_HOME/sbin/start-worker.sh spark://${master_private_ip}:7077"
  done
  echo "Cluster up: spark://${master_private_ip}:7077 ($nodes nodes)"

  local worker_ips_csv
  worker_ips_csv=$(IFS=,; echo "${worker_ips[*]}")

  sshpass -p "$ADMIN_PASSWORD" scp -o StrictHostKeyChecking=no \
    run_benchmark.py "$ADMIN_USERNAME@$master_ip:/tmp/run_benchmark.py"
  sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no "$ADMIN_USERNAME@$master_ip" \
    "sudo mkdir -p /opt/benchmark && sudo mv /tmp/run_benchmark.py /opt/benchmark/run_benchmark.py && sudo chown $ADMIN_USERNAME:$ADMIN_USERNAME /opt/benchmark/run_benchmark.py"

  local retry_arg=""
  if [ -n "$retry_list" ]; then
    sshpass -p "$ADMIN_PASSWORD" scp -o StrictHostKeyChecking=no \
      "$retry_list" "$ADMIN_USERNAME@$master_ip:/tmp/retry_list.csv"
    sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no "$ADMIN_USERNAME@$master_ip" \
      "sudo mkdir -p /opt/benchmark && sudo mv /tmp/retry_list.csv /opt/benchmark/retry_list.csv && sudo chown $ADMIN_USERNAME:$ADMIN_USERNAME /opt/benchmark/retry_list.csv"
    retry_arg="--retry-list /opt/benchmark/retry_list.csv"
  fi

  local dataset_sizes_csv workloads_csv
  dataset_sizes_csv=$(IFS=,; echo "${DATASET_SIZES_MB[*]}")
  workloads_csv=$(IFS=,; echo "${WORKLOAD_TYPES[*]}")

  local remote_cmd="python3 /opt/benchmark/run_benchmark.py \
    --region $region --vm-size $size --vcpu $vcpu --ram-gb $ram --nodes $nodes \
    --master-url spark://${master_private_ip}:7077 --worker-ips \"$worker_ips_csv\" \
    --admin-username $ADMIN_USERNAME --admin-password '$ADMIN_PASSWORD' \
    --storage-account $STORAGE_ACCOUNT_NAME --storage-key '$STORAGE_ACCOUNT_KEY' \
    --dataset-container $DATASET_CONTAINER_NAME --results-container $RESULTS_CONTAINER_NAME \
    --dataset-sizes $dataset_sizes_csv --workloads $workloads_csv \
    --repetitions $REPETITIONS $retry_arg"

  if sshpass -p "$ADMIN_PASSWORD" ssh -o StrictHostKeyChecking=no "$ADMIN_USERNAME@$master_ip" "$remote_cmd"; then
    echo "$region,$size,$nodes,SUCCESS," >> "$SUMMARY_FILE"
  else
    echo "$region,$size,$nodes,FAILED,benchmark run error" >> "$SUMMARY_FILE"
  fi

  echo "Deleting VMs for this combo..."
  for name in "${VM_NAMES[@]}"; do
    az vm delete --resource-group "$RESOURCE_GROUP" --name "$name" --yes --output none &
  done
  wait
  echo "Combo done: $region / $size / $nodes nodes"
}
