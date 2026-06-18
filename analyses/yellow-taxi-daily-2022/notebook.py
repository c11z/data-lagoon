"""NYC yellow-taxi daily trips, 2022 — two-phase analysis notebook (marimo).

PHASE 1 (extract): runs BigQuery EXACTLY ONCE, guarded by a file-existence check, and freezes
daily trip counts to data/daily_trips_2022.parquet. Re-running reloads the parquet for free.

PHASE 2 (analyze/chart): depends ONLY on the local `df`; the BigQuery client is never imported
into these cells, so they cannot re-bill. The chart renders INLINE (bare `fig` expression).

Run with:  uv run marimo edit analyses/yellow-taxi-daily-2022/notebook.py
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
        # NYC Yellow Taxi — daily trips, 2022

        Each row counted as **one distinct trip** (the ~200K spatiotemporal-key collisions
        are left in, per the working assumption). Two-phase: extract daily counts once →
        freeze to parquet → chart locally.
        """
    )


@app.cell
def _():
    from datetime import date
    from pathlib import Path

    import polars as pl

    from data_lagoon import config
    from data_lagoon.render import provenance_footer

    return Path, config, date, pl, provenance_footer


@app.cell
def _config(Path, config, mo):
    # The extraction SQL lives in queries/ (lint-able, version-controlled). It hits the
    # EXPLICIT 2022 table, not the wildcard: airport_fee / pre-2017 location_id do not exist
    # across all shards, so a wildcard scan referencing them errors.
    nb_dir = mo.notebook_dir() or Path.cwd()
    SQL = (nb_dir / "queries" / "01_daily_trips.sql").read_text()
    PARQUET_NAME = "daily_trips_2022.parquet"
    SOFT_GIB = config.SOFT_GIB
    HARD_GIB = config.HARD_GIB
    mo.md(f"**Extraction SQL**\n```sql\n{SQL}```")
    return HARD_GIB, PARQUET_NAME, SOFT_GIB, SQL, nb_dir


@app.cell
def extract(HARD_GIB, PARQUET_NAME, SOFT_GIB, SQL, mo, nb_dir, pl):
    # ---- PHASE 1: BigQuery EXACTLY ONCE; guard = file existence on disk. ----
    parquet_path = nb_dir / "data" / PARQUET_NAME
    if parquet_path.exists():
        df = pl.read_parquet(parquet_path)
        bytes_scanned = 0
        status = mo.md(
            f"✅ Loaded cached `{parquet_path.name}` ({df.height:,} rows) — **no BigQuery call.**"
        )
    else:
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
def analyze(date, df, pl):
    # ---- PHASE 2: local only. Clip to the complete window (source ends Nov 30; Dec 2022 and
    # 18 dirty out-of-2022 dates are dropped) and add a 7-day rolling mean. ----
    clean = (
        df.filter(
            (pl.col("trip_date") >= date(2022, 1, 1))
            & (pl.col("trip_date") <= date(2022, 11, 30))
        )
        .sort("trip_date")
        .with_columns(pl.col("trips").rolling_mean(window_size=7).alias("trips_7d_avg"))
    )
    dropped = df.height - clean.height
    clean
    return clean, dropped


@app.cell
def chart(clean, date):
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_scatter(
        x=clean["trip_date"], y=clean["trips"], mode="lines", name="Daily trips",
        line={"color": "#9ecae1", "width": 1},
    )
    fig.add_scatter(
        x=clean["trip_date"], y=clean["trips_7d_avg"], mode="lines", name="7-day avg",
        line={"color": "#08519c", "width": 2.5},
    )
    fig.add_annotation(
        x=date(2022, 12, 1), y=clean["trips"].max(),
        text="December 2022 absent<br>from source snapshot",
        showarrow=True, arrowhead=2, ax=-60, ay=-20, font={"size": 11, "color": "#a50f15"},
    )
    fig.update_layout(
        title="NYC Yellow Taxi - daily trips, 2022 (Jan 1 to Nov 30)",
        xaxis_title="Pickup date", yaxis_title="Trips per day",
        template="plotly_white", hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    fig  # last bare expression → marimo renders it inline
    return (fig,)


@app.cell
def _(bytes_scanned, dropped, mo, provenance_footer):
    footer = provenance_footer(
        source="raw exploration",
        confidence="high",
        bytes_scanned=bytes_scanned,
        freshness="tlc_yellow_trips_2022 (static); covers Jan 1 - Nov 30, 2022",
        owner="NYC TLC (bigquery-public-data.new_york_taxi_trips)",
    )
    mo.md(
        f"{footer}\n\n*Each row = one trip (collisions ignored). "
        f"{dropped} dirty/out-of-window dates dropped; December 2022 missing from source.*"
    )


if __name__ == "__main__":
    app.run()
