# How Anthropic enables self-service data analytics with Claude

**Category:** Enterprise AI | **Product:** Claude Code | **Date:** June 3, 2026 | **Reading time:** 5 min

**Authors:** Chen Chang, Clement Peng, Justin Leder, Johanne Jiao, and Josh Cherry
(Data Science and Data Engineering team), with thanks to Michael Segner.

---

The article opens by noting that enabling self-service business analytics has "traditionally
been a slog" for data teams. Denormalized tables lead to "overlapping views with inconsistent
definitions," while ringfenced environments miss "the long tail of business questions."

LLMs offer a new path but can "create a false sense of precision" when pointed at a warehouse
without guardrails. The setup "separates stakeholders from the underlying infrastructure,
documentation, and expertise" that previously guided them.

At Anthropic, "95% of business analytics queries are automated via Claude, with ~95% accuracy
in aggregate." This frees the data science team to focus on "causal modeling, forecasting, and
machine learning."

The post shares best practices from meeting with "dozens of Anthropic's top Claude Code users," covering:

- Why analytics accuracy is a context and verification problem, not code generation
- Three failure modes causing most errors
- The agentic analytics stack built to address them
- How effectiveness is measured
- A basic template for skill creation (appendix)

---

## Data is not software

LLMs' generative abilities are described as "a double-edged sword." Coding rewards creativity
with "documentation and tests" as natural guardrails. Analytics often has "only a single
correct answer using a single correct source" with "no deterministic way of proving the
correctness."

The central problem is the "ability to map a user's question to specific and up-to-date entities in our data model."

Three attributes account for most inaccurate responses:

1. **Concept <> entity ambiguity**: With hundreds of viable options, the agent can't choose
   correct fields. Example: what constitutes being "active"? Include fraudulent users?
   What lookback window?

2. **Data staleness**: "data sources, business definitions, and schemas change constantly;
   assets and agent knowledge go stale."

3. **Retrieval failure**: The right information exists but "given the vastness of the search
   space, the agent simply doesn't find it."

---

## Our agentic analytics stack

Each layer attacks one or more failure modes:

1. **Entity ambiguity** → data foundations and sources of truth
2. **Staleness** → maintenance and validation processes
3. **Retrieval failure** → skills ensure the agent "reliably finds and correctly uses that answer"

### Data foundations

Standard practices like "dimensional modeling," shift-left testing, freshness and completeness checks all still apply.

The key shift: "the end user of your data model is no longer a data expert (e.g. data
scientist), but rather agents acting on behalf of users." Results "can't require the user to
validate the underlying correctness."

Best practices:

- **Create canonical datasets**: "The most common failure is that the agent can't map a
  concept" to the correct table/column/metric. The fix is "fewer, more heavily governed
  logical models." "Aggressively deprecate the near-duplicates." Physical rollups "should
  derive mechanically from the canonical models."

- **Enforce your standards**: Foundations hold only with enforcement by "tooling," "CI," and
  "mandate" — downstream teams "build on the governed layer or explain why not."
  "Governance without enforcement otherwise quickly decays."

- **Colocate artifacts**: Nearly all data code "lives in a single repo, with CI checks that
  protect cross-layer integrity." If a modeling change would "break a downstream dashboard or
  invalidate a documented metric, CI flags it."

- **Treat metadata as a first-class product**: The warehouse can be legible if "column and
  table descriptions, canonical metric definitions, grain documentation" and other metadata
  "are maintained with the same rigor as the transformations."

### Sources of truth

These are "the reference surfaces the agent consults to navigate" the warehouse. In descending order of trust:

- **Semantic layer**: Compiled metric and dimension definitions. Agents are "structurally
  required" to use it first. An approach that didn't work: "bootstrapping the semantic layer
  by having an LLM auto-generate metric definitions" — it "encoded the very ambiguities we
  were trying to eliminate." Recommendation: "generating the documentation with Claude, but
  having a human own the definition."

- **Lineage and the transformation graph**: When the semantic layer doesn't cover a question,
  lineage lets the agent "reason about which upstream models feed a concept." It transforms
  "'I don't know the metric' into 'I know which governed model to aggregate from.'"

- **Query corpus**: Historical SQL. "In practice, we found that giving the agent raw retrieval
  access to thousands of prior queries moved accuracy by less than a point." "Unstructured
  retrieval couldn't map a new question to the right precedent." What works is "distilling
  that corpus into structured per-domain reference docs."

- **Business context**: "The layer most teams skip, and the one we underrated the longest."
  Without it, the agent "will answer what the user asked, but not what they meant." They pipe
  in "a company knowledge graph consisting of indexed docs, roadmaps, decision logs, and our
  organizational structure."

The common failure across all four: "poor or stale documentation."

### Skills

A skill is "procedural knowledge: which sources to consult in what order." In Claude Code, a
skill is "a folder of markdown the agent reads on demand."

"Without skills, Claude's ability to answer analytics questions accurately didn't exceed 21%
on our evals. Adding skills gets these numbers consistently above 95%."

Best practices:

**Create pairwise skills:** A **knowledge** skill acts as "a thin top-level router" narrowing
the space "to a few dozen curated files before a query is ever written." The **unbook** skill
"encodes the process a senior analyst would follow" and bundles "a dozen reusable analysis
patterns."

**Create proper reference docs**: Written for LLM retrieval. The article provides a skeleton:

```text
# [Domain] Tables

## Quick Reference
### Business Context — [what this domain means in plain words]
### Entity Grain — [what one row represents]
### Standard Hygiene Filter — [the filter every query in this domain applies]

## Dimensions
- [How the key dimensions are encoded, and how the same concept is named
  differently across tables]

## Key Tables
### [table_name]
- **Grain**: [...] · **Scope/exclusions**: [...]
- **Usage**: [when to use it, when NOT to, join keys, required filters]
[... one short section per governed table ...]

## Gotchas
- [The wrong-answer modes a senior analyst would warn you about]

## Best Practices / Common Query Patterns
- [Default choices, standard cuts, worked patterns where the exact query
  form is the hard part]

## Cross-References
- [Neighboring domain docs that own adjacent questions]
```

**Treat skill maintenance as a first class citizen**: They "watched our offline accuracy drift
from ~95% at launch to ~65% over a month." The solution: "colocating skill markdown files in
the same repo as our transformation models." A code-review hook flags model changes without
skill updates. "Roughly 90% of our data-model PRs now include a skill change."

**Create a consistent experience across surfaces**: "The same skill must provide the same
answer" in Slack, IDE, dashboards, and standalone sessions. On merge, skills sync to "a plugin
marketplace," "cloud-storage blobs," and are "served directly as resources over MCP."

### Validation

#### Offline evaluations

"A common pattern we see is that data teams will set up elaborate analytic environments
without having any process to understand the accuracy."

Two kinds at Anthropic: **Dashboard-based evals** (auto-generated by Claude, human validated)
and **Long tail evals** (Claude generates plausible questions from business context). They also
"harvest every time a stakeholder corrects the agent."

Best practices:

- **Anchor ground truth**: "Pin every eval to a snapshot date" or "have the grader judge the
  agent's query rather than its number."

- **Store results like telemetry**: Every run lands in a warehouse table with "skill version,
  git SHA, model ID, per-assertion pass/fail, token count, and wall-clock."

- **Gate launches per domain**: Domain owners can't launch "until their slice of the eval set
  clears some threshold (we initially used ~90%)."

- **Create the appropriate number**: "Diminishing returns past a few dozen per topic" and
  "that ceiling drops with each new model generation."

- **Offline eval accuracy should be ~100%**; every correct answer should hit the semantic layer.

#### Ablation techniques

Structural decisions are made by "holding our offline eval set fixed" and varying "exactly one component."

- **Design for null results**: They gave the agent "direct grep access to our entire dashboard,
  transformation, and analyst-notebook SQL." "Accuracy moved by less than a point in either
  direction." The information was there, the agent saw it, "and it still didn't use it." This
  showed "our bottleneck wasn't access to prior work, it was structure."

- **Ablate at PR granularity**: Every skill edit gets "a before / after run on the relevant eval slice."

- **Keep a short list of what didn't work**: Examples: "stacking additional rounds of doc
  refinement past a certain point" (three consecutive net-negative iterations) and "swapping
  the adversarial reviewer to a cheaper model."

#### Online validation

- **Adversarial review**: Employing a skill to "aggressively challenge all underlying
  assumptions" increased accuracy by 6% but cost "32% more tokens and 72% higher latency."

- **Provenance footer**: Every response carries source tier, freshness, and model owner.
  "A 'raw table, freshness unknown' footer is a signal to verify."

- **Data quality checks**: Basic checks ensuring "the referenced field is up-to-date, complete, and has no anomalies."

- **Passive monitoring**: Two signals tracked: "share of agent queries that resolve through
  the semantic layer" and "share of responses that use correction language."

- **Active correction harvesting**: A scheduled agent scans channels for corrections, "drafts
  a one-line fix to the relevant reference doc, and opens a PR." Corrections feed back into
  offline evals.

The unresolved failure mode: "The answer is wrong, but looks plausible and is used without
objection." Mitigations include provenance footers and "explicit human sign-off on anything
leadership-bound," though they "don't have a robust solution yet."

---

## Getting started

"A handful of canonical datasets, a few dozen offline evals, and a thin knowledge skill will capture most of the upside."

Key questions for teams:

- **How important is a correct answer today vs. in the future?** Companies often build
  "infrastructure to account for current model shortfalls that become moot once those models
  improve."

- **How do you anticipate business complexity changing?** Some processes may be "overkill"
  for simple data models with few consumers.

- **How technical is the audience?** Data scientists who "can recognize when an answer is
  incorrect" allow more error tolerance than audiences with "no familiarity with the underlying
  data model."

- **How much will you spend for improved accuracy?** Processes like "adversarial validation
  can significantly improve accuracy, but often at a higher cost and latency."

- **What is your comfort around access controls?** "Agents are often significantly more
  performant the more context they have" but "broad data access cuts against most companies'
  governance posture."

The greatest gains come from "addressing each of the three failure modes: collapsing ambiguity
into a single governed answer, making the answer easily discoverable, and flagging when either
has gone stale."

---

## Appendix

### Skill File Skeleton

The article provides the full skeleton of their main warehouse skill with bracketed placeholders. The complete code block:

```text
---
name: [warehouse-skill]
version: [x.y.z]
description: "IF the user asks to query [the company]'s data warehouse for any
  [list of business domains] question — THEN invoke this skill. DO NOT invoke
  for [adjacent engineering tasks] or questions with no data-warehouse component."
---

# [Warehouse] Skill Instructions

## Description
The single source of truth for safe and effective [warehouse] querying.
Referenced by other skills [listed] for query execution guidance.

Act as a Data Analyst, providing strategic insights and data-driven
recommendations but seek guidance along the way.

**Out-of-scope decisions**: [product areas, etc.] → surface data only,
state "decision is [owning team]'s call", do NOT take a position or author
code fixes.

## Executing queries
Priority:
1. **[Managed connection]** (if available): [query tool] / [schema tool]
2. **[CLI fallback]** (if installed): [default project, fallback project]
3. **Neither** — ask the user to authenticate, then stop

---

# Semantic Layer (REQUIRED first step)

The governed semantic layer is the **mandatory default path** for every data
question — same numbers as [the BI tool], joins/grain/filters baked in. Raw SQL
via the reference docs below is the **fallback**, used only after the
semantic-layer path is shown not to cover the ask.

## Required workflow
1. **Load** — [how to load the semantic layer in each runtime, with fallbacks]
2. **Discover** — search measures/dimensions by keyword; **always check
   segments** (the named canonical population filters — hand-rolled WHERE
   clauses for these are the dominant wrong-answer mode)
3. **Compile + run** — build the spec → compile to SQL → execute
4. **Fallback** — only if discovery finds no relevant metric or compile fails
   → raw SQL via `references/*.md` (PART 3 below)

> **Don't bail early.** Do NOT fall back to raw SQL on these grounds:
> - "[custom date filtering / cohorts]" → [covered by time-dimension specs]
> - "[needs a join]" → [the metric layer already encapsulates its joins]
> - [3–4 more pre-rebutted excuses agents use to skip the semantic layer]

### Date windows & timezone — decide before you query
- **As-of date vs trailing-N days**: [convention for each]
- **"Last week/month"** → the last *complete* calendar week/month, not trailing-7/30
- **Timezone default**: [TZ]; [exception for certain reporting rollups]
- **Freshness lag**: [some] tables settle late — anchor on MAX(date), not "yesterday"

---

# PART 1: MUST KNOW (Read First for Every Request)

## 🚀 Quick Start Workflow
1. **Check for red flags first**: [restricted/PII requests, gated domains,
   high-stakes asks that need extra validation]
2. **Out of scope — escalate, don't guess**: [access requests, pipeline
   troubleshooting, stale dashboards, root-cause assertions, product/pricing
   recommendations] → redirect to [the owning team], don't answer
3. **Clarify the request**: time period, segment, the business decision it informs
4. **Check for existing dashboards**: [per-domain dashboard catalogs]
5. **Identify the data source**: [navigation map below; prefer governed/aggregated tables]
6. **Execute the analysis**: [required filters + adversarial review]
7. **Deliver insights**: show methodology, differentiate observations from interpretations

## 🏢 Business Context

### Entity Disambiguation (MUST CLARIFY)
- **"[Term A]" can mean**: [entity 1] or [entity 2] — always clarify which
- **"[Term B]" can mean**: [entity 1] → [entity 2] → [entity 3] (one-to-many chain)
- **"Users"**: [which identifier gives accurate counts, and which ones inflate them]

### Business Terminology
- [Current product names vs deprecated aliases that still appear as frozen
  values in the data layer — write with the new names, filter with the old]
- [Key internal acronyms]
- **[Headline metric] calculations**: [monthly / default window / leading indicator]
- **Unfamiliar terms — search [internal docs], don't guess**

### Data Integrity Requirements ⚠️
- **NEVER**: make up data/columns; make speculative assertions beyond what data shows
- **ALWAYS**: use safe division; differentiate observations ("data shows X")
  from interpretations ("this suggests Y"); flag limitations

---

# PART 2: HOW TO DO (Follow During Execution)

## 🔧 Technical Execution Guide
- [Managed-connection tools and CLI invocation details]
- **PII protection**: for restricted data, return the SQL for the user to run
  themselves — do not return results

## 📊 Analysis Best Practices Guide
1. Clarify the ask before querying
2. Show your work (filters, inclusions/exclusions, freshness)
3. Clarify denominators
4. Consider sample bias
5. Connect to business impact
6. **Adversarial SQL review (MANDATORY)** — spawn the [sql-reviewer] sub-agent
   for every query before the final answer; blocking findings must be fixed
   and re-reviewed; do not self-certify
7. **Report with provenance** — every answer ends with a footer:
   > **Source:** [semantic layer | governed table | raw exploration] ·
   > **Confidence:** [tier] · **Reviewed:** [reviewer ✓, round N] ·
   > **Freshness:** [max date in the data] · **Owner:** [owning team]

---

# PART 3: DATA REFERENCES & RESOURCES

## 📚 Knowledge Base Navigation
### [Domain A] → `references/[domain_a].md`
- **Use for**: [kinds of questions]
- **Key tables**: [...]
- **Dashboards**: `references/[domain_a]_dashboards.json`

### [Domain B] → `references/[domain_b].md`
- **Use for**: [...]

[... one entry per business domain — a few dozen in total ...]

## ⚠️  Troubleshooting Guide

### When Information Is Missing
- [missing tables / access denied / outdated docs / unknown enum values → what to do]

### Field Naming Gotchas
- Use `[field_x_v2]` NOT `[field_x]`
- [Two similarly-named tables report the same metric at different grains — which to use]
- [Which of two plausible sources is canonical for the headline metric]
- [… a dozen more hard-won one-liners …]
```
