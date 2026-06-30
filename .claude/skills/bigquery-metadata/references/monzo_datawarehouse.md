# monzo_datawarehouse Tables

Reference doc for `analytics-take-home-test.monzo_datawarehouse`. Kept consistent with
`domainspec/monzo_datawarehouse.yaml` (the machine-readable source of truth). That spec
currently defines **tables only** — no metrics or segments — so queries here are
**hand-written SQL** (still dry-run + hard-capped). Compile from the layer only once a human
ratifies metric/segment definitions into the yaml.

> **Not public data.** This dataset is in the `analytics-take-home-test` project, NOT
> `bigquery-public-data`. Reference the fully-qualified
> `analytics-take-home-test.monzo_datawarehouse.<table>` names; the query bills to your own
> project. `bq_list.py` (which defaults to `bigquery-public-data`) cannot list it — use
> `bq_schema.py --table analytics-take-home-test.monzo_datawarehouse.<table>` instead.

## Quick Reference

### Business Context

Monzo (UK challenger bank) analytics take-home dataset: account lifecycle plus daily
transaction activity, keyed on a hashed account id. Use it for account growth, closures /
churn, reactivation, and transaction activity — and the headline question, counting /
forecasting **"active" accounts** (definition is human-owned; see gotchas). Counts only — no
PII, amounts, or merchants.

### Entity Grain

- `account_created` / `account_closed` / `account_reopened` — one **event** per row.
- `account_transactions` — one **(account, day)** with ≥1 transaction (a **sparse** daily
  panel; absent days = zero, not missing).

### Standard Hygiene Filter

None forced. `account_transactions` is clean (`transactions_num` always ≥1, never NULL). For
splits by `account_type`, add `WHERE account_type IS NOT NULL` inline to drop the 2 NULL rows
(no segment is defined for this).

## Key Tables

| Table | Rows / Size | Grain | Notes |
|---|---|---|---|
| `account_created` | 12,000 / 2.3 MiB | one account (1 row/account) | `account_id` ↔ `user_id` 1:1 here; `account_type` |
| `account_closed` | 4,013 / 0.4 MiB | one closure **event** | 3,909 distinct accts → 104 repeat closures |
| `account_reopened` | 7 / 700 B | one reopen event | every reopened acct ∈ closed |
| `account_transactions` | 308,083 / 31 MiB | one (account, day) ≥1 txn | **sparse panel**; `transactions_num` 1–1000 |

All four are **US**, **NOT partitioned**, coverage **2017-08 → 2020-08** (static snapshot).

## Dimensions

- **Time**: `created_ts` / `closed_ts` / `reopened_ts` (TIMESTAMP) and `date` (DATE on
  `account_transactions`). **No cost-relevant time cut exists** (nothing is partitioned) —
  pass `DATE_TRUNC(date, MONTH)`, `EXTRACT(...)`, etc. as a dimension, but know it does not
  reduce bytes (tables are tiny, so this is fine).
- **Account type** (`account_created` only): `uk_retail` (4,554), `uk_retail_pot` (7,042 —
  savings Pots), `uk_retail_joint` (402), NULL (2). Pair splits with an inline
  `WHERE account_type IS NOT NULL` (drops the 2 NULL rows).
- **Join key**: `account_id_hashed` across all four tables (clean referential integrity).
  `user_id_hashed` is on `account_created` only and is **1:1** with the account here (12,000
  users / 12,000 accounts — a unique user even per Pot; cannot roll accounts up to a person).
  Both ids are opaque **base64-encoded 512-bit one-way hash digests** (88 chars, `==` padding →
  64 high-entropy bytes): deterministic join keys only, **not** decodable to real
  `acc_…`/`user_…` ids (no sequential preimage matches SHA-512/SHA3-512/BLAKE2b).

## Gotchas

- **Not public / location US.** Tables live in `analytics-take-home-test` (needs read access
  on your account) and are in the **US** multi-region — do **not** pass `location='EU'`
  (unlike london_bicycles). `bq_list.py --dataset` won't find them; use `bq_schema.py` with
  the fully-qualified name.
- **Nothing is partitioned.** `account_transactions.date` is a plain DATE, not a partition —
  filtering it does **not** cut bytes. Harmless here: the table is ~31 MiB (rest <3 MiB), well
  under the 1 GiB soft cap. Still no `SELECT *` (contract).
- **`account_transactions` is a SPARSE panel** — grain is (account, day) with ≥1 transaction
  (VERIFIED unique on `(date, account_id_hashed)`). A missing (account, day) = **zero**
  transactions, not missing data: left-join a calendar/account spine and fill 0 for a
  continuous series. `transactions_num` is 1–**1000** (max looks **capped** at 1000).
- **`account_closed` is one closure EVENT, not one account** — 4,013 rows / 3,909 accounts
  (104 repeats), but only **7** reopen events. Closure history is not internally consistent;
  dedupe to one closure per account (MIN/MAX `closed_ts`). Count accounts with
  `COUNT(DISTINCT account_id_hashed)`, closure events with `COUNT(*)`.
- **Accounts ≠ transacting accounts.** Only **4,327 of 12,000** accounts ever transact (Pots
  rarely do) — "number of accounts" and "transacting accounts" differ ~3×. Be explicit about
  the population.
- **Static 2020 snapshot** — coverage ends 2020-08-12; treat "latest" as Aug 2020, not today.
  Freshness anchor: `MAX(date)` on `account_transactions`.
- **"Active accounts" is a business definition** (which types count, what window, how reopens
  are treated) and is deliberately NOT a segment (needs a time-windowed join the compiler does
  not emit). Build it by hand from `account_transactions` — e.g. transacting accounts per
  window, or active account-days — and have a human ratify "active" before reporting it.

## Best Practices / Common Query Patterns

The semantic layer defines no metrics or segments for this dataset yet, so write SQL by hand
(every query still goes through `bq_dry_run.py` → `capped_query(..., location="US")`). Use
`spec_lookup.py --dataset monzo_datawarehouse --query <term>` to browse tables/columns — not
`--compile`, which has nothing to compile here.

```sql
-- Accounts by type (drop the 2 NULL-type rows inline):
SELECT account_type, COUNT(*) AS accounts
FROM `analytics-take-home-test.monzo_datawarehouse.account_created`
WHERE account_type IS NOT NULL
GROUP BY account_type;

-- Monthly transacting accounts (closest building block to "active"):
SELECT DATE_TRUNC(`date`, MONTH) AS month, COUNT(DISTINCT account_id_hashed) AS accounts
FROM `analytics-take-home-test.monzo_datawarehouse.account_transactions`
GROUP BY month;

-- Distinct accounts closed vs. closure events:
SELECT COUNT(DISTINCT account_id_hashed) AS accounts_closed, COUNT(*) AS closure_events
FROM `analytics-take-home-test.monzo_datawarehouse.account_closed`;
```

- No joins are emitted for you: group by `account_id_hashed`, then join `account_created`
  (for `account_type`) in post-processing.
- Tables are tiny and un-partitioned, so a full scan stays far under the soft cap; still no
  `SELECT *`. Freshness anchor is `MAX(date)` on `account_transactions` (≈ 2020-08-12).

## Cross-References

- SQL recipes: `../../bigquery-query/references/sql-patterns.md`
- Cost rules: `../../bigquery-query/references/cost-rules.md`
- Date conventions: `../../bigquery-query/references/date-conventions.md`
