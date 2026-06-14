"""data-lagoon two-phase analysis notebook (marimo).

PHASE 1 (extract): hits BigQuery EXACTLY ONCE and freezes the result to parquet under this
analysis folder's data/ directory. The guard is a plain file-existence check — so the cached
data is visible on disk, not hidden in a cache. Re-running the notebook (marimo re-runs cells
reactively) reloads the parquet for free; it never re-queries.

PHASE 2 (analyze/chart/table): depends ONLY on the local `df`. The BigQuery client is never
imported into these cells, so they are structurally incapable of re-billing.

To force a fresh extract: delete the parquet file in data/ (or change a PARAM, which keys a
new filename). Run with:  uv run marimo edit <this notebook>
"""

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # Trending search terms — google_trends

        Two-phase notebook: **extract once → freeze to parquet → analyze locally.**
        Edit the **config** cell below, then run. Phase-1 calls BigQuery only when the
        parquet is missing.
        """
    )


@app.cell
def _():
    from pathlib import Path

    import polars as pl

    from data_lagoon import config
    from data_lagoon.render import provenance_footer
    from data_lagoon.spec import TimeWindow, compile_metric, load_dataset

    return (
        Path,
        TimeWindow,
        compile_metric,
        config,
        load_dataset,
        pl,
        provenance_footer,
    )


@app.cell
def _config(TimeWindow, compile_metric, config, load_dataset, mo):
    # ---- EDIT ME: the analysis request, expressed against the semantic layer ----
    METRIC = "avg_score"
    DIMENSIONS = ["term"]
    SEGMENTS = ["top_10"]  # plus the metric's default segments
    LAST_N_DAYS = 7  # trailing partitions of refresh_date (cost-relevant!)
    LIMIT = 20

    # Cost caps for THIS notebook (bytes). hard = maximum_bytes_billed (job fails over it).
    SOFT_GIB = config.SOFT_GIB
    HARD_GIB = config.HARD_GIB

    # Compile the request to cost-safe SQL via the DomainSpec (always partition-filtered).
    dataset = load_dataset(config.DOMAINSPEC_DIR / "google_trends.yaml")
    SQL = compile_metric(
        dataset,
        METRIC,
        dimensions=DIMENSIONS,
        segments=SEGMENTS,
        time_window=TimeWindow(last_n_days=LAST_N_DAYS),
        limit=LIMIT,
    )
    # PARAMS key the parquet filename: changing one maps to a NEW file (fresh extract),
    # rather than silently reusing stale cached data.
    PARAMS = {"metric": METRIC, "days": LAST_N_DAYS, "limit": LIMIT}
    mo.md(f"**Compiled SQL**\n```sql\n{SQL}```")
    return HARD_GIB, PARAMS, SOFT_GIB, SQL, dataset


@app.cell
def extract(HARD_GIB, PARAMS, Path, SQL, SOFT_GIB, mo, pl):
    # ---- PHASE 1: run BigQuery EXACTLY ONCE; guard = file existence on disk. ----
    nb_dir = mo.notebook_dir() or Path.cwd()
    pkey = "_".join(f"{k}-{v}" for k, v in PARAMS.items())
    parquet_path = nb_dir / "data" / f"extract_{pkey}.parquet"

    if parquet_path.exists():
        df = pl.read_parquet(parquet_path)
        bytes_scanned = 0
        status = mo.md(
            f"✅ Loaded cached `{parquet_path.name}` ({df.height:,} rows) — **no BigQuery call.**"
        )
    else:
        # Imported lazily and only on the extract path: phase-2 cells never see this.
        from data_lagoon.bq import capped_query, dry_run

        bytes_scanned = dry_run(SQL, soft_gib=SOFT_GIB, hard_gib=HARD_GIB).total_bytes_processed
        df = capped_query(SQL, soft_gib=SOFT_GIB, hard_gib=HARD_GIB)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(parquet_path, compression="zstd")
        status = mo.md(
            f"💸 Ran BigQuery once, froze `{parquet_path.name}` ({df.height:,} rows). "
            "Delete the file to force a re-extract."
        )
    status
    return bytes_scanned, df, parquet_path


@app.cell
def analyze(df):
    # ---- PHASE 2: analysis depends ONLY on `df`. No BigQuery client in scope here. ----
    df


@app.cell
def chart(df):
    import plotly.express as px

    # plotly 6 accepts polars directly (via narwhals) — no pandas dependency needed.
    fig = px.bar(df, x="term", y="avg_score", title="Top terms by relative search interest")
    fig
    return (px,)


@app.cell
def table(df):
    from great_tables import GT

    GT(df).tab_header(title="Trending terms", subtitle="from frozen parquet").fmt_number(
        columns="avg_score", decimals=1
    )
    return (GT,)


@app.cell
def _(bytes_scanned, dataset, mo, provenance_footer):
    source = "semantic layer"
    footer = provenance_footer(
        source=source,
        confidence="medium",
        bytes_scanned=bytes_scanned,
        freshness="anchor on MAX(refresh_date) — see queries/",
        owner="Google (bigquery-public-data.google_trends)",
    )
    mo.md(footer)


if __name__ == "__main__":
    app.run()
