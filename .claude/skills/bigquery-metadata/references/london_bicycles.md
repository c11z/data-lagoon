# london_bicycles Tables

Reference doc for `bigquery-public-data.london_bicycles`. Kept consistent with
`domainspec/london_bicycles.yaml` (the machine-readable source of truth — prefer compiling a
metric from it over hand-writing SQL).

## Quick Reference

### Business Context

Transport for London (TfL) **Santander Cycles** public bike-share hires — London's Citi
Bike. Use it for hire volume, trip **duration**, station-to-station flows, and station
**location/capacity**. Durations are real seconds; counts are real hires — not relative.

### Entity Grain

One row = one **bike hire** (a trip from a start dock to an end dock) in `cycle_hire`
(~83.4M rows). `cycle_stations` is a tiny (~800-row) **live snapshot** of docking stations,
one row = one station.

### Standard Hygiene Filter

None forced. For duration analysis use the **`valid_trip`** segment (`duration > 0 AND
start_station_id IS NOT NULL`) to drop dirty rows.

## Key Tables

| Table | Rows / Size | Grain | Notes |
|---|---|---|---|
| `cycle_hire` | 83.4M / 9.57 GiB | one bike hire | **NOT partitioned/sharded**; 2015-01-04 → 2023-01-15 |
| `cycle_stations` | ~800 / 80 KiB | one docking station | **live snapshot** (lat/long, capacity); not history |

## Dimensions

- **Time**: `start_date` / `end_date` (TIMESTAMP, UTC). **No cost-relevant time cut exists**
  (not partitioned) — pass `EXTRACT(HOUR FROM start_date)`, `DATE(start_date)`, etc. as a
  dimension, but know it does not reduce bytes.
- **Geo / station**: `start_station_id` / `end_station_id` (join `cycle_stations.id` for
  lat/long & capacity). Names are denormalized as `start_station_name`/`end_station_name`.
- **Bike model**: `bike_model` (`'CLASSIC'` / `'PBSC_EBIKE'`) — **only from 2022-09-12 on**;
  `''` or `NULL` before. Always pair with the `model_recorded` segment.

## Gotchas

- **LOCATION IS EU, NOT US.** The project default is US; these tables are EU. Every dry-run
  and query MUST pass `location='EU'` (`bq_dry_run.py --location EU`, `capped_query(...,
  location="EU")`) or BigQuery returns 403 "does not have permission / does not exist". This
  is the #1 failure on this dataset.
- **`cycle_hire` is NOT partitioned and NOT sharded** — one physical 9.57 GiB table. There is
  no cost-pruning column; filtering `start_date` does **not** cut bytes. Select only needed
  columns (compiled metrics scan just metric + dimension columns; one INT64/TIMESTAMP column
  ≈ 0.7 GiB). `SELECT *` (~9.6 GiB) exceeds the **5 GiB hard cap**.
- **`bike_model` is only populated from 2022-09-12 onward** (`CLASSIC`/`PBSC_EBIKE`); ~2.4M
  of 83.4M rows. Classic-vs-ebike analysis is valid only for the last ~4 months — use the
  `model_recorded` segment; never assume historical model coverage.
- **Dirty rows**: `duration` (SECONDS) can be 0/negative/NULL (~60k); `start_station_id` is
  NULL for ~230k early rows. Use `valid_trip`. `duration_ms` just repeats `duration` in ms.
- **Coverage 2015-01-04 → 2023-01-15; no longer updated** — "latest" means Jan 2023.
- **`cycle_stations` is a snapshot**, not a time series: `bikes_count`/`nbEmptyDocks`/`locked`
  are one recent reading. Use it for location, capacity, and id→name; never trend availability.

## Best Practices / Common Query Patterns

- Compile from the semantic layer, e.g. mean trip minutes by start station (valid trips):
  `uv run python scripts/spec_lookup.py --dataset london_bicycles --metric avg_duration_min
  --dimensions start_station_name --limit 10 --compile`
- E-bike share among model-recorded hires (2022-09 on):
  `... --metric ebike_share --dimensions "DATE(start_date)" --compile` (then run with
  `--location EU`).
- Station coordinates/capacity: compile grouped by `start_station_id`, then join
  `cycle_stations` (id → latitude/longitude/docks_count) in post-processing — the compiler
  emits no joins.
- Freshness anchor for the provenance footer: `MAX(start_date)` (≈ 2023-01-15).

## Cross-References

- SQL recipes: `../../bigquery-query/references/sql-patterns.md`
- Cost rules: `../../bigquery-query/references/cost-rules.md`
- Date conventions: `../../bigquery-query/references/date-conventions.md`
