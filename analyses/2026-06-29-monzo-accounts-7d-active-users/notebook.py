"""Monzo accounts model + `active_users_7d_rate` — two-phase analysis notebook (marimo).

PHASE 1 (extract): hits BigQuery EXACTLY ONCE per source table, guarded by a file-existence
check, and freezes the four `monzo_datawarehouse` tables to data/raw_*.parquet. Re-running
reloads the parquet for free.

PIPELINE (DuckDB-on-parquet, the "warehouse"): deterministic local SQL builds the cumulative
account datelist (Task 1) and the user-attributed `active_users_7d_rate` grouping-set cube (Task 2),
each materialised to models/*.parquet. No BigQuery client is imported here, so these cells
cannot re-bill.

Run:    uv run marimo edit analyses/2026-06-29-monzo-accounts-7d-active-users/notebook.py
Export: uv run marimo export html <this notebook> -o out/notebook.html   (then print-to-PDF)
"""

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="medium", auto_download=["html"])


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Monzo — Accounts Model & 7d_active_users Metric

    A reliable **accounts** data model (Task 1) and a user-level **`active_users_7d_rate`**
    metric (Task 2) over `analytics-take-home-test.monzo_datawarehouse`.

    **Approach.** Extract the four nightly-refreshed source tables once to parquet, then build
    everything as **deterministic DuckDB transforms materialised to parquet** (our stand-in for
    production pipelines). The accounts model is a *cumulative datelist*: one row per
    `(snapshot_date, account)` carrying the account's state as of that date, so any historical
    figure is reproducible. The metric is computed in a **grouping-set cube** for fast,
    flexible slicing.

    Deliverable is a PDF of this notebook with independent SQL files representing all tables
    constructed. This project was produced by me (Cory Dominguez) leveraging BigQuery and a custom
    LLM analytics harness called [Data Lagoon](https://github.com/c11z/data-lagoon) that I created
    previously to explore BigQuery public datasets.
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import duckdb
    import plotly.express as px
    import plotly.graph_objects as go
    import polars as pl
    from great_tables import GT

    from data_lagoon import config

    return GT, Path, config, duckdb, go, pl, px


@app.cell
def _(mo):
    mo.md("""
    ## The Dataset

    The BigQuery `monzo_datawarehouse` dataset contains four "nightly-refreshed" tables
    derived from append-only backend logs: `account_created`, `account_closed`,
    `account_reopened` (lifecycle events) and `account_transactions` (a sparse daily
    transaction-count panel). Ids are hashed; counts only (no PII, amounts, or merchants).
    Coverage 2017-08-10 to 2020-08-12 — a static snapshot.

    ### Observations

    - **Sparse activity panel.** `account_transactions` holds one row per (account, day) with
      at least one transaction; a missing (account, day) means **zero**, not missing.
      the source `transactions_num` (exposed as `txn_count`) ranges 1 to 1000 (1000 looks capped).
    - **Closures are event-grain.** 4,013 closure rows for 3,909 accounts (104 repeat
      closures) but only 7 reopens — closure history is not internally consistent, so account status
      needs some resolution through an idempotent state machine.
    - **Account types.** `uk_retail`, `uk_retail_pot` (savings "Pots", which rarely transact),
      `uk_retail_joint`, plus 2 NULLs. Only ~4,327 of 12,000 accounts ever transact.
    - **Opaque hashed ids.** `account_id_hashed` / `user_id_hashed` are base64-encoded 512-bit
      one-way digests (join keys only). user-to-account is empirically 1:1 here, but per the
      brief we treat it as 1:Many.
    - **Static snapshot.** Treat "latest" as 2020-08-12; the final day is partial.
    - **Metric naming.** We deliberately avoid using the name `7d_active_users` as described in the
      brief since it starts with a numeric digit, many SQL engines will require you to quote/escape
      it (e.g. `"7d_active_users"`). Additionally the name is ambiguous — it could be read as a
      **count** of active users rather than a **rate**. Instead we create two metrics
      `active_users_7d_count` (the deduplicated active user count) and `active_users_7d_rate`
      (that count ÷ open users) instead, with `_1d`/`_28d` siblings.

    ### Modelling Assumptions

    1. **Account state machine.** Open from `created_ts` until the latest closure; re-opened by
       a later reopen. Closures are **idempotent** (re-closing keeps it closed). Same-timestamp
       tie-break precedence: `created < closed < reopened`.
    2. **Cumulative datelist.** One row per `(snapshot_date, account)` from creation through
       `GLOBAL_MAX_DATE`, status carried forward — the one-pass equivalent of an incremental
       "build day *D* from *D-1* + new events" table.
    3. **Account dimension dedup.** If a creation is duplicated we keep the **earliest**
       `created_ts` but the **latest** `user_id_hashed` and `account_type` — modelling that
       accounts can transfer between users and that `account_type` might evolve as a slowly-changing
       dimension.
    4. **NULL `account_type` rows are dropped** (only 2) to keep breakdowns clean. In a
       production pipeline we would instead **monitor NULL `account_type` counts** as a
       data-quality signal rather than silently drop them.
    5. **Treat `user_id_hashed`:`account_id_hashed` relationship as 1:Many**; every user
       figure uses `COUNT(DISTINCT user)`, at production scale we would use a more efficient
       function such as `APPROX_DISTINCT()`.
    6. **Sparse activity filled.** Activity is left-joined onto the daily spine and absent days
       filled with 0. Transactions dated **before** an account's creation are **explicitly
       excluded** in `stg_transactions` (`txn_date >= created_date`) — 86 such rows (0.03%).
    7. **`active_users_7d_rate` is user-attributed**: among users holding >=1 *open* account in a
       group, the share who transacted on **any** account in the trailing 7 days. Users with
       only closed accounts are excluded. Group rates are **not additive** (a multi-type user
       counts in each type); the `ALL/ALL/ALL` row is the deduplicated headline.
    8. **Account Age Cohort** coarsely bucketed for simplicity: `0-30 / 31-90 / 91-365 / 366+` days since creation.
    9. **Fixed Time Frame** No `CURRENT_DATE`; `GLOBAL_MAX_DATE` is data-derived, so every
       historical rate is exactly recomputable. The final day (2020-08-12) is partial.
    """)
    return


@app.cell
def _(Path, config, mo):
    # ---- Paths & caps. The model "tables" live in models/ as parquet (DuckDB-backed). ----
    nb_dir = mo.notebook_dir() or Path.cwd()
    DATA = nb_dir / "data"
    MODELS = nb_dir / "models"
    QUERIES = nb_dir / "queries"
    MODELS.mkdir(parents=True, exist_ok=True)
    SOFT_GIB = config.SOFT_GIB
    HARD_GIB = config.HARD_GIB
    SOURCES = {
        "raw_account_created": "01_account_created.sql",
        "raw_account_closed": "02_account_closed.sql",
        "raw_account_reopened": "03_account_reopened.sql",
        "raw_account_transactions": "04_account_transactions.sql",
    }
    # Explicit column lists per source (we never SELECT *, anywhere). The source column
    # `transactions_num` is aliased to our convention `txn_count` here at the staging boundary;
    # the BigQuery source table and cached parquet keep the original upstream name.
    SOURCE_COLS = {
        "raw_account_created": "created_ts, account_type, account_id_hashed, user_id_hashed",
        "raw_account_closed": "closed_ts, account_id_hashed",
        "raw_account_reopened": "reopened_ts, account_id_hashed",
        "raw_account_transactions": "txn_date, account_id_hashed, transactions_num AS txn_count",
    }
    return DATA, HARD_GIB, MODELS, QUERIES, SOFT_GIB, SOURCES, SOURCE_COLS


@app.cell
def extract(DATA, HARD_GIB, QUERIES, SOFT_GIB, SOURCES, mo, pl):
    # ---- BigQuery EXACTLY ONCE per table; guard = file existence on disk. ----
    # capped_query() dry-runs and enforces the hard cap internally before any billable work.
    _lines = []
    for _name, _sqlfile in SOURCES.items():
        _pq = DATA / f"{_name}.parquet"
        if _pq.exists():
            _df = pl.read_parquet(_pq)
            _lines.append(f"✅ `{_pq.name}` ({_df.height:,} rows) — cached, no BigQuery call.")
        else:
            from data_lagoon.bq import capped_query  # imported ONLY on the extract path

            _sql = (QUERIES / _sqlfile).read_text()
            _df = capped_query(_sql, location="US", soft_gib=SOFT_GIB, hard_gib=HARD_GIB)
            _pq.parent.mkdir(parents=True, exist_ok=True)
            _df.write_parquet(_pq, compression="zstd")
            _lines.append(f"💸 Ran BigQuery once, froze `{_pq.name}` ({_df.height:,} rows).")
    mo.md("## Extraction to Parquet for DuckDB\n\n" + "\n\n".join(_lines))
    return


@app.cell
def build_events(DATA, SOURCES, SOURCE_COLS, duckdb, mo):
    # ---- DuckDB connection + staging + the append-only-style event stream. ----
    con = duckdb.connect()
    for _name in SOURCES:
        con.execute(
            f"CREATE OR REPLACE VIEW {_name} AS "
            f"SELECT {SOURCE_COLS[_name]} FROM read_parquet('{DATA / f'{_name}.parquet'}')"
        )
    GLOBAL_MAX_DATE = con.execute("""
        SELECT MAX(d) FROM (
            SELECT MAX(CAST(created_ts AS DATE)) AS d FROM raw_account_created
            UNION ALL SELECT MAX(CAST(closed_ts AS DATE)) FROM raw_account_closed
            UNION ALL SELECT MAX(CAST(reopened_ts AS DATE)) FROM raw_account_reopened
            UNION ALL SELECT MAX(txn_date) FROM raw_account_transactions
        )
    """).fetchone()[0]

    # stg_created: one row per account. Dedup keeps the EARLIEST created_ts but the LATEST
    # user_id_hashed and account_type (accounts can transfer; account_type is a slowly-changing
    # dimension). NULL account_type rows are dropped (only 2; monitored in production).
    con.execute("""
        CREATE OR REPLACE TABLE stg_created AS
        SELECT
            account_id_hashed,
            MAX(user_id_hashed)           AS user_id_hashed,
            MAX(account_type)             AS account_type,
            MIN(created_ts)               AS created_ts,
            CAST(MIN(created_ts) AS DATE) AS created_date
        FROM raw_account_created
        WHERE account_type IS NOT NULL
        GROUP BY account_id_hashed
    """)
    # stg_transactions: activity for modelled accounts, with pre-creation txns EXPLICITLY
    # excluded (txn_date >= created_date) -- an account can't transact before it exists.
    con.execute("""
        CREATE OR REPLACE TABLE stg_transactions AS
        SELECT t.account_id_hashed, t.txn_date, t.txn_count
        FROM raw_account_transactions t
        JOIN stg_created c USING (account_id_hashed)
        WHERE t.txn_date >= c.created_date
    """)
    # account_events: the unified lifecycle stream (created / closed / reopened).
    con.execute("""
        CREATE OR REPLACE TABLE account_events AS
        SELECT account_id_hashed, created_ts  AS event_ts, 'created'  AS event_type FROM stg_created
        UNION ALL
        SELECT account_id_hashed, closed_ts,   'closed'   FROM raw_account_closed
        UNION ALL
        SELECT account_id_hashed, reopened_ts, 'reopened' FROM raw_account_reopened
    """)
    # account_status_events: the resolved status after the LAST event on each (account, day).
    con.execute("""
        CREATE OR REPLACE TABLE account_status_events AS
        SELECT account_id_hashed, event_date, status_after
        FROM (
            SELECT
                account_id_hashed,
                CAST(event_ts AS DATE) AS event_date,
                CASE WHEN event_type IN ('created', 'reopened') THEN 'open' ELSE 'closed' END
                    AS status_after,
                row_number() OVER (
                    PARTITION BY account_id_hashed, CAST(event_ts AS DATE)
                    ORDER BY event_ts DESC,
                        CASE event_type WHEN 'reopened' THEN 3 WHEN 'closed' THEN 2 ELSE 1 END DESC
                ) AS rn
            FROM account_events
        )
        WHERE rn = 1
    """)
    _ev = con.execute(
        "SELECT event_type, COUNT(*) AS n FROM account_events GROUP BY 1 ORDER BY 2 DESC"
    ).pl()
    step_events = True
    mo.vstack([mo.md("## Staging Events and Account State Machine"), _ev])
    return GLOBAL_MAX_DATE, con, step_events


@app.cell
def build_datelist(GLOBAL_MAX_DATE, MODELS, con, mo, step_events):
    # ---- TASK 1: the cumulative account datelist (+ account-level lness l1/l7/l28). ----
    #
    # We rebuild the entire history in one pass because the source is a fixed, static 
    # snapshot, so there are no new days to append, and the rolling columns (l7/l28)
    # and carried-forward `is_open` (last_value UNBOUNDED PRECEDING) all need cross-day
    # history anyway — a single DuckDB pass computes them cheaply.
    #
    # At production scale, with an evolving dataset, we would NOT rebuild all of history
    # daily. we'd partition the table by `snapshot_date` and WRITE_TRUNCATE one partition
    # per run (idempotent re-runs, no full rescan). There would be added complexity: 
    # l7/l28/is_open are cross-partition, so each incremental build must read back a ~28-day
    # lookback (plus the account's prior status) rather than only that day's rows. But this
    # level of cross partition dependency is efficient at pedabyte scale in most modern Warehouses.
    _ = step_events  # ordering dependency
    con.execute(f"""
        CREATE OR REPLACE TABLE account_datelist AS
        WITH spine AS (
            SELECT
                account_id_hashed, user_id_hashed, account_type, created_date,
                CAST(UNNEST(generate_series(created_date, DATE '{GLOBAL_MAX_DATE}', INTERVAL 1 DAY))
                     AS DATE) AS snapshot_date
            FROM stg_created
        ),
        filled AS (
            SELECT
                s.*,
                last_value(d.status_after IGNORE NULLS) OVER (
                    PARTITION BY s.account_id_hashed ORDER BY s.snapshot_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS status
            FROM spine s
            LEFT JOIN account_status_events d
                ON d.account_id_hashed = s.account_id_hashed AND d.event_date = s.snapshot_date
        ),
        act AS (
            SELECT
                f.*,
                CASE WHEN t.txn_count IS NOT NULL THEN 1 ELSE 0 END AS had_txn,
                t.txn_count
            FROM filled f
            LEFT JOIN stg_transactions t
                ON t.account_id_hashed = f.account_id_hashed AND t.txn_date = f.snapshot_date
        )
        SELECT
            snapshot_date, account_id_hashed, user_id_hashed, account_type, created_date,
            datediff('day', created_date, snapshot_date) AS account_age,
            CASE
                WHEN datediff('day', created_date, snapshot_date) <= 30  THEN '0-30 (new)'
                WHEN datediff('day', created_date, snapshot_date) <= 90  THEN '31-90'
                WHEN datediff('day', created_date, snapshot_date) <= 365 THEN '91-365'
                ELSE '366+ (established)'
            END AS account_age_bucket,
            (status = 'open') AS is_open,
            had_txn AS l1,
            CAST(SUM(had_txn) OVER (PARTITION BY account_id_hashed ORDER BY snapshot_date
                 ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS INTEGER)  AS l7,
            CAST(SUM(had_txn) OVER (PARTITION BY account_id_hashed ORDER BY snapshot_date
                 ROWS BETWEEN 27 PRECEDING AND CURRENT ROW) AS INTEGER) AS l28,
            COALESCE(txn_count, 0) AS txn_count
        FROM act
    """)
    con.execute(
        "COPY (SELECT snapshot_date, account_id_hashed, user_id_hashed, account_type, "
        "created_date, account_age, account_age_bucket, is_open, l1, l7, l28, "
        f"txn_count FROM account_datelist) TO '{MODELS / 'account_datelist.parquet'}' "
        "(FORMAT PARQUET)"
    )
    con.execute(
        "COPY (SELECT account_id_hashed, event_ts, event_type FROM account_events) TO "
        f"'{MODELS / 'account_events.parquet'}' (FORMAT PARQUET)"
    )
    datelist_rows = con.execute("SELECT COUNT(*) FROM account_datelist").fetchone()[0]
    _sample = con.execute("""
        SELECT snapshot_date, account_type, account_age_bucket, is_open, txn_count, l1, l7, l28
        FROM account_datelist
        WHERE account_id_hashed = (
            SELECT account_id_hashed FROM account_datelist WHERE l28 > 2 LIMIT 1
        )
        ORDER BY snapshot_date DESC LIMIT 6
    """).pl()
    step_datelist = True
    mo.vstack(
        [
            mo.md(
                "## Task 1 — `account_datelist` Model\n"
                f"**{datelist_rows:,} rows** (one per account per day from creation)"
            ),
            _sample,
        ]
    )
    return datelist_rows, step_datelist


@app.cell
def build_metric(MODELS, con, mo, step_datelist):
    # ---- TASK 2: user-level activity → open-account dimension bridge → grouping-set cube. ----
    _ = step_datelist
    con.execute("""
        CREATE OR REPLACE TABLE user_signup AS
        SELECT user_id_hashed, date_trunc('month', MIN(created_date)) AS signup_cohort
        FROM stg_created GROUP BY user_id_hashed
    """)
    # user_daily: user-attributed activity (any account) over the 1d / 7d / 28d windows.
    con.execute("""
        CREATE OR REPLACE TABLE user_daily AS
        SELECT
            snapshot_date, user_id_hashed,
            MAX(CASE WHEN l1  > 0 THEN 1 ELSE 0 END) AS active_1d,
            MAX(CASE WHEN l7  > 0 THEN 1 ELSE 0 END) AS active_7d,
            MAX(CASE WHEN l28 > 0 THEN 1 ELSE 0 END) AS active_28d
        FROM account_datelist GROUP BY snapshot_date, user_id_hashed
    """)
    # bridge: each open user attributed to the dims of their OPEN accounts (+ user signup cohort).
    con.execute("""
        CREATE OR REPLACE TABLE user_daily_bridge AS
        SELECT DISTINCT
            dl.snapshot_date, dl.user_id_hashed, dl.account_type, dl.account_age_bucket,
            us.signup_cohort
        FROM account_datelist dl
        JOIN user_signup us USING (user_id_hashed)
        WHERE dl.is_open
    """)
    # the cube: active_users_7d_count/_rate (+1d/28d) as metric columns over grouping sets.
    # GROUPING()->'ALL'. Names are `_count` vs `_rate` and don't start with a digit (no escaping).
    con.execute("""
        CREATE OR REPLACE TABLE active_user_cube AS
        SELECT
            b.snapshot_date,
            IF(GROUPING(b.account_type) = 1, 'ALL', b.account_type) AS account_type,
            IF(GROUPING(b.account_age_bucket) = 1, 'ALL', b.account_age_bucket)
                AS account_age_bucket,
            IF(GROUPING(b.signup_cohort) = 1, 'ALL', CAST(b.signup_cohort AS VARCHAR))
                AS signup_cohort,
            COUNT(DISTINCT b.user_id_hashed) AS open_users,
            COUNT(DISTINCT b.user_id_hashed) FILTER (WHERE ud.active_1d = 1)
                AS active_users_1d_count,
            COUNT(DISTINCT b.user_id_hashed) FILTER (WHERE ud.active_7d = 1)
                AS active_users_7d_count,
            COUNT(DISTINCT b.user_id_hashed) FILTER (WHERE ud.active_28d = 1)
                AS active_users_28d_count,
            CAST(COUNT(DISTINCT b.user_id_hashed) FILTER (WHERE ud.active_1d = 1) AS DOUBLE)
                / NULLIF(COUNT(DISTINCT b.user_id_hashed), 0) AS active_users_1d_rate,
            CAST(COUNT(DISTINCT b.user_id_hashed) FILTER (WHERE ud.active_7d = 1) AS DOUBLE)
                / NULLIF(COUNT(DISTINCT b.user_id_hashed), 0) AS active_users_7d_rate,
            CAST(COUNT(DISTINCT b.user_id_hashed) FILTER (WHERE ud.active_28d = 1) AS DOUBLE)
                / NULLIF(COUNT(DISTINCT b.user_id_hashed), 0) AS active_users_28d_rate
        FROM user_daily_bridge b
        JOIN user_daily ud USING (snapshot_date, user_id_hashed)
        GROUP BY b.snapshot_date, GROUPING SETS (
            (),
            (b.account_type),
            (b.account_age_bucket),
            (b.signup_cohort),
            (b.account_type, b.account_age_bucket)
        )
    """)
    con.execute(
        "COPY (SELECT snapshot_date, user_id_hashed, account_type, account_age_bucket, "
        f"signup_cohort FROM user_daily_bridge) TO '{MODELS / 'user_daily_bridge.parquet'}' "
        "(FORMAT PARQUET)"
    )
    con.execute(
        "COPY (SELECT snapshot_date, account_type, account_age_bucket, signup_cohort, "
        "open_users, active_users_1d_count, active_users_7d_count, active_users_28d_count, "
        "active_users_1d_rate, active_users_7d_rate, active_users_28d_rate "
        f"FROM active_user_cube) TO '{MODELS / 'active_user_cube.parquet'}' "
        "(FORMAT PARQUET)"
    )
    metric_rows = con.execute("SELECT COUNT(*) FROM active_user_cube").fetchone()[0]
    _sample = con.execute("""
        SELECT snapshot_date, open_users, active_users_7d_count, active_users_7d_rate
        FROM active_user_cube
        WHERE account_type='ALL' AND account_age_bucket='ALL' AND signup_cohort='ALL'
        ORDER BY snapshot_date DESC LIMIT 5
    """).pl()
    step_metric = True
    mo.vstack(
        [
            mo.md(
                "## Task 2 — `7d_active_users` Metric\n"
                f"**{metric_rows:,} rows** (grouping-set cube: date x dimensions; "
                "`active_users_7d_rate` as the metric column)"
            ),
            _sample,
        ]
    )
    return metric_rows, step_metric


@app.cell
def quality_checks(DATA, GT, MODELS, SOURCE_COLS, duckdb, mo, pl, step_metric):
    # ---- Data quality checks over the PARQUET artifacts (fresh connection). ----
    _ = step_metric
    t = duckdb.connect()
    for _n in SOURCE_COLS:
        t.execute(
            f"CREATE VIEW {_n} AS "
            f"SELECT {SOURCE_COLS[_n]} FROM read_parquet('{DATA / f'{_n}.parquet'}')"
        )
    t.execute(
        "CREATE VIEW account_datelist AS SELECT snapshot_date, account_id_hashed, "
        "account_type, created_date, is_open FROM "
        f"read_parquet('{MODELS / 'account_datelist.parquet'}')"
    )
    t.execute(
        "CREATE TABLE stg AS SELECT account_id_hashed, CAST(MIN(created_ts) AS DATE) created_date "
        "FROM raw_account_created WHERE account_type IS NOT NULL GROUP BY 1"
    )
    _gmax = t.execute("SELECT MAX(snapshot_date) FROM account_datelist").fetchone()[0]

    def q(sql):
        return t.execute(sql).fetchone()[0]

    _dup = q(
        "SELECT COUNT(*) FROM (SELECT snapshot_date, account_id_hashed FROM account_datelist "
        "GROUP BY 1,2 HAVING COUNT(*)>1)"
    )
    _acc_ok = q("SELECT COUNT(DISTINCT account_id_hashed) FROM account_datelist") == q(
        "SELECT COUNT(DISTINCT account_id_hashed) FROM raw_account_created "
        "WHERE account_type IS NOT NULL"
    )
    _span_bad = q(f"""SELECT COUNT(*) FROM (
        SELECT dl.account_id_hashed, COUNT(*) n,
               ANY_VALUE(datediff('day', c.created_date, DATE '{_gmax}')+1) exp,
               MIN(dl.snapshot_date) mn, MAX(dl.snapshot_date) mx, ANY_VALUE(c.created_date) cd
        FROM account_datelist dl JOIN stg c USING (account_id_hashed) GROUP BY 1
        HAVING n<>exp OR mn<>cd OR mx<>DATE '{_gmax}')""")
    _bad_type = q(
        "SELECT COUNT(*) FROM (SELECT DISTINCT account_type FROM account_datelist) "
        "WHERE account_type NOT IN ('uk_retail','uk_retail_pot','uk_retail_joint')"
    )
    _bad_txn = q(
        "SELECT COUNT(*) FROM raw_account_transactions "
        "WHERE txn_count<1 OR txn_count>1000"
    )
    _orph = q(
        "SELECT COUNT(*) FROM (SELECT DISTINCT account_id_hashed FROM raw_account_closed "
        "UNION SELECT DISTINCT account_id_hashed FROM raw_account_transactions) x "
        "WHERE x.account_id_hashed NOT IN (SELECT account_id_hashed FROM raw_account_created)"
    )
    _null_type = q("SELECT COUNT(*) FROM raw_account_created WHERE account_type IS NULL")
    _txn_before = q(
        "SELECT COUNT(*) FROM raw_account_transactions r JOIN stg c USING(account_id_hashed) "
        "WHERE r.txn_date < c.created_date"
    )
    _null_open = q(
        "SELECT COUNT(*) FROM account_datelist WHERE is_open IS NULL OR "
        "(is_open AND snapshot_date < created_date)"
    )
    t.close()

    # Each category rolls up one or more underlying checks. `blocking` failing -> fail (blocks
    # downstream consumption); a tripped `advisory` -> warn (anomaly we remediated in-pipeline).
    def _status(blocking, advisory_clean=True):
        if not blocking:
            return "❌ fail"
        return "✅ pass" if advisory_clean else "⚠️ warn"

    _rows = [
        (
            "1 · Grain / Deduplication",
            _status(_dup == 0),
            f"One row per (snapshot_date, account_id_hashed) — {_dup} duplicate keys. "
            "A duplicate would fan out every downstream aggregate.",
        ),
        (
            "2 · Unexpected NULLs",
            _status(_null_open == 0, _null_type == 0),
            f"Modelled status is never NULL or open-before-creation ({_null_open}). "
            f"Source account_type is NULL on {_null_type} accounts — dropped in-pipeline (2 rows, "
            "immaterial); in production we'd alert on a NULL-rate threshold, not silently drop.",
        ),
        (
            "3 · Referential Integrity",
            _status(_orph == 0),
            f"Every closed or transacting account exists in account_created — {_orph} orphans. "
            "Catches mis-keyed or out-of-order upstream events.",
        ),
        (
            "4 · Dimensional Drift",
            _status(_bad_type == 0 and _bad_txn == 0),
            f"The account_type column stays in the known set ({_bad_type} unexpected) and "
            f"txn_count column within [1, 1000] ({_bad_txn} out of range). A new upstream "
            "category or value surfaces here instead of silently mis-bucketing.",
        ),
        (
            "5 · Reconciliation / Completeness",
            _status(_acc_ok and _span_bad == 0, _txn_before == 0),
            f"Modelled accounts tie back to source and every spine is full-length "
            f"({_span_bad} gappy or short). {_txn_before} transactions pre-date their account's "
            "creation — excluded in-pipeline; in production we'd alert on this clock-skew signal.",
        ),
    ]
    checks_df = pl.DataFrame(
        {
            "category": [r[0] for r in _rows],
            "result": [r[1] for r in _rows],
            "detail": [r[2] for r in _rows],
        }
    )
    blocking_pass = not any("fail" in r[1] for r in _rows)
    mo.vstack(
        [
            mo.md(
                "## Data Quality Checks\n"
                "Assuming raw unvalidated source data here are 7 specific checks associated with "
                "5 categories: (Grain / Deduplication, Unexpected NULLs, Referential "
                "Integrity, Dimensional Drift, and Reconciliation / Completeness) — each rolling up "
                "one or more checks. These would run as intermediate checks after each batch builds "
                "the latest partitions: any failed check blocks downstream consumption "
                "(the datelist and cube are not published). A `warn` marks an anomaly the raw "
                "data exhibited that we remediated in this notebook but would otherwise block in production."
            ),
            GT(checks_df)
            .tab_header(
                title="Accounts model — data quality checks",
                subtitle="pass = clean · warn = anomaly detected, remediated in-pipeline",
            )
            .cols_label(category="Category", result="Result", detail="Detail"),
        ]
    )
    return (blocking_pass,)


@app.cell
def _(MODELS, mo, pl, step_metric):
    # ---- Load the small metric cube for charting (Phase-2: local parquet only). ----
    _ = step_metric
    metric = pl.read_parquet(MODELS / "active_user_cube.parquet")
    # Okabe-Ito: a colour-blind-safe qualitative palette, reused across every chart.
    OKABE_ITO = [
        "#0072B2",  # blue
        "#E69F00",  # orange
        "#009E73",  # bluish green
        "#D55E00",  # vermillion
        "#CC79A7",  # reddish purple
        "#56B4E9",  # sky blue
        "#F0E442",  # yellow
        "#000000",  # black
    ]
    mo.md(
        "## Visualizations — `active_users_7d_rate` over time\n\n"
        "*Rate = users active in the trailing window ÷ users with ≥1 open account "
        "(user-attributed). Early dates are noisy (tiny denominator); the final day is partial.*"
    )
    return OKABE_ITO, metric


@app.cell
def chart_headline(OKABE_ITO, go, metric, pl):
    # Headline: overall 1d / 7d / 28d active-user rate over time (Okabe-Ito palette).
    overall = metric.filter(
        (pl.col("account_type") == "ALL")
        & (pl.col("account_age_bucket") == "ALL")
        & (pl.col("signup_cohort") == "ALL")
    ).sort("snapshot_date")
    fig_headline = go.Figure()
    for _col, _color, _w in (
        ("active_users_1d_rate", OKABE_ITO[2], 1.4),
        ("active_users_28d_rate", OKABE_ITO[1], 1.4),
        ("active_users_7d_rate", OKABE_ITO[0], 2.6),
    ):
        fig_headline.add_scatter(
            x=overall["snapshot_date"],
            y=overall[_col],
            mode="lines",
            name=_col,
            line={"color": _color, "width": _w},
        )
    fig_headline.add_annotation(
        x=overall["snapshot_date"].max(),
        y=overall["active_users_7d_rate"].min(),
        text="final day partial",
        showarrow=True,
        arrowhead=2,
        ax=-55,
        ay=30,
        font={"size": 10, "color": OKABE_ITO[3]},
    )
    fig_headline.update_layout(
        title="Active-user rate over time (all open users)",
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    fig_headline.update_yaxes(title_text="active rate", tickformat=".0%")
    fig_headline.update_xaxes(title_text="snapshot date")
    fig_headline
    return


@app.cell
def chart_by_type(OKABE_ITO, metric, pl, px):
    # active_users_7d_rate by account_type (NULL account_type rows dropped upstream).
    by_type = metric.filter(
        (pl.col("account_type") != "ALL")
        & (pl.col("account_age_bucket") == "ALL")
        & (pl.col("signup_cohort") == "ALL")
    ).sort("snapshot_date")
    fig_type = px.line(
        by_type,
        x="snapshot_date",
        y="active_users_7d_rate",
        color="account_type",
        color_discrete_sequence=OKABE_ITO,
        title="active_users_7d_rate by account_type",
        labels={"snapshot_date": "Date", "active_users_7d_rate": "7d active rate"},
    )
    fig_type.update_layout(template="plotly_white", hovermode="x unified")
    fig_type.update_yaxes(tickformat=".0%")
    fig_type
    return


@app.cell
def chart_by_age(OKABE_ITO, metric, pl, px):
    # active_users_7d_rate by account_age bucket (tenure cohort).
    by_age = metric.filter(
        (pl.col("account_type") == "ALL")
        & (pl.col("account_age_bucket") != "ALL")
        & (pl.col("signup_cohort") == "ALL")
    ).sort("snapshot_date")
    _order = ["0-30 (new)", "31-90", "91-365", "366+ (established)"]
    fig_age = px.line(
        by_age,
        x="snapshot_date",
        y="active_users_7d_rate",
        color="account_age_bucket",
        category_orders={"account_age_bucket": _order},
        color_discrete_sequence=OKABE_ITO,
        title="active_users_7d_rate by account age (tenure)",
        labels={"snapshot_date": "Date", "active_users_7d_rate": "7d active rate"},
    )
    fig_age.update_layout(template="plotly_white", hovermode="x unified")
    fig_age.update_yaxes(tickformat=".0%")
    fig_age
    return


@app.cell
def chart_cohort_heatmap(go, metric, pl):
    # active_users_7d_rate by SIGNUP COHORT, age-aligned (classic retention triangle).
    #
    # signup_cohort partitions users 1:1 (the month of a user's first account), so unlike
    # account_type/age it is a clean, non-overlapping cut of the base. Calendar-time lines would
    # be ~37-way spaghetti; the informative view is RETENTION: align every cohort by age
    # (months since signup) so column j compares each cohort's month-j 7d rate. We sample one
    # point per (cohort, calendar-month) -- the MONTH-END snapshot -- consistent with "as of"
    # semantics and the trailing-7d window.
    _coh = (
        metric.filter(
            (pl.col("account_type") == "ALL")
            & (pl.col("account_age_bucket") == "ALL")
            & (pl.col("signup_cohort") != "ALL")
        )
        .with_columns(
            # signup_cohort is a month-truncated TIMESTAMP rendered as 'YYYY-MM-01 00:00:00';
            # slice the YYYY/MM rather than parse, so the format never bites us.
            pl.col("signup_cohort").str.slice(0, 4).cast(pl.Int32).alias("_cy"),
            pl.col("signup_cohort").str.slice(5, 2).cast(pl.Int32).alias("_cm"),
        )
        .with_columns(
            (
                (pl.col("snapshot_date").dt.year() - pl.col("_cy")) * 12
                + (pl.col("snapshot_date").dt.month() - pl.col("_cm"))
            ).alias("months_since_signup")
        )
        .sort("snapshot_date")
    )
    # One row per (cohort, months_since_signup): the latest (= month-end) snapshot in that month.
    _month_end = _coh.group_by("signup_cohort", "months_since_signup", maintain_order=True).agg(
        pl.col("active_users_7d_rate").last().alias("rate"),
        pl.col("open_users").last().alias("open_users"),
    )
    _rows = _month_end.to_dicts()
    _cohorts = sorted({r["signup_cohort"] for r in _rows})  # oldest -> newest
    _xs = list(range(max(r["months_since_signup"] for r in _rows) + 1))
    _lk = {(r["signup_cohort"], r["months_since_signup"]): r for r in _rows}
    _z = [[(_lk.get((c, m)) or {}).get("rate") for m in _xs] for c in _cohorts]
    _open = [[(_lk.get((c, m)) or {}).get("open_users") for m in _xs] for c in _cohorts]
    _fig = go.Figure(
        go.Heatmap(
            z=_z,
            x=_xs,
            y=[c[:7] for c in _cohorts],  # 'YYYY-MM' label
            customdata=_open,
            colorscale="Viridis",
            zmin=0,
            colorbar={"title": "7d rate", "tickformat": ".0%"},
            hovertemplate=(
                "cohort %{y}<br>month %{x} since signup<br>"
                "7d active rate %{z:.1%}<br>open users %{customdata:,}<extra></extra>"
            ),
        )
    )
    _fig.update_layout(
        title=(
            "active_users_7d_rate by signup cohort, age-aligned"
            "<br><sub>rows = monthly signup cohort · x = months since signup · month-end "
            "snapshots · each row traces one cohort's 7d rate as it ages · "
            "early/small cohorts have noisy denominators</sub>"
        ),
        template="plotly_white",
    )
    _fig.update_xaxes(title_text="months since signup", dtick=3)
    _fig.update_yaxes(title_text="signup cohort", autorange="reversed")  # oldest cohort on top
    _fig
    return


@app.cell
def table_latest(GT, metric, pl):
    # Latest-day snapshot: active_users_7d_rate by account_type x account_age.
    _gmax = metric["snapshot_date"].max()
    latest = (
        metric.filter(
            (pl.col("account_type") != "ALL")
            & (pl.col("account_age_bucket") != "ALL")
            & (pl.col("signup_cohort") == "ALL")
            & (pl.col("snapshot_date") == _gmax)
        )
        .select(
            "account_type",
            "account_age_bucket",
            "open_users",
            "active_users_7d_count",
            "active_users_7d_rate",
        )
        .sort("account_type", "account_age_bucket")
    )
    gt_latest = (
        GT(latest)
        .tab_header(
            title="active_users_7d_rate by type x age",
            subtitle=f"snapshot {_gmax} (final day is partial)",
        )
        .fmt_percent(columns="active_users_7d_rate", decimals=1)
        .fmt_number(columns=["open_users", "active_users_7d_count"], decimals=0, use_seps=True)
        .cols_label(
            account_type="Account type",
            account_age_bucket="Age bucket",
            open_users="Open users",
            active_users_7d_count="Active (7d)",
            active_users_7d_rate="7d rate",
        )
    )
    gt_latest
    return


@app.cell
def _(blocking_pass, datelist_rows, metric_rows, mo):
    _checks = "all pass ✅ (warnings remediated)" if blocking_pass else "FAILED ❌ (blocked)"
    mo.md(
        f"*Models: `account_datelist` ({datelist_rows:,} rows) · "
        f"`active_user_cube` ({metric_rows:,} rows). "
        f"Data quality checks: {_checks}. "
        "`active_users_7d_rate` is user-attributed; the ALL/ALL/ALL row is the headline rate. "
        "Re-run is deterministic (no CURRENT_DATE; data-derived max date).*"
    )
    return


if __name__ == "__main__":
    app.run()
