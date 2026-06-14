"""Tests for the BigQuery choke point — cost math and the hard-cap enforcement.

No network: the BigQuery client is replaced with fakes so we exercise the guard logic
(dry-run -> cap check -> capped execution) without credentials.
"""

from __future__ import annotations

import pyarrow as pa
import pytest

from data_lagoon import bq, config


def test_byte_math():
    assert config.gib_to_bytes(1) == 1024**3
    assert config.gib_to_bytes(5) == 5 * 1024**3
    assert config.bytes_to_gib(1024**3) == 1.0
    assert config.est_usd(config.TIB) == pytest.approx(6.25)


def test_scalar_params_type_inference():
    params = bq._scalar_params({"a": 1, "b": "x", "c": 1.5, "d": True})
    by_name = {p.name: p.type_ for p in params}
    assert by_name == {"a": "INT64", "b": "STRING", "c": "FLOAT64", "d": "BOOL"}


class _FakeResult:
    def to_arrow(self, *, create_bqstorage_client=False):
        return pa.table({"term": ["a", "b"], "avg_score": [90, 80]})


class _FakeJob:
    def result(self):
        return _FakeResult()


class _FakeClient:
    def __init__(self):
        self.last_job_config = None

    def query(self, sql, *, job_config, location):
        self.last_job_config = job_config
        return _FakeJob()


def test_capped_query_refuses_over_hard_cap(monkeypatch):
    over = config.gib_to_bytes(99)
    monkeypatch.setattr(
        bq,
        "dry_run",
        lambda *a, **k: bq.DryRunResult(
            over, config.bytes_to_gib(over), config.est_usd(over), True, True
        ),
    )
    # _client must NOT be reached when the estimate is over the cap.
    monkeypatch.setattr(bq, "_client", lambda *a, **k: pytest.fail("should not run the query"))
    with pytest.raises(bq.BytesBilledExceeded):
        bq.capped_query("SELECT 1", hard_gib=5.0, verbose=False)


def test_capped_query_executes_with_cap(monkeypatch):
    small = config.gib_to_bytes(0.001)
    monkeypatch.setattr(
        bq,
        "dry_run",
        lambda *a, **k: bq.DryRunResult(small, config.bytes_to_gib(small), 0.0, False, False),
    )
    fake = _FakeClient()
    monkeypatch.setattr(bq, "_client", lambda *a, **k: fake)
    df = bq.capped_query("SELECT 1", hard_gib=5.0, verbose=False)
    assert df.shape == (2, 2)
    assert df["term"].to_list() == ["a", "b"]
    # the hard cap was actually set on the executed job
    assert fake.last_job_config.maximum_bytes_billed == config.gib_to_bytes(5.0)
