# THESIS CONTEXT — read this first in every new chat

> **Report location:** the assembled dissertation (`final report2.docx`) lives at
> `/Users/manojanbalagan/Documents/Projects/IIT/Research`. The code and results live in this repo
> (`~/Documents/research/research/cost-aware-infrastructure-optimization`).
>
> **NOTE — structure superseded.** The 13-chapter skeleton below was replaced by the supervisor's
> 9-chapter structure now in `final report2.docx`: 1 Introduction · 2 Literature Review ·
> 3 Software Requirements Analysis (SRS) · 4 Methodology and Project Management · 5 Design ·
> 6 Implementation · 7 Testing · 8 Evaluation (incl. 8.10 LEPSI) · 9 Conclusion and Future Work.
> Workload fingerprinting does **not** appear anywhere in the current report and is future work only.

> **New chat? Do this:** Read this file, then `DISSERTATION_SKELETON.md`, then any already-written
> chapter files in `thesis/`. Then draft the requested chapter. Update the Status table below when done.

---

## The project in one paragraph

An MSc dissertation (RGU CMM799, MSc Big Data Analytics) building a **cost-, SLA- and carbon-aware
cluster configuration recommender for Apache Spark** across AWS EMR and Azure IaaS. Given a dataset
size, workload type and SLA deadline, it predicts runtime and cost for every candidate configuration
(instance type × node count × region × provider) and returns a Pareto front of cheapest / greenest /
fastest-within-SLA options.

The intended novel contribution is a **workload fingerprinting layer** for cross-workload
generalisation: predicting good configurations for a *previously unseen* workload type from
early-runtime resource-usage signatures (CPU utilisation, GC time, shuffle read/write bytes, I/O wait,
task duration variance), avoiding the full profiling runs that CherryPick, Ernest and PARIS require.

## Author

Manoj (Karthik Manoj). GitHub `KarthikManoj`. Repo `cost_aware_tool`.

---

## HARD CONSTRAINT — read before proposing anything

**Six days total, thesis started from zero.** Roughly 18 pages/day required.

Consequences that override normal best practice:

- **No new experiments, no new code, no refactoring.** Results come from data already on disk.
- **Every one of the 15 required sections must exist, even if thin.** A missing mandatory chapter is a
  structural failure; a short chapter just scores lower in one place. If behind, thin uniformly.
- **Never suggest improving the software.** The deliverable is the document.
- Tables, figures and diagrams are legitimate content and 4–5× faster to produce than prose. Target
  25–30 pages of them.

### Fingerprint status — CHECK BEFORE WRITING CH. 4/8/10/11

Fingerprinting is **designed but not implemented**. No fingerprint code exists in the repo;
`cleaned_dataset.csv` has only `dataset_size_mb, workload_type, instance_type, nodes, runtime_minutes,
cost_usd, cpu_avg_pct, memory_avg_pct, source`.

Contingent on a one-off check of `s3://cost-aware-spark-research-manoj-2026/emr-logs/` for archived
Spark event logs:

- **Logs found** → extract fingerprints, run leave-one-workload-out (train on 2 workload types, test on
  the 3rd), compare against the no-fingerprint baseline. Ch. 11 reports it as a result.
- **Logs absent** → fingerprinting is **specified but not empirically validated**. Design it fully in
  Ch. 4 and Ch. 8, state the honest limitation in Ch. 10, and move it to future work in Ch. 13. Do NOT
  claim or imply results that were not produced.

**Current resolution:** _UNRESOLVED — update this line once checked._

---

## Formatting rules (RGU MSc Project Guidelines v1.0)

| Rule | Value |
|---|---|
| Length | 100–110 pages excluding appendices |
| Paper / spacing | A4, 1.5 line spacing (single in appendices) |
| Font | 11pt or 12pt (10pt permitted in appendices) |
| Pagination | All pages numbered |
| **Citation style** | **Harvard** (author surname + date) — RGU requirement |
| Abstract | Single line spacing, ~300 words |
| Slides | Maximum 10–12 |

**Mandatory front matter:** signed front cover, title page, **signed and dated declaration**,
acknowledgements, abstract, table of contents. Unsigned cover or declaration = not accepted for assessment.

**Mandatory appendices:** project plan (~1000 words, with Gantt), detailed design documentation, test
data and results, user guide, installation guide. Plus weekly log sheets and the SPER ethics form.

**Automatic fail:** fewer than 7 recorded supervisor contact points means the report is not marked at
all. (Status: unconfirmed — Manoj to verify with supervisor.)

---

## House style — keep consistent across chapters

- **Third person, past tense** for work done ("the harness was implemented"). Present tense for the
  artefact's behaviour ("the recommender returns a Pareto front").
- **British English** (optimisation, analyse, behaviour, modelling).
- **Harvard citations inline**: (Alipourfard et al., 2017). Never IEEE numerics — the existing Ch. 2
  draft uses IEEE style and must be converted.
- Number all figures and tables, caption every one, and refer to each at least once in the body text.
- Do not invent cross-references. Only cite a section number if that section exists in the skeleton.
- Do not fabricate citations, results or figures. If a number is unavailable, insert
  `[TODO: value from data/models/<file>]` rather than inventing it.

### Canonical terminology — use exactly these

| Use | Not |
|---|---|
| the recommender | the tool, the system, the app |
| workload fingerprint | signature, profile, footprint |
| configuration | config, setup |
| SLA deadline | time constraint, deadline |
| benchmark harness | test framework, runner |
| cross-workload generalisation | transfer learning, generalization (US spelling) |
| workload types: **cpu-heavy**, **memory-heavy**, **io-heavy** | CPU-bound, memory-intensive, IO |

---

## Literature — the comparison set

**CherryPick** (Bayesian search), **Ernest** (analytical performance modelling), **Micky** (collective
profiling), **PARIS** (transfer via workload characterisation), **OtterTune** (DBMS knob tuning),
**Arrow**. A Ch. 2 draft with 18 references exists in IEEE style and needs Harvard conversion.

The gap to argue throughout: these systems either require full profiling runs per workload, or do not
generalise to unseen workload types, and none jointly optimise cost, SLA and carbon.

---

## Results already on disk — Ch. 11 draws from these, no re-running

| File | Contents |
|---|---|
| `data/models/cross_validation_metrics.json` | Grouped 5-fold CV, 4 models, mean ± std |
| `data/models/model_comparison.json` | Holdout comparison |
| `data/models/model_metrics.json` | Best model: runtime R² 0.957, cost R² 0.920 |
| `data/models/feature_importance.json` | Tree-based importances |
| `data/eda/` | Descriptive statistics, grouped summary |
| `data/performance/cleaned_data/cleaned_dataset.csv` | Cleaned benchmark corpus |

**Headline CV numbers (grouped 5-fold):** random forest is best — runtime R² 0.893 ± 0.045,
cost R² 0.894 ± 0.027. Gradient boosting close behind (0.885 / 0.874); decision tree 0.834 / 0.820;
linear regression weakest at 0.683 / 0.720.

Splits are **grouped by configuration** (cloud, region, size, workload, machine type, nodes) so
repeated runs of the same setup never straddle train and test. This is a deliberate methodological
choice and should be argued explicitly in Ch. 7.

---

## Experimental setup — facts for Ch. 7, 8, 9

**Corpus:** ~1,011 AWS rows and ~800 Azure rows after cleaning. 234 original EMR runs, collected
without Spark event logging enabled.

**AWS:** EMR 6.15.0, region ap-south-1, bucket `cost-aware-spark-research-manoj-2026`. Dataset sizes
100/500/1024/2048/3072/5120 MB.

**Azure:** Standalone Spark on plain Ubuntu 22.04 IaaS VMs — *not* Databricks, which was rejected on
cost and reliability grounds under a $100 credit account. Matrix: 6 VM sizes across Dsv3/Dasv4/Ddsv4
families, Central India and Southeast Asia, 2 and 4 nodes, 3 workload types, 5 dataset sizes
(10 MB–5 GB), 2 repetitions.

**Quota constraints (a genuine finding, report honestly):** Central India capped at 32 vCPUs,
Southeast Asia at 10. Dsv5/Dasv5 have zero quota in both regions and were excluded.

**Pricing:** on-demand as the SLA-safe basis (24 AWS rows, 18 Azure rows). Spot retained for
sensitivity analysis only — never as a primary recommendation.

**Carbon model:** per-run, computed as runtime × power draw × grid carbon intensity × PUE.
Electricity Maps for intensity and renewable percentage (late 2025–mid 2026); Boavizta and Cloud
Carbon Footprint for per-instance power draw; PUE constants AWS ≈ 1.15, Azure ≈ 1.18. Per-run
computation plus Pareto output is what prevents Singapore trivially always "winning" on carbon.

**Known data caveats — state as limitations, do not paper over:**
- AWS and Azure sample sizes are close but unequal (~1,011 vs ~800).
- AWS rows carry no timestamp, so their carbon features fall back to the region's all-time mean;
  only Azure rows get a date-matched reading. The `carbon_feature_source` column records which path
  each row took.
- Carbon/renewable data is a static snapshot, not live.
- Input data is synthetic, generated by `dataset_generator/`.

---

## Implementation war stories — Ch. 9.13 material, genuinely markable

1. **cloud-init YAML parse failure** — an unindented Python heredoc inside a `content: |` block broke
   parsing. Fixed by extracting the Python into its own `write_files` entry.
2. **PEP 668 on Ubuntu 22.04** blocked `pip3 install`. Fixed with `--break-system-packages` in the
   cloud-init template, plus an error trap and fast-fail polling.
3. **macOS bash 3.2** lacks `declare -A`. Fixed by installing bash 5.x via Homebrew and updating shebangs.
4. **BSD `sed` delimiter collision** with base64 storage keys containing `/`. Fixed by switching to `|`.
5. **Shebang/content mismatches in cloud-init** caused silent, hard-to-trace failures — every file in
   the pipeline had to be audited.
6. **Azure quota ceilings** forced reduction of the benchmark matrix mid-campaign.
7. **Event logging was not enabled** on the original EMR campaign — the root cause of the fingerprint
   blocker, and an honest lesson for Ch. 13.3 ("what could have been done better").

**Script run order (Azure):** `run_sequential_matrix.sh` → `collect_results.sh` → `retry_failed.sh` →
`collect_results.sh` to confirm.

---

## Repository map — for Ch. 9

```
dataset_generator/   synthetic Spark input generation
spark_jobs/          cpu_heavy.py, memory_heavy.py, io_heavy.py, common.py
aws/                 emr_runner.py, upload_to_s3.py
AzureVM_creation/    cloud-init templating, sequential matrix runner, retry/resume, result collection
scripts/             EMR batch runners (resumable), cleaning, packaging, local demo
cloud_prices/        AWS + Azure on-demand price collection
Carbon_dataset/      carbon_collect.py, renewable_collect.py (Electricity Maps)
metrics/             collect_metrics.py — appends one experiment result to the performance CSV
ml/                  preprocessing, train_model, eda, recommendation_engine, merge_model_dataset
dashboard/           Streamlit app
tests/               pytest — cost calc, carbon join, scoring/tie-breaks, schema
```

**Stack:** Python 3.11, PySpark, scikit-learn, pandas, boto3, Bash 5.x, Streamlit, pytest.
Dependencies pinned in `requirements.txt` to the versions the reported results were produced with.

---

## Ethics / legal — Ch. 12 substance

No human subjects; the SPER form is routine but **mandatory**. Real content to cover:

- Cloud provider terms of service on benchmarking and publishing performance figures
- Electricity Maps and Boavizta data licensing for redistribution
- Open-source licence compliance across the dependency tree
- Credential handling — environment variables only, no hardcoded secrets, least-privilege IAM
- No personal data processed; synthetic inputs only. Argue GDPR non-applicability, don't just assert it
- **Greenwashing risk** — carbon figures are model estimates from published constants, not
  measurements. Presenting them as measurements would be a professional-integrity failure. Worth a
  full page and it scores well
- BCS Code of Conduct; reproducibility and honest reporting
- **Third-party code declaration is mandatory** — identify original authors, delimit extent, confirm
  it is a minor proportion. Undeclared code is academic misconduct

---

## Chapter status

Update this table at the end of every chat. One file per chapter in `thesis/`.

| Ch | Title | Target pp | File | Status |
|----|-------|-----------|------|--------|
| — | Front matter | — | `thesis/00_front_matter.md` | Not started |
| 1 | Introduction and Motivation | 8–10 | `thesis/01_introduction.md` | Not started |
| 2 | Literature Review | 18–22 | `thesis/02_literature_review.md` | IEEE draft exists — needs Harvard conversion |
| 3 | Software Tools Evaluation | 8–10 | `thesis/03_tools.md` | Not started |
| 4 | Problem Analysis and Proposed Solution | 8–10 | `thesis/04_problem_analysis.md` | Not started |
| 5 | Aims, Objectives and Specification | 6–8 | `thesis/05_objectives.md` | **Drafted** — O1–O6 + EC1–EC17 fixed; 2 conditional criteria pending S3 check |
| 6 | Requirements | 6–8 | `thesis/06_requirements.md` | Not started |
| 7 | Methodology | 8–10 | `thesis/07_methodology.md` | Not started |
| 8 | Design | 12–14 | `thesis/08_design.md` | Not started |
| 9 | Implementation | 14–16 | `thesis/09_implementation.md` | Not started |
| 10 | Objectives vs Achievements | 6–8 | `thesis/10_achievements.md` | Not started |
| 11 | Critical Evaluation | 14–16 | `thesis/11_evaluation.md` | Not started |
| 12 | Professional, Social, Legal, Ethical | 6–8 | `thesis/12_ethics.md` | Not started |
| 13 | Conclusions and Future Work | 6–8 | `thesis/13_conclusions.md` | Not started |
| — | References (Harvard) | — | `thesis/14_references.md` | Not started |
| — | Appendices A–G | — | `thesis/15_appendices.md` | Not started |

### Decisions log — append as chapters are written

Record anything a later chapter must stay consistent with: objective numbering (O1–O6), requirement
IDs (FR1…, NFR1…), figure/table numbering, and any claim made that a later chapter must honour.

**Ch. 5 (drafted) — binding decisions. Later chapters must honour all of these.**

*Objective numbering — O1–O6 are now fixed. Do not renumber, reorder or add.*

| ID | Objective | Success criterion | Where verified |
|----|-----------|-------------------|----------------|
| O1 | Two-provider benchmark corpus | ≥1,500 cleaned runs, ≥3 workload types, ≥5 dataset sizes, ≥2 node counts | §11.1, App. C |
| O2 | Runtime + cost prediction | Grouped 5-fold CV R² ≥ 0.85 both targets, fold std ≤ 0.10, ≥4 model families | §11.1 |
| O3 | Workload fingerprint representation | Stage 1 design (unconditional) / Stage 2 leave-one-workload-out (conditional) | §11.2, §11.4, App. B |
| O4 | Cost + per-run carbon models | On-demand pricing all 4 regions; per-run carbon, cited constants, recorded provenance | §11.9 |
| O5 | Pareto-front recommender under SLA | Non-empty, non-dominated, SLA-feasible, deterministic tie-breaks | §11.5, §11.7 |
| O6 | Critical evaluation | Regret + SLA violation rate; baseline comparison; ablation (cond.); confidence intervals | §11.1–11.12 |

*Evaluation criteria EC1–EC17 defined in Table 5.3.* **Ch. 10 must score against these exact IDs and
thresholds** — do not invent new criteria or soften a threshold retrospectively. EC7 and EC8 are the
only conditional ones (both gated on the S3 event-log check).

*O3 is claimed at DESIGN STAGE ONLY.* Ch. 5 explicitly states no leave-one-workload-out result is
claimed. Ch. 8 must give the full specification (§8.4); Ch. 11 must report **no** LOWO figures unless
actually produced; Ch. 10 must mark EC7/EC8 as *not achieved* with cause if unresolved. A `[TODO]`
marker sits in Ch. 5 §5.2/O3 pointing at THESIS_CONTEXT line 55 — resolve both together.

*Definitions fixed in §5.3 — reuse verbatim, do not redefine:*
- **"Optimal" = Pareto optimality.** The recommender returns a set, never a single best configuration.
  No chapter may claim it identifies *the* optimal configuration.
- **Tie-break precedence (Table 5.2):** SLA feasibility → cost → carbon → runtime → node count, then
  instance type lexicographic. Ch. 8.8 and the `tests/` scoring tests must match this exact order.
- **SLA deadline = hard constraint on predicted runtime**, applied as a pre-ranking filter. Never a
  soft penalty term. Consequence accepted: point-estimate filtering admits true-runtime breaches,
  measured as SLA violation rate in §11.5.
- **"Unseen workload type" = strict reading** — absent from training entirely, not merely an
  unbenchmarked configuration. The weak reading is already covered by O2's grouped splitting and is
  not a contribution.

*Claims Ch. 5 has already committed to — later chapters must not contradict:*
- Random forest is the best model: runtime R² 0.893 ± 0.045, cost R² 0.894 ± 0.027 (grouped 5-fold).
  Also quoted: GB 0.885 ± 0.038 / 0.874 ± 0.035; DT 0.834 ± 0.067 / 0.820 ± 0.057; LR 0.683 ± 0.028 /
  0.720 ± 0.020. Ch. 11 must reproduce these exactly from `cross_validation_metrics.json`.
- Corpus ~1,011 AWS + ~800 Azure. **Note: ~1,811 total meets EC1's ≥1,500 threshold** — if the real
  cleaned row count differs, EC1 and the O1 status note both need revising.
- Spot pricing is sensitivity-only, justified by unbounded runtime risk from capacity reclaim.
- Only 3 workload types → LOWO yields 3 folds; conceded in §5.3.3 as insufficient for robustness.
  §11.12 and §13.4 must carry this, and no chapter may argue it away.
- AWS rows lack timestamps → region all-time-mean carbon fallback; Azure rows date-matched.

*Formatting conventions established:*
- Tables numbered `Table <chapter>.<n>` (Ch. 5 used 5.1, 5.2, 5.3). Figures follow the same scheme.
- Harvard citations in the RGU style used in Ch. 5's reference block. **Ch. 2's IEEE draft must be
  converted to match.** Ch. 5 cites only Alipourfard *et al.* (2017), Venkataraman *et al.* (2016),
  Yadwadkar *et al.* (2017); these are duplicated in the chapter file for drafting convenience and
  must be de-duplicated into `thesis/14_references.md` before submission.
- `thesis/` directory created by this chapter; it did not previously exist.
