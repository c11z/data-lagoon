---
name: bigquery-chart
description: >-
  IF the user wants to visualize/chart query results or build a publication-quality table
  from an already-extracted (frozen parquet / polars) result — THEN invoke this skill to
  build plotly figures and great-tables tables from LOCAL data AS AN INLINE CELL in the
  analysis's marimo notebook (never a standalone HTML/PNG export). DO NOT invoke to run
  BigQuery (this skill never queries) — extract first with bigquery-notebook/bigquery-query.
allowed-tools: Bash(uv run:*), Read, Write, Edit
---

# BigQuery Chart — visuals & tables from frozen data

Reads the **local parquet** produced by the two-phase notebook (or any polars frame) and
renders charts/tables **as inline cells in a marimo notebook**. **It never re-queries
BigQuery** — all inputs are on disk.

## Hard rules

1. Input is `analyses/<slug>/data/*.parquet` (or a polars frame already in scope). If the
   data isn't extracted yet, stop and route to `bigquery-notebook`. Never import the
   BigQuery client.
2. **The deliverable is a chart CELL in the analysis's marimo notebook**
   (`analyses/<slug>/notebook.py`), rendered inline by leaving `fig` / `GT(...)` as the
   cell's last bare expression. **Do NOT write standalone HTML or PNG** (`fig.write_html`,
   `GT.save`) as the output — the notebook is the artifact. If the analysis has no notebook
   yet, scaffold one first with `bigquery-notebook` (`scripts/new_analysis.py`), then add
   the chart cell to it.

## Workflow

1. **Find the notebook**: locate `analyses/<slug>/notebook.py`. If there isn't one, scaffold
   it via `bigquery-notebook` so the chart has a home; charting never lives in a loose script.
2. **Use the frozen `df`** already loaded by the notebook's Phase-1 cell. (For a stray
   parquet with no notebook cell yet, add a guarded `pl.read_parquet(...)` load cell — never
   a BigQuery call.)
3. **Pick the form** by data shape (see `references/chart-recipes.md`):
   time → line; category ranking → bar; parts-of-whole → treemap/pie (sparingly); a small
   ranked set → a great-table.
4. **Add a Phase-2 chart cell**: build `fig` (plotly) and/or `great_tables.GT(df)` and leave
   it as the cell's **last bare expression** so marimo displays it inline. Give the cell's
   artifacts distinct names (single-definition rule). No `write_html` / `save`.
5. Keep the **provenance footer** cell with any shared figure/table.
6. **View**: `uv run marimo edit analyses/<slug>/notebook.py`. A static copy for sharing is
   the notebook skill's `marimo export html <notebook.py>` (exports the whole record) — not
   a hand-rolled per-figure HTML file.

## When to use / not

- **Use** to chart/tabulate a result you already extracted.
- **Don't use** to fetch data → `bigquery-notebook` / `bigquery-query`.

## References

| Topic | File |
|---|---|
| plotly + great-tables recipes from polars | `references/chart-recipes.md` |
