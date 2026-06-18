"""Tests for the DomainSpec semantic layer and its SQL compiler."""

from __future__ import annotations

import pytest

from data_lagoon import config
from data_lagoon.spec import (
    Dataset,
    TimeWindow,
    compile_metric,
    load_dataset,
    load_domainspec,
    search_dataset,
)

SAMPLE = {
    "name": "demo",
    "business_context": "demo dataset",
    "tables": [
        {
            "name": "proj.ds.events",
            "grain": "one event",
            "partition_column": "refresh_date",
            "time_column": "refresh_date",
            "hygiene_filter": "is_valid",
            "columns": [
                {"name": "term", "dtype": "STRING"},
                {"name": "score", "dtype": "INT64"},
            ],
        }
    ],
    "segments": [
        {"name": "top_10", "sql_predicate": "rank <= 10", "description": "top ten"},
    ],
    "metrics": [
        {
            "name": "avg_score",
            "table": "proj.ds.events",
            "sql": "AVG(score)",
            "grain": "avg per group",
            "description": "mean score",
            "default_segments": [],
        }
    ],
}


def _dataset() -> Dataset:
    return Dataset.model_validate(SAMPLE)


def test_extra_keys_forbidden():
    bad = {**SAMPLE, "surprise": 1}
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        Dataset.model_validate(bad)


def test_unknown_metric_table_rejected():
    bad = {**SAMPLE, "metrics": [{**SAMPLE["metrics"][0], "table": "proj.ds.nope"}]}
    with pytest.raises(ValueError, match="unknown table"):
        Dataset.model_validate(bad)


def test_unknown_default_segment_rejected():
    bad = {**SAMPLE, "metrics": [{**SAMPLE["metrics"][0], "default_segments": ["ghost"]}]}
    with pytest.raises(ValueError, match="unknown segment"):
        Dataset.model_validate(bad)


def test_compile_basic_shape():
    sql = compile_metric(
        _dataset(),
        "avg_score",
        dimensions=["term"],
        segments=["top_10"],
        time_window=TimeWindow(last_n_days=7),
        limit=20,
    )
    assert "FROM `proj.ds.events`" in sql
    assert "AVG(score) AS avg_score" in sql
    assert "refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)" in sql
    assert "is_valid" in sql  # hygiene filter applied
    assert "rank <= 10" in sql  # segment predicate applied
    assert "GROUP BY term" in sql
    assert "ORDER BY avg_score DESC" in sql
    assert sql.strip().endswith("LIMIT 20")


def test_compile_requires_time_window_on_partitioned_table():
    with pytest.raises(ValueError, match="time_window is required"):
        compile_metric(_dataset(), "avg_score", dimensions=["term"])


def test_compile_explicit_window():
    sql = compile_metric(
        _dataset(),
        "avg_score",
        time_window=TimeWindow(start="2026-01-01", end="2026-01-31"),
    )
    assert "BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'" in sql
    assert "GROUP BY" not in sql  # no dimensions


def test_timewindow_requires_exactly_one_mode():
    with pytest.raises(ValueError, match="exactly one"):
        TimeWindow()
    with pytest.raises(ValueError, match="exactly one"):
        TimeWindow(last_n_days=7, start="2026-01-01")


def test_search_finds_metric():
    matches = search_dataset(_dataset(), "score")
    kinds = {m["kind"] for m in matches}
    assert "metric" in kinds or "column" in kinds


def test_real_google_trends_spec_loads():
    ds = load_dataset(config.DOMAINSPEC_DIR / "google_trends.yaml")
    assert ds.name == "google_trends"
    # the partitioned tables must declare a partition column (cost safety)
    assert all(t.partition_column == "refresh_date" for t in ds.tables)
    # a known metric compiles to partition-filtered SQL
    sql = compile_metric(
        ds, "avg_score", dimensions=["term"], time_window=TimeWindow(last_n_days=7), limit=10
    )
    assert "refresh_date >=" in sql


def test_load_domainspec_directory():
    spec = load_domainspec(config.DOMAINSPEC_DIR)
    assert "google_trends" in {d.name for d in spec.datasets}


# --- date-sharded (wildcard) tables -------------------------------------------
SHARDED = {
    "name": "ga",
    "business_context": "sharded demo",
    "tables": [
        {
            "name": "proj.ds.ga_sessions_*",
            "grain": "one session",
            "shard_suffix": "_TABLE_SUFFIX",
            "time_column": "date",
        }
    ],
    "segments": [
        {"name": "mobile", "sql_predicate": "device.isMobile", "description": "mobile"},
    ],
    "metrics": [
        {
            "name": "sessions",
            "table": "proj.ds.ga_sessions_*",
            "sql": "COUNT(*)",
            "grain": "session count",
            "description": "sessions",
        },
        {
            "name": "product_revenue",
            "table": "proj.ds.ga_sessions_*",
            "sql": "SUM(product.productRevenue) / 1000000",
            "grain": "revenue per product",
            "description": "product revenue",
            "unnest": ["hits", "hits.product"],
        },
    ],
}


def _sharded() -> Dataset:
    return Dataset.model_validate(SHARDED)


def test_partition_and_shard_mutually_exclusive():
    bad_table = {**SHARDED["tables"][0], "partition_column": "date"}
    bad = {**SHARDED, "tables": [bad_table]}
    with pytest.raises(ValueError, match="not both"):
        Dataset.model_validate(bad)


def test_sharded_requires_time_window():
    with pytest.raises(ValueError, match="time_window is required"):
        compile_metric(_sharded(), "sessions")


def test_sharded_emits_string_suffix_filter():
    sql = compile_metric(
        _sharded(), "sessions", time_window=TimeWindow(start="2017-01-01", end="2017-01-31")
    )
    # string YYYYMMDD literals on the suffix pseudo-column — not DATE literals
    assert "_TABLE_SUFFIX BETWEEN '20170101' AND '20170131'" in sql
    assert "DATE '" not in sql


def test_sharded_last_n_days_uses_format_date():
    sql = compile_metric(_sharded(), "sessions", time_window=TimeWindow(last_n_days=7))
    assert "_TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))" in sql


def test_sharded_yearly_format_renders_year_suffix():
    yearly = {
        **SHARDED,
        "tables": [{**SHARDED["tables"][0], "shard_format": "%Y"}],
        "metrics": [SHARDED["metrics"][0]],
    }
    sql = compile_metric(
        Dataset.model_validate(yearly),
        "sessions",
        time_window=TimeWindow(start="2015-06-01", end="2016-08-31"),
    )
    # sub-year bounds collapse to whole-year suffixes (tables are not sub-year prunable)
    assert "_TABLE_SUFFIX BETWEEN '2015' AND '2016'" in sql


def test_unnest_builds_cross_join_in_from():
    sql = compile_metric(
        _sharded(),
        "product_revenue",
        dimensions=["product.v2ProductName"],
        time_window=TimeWindow(start="2017-01-01", end="2017-01-31"),
    )
    assert (
        "FROM `proj.ds.ga_sessions_*`, UNNEST(hits) AS hits, UNNEST(hits.product) AS product" in sql
    )
    assert "GROUP BY product.v2ProductName" in sql
