#!/usr/bin/env bash
# Run only the 2048MB and 3072MB AWS EMR experiments for every candidate
# instance type at both 2-node and 4-node cluster sizes, in both AWS regions.
set -euo pipefail

cd "$(dirname "$0")/.."

COMMON_ARGS=(
  --dataset-sizes-mb 2048,3072
  --workloads cpu-heavy,memory-heavy,io-heavy
  --instance-types m5.xlarge,m5a.xlarge,m6i.xlarge,c5.xlarge,c5a.xlarge,c6i.xlarge
  --nodes-list 2,4
  --pricing-model on-demand
  --price-path cloud_prices/aws_prices.csv
  --output data/performance/performance_dataset.csv
  --failed-output data/performance/failed_emr_experiments.csv
  --step-timeout-minutes 90
  --submit
)

echo "Running 2048/3072 EMR matrix in ap-south-1..."
python3 scripts/run_emr_regional_resumable_batch.py   --region ap-south-1   --ec2-key-name ""   "${COMMON_ARGS[@]}"

echo "Running 2048/3072 EMR matrix in ap-southeast-1..."
echo "Using ap-southeast-1 subnet subnet-0e24ae0acdd26d075."
python3 scripts/run_emr_regional_resumable_batch.py   --region ap-southeast-1   --subnet-id ""   --ec2-key-name cost-aware-emr-key   "${COMMON_ARGS[@]}"
