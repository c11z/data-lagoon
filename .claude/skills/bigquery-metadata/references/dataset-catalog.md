# Dataset Catalog & Navigation

## Curated datasets (have a semantic layer + reference doc)

These get the full treatment — a `domainspec/<name>.yaml` semantic layer and a reference
doc. Resolve questions through them first.

| Dataset | Reference doc | Use for |
|---|---|---|
| `google_trends` | `google_trends.md` | trending / rising search terms by week, US DMA or country |
| `google_analytics_sample` | `google_analytics_sample.md` | web/ecommerce analytics (sessions, revenue, products) for the Merchandise Store |
| `new_york_taxi_trips` | `new_york_taxi_trips.md` | NYC taxi ride volume, fares, tips, distance, pickup/dropoff zones |

To expand the allowlist, see the project README ("Add a dataset"): author a
`domainspec/<name>.yaml`, regenerate the schema, and write a `references/<name>.md`
following the same skeleton as `google_trends.md`. Add the dataset to
`ALLOWLIST` in `src/data_lagoon/config.py`.

## Non-curated public datasets

The metadata scripts work against **any** `bigquery-public-data` dataset for free — there's
just no semantic layer, so:

- Discover: `uv run python scripts/bq_list.py` (all) or `--dataset <id> --with-size`.
- Inspect: `uv run python scripts/bq_schema.py --table bigquery-public-data.<dataset>.<table>`.
- Treat any answer as **raw exploration** in the provenance footer (lower confidence).
- Be extra careful with cost: large public tables (e.g. `github_repos`, `wikipedia`,
  `crypto_*`) can scan terabytes. Always `bq_dry_run.py` first and keep the hard cap on.

## What this skill does NOT do

- It does not run billable queries → `bigquery-query`.
- It does not track lineage — public datasets have no transformation pipelines (a
  deliberate omission for this harness).
