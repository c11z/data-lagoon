# new_york_taxi_trips Tables

Reference doc for `bigquery-public-data.new_york_taxi_trips`. Kept consistent with
`domainspec/new_york_taxi_trips.yaml` (the machine-readable source of truth — prefer
compiling a metric from it over hand-writing SQL).

## Quick Reference

### Business Context

NYC Taxi & Limousine Commission (TLC) trip records. **Yellow** and **green** taxis carry
full fare detail; **FHV** (for-hire vehicles) are sparse pickups only (no fares). Use it for
ride volume, fares, tipping, distance, and pickup/dropoff **zone** questions. Scores are
real dollars/miles — not relative.

### Entity Grain

One row = one **trip** (yellow/green) or one **pickup** (FHV). There is **one physical table
per year** (`tlc_yellow_trips_2015`); query the per-service wildcard.

### Standard Hygiene Filter

None forced. For fare analysis use the **`valid_trip`** segment (`fare_amount > 0 AND
trip_distance > 0`) to drop dirty rows.

## Key Tables

| Wildcard | Years | Grain | Notes |
|---|---|---|---|
| `tlc_yellow_trips_*` | 2011-2022 | one yellow trip | flagship; full fares/tips |
| `tlc_green_trips_*` | 2014-2022 | one green trip | yellow schema + ehail/trip_type |
| `tlc_fhv_trips_*` | 2015-2017 | one FHV pickup | **no fares/distance/dropoff**; DATETIME pickup |
| `taxi_zone_geom` | — | one taxi zone (263) | lookup: location_id → name/borough/polygon |

## Dimensions

- **Time**: `pickup_datetime` (TIMESTAMP; DATETIME for FHV). The **year** is the only
  cost-relevant cut. For hour-of-day etc., pass a dimension like
  `EXTRACT(HOUR FROM pickup_datetime)`.
- **Geo**: `pickup_location_id` / `dropoff_location_id` (join `taxi_zone_geom.zone_id`).
- **Payment / rate**: `payment_type` (`'1'`=card, `'2'`=cash), `rate_code`
  (`'2.0'`=JFK) — both string-coded (verified on 2022 data).

## Gotchas

- **NOT partitioned — sharded by YEAR only.** Filter `_TABLE_SUFFIX` by year (`'2015'`). A
  month/day window does **not** cut bytes; the whole matching year table is scanned.
- **Big tables.** A single year of yellow is 15-47 GiB across all columns. Compiled metrics
  scan only their columns, but early years (2011-2017) can still exceed the **5 GiB hard
  cap** even for a few columns — use a recent year (2020-2022) for exploration, or raise
  `DATA_LAGOON_HARD_GIB`. `SELECT *` is forbidden here especially.
- **Cash tips are NOT recorded.** `tip_amount` is meaningful only for card trips
  (`payment_type='1'`). The `tip_pct` metric defaults to the `credit_card` segment.
- **Coded columns are strings**: `payment_type='1'/'2'`, `rate_code='1.0'/'2.0'`.
  `fare_amount`/`total_amount` can be 0 or negative (dirty) — use `valid_trip`.
- **FHV is sparse**: pickups only; no fares/distance/passengers/dropoff; `location_id` is
  INTEGER (CAST to STRING to join zones).
- **Coverage**: green starts 2014, FHV is 2015-2017 only, 2023 tables are empty.

## Best Practices / Common Query Patterns

- Compile from the semantic layer, e.g. tip rate by pickup zone (card trips, 2022):
  `uv run python scripts/spec_lookup.py --dataset new_york_taxi_trips --metric tip_pct
  --dimensions pickup_location_id --start 2022-01-01 --end 2022-12-31 --limit 10 --compile`
- FHV pickup volume by borough (2016):
  `... --metric fhv_trips --dimensions borough --start 2016-01-01 --end 2016-12-31 --compile`
- Zone names: compile grouped by `pickup_location_id`, then join `taxi_zone_geom` in
  post-processing (the compiler does not emit joins).
- Freshness anchor for the provenance footer: `MAX(pickup_datetime)` within the year.

## Cross-References

- SQL recipes: `../../bigquery-query/references/sql-patterns.md`
- Cost rules: `../../bigquery-query/references/cost-rules.md`
- Date conventions: `../../bigquery-query/references/date-conventions.md`
