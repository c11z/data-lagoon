---
name: bigquery-notebook
description: >-
  IF the user wants a reproducible, persistent analysis of BigQuery public data (a record
  they can revisit), or says "make a notebook / analysis" — THEN invoke this skill to
  scaffold a two-phase marimo notebook that extracts once to parquet and analyzes locally.
  DO NOT invoke for one-off queries (use bigquery-query) or pure metadata lookups.
allowed-tools: Bash(uv run:*), Read, Write
---

# BigQuery Notebook — the persistent analysis record ("unbook")

Encodes the senior-analyst process as a marimo notebook: clarify → find the source (via
`bigquery-metadata`) → extract once → analyze → chart/table → provenance footer. The
notebook `.py` + frozen parquet + saved `.sql` are the durable record of the conversation.

## The two-phase convention (billing safety — non-negotiable)

marimo re-runs cells reactively; an auto-re-running BigQuery cell is a billing incident.
So:

- **Phase 1 (extract)**: runs BigQuery **exactly once**, guarded by a **file-existence
  check**, and freezes the result to `data/*.parquet`. On re-run it reloads parquet for free.
- **Phase 2 (analyze/chart/table)**: depends **only** on the local `df`. The BigQuery client
  is never imported into these cells, so they are structurally incapable of re-billing.

Read `references/marimo-cells.md` before editing cells.

## Workflow

1. **Scaffold**: `uv run python scripts/new_analysis.py --slug <kebab> --dataset google_trends`
   → creates `analyses/<date>-<slug>/{notebook.py, data/, queries/, out/}`.
2. **Set the request** in the notebook's `_config` cell (metric, dimensions, segments,
   time window, caps) — it compiles cost-safe SQL from the DomainSpec.
3. **Run**: `uv run marimo edit analyses/<date>-<slug>/notebook.py`. Phase 1 calls BigQuery
   only if the parquet is missing (it dry-runs and caps via `capped_query()`).
4. **Save the SQL** the notebook compiled into `queries/` and lint it
   (`uv run sqlfluff lint analyses/<date>-<slug>/queries/`).
5. **End with the provenance footer** (already wired in the template's last cell).
6. **Share**: `uv run marimo export html analyses/<date>-<slug>/notebook.py` for a static record.

## To force a fresh extract

Delete the parquet in `data/` (or change a PARAM — the filename is param-keyed, so a changed
param maps to a new file rather than silently reusing stale data).

## When to use / not

- **Use** for any analysis worth keeping or re-running.
- **Don't use** for a quick one-shot answer → `bigquery-query`. For charts on an existing
  parquet → `bigquery-chart`.

## References

| Topic | File |
|---|---|
| marimo cell recipes + two-phase rules | `references/marimo-cells.md` |
| query execution / caps | `../bigquery-query/SKILL.md` |
