# Chapter 5 — Aims, Objectives and Specification

## 5.1 Aim

The aim of this project was to design, implement and critically evaluate a cost-, SLA- and
carbon-aware cluster configuration recommender for Apache Spark that selects near-optimal
configurations across two cloud providers, and to specify a workload fingerprinting layer intended to
extend that recommender to previously unseen workload types without requiring a full profiling run.

The remainder of this chapter decomposes that aim into six objectives (Section 5.2), resolves the
terms within it that are ambiguous without further definition (Section 5.3), and fixes the evaluation
criteria against which the work is assessed in Chapter 10 (Section 5.4). The guidelines for this
module note that restating the original project description does not constitute a specification;
accordingly, each objective below is given a rationale, an explicit success criterion expressed as a
measurable threshold, and a verification method identifying the evidence that settles it.

---

## 5.2 Objectives

Six objectives were defined. They are ordered by dependency rather than importance: O1 supplies the
data that O2 consumes, O2 supplies the predictive layer that O5 ranks over, and O6 evaluates the
result. O3 and O4 are independent of one another and both feed O5.

### O1 — Construct an empirical benchmark corpus of Spark runs spanning two providers and four regions

**Description.** A benchmark harness was to be built that provisions Spark clusters, executes
controlled workloads against datasets of varying size, and records runtime, cost and resource-usage
telemetry for each run. The harness was required to cover both AWS EMR and Azure IaaS, and to span a
matrix of workload types, dataset sizes, instance types, node counts and regions. Repetitions were
required so that run-to-run variance could be quantified rather than assumed away.

**Rationale.** Every downstream component depends on this corpus. The systems reviewed in Chapter 2
are evaluated predominantly on a single provider — CherryPick and Arrow on AWS, Ernest on EC2
(Alipourfard *et al.*, 2017; Venkataraman *et al.*, 2016) — which leaves open whether a configuration
model transfers across providers whose instance families, pricing structures and virtualisation
overheads differ. A two-provider corpus is a precondition for asking that question at all.

**Success criterion.** A cleaned, schema-validated corpus of at least 1,500 runs, covering both
providers, at least three workload types, at least five dataset sizes, and at least two node counts,
with every run traceable to the configuration that produced it.

**Verification method.** Row counts and coverage cross-tabulations computed over
`data/performance/cleaned_data/cleaned_dataset.csv` and reported in Chapter 11, with the full matrix
tabulated in Appendix C.

**Status note.** The corpus as assembled contains approximately 1,011 AWS rows and approximately 800
Azure rows. The provider split is unequal, and the coverage of the Azure arm was reduced mid-campaign
by vCPU quota ceilings (Central India capped at 32 vCPUs, Southeast Asia at 10, with the Dsv5 and
Dasv5 families unavailable in both). This is reported as a constraint on external validity in Chapters
10 and 11 rather than concealed.

### O2 — Develop and validate predictive models for runtime and cost under configuration-grouped cross-validation

**Description.** Supervised regression models were to be trained to predict wall-clock runtime and
monetary cost for a candidate configuration, given dataset size, workload type, instance type, node
count, region and provider. Several model families were to be compared rather than a single family
adopted by assertion.

**Rationale.** The recommender cannot rank configurations it has not observed unless it can predict
their behaviour. The choice of validation protocol matters more here than the choice of model family:
because the corpus contains repeated runs of identical configurations, a naive random split would place
near-duplicate rows on both sides of the train/test boundary and inflate the reported score. Splitting
grouped by configuration — that is, by the tuple (cloud, region, dataset size, workload type, machine
type, node count) — is therefore a deliberate methodological commitment, argued in Section 7.3.3, and
not an implementation detail.

**Success criterion.** Under grouped five-fold cross-validation, the best-performing model was
required to achieve a coefficient of determination of at least 0.85 for both runtime and cost, with the
standard deviation across folds not exceeding 0.10 for either target. A minimum of four model families
was to be compared.

**Verification method.** Cross-validation metrics recorded in `data/models/cross_validation_metrics.json`
and holdout metrics in `data/models/model_comparison.json`, reported in Section 11.1.

**Status note.** Four families were compared. Random forest performed best, achieving runtime
R² 0.893 ± 0.045 and cost R² 0.894 ± 0.027 under grouped five-fold cross-validation, with gradient
boosting close behind (0.885 ± 0.038 and 0.874 ± 0.035), decision tree at 0.834 ± 0.067 and 0.820 ±
0.057, and linear regression weakest at 0.683 ± 0.028 and 0.720 ± 0.020. The criterion is therefore met
on both targets and on both parts of the stability requirement.

### O3 — Design a workload fingerprint representation supporting cross-workload generalisation

**Description.** A feature representation was to be specified that characterises a workload from
early-runtime resource-usage telemetry rather than from a completed profiling campaign. The intended
feature vector comprises CPU utilisation, garbage-collection time, shuffle read and write volumes, I/O
wait, and task duration variance, extracted from Spark event logs, normalised so that a fingerprint is
comparable across cluster sizes, and truncated to an early fraction of a run.

**Rationale.** This is the intended novel contribution of the project. The systems surveyed in Chapter
2 either require a full profiling run for each new workload — the search-based approach of CherryPick
and the analytical modelling of Ernest both do — or amortise profiling across a pool of workloads
already seen, as Micky does, or transfer using a characterisation obtained from dedicated benchmark
probes, as PARIS does (Yadwadkar *et al.*, 2017). None predicts a good configuration for a workload
type absent from training using only telemetry emitted incidentally by the first moments of a run. If
early-runtime signatures do carry the information needed to place an unseen workload near a known one,
the profiling cost that dominates the practical adoption of these systems can largely be avoided.

**Success criterion.** This objective was specified in two stages, because its empirical component is
contingent on data availability:

- *Design stage (unconditional).* A complete, implementable specification of the fingerprint feature
  vector, the event-log parse strategy, the normalisation scheme and the truncation fraction, at a level
  of detail sufficient for a third party to implement it.
- *Validation stage (conditional).* A leave-one-workload-out protocol — train on two of the three
  workload types, test on the third, rotating the held-out type — showing configuration-ranking quality
  on the held-out type superior to a no-fingerprint baseline.

**Verification method.** The design stage is verified by the presence of Section 8.4 and the schema
in Appendix B. The validation stage is verified by per-held-out-workload results in Section 11.2 and
the ablation study in Section 11.4.

**Status note — material and unresolved at the time of writing.** The 234 original EMR runs were
collected without `spark.eventLog.enabled` set, so no event logs were emitted for them, and no
fingerprint extraction code exists in the repository. Whether the validation stage can be attempted at
all depends on whether archived event logs exist under
`s3://cost-aware-spark-research-manoj-2026/emr-logs/`; **this check has not yet been performed**
`[TODO: resolve S3 event-log check; update this paragraph, THESIS_CONTEXT.md line 55, and Sections 10.1, 11.2 and 13.4 accordingly]`.
Until it is resolved, O3 is claimed as *specified and designed* only. The design stage is treated as
independently creditable — a specification is a legitimate contribution — but no result is claimed for
the validation stage, and Chapter 11 reports no leave-one-workload-out figures unless they were
actually produced. Overstating this would be an integrity failure of exactly the kind Section 12.1
commits the project to avoiding.

### O4 — Formulate a cost model and a per-run carbon model

**Description.** Two quantitative models were required: a monetary cost model mapping a configuration
and a predicted runtime to a price, and a carbon model estimating operational emissions for the same
run.

**Rationale.** Cost is the objective practitioners already optimise; carbon is the objective the
literature on cloud configuration tuning has largely omitted. Treating carbon per-run rather than
per-region is what makes the second model informative: a purely regional ranking of grid carbon
intensity would resolve to the same answer for every query, rendering the carbon dimension decorative.
Computing emissions as runtime × power draw × grid carbon intensity × power usage effectiveness means a
configuration can win on carbon by finishing sooner or by drawing less power, not merely by being
located in a cleaner grid.

**Success criterion.** On-demand pricing collected for every instance type in the candidate set across
all four target regions, with spot pricing retained strictly as a sensitivity layer and never as the
basis of a primary recommendation. Carbon estimates computed per run from documented published
constants, with the provenance of every constant cited and the fallback path for rows lacking a
timestamp recorded explicitly in the data.

**Verification method.** Pricing coverage tables and the carbon model derivation in Sections 8.6 and
8.7; the `carbon_feature_source` column demonstrating per-row provenance; sensitivity analysis in
Section 11.9.

**Status note.** On-demand pricing was collected (24 AWS rows, 18 Azure rows across the target
regions). Carbon intensity and renewable percentage came from Electricity Maps, per-instance power draw
from Boavizta and Cloud Carbon Footprint, and PUE constants of approximately 1.15 for AWS and 1.18 for
Azure. Two caveats are carried forward as limitations rather than resolved: the AWS rows carry no
timestamp and therefore fall back to a region all-time mean intensity, whereas Azure rows receive a
date-matched reading; and the carbon dataset is a static snapshot covering late 2025 to mid 2026, not a
live signal.

### O5 — Implement a multi-objective recommender returning a Pareto front under an SLA deadline constraint

**Description.** The recommender takes a dataset size, a workload type and an SLA deadline, predicts
runtime, cost and carbon for every candidate configuration, eliminates those predicted to breach the
deadline, and returns a Pareto front exposing the cheapest, greenest and fastest-within-SLA options
rather than a single collapsed recommendation. A dashboard presents this front interactively.

**Rationale.** Cost, runtime and carbon conflict, and the exchange rate between them is a matter of
institutional policy, not a technical fact the recommender is entitled to decide. Collapsing three
objectives into one scalar score requires weights that would have to be invented, and inventing them
would silently embed the author's preferences in every recommendation the tool makes. Returning the
non-dominated set instead defers the trade-off to the user who owns it — a design position defended in
Section 8.8 and revisited in Section 5.3 below.

**Success criterion.** The recommender returns, for any valid query, a non-empty Pareto front in which
no returned configuration is dominated by another on all three objectives simultaneously; every returned
configuration satisfies the SLA deadline under the predicted runtime; ties are broken by a documented,
deterministic rule; and the end-to-end response is fast enough for interactive use.

**Verification method.** Unit tests over cost calculation, the carbon join, scoring and tie-break
behaviour, and schema conformance (`tests/`); recommendation-quality metrics — regret against an oracle
and SLA violation rate — in Section 11.5; measured response latency in Section 11.7.

### O6 — Critically evaluate the recommender against baselines and documented solutions

**Description.** The recommender was to be evaluated not only on raw predictive accuracy but on the
quality of the decisions it produces, against a stated baseline, with the practical cost-benefit
argument quantified rather than asserted.

**Rationale.** A high R² does not by itself establish that a recommender is useful; a model can predict
runtime well and still rank configurations badly if its errors are correlated with the ranking
dimension. The claim this project ultimately makes is economic — that a quantity of profiling cost is
avoided in exchange for a quantity of accuracy — and that claim only becomes assessable when both
quantities are measured.

**Success criterion.** Recommendation quality reported as regret against an oracle and as SLA
violation rate, not accuracy alone; comparison against the earlier non-fingerprint recommender as an
explicit baseline; an ablation study identifying which feature groups carry the transfer, conditional on
O3's validation stage being reachable; results positioned against CherryPick, Ernest and PARIS as
reported in their respective papers, with the limits of cross-paper comparison stated; and variability
reported as confidence intervals rather than point estimates.

**Verification method.** Sections 11.1 through 11.11, with limitations consolidated in Section 11.12.

### Objective summary and traceability

**Table 5.1 — Objectives, verification evidence and chapter mapping**

| ID | Objective (abbreviated) | Success criterion (abbreviated) | Verified in | Designed in |
|----|--------------------------|----------------------------------|-------------|-------------|
| O1 | Two-provider benchmark corpus | ≥1,500 cleaned runs, ≥3 workload types, ≥5 dataset sizes, ≥2 node counts | §11.1, App. C | §8.2, §9.5–9.6 |
| O2 | Runtime and cost prediction | Grouped 5-fold CV R² ≥ 0.85 both targets, fold std ≤ 0.10, ≥4 model families | §11.1 | §8.5, §9.10 |
| O3 | Workload fingerprint representation | Stage 1: complete specification. Stage 2 *(conditional)*: leave-one-workload-out beats no-fingerprint baseline | §11.2, §11.4, App. B | §8.4, §9.7 |
| O4 | Cost and per-run carbon models | On-demand pricing across all four regions; per-run carbon from cited constants with recorded provenance | §11.9 | §8.6–8.7, §9.8–9.9 |
| O5 | Pareto-front recommender under SLA | Non-empty, non-dominated, SLA-feasible front with deterministic tie-breaks | §11.5, §11.7 | §8.8–8.9, §9.11–9.12 |
| O6 | Critical evaluation | Regret and SLA violation rate reported; baseline comparison; ablation *(conditional)*; confidence intervals | §11.1–11.12 | §7.4 |

---

## 5.3 Interpretation of ambiguous objectives

Three terms in the aim carry more than one defensible reading. Each is fixed here so that Chapter 10
scores the work against a stated interpretation rather than a retrospective one.

### 5.3.1 What "optimal" means when three objectives conflict

"Optimal" has no single referent in a three-objective problem. The cheapest configuration is rarely the
fastest; the greenest is frequently neither. This project adopts **Pareto optimality** as the operative
definition: a configuration is optimal if no other candidate is at least as good on all three objectives
and strictly better on at least one. The recommender therefore returns a set, not an element.

Two consequences follow, and both are accepted deliberately. First, the recommender cannot claim to
identify *the* best configuration, and no such claim is made anywhere in this dissertation. Second, the
user must perform the final selection, which shifts a genuine cognitive burden onto them — the
mitigation is the dashboard's labelling of the front's extreme points (cheapest, greenest,
fastest-within-SLA), which covers the common cases without imposing weights.

Where a total order is unavoidable — in tie-breaking, and in computing regret against an oracle for
evaluation purposes — precedence is applied in the order given in Table 5.2. This ordering is a
convention adopted for reproducibility, not a claim about what users ought to value.

**Table 5.2 — Tie-break precedence where a total order is required**

| Precedence | Criterion | Justification |
|---|---|---|
| 1 | SLA feasibility | Hard constraint; an infeasible configuration is not a candidate at all |
| 2 | Predicted cost (ascending) | The objective practitioners are documented to optimise first |
| 3 | Predicted carbon (ascending) | Secondary objective; the project's distinguishing dimension |
| 4 | Predicted runtime (ascending) | Slack beyond the deadline has no value once the deadline is met |
| 5 | Node count, then instance type (lexicographic) | Deterministic final tie-break; ensures reproducible output |

### 5.3.2 What the SLA deadline constrains

The SLA deadline is treated as a **hard constraint on predicted runtime**, not as a soft penalty term.
A configuration whose predicted runtime exceeds the deadline is removed from the candidate set before
ranking, and cannot re-enter it by being sufficiently cheap or sufficiently clean.

This raises a question the specification must answer honestly: prediction is uncertain, so filtering on
a point estimate will admit configurations whose true runtime breaches the deadline. The project's
position is that this is a real and quantifiable failure mode rather than a modelling embarrassment,
and it is measured directly as the SLA violation rate in Section 11.5. The corresponding design
decision — that on-demand pricing rather than spot pricing forms the basis of any primary
recommendation — follows from the same reasoning: spot capacity can be reclaimed mid-run, which
introduces a runtime risk the recommender cannot bound, so spot appears only in the sensitivity analysis
of Section 11.9.

### 5.3.3 What "unseen workload type" means

A workload type is *unseen* if no run of that type appeared anywhere in the training data — including
in a different region, on a different provider, or at a different dataset size. This is the strict
reading, and it is the reading the leave-one-workload-out protocol enforces by holding out an entire
workload type rather than a sample of its runs.

The weaker reading, under which a workload is unseen merely because the specific *configuration* was
not benchmarked, is already handled by O2 and its grouped splitting protocol, and would not constitute a
contribution over the existing literature. The distinction matters because the two readings are easily
conflated in reporting, and the stronger claim is the one that would be unwarranted.

It should be stated plainly that with only three workload types available (cpu-heavy, memory-heavy,
io-heavy), the leave-one-workload-out protocol yields three folds — enough to demonstrate the principle,
not enough to establish it robustly. This is recorded as a limitation in Section 11.12 and as future
work in Section 13.4, and it is not offset by any argument made elsewhere in this dissertation.

---

## 5.4 Evaluation criteria

The criteria below were fixed before the evaluation in Chapter 11 was written, so that Chapter 10 can
score each objective against a stated threshold rather than against a standard chosen once the results
were known. Thresholds are drawn from what the corpus and the six-objective scope make attainable;
where a criterion is contingent on the unresolved fingerprint question of Section 5.2 (O3), that
contingency is marked.

**Table 5.3 — Evaluation criteria, thresholds and evidence**

| # | Criterion | Threshold | Objective | Evidence |
|---|---|---|---|---|
| EC1 | Corpus size and coverage | ≥1,500 cleaned runs across 2 providers, 4 regions, 3 workload types | O1 | §11.1, App. C |
| EC2 | Runtime prediction accuracy | Grouped 5-fold CV R² ≥ 0.85 | O2 | §11.1 |
| EC3 | Cost prediction accuracy | Grouped 5-fold CV R² ≥ 0.85 | O2 | §11.1 |
| EC4 | Model stability | Fold-wise std ≤ 0.10 on both targets | O2 | §11.1 |
| EC5 | Model family breadth | ≥4 families compared on identical splits | O2 | §11.1 |
| EC6 | Fingerprint specification completeness | Feature vector, parse strategy, normalisation and truncation all specified to implementable detail | O3 | §8.4, App. B |
| EC7 | Cross-workload generalisation *(conditional)* | Held-out-workload ranking quality exceeds no-fingerprint baseline on ≥2 of 3 folds | O3 | §11.2 |
| EC8 | Feature attribution *(conditional)* | Ablation isolates which fingerprint feature groups carry the transfer | O3 | §11.4 |
| EC9 | Pricing coverage | On-demand prices for every candidate instance type in all 4 regions | O4 | §8.6 |
| EC10 | Carbon provenance | Every constant cited; per-row source recorded in `carbon_feature_source` | O4 | §8.7, §11.9 |
| EC11 | Pareto front validity | Front non-empty and internally non-dominated for all valid queries | O5 | §11.5 |
| EC12 | SLA violation rate | Reported with confidence interval; no undeclared violations | O5 | §11.5 |
| EC13 | Recommendation latency | Interactive response for a single query | O5 | §11.7 |
| EC14 | Regret against oracle | Reported per workload type, not only in aggregate | O6 | §11.5 |
| EC15 | Baseline comparison | Quantified against the earlier non-fingerprint recommender | O6 | §11.3 |
| EC16 | Reproducibility | Pinned dependencies, seeded splits, results regenerable from committed data | O6 | §9.14, App. E |
| EC17 | Statistical reporting | Variability reported as mean ± std or confidence intervals throughout | O6 | §11.11 |

Criteria EC7 and EC8 are the only two whose satisfaction is not within the project's control at the
time of writing, both being contingent on the availability of archived Spark event logs. Should they
prove unreachable, Chapter 10 records them as *not achieved* with the cause stated, rather than
reinterpreting the criterion to fit the outcome. The guidelines for this module note that a
partially-met objective accompanied by a clear explanation is assessed more favourably than an
overclaimed one, and that principle is applied literally here.

---

## 5.5 Summary

Six objectives were specified, each with a measurable success criterion and a named source of
verifying evidence, and consolidated into seventeen evaluation criteria in Table 5.3. Four of the six
(O1, O2, O4, O5) were pursued to completion and are assessed on evidence already held; O6 depends on
them and is assessed in Chapter 11. O3, which carries the project's intended novel contribution, is
claimed at the design stage only, its empirical validation being contingent on a data availability
question that remains open. Chapter 6 translates these objectives into functional and non-functional
requirements; Chapter 10 returns to Table 5.3 and scores each criterion against the evidence produced.

---

### References cited in this chapter

Alipourfard, O., Liu, H.H., Chen, J., Venkataraman, S., Yu, M. and Zhang, M. (2017) 'CherryPick:
adaptively unearthing the best cloud configurations for big data analytics', in *Proceedings of the
14th USENIX Symposium on Networked Systems Design and Implementation (NSDI '17)*. Boston, MA, pp.
469–482.

Venkataraman, S., Yang, Z., Franklin, M., Recht, B. and Stoica, I. (2016) 'Ernest: efficient
performance prediction for large-scale advanced analytics', in *Proceedings of the 13th USENIX
Symposium on Networked Systems Design and Implementation (NSDI '16)*. Santa Clara, CA, pp. 363–378.

Yadwadkar, N.J., Hariharan, B., Gonzalez, J.E., Smith, B. and Katz, R.H. (2017) 'Selecting the best VM
across multiple public clouds: a data-driven performance modeling approach', in *Proceedings of the
2017 Symposium on Cloud Computing (SoCC '17)*. Santa Clara, CA, pp. 452–465.

> Full reference list is maintained in `thesis/14_references.md`. Entries above are reproduced here
> for drafting convenience and must be de-duplicated against that file before submission.
