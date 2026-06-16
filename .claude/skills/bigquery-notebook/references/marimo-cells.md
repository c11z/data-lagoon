# marimo cell recipes & the two-phase rules

marimo notebooks are pure `.py` files. Cells form a dataflow DAG by variable references, and
**each variable may be defined in only one cell** (no Jupyter-style redefinition). Cells run
on open in every mode (`edit`, `run`, `python nb.py`), so the extraction guard is mandatory.

## The extraction cell (Phase 1) — the only cell that may touch BigQuery

```python
@app.cell
def extract(HARD_GIB, PARAMS, Path, SQL, SOFT_GIB, mo, pl):
    nb_dir = mo.notebook_dir() or Path.cwd()
    pkey = "_".join(f"{k}-{v}" for k, v in PARAMS.items())  # params -> filename
    parquet_path = nb_dir / "data" / f"extract_{pkey}.parquet"
    if parquet_path.exists():
        df = pl.read_parquet(parquet_path)
        bytes_scanned = 0
    else:
        from data_lagoon.bq import capped_query, dry_run  # imported ONLY on this path
        bytes_scanned = dry_run(SQL, soft_gib=SOFT_GIB, hard_gib=HARD_GIB).total_bytes_processed
        df = capped_query(SQL, soft_gib=SOFT_GIB, hard_gib=HARD_GIB)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(parquet_path, compression="zstd")
    return bytes_scanned, df, parquet_path
```

Why a file-existence guard and **not** `@mo.persistent_cache`: persistent_cache keys on the
surrounding code, so an incidental edit silently re-bills, and the cache is opaque. A parquet
file on disk is visible, portable, and invalidated by simply deleting it.

## Phase-2 cells — depend only on `df`

Give each downstream artifact a distinct name (`top`, `fig`, `summary`) — the single-
definition rule forbids redefining `df`. None of these import `google.cloud.bigquery`, so
they cannot re-bill no matter how often marimo re-runs them.

```python
@app.cell
def analyze(df, pl):
    top = df.sort("avg_score", descending=True).head(15)
    top  # last bare expression = the cell's displayed value
    return (top,)
```

## Reusable analysis patterns (build from the frozen `df`)

- **Time series**: `df.group_by("week").agg(pl.col("score").mean())` → line chart.
- **Top-N / ranking**: `df.sort("metric", descending=True).head(n)` → bar + great-table.
- **Rate decomposition**: join two windows and compute `SAFE_DIVIDE`-style deltas in polars.
- **DuckDB for ad-hoc SQL over the parquet** (no BigQuery): `duckdb.sql("SELECT ... FROM read_parquet('data/extract_*.parquet')").pl()`.

## Gotchas

- `mo.notebook_dir()` gives the notebook's folder so `data/` resolves regardless of CWD.
- Don't add a second BigQuery call in a later cell "just to enrich" — add it to the single
  extraction cell (or a second guarded extraction cell with its own parquet).
