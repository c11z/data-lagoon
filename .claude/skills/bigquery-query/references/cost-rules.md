# Cost rules & guardrails

BigQuery on-demand bills **bytes scanned to the querying project** (`c11z-data-lagoon`),
~$6.25/TiB after the 1 TiB/month free tier. Querying public data is not free — it bills *us*.

## The non-negotiables

1. **Dry-run before every execute.** `uv run python scripts/bq_dry_run.py --file q.sql`
   returns the byte estimate for free. Read it.
2. **Always set `maximum_bytes_billed`.** `capped_query()` does this automatically (default
   hard cap = 5 GiB). A query over the cap **fails with no charge** — that's the point.
3. **Partition filter or bust.** Every google_trends query MUST filter `refresh_date`.
   Missing it scans the whole table history.

## Myths to reject

- ❌ "`LIMIT 100` makes it cheap." `LIMIT` caps **rows returned**, not **bytes scanned**.
  Cost is unchanged. Use a partition filter and select fewer columns instead.
- ❌ "`SELECT *` is fine for a peek." `SELECT *` scans every column = the most expensive
  thing you can do. Select only the columns you need.
- ❌ "Metadata is expensive." `bq_list` / `bq_schema` (and `get_table`) scan **0 bytes** —
  use them freely to plan before querying.

## Thresholds (defaults, overridable via env)

- **Soft = 1 GiB** — dry-run warns; confirm with the user before running.
- **Hard = 5 GiB** — `maximum_bytes_billed`; the job fails above it.
- Env overrides: `DATA_LAGOON_SOFT_GIB`, `DATA_LAGOON_HARD_GIB`.

## Exfil prudence

Pull aggregates, not raw rows. Freeze results to parquet once (the two-phase notebook), then
analyze locally — never re-run an extraction cell, and never dump a large result set into the
chat. For restricted/PII data (rare in public datasets) return the SQL, not the rows.

## Region trap

The scratch dataset and every job's `location` must be `US` (google_trends is US
multi-region). A location mismatch is the #1 silent failure.
