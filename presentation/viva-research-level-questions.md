# Research-level viva questions — your project

Built by mapping the question *patterns* your friends were asked onto this project.
These are not technical attacks. They check that you made the decisions yourself and
can justify them in plain language. Answer in 3–5 sentences, then stop.

---

## The mapping

| What your friend was asked | The underlying pattern | Your version of it |
|---|---|---|
| "How did you make the gold standard?" | How did you build the thing you score against? | **How did you build your ground truth?** |
| "Why did you use FAIS normalisation?" | Justify one specific normalisation choice | **Why ratio-to-best rather than min–max?** |
| "How was the gazetteer used?" | How did you use an external lookup resource? | **How did you use the power, price and zone tables?** |
| "How does agent selection support downstream decision-making?" | How does component X feed the final decision? | **How does runtime prediction support the carbon decision?** |
| "How does explanation generation work in the explainer agent?" | How does your system explain itself? | **How is `recommendation_reason` generated?** |
| "What transfer learning technique was used for optimisation?" | What tuning did you apply, and what does it transfer to? | **What hyperparameter tuning did you do?** (none) |
| "What's the domain contribution to big data analytics?" | So what, for the field? | **What's your contribution to big data / cloud?** |
| "What would you do differently?" | Reflection | Same question |

**The meta-lesson from your friend's first question** — they asked about the gold standard
because he *mentioned it verbally* and it was not on a slide. Anything you say out loud is
fair game, and unslided claims attract more scrutiny than slided ones, not less. Do not
improvise claims during the talk that you have not prepared to defend.

---

## 1. How did you build your ground truth?

`build_ground_truth()` in `ml/evaluate_recommendations.py`.

I group every measured run by scenario (workload type × dataset size), configuration
(cloud, region, machine type, nodes) and electricity zone, then take the **mean** runtime
and **mean** cost across repeated runs of that configuration. Each row also keeps a `runs`
column recording how many observations backed that mean.

"The optimum" for a scenario at a given SLA level is then defined as: among configurations
whose **measured** runtime satisfies the deadline, the one with the lowest measured cost.
That is what every method — mine and all four baselines — is scored against.

For carbon regret the ground truth uses a deliberately simplified proxy,
`(runtime / 60) × carbon_intensity`, which omits power draw and PUE. That is correct here
because carbon regret is a *ratio between candidates within one scenario*, so any constant
factor cancels. Absolute emissions figures come from `ml/carbon_analysis.py`, which uses the
full formula.

**Own this:** averaging collapses variance. A configuration with an 84% coefficient of
variation is represented by its mean as though it were reliable. The `runs` column preserves
the evidence count, but nothing downstream uses it.

---

## 2. Why ratio-to-best rather than min–max normalisation?

Both are in the code — `_min_max()` and `_ratio_to_best()` in `ml/recommendation_engine.py`.
The single-objective goals use min–max; **Balanced** uses ratio-to-best.

Min–max maps a criterion onto [0,1] using the observed spread of the candidate set. The
problem is that the spread is set by candidates that never realistically compete. In the
demonstration scenario one large multi-node AWS configuration stretched the cost range, so a
38.2% cost difference between the two leading candidates normalised to 0.021, while a 43.5%
runtime difference normalised to 0.139 — runtime carried **5.7× the influence of cost**
despite both being weighted 0.35.

Ratio-to-best instead expresses each value as a proportional gap from the best candidate on
that criterion: 0.0 means best, 0.38 means 38% worse than the best available. It is
independent of the spread and independent of units, so a weight of 0.35 actually behaves
like 0.35.

There is one guard: if the best value is non-positive or non-finite you cannot divide by it,
so the function falls back to min–max.

**Own this:** for the pure Cost and Runtime modes min–max is harmless, because it is a
monotonic transform and the ranking is unchanged. It only bites where two normalised terms
are combined — which is the Carbon mode (emissions + renewable penalty) and Balanced. Using
ratio-to-best throughout would be the more consistent construction.

---

## 3. How did you use the external lookup tables?

Three of them, and this is the closest analogue to a gazetteer.

**`Carbon_dataset/zones.py`** — a controlled mapping from a cloud region to an external
authority's identifier: (cloud, region) → Electricity Maps zone. This is genuinely
gazetteer-like. Two regions can share one zone: AWS `ap-southeast-1` and Azure Southeast Asia
both resolve to `SG`, which is why `carbon_collect.py` caches per zone and fetches it once.

**`config/instance_power_draw.csv`** — machine type → watts, built by
`scripts/build_power_table.py` from published Cloud Carbon Footprint coefficients at a 50%
vCPU utilisation assumption. Every row carries a `source` string recording its provenance
(microarchitecture, processor model, and whether a substitution was made). Joined on
machine type in both `carbon_analysis.py` and the engine's `_power_w()`.

**`config/instance_prices.csv`** and `cloud_prices/*.csv` — instance type → hourly price,
fetched once from the AWS Pricing API and the Azure Retail Prices API and snapshotted with a
fetch date, so the experiment reproduces exactly even after providers change prices.

There is a documented fallback chain for power: published table → infer vCPU count from the
machine-type name and apply 12 W/vCPU → a 60 W default. The `warnings` array in
`carbon_analysis_summary.json` is empty, which confirms no reported figure used a fallback.

---

## 4. How does the prediction support the downstream decision?

This is the architectural question and it is the one worth rehearsing hardest.

Emissions are never measured at decision time — they are **derived from the prediction**.
The chain in `_rank_configurations()` runs in this order:

1. `model.predict()` → runtime and cost for every candidate
2. clip to physically plausible values
3. join power draw and PUE from the lookup tables
4. `emissions = (power_W × nodes / 1000) × (runtime / 60) × intensity × PUE`
5. `sla_valid = predicted_runtime <= deadline` → filter
6. score by the selected objective
7. attach a reason, sort, rank

So prediction sits upstream of everything. You cannot answer the carbon question without
first answering the performance question, because runtime is an input to the emissions
formula. And the SLA filter also runs on predicted runtime, so the prediction gates the
feasible set before any scoring happens at all.

**That is the argument for one integrated framework** rather than a carbon tool bolted onto
a separate performance tool — the two questions are not separable.

---

## 5. How does your system explain its recommendations?

`_build_reason()` in `ml/recommendation_engine.py`. Every returned row carries a
`recommendation_reason` column, composed from two things: the optimisation goal the user
selected, and whether the SLA fallback fired.

There are four goal templates ("ranked by lowest predicted cost", "ranked by fastest
predicted runtime", "ranked by lowest predicted emissions for this job and higher renewable
percentage", "ranked by best trade-off between runtime, cost, carbon, and renewable
energy"), and a prefix — `"No configuration satisfied the SLA; "` — is prepended to *every*
row when nothing met the deadline, so a constraint violation is surfaced rather than hidden.

**Be precise about what this is: template-based, not model-derived.** It states which
objective produced the ranking. It does not state which feature drove *this particular
candidate's* score, or why candidate 1 beat candidate 2.

A stronger version would surface per-candidate attribution — at minimum the four normalised
component scores that fed the Euclidean distance, so the user can see the trade-off that was
struck; ideally SHAP values on the prediction itself. Global feature importances exist in
`feature_importance.json`, but they are not per-recommendation.

This is also a good answer to "what would you do differently."

---

## 6. What optimisation or tuning technique did you use?

**Effectively none, and say so plainly rather than dressing it up.**

Random Forest uses 250 trees, `min_samples_leaf=1` and a fixed seed. Gradient Boosting and
Decision Tree use scikit-learn defaults with a fixed seed. There is no `GridSearchCV`, no
`RandomizedSearchCV`, and no Bayesian optimisation anywhere in the pipeline.

The consequence is that my comparison is between **default-configured algorithms**, not
tuned ones. The p = 0.177 result separating Random Forest from Gradient Boosting should be
read in that light — a properly tuned Gradient Boosting might well beat an untuned Random
Forest. Given the two were statistically inseparable at defaults, tuning is the obvious next
step and it is cheap.

**If they push on "transfer":** what the model transfers to is an unbenchmarked *scenario* —
a (workload type × dataset size) combination it has not seen — evaluated by
leave-one-scenario-out. It does **not** transfer to an unseen workload type, and it does not
transfer to an unseen instance type: `machine_type` is an opaque one-hot category, so a novel
instance encodes as all-zeros under `handle_unknown="ignore"` and predicts near the
conditional mean. Making that work would require learning instance *characteristics* —
vCPUs, memory, clock, family — as features instead.

---

## 7. What is your contribution to big data analytics?

Three, in order of strength.

**Methodological.** Per-run emissions accounting and grid-intensity ranking give opposite
answers. Intensity ranking selects Singapore in all 21 scenarios; per-run accounting selects
Azure Central India, 0.346 against 0.448 gCO₂eq. Any carbon-aware scheduler that ranks
regions by grid intensity — which is the common approach in that literature — can therefore
be systematically wrong about which deployment actually emits less.

**Empirical.** A corpus of 1,811 measured multi-cloud Spark executions with cost and carbon
attached. The practical payoff is zero-benchmark-run inference: someone facing this decision
can get advice without running their own profiling campaign, which is exactly what CherryPick
and Ernest still require.

**Protocol.** Leakage-controlled evaluation. Grouping the split on configuration is not
standard practice in this literature, and without it a corpus containing repeated runs
produces an inflated R² that measures memorisation rather than generalisation.

**Specifically for big data:** the finding that **node-hours is the shared driver of both
cost and carbon**. Doubling from 2 to 4 nodes cuts runtime by 43% but raises cost 38% and
emissions 39%, because the runtime saving is sublinear while node-hours are linear. That is
directly actionable for anyone sizing a Spark cluster, and it is why cost and carbon turned
out to be aligned rather than in tension.

---

## 8. What would you do differently if you started over?

Five, ordered by how much they would change the result.

1. **Enable Spark event logging at cluster launch on EMR.** It is off by default and has to
   be configured when the cluster is created. Those logs are the enabling data for workload
   fingerprinting, which would remove the requirement for the user to self-classify their
   job. By the time I understood that, the campaign was complete and the budget spent. That
   is the single most consequential planning failure in the project.
2. **Define SLA deadlines independently of the measured data.** Percentiles of the measured
   runtime distribution mean the constraint is derived from the same data I score against.
3. **Predict runtime only, and compute cost in closed form.** Cost is price × nodes ×
   runtime, all known at inference, so the second model head is largely redundant.
4. **Complete the resource-utilisation collection.** `cpu_avg_pct` is null for about 56% of
   rows and `memory_avg_pct` for all of them, which forces a flat 50% utilisation assumption
   in the emissions calculation.
5. **Run a weight sensitivity sweep** on 0.35 / 0.35 / 0.20 / 0.10 — sweep the weights and
   report how often the top-1 recommendation changes. Half a day of compute, and the cheapest
   credibility improvement available to this work.

---

## Other basic questions in the same spirit

**Why Apache Spark rather than Dask or Flink?**
Spark is the de facto standard for batch analytics on both providers, with a managed service
on AWS (EMR) and first-class support on Azure, so the comparison reflects what practitioners
actually run. Flink is stream-first; Dask has no equivalent managed offering on either
provider, which would have made the multi-cloud comparison harder, not easier.

**Why those three workload classes?**
They span the three resource bottlenecks a distributed job can hit — compute, memory and
I/O — which is the standard taxonomy in benchmarking literature. A configuration that is
optimal for one is not necessarily optimal for another, and that is precisely the variation
the recommender needs in order to be useful.

**Did you verify the workloads really are CPU-, memory- and I/O-bound?**
By construction rather than by measurement. cpu-heavy uses narrow transforms with eight
chained transcendental operations per row and one shuffle; memory-heavy caches two frames and
joins on a 50,000-key space; io-heavy writes Parquet, re-reads it and writes again.
I did not verify empirically against profiling counters, because `cpu_avg_pct` is missing for
56% of rows. Demonstrating the three classes are separable on measured resource profiles is
something the fingerprinting extension would have to establish first.

**Why only 2 and 4 nodes?**
Azure quota, and it is per (region, VM family) rather than a single cap — 10 vCPUs for the
DASv4 family in southeastasia, for example. `config.env` carries the cap table and the runner
skips combinations that cannot physically fit. Two levels still isolate the effect of
horizontal scaling, which is the factor I needed.

**Why on-demand pricing rather than spot?**
Because the SLA guarantee is the point. Spot instances can be reclaimed mid-job, which makes
any deadline commitment unsound. Spot becomes safe only once the recommender reasons about
slack — which is the uncertainty-aware extension: surface spot only where the predicted
runtime leaves enough headroom that a reclaim-and-restart still fits.

**Why MAE, RMSE and R² rather than one metric?**
They answer different questions. MAE is average error in the target's own units — about 16
seconds — which is what a user cares about. RMSE squares errors first, so RMSE much larger
than MAE indicates a tail of large misses rather than uniform error; mine are 0.477 against
0.268, roughly 1.8×. R² is scale-free and says how much variance is explained relative to
predicting the mean, which is what makes the linear-versus-ensemble comparison interpretable.

**Why leave-one-scenario-out rather than a random split?**
Because the question the system has to answer is "what should I use for a workload and size I
have not benchmarked?" A random split would leave rows from the same scenario in both train
and test, which answers an easier question than the one a user actually asks.

**Why those four baselines?**
They bracket the space of what a practitioner would plausibly do without a model.
`historical_mean` is "use the average of what we've seen"; `nearest_size` is "look up the
closest job we ran"; `largest_cluster` is over-provisioning, which is the common real-world
default; `random` establishes the floor. `largest_cluster` and `random` deliberately reuse
`historical_mean`'s predictions, because they differ only in the *selection rule*, not in how
they estimate runtime — that isolates the contribution of the ranking logic.

**Why Electricity Maps?**
It publishes zone-level grid carbon intensity and renewable share with daily granularity and
a documented methodology, over a historical range rather than only live values, which is what
a reproducible experiment needs. The `zones.py` mapping is explicit and validated so the
region-to-zone assignment is auditable rather than assumed.

**What is PUE?**
Power Usage Effectiveness — total facility energy divided by IT equipment energy. A PUE of
1.15 means 15% overhead for cooling, power distribution and lighting on top of what the
servers themselves draw. It scales IT-level energy up to facility-level energy, which is what
should be multiplied by grid intensity. I use 1.15 for AWS and 1.18 for Azure, from published
sustainability reports.

**Why regional mean carbon rather than matching each run to its timestamp?**
`merge_model_dataset.py` supports both — `--carbon-basis regional_mean` and `per_run`. I used
regional mean because AWS EMR runs carry no execution timestamp, so only Azure rows could be
date-matched. Using different bases for the two providers would make them incomparable, so I
applied one basis uniformly. Every row records which path it took in `carbon_feature_source`.

**What does your system do that a cloud cost calculator doesn't?**
A calculator requires you to already know the configuration *and* how long the job will run,
and then just multiplies. Those two things are exactly what you do not know before you run
it. My system predicts the duration from the workload's characteristics, which is what makes
the cost figure — and the emissions figure — available in advance rather than afterwards.
