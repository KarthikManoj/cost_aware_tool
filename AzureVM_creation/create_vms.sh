#!/usr/bin/env bash
# Creates N VMs for a (region, size, nodes) combo and waits for cloud-init to
# finish, without running the benchmark. Prints the resulting IPs ready to
# feed straight into resume_existing_combo.sh. Safe to run in parallel with
# an active combo in a different region/resource - az calls don't conflict
# across independent VMs.
# Usage:
#   ./create_vms.sh <region> <vm_size> <nodes>
set -euo pipefail

source ./common.sh

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <region> <vm_size> <nodes>"
  echo "Example: $0 southeastasia Standard_D2s_v3 2"
  exit 2
fi

region="$1"
size="$2"
nodes="$3"

if ! command -v sshpass >/dev/null 2>&1; then
  echo "ERROR: sshpass is not installed locally or is not in PATH."
  exit 1
fi

read -r vcpu ram <<< "$(vm_specs "$size")"
if [ "$(fits_quota "$region" "$size" "$nodes")" == "no" ]; then
  needed=$((vcpu * nodes))
  cap="${REGION_VCPU_CAP[$region]:-unknown}"
  echo "ERROR: needs ${needed} vCPUs, region cap for $region is ${cap}. Pick a smaller size/node count."
  exit 1
fi

if [ ! -f cloud-init-final.yaml ]; then
  echo "ERROR: cloud-init-final.yaml not found. Run ./run_sequential_matrix.sh once (it regenerates this file) or build it manually first."
  exit 1
fi

# A resource group's --location is just where its own metadata lives - it
# does not restrict which region VMs inside it deploy to. Re-creating an
# existing group with a different location fails, so only create it if it
# doesn't exist yet (first region wins the group's nominal location).
if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az group create --name "$RESOURCE_GROUP" --location "$region" --output none
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

echo ""
echo "Waiting for cloud-init install to finish on all VMs (this is the slow part)..."
install_ok=true
for ip in "${VM_IPS[@]}"; do
  if ! wait_for_install "$ip"; then
    echo "ERROR: install did not finish on $ip within timeout"
    install_ok=false
  fi
done

if [ "$install_ok" != "true" ]; then
  echo "One or more VMs failed to install. Left running for inspection - delete with ./delete_all_vms.sh when done."
  exit 1
fi

echo ""
echo "All VMs ready. IPs (master first, then workers):"
echo "${VM_IPS[@]}"
echo ""
echo "Next:"
echo "  ./resume_existing_combo.sh $region $size $nodes ${VM_IPS[*]}"
