# data-lagoon

LLM context harness for self-service analytics over **Google BigQuery public datasets**,
modeled on Anthropic's *How Anthropic enables self-service data analytics with Claude*
(`anthropic_analytics_article.md`). The thesis: analytics accuracy is a **context +
verification** problem, not a code-gen one. So we invest in *structure* — a curated semantic
layer, per-dataset reference docs, a routing skill tree, and cost guardrails — not in pointing
the model at raw data.

## What's here

| Layer | What | Where |
|---|---|---|
| Semantic layer | pydantic DomainSpec that **compiles to SQL** (metrics, segments, grain, partition filters) | `domainspec/`, `src/data_lagoon/spec.py` |
| BigQuery choke point | one capped path: dry-run → `maximum_bytes_billed` → Arrow → polars | `src/data_lagoon/bq.py` |
| Free metadata | list datasets/tables, schema, size, partitioning (zero bytes scanned) | `src/data_lagoon/catalog.py`, `scripts/bq_*.py` |
| Skill tree | knowledge router + query + notebook + chart | `.claude/skills/` |
| Persistent analyses | two-phase marimo notebooks (extract once → parquet → analyze) | `templates/`, `analyses/` |
| Infra | Terraform: APIs, scratch dataset, IAM, optional budget | `terraform/` |
| Validation | offline evals graded on the *query*, stored as telemetry | `evals/` |

Toolchain: **uv** · polars · duckdb · plotly · pyarrow · google-cloud-bigquery[bqstorage] ·
great-tables · pydantic · rich · marimo · ruff · sqlfluff · pytest.

## Setup

```bash
# 1. Toolchain (uv manages Python + deps). If `uv` isn't installed:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install deps into a project venv. UV_SYSTEM_CERTS=1 makes uv trust the system/corporate
#    trust store (needed behind a TLS-intercepting proxy).
UV_SYSTEM_CERTS=1 uv sync

# 3. Authenticate to GCP with Application Default Credentials (no service-account keys).
gcloud auth application-default login
gcloud config set project c11z-data-lagoon

# 4. (Optional) Provision infra — enables APIs + a self-expiring scratch dataset.
cd terraform && terraform init && terraform apply
```

> **Note on this machine:** it's Santa-managed. `uv`/`terraform` must be allowlisted (already
> synced). Run everything via `uv run` so tools come from the pinned project venv. If you see
> SSL errors from uv, prefix `UV_SYSTEM_CERTS=1`.

## Everyday use

```bash
# Discover (free, no query): search the semantic layer / inspect tables
uv run python scripts/spec_lookup.py --query "rising terms"
uv run python scripts/bq_schema.py --table bigquery-public-data.google_trends.top_terms

# Compile a metric to cost-safe SQL (always partition-filtered)
uv run python scripts/spec_lookup.py --dataset google_trends --metric avg_score \
  --dimensions term --segments top_10 --last-n-days 7 --limit 20 --compile

# Estimate cost without running (free dry-run)
uv run python scripts/bq_dry_run.py --file analyses/<slug>/queries/q.sql

# Start a persistent, billing-safe analysis
uv run python scripts/new_analysis.py --slug trends-demo --dataset google_trends
uv run marimo edit analyses/<date>-trends-demo/notebook.py

# Quality gates
uv run ruff check . && uv run ruff format --check .
uv run sqlfluff lint analyses/<slug>/queries/
uv run pytest
uv run python evals/run_evals.py
```

## Billing safety (defense in depth)

- **Two-phase notebooks**: extraction cells hit BigQuery **once**, guarded by a file-existence
  check, and freeze to `data/*.parquet`. Analysis cells read only the parquet — structurally
  unable to re-bill.
- **`capped_query()`** dry-runs first and sets `maximum_bytes_billed` (default soft 1 GiB warn
  / hard 5 GiB fail). `LIMIT` does **not** reduce cost; `SELECT *` is forbidden; every query
  must filter the table's declared partition/shard column when it has one (e.g. google_trends →
  `refresh_date`, year-sharded tables → `_TABLE_SUFFIX`).
- **Exfil prudence**: return aggregates + SQL, never dump raw rows.
- **Terraform**: least-privilege IAM (`jobUser` + scratch-only `dataEditor`), auto-expiring
  scratch tables, optional budget alert (`create_budget`, off by default).

## Add a dataset

1. Author `domainspec/<name>.yaml` (tables, segments, metrics, gotchas) — **humans own metric
   definitions**; Claude may draft prose only.
2. `uv run python scripts/gen_schema.py` to refresh `domainspec/_schema.json`.
3. Write `.claude/skills/bigquery-metadata/references/<name>.md` (same skeleton as
   `google_trends.md`) and add an entry to `references/dataset-catalog.md`.
4. Add `<name>` to `ALLOWLIST` in `src/data_lagoon/config.py`.
5. `uv run python scripts/check_spec_doc_sync.py` must pass (staleness guard).

## Deliberate scope cuts (vs. the article)

No lineage tracking (public datasets have no pipelines); no query-corpus retrieval; adversarial
review deferred (flag-gated placeholder in the query skill); single-surface (no MCP/marketplace
sync).
