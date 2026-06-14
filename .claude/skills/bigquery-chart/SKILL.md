---
name: bigquery-chart
description: >-
  IF the user wants to visualize/chart query results or build a publication-quality table
  from an already-extracted (frozen parquet / polars) result — THEN invoke this skill to
  build plotly figures and great-tables tables from LOCAL data. DO NOT invoke to run
  BigQuery (this skill never queries) — extract first with bigquery-notebook/bigquery-query.
allowed-tools: Bash(uv run:*), Read, Write
---

# BigQuery Chart — visuals & tables from frozen data

Reads the **local parquet** produced by the two-phase notebook (or any polars frame) and
renders charts/tables. **It never re-queries BigQuery** — all inputs are on disk.

## Hard rule
Input is `analyses/<slug>/data/*.parquet` (or a polars frame already in scope). If the data
isn't extracted yet, stop and route to `bigquery-notebook`. Never import the BigQuery client.

## Workflow
1. **Load**: `df = pl.read_parquet("analyses/<slug>/data/<file>.parquet")`.
2. **Pick the form** by data shape (see `references/chart-recipes.md`):
   time → line; category ranking → bar; parts-of-whole → treemap/pie (sparingly); a small
   ranked set → a great-table.
3. **Build**: plotly figure and/or `great_tables.GT(df)`.
4. **Export** to `analyses/<slug>/out/`: `fig.write_html(..., include_plotlyjs="cdn")` and
   `GT(...).save("out/table.png")` or `.as_raw_html()`.
5. Keep the **provenance footer** with any shared figure/table.

## When to use / not
- **Use** to chart/tabulate a result you already extracted.
- **Don't use** to fetch data → `bigquery-notebook` / `bigquery-query`.

## References
| Topic | File |
|---|---|
| plotly + great-tables recipes from polars | `references/chart-recipes.md` |
