# Presentation script — 20 minutes

**Total spoken time: 19:05.** That leaves roughly a minute of slack for settling in,
a slide that sticks, or a sentence you want to repeat.

**Pace.** This is written at about 140 words per minute, which is a measured
presentation pace — noticeably slower than conversation. If you find yourself
finishing a slide early, you are rushing. Slow down rather than adding words.

**How to use it.** Rehearse from this until the shape is in your head, then present
from the shape, not the page. Reading aloud is obvious from the front of a room. The
sentences in **bold** are the ones worth landing precisely; everything else can be
paraphrased.

---

## Slide 1 — Title · 0:45 · *(clock 0:45)*

Good morning. My name is Manoj Karthik Anbalagan, and this is my dissertation —
Cost-Aware and Carbon-Aware Infrastructure Optimization for Multi-Cloud Big Data
Processing Pipelines.

In one sentence: I designed, built and evaluated a machine learning framework that
recommends how to deploy an Apache Spark job across AWS and Azure, considering
runtime, cost, an SLA deadline and carbon emissions together.

**The number I'd like you to hold on to is this one — one thousand, eight hundred and
eleven. That is how many Spark jobs I executed on live cloud infrastructure to build
this. Not simulated. Measured.**

---

## Slide 2 — The problem · 1:50 · *(clock 2:35)*

Here's the problem, and it's a genuinely awkward one.

Before you can run a Spark job in the cloud, you have to make four decisions. Which
provider. Which region. Which machine type. How many nodes. All four, before anything
runs.

**That single choice determines three things you care about — what the job costs, how
long it takes, and how much carbon it emits. And none of those three are knowable
until after you've run it.**

So you might reach for a cloud cost calculator. But a calculator asks you for the
configuration and the duration, and then multiplies. Those are exactly the two things
you don't have. You might reach for an optimisation tool — but those need the workload
to already be running on that provider so they can observe it.

What happens in practice is guesswork, habit, or over-provisioning. Pick something
larger than you need, and hope. And carbon usually doesn't enter the conversation at
all.

I surveyed forty-six practitioners at the start of this project. Cost mattered to
seventy-six per cent of them. Runtime to seventy-two. Carbon to sixty-seven. Those are
the four factors this framework optimises.

And this is not a hypothetical concern. *(gesture to the sources)* Datacentre
emissions from Microsoft, Amazon and Google are under active public scrutiny — that
Guardian piece is from July. And Microsoft Research's own sustainability programme
names, as one of its three stated goals, giving developers tools to find appropriate
tradeoffs between performance and carbon emissions. **That is precisely what I've
built.**

---

## Slide 3 — Literature review · 1:35 · *(clock 4:10)*

So what already exists?

I reviewed thirteen systems and assessed each against six capabilities — big data
processing, cost optimisation, carbon awareness, multi-cloud support, machine
learning, and whether it actually produces a recommendation.

They fall into three groups.

The first — references one, two, three, twelve and thirteen — optimises cost and
performance. Right-sizing workloads, comparing prices across providers, improving
scalability. Strong work, but carbon is absent or partial.

The second — four through nine — is carbon-aware. Shifting workloads into low-carbon
periods, tracking footprint through DevOps pipelines, energy-aware scheduling. But
these treat sustainability as an isolated objective, separate from cost and
performance.

The third — two, ten and eleven — applies AI to cloud operations. Predictive
provisioning, observability, automated resource management. These optimise one or two
objectives, not all of them.

Look down the columns and the pattern is clear. Every row has gaps. **No existing
system predicts workload performance, estimates infrastructure cost, incorporates
sustainability, and recommends a configuration across more than one provider — all at
once.**

That's the gap this research fills. And I want to be precise about the claim: it is
coverage, not superiority. I'm not saying I do cost optimisation better than the cost
optimisation papers do. I'm saying nobody had put all six together.

---

## Slide 4 — Aim and questions · 1:05 · *(clock 5:15)*

So, the aim. To design, develop and evaluate a machine learning-based multi-cloud
framework that recommends Apache Spark deployment configurations across AWS and Azure,
by jointly considering execution runtime, infrastructure cost, SLA constraints,
regional carbon intensity and renewable energy availability.

Three questions follow from that.

First — can runtime and cost be predicted accurately enough from configuration alone,
with no profiling run, for a workload the system has never benchmarked at that size?

Second — does a model-driven recommendation actually beat simple heuristics, once you
impose a hard deadline?

Third — does computing emissions per run change the deployment decision, compared with
simply ranking regions by how clean their electricity grid is?

I'll answer all three. **And the third one produced the most interesting result in the
project, so I'll come back to it at the end.**

---

## Slide 5 — The proposed solution · 1:35 · *(clock 6:50)*

This is the framework. Five layers.

**Cloud Benchmarking** runs the three Spark workloads across instance types and node
counts, on EMR and on Azure VMs. That's the layer that produces the measurements.

**Dataset Integration** takes two providers' very different output schemas,
standardises them into one table, and joins in pricing and carbon data.

**Machine Learning** preprocesses that table, trains four regression models under
cross-validation, and persists the best one.

**The Recommendation Engine** — highlighted, because this is where the research
contribution sits — generates candidate configurations, predicts runtime and cost for
each, computes emissions, filters on the SLA, and ranks by the chosen objective.

And **User Interaction** is a Streamlit application returning a ranked Top-N with a
stated reason on every row.

The user supplies five things. Dataset size. Workload class. An SLA deadline in
minutes. An optimisation goal — cost, runtime, carbon or balanced. And how many
results they want back.

**And here is the line that separates this from the prior work: no new benchmark run
is needed at inference.** The engine scores every candidate — an average of thirty-
three per scenario — from the trained model alone. Comparable systems in the
literature minimise profiling. They don't eliminate it.

---

## Slide 6 — Building the corpus · 1:45 · *(clock 8:35)*

Let me show you how the corpus was built, because everything downstream rests on it.

Three Spark workloads, each written to stress a different bottleneck. The CPU-heavy
job applies eight chained mathematical transformations to every row, then a single
grouped aggregation — the transforms are narrow, so there's no shuffle until that
groupBy. The memory-heavy job caches two DataFrames, forces them into memory, and
joins them on a fifty-thousand-key space. The I/O-heavy job repartitions, writes
Parquet, re-reads what it has just written, and writes again — two writes and a read
is what makes it I/O-dominated.

The matrix: two clouds, four regions, twelve machine types, two node counts, seven
dataset sizes from ten megabytes to five gigabytes, and three workloads.

On AWS that's EMR — managed YARN, reading from S3. On Azure I provisioned Ubuntu
virtual machines and ran Spark in standalone mode, which meant building the entire
provisioning layer myself using cloud-init.

One design decision worth pointing out. **Four hundred and thirty-nine configurations
were run more than once, and that was deliberate.** Cloud infrastructure is shared
tenancy — the same job on the same machine does not take the same time twice. The
median coefficient of variation across those repeats is four point one five per cent,
which tells me the campaign reproduces. And quantifying that variance is what
justifies the model selection method I'm about to describe.

---

## Slide 7 — Cost and carbon · 1:50 · *(clock 10:25)*

Two quantities have to be derived from every run.

Cost is straightforward. Hourly price, times nodes, times runtime. For AWS I use the
EC2 price *plus* the EMR service fee, so both providers are costed on a like-for-like
basis rather than flattering AWS with the bare compute rate. Prices were fetched once
from the AWS Pricing API and the Azure Retail Prices API and stored with a fetch date,
so the experiment reproduces exactly even after providers change their pricing.

Carbon is more involved. Emissions equal power draw, times node count, divided by a
thousand, times runtime in hours, times the grid's carbon intensity, times PUE. Power
draw comes from published Cloud Carbon Footprint coefficients at a fifty per cent
utilisation assumption. PUE is Power Usage Effectiveness — it accounts for cooling and
power distribution overhead on top of what the servers themselves draw; one point one
five for AWS, one point one eight for Azure. Grid intensity and renewable share come
from Electricity Maps — six hundred and forty-three grams per kilowatt-hour for
western India, four hundred and eighty-one for Singapore.

Three scoping decisions underneath, all deliberate. **Cost is attributable per
execution**, because provider billing aggregates at account level and arrives days
late — it cannot be tied to a single job. **Emissions are operational**, computed from
energy actually drawn during the run. And **a single utilisation basis** is applied
across all 1,811 runs, so every configuration is assessed on identical terms.

---

## Slide 8 — The ML pipeline · 1:45 · *(clock 12:10)*

Now the machine learning.

Nine features predict two targets — runtime in minutes, and cost in dollars. Cloud,
region, electricity zone, workload type and machine type are categorical, so they're
one-hot encoded. Dataset size, node count, carbon intensity and renewable percentage
are numeric, so they're standard-scaled. All four models share one preprocessing
pipeline, so the comparison between them is genuinely like-for-like.

**But the most important line of code in this project is the grouping.**

I define a group key from six columns — cloud, region, dataset size, workload type,
machine type and node count. That tuple identifies one benchmark configuration. Every
train-test split, and every cross-validation fold, is grouped on it.

Here's why that matters. I have four hundred and thirty-nine configurations that were
run more than once. Without grouping, a configuration run three times could put two
runs in training and one in test. **The model would then be scored on a value it has
effectively memorised.** You'd get a higher R-squared, and it would be measuring
interpolation over repeated runs rather than generalisation.

With grouping, every run of a configuration stays on the same side of every boundary.
So the accuracy figures I'm about to show you describe generalisation to
configurations the model has never seen in any form.

And selection is made on cross-validation rather than a single partition — because
with that much measurement variance, one split is a high-variance estimate.

---

## Slide 9 — The recommendation engine · 1:40 · *(clock 13:50)*

The engine runs five stages.

**One** — build the candidate set. Every distinct combination of cloud, region,
machine type and node count observed for that workload. An average of thirty-three per
scenario.

**Two** — predict runtime and cost for all of them, with a physical-plausibility floor
applied before anything moves on.

**Three** — compute emissions for each candidate. And note the ordering here, because
this is the architectural point. **Emissions are computed *from* the predicted
runtime.** Carbon enters the decision, not the prediction. Which means you cannot
answer the carbon question without first answering the performance question.

**Four** — filter on the SLA. Anything whose predicted runtime exceeds the deadline is
dropped. If nothing meets it, the engine returns the closest alternatives and says so
explicitly on every row, rather than returning an empty result.

**Five** — score and rank by the selected objective.

The balanced objective is a weighted Euclidean distance from the ideal point —
thirty-five per cent runtime, thirty-five cost, twenty emissions, ten renewable share.
Two design choices there. Each term is a proportional gap from the best available
candidate rather than a min–max score, because min–max lets candidates that never
realistically compete determine how much a criterion actually weighs. And squaring
before weighting penalises a configuration that's excellent on one axis and poor on
another — which is exactly what a balanced mode should do.

---

## Slide 10 — Results: prediction · 1:30 · *(clock 15:20)*

So — can it predict?

On the left, predicted against measured runtime for the deployed model, on
configurations held out by group. The dashed line is perfect prediction. The points
track it closely across the full range.

On the right, the cross-validated figures for all four models. Linear regression
explains about sixty-eight per cent of runtime variance. A single decision tree
reaches eighty-three. Both ensembles reach eighty-nine.

**Random Forest is the deployed model. Runtime R-squared of nought point eight eight
nine. Cost R-squared of nought point eight nine zero. Mean absolute error on runtime
of nought point two seven minutes — about sixteen seconds.**

Two reasons for that choice. First, selection is made on grouped cross-validation,
where every configuration is tested exactly once — a far more stable estimate than any
single partition. Second, Random Forest leads on all four cross-validated metrics.

And the ensembles separate cleanly from the simpler models — paired t-tests give p
equals nought point zero zero one six against the decision tree, and nought point zero
zero zero one against linear regression. So the ensemble step is doing real work.

---

## Slide 11 — Results: recommendation quality · 1:40 · *(clock 17:00)*

Prediction accuracy is a means, not an end. The real question is whether the
recommendations are any good.

I evaluated this leave-one-scenario-out. There are twenty-one scenarios — each one a
workload type crossed with a dataset size. For each, I train on the remaining twenty,
then ask the model to rank roughly thirty-three configurations it has never seen at
that size, and score it against ground truth built from the measured runs.

Four baselines compete under identical deadlines. Historical mean — use the average of
what we've seen. Nearest size — look up the closest job we ran. Largest cluster —
over-provision, which is the common real-world default. And random, which sets the
floor.

**At a medium deadline the model picks the optimal configuration in ninety point five
per cent of scenarios.** Nearest size manages eighty-one. Historical mean, forty-
three. Largest cluster, twenty-nine. Random never finds it.

The sweep across deadline tightness is underneath. Under a loose deadline the model
reaches ninety-five point two per cent top-one accuracy **with zero SLA violations**.
And against the strongest baseline it cuts the SLA violation rate by roughly a third —
nought point zero nine five against nought point one four three.

That's the result I'd emphasise. It isn't only picking cheaper configurations. It's
meeting deadlines more reliably.

---

## Slide 12 — The headline finding · 2:05 · *(clock 19:05)*

I'll finish with the finding I did not expect.

If you want to run a job with the lowest carbon emissions, the obvious approach — and
it's the common one in the carbon-aware literature — is to rank regions by grid carbon
intensity and pick the cleanest. On that basis Singapore wins every time: four hundred
and eighty-one grams per kilowatt-hour, against six hundred and forty-three for
western India. It would select Singapore in all twenty-one of my scenarios.

**But when you compute emissions per run — power, times nodes, times runtime, times
intensity, times PUE — the ranking inverts.** Azure Central India emits nought point
three four six grams per run. Azure Southeast Asia, nought point four four eight. The
region on the dirtier grid produces the lower emissions.

The reason is the hardware. The AMD EPYC parts available in Central India draw about
one point zero eight watts per virtual CPU. The Intel alternatives draw between two
point three and two point seven two. **A cleaner grid doesn't help you if the job runs
on hardware that needs twice the electricity to do the same work.**

Why does that matter? Because emissions can only be computed from a predicted runtime.
The carbon question and the performance question have to be answered together — and
that is the case for one integrated framework rather than two separate tools.

There's a practical finding alongside it. The cheapest configuration was also the
greenest in all twenty-one scenarios. On this corpus, optimising for cost did not cost
sustainability.

What comes next is workload fingerprinting from Spark event logs, so the system
characterises a job automatically instead of asking the user to classify it. And
uncertainty-aware SLA filtering using prediction intervals, which would open the door
to spot pricing under a hard deadline.

**Thank you. I'm happy to take questions.**

---

## If you are running long

Cut in this order. Each is self-contained, so removing it leaves no dangling reference.

1. **Slide 7**, the three scoping decisions at the end — the audience can read the
   cards. *Saves ~25 seconds.*
2. **Slide 6**, the per-workload descriptions — say "three workloads, stressing CPU,
   memory and I/O respectively" and move on. *Saves ~30 seconds.*
3. **Slide 3**, the third grouping (AI-driven) — the gap statement still lands with
   two. *Saves ~20 seconds.*
4. **Slide 9**, the two design choices behind the balanced score — keep the five
   stages, drop the justification. *Saves ~30 seconds.*

That's just under two minutes of slack without losing anything structural.

## If you are running short

Expand slide 12. Add the node-count trade-off: doubling from two nodes to four cuts
runtime by forty-three per cent but raises cost by thirty-eight and emissions by
thirty-nine, because the runtime saving is sublinear while node-hours are linear. It's
a concrete, memorable number and it reinforces why cost and carbon moved together.

## Delivery notes

- **Slide 3 is the one to resist reading.** Thirteen rows of ticks are there to be
  looked at, not recited. Give the three groupings and let the audience scan.
- **Say the big numbers slowly and only once.** 1,811. 0.889. 0.905. 0.346 against
  0.448. Rushing a number is the same as not saying it.
- **Pause after the reversal on slide 12.** It's counter-intuitive and the audience
  needs a beat to register it before you explain why.
- **Do not improvise claims you have not prepared.** Anything you say out loud is fair
  game in the viva, and unslided statements attract more scrutiny than slided ones.
