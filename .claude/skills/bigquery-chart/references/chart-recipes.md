# Chart & table recipes (polars → plotly / great-tables)

All inputs are local (frozen parquet / polars frames). Never query BigQuery here.

**Every figure/table is a marimo notebook cell.** Build it and leave the object (`fig`,
`gt`) as the cell's **last bare expression** — marimo renders it inline. Do **not**
`fig.write_html(...)` or `GT.save(...)`; the notebook is the artifact, not a loose file.

## Choose by data shape

| Data shape | Chart |
|---|---|
| metric over time (`week`) | line (`px.line`) |
| ranking across categories (`term`) | horizontal bar (`px.bar`, `orientation="h"`) |
| a few parts of a whole | treemap; pie only for ≤5 slices |
| a small ranked table to publish | great-tables `GT` |

## plotly from polars

plotly 6 (with narwhals) + numpy accept polars frames **directly** — no pandas needed. If you
ever need a pandas-only feature, `uv add pandas` then pass `df.to_pandas()`.

```python
@app.cell
def chart_bar(df, px):
    fig = px.bar(
        df.sort("avg_score", descending=True).head(15),
        x="avg_score", y="term", orientation="h",
        title="Top terms by relative search interest",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    fig  # last bare expression → marimo renders it inline
    return (fig,)
```

## Time series

```python
@app.cell
def chart_ts(df, pl, px):
    ts = df.group_by("week").agg(pl.col("score").mean().alias("avg_score")).sort("week")
    fig_ts = px.line(ts, x="week", y="avg_score", title="Interest over time")
    fig_ts
    return (fig_ts,)
```

## Publication table (great-tables from polars)

```python
@app.cell
def table_top(GT, df):
    gt = (
        GT(df.sort("avg_score", descending=True).head(10))
        .tab_header(title="Top trending terms", subtitle="last 7 days, US DMAs")
        .fmt_number(columns="avg_score", decimals=1)
        .cols_label(term="Term", avg_score="Avg score")
        .tab_source_note("Source: bigquery-public-data.google_trends · relative interest (0-100)")
    )
    gt  # marimo renders great-tables inline; no .save() / .as_raw_html() needed
    return (gt,)
```

## Notes

- Do all aggregation/sorting/filtering in **polars** first; great-tables is presentation
  only and wants a materialized frame (call `.collect()` on a LazyFrame first).
- marimo renders plotly figures and great-tables objects inline from the bare expression —
  **no Chromium/kaleido backend needed**. That is the whole point of charting in the
  notebook instead of exporting `write_image`/`GT.save` PNGs.
- Keep the relative-interest caveat visible — scores are not absolute volumes.
