---
name: bigquery-query
description: >-
  IF the user asks to write, cost-check, or run a BigQuery SQL query against a public
  dataset — THEN invoke this skill, which ALWAYS lints, dry-runs for a byte estimate, and
  executes only with a maximum_bytes_billed hard cap. DO NOT invoke for infra/Terraform
  tasks, for pure metadata lookups (use bigquery-metadata), or for non-data questions.
allowed-tools: Bash(uv run:*), Read, Write
---

# BigQuery Query — the single source of truth for safe querying

Referenced by `bigquery-notebook` and `bigquery-chart` for query-execution guidance. Act as
a careful data analyst: surface data and methodology; never invent numbers.

## Executing queries — priority ladder

1. **Python client (preferred)**: `data_lagoon.bq.capped_query()` (used by the scripts and
   notebooks) — dry-runs then caps automatically.
2. **CLI fallback**: `bq query --use_legacy_sql=false --maximum_bytes_billed=<bytes> ...`
   (only if explicitly needed; the cap flag is mandatory).
3. **Neither / not authenticated** → ask the user to run
   `gcloud auth application-default login` and `gcloud config set project c11z-data-lagoon`,
   then stop.

## Semantic Layer (REQUIRED first step)

The DomainSpec is the **mandatory default path** for every data question — joins, grain, and
filters are baked in. Raw SQL is the **fallback**, used only after the semantic layer is
shown not to cover the ask.

### Required workflow

1. **Load / Discover** — `uv run python scripts/spec_lookup.py --query "<concept>"`. Always
   check **segments** (named population filters) — never hand-roll a `WHERE` for one.
2. **Compile + run** — compile the metric to SQL, then execute capped:
   `uv run python scripts/spec_lookup.py --dataset google_trends --metric <m>
   --dimensions <d> --segments <s> --last-n-days <n> --limit <k> --compile`
3. **Fallback** — only if discovery finds no relevant metric or compile can't express the
   ask → write raw SQL using `references/sql-patterns.md`.

> **Don't bail early** to raw SQL on these grounds:
>
> - "needs custom date filtering" → use `--last-n-days` / `--start`/`--end` (TimeWindow).
> - "needs a different grouping" → use `--dimensions`.
> - "needs a population cut" → use a `--segments` name (add one to the YAML if missing).

### Date windows & timezone — decide before you query

- **"Last week/month"** = the last *complete* calendar week/month, **not** trailing 7/30 days.
- **Freshness**: anchor on `MAX(refresh_date)`, not "today" — partitions settle on refresh.
- **Timezone**: default UTC. `week` is a Sunday-anchored DATE.

## PART 1 — MUST KNOW (every request)

1. **Cost red flags first** (see `references/cost-rules.md`): refuse `SELECT *` on large
   tables and any query missing a partition filter. `LIMIT` does **not** cut cost.
2. **Exfil prudence**: prefer aggregations; return SQL + small aggregates or a capped
   sample — never dump large raw result sets to the user.
3. **Clarify** the time period, segment, and the decision the answer informs.
4. **Data integrity** (`references/data-integrity.md`): NEVER invent data/columns; ALWAYS
   use safe division; separate observations ("data shows X") from interpretation
   ("this suggests Y"); flag limitations.

## PART 2 — HOW TO (during execution)

1. **Write** SQL into `analyses/<slug>/queries/<name>.sql` (version-controlled record).
2. **Lint**: `uv run sqlfluff lint analyses/<slug>/queries/` → fix reported violations →
   re-lint. (`uv run sqlfluff fix analyses/<slug>/queries/` auto-fixes most.)
3. **Dry-run**: `uv run python scripts/bq_dry_run.py --file <that .sql>` → read bytes/est.
   If over the soft threshold, warn and confirm; if over the hard cap, narrow the query.
4. **Execute capped** via `capped_query()` (or the `--maximum_bytes_billed` flag). The job
   fails (no charge) rather than overspending.
5. **Adversarial review** *(disabled by default — deviation from the article's "mandatory")*.
   To enable later, spawn a reviewer sub-agent to refute the query's assumptions before the
   answer; correctness today rests on lint + dry-run + the hard cap.
6. **Report with a provenance footer** (exact format in `references/data-integrity.md`):
   `> **Source:** … · **Confidence:** … · **Bytes scanned:** … · **Freshness:** … · **Owner:** … · **Reviewed:** …`

## PART 3 — References

| Topic | File |
|---|---|
| Common google_trends SQL patterns | `references/sql-patterns.md` |
| Cost rules & guardrails | `references/cost-rules.md` |
| Date / timezone conventions | `references/date-conventions.md` |
| Data integrity + provenance footer | `references/data-integrity.md` |
