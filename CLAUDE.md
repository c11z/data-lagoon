# data-lagoon — operating contract for Claude

A context harness for analytics over BigQuery **public** datasets. Optimize for *correct
entity mapping*, not clever SQL. Procedural depth lives in `.claude/skills/`; read the
relevant SKILL.md before acting.

## Non-negotiables

1. **Look up before you query.** Start with `bigquery-metadata` → search the DomainSpec
   (`scripts/spec_lookup.py`) and inspect tables (`scripts/bq_schema.py`, free) before
   writing SQL.
2. **Semantic layer first.** If a metric/segment exists, compile it (`--compile`); never
   hand-roll a `WHERE` for a population that has a named segment.
3. **Cost guardrails, always.** Dry-run (`scripts/bq_dry_run.py`) before executing; run only
   through `data_lagoon.bq.capped_query()` (sets `maximum_bytes_billed`). Every query MUST
   filter the table's declared partition/shard column when it has one (the DomainSpec records
   it per table — e.g. google_trends → `refresh_date`, year-sharded tables → `_TABLE_SUFFIX`).
   `LIMIT` does not reduce cost; `SELECT *` is forbidden.
4. **Two-phase notebooks.** Analyses are marimo notebooks that extract **once** to parquet
   (file-existence guard) and analyze locally. Never put a BigQuery call in a phase-2 cell.
5. **Exfil prudence.** Return aggregates + the SQL; don't dump large raw result sets.
6. **Humans own metric definitions.** Draft prose for `domainspec/*.yaml`, but don't invent
   metric/segment semantics.
7. **No invented data.** Use `SAFE_DIVIDE`; separate observations from interpretation; flag
   dataset-specific limitations the DomainSpec calls out (e.g. relative scores, rolling
   windows, latest-refresh dedup, sampled sessions).

## Stack & commands (run everything via uv)

polars/duckdb (local), plotly + great-tables (output), pyarrow, google-cloud-bigquery
[bqstorage]. `UV_SYSTEM_CERTS=1 uv sync`; `uv run ruff check . && uv run ruff format`;
`uv run sqlfluff lint <dir>`; `uv run rumdl check .`; `uv run pytest`; `uv run python evals/run_evals.py`.

## Map

- `src/data_lagoon/` — spec (compiler), bq (capped client), catalog (free metadata), render.
- `scripts/` — JSON-output CLIs the skills call.
- `domainspec/` — the semantic layer (source of truth) + generated `_schema.json`.
- `.claude/skills/` — bigquery-metadata (router) · bigquery-query (warehouse) ·
  bigquery-notebook (unbook) · bigquery-chart.
- `terraform/` — IAM + scratch dataset + optional budget (apply is the user's step).

Deliberately omitted: lineage, query-corpus retrieval, always-on adversarial review,
multi-surface sync.
