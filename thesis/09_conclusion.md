# 9 Conclusion and Future Work

## 9.1 Challenges Faced

Cloud resource availability was the most persistent constraint. Azure quotas were capped at 32 vCPUs in Central India and 10 in Southeast Asia, with Dsv5 and Dasv5 carrying zero quota in both regions, forcing the benchmark matrix to be reduced mid-campaign — the direct cause of the unequal AWS and Azure sample sizes. Azure Databricks also proved impractical under a limited-credit account and was replaced with self-managed Spark on Ubuntu 22.04 virtual machines, which meant building the entire provisioning layer from scratch.

Two data problems proved consequential. AWS records carry no execution timestamp, so their carbon features fall back to a region-wide all-time mean while Azure records are date-matched; the `carbon_feature_source` column records which path each row took. Repeatability was also uneven: across 439 repeated configurations the median coefficient of variation in runtime was 4.15% but the maximum reached 84.45%, most plausibly from shared-tenancy variability, which sets a floor on the accuracy any model built on this data can achieve.

## 9.2 Achievement of Learning Outcomes

The project required formulating a research problem independently, appraising prior work to establish a defensible gap, and designing an artefact addressing it under real constraints. Chapters 1 and 2 demonstrate problem definition and critical synthesis; Chapters 3 to 6 requirements engineering, design justification and implementation; Chapters 7 and 8 evaluation against criteria fixed in advance rather than selected retrospectively.

Two outcomes were tested most severely: defending engineering decisions under uncertainty, as in the Databricks-to-IaaS reversal; and reporting inconvenient results honestly, since Section 8.1 records both that the selected model's advantage over a simple heuristic is narrower than expected and that the two best models are not statistically separable.

## 9.3 Relevance of Taught Modules

The mapping below is indicative; exact module titles should be substituted from the programme specification before submission.

| Module area | Contribution to the project |
|---|---|
| Big Data Analytics / Distributed Processing | Spark execution model and the CPU-, memory- and I/O-bound distinction defining the three workload classes |
| Machine Learning / Data Mining | Regression model families, cross-validation design, and group-aware splitting to prevent leakage from repeated configurations |
| Research Methods | Research Onion framework, hypothesis framing, and the statistical testing in Section 8.1 |
| Software Engineering / Systems Analysis | Stakeholder and use case modelling, MoSCoW prioritisation, requirements traceability |
| Cloud Computing / Infrastructure | Provider service models, pricing structures and regional deployment considerations |
| Professional and Ethical Issues in Computing | The LEPSI evaluation in Section 8.10, particularly the treatment of modelled carbon figures |

Research Methods proved the most load-bearing: defining evaluation criteria before generating results removed the temptation to select the metric that flattered the artefact.

## 9.4 New Skills and Knowledge Gained

Cloud infrastructure automation at scale was the largest gain. Building a resumable, idempotent harness that provisions virtual machines, injects configuration through cloud-init, executes a workload matrix and retries failures without duplicating work is a different exercise from launching a cluster manually.

The second was empirical rigour in systems measurement — recognising that repeated runs of an identical configuration must never straddle a train-test boundary, and implementing grouped cross-validation accordingly. The third was carbon accounting methodology: deriving per-instance power draw from published Cloud Carbon Footprint coefficients, mapping instance families to processor microarchitectures, and learning where that modelling chain stops being trustworthy.

## 9.5 Contribution to the Body of Knowledge (BoK)

### 9.5.1 Technical Contribution

The principal technical contribution is a working multi-cloud framework that predicts runtime and cost for a Spark workload and returns a ranked set of configurations under a user-specified SLA deadline. Three properties distinguish it from provider pricing calculators and the single-provider tools reviewed in Chapter 2: it scores AWS EMR and self-managed Azure Spark within one unified model rather than through separate estimates; sustainability is a first-class objective, with emissions computed per run; and it requires **zero new benchmark runs at inference time**, scoring all candidates — a mean of 32.8 per scenario — from the trained model alone.

### 9.5.2 Research Contribution

Three empirical results are contributed.

On predictive feasibility, grouped five-fold cross-validation over 1,811 benchmark records gave a random forest runtime R² of 0.889 ± 0.056 and cost R² of 0.890 ± 0.034, against 0.683 ± 0.031 and 0.720 ± 0.023 for linear regression. Runtime and cost are therefore predictable to a useful degree, but the relationship is materially non-linear — a qualification of RQ2 a linear baseline alone would have obscured.

On recommendation quality, evaluated leave-one-scenario-out across 21 scenarios, the recommender achieved top-1 accuracy of 0.81, 0.90 and 0.95 at tight, medium and loose SLA deadlines, with mean cost regret of 16.6%, −0.4% and 1.1%, against a random baseline that never selected the optimum. A nearest-dataset-size heuristic, however, reaches 0.76 to 0.86 top-1 accuracy at comparable regret, so the model's defensible advantage is a lower SLA violation rate (0.095 against 0.143 at medium tightness), not cheaper recommendations.

The carbon result is the most novel. In all 21 scenarios the cheapest configuration was also the greenest. Azure Central India carries a grid a third dirtier than Singapore's (643 against 481 gCO₂eq/kWh) yet produced lower per-run emissions (0.346 against 0.448 gCO₂eq), because the AMD EPYC-based `Standard_D2as_v4` draws 1.08 W per vCPU against 2.30 to 2.72 W for the Intel alternatives. **Processor efficiency dominates grid cleanliness at this workload scale.** This answers RQ3 and validates computing emissions per run rather than comparing regional intensities, which would have recommended Singapore in every case and would have been wrong.

### 9.5.3 Practical Contribution

Two reusable artefacts were produced: an empirical corpus of 1,811 cleaned Spark execution records spanning two providers, four regions, twelve machine types, three workload classes and seven dataset sizes from 10 MB to 5 GB, where comparable published corpora are typically single-provider; and the benchmark automation suite, including a power-table generator that derives per-instance draw from published coefficients with a recorded provenance chain, allowing the carbon assumptions to be audited or re-derived.

## 9.6 Limitations

### 9.6.1 Technical Limitations

The SLA deadline is applied as a hard filter on a point estimate of predicted runtime, with no representation of uncertainty — the mechanism behind the residual SLA violation rate of 0.095 at medium tightness.

The carbon figures are modelled estimates, not measurements. Power draw is computed at a fixed 50% vCPU utilisation rather than measured utilisation; the `c6i` and `m6i` instances are Ice Lake, for which Cloud Carbon Footprint publishes no coefficient, so Cascade Lake was substituted, overstating their draw; and embodied manufacturing carbon is excluded entirely. Pricing and carbon data are static snapshots rather than live feeds. Feature importance also shows dataset size dominating both targets (0.626 for runtime, 0.558 for cost) while carbon features contribute under 0.01, so the sustainability variables inform the ranking stage far more than the prediction stage.

### 9.6.2 Operational Limitations

The design was bounded by quota and budget rather than scientific preference: two regions per provider, twelve machine types, cluster sizes of two and four nodes, and datasets no larger than 5 GB — an order of magnitude below production workloads. Sample sizes are unequal (roughly 1,011 AWS records against approximately 800 Azure), and all input data is synthetic, reproducing each workload class's resource-usage profile without the data skew of real datasets. The framework remains a research prototype, untested under concurrent multi-user load.

### 9.6.3 Methodological Limitations

The evaluation protocol is leave-one-scenario-out, where a scenario is a workload type paired with a dataset size. It measures generalisation to an unbenchmarked *configuration*, not to a previously unseen *workload type*; no claim of cross-workload generalisation is supported.

With 21 scenarios, one scenario represents 4.8 percentage points of top-1 accuracy, so differences between the stronger methods rest on small absolute counts. Paired t-tests on cross-validation fold errors found no significant difference between random forest and gradient boosting (p = 0.185 for runtime MAE, p = 0.107 for cost MAE), and on the held-out split gradient boosting was marginally ahead (average R² 0.908 against 0.896). Random forest was selected on cross-validated stability, but its superiority is not statistically supported. Finally, the qualitative evaluation in Section 8.2 was constrained in sample size and so supplements rather than corroborates the quantitative results.

## 9.7 Future Enhancements

### 9.7.1 Workload Fingerprinting for Unseen Workload Types

The clearest extension removes the dependence on pre-characterised workload classes. Rather than requiring the user to declare a workload as CPU-, memory- or I/O-heavy, the framework could derive a fingerprint from early-runtime Spark event log metrics — CPU utilisation, garbage collection time, shuffle volumes, I/O wait and task duration variance — and recommend a configuration for a workload type absent from training entirely, validated leave-one-workload-out. This addresses the cold-start limitation CherryPick and PARIS also leave open, and was not attempted here because Spark event logging was not enabled during the benchmark campaign.

### 9.7.2 Uncertainty-Aware SLA Filtering

Replacing the point-estimate filter with a prediction interval, via quantile regression or conformal prediction, would let the recommender reason about the probability of meeting a deadline, and allow spot-priced configurations to be surfaced safely wherever predicted runtime leaves sufficient slack.

### 9.7.3 Expanded Benchmark Coverage

Extending the corpus to datasets well beyond 5 GB, to memory-optimised and GPU-accelerated instance families, and to workload classes such as graph processing would test whether the observed scaling relationships hold outside the benchmarked range.

### 9.7.4 Live Pricing and Carbon-Aware Temporal Scheduling

Live pricing APIs and streaming grid intensity feeds would make recommendations current rather than historical, and enable a new capability: recommending *when* to run a deferrable job, not only where.

### 9.7.5 Extension to Additional Providers and Regions

Adding Google Cloud Dataproc and a wider set of regions would test whether the unified model generalises to a third provider, and broaden the spread over which the processor-efficiency-versus-grid-cleanliness trade-off can be examined.

### 9.7.6 Deployment as an Integrated Service

Exposing the recommender through an API integrated with job submission pipelines, with periodic retraining as records accumulate, would move the artefact from prototype toward an operational tool that improves as it is used.

## 9.8 Conclusion

This research asked whether cloud infrastructure selection for Apache Spark workloads could be automated in a way that jointly respects cost, runtime, SLA commitments and environmental impact across more than one provider. Chapter 2 established that existing work addresses these objectives largely in isolation, and that no reviewed system or commercial tool offered cross-provider carbon-aware configuration recommendation.

The framework answers that question affirmatively, within defined boundaries. Benchmarking 1,811 Spark executions established that runtime and cost are predictable from workload and configuration descriptors, with a random forest reaching R² of 0.889 and 0.890 respectively. The recommender built on those predictions selects the optimal configuration in 90% to 95% of unseen scenarios at medium and loose deadlines, with mean cost regret at or near zero, and requires no new benchmark runs for a scenario it has never encountered. The sustainability finding is the more novel: computing emissions per run showed that processor efficiency outweighs grid cleanliness at this scale, and that in all 21 scenarios the cheapest configuration was also the greenest, so cost and carbon proved aligned rather than in tension.

The boundaries are real — the framework generalises to unbenchmarked configurations, not unseen workload types; its carbon figures are modelled, not measured; and its advantage over a simple size-matching heuristic lies in SLA reliability rather than cost. Within them the contribution stands: a working, evaluated framework treating cost, time and carbon as a single joint decision across two cloud providers, with an empirical corpus and an auditable carbon-modelling chain that others can extend.
