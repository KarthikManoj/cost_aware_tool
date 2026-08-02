# Cost-Aware and Carbon-Aware Infrastructure Optimization

MSc dissertation project. Benchmarks Apache Spark workloads on AWS EMR and
Azure Databricks, trains ML models to predict runtime and cost for any
cloud configuration, and ranks candidate infrastructure by cost, runtime,
carbon intensity, or a balanced trade-off between all four factors — subject
to a user-specified SLA.

## Project layout

```
dataset_generator/   synthetic Spark input data (CSV/Parquet)
spark_jobs/           the three benchmark workloads (cpu/memory/io-heavy)
aws/                  EMR cluster + step submission (dry-run by default)
scripts/               batch experiment runners (EMR, Azure Databricks), cleaning, packaging
metrics/               appends one experiment result to the performance CSV
Carbon_dataset/        daily carbon intensity + renewable percentage by cloud/region
ml/                     preprocessing, training, cross-validation, recommendation engine
dashboard/              Streamlit app
tests/                  pytest unit tests
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # only needed to run tests
```

`requirements.txt` is pinned to the exact versions the reported results were
produced with. If you upgrade a dependency, re-run the pipeline below and
diff `data/models/model_comparison.json` before trusting new numbers —
scikit-learn especially changes model defaults across major versions.

## Pipeline (run in this order)

1. **Generate synthetic Spark input data** (optional — only needed if you
   want to re-run the Spark workloads yourself):
   `python dataset_generator/generate_dataset.py --output data/synthetic/events.csv --target-size-mb 500`

2. **Run the benchmark workloads.** Locally with `spark-submit spark_jobs/cpu_heavy.py --input <path> --output <path>`,
   or as a batch against real infrastructure:
   - AWS EMR: `scripts/run_emr_regional_resumable_batch.py` (dry-run by default; pass `--submit` to create billable clusters)
   - Azure Databricks: `scripts/run_azure_databricks_batch.py` (needs `DATABRICKS_HOST` / `DATABRICKS_TOKEN`; dry-run by default)

   Both batch runners append successes to a performance CSV and failures to
   a separate CSV via `metrics/collect_metrics.py`, so a batch can be killed
   and resumed without re-billing completed runs.

3. **Merge performance + carbon data:**
   `python ml/merge_model_dataset.py`
   Produces `data/models/cloud_carbon_model_dataset.csv`. Rows with a real
   run timestamp (Azure) are matched to that day's actual regional carbon
   reading; rows without one (AWS, which this dataset never timestamps) fall
   back to the region's all-time mean. Each row's `carbon_feature_source`
   column records which path it took.

4. **Train and compare models:**
   `python ml/train_model.py`
   Trains linear regression, decision tree, random forest, and gradient
   boosting, picks the best by average R²/RMSE on a held-out split, and
   saves `best_cloud_model.joblib`, `model_comparison.json`,
   `prediction_comparison.csv`, and `feature_importance.json` (for
   tree-based winners) under `data/models/`.

   For a more defensible metric than a single holdout split, also run:
   `python ml/train_model.py --cross-validate`
   which grouped-5-fold cross-validates all four models and saves
   `cross_validation_metrics.json` with mean ± std per metric.

   Both the holdout split and cross-validation folds are **grouped by
   configuration** (cloud, region, size, workload, machine type, nodes) so
   that repeated benchmark runs of the same setup — which this dataset
   deliberately contains, to capture runtime variance — never land in both
   the train and test side of a split.

5. **Explore recommendations:**
   `python ml/example_usage.py` prints top-5 recommendations for a fixed
   scenario under each optimization goal, or use the dashboard.

## Dashboard

```bash
streamlit run dashboard/app.py
```

Set dataset size, workload type, SLA, and optimization goal
(cost / runtime / carbon / balanced); the app ranks every AWS/Azure
configuration in the merged dataset — nothing is hardcoded — and shows the
top N with supporting charts, plus buttons to retrain and cross-validate,
and read-outs of model comparison, cross-validation, and feature
importance results.

## Tests

```bash
pytest
```

Covers cost calculation, the carbon nearest-date/fallback join logic, the
recommendation engine's scoring and tie-break rules, and the
feature/target schema.

## Known limitations

- **AWS/Azure sample size is close but not equal** (~1,011 AWS rows vs. ~800
  Azure rows after cleaning), which is unlikely to be the sole driver of
  "Azure ranks higher" results but is worth stating as a limitation rather
  than treating the comparison as perfectly balanced.
- **AWS runs have no timestamp**, so their carbon/renewable features are
  always the region's all-time mean rather than a date-matched reading;
  only Azure rows benefit from the nearest-daily-reading join.
- **Carbon/renewable data is a static snapshot** (`Carbon_dataset/*.csv`),
  not live. Refresh it with:
  `ELECTRICITYMAPS_API_KEY=... python Carbon_dataset/carbon_collect.py`
  and `ELECTRICITYMAPS_API_KEY=... python Carbon_dataset/renewable_collect.py`
  before drawing conclusions that depend on current grid conditions.

## Secrets

Set credentials as environment variables — never hardcode them in source:

- `ELECTRICITYMAPS_API_KEY` for `Carbon_dataset/carbon_collect.py` and `renewable_collect.py`
- `DATABRICKS_HOST` / `DATABRICKS_TOKEN` for `scripts/run_azure_databricks_batch.py`
- AWS credentials via the standard boto3 mechanisms (`~/.aws/credentials`, env vars, or an instance role) for `aws/emr_runner.py` and the EMR batch scripts
