#!/usr/bin/env bash
# Regenerate every quantitative result needed for the evaluation chapter.
#
#   bash scripts/run_evaluation.sh
#
# Run from the repository root with the virtualenv active.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -d .venv && -z "${VIRTUAL_ENV:-}" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

mkdir -p data/results

echo "=============================================="
echo "1/6  Rebuilding merged performance+carbon dataset"
echo "=============================================="
python ml/merge_model_dataset.py

echo
echo "=============================================="
echo "2/6  Exploratory data analysis"
echo "=============================================="
python ml/eda.py

echo
echo "=============================================="
echo "3/6  Model comparison, predictions, importances"
echo "=============================================="
python ml/train_model.py | tee data/models/model_comparison.txt

echo
echo "=============================================="
echo "4/6  Grouped k-fold cross-validation"
echo "=============================================="
python ml/train_model.py --cross-validate --cv-folds 5

echo
echo "=============================================="
echo "5/6  Recommendation quality and baselines"
echo "=============================================="
python ml/evaluate_recommendations.py --all-models | tee data/results/recommendation_quality.txt

echo
echo "=============================================="
echo "6/6  Carbon, Pareto front and significance tests"
echo "=============================================="
python ml/carbon_analysis.py | tee data/results/carbon_analysis.txt
python ml/statistical_tests.py | tee data/results/statistical_tests.txt

echo
echo "=============================================="
echo "Worked recommendation examples"
echo "=============================================="
for workload in cpu-heavy memory-heavy io-heavy; do
  for goal in cost runtime carbon balanced; do
    python ml/recommendation_engine.py \
      --dataset-size-mb 1024 \
      --workload-type "$workload" \
      --sla-runtime-minutes 5 \
      --optimization-goal "$goal" \
      --top-n 5 \
      --csv-output "data/results/example_${workload}_1024mb_${goal}.csv" \
      > /dev/null
  done
done
echo "Wrote 12 worked examples to data/results/"

echo
echo "Done. Everything is under data/models/ and data/results/."
