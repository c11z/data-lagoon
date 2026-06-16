# google_trends Tables

Reference doc for `bigquery-public-data.google_trends`. Kept consistent with
`domainspec/google_trends.yaml` (the machine-readable source of truth — prefer compiling a
metric from it over hand-writing SQL).

## Quick Reference

### Business Context

Google Trends Top Charts: the 25 most **popular** ("top") and fastest-**rising** ("rising")
Google search terms by week, broken out by US **DMA** (Designated Market Area) and, in the
`international_*` tables, by country/region. Answers "what was trending where/when". Scores
are **relative** search interest (0–100), **not** absolute search volume.

### Entity Grain

One row = one **(geography, term, week)** ranking as reported on a given `refresh_date`.
For the DMA tables geography = US DMA; for the international tables = country (+ optional region).

### Standard Hygiene Filter

None is mandatory beyond the **required** `refresh_date` partition filter. Add
`score IS NOT NULL` (segment `nonnull_score`) when averaging scores.

## Dimensions

- **Geography**: `dma_name` / `dma_id` (US only) vs `country_code` / `region_code`
  (international). The same idea, different columns per table.
- **Time**: `week` (the ranking's week, a Sunday) vs `refresh_date` (when Google published
  it — **the partition**). These are different; see Gotchas.
- **Rank vs score**: `rank` 1–25 (1 = top); `score` 0–100 relative interest;
  `percent_gain` (rising tables only) = week-over-week growth.

## Key Tables

### top_terms (US DMA, most popular)

- **Grain**: (dma, term, week) as of refresh_date · **Scope**: US DMAs only.
- **Usage**: "most popular terms"; filter `refresh_date`; required filter: `refresh_date`. Join key: `dma_id, week, refresh_date`.

### top_rising_terms (US DMA, fastest rising)

- **Grain**: (dma, term, week) · **Scope**: US DMAs; has `percent_gain`.
- **Usage**: "fastest-growing / breakout terms". Do NOT use for absolute popularity.

### international_top_terms (country/region, most popular)

- **Grain**: (country/region, term, week) · **Scope**: non-US-DMA, worldwide.
- **Usage**: trends outside the US DMA breakdown; segment `country_us` restricts to the US.

### international_top_rising_terms (country/region, fastest rising)

- **Grain**: (country/region, term, week) · has `percent_gain`.

## Gotchas

- **Partitioned by `refresh_date`.** ALWAYS filter it — otherwise you scan the full ~5-year
  history. `LIMIT` does **not** reduce bytes scanned; only a partition filter does.
- **Latest-refresh dedup.** The same `week` appears under many `refresh_date`s (each refresh
  re-reports recent weeks). For "the" ranking of a week, take the latest refresh:
  `WHERE refresh_date = (SELECT MAX(refresh_date) FROM \`...top_terms\`)`. Otherwise rows
  double-count across refreshes.
- **rank vs score.** `rank` 1 = most popular; `score` is relative (0–100) and may be NULL.
- **US vs international.** `top_terms`/`top_rising_terms` are US DMAs only; use the
  `international_*` tables for other countries.
- **popular vs rising.** `top_terms` = most popular; `top_rising_terms` = fastest growing.
  Don't conflate them.
- **Rolling window** — roughly the last 5 years are retained; older weeks drop off.

## Best Practices / Common Query Patterns

- Prefer compiling from the semantic layer:
  `uv run python scripts/spec_lookup.py --dataset google_trends --metric avg_score
  --dimensions term --segments top_10 --last-n-days 7 --limit 20 --compile`
- For a clean weekly ranking, combine the partition filter with the latest-refresh dedup
  (see `bigquery-query/references/sql-patterns.md`).
- Freshness anchor for the provenance footer: `MAX(refresh_date)`.

## Cross-References

- SQL recipes: `../../bigquery-query/references/sql-patterns.md`
- Cost rules: `../../bigquery-query/references/cost-rules.md`
- Date conventions: `../../bigquery-query/references/date-conventions.md`
