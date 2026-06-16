# Chart & table recipes (polars → plotly / great-tables)

All inputs are local (frozen parquet / polars frames). Never query BigQuery here.

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
import plotly.express as px

fig = px.bar(
    df.sort("avg_score", descending=True).head(15),
    x="avg_score", y="term", orientation="h",
    title="Top terms by relative search interest",
)
fig.update_layout(yaxis={"categoryorder": "total ascending"})
fig.write_html("out/top_terms.html", include_plotlyjs="cdn")  # small, shareable
```

## Time series

```python
ts = df.group_by("week").agg(pl.col("score").mean().alias("avg_score")).sort("week")
px.line(ts, x="week", y="avg_score", title="Interest over time")
```

## Publication table (great-tables from polars)

```python
from great_tables import GT

gt = (
    GT(df.sort("avg_score", descending=True).head(10))
    .tab_header(title="Top trending terms", subtitle="last 7 days, US DMAs")
    .fmt_number(columns="avg_score", decimals=1)
    .cols_label(term="Term", avg_score="Avg score")
    .tab_source_note("Source: bigquery-public-data.google_trends · relative interest (0-100)")
)
gt.as_raw_html()          # embed in a report (no browser dependency)
# gt.save("out/top_terms.png")   # needs a headless-browser backend
```

## Notes

- Do all aggregation/sorting/filtering in **polars** first; great-tables is presentation
  only and wants a materialized frame (call `.collect()` on a LazyFrame first).
- `write_image` (PNG) and `GT.save("*.png")` need a Chromium/kaleido backend; prefer HTML
  (`write_html` / `as_raw_html`) when you don't have one.
- Keep the relative-interest caveat visible — scores are not absolute volumes.
