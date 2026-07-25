#!/usr/bin/env bash
# SAFETY NET ONLY: run_sequential_matrix.sh already deletes each combo's VMs
# (and, via delete_vm_full, their NIC/public-IP/OS-disk) as it goes. Use this
# if a run was interrupted (Ctrl-C, laptop slept, etc.) and left VMs running,
# or as a final wipe once you're fully done. Does NOT touch the resource
# group itself, the storage account, or anything else that isn't a VM/NIC/
# public-IP/disk - those are preserved intentionally for future runs.
# Set AUTO_CONFIRM=1 to skip the interactive prompt (unattended/autonomous use).
set -e
source ./common.sh
source ./combo_runner.sh

echo "VMs currently in $RESOURCE_GROUP:"
az vm list --resource-group "$RESOURCE_GROUP" --output table

if [ "${AUTO_CONFIRM:-0}" != "1" ]; then
  read -p "Delete ALL of the above (and their NICs/public IPs/OS disks)? (y/n) " CONFIRM
  if [ "$CONFIRM" != "y" ]; then echo "Aborted."; exit 0; fi
fi

for name in $(az vm list --resource-group "$RESOURCE_GROUP" --query "[].name" -o tsv); do
  echo "Deleting $name and its NIC/public-IP/OS-disk..."
  delete_vm_full "$name" &
done
wait

# Defense in depth: sweep any NIC/public-IP/disk left over with no VM at
# all (e.g. from a create that failed before the VM resource ever existed,
# or the create/wait failure path in an old version of this script).
echo ""
echo "Sweeping orphaned NICs/public IPs/disks with no attached VM..."
for id in $(az network nic list --resource-group "$RESOURCE_GROUP" --query "[?virtualMachine==null].id" -o tsv); do
  az network nic delete --ids "$id" --output none &
done
wait
for id in $(az network public-ip list --resource-group "$RESOURCE_GROUP" --query "[?ipConfiguration==null].id" -o tsv); do
  az network public-ip delete --ids "$id" --output none &
done
wait
for id in $(az disk list --resource-group "$RESOURCE_GROUP" --query "[?diskState=='Unattached'].id" -o tsv); do
  az disk delete --ids "$id" --yes --output none &
done
wait

echo ""
echo "All ephemeral VM/NIC/public-IP/disk resources deleted."
echo "Preserved (not touched): resource group '$RESOURCE_GROUP', storage account, and anything else."
