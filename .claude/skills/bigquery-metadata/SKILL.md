---
name: bigquery-metadata
description: >-
  IF the user asks what BigQuery public data exists, about tables/columns/schemas/metrics,
  or to find the right dataset/table/metric for an analytics question — THEN invoke this
  skill to resolve the question against the DomainSpec semantic layer and free table
  metadata BEFORE any SQL is written. DO NOT invoke to write/run queries (use
  bigquery-query) or for questions with no data-warehouse component.
allowed-tools: Bash(uv run:*), Read
---

# BigQuery Metadata — the knowledge router

The entry point for every analytics request. Its one job is to collapse a vague question
into **the right entity** before a query is written — the article's fix for *retrieval
failure*. Always look up before you query.

## Hard rule: semantic layer first

1. **Search the DomainSpec.** If the question maps to a defined **metric** or **segment**,
   use it. Never hand-roll a population filter (a `WHERE` for "top 10", "US only", etc.)
   when a named segment exists — hand-rolled population filters are the dominant
   wrong-answer mode.
2. **If no spec coverage**, route to the matching per-dataset reference doc (PART 3 below).
3. **If the dataset isn't curated**, introspect it with free metadata (`bq_list`/`bq_schema`).

## Quick reference (all free — zero bytes scanned)

| Need | Command |
|---|---|
| Search the semantic layer | `uv run python scripts/spec_lookup.py --query "rising terms"` |
| List curated datasets | `uv run python scripts/bq_list.py --allowlist` |
| List tables in a dataset | `uv run python scripts/bq_list.py --dataset google_trends --with-size` |
| Schema + size + partitioning | `uv run python scripts/bq_schema.py --table bigquery-public-data.google_trends.top_terms` |

## Workflow (Load → Discover → Route)

1. **Load / Discover** — run `spec_lookup.py --query "<concept>"`. Read the matched
   metrics, segments, and tables.
2. **Resolve the entity** — confirm the concrete `dataset.table`, its **grain** (what one
   row is), its **partition column**, and the columns you need via `bq_schema.py`.
3. **Emit a context packet** for the query step: `{table, grain, partition_column,
   hygiene_filter, columns, bytes, freshness}` plus the metric/segments to use.
4. **Hand off** to `bigquery-query` (to run it) or `bigquery-notebook` (for a persistent
   analysis). This skill never runs billable queries.

## PART 3 — Knowledge Base Navigation

Route to ONE reference file; do not load them all.

### google_trends → `references/google_trends.md`

- **Use for**: what's trending / rising in search, by week, by US DMA or by country.
- **Key tables**: `top_terms`, `top_rising_terms`, `international_top_terms`, `international_top_rising_terms`.
- **Never**: query without a `refresh_date` partition filter.

### google_analytics_sample → `references/google_analytics_sample.md`

- **Use for**: web analytics for the Google Merchandise Store — sessions, users, pageviews,
  bounce rate, traffic sources, device/geo, and ecommerce (transactions, revenue, products).
- **Key table**: `ga_sessions_*` (date-SHARDED wildcard; one row = one session; nested `hits`).
- **Never**: query without a `_TABLE_SUFFIX` shard filter (YYYYMMDD strings); never forget
  revenue is in micros.

### new_york_taxi_trips → `references/new_york_taxi_trips.md`

- **Use for**: NYC taxi ride volume, fares, tips, distance, and pickup/dropoff zones —
  yellow/green (full fares) and FHV (pickups only).
- **Key tables**: `tlc_yellow_trips_*`, `tlc_green_trips_*`, `tlc_fhv_trips_*` (year-sharded
  wildcards), `taxi_zone_geom` (zone lookup).
- **Never**: query without a `_TABLE_SUFFIX` year filter; never `SELECT *` (tables are huge
  and unpartitioned).

### london_bicycles → `references/london_bicycles.md`

- **Use for**: London Santander Cycles bike-share — hire volume, trip duration, station-to-
  station flows, and station location/capacity. Coverage 2015-01 to 2023-01.
- **Key tables**: `cycle_hire` (one bike hire; ~83.4M rows, NOT partitioned/sharded),
  `cycle_stations` (live ~800-station snapshot: lat/long, capacity).
- **Never**: query in US — these tables are **EU** (pass `location='EU'`); never `SELECT *`
  (the 9.57 GiB table blows the cap); never assume `bike_model` exists before 2022-09-12.

### Any other public dataset (not curated) → `references/dataset-catalog.md`

- Introspect with `bq_list` / `bq_schema` first; there is no semantic layer for it, so
  treat results as **raw exploration** in the provenance footer.

## When to use / not

- **Use** for "what data do we have", "which table/column/metric", "is X available".
- **Don't use** to author or execute SQL → `bigquery-query`. For a saved analysis →
  `bigquery-notebook`.

## References

| Topic | File | When to read |
|---|---|---|
| google_trends domain | `references/google_trends.md` | any trends question |
| google_analytics_sample domain | `references/google_analytics_sample.md` | web/ecommerce analytics question |
| new_york_taxi_trips domain | `references/new_york_taxi_trips.md` | NYC taxi rides / fares / zones question |
| london_bicycles domain | `references/london_bicycles.md` | London bike-share hires / stations question |
| Non-curated datasets | `references/dataset-catalog.md` | dataset outside the allowlist |
