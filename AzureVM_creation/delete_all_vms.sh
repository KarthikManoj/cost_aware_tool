#!/bin/bash
# SAFETY NET ONLY: run_sequential_matrix.sh already deletes each combo's VMs
# as it goes. Use this if a run was interrupted (Ctrl-C, laptop slept, etc.)
# and left VMs running, or as a final wipe once you're fully done.
set -e
source ./common.sh

echo "VMs currently in $RESOURCE_GROUP:"
az vm list --resource-group "$RESOURCE_GROUP" --output table

read -p "Delete ALL of the above? (y/n) " CONFIRM
if [ "$CONFIRM" != "y" ]; then echo "Aborted."; exit 0; fi

for name in $(az vm list --resource-group "$RESOURCE_GROUP" --query "[].name" -o tsv); do
  echo "Deleting $name..."
  az vm delete --resource-group "$RESOURCE_GROUP" --name "$name" --yes --output none &
done
wait

echo ""
echo "VMs deleted. Disks/NICs/public IPs may still linger and cost a small"
echo "amount - the guaranteed way to zero out cost is deleting the whole group:"
echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
