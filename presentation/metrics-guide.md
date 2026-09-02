# Metrics guide — what they are, your values, and how to say them

Every number verified against the result artefacts in `data/models/` and `data/results/`.
Nine families. The shortlist for the 20-minute talk is at the end.

---

# FAMILY 1 — Prediction accuracy (regression)

You report three, and you should be able to say why three rather than one: they answer
different questions and one of them is a diagnostic for the others.

### MAE — Mean Absolute Error
**What it is.** The average size of the error, ignoring direction, in the target's own
units. `mean(|actual − predicted|)`.

**Your value.** Runtime **0.270 minutes ≈ 16 seconds**. Cost **$0.0024**.

**Why it matters here.** This is the number a user experiences. If the system says
four minutes, expect roughly four minutes give or take sixteen seconds. It is the
honest headline because it is in minutes, not a unitless score.

**Say this:** *"MAE is the average error in the target's own units — mine is sixteen
seconds on runtime, which is what a user actually feels."*

### RMSE — Root Mean Squared Error
**What it is.** `sqrt(mean((actual − predicted)²))`. Squaring before averaging means
large errors are penalised disproportionately.

**Your value.** Runtime **0.477 minutes**. Cost **$0.0040**.

**Why it matters here.** RMSE ÷ MAE is a **distribution diagnostic**. If they're close,
errors are uniform. If RMSE is much larger, a few bad predictions dominate. Yours is
0.477 / 0.268 = **roughly 1.8×**, which tells you there is a tail of larger errors
rather than uniform error — consistent with runtime being heavily right-skewed
(skew 2.57).

**Say this:** *"RMSE punishes large misses. The fact that mine is about 1.8 times MAE
tells me the error isn't uniform — there's a tail, and it's on the long-running jobs."*

### R² — Coefficient of determination
**What it is.** `1 − SS_res/SS_tot` — the proportion of variance in the target the model
explains, relative to a baseline that just predicts the mean. Scale-free, so you can
compare across targets with different units.

**Your value.** Runtime **0.889 ± 0.055**. Cost **0.890 ± 0.034**.

**Why it matters here.** It's the only one of the three that lets you compare the
runtime model and the cost model on the same axis, and it's what makes the
linear-versus-ensemble comparison interpretable.

**The caveat to volunteer.** R² rewards a model for capturing variance that comes from
an easy, dominant feature — dataset size carries 0.606 importance — so a high R² partly
reflects that runtime scales with data size, which is not a deep insight. It's also
sensitive to the spread of the test set: a fold containing the 13-minute outlier has
more variance to explain than one that doesn't, which is where the ±0.055 comes from.

**The relative-error framing.** MAE 0.270 against a median runtime of 1.272 minutes is
about a **21% relative error**. That's the more sober number, and quoting it yourself
reads as rigour rather than weakness.

---

# FAMILY 2 — Model comparison and statistical significance

This family is what separates "I picked the best number" from "I tested whether the
difference is real."

### Standard deviation across folds
Reported as `± value` on every CV metric. Runtime R² ±0.055 for Random Forest, ±0.079
for the Decision Tree. **Lower means more stable across different data partitions** —
and the fact that the single tree has the widest spread is exactly why bagging helps.

### Paired t-test (`scipy.stats.ttest_rel`)
**What it is.** Tests whether the mean *difference* between two models across matched
folds is significantly different from zero. Pairing is correct here because every model
sees identical folds, so between-fold variance is removed.

**Your results, runtime MAE:**

| Comparison | p-value | Significant? |
|---|---|---|
| Random Forest vs Linear Regression | 0.0001 | ✅ |
| Gradient Boosting vs Linear Regression | 0.0001 | ✅ |
| Random Forest vs Decision Tree | 0.0016 | ✅ |
| Decision Tree vs Gradient Boosting | 0.0200 | ✅ |
| **Random Forest vs Gradient Boosting** | **0.1767** | ❌ |

Overall: **9 of 12 pairwise comparisons reach significance.** The test isn't powerless
— it separates the ensembles from the tree and the linear baseline cleanly. It just
cannot separate the two ensembles from each other.

**The critical framing.** Failing to reject is **not** proof of equivalence. With n = 5
the test has low power, so a real difference could go undetected. Say *"I have no
evidence of a difference"*, never *"they're equivalent."*

### Wilcoxon signed-rank
Non-parametric alternative that avoids the normality assumption. **With 5 paired
observations it cannot reach p < 0.05 at all** — the minimum achievable p-value is
above the threshold. That's recorded in `statistical_tests_summary.json` and it's why
you quote the t-test and effect size instead.

### Cohen's d — effect size
**What it is.** The standardised size of a difference: mean difference ÷ pooled
standard deviation. Conventionally ~0.2 small, ~0.5 medium, ~0.8 large.

**Your values, runtime MAE.** RF vs GB **d = 0.73** (medium-to-large *despite*
p = 0.177). RF vs Decision Tree **d = 3.39**. RF vs Linear Regression **d = 6.35**.

**Why report it alongside p.** A p-value tells you whether you can detect a difference;
d tells you how *big* it is. The RF/GB case is the textbook illustration: a
medium-to-large effect that is not statistically detectable at n = 5. That pair of
numbers together is a much more honest description than either alone.

### 95% confidence interval
For RF vs GB on runtime MAE the interval is **[−0.010, +0.041]** — it straddles zero,
which is the same conclusion as p > 0.05 expressed in the metric's own units.

---

# FAMILY 3 — Data quality and repeatability

This family is unusual for a student project and worth spending time on.

### Coefficient of variation (CV%)
**What it is.** `standard deviation ÷ mean × 100` for repeated runs of one identical
configuration. A unitless measure of how reproducible a measurement is.

**Your values.** 439 configurations were run more than once. **Median CV 4.15%,
maximum 84.45%.**

**Why it matters.** It sets a **ceiling on achievable accuracy** — no model can predict
a quantity that isn't reproducible. The 84% worst case is almost certainly
shared-tenancy interference: noisy neighbours on the underlying host. It's also the
substantive argument for selecting on cross-validation rather than a single split,
because with that much measurement variance one partition is a high-variance estimate.

**Say this:** *"I measured my own measurement noise. The median is 4.15%, so the
campaign reproduces — but the worst case is 84%, and that's a hard ceiling no amount of
modelling can pass."*

---

# FAMILY 4 — Recommendation quality (decision-level)

**This is your most distinctive family.** Most dissertations stop at R². You went on to
measure whether the *decisions* are good, against four competing baselines. Lead with
this if you have to choose.

Protocol: leave-one-scenario-out across all 21 workload × dataset-size scenarios.

### Top-1 accuracy
Fraction of scenarios where the recommender's first choice is the true optimum — the
cheapest configuration whose *measured* runtime meets the SLA.

| Method | Tight | Medium | Loose |
|---|---|---|---|
| **Random Forest** | 0.810 | **0.905** | **0.952** |
| Nearest size | 0.762 | 0.810 | 0.857 |
| Historical mean | 0.524 | 0.429 | 0.429 |
| Largest cluster | 0.286 | 0.286 | 0.286 |
| Random | 0.000 | 0.000 | 0.000 |

### Top-3 hit rate
Whether the true optimum appears anywhere in the top three. Relevant because the tool
returns a ranked list, not a single answer — a user sees several options.
**Yours: 0.905 tight, 0.905 medium, 0.952 loose.**

### Cost regret (%)
How much more expensive the chosen configuration is than the true constrained optimum.
Zero is perfect.
**Yours: +16.56% tight, −0.37% medium, +1.07% loose.**

⚠️ **Negative regret is not better-than-optimal.** It is the arithmetic signature of an
SLA violation — when the model under-predicts runtime, a genuinely too-slow and usually
cheaper configuration enters the believed-feasible set. **The −0.37% and the 0.095
violation rate are the same phenomenon measured twice.** The clean figure to quote is
the loose-SLA **+1.07% at a 0.000 violation rate**.

### SLA violation rate
Fraction of scenarios where the recommended configuration's *measured* runtime exceeded
the deadline. **This is your defensible advantage.**

**Random Forest 0.095 vs nearest-size 0.143 at the medium SLA** — roughly a third fewer
violations. And **0.000 at the loose SLA**.

*Definitional note, in case someone reads the code:* `sla_violation` is defined as
`measured_runtime > sla AND not infeasible`, so a scenario where the model found nothing
feasible is counted separately under `no_feasible_prediction`. Different failure modes,
counted separately — defensible, but know it.

### Infeasible rate
Fraction of scenarios where no candidate's predicted runtime met the deadline, so the
engine fell back to returning the closest alternatives.
**Yours: 0.048 tight, 0.000 medium, 0.000 loose.** Historical mean hits 0.381–0.429.

---

# FAMILY 5 — Sustainability metrics

### Carbon intensity (gCO₂eq/kWh)
Grams of CO₂-equivalent per kilowatt-hour of grid electricity. From Electricity Maps.
**IN-WE (Mumbai / Central India) 643.3 · SG (Singapore / Southeast Asia) 480.7.**

### Renewable percentage
Share of grid generation from renewable sources.
**Central India 18.9% · Singapore ~5.8%.**

### PUE — Power Usage Effectiveness
Total facility energy ÷ IT equipment energy. A PUE of 1.15 means 15% overhead for
cooling, power distribution and lighting on top of what the servers draw. It scales
IT-level energy up to facility-level energy, which is what should be multiplied by grid
intensity. **AWS 1.15 · Azure 1.18 · default 1.20**, from published sustainability
reports.

### Energy (kWh) and emissions (gCO₂eq)
```
energy_kWh   = power_W × nodes / 1000 × runtime_min / 60
emissions_g  = energy_kWh × carbon_intensity × PUE
```
**Mean per-run emissions by region:** Azure Central India **0.346** · Azure Southeast
Asia **0.448** · AWS ap-southeast-1 **0.467** · AWS ap-south-1 **0.567** gCO₂eq.

### Watts per vCPU
The efficiency figure that drives your headline finding. From Cloud Carbon Footprint
coefficients at 50% utilisation.
**AMD EPYC (2nd gen) 1.08 W/vCPU vs Intel 2.30–2.72 W/vCPU.** Roughly a 2.5× gap.

---

# FAMILY 6 — Multi-objective metrics

### Pareto front size
A configuration is **Pareto-optimal** (non-dominated) if no other configuration is
better on *every* objective — cost, runtime and emissions. The front is the set of such
configurations.

**Yours: mean 2.05 members per scenario, maximum 5.**

**How to read it.** A front of 1 means one configuration dominates everything — no
trade-off exists. A front of 5 means five genuinely defensible answers depending on what
you weight. A mean of 2.05 says trade-off structure exists but is modest on this corpus,
and it's mostly against *runtime* rather than against cost.

### Cheapest-is-greenest coincidence
**21 of 21 scenarios.** The cheapest configuration was also the lowest-emitting.
Explain *why* rather than just stating it: cost is `price × nodes × runtime` and
emissions are `power × nodes × runtime × intensity × PUE` — **both are linear in
node-hours**, so within a region they can only diverge if the price-per-watt ordering
differs from the watts-per-node ordering. On your corpus the 2-node `Standard_D2as_v4`
is simultaneously cheapest per hour and lowest power draw, so it wins both.

### Ratio-to-best and the balanced optimisation score
`ratio_to_best = (value − best) / best` — a proportional gap from the best candidate.
0.0 means best; 0.38 means 38% worse than the best available. Unit-free and independent
of the spread of the candidate set.

```
Score = √(0.35·runtime² + 0.35·cost² + 0.20·emissions² + 0.10·renewable_penalty²)
```
A weighted Euclidean distance from the ideal point. **Lower is better.** Balanced mode
selects a configuration no single-objective mode selects in **3 of 21 scenarios**.

### Node-count trade-off
The most quotable operational number you have. Doubling from 2 nodes to 4:
**runtime −43%, cost +38%, emissions +39%.** The runtime saving is sublinear while
node-hours are linear — which is the mechanism behind everything above.

---

# FAMILY 7 — Interpretability

### Feature importance (Gini / impurity reduction)
How much each feature reduces impurity across all splits in the forest, normalised to
sum to 1.

**Runtime target:** `dataset_size_mb` **0.606** · `machine_type_Standard_D2s_v3` 0.096
· `workload_type_io-heavy` 0.089 · `nodes` 0.080 · all carbon features combined
**< 0.01**.

**Two caveats to volunteer.**
1. These are *impurity-based*, which is known to be biased toward continuous and
   high-cardinality features. `dataset_size_mb` is continuous; the machine types are
   binary one-hots. So 0.606 is somewhat inflated relative to a **permutation
   importance**, which is the more trustworthy measure — and which I did not compute.
2. The near-zero carbon importance is not a finding about carbon. Those features have
   exactly one distinct value per region, so they are perfectly collinear with the
   region one-hot and carry zero independent information. It's arithmetic, not insight.

---

# FAMILY 8 — Corpus descriptive statistics

| Metric | Value |
|---|---|
| Total measured runs | **1,811** (AWS 1,011 · Azure 800) |
| Unique configurations (groups) | **689** |
| Configurations run more than once | 439 — so **250 were run only once** |
| Runs per configuration | min 1 · median 2 · max 12 |
| Scenarios (workload × size) | 21 |
| Candidates per scenario | mean **32.8**, max 36 |
| Runtime min / median / max | 0.271 / **1.272** / 13.03 minutes |
| Runtime mean ± SD | 1.806 ± 1.583 min |
| Runtime skew / kurtosis | **2.573 / 9.263** (heavily right-tailed) |
| Median cost | AWS $0.0139 · Azure $0.0075 |
| Design matrix after one-hot | 1,811 × **27** |

---

# FAMILY 9 — Qualitative evaluation

**10 participants** — 5 Cloud/DevOps/SRE, 3 Software Engineers, 2 Data Engineers.
All Likert medians at Agree or Strongly Agree. All ten reported the recommendation met
the SLA they specified. **Adoption intent median 9/10, but bimodal — seven scored 9 and
one scored 1, unexplained.**

Treat this as corroborative, never inferential: convenience sample, unblinded,
evaluated in the developer's presence. The bimodality is more interesting than the
median — a single strong dissent points at something the design missed, and the
instrument failed to capture why.

---

# ⚠️ ONE METRIC TO HANDLE CAREFULLY

`recommendation_quality_summary.csv` reports **mean carbon regret 53.7%** and **mean
runtime regret 33.8%** at the medium SLA. **Do not put these on a slide without
understanding them**, and here is why.

`evaluate_recommendations.py` uses a *simplified* emissions proxy:
```
emissions ≈ (runtime / 60) × carbon_intensity        # power draw and PUE omitted
```
The docstring justifies this as "a ratio within one scenario", but that reasoning only
holds if the omitted terms are constant across candidates — and **`power_W` varies by
machine type, so it does not cancel.**

I checked this directly. **The proxy identifies a different "greenest" configuration
than the full formula in 21 of 21 scenarios.** Concretely, for cpu-heavy at 1024 MB:

| Criterion | Winner |
|---|---|
| Cheapest | Azure Central India `Standard_D2as_v4` ×2 |
| Greenest by the **full** formula | Azure Central India `Standard_D2as_v4` ×2 |
| Greenest by the **proxy** | Azure Southeast Asia `Standard_D4s_v3` ×4 |

Because the proxy drops power draw and node count, it effectively just picks the
*fastest* run in the lowest-intensity region.

**What this means for you.** The 53.7% carbon regret is measured against a definition
of "greenest" that contradicts your headline finding. It is not evidence against
cheapest-is-greenest — the two files simply define emissions differently.

**How to handle it.** Don't quote carbon regret in the presentation; quote cost regret
and SLA violation, which are unaffected. If asked in the viva, the answer is: *"Those
two files use different emissions definitions. The evaluation script uses a
runtime-only proxy on the assumption that the omitted terms cancel within a scenario,
which is wrong because power draw varies by machine type. The headline carbon finding
comes from `carbon_analysis.py`, which uses the full formula including power draw, node
count and PUE. The evaluation script should be corrected to use the same formula — it's
a one-line change to `emissions_gco2eq()`."*

Owning this before it's found is worth far more than hoping nobody reads that file.

---

# THE SHORTLIST FOR A 20-MINUTE TALK

Eight numbers. Say each once, slowly.

| # | Metric | Value | Slide |
|---|---|---|---|
| 1 | Measured runs | **1,811** | 1 |
| 2 | Repeated configurations / median CV | **439 / 4.15%** | 6 |
| 3 | Runtime R² (grouped CV) | **0.889 ± 0.055** | 10 |
| 4 | Runtime MAE | **0.270 min ≈ 16 s** | 10 |
| 5 | Significance vs simpler models | **p = 0.0016 / p = 0.0001** | 10 |
| 6 | Top-1 accuracy (medium SLA) | **0.905** vs 0.810 baseline | 11 |
| 7 | SLA violation rate | **0.095** vs 0.143 — and **0.000** at loose | 11 |
| 8 | Per-run emissions reversal | **0.346 vs 0.448** gCO₂eq | 12 |

**Hold in reserve, for questions only:** RMSE/MAE ratio 1.8×, Cohen's d 0.73,
Pareto front 2.05, watts-per-vCPU 1.08 vs 2.30–2.72, the 43%/38%/39% node trade-off,
689 unique configurations of which 250 are singletons.

**Do not volunteer:** carbon regret and runtime regret, for the reason above.
