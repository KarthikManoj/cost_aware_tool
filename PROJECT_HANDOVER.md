# Project Handover — Technical Summary for Report Writing

> Everything below was verified by reading the actual source and data files in the repository,
> not reconstructed from notes. File and line references are given so any claim can be checked.
>
> **Read the "Accuracy warnings" section before writing anything.** Three things in this project are
> commonly described inaccurately, and repeating those descriptions in a dissertation would be a
> factual error in the submitted work.

---

## 1. What the project is

A **cost-, SLA- and carbon-aware cluster configuration recommender for Apache Spark**, spanning
AWS EMR and Azure IaaS.

**Input:** dataset size (MB), workload type (`cpu-heavy` / `memory-heavy` / `io-heavy`), an SLA
deadline in minutes, and an optimisation goal (`cost` / `runtime` / `carbon` / `balanced`).

**Output:** a ranked table of candidate infrastructure configurations — cloud, region, machine type,
node count — each with predicted runtime, predicted cost, carbon intensity, renewable percentage,
an optimisation score, and a human-readable reason for the ranking.

**Domain:** cloud infrastructure optimisation for distributed data processing. Positioned against
CherryPick, Ernest, Micky, PARIS, OtterTune and Arrow.

---

## 2. What was actually built — component inventory

| Component | Location | What it does |
|---|---|---|
| Synthetic data generator | `dataset_generator/generate_dataset.py` | Produces CSV/Parquet Spark input at a target size |
| Benchmark workloads | `spark_jobs/{cpu_heavy,memory_heavy,io_heavy}.py` + `common.py` | Three PySpark jobs stressing different resource dimensions |
| AWS EMR harness | `aws/emr_runner.py`, `aws/upload_to_s3.py`, `scripts/run_emr_*.py` | Provisions EMR clusters, submits Spark steps, resumable batch execution |
| Azure IaaS harness | `AzureVM_creation/*.sh`, `cloud-init-template.yaml`, `run_benchmark.py` | Provisions Ubuntu 22.04 VMs via cloud-init, runs standalone Spark, collects results |
| Price collection | `cloud_prices/fetch_cloud_prices.py` | AWS + Azure on-demand hourly pricing, scoped to target regions |
| Carbon collection | `Carbon_dataset/carbon_collect.py`, `renewable_collect.py` | Daily carbon intensity + renewable % from Electricity Maps |
| Metric recording | `metrics/collect_metrics.py` | Computes cost, appends one experiment row to the performance CSV |
| Dataset merge | `ml/merge_model_dataset.py` | Joins AWS + Azure performance with carbon features |
| Preprocessing | `ml/preprocessing.py` | Feature/target definitions, one-hot + scaling pipeline |
| Training | `ml/train_model.py` | Trains and compares 4 models, grouped holdout + grouped CV |
| Recommender | `ml/recommendation_engine.py` | Scores, filters by SLA, ranks configurations |
| EDA | `ml/eda.py` | Descriptive statistics and grouped summaries |
| Dashboard | `dashboard/app.py` | Streamlit interface |
| Tests | `tests/` (5 files, pytest) | Cost calculation, carbon join, scoring/tie-breaks, schema |

**Stack:** Python 3.11, PySpark, scikit-learn, pandas, boto3, Bash 5.x, Streamlit, pytest.
Dependencies pinned in `requirements.txt` to the versions the reported results were produced with.

---

## 3. How the experiments were run — methodology

### 3.1 Benchmark design

Three workload types, chosen to span the resource space: `cpu-heavy`, `memory-heavy`, `io-heavy`.
Spark configured with `spark.sql.shuffle.partitions = 64` (`spark_jobs/common.py:16`). Input read as
CSV with header and schema inference, or Parquet.

**AWS EMR arm**
- EMR release 6.15.0, region `ap-south-1` (plus `ap-southeast-1` in the regional batch)
- Instance types: `c5.xlarge`, `c5a.xlarge`, `c6i.xlarge`, `m5.xlarge`, `m5a.xlarge`, `m6i.xlarge`
- Node counts: 2 and 4
- Dataset sizes: 10, 100, 500, 1024, 2048, 3072, 5120 MB
- S3 bucket `cost-aware-spark-research-manoj-2026`
- Batch runners are **resumable** — successes append to a performance CSV, failures to a separate
  CSV, so a killed batch does not re-bill completed runs

**Azure IaaS arm**
- Standalone Spark on plain Ubuntu 22.04 VMs, provisioned by cloud-init. **Not Databricks**
- 6 VM sizes across Dsv3, Dasv4, Ddsv4 families
- Regions: Central India, Southeast Asia
- Node counts: 2 and 4; dataset sizes 10 MB–5 GB; 2 repetitions
- Run order: `run_sequential_matrix.sh` → `collect_results.sh` → `retry_failed.sh` → `collect_results.sh`

Repeated runs of identical configurations were collected deliberately, to capture runtime variance.
This is what makes the grouped splitting in §5 necessary.

### 3.2 Why Databricks was abandoned

The Databricks path was attempted and produced only **5 usable rows**
(`data/performance/azure_databricks_performance_dataset.csv`) against **80 failures**
(`failed_azure_databricks_experiments.csv`). Rejected on cost and reliability grounds under a $100
credit account, and replaced by standalone Spark on IaaS. This is evidence for the tools-evaluation
chapter, not a gap.

### 3.3 Constraints encountered

- Azure vCPU quota: Central India capped at 32, Southeast Asia at 10
- Dsv5 / Dasv5 families had zero quota in both regions and were excluded from the matrix
- These constraints reduced the achievable matrix mid-campaign and should be reported as a
  limitation on external validity

---

## 4. The data

| Dataset | Rows | Notes |
|---|---|---|
| `data/performance/performance_dataset.csv` | **1,011** | AWS EMR |
| `data/performance/merged_azure_results_clean.csv` | **800** | Azure, SUCCESS rows only |
| **`data/models/cloud_carbon_model_dataset.csv`** | **1,811** | Merged — this is the training set |
| `data/performance/cleaned_data/cleaned_dataset.csv` | 207 | Early AWS-only campaign |
| `azure_databricks_performance_dataset.csv` | 5 | Abandoned Databricks path |
| `failed_azure_databricks_experiments.csv` | 80 | Failure log |
| `failed_emr_retry_experiments.csv` | 11 | Failure log |

1,011 + 800 = 1,811 exactly, so nothing was lost in the merge.

**Merged dataset schema** (21 columns): `cloud, region, run_date, dataset_size_mb, workload_type,
machine_type, nodes, runtime_minutes, cost_usd, cpu_avg_pct, memory_avg_pct, electricity_zone,
carbon_intensity_mean, renewable_percentage_mean, carbon_intensity_min, carbon_intensity_max,
renewable_percentage_min, renewable_percentage_max, carbon_days_available, carbon_feature_source,
estimated_emissions_gco2eq`

**Observed ranges** (from `data/eda/eda_summary.json`, computed on the earlier 207-row AWS subset —
do **not** present these as statistics of the full 1,811-row corpus): runtime 0.67–7.31 min
(mean 1.69); cost $0.0050–$0.0509 (mean $0.0173).

### 4.1 How carbon data was joined — `ml/merge_model_dataset.py`

Two paths, recorded per row in `carbon_feature_source`:

1. **`nearest_daily_reading`** — rows with a real run timestamp (Azure only) are matched to that
   region's nearest daily carbon reading using `pd.merge_asof(direction="nearest")`, keyed on
   cloud and region.
2. **`regional_mean`** — rows without a timestamp (all AWS rows; that campaign never recorded one)
   fall back to the region's all-time mean intensity and renewable percentage.

Join keys are case-normalised because the carbon files mix `"aws"` and `"Azure"` spellings
(`merge_model_dataset.py:122-123`). Both timestamp columns are pinned to `datetime64[ns, UTC]`
because `merge_asof` requires exactly matching resolution.

Region → electricity zone mapping: `ap-south-1` → `IN`, `ap-southeast-1` → `SG`
(`metrics/collect_metrics.py:32-35`).

---

## 5. How the models were trained

**Features** (9, `ml/preprocessing.py:9-19`): `cloud`, `region`, `electricity_zone`,
`dataset_size_mb`, `workload_type`, `machine_type`, `nodes`, `carbon_intensity_mean`,
`renewable_percentage_mean`.

**Targets** (2, `preprocessing.py:20`): `runtime_minutes`, `cost_usd`. Predicted jointly via
`MultiOutputRegressor`.

**Preprocessing:** `OneHotEncoder(handle_unknown="ignore")` on the 5 categorical columns,
`StandardScaler` on the 4 numeric columns, combined in a `ColumnTransformer`.

**Models compared:** linear regression, decision tree, random forest, gradient boosting.

**Grouped splitting — the key methodological choice.** The group key is the full configuration
tuple (cloud, region, dataset size, workload, machine type, nodes). `GroupShuffleSplit` for the
holdout, `GroupKFold` for cross-validation. Because the corpus deliberately contains repeated runs
of identical configurations, an ordinary random split would place near-duplicate rows on both sides
and inflate scores. Grouping prevents that leakage. Argue this explicitly — it is a genuine
methodological strength.

**Row filtering:** `train_model.py:98` drops any row missing a feature or target. The effective
training N is therefore ≤ 1,811 — **compute and report the real post-`dropna` figure** rather than
quoting 1,811 as the number trained on.

Holdout test size: 0.25 when n ≥ 12, else 0.34. CV default: 5 folds, clamped to the number of
unique groups.

---

## 6. Results

### 6.1 Grouped 5-fold cross-validation — `data/models/cross_validation_metrics.json`

The defensible headline numbers. Mean ± std across folds.

| Model | Runtime R² | Runtime MAE (min) | Cost R² | Cost MAE (USD) |
|---|---|---|---|---|
| Linear regression | 0.683 ± 0.028 | 0.575 ± 0.028 | 0.720 ± 0.020 | 0.0043 ± 0.0001 |
| Decision tree | 0.834 ± 0.067 | 0.330 ± 0.021 | 0.820 ± 0.057 | 0.0028 ± 0.0001 |
| **Random forest** | **0.893 ± 0.045** | **0.267 ± 0.025** | **0.894 ± 0.027** | **0.0024 ± 0.0003** |
| Gradient boosting | 0.885 ± 0.038 | 0.285 ± 0.021 | 0.874 ± 0.035 | 0.0025 ± 0.0003 |

**Random forest wins on every metric for both targets.** The ordering is stable and interpretable:
linear regression clearly worst, confirming the runtime/cost surface is non-linear in the features;
tree ensembles substantially better than a single tree, confirming variance reduction helps.

### 6.2 Single best-model holdout — `data/models/model_metrics.json`

| Target | MAE | RMSE | R² |
|---|---|---|---|
| `runtime_minutes` | 0.1895 min | 0.3181 | 0.9573 |
| `cost_usd` | $0.0020 | $0.0037 | 0.9200 |

**Report the cross-validated numbers as the headline, not these.** A single holdout split on this
corpus is optimistic — the gap (R² 0.957 vs 0.893 for runtime) is exactly the effect that
cross-validation exists to expose. Presenting the higher number as the primary result and burying
the lower one invites an obvious challenge at the demonstration. Lead with CV, present the holdout
as a secondary comparison, and note the gap yourself.

Relative error context: runtime MAE 0.267 min against a mean runtime of ~1.69 min is roughly 16%.

### 6.3 Other result artefacts

| File | Contents |
|---|---|
| `data/models/best_cloud_model.joblib` | Serialised winning pipeline |
| `data/models/model_comparison.json` | Holdout comparison across all four models |
| `data/models/prediction_comparison.csv` | Per-row predicted vs actual |
| `data/models/feature_importance.json` | Feature importances (tree-based winners only) |
| `data/models/recommendation_examples/top_5_{cost,runtime,carbon,balanced}_recommendations.csv` | Worked recommender output per goal |
| `data/eda/descriptive_statistics.csv`, `grouped_summary.csv` | EDA tables |

---

## 7. How recommendations are derived — `ml/recommendation_engine.py`

Five stages:

**1. Build the candidate set.** Filter the merged dataset to the requested workload type, take
distinct combinations of (cloud, region, electricity zone, machine type, nodes, carbon intensity,
renewable percentage), then substitute the user's requested `dataset_size_mb`
(`_build_candidate_frame`, lines 209–225).

> The recommender therefore only ever proposes configurations it has observed in the corpus. It
> interpolates across dataset size, but does not extrapolate to unseen hardware. State this.

**2. Predict.** Run the trained pipeline over all candidates. Predictions clipped at
`runtime ≥ 0.01` and `cost ≥ 0.0` to prevent physically meaningless negatives (lines 188–189).

**3. Apply the SLA as a hard filter.** Keep candidates where predicted runtime ≤ SLA. If none
qualify, fall back to the full set and prefix every recommendation reason with *"No configuration
satisfied the SLA"* rather than returning an empty result (lines 190–197).

**4. Score.** Each of runtime, cost, carbon intensity and renewable percentage is min-max normalised
to [0,1] across the candidate set. Renewable is inverted into a penalty (`1 − renewable_score`) so
that lower is better for every term. **Lower score = better.**

| Goal | Formula |
|---|---|
| `cost` | `cost_score` |
| `runtime` | `runtime_score` |
| `carbon` | `carbon_score + 0.25 × renewable_penalty` |
| `balanced` | `0.35 × runtime + 0.35 × cost + 0.20 × carbon + 0.10 × renewable_penalty` |

**5. Sort with explicit tie-breaks.** Each goal has its own tie-break chain — for `cost`:
score → cost → runtime → carbon → renewable. Renewable always sorts descending, everything else
ascending (lines 253–296). Output is renamed to presentation columns and ranked from 1.

Every row carries a `Recommendation Reason` string explaining why it ranked where it did.

---

## 8. How results are presented

**Streamlit dashboard** (`dashboard/app.py`) — user sets dataset size, workload type, SLA and
optimisation goal; the app ranks every configuration in the merged dataset (nothing hardcoded) and
displays the top N with supporting charts, plus buttons to retrain and cross-validate, and read-outs
of model comparison, cross-validation and feature importance.

**CLI** — `ml/recommendation_engine.py` runs standalone with `--dataset-size-mb`, `--workload-type`,
`--sla-runtime-minutes`, `--optimization-goal`, `--top-n`, and optional `--csv-output` / `--json-output`.

**Worked examples** — `ml/example_usage.py` prints top-5 recommendations for a fixed scenario under
each of the four goals; saved outputs are in `data/models/recommendation_examples/`.

**Machine-readable artefacts** — all metrics written as JSON (§6.3), suitable for direct inclusion
as report tables.

---

## 9. Accuracy warnings — read before writing

These three points matter. Each is a case where the natural description of the project does not
match what the code does, and repeating the natural description in a submitted dissertation would
be a factual misstatement.

### 9.1 It is not a Pareto front

The project is often described as producing a Pareto front of cheapest / greenest / fastest options.
**It does not.** `_calculate_score` implements **weighted-sum scalarisation over min-max normalised
objectives** — a single scalar score per candidate, then a sort.

This differs from Pareto optimality in a way that matters: weighted-sum scalarisation cannot reach
points on a non-convex region of the trade-off surface, whereas a true Pareto front enumerates all
non-dominated solutions.

**Write it as:** *a weighted-sum multi-objective scoring function with configurable optimisation
goals.* Note in limitations that a true Pareto-front formulation would be a natural extension.
This is a legitimate and common approach — it just needs its correct name.

### 9.2 The carbon model has no power draw or PUE term

The planned formula was runtime × power draw × grid intensity × PUE. The **implemented** formula
(`merge_model_dataset.py:241-243`) is:

```python
estimated_emissions_gco2eq = (runtime_minutes / 60) * carbon_intensity_mean
```

No power draw. No PUE. No node count. The instance power-draw lookup table was never built.

Consequences to state honestly:
- Emissions scale only with runtime and regional intensity
- A 2-node and a 4-node cluster of the same runtime get **identical** estimated emissions, which is
  physically wrong
- Dimensionally, gCO₂eq/kWh × hours yields gCO₂eq only if power draw is 1 kW — so the figure carries
  an implicit and unstated 1 kW assumption

**Write it as:** a *relative* carbon proxy for ranking regions, not an absolute emissions estimate.
Do not claim absolute gCO₂eq figures are physically calibrated. Completing the power/PUE model is
strong, concrete future work. Understating this would be the most serious integrity risk in the
report — the greenwashing discussion in the ethics chapter should reference it directly.

### 9.3 Cost is a deterministic function of runtime, so the two targets are not independent

From `metrics/collect_metrics.py:65-71`:

```python
cost = hourly_price(machine_type) × nodes × (runtime_minutes / 60)
```

`machine_type` and `nodes` are both model features, and `runtime_minutes` is the other target.
So `cost_usd` is exactly determined by the features plus the runtime target — it was never measured
independently.

The evidence is visible in your own results: CV runtime R² 0.893 and cost R² 0.894 are almost
identical, which is what you would expect if the second target is an affine transform of the first.

**Do not claim two independent prediction tasks.** Write it as: cost is derived analytically from
predicted runtime and the published on-demand price; it is modelled as a second target for
convenience and consistency of the output interface, and its accuracy is inherited from runtime
accuracy rather than independent. Flag in limitations that a single-target runtime model plus the
cost identity would be equivalent and simpler.

If a marker spots any of these three before you raise them, it reads as an oversight. Raised first,
each reads as methodological self-awareness — which is precisely what the "critical evaluation"
grading criterion rewards.

---

## 10. What was NOT done

Be explicit about this in the objectives-versus-achievements chapter.

- **Workload fingerprinting is not implemented.** No fingerprint code exists in the repository. The
  intended novel contribution — predicting configurations for unseen workload types from
  early-runtime resource signatures — was designed but not built.
- **Spark event logging was never enabled** on the EMR campaign, so GC time, shuffle read/write
  bytes, I/O wait and task duration variance were never captured. This is the root cause of the above.
- **Leave-one-workload-out validation was never run.** No cross-workload generalisation result exists.
- **The instance power-draw lookup table was never built** (see §9.2).
- **The Azure benchmark matrix was not completed** — quota ceilings blocked parts of it.
- **Spot pricing sensitivity analysis** was scoped but not performed.
- `cpu_avg_pct` is sparsely populated and `memory_avg_pct` is largely empty; neither is used as a
  model feature.

---

## 11. Implementation problems solved — worth a chapter section

Genuine engineering content, and the kind of material that distinguishes a strong implementation
chapter from a code walkthrough.

1. **cloud-init YAML parse failure** — an unindented Python heredoc inside a `content: |` block broke
   YAML parsing. Resolved by extracting the Python into its own `write_files` entry.
2. **PEP 668 on Ubuntu 22.04** blocked `pip3 install` in cloud-init. Resolved with
   `--break-system-packages`, plus an error trap and fast-fail polling so failures surfaced quickly
   instead of hanging the matrix.
3. **macOS bash 3.2 lacks `declare -A`** (associative arrays). Resolved by installing bash 5.x via
   Homebrew and updating shebangs across the script suite.
4. **BSD `sed` delimiter collision** — base64 storage keys containing `/` broke `s/.../.../`.
   Resolved by switching to `|` as the delimiter.
5. **Shebang/content mismatches in cloud-init** caused silent, untraceable failures; every file in
   the pipeline had to be audited.
6. **`pd.merge_asof` resolution mismatch** — pandas ≥ 2.x inferred different datetime resolutions for
   columns parsed from differently-formatted date strings, and `merge_asof` requires exact
   resolution match. Resolved by pinning both sides to `datetime64[ns, UTC]`.
7. **Mixed cloud-name spellings** across carbon files (`"aws"` vs `"Azure"`) broke joins. Resolved
   with case-normalised join keys.
8. **Azure quota ceilings** forced mid-campaign reduction of the benchmark matrix.
9. **Databricks unreliability** under a constrained credit account forced the pivot to standalone
   Spark on IaaS (§3.2).

---

## 12. Testing

`pytest`, 5 test files:

| File | Covers |
|---|---|
| `tests/test_collect_metrics.py` | Cost calculation from price table |
| `tests/test_preprocessing.py` | Feature/target schema integrity |
| `tests/test_recommendation_engine.py` | Scoring, SLA filtering, tie-break rules |
| `tests/test_merge_model_dataset.py` | Carbon nearest-date join and regional-mean fallback |
| `tests/conftest.py` | Shared fixtures |

---

## 13. Reproduction pipeline

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python dataset_generator/generate_dataset.py --output data/synthetic/events.csv --target-size-mb 500
python scripts/run_emr_regional_resumable_batch.py          # dry-run; --submit creates billable clusters
python ml/merge_model_dataset.py                            # → cloud_carbon_model_dataset.csv
python ml/train_model.py                                    # → best model + comparison + importances
python ml/train_model.py --cross-validate                   # → cross_validation_metrics.json
python ml/example_usage.py                                  # → worked recommendations
streamlit run dashboard/app.py
pytest
```

Batch runners default to **dry-run**; `--submit` is required to create billable infrastructure.

---

## 14. Security and data handling

- All credentials via environment variables — none hardcoded. `ELECTRICITYMAPS_API_KEY`,
  `DATABRICKS_HOST` / `DATABRICKS_TOKEN`, AWS credentials via standard boto3 mechanisms
- No personal data processed anywhere in the project; all Spark input is synthetic
- Third-party data: Electricity Maps (carbon/renewable), Boavizta and Cloud Carbon Footprint
  (referenced for power figures, though not ultimately used — see §9.2). Licensing for
  redistribution must be checked before including raw data in appendices

---

## 15. Known limitations — for the limitations section

1. Sample sizes are close but unequal: 1,011 AWS vs 800 Azure. Cross-provider comparisons should be
   caveated rather than presented as balanced
2. AWS rows carry no timestamp, so their carbon features are regional all-time means while Azure
   rows get date-matched readings — an asymmetry in feature quality between the two arms
3. Carbon and renewable data is a static snapshot, not live
4. The carbon model omits power draw, PUE and node count (§9.2)
5. Cost is not independently measured — it is derived from runtime (§9.3)
6. Ranking is weighted-sum, not true Pareto (§9.1)
7. Only 3 workload types, all synthetic
8. Runs are small-scale: mean runtime ~1.69 min, max 7.31 min, datasets ≤ 5 GB, clusters of 2–4
   nodes. The contribution is methodological and scale-independent in principle, but was not
   validated at production scale
9. Instance coverage was constrained by Azure vCPU quotas; Dsv5/Dasv5 excluded entirely
10. The recommender cannot propose configurations absent from the training corpus
11. `carbon_intensity_mean` and `renewable_percentage_mean` are used as features to predict runtime,
    despite having no causal effect on it — they function as regional proxies. Check
    `feature_importance.json`: if they rank low the point is minor; if high, it needs discussion

---

## 16. Numbers to quote

| Quantity | Value |
|---|---|
| Total benchmark runs (merged) | **1,811** |
| AWS EMR runs | 1,011 |
| Azure runs | 800 |
| Rows trained on | ≤1,811 — **compute the post-`dropna` figure** |
| Models compared | 4 |
| Best model | Random forest |
| Runtime R² (grouped 5-fold CV) | **0.893 ± 0.045** |
| Cost R² (grouped 5-fold CV) | **0.894 ± 0.027** |
| Runtime MAE (CV) | 0.267 ± 0.025 min |
| Cost MAE (CV) | $0.0024 ± 0.0003 |
| Runtime R² (single holdout) | 0.957 |
| Cost R² (single holdout) | 0.920 |
| Features | 9 |
| Targets | 2 (but see §9.3) |
| Workload types | 3 |
| Clouds / regions | 2 / 4 |
| Instance types (AWS) | 6 |
| VM families (Azure) | Dsv3, Dasv4, Ddsv4 |
| Node counts | 2, 4 |
| Dataset sizes | 10 MB – 5 GB |
| Test files | 5 |
