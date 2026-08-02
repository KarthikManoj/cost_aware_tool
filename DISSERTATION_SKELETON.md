# MSc Dissertation Skeleton — CMM799

**Working title:** Workload Fingerprinting for Cross-Workload Generalisation in Cost- and Carbon-Aware Spark Cluster Configuration

**Target:** 100–110 pages excluding appendices | A4, 1.5 spacing, 11–12pt, numbered pages | Harvard citations

---

## Front matter (not counted in the 100–110)

| Item | Notes |
|---|---|
| Front cover | Obtain from School Office. **Must be signed** — unsigned = not accepted for assessment |
| Title page | Format per Guidelines §14.2: "MSc Project Report" / title / name / year / degree statement |
| Declaration | Verbatim text from §14.3. **Must be signed and dated** |
| Acknowledgements | ~½ page |
| Abstract | Single line spacing, ~300 words. Problem → gap → approach → headline result → contribution |
| Table of contents | Section names + start pages |
| List of figures / tables | Optional but expected at this length |

---

## Chapter 1 — Introduction and Motivation
**Target: 8–10 pages** · *Maps to required section 1*

- 1.1 Context: cloud infrastructure cost as an operational problem; Spark configuration as a search space
- 1.2 The configuration problem — combinatorial space (instance family × size × node count × region × provider)
- 1.3 Why existing auto-tuners fall short: the profiling cost problem
- 1.4 The carbon dimension — why cost-only optimisation is an incomplete objective
- 1.5 Research question and hypothesis
  > *Can early-runtime resource-usage fingerprints predict near-optimal cluster configurations for a previously unseen workload type, without a full profiling run?*
- 1.6 Contributions (state as a numbered list — markers look for this)
  1. A fingerprint feature representation extracted from Spark event logs
  2. A cross-workload generalisation model validated leave-one-workload-out
  3. A multi-objective (cost / runtime / carbon) recommender over a two-provider, four-region benchmark corpus
  4. An empirical dataset of N Spark runs across AWS EMR and Azure IaaS
- 1.7 Dissertation structure

---

## Chapter 2 — Literature Review
**Target: 18–22 pages** · *Maps to required section 2*

> You already have a draft with 18 IEEE-style references. **Convert to Harvard** (author-surname + date) — §15 of the guidelines advises Harvard for all RGU student work.

- 2.1 Review methodology — databases searched, inclusion criteria, date range
- 2.2 Cloud configuration optimisation
  - 2.2.1 Black-box / Bayesian search — **CherryPick**
  - 2.2.2 Analytical performance modelling — **Ernest**
  - 2.2.3 Collective / shared profiling — **Micky**
  - 2.2.4 Transfer via workload characterisation — **PARIS**
  - 2.2.5 Database and system parameter tuning — **OtterTune**, **Arrow**
- 2.3 **Critical synthesis table** — columns: system / approach / profiling cost / handles unseen workloads? / multi-objective? / evaluated on. *This table is where you earn the "critical" mark — end it with the explicit gap your work fills.*
- 2.4 Spark performance characterisation and event-log instrumentation
- 2.5 Cloud carbon accounting — Electricity Maps, Boavizta, Cloud Carbon Footprint, PUE methodology and its known limitations
- 2.6 Multi-objective optimisation and Pareto-front presentation in systems research
- 2.7 **Professional, social, legal and ethical issues arising from the literature** — *required by §4 to appear in the review itself, not only in Ch. 12*
- 2.8 Summary — the gap, restated as the justification for Chapters 4–9

---

## Chapter 3 — Discussion and Evaluation of Software Tools
**Target: 8–10 pages** · *Maps to required section 3*

Frame every choice as **alternatives considered → criteria → decision → consequence**. This chapter is graded on justification, not description.

- 3.1 Distributed processing: Spark vs. Flink vs. Dask
- 3.2 Managed vs. self-managed: **EMR vs. Databricks vs. standalone Spark on IaaS** — document the real decision (Databricks rejected on cost and reliability under a $100 credit account; standalone on Ubuntu 22.04 chosen for Azure)
- 3.3 ML stack: scikit-learn vs. XGBoost/LightGBM — justify given dataset size
- 3.4 Orchestration: Bash + boto3 + Azure CLI vs. Terraform/Airflow — justify the pragmatic choice
- 3.5 Interface: Streamlit vs. Flask/Dash
- 3.6 Carbon data sources: Electricity Maps vs. WattTime vs. provider-published figures
- 3.7 Summary table of the final stack with version pinning rationale

---

## Chapter 4 — Problem Analysis and Proposed Solution
**Target: 8–10 pages** · *Maps to required section 4*

- 4.1 Formal problem statement — decision variables, objective functions, SLA as a hard constraint
- 4.2 The cold-start problem for unseen workload types
- 4.3 **Analysis of alternatives** (guidelines explicitly require this): full profiling / analytical modelling / static heuristics / **fingerprint-based transfer**
- 4.4 The fingerprint hypothesis — why early-runtime resource signatures should transfer across workload types
- 4.5 Proposed architecture (high-level diagram)
- 4.6 Scope and explicit exclusions — streaming, autoscaling, spot interruption modelling, GPU instances

---

## Chapter 5 — Aims, Objectives and Specification
**Target: 6–8 pages** · *Maps to required section 5*

> Guidelines warn: reproducing the original project description is **not sufficient**. Each objective needs its own paragraph explaining what it entails and how it will be measured.

- 5.1 Aim (single sentence)
- 5.2 Objectives O1–O6, each with: description / rationale / success criterion / verification method
- 5.3 Interpretation of ambiguous objectives — e.g. what "optimal" means when three objectives conflict
- 5.4 Evaluation criteria defined up front (so Ch. 10 can be scored against them)

---

## Chapter 6 — Requirements
**Target: 6–8 pages** · *Maps to required section 6*

- 6.1 Functional requirements — FR1…FRn, tabulated, each with MoSCoW priority + source + acceptance test
- 6.2 Non-functional requirements — NFR1…NFRn covering:
  - Prediction accuracy thresholds (R², MAE)
  - Recommendation latency
  - Reproducibility (pinned dependencies, seeded splits)
  - Cost ceiling of the experimental campaign itself
  - Security — credential handling, no hardcoded secrets
  - Portability across providers
- 6.3 Requirements traceability matrix (requirement → design section → test case) — *carry this into Ch. 10*

---

## Chapter 7 — Methodology
**Target: 8–10 pages** · *Maps to required section 7*

- 7.1 Research strategy: design-science / experimental systems research
- 7.2 Development process — iterative increments, with justification vs. waterfall
- 7.3 **Experimental design**
  - 7.3.1 Benchmark matrix: workload types × dataset sizes × instance types × node counts × regions × providers × repetitions
  - 7.3.2 Repetition strategy and variance capture (3× runs, confidence intervals)
  - 7.3.3 **Grouped splitting** — why repeated runs of one configuration must never straddle train/test
  - 7.3.4 **Leave-one-workload-out protocol** — the core validation design; train on 2 workload types, test on the 3rd
  - 7.3.5 Baseline for comparison — the earlier non-fingerprint recommender
- 7.4 Metrics: R², MAE, RMSE for prediction; regret / SLA-violation rate / cost-vs-oracle for recommendation quality
- 7.5 Threats to validity — internal, external, construct (quota-constrained instance coverage, 3-workload limit, synthetic input data)

---

## Chapter 8 — Design
**Target: 12–14 pages** · *Maps to required section 8*

- 8.1 System architecture — component diagram, data flow end to end
- 8.2 Benchmark harness design
  - 8.2.1 AWS EMR path — cluster provisioning, step submission, **event-log configuration**, resumability
  - 8.2.2 Azure IaaS path — cloud-init provisioning, standalone Spark bring-up, result collection
- 8.3 Workload design — cpu-heavy, memory-heavy, io-heavy: what each stresses and why the triple spans the space
- 8.4 **Fingerprint extraction design** *(the novel contribution — give it the most space)*
  - 8.4.1 Spark event log schema and the parse strategy
  - 8.4.2 Feature vector definition: CPU utilisation, GC time, shuffle read/write bytes, I/O wait, task duration variance
  - 8.4.3 Early-runtime truncation — how much of a run is enough, and how that fraction was chosen
  - 8.4.4 Normalisation across cluster sizes (so a fingerprint is scale-invariant)
- 8.5 Prediction model design — targets, feature encoding, model family selection
- 8.6 Cost model — on-demand as the SLA-safe basis; spot retained for sensitivity analysis only
- 8.7 Carbon model — runtime × power draw × grid intensity × PUE; per-run rather than per-region, and why that matters
- 8.8 Recommendation and ranking — SLA filtering, scoring, tie-breaks, **Pareto front** construction
- 8.9 Dashboard design — screens, controls, information architecture
- 8.10 Data model / schema definitions

---

## Chapter 9 — Implementation
**Target: 14–16 pages** · *Maps to required section 9*

- 9.1 Resources and facilities used — accounts, credit limits, quotas, local hardware
- 9.2 Repository structure and module responsibilities
- 9.3 Dataset generation
- 9.4 Spark workload implementations
- 9.5 AWS EMR automation — batch runner, resumability, failure capture
- 9.6 Azure automation — cloud-init templating, sequential matrix runner, retry/resume, result collection
- 9.7 **Fingerprint pipeline implementation** — event log retrieval, parsing, feature assembly
- 9.8 Pricing ingestion — AWS and Azure on-demand collection, scoping to target regions
- 9.9 Carbon and renewable data ingestion — zone mapping, granularity, join strategy and fallback
- 9.10 Model training, comparison and cross-validation
- 9.11 Recommendation engine
- 9.12 Dashboard
- 9.13 **Implementation challenges and resolutions** — *a genuinely markable section; you have strong material:*
  - Azure quota ceilings (Central India 32 vCPU, SEA 10) and the resulting matrix reduction
  - cloud-init YAML parse failure from an unindented Python heredoc
  - PEP 668 blocking pip on Ubuntu 22.04
  - macOS bash 3.2 lacking associative arrays
  - BSD `sed` delimiter collision with base64 keys containing `/`
  - Retrofitting event logging onto a benchmark campaign already in progress
- 9.14 Testing — unit test coverage, what is and isn't covered
- 9.15 Third-party code declaration — **mandatory**; identify author, delimit extent, confirm minor proportion

---

## Chapter 10 — Objectives vs. Achievements
**Target: 6–8 pages** · *Maps to required section 10*

- 10.1 Objective-by-objective assessment table: objective / success criterion / evidence / **achieved · partial · not achieved**
- 10.2 Requirements traceability — FR/NFR verification status
- 10.3 Honest account of what was descoped and why (quota limits, credit ceilings, time)

> Markers reward candour here. A partially-met objective with a clear explanation scores better than an overclaimed one.

---

## Chapter 11 — Critical Evaluation
**Target: 14–16 pages** · *Maps to required section 11 — highest-value chapter after the lit review*

- 11.1 Prediction accuracy results — model comparison, grouped CV with mean ± std
- 11.2 **Leave-one-workload-out results — the headline experiment.** Per-held-out-workload breakdown, not just an average
- 11.3 **Comparison against the baseline** (your earlier non-fingerprint system) — quantify what the fingerprint layer buys
- 11.4 **Ablation study** — fingerprint features removed one group at a time; which features actually carry the transfer
- 11.5 Recommendation quality — regret vs. oracle, SLA violation rate
- 11.6 Cost-benefit: profiling cost avoided vs. accuracy sacrificed. *This is the practical argument for the whole thesis — make it explicit and quantified*
- 11.7 Efficiency and performance of the tool itself
- 11.8 Cross-provider comparison — with the sample-imbalance caveat stated plainly
- 11.9 Carbon results and sensitivity analysis
- 11.10 **Comparison with documented solutions** — position results against CherryPick/PARIS/Ernest as reported in their papers, noting the limits of cross-paper comparison
- 11.11 Statistical rigour — confidence intervals, significance testing where applicable
- 11.12 Limitations: 3 workload types, quota-restricted instance coverage, synthetic inputs, static carbon snapshot, AWS rows lacking timestamps

---

## Chapter 12 — Professional, Social, Legal and Ethical Issues
**Target: 6–8 pages** · *Maps to required section 12*

- 12.1 Professional — BCS Code of Conduct; reproducibility and honest reporting of benchmark results
- 12.2 Legal — AWS and Azure terms of service on benchmarking and publishing performance figures; Electricity Maps and Boavizta data licensing for redistribution; open-source licence compliance for the dependency tree
- 12.3 Data protection — no personal data processed; synthetic inputs only; GDPR non-applicability argued rather than assumed
- 12.4 Security — credential management, avoidance of hardcoded secrets, least-privilege IAM
- 12.5 Environmental / social — the sustainability motivation, **and** the honesty constraint: carbon figures are model estimates from published constants, not measurements. Discuss the risk of greenwashing if such estimates are presented as fact
- 12.6 Economic and social impact of automated infrastructure optimisation
- 12.7 SPER form outcome and any conditions

---

## Chapter 13 — Conclusions and Future Work
**Target: 6–8 pages** · *Maps to required section 13*

- 13.1 Summary of contributions against the research question
- 13.2 Key findings
- 13.3 **What could have been done better** — explicitly required by the guidelines. Event logging from run one; earlier quota escalation; a fourth workload type
- 13.4 Future work — more workload types, streaming, autoscaling, spot-interruption modelling, live carbon signals, online/continual learning, GPU instance families
- 13.5 Closing reflection

---

## References
*Maps to required section 14* · Harvard style throughout · assemble continuously, not at the end

---

## Appendices *(not counted toward 100–110)*
*Maps to required section 15 — all five are mandatory*

| Appendix | Contents |
|---|---|
| **A — Project plan** | ~1000 words / ~3 pages. **Gantt or equivalent diagram**, rationale per activity, resource review (cloud credits, quotas) and their implications for the schedule |
| **B — Detailed design documentation** | Full class/module diagrams, schemas, event-log field mappings |
| **C — Test data and results** | Full benchmark matrix, per-run results, complete model comparison and CV tables |
| **D — User guide** | Dashboard walkthrough, interpreting the Pareto front |
| **E — Installation guide** | venv setup, dependency install, credential configuration, cloud prerequisites |
| **F — Weekly log sheets** | Every week, with supervisor meetings minuted |
| **G — SPER form** | Completed and signed |

Single spacing and 10pt permitted in appendices. Full code listings are **not** required in the report — the code ships on the CD/data-stick.

---

## Submission checklist

- [ ] Report uploaded to **Turnitin dropbox** on CampusMoodle
- [ ] Source code uploaded (runnable by markers) — or video demo if not feasible
- [ ] Presentation slides uploaded (**max 10–12 slides**)
- [ ] SPER ethical review form submitted
- [ ] **2 printed copies** + CD to the school office
- [ ] Front cover **signed**
- [ ] Declaration **signed and dated**
- [ ] Weekly log sheets complete
- [ ] **≥ 7 contact points recorded** — below this the report is not marked and the project fails with grade F
- [ ] Draft run through Turnitin ahead of final submission

---

## Critical path

The fingerprint layer is the contribution. It is not yet implemented, and it is strictly serial:

1. **EMR cluster config JSON with `spark.eventLog.enabled` → S3** ← *blocking everything downstream*
2. Re-run the benchmark matrix with event logging on
3. Event-log parser → fingerprint feature vectors
4. Fingerprint model (KNN / Random Forest) + leave-one-workload-out validation
5. Ablation study + baseline comparison
6. Ch. 11 written from real results

Chapters 2, 3, 5, 6, 7 and 12 can be written in parallel with the experimental campaign — do them while clusters run rather than after.

**Existing assets:** 234 AWS EMR runs (no event logs — valid as baseline, insufficient for fingerprints), ~1,011 AWS + ~800 Azure rows in the merged model dataset, Azure benchmark automation, pricing collection (24 AWS / 18 Azure rows), carbon and renewable ingestion, four-model training with grouped CV, recommendation engine, Streamlit dashboard, pytest suite, Ch. 2 draft with 18 references.
