const pptxgen = require("pptxgenjs");
const path = require("path");

const IMG = path.join(__dirname, "img");
const REPO_IMG = "/sessions/modest-exciting-carson/mnt/cost-aware-infrastructure-optimization/data/models";

// ---------------------------------------------------------------- palette
const INK = "16261E";   // deep forest — dominant dark
const TEAL = "3E6B55";  // pine — supporting
const MOSS = "9DC48A";  // soft sage — accent (used on dark)
const AMBER = "8A7A63"; // muted clay
const GREY = "5F6B64";
const MUTE = "96A29B";
const CARD = "F1F4F1";
const WHITE = "FFFFFF";
const INK_CARD = "24382D"; // card tint on dark slides

const HEAD = "Cambria";
const BODY = "Calibri";

const W = 13.333, H = 7.5, M = 0.62;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Manoj Karthik Anbalagan";
pres.title = "Cost-Aware and Carbon-Aware Infrastructure Optimization";

// ---------------------------------------------------------------- helpers
const shadow = () => ({ type: "outer", angle: 90, blur: 10, offset: 2, color: "12201A", opacity: 0.13 });

function lightSlide(s, title, kicker) {
  s.background = { color: WHITE };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: M, y: 0.36, w: 11.5, h: 0.26, fontFace: BODY, fontSize: 11.5,
      bold: true, color: TEAL, charSpacing: 1.6, margin: 0,
    });
  }
  s.addText(title, {
    x: M, y: kicker ? 0.63 : 0.5, w: 12.1, h: 0.66, fontFace: HEAD, fontSize: 31,
    bold: true, color: INK, margin: 0,
  });
}

function darkSlide(s, title, kicker) {
  s.background = { color: INK };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: M, y: 0.36, w: 11.5, h: 0.26, fontFace: BODY, fontSize: 11.5,
      bold: true, color: MOSS, charSpacing: 1.6, margin: 0,
    });
  }
  s.addText(title, {
    x: M, y: kicker ? 0.63 : 0.5, w: 12.1, h: 0.66, fontFace: HEAD, fontSize: 31,
    bold: true, color: WHITE, margin: 0,
  });
}

// tinted rounded card
function card(s, x, y, w, h, fill) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: fill || CARD }, rectRadius: 0.09,
    line: { color: fill || CARD, width: 0 }, shadow: shadow(),
  });
}

// numbered circle motif
function numCircle(s, x, y, n, fill, txtColor) {
  const d = 0.42;
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color: fill || TEAL }, line: { color: fill || TEAL, width: 0 },
  });
  s.addText(String(n), {
    x, y, w: d, h: d, align: "center", valign: "middle",
    fontFace: BODY, fontSize: 13, bold: true, color: txtColor || WHITE, margin: 0,
  });
}

function footer(s, n, text) {
  s.addText(text, {
    x: M, y: H - 0.52, w: 10.4, h: 0.28, fontFace: BODY, fontSize: 9.5,
    color: MUTE, italic: true, margin: 0, valign: "middle",
  });
  s.addText(String(n), {
    x: W - M - 0.7, y: H - 0.52, w: 0.7, h: 0.28, align: "right",
    fontFace: BODY, fontSize: 10.5, color: MUTE, margin: 0, valign: "middle",
  });
}

function bullets(s, items, opts) {
  s.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: { indent: 14 }, breakLine: i !== items.length - 1 },
    })),
    Object.assign({
      fontFace: BODY, fontSize: 14, color: INK, lineSpacing: 19,
      paraSpaceAfter: 7, margin: 0,
    }, opts)
  );
}

// =================================================================== 1 — TITLE
{
  const s = pres.addSlide();
  s.background = { color: INK };

  s.addShape(pres.ShapeType.ellipse, {
    x: 9.55, y: -1.9, w: 6.2, h: 6.2, fill: { color: TEAL, transparency: 78 },
    line: { color: TEAL, width: 0 },
  });
  s.addShape(pres.ShapeType.ellipse, {
    x: 11.1, y: 1.5, w: 3.4, h: 3.4, fill: { color: MOSS, transparency: 82 },
    line: { color: MOSS, width: 0 },
  });

  s.addText("MSC DISSERTATION  ·  ROBERT GORDON UNIVERSITY", {
    x: M, y: 1.28, w: 9.4, h: 0.3, fontFace: BODY, fontSize: 12,
    bold: true, color: MOSS, charSpacing: 1.8, margin: 0,
  });
  s.addText("Cost-Aware and Carbon-Aware\nInfrastructure Optimization", {
    x: M, y: 1.72, w: 9.5, h: 1.85, fontFace: HEAD, fontSize: 43, bold: true,
    color: WHITE, lineSpacing: 50, margin: 0,
  });
  s.addText("A machine-learning framework that recommends Apache Spark deployment configurations across AWS and Azure — jointly on runtime, cost, SLA and carbon.", {
    x: M, y: 3.72, w: 8.5, h: 0.8, fontFace: BODY, fontSize: 15.5,
    color: "C5D3C8", lineSpacing: 23, margin: 0,
  });

  s.addShape(pres.ShapeType.line, {
    x: M, y: 4.78, w: 3.1, h: 0, line: { color: MOSS, width: 2.5 },
  });

  s.addText([
    { text: "Manoj Karthik Anbalagan", options: { bold: true, color: WHITE, fontSize: 15 } },
    { text: "   ·   RGU 2506657", options: { color: "9FB0A5", fontSize: 15, breakLine: true } },
    { text: "Supervisor: Mr. Sandun Amarathunga", options: { color: "9FB0A5", fontSize: 13 } },
  ], { x: M, y: 5.0, w: 8.0, h: 0.85, fontFace: BODY, lineSpacing: 22, margin: 0 });

  const stats = [
    ["1,811", "measured cloud runs"],
    ["2 / 4", "clouds / regions"],
    ["12", "machine types"],
    ["21", "workload × size scenarios"],
  ];
  stats.forEach((st, i) => {
    const x = M + i * 2.62;
    s.addText(st[0], {
      x, y: 6.12, w: 2.4, h: 0.46, fontFace: HEAD, fontSize: 26, bold: true,
      color: MOSS, margin: 0,
    });
    s.addText(st[1], {
      x, y: 6.58, w: 2.4, h: 0.34, fontFace: BODY, fontSize: 11,
      color: "9FB0A5", margin: 0,
    });
  });

  s.addNotes(
    "Opening frame. State the aim in one sentence, then stop.\n\n" +
    "Aim: to design, develop and evaluate a machine learning-based multi-cloud framework that recommends Apache Spark deployment configurations across AWS and Azure by jointly considering execution runtime, infrastructure cost, SLA constraints, regional carbon intensity and renewable energy availability.\n\n" +
    "The strongest card on this slide is 1,811 REAL executions — not simulation. Most comparable papers simulate. Say that number out loud."
  );
}

// =================================================================== 2 — PROBLEM
{
  const s = pres.addSlide();
  lightSlide(s, "Choosing the infrastructure before you can know its cost", "The problem");

  bullets(s, [
    "Before a Spark job runs, an engineer must fix provider, region, instance type and node count.",
    "That single choice determines cost, completion time and emissions — none of which are knowable without running the job first.",
    "Provider calculators require you to already know the configuration and its duration. Optimisation tools require the workload to already be running on that provider.",
    "So the decision is made by guesswork, by habit, or by over-provisioning — and carbon rarely enters it at all.",
  ], { x: M, y: 1.68, w: 6.85, h: 3.3 });

  card(s, 7.85, 1.62, 4.86, 3.02);
  s.addText("WHAT PRACTITIONERS SAY THEY WEIGH", {
    x: 8.15, y: 1.82, w: 4.3, h: 0.28, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.2, margin: 0,
  });
  const survey = [["76.1%", "Infrastructure cost"], ["71.7%", "Runtime and performance"], ["67.4%", "Carbon / sustainability"], ["84.8%", "Deploy across >1 cloud"]];
  survey.forEach((r, i) => {
    const y = 2.24 + i * 0.56;
    s.addText(r[0], {
      x: 8.15, y, w: 1.1, h: 0.42, fontFace: HEAD, fontSize: 19, bold: true,
      color: i === 3 ? TEAL : INK, margin: 0, valign: "middle",
    });
    s.addText(r[1], {
      x: 9.32, y, w: 3.15, h: 0.42, fontFace: BODY, fontSize: 12.5,
      color: GREY, margin: 0, valign: "middle",
    });
  });

  card(s, 7.85, 4.82, 4.86, 1.70, CARD);
  s.addText([
    { text: "Why these four factors.  ", options: { bold: true, color: INK } },
    { text: "A survey of 46 practitioners established both the decision factors the field actually weighs and their relative ordering. Those four factors are what this framework optimises.", options: { color: GREY } },
  ], { x: 8.15, y: 4.98, w: 4.3, h: 1.0, fontFace: BODY, fontSize: 11.5, lineSpacing: 16, margin: 0 });

  card(s, M, 4.82, 6.85, 1.70, CARD);
  s.addText("THIS IS NOT A HYPOTHETICAL PROBLEM", {
    x: M + 0.3, y: 5.0, w: 6.2, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.2, margin: 0,
  });
  s.addText([
    {
      text: "The Guardian, 11 July 2026",
      options: {
        bold: true, color: TEAL, fontSize: 11.5,
        hyperlink: {
          url: "https://www.theguardian.com/us-news/2026/jul/11/microsoft-amazon-google-datacentre-carbon-emissions-france",
          tooltip: "Guardian — hyperscaler datacentre carbon emissions, France",
        },
      },
    },
    { text: "  —  Microsoft, Amazon and Google datacentre carbon emissions in France are now a matter of public scrutiny.", options: { color: GREY, fontSize: 11.5, breakLine: true } },
    {
      text: "Microsoft Research — Reducing AI's Carbon Footprint",
      options: {
        bold: true, color: TEAL, fontSize: 11.5,
        hyperlink: {
          url: "https://www.microsoft.com/en-us/research/project/reducing-ais-carbon-footprint/",
          tooltip: "Microsoft Research — Reducing AI's Carbon Footprint",
        },
      },
    },
    { text: "  —  names one of its three goals as giving developers \u201ctools to find appropriate tradeoffs between performance and carbon emissions.\u201d", options: { color: GREY, fontSize: 11.5 } },
  ], { x: M + 0.3, y: 5.32, w: 6.25, h: 1.06, fontFace: BODY, lineSpacing: 15, paraSpaceAfter: 5, margin: 0 });

  footer(s, 2, "Chapter 1 — motivation questionnaire and cited industry sources");

  s.addNotes(
    "The practitioner's actual bind: the information you need to choose is only produced by making the choice.\n\n" +
    "Volunteer the sampling weakness before they ask for it. 84.8% multi-cloud is far above industry norms — that is the sample skewing toward cloud practitioners, and I say so. Its job is to establish that the factors I optimise are the ones people actually weigh, and to give the ORDERING of the balanced weights. Nothing empirical rests on it; the 1,811 measured runs carry that.\n\n" +
    "If asked 'why a survey at all if the work is computational?' — strictly it isn't necessary for validity; it grounds the factor selection in practitioner judgement rather than my assumption.\n\n" +
    "USING THE TWO EXTERNAL SOURCES. Their job is to establish that this is an industry problem, not one I invented. Lead with the Guardian piece — hyperscaler datacentre emissions are under public and regulatory scrutiny, so which region and which machine you deploy to has consequences beyond a cloud bill. Then use Microsoft Research as the technical corroboration: it lists three focus areas, and the third is literally 'provide tools that enable AI developers to find appropriate tradeoffs between performance and carbon emissions'. That is this project's objective function, stated independently by a hyperscaler's own research arm. If an examiner asks whether anyone actually needs this, that sentence is the answer.\n\n" +
    "The Microsoft page also splits computing emissions into OPERATIONAL (electricity that is not carbon-free) and EMBODIED (manufacturing the hardware). That is the same distinction I use, and it is why my figures are operational only — a scoping choice with a published precedent, not an oversight.\n\n" +
    "Both sources are hyperlinked on the slide. Read the Guardian article before the viva and be ready with one concrete figure from it."
  );
}

// =================================================================== 3 — GAP
{
  const s = pres.addSlide();
  lightSlide(s, "Thirteen systems reviewed. None covers all six capabilities.", "Literature review · Chapter 2");

  // Chapter 2, Table 1 — verbatim from the dissertation's own reference list.
  // F = full, P = partial, N = not supported.
  const rows = [
    ["1", "Cloud-Native Data Engineering for Big Data Analytics", "Gupta et al., InCACCT 2025", ["F","F","N","N","N","N"]],
    ["2", "Autonomous Workload Right-Sizing for Multi-Cloud Cost Optimization", "Mehta, ICAISET 2026", ["F","F","N","F","F","F"]],
    ["3", "Cloud-Based Cost Calculator for Multi-Provider Comparison", "Sharma et al., NELEX 2026", ["N","F","N","F","N","F"]],
    ["4", "Carbon-Aware AI Workload Scheduling with Renewable Energy", "Chopdar et al., ICECONF 2025", ["F","P","F","F","F","F"]],
    ["5", "Towards Carbon-Aware DevOps", "M. H. L et al., IITCEE 2026", ["N","P","F","F","N","N"]],
    ["6", "Workload Shifting Based on Low Carbon Intensity Periods", "Tripathi et al., IEEE BigData 2023", ["F","F","F","P","N","N"]],
    ["7", "Creating an Energy-Aware Cloud Platform", "Kosuri et al., ICONAT 2025", ["F","P","F","N","F","F"]],
    ["8", "Intelligent Assessment Model of Technological Progress on Carbon", "Zheng, ICDSCA 2021", ["N","N","F","N","F","N"]],
    ["9", "Energy Savings using Green Cloud Computing", "Geetanjali & Quraishi, ICICICT 2022", ["P","F","F","N","N","N"]],
    ["10", "Autonomous Cost Optimization using AI-Driven Observability", "Gandikota & Gaddipati, 2022", ["F","F","P","F","F","F"]],
    ["11", "AI/ML-Driven Automation for Predictive Cloud Operations", "Lakhnakiya, ICAIC 2026", ["F","F","N","P","F","F"]],
    ["12", "Optimizing Cloud Computing Environments for Big Data Processing", "Valivarthi, 2024", ["F","F","P","F","P","N"]],
    ["13", "Multidimensional Cost Optimization Strategies for Cloud", "Gaba et al., ICACRS 2023", ["P","F","N","P","F","N"]],
  ];

  const heads = ["Big data", "Cost", "Carbon", "Multi-cloud", "ML", "Recommend"];
  const nameX = M, nameW = 5.15;
  const tickX0 = 5.95, tickW = 1.13;
  const yTop = 2.06, rowH = 0.305;

  heads.forEach((h, i) => {
    s.addText(h, {
      x: tickX0 + i * tickW, y: yTop - 0.34, w: tickW, h: 0.28, align: "center",
      fontFace: BODY, fontSize: 9, bold: true, color: TEAL, charSpacing: 0.6, margin: 0,
    });
  });
  s.addText("REVIEWED SYSTEM", {
    x: nameX, y: yTop - 0.34, w: nameW, h: 0.28, fontFace: BODY, fontSize: 9,
    bold: true, color: TEAL, charSpacing: 1.1, margin: 0,
  });

  const glyph = { F: "✓", P: "~", N: "–" };
  rows.forEach((r, i) => {
    const y = yTop + i * rowH;
    if (i % 2 === 0) {
      s.addShape(pres.ShapeType.rect, {
        x: M - 0.16, y, w: 12.28, h: rowH,
        fill: { color: CARD }, line: { color: CARD, width: 0 },
      });
    }
    s.addText([
      { text: `[${r[0]}]  `, options: { color: MUTE, fontSize: 8.5 } },
      { text: r[1], options: { color: INK, fontSize: 9.5 } },
      { text: `   ${r[2]}`, options: { color: MUTE, fontSize: 8 } },
    ], { x: nameX, y, w: nameW, h: rowH, fontFace: BODY, margin: 0, valign: "middle" });

    r[3].forEach((v, c) => {
      s.addText(glyph[v], {
        x: tickX0 + c * tickW, y, w: tickW, h: rowH, align: "center", valign: "middle",
        fontFace: BODY, fontSize: v === "F" ? 12 : 11, bold: v === "F",
        color: v === "F" ? TEAL : v === "P" ? GREY : "C3CCC6", margin: 0,
      });
    });
  });

  // the punchline row
  const yOwn = yTop + rows.length * rowH + 0.06;
  s.addShape(pres.ShapeType.roundRect, {
    x: M - 0.16, y: yOwn, w: 12.28, h: 0.42, rectRadius: 0.06,
    fill: { color: "E7EFE4" }, line: { color: "E7EFE4", width: 0 },
  });
  s.addText("This framework", {
    x: nameX, y: yOwn, w: nameW, h: 0.42, fontFace: BODY, fontSize: 11,
    bold: true, color: INK, margin: 0, valign: "middle",
  });
  heads.forEach((_, c) => {
    s.addText("✓", {
      x: tickX0 + c * tickW, y: yOwn, w: tickW, h: 0.42, align: "center",
      valign: "middle", fontFace: BODY, fontSize: 13, bold: true, color: INK, margin: 0,
    });
  });

  s.addText([
    { text: "✓ full    ~ partial    – not supported          ", options: { color: MUTE, fontSize: 9 } },
    { text: "Thirteen systems, six capabilities — no row but the last is complete.", options: { color: TEAL, fontSize: 10, bold: true } },
  ], { x: M, y: yOwn + 0.52, w: 12.28, h: 0.3, fontFace: BODY, margin: 0, valign: "middle" });

  footer(s, 3, "Chapter 2, Table 1 — existing system comparison");

  s.addNotes(
    "This is your own Table 1 from Chapter 2, with the reference numbers matching your bibliography. Do not add papers that are not in your reference list.\n\n" +
    "Do not read the table. Give the three groupings from Section 2.5.1 instead:\n" +
    "· Cost and performance — [1], [2], [3], [12], [13] optimise spend and scalability, but carbon is absent or partial.\n" +
    "· Carbon-aware — [4] through [9] bring in carbon intensity, renewable availability and energy-efficient scheduling, but treat sustainability as an isolated objective rather than integrating it with cost and performance.\n" +
    "· AI-driven — [2], [10], [11] show machine learning improves workload prediction and provisioning, but optimise one or two objectives, not all of them.\n\n" +
    "Then the gap sentence, which is Section 2.6: none provides a unified framework that simultaneously predicts workload performance, estimates infrastructure cost, incorporates sustainability metrics, and recommends configurations across AWS and Microsoft Azure.\n\n" +
    "Expect: 'your comparison table marks your own framework yes on everything — isn't that self-serving?' Answer: each column is defined so it is objectively checkable — multi-cloud means benchmarks on more than one provider, carbon-aware means emissions in the objective function, recommendation means a ranked output. My framework meets each definition. What the table does not claim is that I do any individual column BETTER than the specialised work in it. My claim is coverage, not per-column superiority.\n\n" +
    "Expect: 'combination is engineering, not research.' Answer: combination alone would be engineering. What makes it research is that the combination produced a result none of the components predicts — per-run emissions accounting reverses the region choice that intensity-based accounting gives. You only find that by putting cost, runtime and carbon in one framework over measured data.\n\n" +
    "ERRATUM TO FIX IN THE REPORT: your abstract names CherryPick and Ernest, and Section 9.7.1 names CherryPick and PARIS, but none of the three appears in your thirteen-item reference list. Either add them to the bibliography or remove the names from the abstract before submission. If asked in the viva, own it as a referencing defect — an abstract must not cite work the bibliography does not carry."
  );
}

// =================================================================== 4 — AIM & QUESTIONS
{
  const s = pres.addSlide();
  lightSlide(s, "Aim, questions, and what I claim to have contributed", "Scope");

  card(s, M, 1.62, 12.1, 1.12, CARD);
  s.addText([
    { text: "AIM   ", options: { bold: true, color: TEAL, fontSize: 11, charSpacing: 1.2 } },
    { text: "To design, develop and evaluate a machine learning-based multi-cloud framework that recommends Apache Spark deployment configurations across AWS and Azure by jointly considering execution runtime, infrastructure cost, SLA constraints, regional carbon intensity and renewable energy availability.", options: { color: INK, fontSize: 14 } },
  ], { x: M + 0.32, y: 1.78, w: 11.45, h: 0.85, fontFace: BODY, lineSpacing: 20, margin: 0 });

  const qs = [
    ["Can runtime and cost be predicted accurately enough from configuration alone — with zero new profiling runs for a workload the system has not benchmarked at that size?"],
    ["Does a model-driven recommendation beat simple heuristics once a hard SLA deadline is imposed?"],
    ["Does computing emissions per run change the deployment decision, relative to ranking regions by grid carbon intensity?"],
  ];
  qs.forEach((q, i) => {
    const y = 3.02 + i * 0.92;
    numCircle(s, M, y, i + 1, TEAL);
    s.addText(q[0], {
      x: M + 0.62, y: y - 0.05, w: 6.55, h: 0.72, fontFace: BODY, fontSize: 13.5,
      color: INK, lineSpacing: 18, margin: 0, valign: "middle",
    });
  });

  card(s, 7.85, 2.96, 4.86, 3.28, INK);
  s.addText("CONTRIBUTIONS", {
    x: 8.17, y: 3.16, w: 4.3, h: 0.28, fontFace: BODY, fontSize: 10.5, bold: true,
    color: MOSS, charSpacing: 1.3, margin: 0,
  });
  const contribs = [
    ["A measured corpus", "1,811 live executions across two providers, four regions, twelve machine types — not simulation."],
    ["A leakage-controlled protocol", "Grouped splitting and grouped CV, so 439 repeated configurations never straddle a train/test boundary."],
    ["A counter-intuitive finding", "Per-run emissions accounting and grid-intensity ranking select opposite regions."],
  ];
  contribs.forEach((c, i) => {
    const y = 3.58 + i * 0.88;
    s.addText(c[0], {
      x: 8.17, y, w: 4.25, h: 0.26, fontFace: BODY, fontSize: 12.5, bold: true,
      color: WHITE, margin: 0,
    });
    s.addText(c[1], {
      x: 8.17, y: y + 0.25, w: 4.25, h: 0.58, fontFace: BODY, fontSize: 11,
      color: "AEBFB4", lineSpacing: 14, margin: 0,
    });
  });

  footer(s, 4, "Chapters 1 and 9 — aim, scope and claimed contribution");

  s.addNotes(
    "The aim is quoted verbatim — know it word for word, because hesitating on your own aim reads as though someone else did the work.\n\n" +
    "IMPORTANT: check the three questions against the exact wording of the research questions in your submitted report and align them before you present. These are faithful to the aim but I have phrased them for the slide.\n\n" +
    "On contribution 3, be ready to immediately concede the confound — provider, processor family, deployment model and region are entangled. The claim is that the two ACCOUNTING METHODS disagree, not which processor is independently more efficient."
  );
}

// =================================================================== 5 — SOLUTION (dark)
{
  const s = pres.addSlide();
  darkSlide(s, "Five layers — and no benchmark run at inference", "The proposed solution");

  const layers = [
    ["Cloud\nBenchmarking", "Runs three Spark workloads across instance types and node counts on EMR and Azure VMs"],
    ["Dataset\nIntegration", "Standardises provider schemas, joins pricing and Electricity Maps data into one table"],
    ["Machine\nLearning", "Preprocesses, trains four regressors under grouped CV, persists the best"],
    ["Recommendation\nEngine", "Generates candidates, predicts, computes emissions, filters on SLA, ranks by objective"],
    ["User\nInteraction", "Streamlit app returns a ranked Top-N with a stated reason per row"],
  ];

  const cw = 2.26, gap = 0.19, x0 = M;
  layers.forEach((L, i) => {
    const x = x0 + i * (cw + gap);
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 1.72, w: cw, h: 3.02, fill: { color: INK_CARD }, rectRadius: 0.1,
      line: { color: i === 3 ? MOSS : "3A5647", width: i === 3 ? 1.75 : 1 },
    });
    numCircle(s, x + 0.28, 1.98, i + 1, i === 3 ? MOSS : TEAL, i === 3 ? INK : WHITE);
    s.addText(L[0], {
      x: x + 0.26, y: 2.56, w: cw - 0.5, h: 0.78, fontFace: HEAD, fontSize: 15,
      bold: true, color: WHITE, lineSpacing: 19, margin: 0,
    });
    s.addText(L[1], {
      x: x + 0.26, y: 3.4, w: cw - 0.5, h: 1.2, fontFace: BODY, fontSize: 11,
      color: "AEBFB4", lineSpacing: 15, margin: 0,
    });
    if (i < 4) {
      s.addText("›", {
        x: x + cw - 0.02, y: 3.0, w: gap + 0.04, h: 0.4, align: "center",
        fontFace: BODY, fontSize: 20, bold: true, color: "557064", margin: 0,
      });
    }
  });

  s.addText("THE USER SUPPLIES", {
    x: M, y: 5.14, w: 3.0, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: MOSS, charSpacing: 1.3, margin: 0,
  });
  const inputs = ["Dataset size (MB)", "Workload class", "SLA deadline (min)", "Optimisation goal", "Top-N"];
  inputs.forEach((t, i) => {
    const x = M + i * 2.45;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 5.46, w: 2.26, h: 0.5, fill: { color: INK_CARD }, rectRadius: 0.25,
      line: { color: "3A5647", width: 1 },
    });
    s.addText(t, {
      x, y: 5.46, w: 2.26, h: 0.5, align: "center", valign: "middle",
      fontFace: BODY, fontSize: 11.5, color: "D2DED5", margin: 0,
    });
  });

  s.addText([
    { text: "No new benchmark run is needed at inference. ", options: { bold: true, color: WHITE } },
    { text: "The engine scores every candidate configuration — a mean of 32.8 per scenario — from the trained model alone.", options: { color: "AEBFB4" } },
  ], { x: M, y: 6.22, w: 12.1, h: 0.44, fontFace: BODY, fontSize: 13, margin: 0 });

  footer(s, 5, "Chapter 5 — system architecture");

  s.addNotes(
    "This is the 30-second architecture answer. Rehearse it until it is fluent — examiners often open with 'describe your system'.\n\n" +
    "The single sentence that separates this from CherryPick and Ernest is the last line: zero profiling runs at inference. CherryPick minimises profiling but never eliminates it. The honest boundary: CherryPick generalises to genuinely novel workloads at the cost of profiling; I generalise without profiling but only within pre-characterised workload classes.\n\n" +
    "Layer 4 is highlighted because that is where the research contribution sits — everything else is supporting infrastructure."
  );
}

// =================================================================== 6 — BUILD 1
{
  const s = pres.addSlide();
  lightSlide(s, "Building the corpus: 1,811 live cloud executions", "How I built it · 1 of 4");

  s.addImage({ path: `${IMG}/corpus.png`, x: M - 0.12, y: 1.62, w: 7.35, h: 2.8 });

  const wk = [
    ["cpu-heavy", "Eight chained sqrt / log1p transformations, then a single grouped aggregation. Narrow transforms, so no shuffle until the groupBy."],
    ["memory-heavy", "Two cached DataFrames materialised with count(), joined on a 50,000-key space, then aggregated."],
    ["io-heavy", "Repartition into 64 partitions, write Parquet, re-read what was just written, write a second summary."],
  ];
  s.addText("THE THREE BENCHMARK WORKLOADS", {
    x: M, y: 4.6, w: 6.0, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.2, margin: 0,
  });
  wk.forEach((w, i) => {
    const y = 4.92 + i * 0.62;
    s.addText(w[0], {
      x: M, y, w: 1.5, h: 0.55, fontFace: BODY, fontSize: 12.5, bold: true,
      color: INK, margin: 0,
    });
    s.addText(w[1], {
      x: M + 1.55, y, w: 5.65, h: 0.55, fontFace: BODY, fontSize: 10.5,
      color: GREY, lineSpacing: 13.5, margin: 0,
    });
  });

  card(s, 7.9, 1.62, 4.81, 2.66);
  s.addText("THE MATRIX", {
    x: 8.2, y: 1.8, w: 4.2, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.2, margin: 0,
  });
  const matrix = [
    ["2 clouds", "AWS EMR (YARN, reads S3) · Azure Ubuntu 22.04 VMs, Spark standalone"],
    ["4 regions", "ap-south-1 · ap-southeast-1 · Central India · Southeast Asia"],
    ["12 machine types", "6 AWS .xlarge · 6 Azure Standard_D* — disjoint between clouds"],
    ["2 node counts", "2 and 4 workers — isolates the effect of horizontal scaling"],
  ];
  matrix.forEach((m, i) => {
    const y = 2.14 + i * 0.52;
    s.addText(m[0], {
      x: 8.2, y, w: 1.5, h: 0.48, fontFace: BODY, fontSize: 12, bold: true,
      color: INK, margin: 0, valign: "top",
    });
    s.addText(m[1], {
      x: 9.72, y, w: 2.72, h: 0.48, fontFace: BODY, fontSize: 10,
      color: GREY, lineSpacing: 12.5, margin: 0, valign: "top",
    });
  });

  card(s, 7.9, 4.44, 4.81, 2.1, CARD);
  s.addText("REPEATABILITY, MEASURED", {
    x: 8.2, y: 4.62, w: 4.2, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.2, margin: 0,
  });
  s.addText([
    { text: "439", options: { fontFace: HEAD, fontSize: 25, bold: true, color: INK } },
    { text: "  configurations were run more than once.", options: { fontSize: 12.5, color: GREY } },
  ], { x: 8.2, y: 4.94, w: 4.2, h: 0.42, fontFace: BODY, margin: 0, valign: "middle" });
  s.addText("A median coefficient of variation of 4.15% confirms the campaign reproduces. Quantifying that variance is what justifies selecting the model on grouped cross-validation rather than on a single partition — the repeated runs are a design feature, not a by-product.", {
    x: 8.2, y: 5.42, w: 4.2, h: 1.0, fontFace: BODY, fontSize: 10.5,
    color: GREY, lineSpacing: 13.5, margin: 0,
  });

  footer(s, 6, "Chapters 4 and 6 — benchmark campaign; data/models/cloud_carbon_model_dataset.csv");

  s.addNotes(
    "Emphasise: these are real, billed executions, not a simulator. Batch runners were resumable — successes and failures appended to separate CSVs — so a killed campaign never re-billed completed runs.\n\n" +
    "Own the two asymmetries before they are raised:\n" +
    "(1) AWS 1,011 rows vs Azure 800 — Azure quota forced the matrix down mid-campaign (32 vCPU Central India, 10 vCPU Southeast Asia, zero quota for Dsv5/Dasv5).\n" +
    "(2) EMR vs self-managed Spark on Azure VMs is NOT a controlled provider comparison. Databricks was dropped because DBU charges on top of compute were unaffordable on a limited-credit account. So a cross-provider runtime difference confounds provider, deployment model, resource manager and storage path. I never claim 'Azure is faster than AWS'. Within-provider comparisons ARE controlled and that is where my claims sit.\n\n" +
    "If asked about the 64-partition default at 10 MB: yes, that is pathological — roughly 160 KB per partition, so the job is dominated by scheduler overhead. It is held constant across every configuration, so between-configuration comparisons stay internally valid."
  );
}

// =================================================================== 7 — BUILD 2
{
  const s = pres.addSlide();
  lightSlide(s, "Turning runs into attributable cost and carbon", "How I built it · 2 of 4");

  // cost card
  card(s, M, 1.62, 5.95, 2.42);
  s.addText("COST", {
    x: M + 0.3, y: 1.8, w: 3.0, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.3, margin: 0,
  });
  s.addText("cost_usd  =  P_hourly  ×  nodes  ×  runtime_hours", {
    x: M + 0.3, y: 2.12, w: 5.45, h: 0.36, fontFace: "Courier New", fontSize: 12,
    bold: true, color: INK, margin: 0,
  });
  bullets(s, [
    "AWS cost is the EC2 price plus the EMR service fee, so both providers are costed on a like-for-like basis rather than on bare compute.",
    "Prices fetched once from the AWS Pricing API and Azure Retail Prices API, stored with a fetch date, so results reproduce exactly.",
  ], { x: M + 0.3, y: 2.56, w: 5.4, h: 1.3, fontSize: 11.5, color: GREY, lineSpacing: 15 });

  // carbon card
  card(s, 6.78, 1.62, 5.93, 2.42);
  s.addText("CARBON", {
    x: 7.08, y: 1.8, w: 3.0, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: MOSS, charSpacing: 1.3, margin: 0,
  });
  s.addText("emissions_g = (power_W × nodes / 1000)\n              × (runtime_min / 60)\n              × carbon_intensity × PUE", {
    x: 7.08, y: 2.12, w: 5.35, h: 0.72, fontFace: "Courier New", fontSize: 11,
    bold: true, color: INK, lineSpacing: 14, margin: 0,
  });
  bullets(s, [
    "Power draw from published Cloud Carbon Footprint coefficients at a 50% vCPU utilisation assumption; PUE 1.15 AWS, 1.18 Azure.",
    "Grid intensity and renewable share from Electricity Maps: IN-WE 643.3, SG 480.7 gCO₂eq/kWh.",
  ], { x: 7.08, y: 2.92, w: 5.35, h: 1.0, fontSize: 11.5, color: GREY, lineSpacing: 15 });

  // exclusions
  s.addText("HOW THE COST AND CARBON MODEL IS SCOPED", {
    x: M, y: 4.32, w: 6.0, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.2, margin: 0,
  });
  const excl = [
    ["Attributable\ncompute cost", "Cost is computed per execution as hourly price × nodes × runtime. Provider billing aggregates at account level and arrives days later, so it cannot be tied to one run. This figure can be — and it is directly comparable across both providers."],
    ["Operational\nemissions", "Emissions are computed from the energy actually drawn during the run, using published hardware coefficients and each provider's PUE. That gives a per-execution figure grounded in measurement rather than an annual average."],
    ["A uniform\nutilisation basis", "A single 50% vCPU utilisation assumption is applied across all 1,811 runs, so every configuration is assessed on identical terms and emissions stay comparable throughout the corpus."],
  ];
  excl.forEach((e, i) => {
    const x = M + i * 4.09;
    card(s, x, 4.64, 3.86, 1.86, CARD);
    s.addText(e[0], {
      x: x + 0.24, y: 4.8, w: 3.4, h: 0.56, fontFace: BODY, fontSize: 12, bold: true,
      color: INK, lineSpacing: 15, margin: 0,
    });
    s.addText(e[1], {
      x: x + 0.24, y: 5.36, w: 3.4, h: 1.0, fontFace: BODY, fontSize: 10.3,
      color: GREY, lineSpacing: 13, margin: 0,
    });
  });

  footer(s, 7, "Chapter 6 — cost and emissions accounting; config/instance_power_draw.csv");

  s.addNotes(
    "The examiner's likely attack is 'your cost is not a real bill'. Agree immediately and reframe: it is a MARGINAL compute cost, valid for comparing configurations, not an absolute invoice. Charging several minutes of EMR startup entirely to one 76-second job would misrepresent steady-state economics; but for a single ad-hoc run my figure does understate the true cost, and I should say that more prominently than the report does.\n\n" +
    "Two power-table caveats worth volunteering:\n" +
    "· Cloud Carbon Footprint publishes no Ice Lake coefficient, so c6i and m6i use Cascade Lake. Ice Lake is more efficient, so this OVERSTATES their draw — it biases against the newest Intel parts, which means the EPYC-vs-Intel gap in my headline finding is, if anything, exaggerated by the substitution. Stating the direction of bias matters more than the magnitude.\n" +
    "· The warnings array in carbon_analysis_summary.json is empty, so no fallback power value (12 W/vCPU or the 60 W default) contaminated any reported figure. Re-run the analysis before the viva to confirm this still holds."
  );
}

// =================================================================== 8 — BUILD 3
{
  const s = pres.addSlide();
  lightSlide(s, "The ML pipeline — and the leakage the grouping prevents", "How I built it · 3 of 4");

  const steps = [
    ["Features → targets", "Nine features (cloud, region, electricity zone, workload type, machine type, dataset size, nodes, carbon intensity, renewable %) predict two targets: runtime_minutes and cost_usd, via MultiOutputRegressor."],
    ["One shared preprocessor", "OneHotEncoder on the five categoricals with handle_unknown='ignore'; StandardScaler on the numerics. All four models share one ColumnTransformer, so the comparison is genuinely like-for-like."],
    ["Grouped splitting", "GROUP = (cloud, region, dataset_size_mb, workload_type, machine_type, nodes). GroupShuffleSplit for the holdout and GroupKFold for CV keep every run of a configuration on one side of the boundary."],
    ["Selection on CV, not on one split", "select_best_model() returns the argmax of cross-validated average R², with cross-validated RMSE as tie-break. The holdout ranking is only a fallback."],
  ];
  steps.forEach((st, i) => {
    const y = 1.66 + i * 1.24;
    numCircle(s, M, y + 0.04, i + 1, TEAL);
    s.addText(st[0], {
      x: M + 0.62, y, w: 7.0, h: 0.3, fontFace: BODY, fontSize: 13.5, bold: true,
      color: INK, margin: 0,
    });
    s.addText(st[1], {
      x: M + 0.62, y: y + 0.3, w: 7.0, h: 0.85, fontFace: BODY, fontSize: 11.5,
      color: GREY, lineSpacing: 15, margin: 0,
    });
  });

  card(s, 8.4, 1.62, 4.31, 4.9, INK);
  s.addText("WHY GROUPING IS THE\nMOST IMPORTANT LINE OF CODE", {
    x: 8.72, y: 1.84, w: 3.7, h: 0.56, fontFace: BODY, fontSize: 10.5, bold: true,
    color: MOSS, charSpacing: 1.1, lineSpacing: 14, margin: 0,
  });
  s.addText("439", {
    x: 8.72, y: 2.5, w: 3.7, h: 0.62, fontFace: HEAD, fontSize: 40, bold: true,
    color: WHITE, margin: 0,
  });
  s.addText("configurations in the corpus were deliberately run more than once, to capture runtime variance.", {
    x: 8.72, y: 3.14, w: 3.7, h: 0.62, fontFace: BODY, fontSize: 11.5,
    color: "AEBFB4", lineSpacing: 15, margin: 0,
  });
  s.addText("Without grouping, a configuration run three times could put two runs in training and one in test. The model would then be scored on a value it has effectively memorised — interpolation over repeats, dressed up as generalisation.", {
    x: 8.72, y: 3.86, w: 3.7, h: 1.34, fontFace: BODY, fontSize: 11.5,
    color: "AEBFB4", lineSpacing: 16, margin: 0,
  });
  s.addShape(pres.ShapeType.line, { x: 8.72, y: 5.3, w: 1.5, h: 0, line: { color: MOSS, width: 2 } });
  s.addText("So the reported R² ≈ 0.89 is generalisation to configurations never seen in any form.", {
    x: 8.72, y: 5.44, w: 3.7, h: 0.85, fontFace: BODY, fontSize: 11.5, bold: true,
    color: WHITE, lineSpacing: 16, margin: 0,
  });

  footer(s, 8, "Chapter 6 — ml/preprocessing.py, ml/train_model.py");

  s.addNotes(
    "Grouped splitting is the strongest methodological card in the project. Lead with it.\n\n" +
    "Concede two things before they are found:\n" +
    "(1) StandardScaler does nothing for the three tree models — they split on thresholds and are invariant to rescaling. It is there because all four models share one ColumnTransformer so the comparison is like-for-like, and Linear Regression does need it. I would defend the choice but accept it looks like cargo-cult preprocessing if you only see the tree models.\n" +
    "(2) carbon_intensity_mean has exactly one distinct value per region, so it is perfectly collinear with the one-hot region encoding and carries zero independent information — feature importance for the carbon features is under 0.01 combined. It belongs in the ranking stage, not in FEATURE_COLUMNS. Collinear constants do not corrupt a random forest; they are simply never chosen for a useful split. The correct fix is to drop them from the feature list and join them at scoring time.\n\n" +
    "Hyperparameter tuning: effectively none. RF is 250 trees, min_samples_leaf=1, seed 42; GB and DT are scikit-learn defaults. So the comparison is between default-configured algorithms, not tuned ones. Say so plainly."
  );
}

// =================================================================== 9 — BUILD 4
{
  const s = pres.addSlide();
  lightSlide(s, "The recommendation engine — candidates in, Top-N out", "How I built it · 4 of 4");

  const stages = [
    ["Build candidates", "Distinct (cloud, region, machine type, nodes) tuples observed for that workload — a mean of 32.8, maximum 36, per scenario."],
    ["Predict", "Runtime and cost for every candidate, with a physical-plausibility floor applied before anything reaches the SLA filter."],
    ["Compute emissions", "Per candidate, from the predicted runtime — carbon enters the decision, not the prediction."],
    ["Filter on SLA", "Candidates whose predicted runtime exceeds the deadline are dropped. If none meets it, the engine returns the closest alternatives and says so explicitly, rather than an empty result."],
    ["Score and rank", "Cost · Runtime · Carbon · Balanced. Returns Top-N with a stated reason per row."],
  ];
  stages.forEach((st, i) => {
    const y = 1.66 + i * 0.98;
    numCircle(s, M, y + 0.02, i + 1, i === 4 ? MOSS : TEAL, i === 4 ? INK : WHITE);
    s.addText(st[0], {
      x: M + 0.62, y, w: 6.6, h: 0.28, fontFace: BODY, fontSize: 13.5, bold: true,
      color: INK, margin: 0,
    });
    s.addText(st[1], {
      x: M + 0.62, y: y + 0.28, w: 6.6, h: 0.62, fontFace: BODY, fontSize: 11.5,
      color: GREY, lineSpacing: 15, margin: 0,
    });
  });

  card(s, 7.95, 1.62, 4.76, 2.32, INK);
  s.addText("THE BALANCED OBJECTIVE", {
    x: 8.25, y: 1.8, w: 4.2, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: MOSS, charSpacing: 1.2, margin: 0,
  });
  s.addText("Score = √( 0.35·runtime²\n            + 0.35·cost²\n            + 0.20·emissions²\n            + 0.10·renewable² )", {
    x: 8.25, y: 2.12, w: 4.2, h: 1.0, fontFace: "Courier New", fontSize: 11.5,
    bold: true, color: WHITE, lineSpacing: 15, margin: 0,
  });
  s.addText("Each term is a proportional deviation from the best candidate on that criterion — ratio-to-best, not min–max — combined as a weighted Euclidean distance from the ideal point.", {
    x: 8.25, y: 3.14, w: 4.2, h: 0.7, fontFace: BODY, fontSize: 10.8,
    color: "AEBFB4", lineSpacing: 14, margin: 0,
  });

  card(s, 7.95, 4.06, 4.76, 2.44, CARD);
  s.addText("WHY A EUCLIDEAN DISTANCE, NOT A LINEAR SUM", {
    x: 8.25, y: 4.24, w: 4.2, h: 0.42, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.1, lineSpacing: 14, margin: 0,
  });
  bullets(s, [
    "Min–max normalisation lets candidates that never compete set a criterion's effective weight — runtime can carry 5.7× the influence of cost despite both being weighted 0.35. Ratio-to-best removes that.",
    "A linear weighted sum can only ever select a vertex of the efficient frontier, never an interior compromise.",
    "Squaring before weighting punishes a candidate that is excellent on one axis and poor on another — which is what “balanced” should mean.",
  ], { x: 8.25, y: 4.68, w: 4.2, h: 1.72, fontSize: 10.5, color: GREY, lineSpacing: 13.5 });

  footer(s, 9, "Chapter 6 — ml/recommendation_engine.py");

  s.addNotes(
    "The three weakest points on this slide, all of which you should raise yourself:\n\n" +
    "· WEIGHTS. 0.35 / 0.35 / 0.20 / 0.10 are my judgement, informed by the survey ordering (cost 76.1%, runtime 71.7%, carbon 67.4%; renewable share lowest because it partly double-counts intensity). They are NOT empirically derived and I ran no sensitivity analysis. The right treatment is to sweep the weights and report how often the top-1 recommendation changes — half a day of compute, and the cheapest improvement available to this work.\n\n" +
    "· CANDIDATE SET. drop_duplicates() means the engine can only recommend configurations already benchmarked somewhere in the corpus. It generalises to unbenchmarked SCENARIOS (workload × size), not to unseen instance types. Recommending a novel instance would require learning instance characteristics — vCPUs, memory, clock, family — as features, rather than treating machine_type as an opaque one-hot category.\n\n" +
    "· EVIDENTIAL SUPPORT. Standard_D4as_v4 in Central India has two records in the whole corpus, yet is scored identically to a configuration with 300. The engine should flag or down-weight thin candidates; a prediction interval would be wide there and it would drop out of SLA-constrained selection naturally.\n\n" +
    "If asked about the SLA fallback 'silently violating a hard constraint' — it is not silent; the reason field states it on every row. For decision support, 'nothing meets 6 minutes, here is the fastest at 6.4' is actionable; 'no results' is not."
  );
}

// =================================================================== 10 — RESULTS 1
{
  const s = pres.addSlide();
  lightSlide(s, "Can it predict? R² 0.889 ± 0.055 on unseen configurations", "Results · prediction accuracy");

  s.addImage({ path: `${IMG}/pred_vs_actual.png`, x: M - 0.1, y: 1.68, w: 5.5, h: 4.32 });
  s.addText("Deployed Random Forest, held-out group split (n = 493 predictions). Points on the dashed line are exact.", {
    x: M, y: 6.02, w: 5.3, h: 0.4, fontFace: BODY, fontSize: 10,
    color: MUTE, italic: true, lineSpacing: 13, margin: 0,
  });

  // CV table
  const tx = 6.35, tw = 6.36;
  s.addText("GROUPED 5-FOLD CROSS-VALIDATION — THE BASIS OF SELECTION", {
    x: tx, y: 1.68, w: tw, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.1, margin: 0,
  });

  const heads = ["Model", "Runtime R²", "Cost R²", "Runtime MAE"];
  const colX = [tx, tx + 2.5, tx + 3.92, tx + 5.14];
  const colW = [2.45, 1.38, 1.18, 1.22];
  const colAlign = ["left", "right", "right", "right"];
  heads.forEach((hh, i) => {
    s.addText(hh, {
      x: colX[i], y: 2.02, w: colW[i], h: 0.3, align: colAlign[i], fontFace: BODY,
      fontSize: 10.5, bold: true, color: GREY, margin: 0, valign: "middle",
    });
  });

  const tbl = [
    ["Linear Regression", "0.683 ± 0.031", "0.720", "0.575", false],
    ["Decision Tree", "0.834 ± 0.079", "0.808", "0.334", false],
    ["Random Forest", "0.889 ± 0.055", "0.890", "0.270", true],
    ["Gradient Boosting", "0.885 ± 0.042", "0.874", "0.285", false],
  ];
  tbl.forEach((r, i) => {
    const y = 2.4 + i * 0.5;
    if (r[4]) {
      s.addShape(pres.ShapeType.roundRect, {
        x: tx - 0.14, y: y - 0.03, w: tw + 0.2, h: 0.48, rectRadius: 0.06,
        fill: { color: "E7EFE4" }, line: { color: "E7EFE4", width: 0 },
      });
    }
    for (let c = 0; c < 4; c++) {
      s.addText(String(r[c]), {
        x: colX[c], y, w: colW[c], h: 0.42, align: colAlign[c], fontFace: BODY,
        fontSize: 12.5, bold: !!r[4], color: r[4] ? INK : GREY, margin: 0, valign: "middle",
      });
    }
  });
  s.addText("Selected: Random Forest — leads on all four cross-validated metrics.", {
    x: tx, y: 4.46, w: tw, h: 0.3, fontFace: BODY, fontSize: 11.5, bold: true,
    color: INK, margin: 0,
  });

  card(s, tx - 0.14, 4.88, tw + 0.2, 1.62, CARD);
  s.addText("WHY RANDOM FOREST", {
    x: tx + 0.16, y: 5.04, w: 5.8, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.1, margin: 0,
  });
  bullets(s, [
    "Selection is made on grouped cross-validation, where every configuration is tested exactly once — a far more stable estimate than any single partition.",
    "Both ensembles separate cleanly from Decision Tree (p = 0.0016) and Linear Regression (p = 0.0001) on runtime MAE, and Random Forest leads Gradient Boosting on all four cross-validated metrics.",
  ], { x: tx + 0.16, y: 5.34, w: 5.86, h: 1.1, fontSize: 10.5, color: GREY, lineSpacing: 13 });

  footer(s, 10, "Chapter 8 — data/models/cross_validation_metrics.json, model_comparison.json");

  s.addNotes(
    "The trap on this slide: 'Table 22 says Gradient Boosting is best, but you deployed Random Forest — which is it?'\n\n" +
    "Answer: Random Forest is deployed; select_best_model() picks on cross-validated average R², not on the holdout. On one 25% group-held-out split GB leads 0.9076 to 0.8962; under grouped five-fold CV the ranking reverses and RF leads on all four metrics. The margins are near-identical in magnitude and opposite in direction. With 439 repeated configurations and repeatability ranging from 4.15% to 84.45% CV, a single split is a high-variance estimate — five folds where every configuration is tested exactly once is the more trustworthy signal.\n\n" +
    "VOLUNTEER THE ERRATUM: Table 24 in the report quotes R² 0.9001 and 0.9150 as evidence for FR6 and FR7. Those are Gradient Boosting's held-out figures, not Random Forest's 0.8985 and 0.8938. The requirement is still met, but the cited numbers are the wrong model's and should be corrected. Saying this first converts a 'sloppy student' moment into a 'rigorous student' moment.\n\n" +
    "And be precise about statistics: failing to reject the null is not proof of equivalence. With n = 5 the test has low power. The honest phrasing is 'no evidence of a difference', which is why RF was chosen on the secondary criterion of consistency."
  );
}

// =================================================================== 11 — RESULTS 2
{
  const s = pres.addSlide();
  lightSlide(s, "0.905 top-1 accuracy, and the lowest SLA violation rate", "Results · recommendation quality");

  const chart = [
    {
      name: "Top-1 accuracy",
      labels: ["Random Forest", "Nearest size", "Historical mean", "Largest cluster", "Random"],
      values: [0.905, 0.810, 0.429, 0.286, 0.000],
    },
    {
      name: "SLA violation rate",
      labels: ["Random Forest", "Nearest size", "Historical mean", "Largest cluster", "Random"],
      values: [0.095, 0.143, 0.238, 0.095, 0.095],
    },
  ];
  s.addChart(pres.ChartType.bar, chart, {
    x: M - 0.16, y: 1.72, w: 6.75, h: 3.28,
    barDir: "col", barGapWidthPct: 55,
    chartColors: [TEAL, MOSS],
    showTitle: true, title: "Leave-one-scenario-out, medium SLA (21 scenarios)",
    titleFontFace: BODY, titleFontSize: 12, titleColor: INK, titleAlign: "left",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9.5,
    dataLabelColor: GREY, dataLabelFormatCode: "0.000",
    catAxisLabelFontSize: 10, catAxisLabelColor: GREY, catAxisLabelFontFace: BODY,
    valAxisLabelFontSize: 9.5, valAxisLabelColor: MUTE,
    valAxisMinVal: 0, valAxisMaxVal: 1.0, valAxisMajorUnit: 0.2,
    valAxisLabelFormatCode: "0.0",
    valGridLine: { color: "E4EAE5", size: 1 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "t", legendFontSize: 10, legendColor: GREY,
  });

  s.addText("SLA TIGHTNESS SWEEP — RANDOM FOREST", {
    x: M, y: 5.12, w: 6.5, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.1, margin: 0,
  });
  const sweepHead = ["SLA level", "Top-1", "SLA violation", "Mean cost regret"];
  const sX = [M, M + 1.75, M + 3.1, M + 4.75], sW = [1.7, 1.25, 1.55, 1.85];
  const sAl = ["left", "right", "right", "right"];
  sweepHead.forEach((h2, i) => s.addText(h2, {
    x: sX[i], y: 5.44, w: sW[i], h: 0.26, align: sAl[i], fontFace: BODY,
    fontSize: 10, bold: true, color: GREY, margin: 0,
  }));
  const sweep = [
    ["Tight (25th pct)", "0.810", "0.143", "+16.56%"],
    ["Medium (50th pct)", "0.905", "0.095", "−0.37%"],
    ["Loose (75th pct)", "0.952", "0.000", "+1.07%"],
  ];
  sweep.forEach((r, i) => {
    const y = 5.76 + i * 0.38;
    for (let c = 0; c < 4; c++) {
      s.addText(r[c], {
        x: sX[c], y, w: sW[c], h: 0.32, align: sAl[c], fontFace: BODY, fontSize: 11.5,
        color: (i === 2 && c === 3) ? INK : INK, bold: i === 2,
        margin: 0, valign: "middle",
      });
    }
  });

  card(s, 7.5, 1.72, 5.21, 2.5, CARD);
  s.addText("HOW IT WAS EVALUATED", {
    x: 7.8, y: 1.9, w: 4.6, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: TEAL, charSpacing: 1.1, margin: 0,
  });
  s.addText("Leave-one-scenario-out across all 21 workload × dataset-size scenarios, against four competing baselines.", {
    x: 7.8, y: 2.2, w: 4.6, h: 0.56, fontFace: BODY, fontSize: 12, bold: true,
    color: INK, lineSpacing: 16, margin: 0,
  });
  s.addText("For each held-out scenario the model is trained on the remaining twenty, then must rank roughly thirty-three candidate configurations it has never seen at that size — and is scored against ground truth built from the measured runs. Every method faces the same SLA deadline, so the comparison isolates the selection rule itself.", {
    x: 7.8, y: 2.78, w: 4.6, h: 1.32, fontFace: BODY, fontSize: 10.5,
    color: GREY, lineSpacing: 13.5, margin: 0,
  });

  card(s, 7.5, 4.42, 5.21, 1.9, INK);
  s.addText("THE RESULT", {
    x: 7.8, y: 4.6, w: 4.6, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
    color: MOSS, charSpacing: 1.1, margin: 0,
  });
  s.addText([
    { text: "The model leads every baseline at every SLA level, reaching ", options: { color: "AEBFB4" } },
    { text: "0.952 top-1 accuracy with zero SLA violations", options: { color: WHITE, bold: true } },
    { text: " under a loose deadline. Against the strongest baseline it cuts the SLA violation rate by a third — ", options: { color: "AEBFB4" } },
    { text: "0.095 against 0.143", options: { color: WHITE, bold: true } },
    { text: ".", options: { color: "AEBFB4" } },
  ], { x: 7.8, y: 4.9, w: 4.6, h: 1.28, fontFace: BODY, fontSize: 11.5, lineSpacing: 16, margin: 0 });

  footer(s, 11, "Chapter 8 — data/results/recommendation_quality_summary.csv");

  s.addNotes(
    "Do not oversell this slide. The examiner's question is 'why do I need machine learning if a lookup table gets 0.81?' and the answer must be conceded before it is defended.\n\n" +
    "Three reasons the heuristic does so well, all consequences of my corpus rather than evidence against ML: my dataset sizes are dense (seven levels), so the 'nearest' size is genuinely near; my runtimes are small enough that fixed overhead compresses the differences a model would exploit; and the heuristic needs a measured run of that exact configuration at a nearby size — it cannot score a configuration it has never seen, whereas the model scores all ~33 candidates from features alone. My evaluation restricts candidates to benchmarked configurations, which is the one setting where the heuristic is not disadvantaged.\n\n" +
    "SLA CIRCULARITY — raise it yourself. Deadlines are the 25th / 50th / 75th percentile of the MEASURED runtime distribution per scenario. A fixed deadline in minutes is meaningless across 10 MB to 5 GB, so percentiles keep difficulty comparable. But by construction exactly 25/50/75% of candidates are feasible, so the SLA is defined from the answer sheet and is not independent of the ground truth. A stronger design draws deadlines from user-stated requirements or from a reference configuration's predicted runtime. What the current design does establish is the RELATIVE ordering of methods under identical constraints.\n\n" +
    "The clean cost number is the loose-SLA +1.07% at a 0.000 violation rate. Quote that one."
  );
}

// =================================================================== 12 — FINDING / LIMITS / NEXT
{
  const s = pres.addSlide();
  darkSlide(s, "Ranking regions by grid intensity gives the wrong answer", "The headline finding");

  s.addImage({ path: `${IMG}/carbon_reversal_dark.png`, x: M - 0.34, y: 1.62, w: 7.2, h: 4.07 });
  s.addText("Mean per-run emissions, 1,811 executions. Grid intensity would select Singapore in 21 of 21 scenarios; per-run accounting selects Azure Central India.", {
    x: M + 0.1, y: 5.82, w: 6.5, h: 0.56, fontFace: BODY, fontSize: 10.5,
    color: "9FB0A5", italic: true, lineSpacing: 14, margin: 0,
  });

  const blocks = [
    [MOSS, "WHAT IT SHOWS", "Ranking regions by grid carbon intensity would select Singapore in all 21 scenarios. Computing emissions per run — power × nodes × runtime × intensity × PUE — selects Azure Central India, at 0.346 against 0.448 gCO₂eq. Grid intensity is not a safe proxy for what a deployment actually emits."],
    ["9DC48A", "WHY IT MATTERS", "Emissions can only be computed from a predicted runtime, so the carbon question and the performance question have to be answered together — which is precisely the case for one integrated framework. And on this corpus the cheapest configuration was also the greenest in 21 of 21 scenarios: optimising for cost did not cost sustainability."],
    [MOSS, "WHAT COMES NEXT", "Workload fingerprinting from Spark event-log metrics, so the system characterises a job automatically instead of asking the user to classify it. Then uncertainty-aware SLA filtering — quantile or conformal prediction intervals — which opens the door to spot pricing under a hard deadline."],
  ];
  blocks.forEach((b, i) => {
    const y = 1.66 + i * 1.66;
    s.addShape(pres.ShapeType.roundRect, {
      x: 7.62, y, w: 5.09, h: 1.5, fill: { color: INK_CARD }, rectRadius: 0.09,
      line: { color: "3A5647", width: 1 },
    });
    s.addShape(pres.ShapeType.ellipse, {
      x: 7.9, y: y + 0.22, w: 0.15, h: 0.15, fill: { color: b[0] }, line: { color: b[0], width: 0 },
    });
    s.addText(b[1], {
      x: 8.15, y: y + 0.17, w: 4.3, h: 0.26, fontFace: BODY, fontSize: 10.5, bold: true,
      color: b[0], charSpacing: 1.1, margin: 0,
    });
    s.addText(b[2], {
      x: 7.9, y: y + 0.46, w: 4.55, h: 0.96, fontFace: BODY, fontSize: 10.2,
      color: "AEBFB4", lineSpacing: 13, margin: 0,
    });
  });

  footer(s, 12, "Chapters 8 and 9 — data/results/carbon_by_region.csv, tradeoff_by_scenario.csv");

  s.addNotes(
    "Close on this. It is the single most important contribution and it is genuinely counter-intuitive.\n\n" +
    "Expect: 'isn't cheapest-is-greenest trivially true given your formula?' It is close to structural and you must not oversell it. Cost is hourly price × nodes × runtime; emissions are power × nodes × runtime × intensity × PUE. Both are linear in NODE-HOURS. Within one region, intensity and PUE are constants, so the two can only diverge if the price-per-watt ordering differs from the watts-per-node ordering, or if the comparison crosses regions. In my corpus the 2-node Standard_D2as_v4 is simultaneously cheapest per hour and lowest power draw (1.08 W/vCPU against 2.30–2.72 for Intel), so it wins both. Doubling to 4 nodes cuts runtime 43% but raises cost 38% and emissions 39% — the runtime saving is sublinear while node-hours are linear. The correct claim is narrow: on THIS corpus, cost and carbon were aligned. Not a general law. The Pareto front averages 2.05 members, maximum 5, so residual trade-off structure exists — mostly against runtime.\n\n" +
    "Expect: 'why didn't you do the fingerprinting?' Spark event logging is not enabled by default on EMR and must be configured at cluster launch. By the time I understood it was the enabling data, the campaign was complete and the budget spent. That is a planning failure and the most consequential one in the project. Say it plainly.\n\n" +
    "Finish with the aim, not with an apology. You have 1,811 real measured runs; defend what is defensible."
  );
}

pres.writeFile({ fileName: path.join(__dirname, "..", "cost-carbon-aware-optimization-viva.pptx") })
  .then(f => console.log("wrote", f));
