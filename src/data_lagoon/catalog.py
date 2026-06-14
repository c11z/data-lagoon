"""Free metadata introspection over BigQuery.

Every function here uses metadata-only operations (``list_datasets``, ``list_tables``,
``get_table``) that scan **zero bytes** and so cost nothing. This is the cheap, safe way
to answer "what data exists / what's its shape / how big is it" before any query is run.
"""

from __future__ import annotations

from typing import Any

from . import config


def _client(project: str | None = None) -> Any:
    from google.cloud import bigquery

    return bigquery.Client(project=project or config.PROJECT_ID)


def list_public_datasets(
    *, allowlist_only: bool = False, project: str = config.PUBLIC_PROJECT
) -> list[dict]:
    """List datasets in a project (default: bigquery-public-data). Metadata only — free."""
    client = _client()
    rows = []
    for ds in client.list_datasets(project):
        dataset_id = ds.dataset_id
        if allowlist_only and dataset_id not in config.ALLOWLIST:
            continue
        rows.append({"dataset_id": dataset_id, "project": project})
    return rows


def list_tables(
    dataset_id: str, *, project: str = config.PUBLIC_PROJECT, with_size: bool = False
) -> list[dict]:
    """List tables in a dataset. ``with_size`` adds row/byte counts (free; one get per table)."""
    client = _client()
    ref = f"{project}.{dataset_id}"
    rows = []
    for t in client.list_tables(ref):
        row = {
            "table_id": t.table_id,
            "full": f"{project}.{dataset_id}.{t.table_id}",
            "type": t.table_type,
        }
        if with_size:
            full = client.get_table(t.reference)
            row["rows"] = full.num_rows
            row["bytes"] = full.num_bytes
            row["gib"] = round(config.bytes_to_gib(full.num_bytes or 0), 3)
        rows.append(row)
    return rows


def describe_table(fq_table: str) -> dict:
    """Full metadata for one fully-qualified table (``project.dataset.table``) — free.

    Returns row/byte counts, location, partitioning/clustering, last-modified time, and
    the column schema with descriptions. Note: ``modified`` is a cheap freshness proxy;
    the accurate signal is ``MAX(<partition_column>)`` which requires a (cheap) query.
    """
    client = _client()
    t = client.get_table(fq_table)

    partitioning = None
    if t.time_partitioning is not None:
        partitioning = {
            "kind": "time",
            "type": t.time_partitioning.type_,
            "field": t.time_partitioning.field,
        }
    elif t.range_partitioning is not None:
        partitioning = {"kind": "range", "field": t.range_partitioning.field}

    return {
        "table": fq_table,
        "rows": t.num_rows,
        "bytes": t.num_bytes,
        "gib": round(config.bytes_to_gib(t.num_bytes or 0), 3),
        "location": t.location,
        "description": t.description,
        "partitioning": partitioning,
        "clustering": list(t.clustering_fields or []),
        "modified": t.modified.isoformat() if t.modified else None,
        "columns": [
            {"name": f.name, "type": f.field_type, "mode": f.mode, "description": f.description}
            for f in t.schema
        ],
    }
