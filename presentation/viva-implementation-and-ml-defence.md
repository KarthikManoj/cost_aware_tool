# Viva defence — implementation, ML choices, generalisability, loopholes

Companion to `VIVA_PREPARATION.md` and `viva-research-level-questions.md`.
This one is built for the pattern your friends described: the first reader probes
**what you actually implemented and why**, the supervisor probes **loopholes**, and
nothing is asked as a standalone technical question — everything is tied back to your
thesis.

Every fact below was verified against the code and the result artefacts, not from the
report.

---

# PART 0 — HOW TO ANSWER AT LENGTH

Your friends are right that longer answers serve you, but only if the length is
*structured*. Rambling reads as padding. Use this five-move shape — it naturally
produces a 60–90 second answer and it ends on your terms.

1. **Claim** — the direct answer, one sentence, no build-up.
2. **Mechanism** — how it actually works in your code. Name the file and the function.
3. **Evidence** — the number, the table, the artefact.
4. **Limitation** — name the weakness yourself, precisely and narrowly.
5. **What I'd change** — the specific fix, which shows you understand the boundary.

Move 4 is the one that separates a merit from a distinction. But **bound it**: say
what the limitation does *and does not* invalidate. "That's a real limitation, and
here is exactly what it does and does not affect" is the sentence to have ready.

Never volunteer a limitation that isn't in the question's blast radius. Owning a flaw
they asked about is rigour. Volunteering three they didn't ask about is self-harm.

---

# PART 1 — END-TO-END IMPLEMENTATION GUIDE

Know this well enough to walk it in ninety seconds without notes.

## 1.1 The nine stages

| # | Stage | File | In → Out |
|---|---|---|---|
| 1 | Synthetic input generation | `dataset_generator/generate_dataset.py` | params → `events_<size>.csv` at 7 sizes |
| 2 | Workload definition | `spark_jobs/{cpu,memory,io}_heavy.py` + `common.py` | CSV → Parquet + a JSON metric line |
| 3a | AWS execution | `aws/emr_runner.py`, `scripts/run_emr_regional_resumable_batch.py` | job spec → EMR cluster + step |
| 3b | Azure execution | `AzureVM_creation/create_vms.sh`, `cloud-init-final.yaml`, `run_benchmark.py` | job spec → VM cluster + timed run |
| 4 | Metric capture | `metrics/collect_metrics.py` | one run → one row appended to performance CSV |
| 5 | Price capture | `cloud_prices/fetch_cloud_prices.py` | pricing APIs → `aws_prices.csv`, `azure_prices.csv` |
| 6 | Carbon capture | `Carbon_dataset/zones.py`, `carbon_collect.py`, `renewable_collect.py` | Electricity Maps → daily CSVs |
| 7 | **Merge** | `ml/merge_model_dataset.py` | all of the above → `cloud_carbon_model_dataset.csv` (1,811 × 21) |
| 8 | Training | `ml/preprocessing.py`, `ml/train_model.py` | merged CSV → `best_cloud_model.joblib` + 4 JSON artefacts |
| 9 | Recommendation | `ml/recommendation_engine.py`, `dashboard/app.py` | 5 user inputs → ranked Top-N |

Analysis sits alongside stage 9: `ml/carbon_analysis.py` (emissions, Pareto front),
`ml/evaluate_recommendations.py` (leave-one-scenario-out vs 4 baselines),
`ml/statistical_tests.py` (per-fold metrics, paired tests, repeatability).

## 1.2 The numbers that describe the corpus

| Quantity | Value |
|---|---|
| Rows | 1,811 (AWS 1,011 · Azure 800) |
| **Unique configurations (groups)** | **689** |
| Configurations run more than once | 439 — so **250 were run only once** |
| Runs per configuration | min 1 · median 2 · max 12 |
| Scenarios (workload × size) | 21 |
| Candidates per scenario | mean 32.8, max 36 |
| Features → targets | 9 → 2 |
| **Design matrix after one-hot** | **1,811 × 27** |

That 250-singleton figure is worth knowing. It means over a third of your
configurations have a "mean" backed by a single observation. Nobody has asked you that
yet — be ready.

---

# PART 2 — WHY THESE ML MODELS (AND WHY NOT THE OTHERS)

This is the first reader's territory. Answer in three layers: why this *task
formulation*, why these *four*, why not the *obvious alternatives*.

## 2.1 Why supervised regression at all?

**Claim.** The quantities the decision needs — runtime in minutes and cost in dollars
— are continuous, and I have labelled measurements of both for every run. That is a
supervised regression problem by definition.

**Why not classification?** I could have framed it as "predict the best configuration"
as a 33-class problem. I rejected that for three reasons. First, the class set changes
with the candidate pool — adding one instance type changes the label space, so the
model would need retraining rather than just rescoring. Second, it throws away the
magnitude information: a classifier can tell you which is best but not *by how much*,
and the whole point of the balanced objective is trading off magnitudes. Third, and
decisively, the SLA filter needs an absolute predicted runtime in minutes to compare
against a user's deadline. A class label cannot be compared to "six minutes".

**Why not clustering?** Unsupervised methods would group similar configurations, but I
have labels — discarding them to cluster would be strictly less informative.

**Why not reinforcement learning?** RL is the theoretically attractive framing —
choose a configuration, observe the reward, improve the policy. It's infeasible here
because each episode is a real, billed cloud execution. Learning a useful policy over
a 33-action space would take thousands of episodes. My entire corpus of 1,811 runs
would be a few hundred episodes and it exhausted the budget.

## 2.2 Why these four models specifically

They form a deliberate **complexity ladder**, so the comparison answers "how much
model does this problem actually need?"

| Model | Role in the study | CV runtime R² |
|---|---|---|
| Linear Regression | Establishes the linear ceiling | 0.683 ± 0.031 |
| Decision Tree | Non-linearity with a single high-variance learner | 0.834 ± 0.079 |
| Random Forest | Variance reduction by bagging — **deployed** | **0.889 ± 0.055** |
| Gradient Boosting | Bias reduction by sequential fitting | 0.885 ± 0.042 |

**The scientific point.** Linear regression reaching only 0.683 demonstrates the
relationship is genuinely non-linear — runtime scales sublinearly with dataset size,
and node count interacts with workload type. The jump from Decision Tree 0.834 to
Random Forest 0.889 demonstrates that variance, not bias, was the binding constraint —
which is exactly what you'd expect on a corpus with shared-tenancy measurement noise.
So the ladder isn't decoration; each rung tests a hypothesis about the problem.

**Why tree ensembles suit this data specifically.** Four properties of my corpus point
straight at them:

- The dominant feature is a **threshold effect** — runtime jumps at dataset-size
  boundaries rather than scaling smoothly. Trees split on thresholds natively.
- Most features are **categorical with no natural ordering** — `c5.xlarge` is not
  "less than" `m6i.xlarge`. Trees handle one-hot categoricals without imposing order.
- There are **strong interactions** — the effect of doubling nodes depends on the
  workload type and the dataset size. Trees capture interactions without me having to
  specify interaction terms.
- The dataset is **small and tabular** (1,811 × 27). This is precisely the regime where
  tree ensembles remain the strongest family; deep learning's advantage appears at
  orders of magnitude more data.

**Multi-output handling.** All four are wrapped in `MultiOutputRegressor`, because
`GradientBoostingRegressor` fits a single target natively. The wrapper clones the
estimator once per target, so a full comparison run fits **eight models**. *Limitation
I'd state:* the wrapper treats the two targets as independent and cannot exploit the
correlation between them — and since cost is close to a deterministic function of
runtime, that is a missed opportunity. Section 2.6 below covers this.

## 2.3 Why not the alternatives — prepare all eight

### Ridge / Lasso / ElasticNet
Regularised linear models would have been cheap and would have handled the collinear
carbon features gracefully. I didn't include them because plain OLS already
established the linear ceiling at R² 0.683, and regularisation reduces variance, not
bias — it cannot close a 0.21 gap that comes from genuine non-linearity.
**Concede:** including Lasso would have been a *better* way to demonstrate that the
carbon features carry no information than post-hoc feature importances do, because the
coefficients would have been driven to zero explicitly. It's a cheap addition and I'd
include it in a revision.

### Support Vector Regression
Rejected on three grounds specific to this study. SVR has no native multi-output, so
it would need the same wrapper. It is highly sensitive to `C`, `epsilon` and `gamma` —
and since I ran no hyperparameter search, an untuned SVR would have been a strawman
rather than a fair comparison. And it exposes no feature importances, which I needed
for Chapter 8's analysis of what actually drives runtime.

### k-Nearest Neighbours
**I did use this — as a baseline.** `predict_nearest_size` in
`evaluate_recommendations.py` is a 1-NN lookup in dataset-size space, conditioned on
an exact match of configuration and workload. It reaches **0.810 top-1 accuracy at the
medium SLA against my model's 0.905**. So the KNN idea is in the study, correctly
positioned as the strongest naive alternative rather than as a candidate model.
That framing is stronger than "I didn't try KNN".

### XGBoost / LightGBM / CatBoost
The most likely follow-up, so have the honest answer. They would probably match or
slightly beat scikit-learn's Gradient Boosting. I didn't use them because: the
environment is pinned to a reproducible scikit-learn stack (`requirements.txt` fixes
`scikit-learn==1.8.0`) and adding gradient-boosting libraries widens the dependency
surface; their advantage is largest on large, high-cardinality data, and at 1,811 × 27
the gain over sklearn's ensembles is marginal; and their real edge comes from tuning,
which I had no budget for. **Concede:** a tuned LightGBM is the obvious next
comparison, and given RF and GB were statistically inseparable at defaults, I cannot
claim my winner would survive it.

### Neural networks / MLP
1,811 rows and 27 features is one to two orders of magnitude below where neural
networks become competitive on tabular data — the consistent finding in the tabular
benchmarking literature is that tree ensembles still lead in this regime. An MLP would
also need architecture and learning-rate tuning I didn't budget, and would give me no
feature importances. It would have been a fashionable choice, not a defensible one.

### Gaussian Process regression
**The strongest "why not" answer you have, so use it.** A GP would give a predictive
*variance* natively — which is precisely the thing I identify as the most valuable
missing capability, because the residual 0.095 SLA violation rate comes from filtering
on a point estimate with no confidence attached. I didn't use one because GP training
is O(n³) and, more importantly, because I framed uncertainty as future work rather than
core scope. If I were starting again, a GP or a quantile-regression forest would be in
the comparison from the beginning, not deferred.

### Bayesian optimisation (the CherryPick approach)
This is a **search strategy, not a predictor**, and it solves a different problem.
Bayesian optimisation finds a good configuration for one recurring workload by
iteratively running it and updating a surrogate. My problem formulation is the
opposite: zero new runs at inference, generalising across workloads from a
pre-collected corpus. The two are complementary rather than competing — BO minimises
profiling; I eliminate it, at the cost of only working within pre-characterised
workload classes.

### Time-series models
No temporal dependence exists in the target. Given the configuration, each run is
independent — runtime doesn't depend on when the previous run happened. The one place
time *does* matter is grid carbon intensity, which varies hourly, and I address that
as a limitation rather than by modelling it.

---

# PART 3 — FEATURE SELECTION

Expect this. Answer it head-on rather than implying you did something you didn't.

## 3.1 What method did you use?

**Claim.** I used **domain-driven manual selection**, not an algorithmic feature
selection method. `FEATURE_COLUMNS` in `ml/preprocessing.py` is a fixed list of nine.
There is no `SelectKBest`, no RFE, no variance thresholding, no PCA anywhere in the
codebase.

**The justification.** The feature set is not a search problem here — it is the set of
things a user actually knows *before* running the job. That is a hard constraint from
the problem definition, not a modelling preference. A feature the user cannot supply
at inference time is useless regardless of how predictive it is. So the nine are:
what they choose (cloud, region, machine type, nodes), what they know about the job
(dataset size, workload type), and what is determined by their choice (electricity
zone, carbon intensity, renewable percentage).

**The limitation, stated plainly.** Domain selection is defensible for *inclusion* but
it gave me no mechanism for *exclusion*. That is exactly how the collinearity defect
below survived into the final feature set. An algorithmic pass — even something as
simple as a correlation filter or Lasso coefficients — would have caught it before
training rather than after.

## 3.2 What did feature importance actually show?

From `data/models/feature_importance.json`, for the runtime target:

| Feature | Importance |
|---|---|
| `dataset_size_mb` | **0.606** |
| `machine_type_Standard_D2s_v3` | 0.096 |
| `workload_type_io-heavy` | 0.089 |
| `nodes` | 0.080 |
| all carbon + renewable features **combined** | **< 0.01** |

Two readings. The useful one: dataset size dominating at 0.61 is exactly what you'd
expect if real work is being measured rather than fixed overhead — which is a defence
against the "you're only measuring startup" attack. The uncomfortable one: the carbon
features contribute essentially nothing, for the reason in 3.3.

**Be careful with the phrasing.** These are *impurity-based* importances (Gini
reduction), which are known to be biased toward high-cardinality and continuous
features. `dataset_size_mb` is continuous with seven levels; the one-hot machine types
are binary. So the 0.606 is somewhat inflated relative to a permutation importance,
which is the more trustworthy measure. I did not compute permutation importances.
Saying this yourself is a strong move.

## 3.3 The collinearity defect — own this before they find it

**Verified fact:** `carbon_intensity_mean` has **exactly one distinct value per
region**, and all 1,811 rows have `carbon_feature_source = regional_mean`.

So `carbon_intensity_mean`, `renewable_percentage_mean` and `electricity_zone` are all
**perfectly collinear with the one-hot encoded region**. They carry zero independent
predictive information. The near-zero feature importance is not a finding about carbon
— it is arithmetic.

**Why they're in the file at all.** The merged dataset is a single artefact serving two
stages. The *prediction* stage doesn't need them. The *ranking* stage genuinely does —
the emissions calculation multiplies predicted runtime by power draw by grid intensity
by PUE, so the columns must be present per row. Including them in `FEATURE_COLUMNS`
was a design error, not a necessity.

**Does it damage the results?** Not materially. A collinear constant is simply never
selected for a useful split in a tree, which is why importance is near zero rather
than misleading. It would matter for a linear model's coefficient interpretation, and
I don't interpret those coefficients.

**The fix.** Drop the three from `FEATURE_COLUMNS`, keep them in the dataframe, and
join them at scoring time. That reduces the effective feature set from nine to six.

## 3.4 What features are missing

Be ready with this, because "what would you add?" follows naturally.

- **Instance characteristics as features** — vCPUs, memory GB, clock speed, processor
  family. Currently `machine_type` is an opaque one-hot, which is why the model cannot
  score an instance type it has never seen. This is the single highest-value addition.
- **Measured resource utilisation** — `cpu_avg_pct` is null for **55.8%** of rows and
  `memory_avg_pct` for **100%**. With full coverage these would support both better
  prediction and a genuine workload fingerprint.
- **Spark event-log metrics** — shuffle read/write volumes, GC time, task duration
  variance. Not collected because event logging is off by default on EMR and I hadn't
  configured it at cluster launch.
- **Input data characteristics** — row count, column count, cardinality, compression.
  Currently only size in megabytes, which conflates a wide sparse file with a narrow
  dense one.

---

# PART 4 — HYPERPARAMETER TUNING

## 4.1 The honest answer

**There is none.** Verified by search across the entire codebase — no `GridSearchCV`,
no `RandomizedSearchCV`, no `param_grid`, no Optuna, no Hyperopt.

The actual settings, from `MODEL_REGISTRY` in `ml/train_model.py`:

| Model | Parameters |
|---|---|
| Linear Regression | scikit-learn defaults |
| Decision Tree | defaults, `random_state=42` |
| Random Forest | `n_estimators=250`, `min_samples_leaf=1`, `n_jobs=-1`, `random_state=42` |
| Gradient Boosting | defaults, `random_state=42` |

The only non-default value in the entire study is `n_estimators=250` (up from 100).

## 4.2 How to defend it

**Do not dress this up.** The defensible position has four parts.

1. **State the consequence precisely.** My comparison is between *default-configured
   algorithms*, not tuned ones. That is a real limitation on the model-selection claim.
2. **Bound what it invalidates.** It does not invalidate the *accuracy* figures — R²
   0.889 under grouped cross-validation is a real, honestly-earned number regardless of
   whether a tuned model could do better. It invalidates only the claim that Random
   Forest is the *best available* model. I make the weaker claim: it is the best of the
   four I compared, at defaults.
3. **Connect it to the significance test.** RF and GB are statistically inseparable
   (p = 0.177 on runtime MAE, p = 0.105 on cost MAE). A tuned Gradient Boosting could
   plausibly separate from an untuned Random Forest. So the tuning gap and the
   non-significance result should be read together, and I say so.
4. **Give the specific fix.** A `RandomizedSearchCV` nested inside the outer
   `GroupKFold` — nested cross-validation, so tuning happens only on training folds
   and the outer estimate stays unbiased. Search space: `max_depth`,
   `min_samples_leaf`, `max_features` for RF; `learning_rate`, `n_estimators`,
   `max_depth`, `subsample` for GB. That is a few hours of compute on this dataset.

## 4.3 The follow-ups you'll get

**"`min_samples_leaf=1` — isn't that overfitting?"**
Individual trees are grown to purity, so yes, each one overfits. That is intended
behaviour for a random forest: bootstrap sampling plus feature subsampling at each
split means the variance of individual overfit trees averages out across 250 of them
while bias stays low. It's the scikit-learn default and it's why forests are robust
without tuning. The evidence it isn't overfitting in a way that matters is the grouped
CV result — 0.889 ± 0.055 on configurations never seen in any form is not the
signature of an overfit model.

**"Why 250 trees?"**
More trees monotonically reduce variance with diminishing returns and no overfitting
risk — the accuracy curve flattens, it doesn't turn down. 250 is comfortably past the
knee for a dataset this size, and the cost is a slightly larger artefact (the joblib
file is ~40 MB). *Concede:* I didn't plot the out-of-bag error against tree count to
find where it actually flattened, which would have justified the number empirically
rather than by convention.

**"Why `random_state=42` everywhere?"**
Reproducibility — anyone re-running the pipeline gets identical models and metrics.
*Limitation:* every reported number is conditional on one seed. Reporting variance
across several seeds would be more honest. The fold standard deviations partly
compensate, since they expose sensitivity to data partitioning, but not to model
initialisation.

**"Why 5 folds?"**
A conventional bias–variance compromise, and constrained by having 689 groups. It has
a cost I acknowledge: with 5 paired observations, the Wilcoxon signed-rank test
**cannot reach p < 0.05 at all** — the minimum achievable p-value is above it. That's
recorded in `statistical_tests_summary.json`, and it's why I quote the paired t-test
and Cohen's d instead.

---

# PART 5 — GENERALISABILITY

They flagged this specifically. The right answer is a **taxonomy**, not a yes/no.

| Axis | Tested? | Evidence / what happens |
|---|---|---|
| Repeated run of a **seen configuration** | Deliberately excluded | Grouping prevents it; this would be memorisation, not generalisation |
| **Unseen configuration** in a seen scenario | ✅ Yes | Grouped holdout + GroupKFold, runtime R² 0.889 ± 0.055 |
| **Unseen scenario** (workload × size) | ✅ Yes | Leave-one-scenario-out, 0.905 top-1 at medium SLA |
| **Unseen workload type** | ❌ No | Would need leave-one-*workload*-out; not run |
| **Unseen machine type** | ❌ Impossible | `handle_unknown="ignore"` → all-zeros → predicts near conditional mean, **silently** |
| **Unseen provider** | ❌ Impossible | `cloud` is one-hot; a third provider has no encoding |
| **Beyond 5 GB** | ❌ Fails badly | Trees don't extrapolate — prediction saturates at the nearest leaf and is confidently wrong |
| **A different time period** | ❌ No | Prices and carbon are dated snapshots |

## 5.1 The claim you make and the claim you don't

**What I demonstrate:** generalisation to an *unbenchmarked configuration* and an
*unbenchmarked scenario*. That is the practically useful case — a user with a
workload class the system knows, at a size it has not measured, on hardware it has
seen elsewhere in the corpus.

**What I do not claim:** generalisation to an unseen workload type. Conflating those
two would be the most serious overclaim available in this project, and Section 9.6.3
is explicit about it. My protocol holds out (workload × size); holding out cpu-heavy at
2048 MB still leaves cpu-heavy at the other six sizes in training.

**Why I didn't test leave-one-workload-out:** with only three workload classes, each
fold discards a third of the corpus and the result is a single number with no
confidence interval. *That said* — I could have run it and reported it as indicative
with the caveat attached, and it would have been more informative than not running it.
That's a fair criticism.

## 5.2 The two silent failure modes

Be the one who raises these.

**Unknown category.** `OneHotEncoder(handle_unknown="ignore")` encodes an unseen
machine type as all-zeros rather than raising. The model then has no information about
that instance and predicts near the conditional mean — **without any warning**. For a
research prototype that prevents a crash; for production it's a defect. It should log
or reject.

**Out-of-range input.** A user entering 500 GB gets a prediction. Tree ensembles
return the value of the nearest leaf, so the answer saturates at roughly the 5 GB
prediction and is confidently wrong. There is no guard. The correct behaviour is to
warn that the input is outside the validated 10 MB – 5 GB range, or refuse.

## 5.3 The scale question

**"Your median runtime is 1.27 minutes. Does anything here generalise to production?"**

Two parts. The concession: 5 GB is an order of magnitude below production scale, and
fixed overhead is a larger proportion of my runtimes than it would be at scale, which
compresses the differences between configurations and makes the prediction problem
easier than it really is. That is why the nearest-size heuristic performs so nearly as
well — at this scale there isn't much non-linearity left to learn. The bound was
Azure quota (32 vCPUs in Central India, 10 in Southeast Asia) and budget, not
scientific preference.

The defence: runtime spans **0.271 to 13.03 minutes — a 48× range** — so configuration
and size clearly move the number; if it were fixed overhead the variance would be flat.
Dataset size dominates at 0.606 importance, which is what you'd see if real work were
being measured. And I time only `spark-submit`, with the Azure data downloaded to local
disk before the timer starts.

**What generalises is the method** — the per-run emissions accounting, the
leakage-controlled protocol, and the finding that node-hours drive cost and carbon
together. The specific R² and the specific instance rankings are bounded to 10 MB–5 GB,
two node counts and twelve machine types.

---

# PART 6 — THE LOOPHOLES, RANKED

Supervisor territory. Ordered by how much damage an unprepared answer does.

### 1. Workload scale
Covered in 5.3. Highest-damage question in the viva.

### 2. Carbon features carry zero information
Covered in 3.3. One distinct value per region; perfectly collinear with the region
one-hot. Design error in `FEATURE_COLUMNS`, not in the results.

### 3. No hyperparameter tuning
Covered in Part 4. Comparison is between defaults; accuracy claims survive, "best
model" claim weakens.

### 4. No feature selection method
Covered in Part 3. Domain-driven inclusion with no mechanism for exclusion.

### 5. SLA deadlines are derived from the answer sheet
`SLA_LEVELS = {tight: 0.25, medium: 0.50, loose: 0.75}` are percentiles of the
**measured** runtime distribution *for the held-out scenario*. So by construction
exactly 25/50/75% of candidates are feasible, and the constraint is not independent of
the ground truth I score against.
**Defence:** a fixed deadline in minutes is meaningless across 10 MB to 5 GB, so
percentiles keep difficulty comparable across scenarios. What the design establishes
is the *relative* ordering of methods under identical constraints — which is the
comparison I actually make. **Fix:** derive deadlines from user-stated requirements, or
from a multiple of a fixed reference configuration's predicted runtime.

### 6. Negative cost regret
−0.37% at the medium SLA. **Negative regret is not better-than-optimal — it is the
arithmetic signature of an SLA violation.** The optimum is the cheapest configuration
whose *measured* runtime meets the SLA; my engine selects among those whose
*predicted* runtime meets it. When the model under-predicts, a genuinely too-slow and
usually cheaper configuration enters the believed-feasible set. So −0.37% and the
0.095 violation rate are the same phenomenon measured twice. The clean number is the
loose-SLA +1.07% at a 0.000 violation rate.

### 7. Cost is nearly derivable from runtime
Cost = price × nodes × runtime, all known at inference — so a second model head looks
redundant, and cost R² 0.890 is largely runtime R² wearing different units.
**Partial defence, with a number:** the implied hourly rate is *not* constant within a
configuration. For `c5a.xlarge` in ap-south-1 the implied rate has a **coefficient of
variation of 22.6%**, and for `m5a.xlarge` 19.3% — because on EMR the master node can
differ from the workers and the EMR service fee is added on top of EC2. The measured
correlation between runtime and cost is **0.763**, not 1.0. The learned mapping absorbs
that heterogeneity. **Concede anyway:** predicting runtime only and computing cost in
closed form would be simpler and more interpretable, with cost error reported as
propagated runtime error.

### 8. Skewed target, untransformed
Runtime has **skew 2.573 and kurtosis 9.263** — heavily right-tailed. No log transform
was applied. Consequence: RMSE 0.477 against MAE 0.268, roughly 1.8×, which indicates a
tail of larger errors rather than uniform error, and the model under-serves the long
jobs. A `TransformedTargetRegressor` with `log1p` is the standard fix and I didn't use
one. Nobody has raised this yet — have the answer.

### 9. Candidate set is closed
`_build_candidate_frame` uses `drop_duplicates()` on the observed dataset, so the
engine can only recommend configurations already benchmarked somewhere in the corpus.
It generalises to unbenchmarked *scenarios*, not to new instance types. Fix: learn
instance characteristics as features.

### 10. Evidential support is ignored
`Standard_D4as_v4` in Central India has **2 records in the entire corpus**, yet is
scored identically to a configuration with 300 and displayed with no distinction. And
**250 of 689 configurations were run only once**, so their "mean" in the ground truth
is a single observation. The `runs` column preserves the count but nothing downstream
uses it.

### 11. AWS vs Azure is not a controlled comparison
EMR with managed YARN reading S3, versus self-managed Spark standalone on Ubuntu VMs
reading local disk. Different resource managers, different storage paths, different
Spark versions. A cross-provider runtime difference confounds all four. **I never claim
"Azure is faster than AWS."** What is controlled is the comparison *within* a provider.
Cost is comparable across providers because both use the same equation and the EMR fee
is added explicitly.

### 12. The EPYC finding is confounded
Every AMD EPYC part in the corpus sits only in Central India (`Standard_D2as_v4`, 84
records). Provider, processor family, deployment model and region are entangled.
**The claim that survives is methodological:** the two accounting methods disagree. Not
which processor is independently more efficient. Disentangling needs the same instance
family in both regions, which quota blocked.

### 13. Utilisation assumption
Fixed 50% vCPU utilisation across all runs, because `cpu_avg_pct` is null for 55.8% of
rows and `memory_avg_pct` for 100%. Known bias: any workload running hotter than 50%
has emissions understated, cooler has them overstated — and CPU-heavy versus I/O-heavy
almost certainly differ. Applied uniformly for comparability rather than mixing sources.

### 14. Ice Lake substitution
Cloud Carbon Footprint publishes no Ice Lake coefficient, so `c6i` and `m6i` use
Cascade Lake. Ice Lake is more efficient, so this **overstates** their draw — biasing
*against* the newest Intel parts, which means the EPYC-versus-Intel gap in the headline
finding is if anything exaggerated by the substitution. State the direction of bias;
the magnitude isn't quantifiable without a published coefficient.

### 15. Embodied carbon excluded
Operational emissions only. For short jobs on modern hardware, embodied carbon can
exceed operational carbon, so this is a real omission — justified because attributing
manufacturing emissions to a 76-second job needs lifetime and allocation assumptions
that add more uncertainty than signal.

### 16. Statistical power
n = 5 folds. Wilcoxon cannot reach p < 0.05 at all. Failing to reject is **not**
evidence of equivalence — with this power a real difference could easily go undetected.
Correct phrasing: "no evidence of a difference", which is why RF was selected on the
secondary criterion of consistency across all four CV metrics.

### 17. Refit on full data
`compare_models()` refits the winning pipeline on all data after evaluation. This is
the standard two-stage protocol — metrics come from held-out data, the deployed
artefact uses everything. The reported R² is never computed from the refit model. Mild
optimism exists in *selection* since CV used the full dataset, but with four candidate
models and no hyperparameter search it's negligible.

### 18. SLA violation is conditionally defined
In `evaluate_scenario`, `sla_violation` is `measured_runtime > sla AND not infeasible`
— so a scenario where the model found nothing feasible is counted under
`no_feasible_prediction` instead. That's defensible (they're different failure modes)
but it means the violation rate is conditional on the model believing something was
feasible. Know this before someone reads the code.

### 19–22. Documentation and process defects
- **Table 24** quotes R² 0.9001 / 0.9150 — Gradient Boosting's held-out numbers — as
  evidence for FR6/FR7, but Random Forest is deployed (0.8985 / 0.8938). Volunteer this.
- **CherryPick, Ernest and PARIS** are named in the abstract and Section 9.7.1 but
  appear in none of your thirteen references. Fix before submission.
- **Ethics:** the SPER form declares no human participants, but Chapter 1 reports a
  46-respondent questionnaire and Section 8.2 a 10-person evaluation. A survey of human
  opinions *is* human participant research even when low-risk. The remedy is an amended
  SPER declaration. Do not say "it wasn't really human subjects research."
- **Secrets:** `AzureVM_creation/config.env` has a live storage account key and the VM
  admin password in plaintext, in the repo. Rotate and scrub before sharing.

---

# PART 7 — TOOLS AND METHODOLOGIES, JUSTIFIED IN CONTEXT

Every one of these can be asked as "why this and not X?"

| Choice | Why it fits *this* research |
|---|---|
| **Apache Spark** | De facto standard for distributed batch analytics, with a managed service on AWS and first-class support on Azure — so the comparison reflects what practitioners actually run. Flink is stream-first; Dask has no managed equivalent on either provider. |
| **AWS EMR + Azure VMs** | Not symmetric by design. Databricks was planned but DBU charges on top of compute were unaffordable on a limited-credit account. Recorded in Section 8.9 as a materialised risk with "reduced comparability with EMR" as the residual effect. |
| **scikit-learn** | Consistent API across all four models, one `ColumnTransformer` shared, `Pipeline` prevents preprocessing leakage into CV folds, and version-pinnable for reproducibility. |
| **Electricity Maps** | Zone-level intensity *and* renewable share, daily granularity, documented methodology, and a historical range rather than live-only — which a reproducible experiment needs. |
| **Cloud Carbon Footprint coefficients** | Published, peer-reviewed, per-microarchitecture watt-per-vCPU figures with provenance. Each row of `instance_power_draw.csv` carries a `source` string. |
| **On-demand pricing** | The SLA guarantee is the point. Spot instances can be reclaimed mid-job, making any deadline commitment unsound. Spot becomes safe only with uncertainty-aware filtering. |
| **Snapshot prices, not live API** | Reproducibility — re-running later reproduces identical cost values. Cost: recommendations reflect a snapshot date. |
| **Streamlit** | Prototype-appropriate: sub-second inference from a persisted joblib and cached CSV, no web stack to build. Not production — single-user, no auth. |
| **OOAD** | The system is components exchanging artefacts, not a data-flow application. It's what let me swap Databricks for self-managed VMs without touching the ML or recommendation layers. *Concede:* only the engine is genuinely object-oriented; training and merge are procedural modules. |
| **Research Onion** | Positivist, deductive, quantitative mono-method, experimental strategy, cross-sectional. *Concede if the write-up doesn't traverse all six layers explicitly.* |
| **Quantitative** | *Concede:* it's really quantitative-dominant **mixed methods** — Chapter 1's survey and Section 8.2's evaluation both gather human judgement. Describing it as purely quantitative under-describes it. |

---

# PART 8 — TEN LIKELY QUESTIONS, ONE-LINE OPENERS

Rehearse the first sentence of each until it's automatic. The rest can be built live.

1. **"Why Random Forest over Gradient Boosting?"** → "Because selection is made on grouped cross-validation rather than a single split, and Random Forest leads on all four CV metrics — though I'll say immediately that the two are statistically inseparable."
2. **"Why didn't you tune hyperparameters?"** → "I didn't, and the consequence is that my comparison is between default-configured algorithms rather than tuned ones."
3. **"How did you select features?"** → "By domain constraint rather than algorithmically — the feature set is what a user actually knows before running the job."
4. **"Does it generalise?"** → "To unbenchmarked configurations and unbenchmarked scenarios, yes, and I measure both. To an unseen workload type, no, and I don't claim it."
5. **"Why is cost a predicted quantity?"** → "Largely a fair criticism — though the implied hourly rate varies by up to 22.6% within a configuration, which is what the learned mapping absorbs."
6. **"Your carbon features have near-zero importance."** → "They have exactly one distinct value per region, so they're perfectly collinear with region and carry zero independent information. Including them in the feature list was a design error."
7. **"Why not deep learning?"** → "1,811 rows and 27 features is one to two orders of magnitude below where neural networks become competitive on tabular data."
8. **"A lookup table gets 0.81 against your 0.90."** → "It does, and that's a difference of two scenarios in twenty-one. The metric that separates them is SLA violation — 0.095 against 0.143."
9. **"Isn't cheapest-is-greenest trivially true?"** → "It's close to structural, because both cost and emissions are linear in node-hours — so the correct claim is narrow: on this corpus they were aligned rather than in tension."
10. **"What would you do differently?"** → "Enable Spark event logging at cluster launch, which is the enabling data for workload fingerprinting — not configuring it is the most consequential planning failure in the project."

---

# PART 9 — THE NIGHT BEFORE

Verify these three yourself; don't take them on trust:

1. Re-run `python ml/carbon_analysis.py` and confirm the `warnings` array in
   `carbon_analysis_summary.json` is still empty — that's your proof no fallback power
   value (12 W/vCPU or the 60 W default) contaminated any reported emissions figure.
2. Check the abstract against the reference list for CherryPick, Ernest and PARIS.
3. Confirm the exact respondent count for the Chapter 1 questionnaire. The percentage
   granularity (76.1%, 71.7%, 67.4%) is consistent with n = 46 — but know the real
   number rather than inferring it in the room.

**The three cards to play often:** 1,811 real measured executions, not simulation. You
reported against yourself — the heuristic nearly matches the model, the two ensembles
are inseparable, and you said so. And the carbon finding is genuinely counter-intuitive
and correctly caveated.

**The line to hold on every limitation:** *"That's a real limitation, and here is
exactly what it does and does not invalidate."*
