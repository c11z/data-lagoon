# google_analytics_sample Tables

Reference doc for `bigquery-public-data.google_analytics_sample`. Kept consistent with
`domainspec/google_analytics_sample.yaml` (the machine-readable source of truth — prefer
compiling a metric from it over hand-writing SQL).

## Quick Reference

### Business Context

Google Analytics 360 sample data from the **Google Merchandise Store** (a real ecommerce
site), obfuscated. Answers web-analytics questions: sessions, users, pageviews, bounce rate,
traffic sources, device/geo splits, and ecommerce (transactions, revenue, products). Covers
roughly **2016-08-01 to 2017-08-01**. It is a sampled DEMO, not a population.

### Entity Grain

One row = one **session** (visit). The unique key is `(fullVisitorId, visitId)` —
`visitId` alone is not globally unique. Per-hit detail (pageviews, events, products) lives in
the **REPEATED `hits`** record; `UNNEST(hits)` to drop to hit grain and
`UNNEST(hits.product)` for product grain.

### Standard Hygiene Filter

None beyond the **required** shard filter on `_TABLE_SUFFIX` (see Gotchas).

## Key Tables

### ga_sessions_* (date-sharded sessions)

- **Grain**: one session · **Scope**: Merchandise Store, ~Aug 2016–Aug 2017.
- **Shape**: one physical table per day (`ga_sessions_YYYYMMDD`); query the `ga_sessions_*`
  wildcard. **Not partitioned** — this is the key difference from `google_trends`.
- **Cost filter**: `_TABLE_SUFFIX` (YYYYMMDD string), e.g.
  `WHERE _TABLE_SUFFIX BETWEEN '20170701' AND '20170731'`. Join key: `fullVisitorId, visitId`.

(The dataset also has small helper tables `ga_sessions_20170801`-style shards plus
`Google-ecommerce-dataset-table`; the spec governs only the `ga_sessions_*` wildcard.)

## Dimensions

- **Time**: `date` (STRING 'YYYYMMDD', matches the suffix) and `visitStartTime` (POSIX
  seconds). The shard suffix is the cost-relevant one.
- **Traffic**: `channelGrouping`, `trafficSource.source` / `.medium` / `.campaign`.
- **Device / geo**: `device.deviceCategory` / `.isMobile`, `geoNetwork.country` / `.region`.
- **Hit / product** (need UNNEST): `hits.type`, `hits.page.pagePath`,
  `hits.eCommerceAction.action_type`, `hits.product.v2ProductName`.

## Gotchas

- **Date-SHARDED, not partitioned.** ALWAYS filter `_TABLE_SUFFIX` with **YYYYMMDD string**
  literals. Comparing to a DATE literal or wrapping the suffix in a function defeats shard
  pruning and scans every day. `LIMIT` does not reduce bytes.
- **Revenue is in MICROS.** Divide `totals.totalTransactionRevenue`,
  `hits.transaction.transactionRevenue`, `hits.product.productRevenue` by 1,000,000. The
  compiled revenue metrics already do this.
- **Counts/flags are NULL, not 0**, when the event didn't happen (`totals.bounces`,
  `totals.transactions`, `totals.pageviews`, `totals.timeOnSite`). `SUM()` ignores NULLs
  (correct for `bounce_rate = SUM(bounces)/COUNT(*)`); don't `COUNT()` them.
- **`hits` is REPEATED** (and `hits.product` is repeated within it). Hit/product metrics must
  UNNEST — the compiler does this via a metric's `unnest` list. The hits-level segments
  (`purchase_hits`, `page_hits`) only work on hits-unnested metrics.
- **Static window** (~2016-08 to 2017-08). `--last-n-days` (relative to today) returns
  nothing; use `--start`/`--end` inside that range.
- **ecommerce action_type codes**: `'2'`=product detail, `'3'`=add-to-cart, `'5'`=checkout,
  `'6'`=purchase.

## Best Practices / Common Query Patterns

- Prefer compiling from the semantic layer, e.g. revenue by country (mobile, July 2017):
  `uv run python scripts/spec_lookup.py --dataset google_analytics_sample
  --metric transaction_revenue --dimensions geoNetwork.country --segments mobile
  --start 2017-07-01 --end 2017-07-31 --limit 10 --compile`
- Top products by revenue (hits/product grain, auto-UNNEST):
  `... --metric product_revenue --dimensions product.v2ProductName --start 2017-07-01
  --end 2017-07-31 --compile`
- Freshness anchor for the provenance footer: `MAX(date)` (or the latest shard suffix).
- Treat results as **raw/sample** in the provenance footer (sampled GA360 demo data).

## Cross-References

- SQL recipes: `../../bigquery-query/references/sql-patterns.md`
- Cost rules: `../../bigquery-query/references/cost-rules.md`
- Date conventions: `../../bigquery-query/references/date-conventions.md`
