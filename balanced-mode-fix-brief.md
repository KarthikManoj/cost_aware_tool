# Task brief — fix the Balanced optimisation mode

## How to run this

1. **Commit or stash first.** `git commit -am "pre-balanced-fix baseline"` — the regression check in Step 5 depends on being able to diff against known-good output.
2. **Start in plan mode** (`Shift+Tab` twice in Claude Code). Step 0 is investigation only. Let it read the code and come back with findings and a plan before it edits anything — the fix depends on what it finds in Step 0.
3. Paste everything below this line as the task.
4. When it presents the Step 0 findings, check them against the Diagnosis section yourself before approving the edits.

---

## Context

This is a multi-cloud Spark infrastructure recommender. The recommendation engine ranks candidate configurations under four optimisation goals: `cost`, `runtime`, `carbon`, `balanced`.

**The bug:** `balanced` always returns the same top-ranked configuration as `runtime`. It is never independent.

**Hard constraint:** the behaviour of `cost`, `runtime` and `carbon` must NOT change. Their outputs are already published in a dissertation. Only `balanced` may change. Verify this with a regression check before you finish.

---

## Current code (from the scoring function)

```python
if goal == "cost":
    return cost_score
if goal == "runtime":
    return runtime_score
if goal == "carbon":
    return carbon_score + (0.25 * renewable_penalty)
# Balanced weights as specified in the dissertation methodology:
# 0.35 runtime + 0.35 cost + 0.20 carbon + 0.10 renewable penalty.
return (
    (0.35 * runtime_score)
    + (0.35 * cost_score)
    + (0.20 * carbon_score)
    + (0.10 * renewable_penalty)
)
```

Lower score = better. Candidates are ranked ascending.

---

## Step 0 — Investigate first, report back before changing anything

Find and tell me:

1. The file and function containing the code above.
2. **What `carbon_score` is derived from** — is it (a) normalised *regional grid carbon intensity* (gCO₂/kWh, a per-region constant), or (b) normalised *predicted per-run emissions* (gCO₂eq for this specific job, which depends on runtime × nodes × power draw)? This is the crux. Print the source column/expression.
3. What `renewable_penalty` is derived from, and whether it is per-region.
4. Where min–max normalisation happens, and whether it is computed over the full candidate set or some subset.
5. Whether there is a tie-break, and what it sorts on when scores are equal.

---

## Diagnosis (confirm or refute this in Step 0)

Two things are suspected to be wrong:

**Cause 1 — Balanced scores carbon on the wrong variable.**
If `carbon_score` is regional grid intensity, then for any candidate set where all top candidates sit in the same region, `carbon_score` and `renewable_penalty` are identical across those candidates. After min–max normalisation they become constants and contribute nothing to the ranking. That kills 0.20 + 0.10 = **30% of the weight vector**, leaving `0.35·runtime + 0.35·cost`.

This also contradicts the project's own methodology, which ranks the `carbon` goal on *per-run emissions*, not grid intensity, precisely because grid intensity ignores how long a job runs and how many nodes it occupies.

**Cause 2 — equal weights on two anti-correlated criteria produce an exact tie.**
Runtime and cost trade off against each other (more nodes = faster but pricier). With min–max normalisation over two candidates:

```
small cluster:  0.35(1.0) + 0.35(0.0) = 0.35
large cluster:  0.35(0.0) + 0.35(1.0) = 0.35
```

Exact tie → the tie-break decides → it currently falls through to runtime order.

More generally, a **weighted-sum scalarisation always selects a vertex of the Pareto front**, never an interior compromise. So even without an exact tie, `balanced` will land on whichever single objective the weights happen to favour.

---

## Step 1 — Fix the carbon variable

If Step 0 confirms `carbon_score` is regional grid intensity, change the **balanced** branch to use normalised **predicted per-run emissions** — the same quantity the `carbon` goal already uses.

Do NOT change what the `carbon` goal itself computes. If `carbon_score` is shared between both branches, introduce a separate variable (e.g. `emissions_score`) rather than redefining `carbon_score` in place.

Per-run emissions should already exist in the pipeline; the methodology defines them as:

```
Energy (kWh)      = (power_W × nodes / 1000) × (runtime_minutes / 60)
Emissions (gCO2e) = Energy × grid_carbon_intensity × PUE
```

If that value isn't currently carried through to the scoring stage, wire it through.

## Step 2 — Replace the weighted sum with distance-to-ideal

Swap the linear aggregation for a Euclidean (L2) compromise-programming score:

```python
import math

BALANCED_WEIGHTS = {
    "runtime":   0.35,
    "cost":      0.35,
    "emissions": 0.20,
    "renewable": 0.10,
}

def balanced_score(runtime_score, cost_score, emissions_score, renewable_penalty):
    """
    Compromise-programming (L2 / TOPSIS-style) distance from the ideal point.

    Every component is min-max normalised to [0, 1] where 0 is best.
    The ideal point is therefore the origin. Squaring each deviation
    penalises candidates that are excellent on one criterion and poor on
    another, so an all-round compromise outranks a single-axis extreme.

    A linear weighted sum cannot do this: it always selects a vertex of the
    Pareto front, which is why 'balanced' previously collapsed onto 'runtime'.
    """
    w = BALANCED_WEIGHTS
    return math.sqrt(
        w["runtime"]   * runtime_score      ** 2
        + w["cost"]      * cost_score         ** 2
        + w["emissions"] * emissions_score    ** 2
        + w["renewable"] * renewable_penalty  ** 2
    )
```

Keep the weights at 0.35 / 0.35 / 0.20 / 0.10 so the documented weighting rationale still holds — only the aggregation changes.

## Step 3 — Fix the tie-break

The balanced tie-break must not fall through to runtime. Use, in order: lowest predicted emissions → lowest predicted cost → lowest predicted runtime → deterministic key (e.g. cloud, region, machine type, nodes) so results are reproducible across runs.

## Step 4 — Guard degenerate normalisation

Where `max == min` across the candidate set, min–max normalisation currently divides by zero or clamps. Make it return `0.0` for every candidate on that criterion (all equal = no discrimination, no penalty). Apply this consistently and make sure it doesn't alter the three existing goals' outputs.

---

## Step 5 — Verify

Actually run these — do not reason about what the output would be. Execute the code and paste the real results.

1. **Regression check.** For a fixed scenario, confirm the top-15 output for `cost`, `runtime` and `carbon` is byte-identical before and after your changes. Dump each goal's output to a file on the pre-fix commit, re-dump after, and `diff` them. If any differ, you have changed shared code — isolate the balanced path.

   Add this as a permanent regression test so the three published goals can't drift again.

2. **Divergence check across scenarios.** Run all four goals across every benchmarked scenario (there are 21; a mean of ~32.8 candidates are scored per scenario). Produce a table:

   | Scenario | Cost pick | Runtime pick | Carbon pick | Balanced pick | Balanced distinct from all three? |

   Report the fraction of scenarios where `balanced` is distinct.

3. **Regenerate the headline scenario.** For dataset size 500 MB, workload `cpu-heavy`, SLA 6 minutes, output the rank-1 row per goal with columns: Cloud, Region, Machine type, Nodes, Runtime (min), Cost (USD), Emissions (gCO₂eq), Carbon intensity (gCO₂/kWh), Renewable (%). This replaces a table in the dissertation.

4. **Screenshot the scoring function** after the change, and re-run the prototype UI with goal = Balanced and capture the Top-15 panel. Both are figures in the dissertation.

---

## Honest expectation — read this

With only two genuinely distinct candidates surviving SLA filtering, **no aggregation method can produce a third answer**. If after this fix `balanced` still coincides with `runtime` or `cost` in most scenarios, that is a legitimate finding, not a failure: it would mean cost and carbon are aligned at this workload scale, so the trade-off space is close to one-dimensional.

Report the divergence fraction from Step 5.2 honestly either way. Do not tune the weights to manufacture a different answer — a fixed, justified weighting that happens to converge is defensible; a reverse-engineered one is not.

---

## Also worth checking while you're in there

The prototype UI screenshot in the dissertation shows **Central India carbon intensity = 540** and **Southeast Asia = 480**, but the results table in the dissertation reports **Central India = 643.3** and the text elsewhere says **643 vs Singapore 481**. Two different figures for the same region. Find out which is current and whether the carbon intensity lookup changed at some point — if the reported results were generated with a different carbon dataset than the prototype currently uses, that needs resolving before anything is regenerated.
