"""The single BigQuery choke point.

Every query that touches BigQuery goes through here, so there is exactly one place where
cost control lives:

1. ``dry_run`` estimates bytes scanned for free (``dry_run=True``).
2. ``capped_query`` dry-runs first, refuses anything over the hard cap, then executes with
   ``maximum_bytes_billed`` set — so even a mis-estimate cannot bill more than the cap
   (the job fails, no charge, instead).

Heavy/optional imports (``google.cloud.bigquery``, ``polars``) are deferred into the
functions so the module imports cleanly in tests and tooling without credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import config
from .render import human_bytes, log_console

if TYPE_CHECKING:  # pragma: no cover
    import polars as pl


class BytesBilledExceeded(RuntimeError):
    """Raised when a query's estimated bytes exceed the hard cap (before it can run)."""


@dataclass
class DryRunResult:
    total_bytes_processed: int
    gib: float
    est_usd: float
    over_soft: bool
    over_hard: bool


def _client(project: str | None = None) -> Any:
    from google.cloud import bigquery

    return bigquery.Client(project=project or config.PROJECT_ID)


def _scalar_params(params: dict[str, Any] | None) -> list[Any]:
    if not params:
        return []
    from google.cloud import bigquery

    out = []
    for key, value in params.items():
        if isinstance(value, bool):
            bq_type = "BOOL"
        elif isinstance(value, int):
            bq_type = "INT64"
        elif isinstance(value, float):
            bq_type = "FLOAT64"
        else:
            bq_type = "STRING"
        out.append(bigquery.ScalarQueryParameter(key, bq_type, value))
    return out


def dry_run(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    location: str | None = None,
    project: str | None = None,
    soft_gib: float | None = None,
    hard_gib: float | None = None,
) -> DryRunResult:
    """Estimate bytes scanned without running the query (free)."""
    from google.cloud import bigquery

    soft = config.SOFT_GIB if soft_gib is None else soft_gib
    hard = config.HARD_GIB if hard_gib is None else hard_gib
    client = _client(project)
    job_config = bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=_scalar_params(params)
    )
    job = client.query(sql, job_config=job_config, location=location or config.BQ_LOCATION)
    n = int(job.total_bytes_processed or 0)
    return DryRunResult(
        total_bytes_processed=n,
        gib=config.bytes_to_gib(n),
        est_usd=config.est_usd(n),
        over_soft=n > config.gib_to_bytes(soft),
        over_hard=n > config.gib_to_bytes(hard),
    )


def _log_estimate(est: DryRunResult, soft: float, hard: float) -> None:
    msg = (
        f"dry-run: {human_bytes(est.total_bytes_processed)} "
        f"(~${est.est_usd:.4f}); soft={soft} GiB hard={hard} GiB"
    )
    if est.total_bytes_processed > config.gib_to_bytes(hard):
        log_console.print(f"[bold red]✗ {msg} — exceeds hard cap[/]")
    elif est.total_bytes_processed > config.gib_to_bytes(soft):
        log_console.print(f"[yellow]⚠ {msg} — over soft threshold[/]")
    else:
        log_console.print(f"[green]✓ {msg}[/]")


def capped_query(
    sql: str,
    *,
    params: dict[str, Any] | None = None,
    hard_gib: float | None = None,
    soft_gib: float | None = None,
    location: str | None = None,
    project: str | None = None,
    verbose: bool = True,
) -> pl.DataFrame:
    """Dry-run, enforce the hard cap, then execute and return a polars DataFrame.

    The result is pulled via the BigQuery Storage API (``create_bqstorage_client=True``)
    into Arrow, then zero-copy into polars. Raises :class:`BytesBilledExceeded` if the
    estimate is over the hard cap (before any billable work happens).
    """
    import polars as pl
    from google.cloud import bigquery

    hard = config.HARD_GIB if hard_gib is None else hard_gib
    soft = config.SOFT_GIB if soft_gib is None else soft_gib

    est = dry_run(sql, params, location=location, project=project, soft_gib=soft, hard_gib=hard)
    if verbose:
        _log_estimate(est, soft, hard)
    if est.total_bytes_processed > config.gib_to_bytes(hard):
        raise BytesBilledExceeded(
            f"query would scan {human_bytes(est.total_bytes_processed)} "
            f"(~${est.est_usd:.4f}), over the {hard} GiB hard cap. Narrow the query "
            "(tighter partition filter, fewer columns, pre-aggregate) or raise hard_gib."
        )

    client = _client(project)
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=config.gib_to_bytes(hard),
        query_parameters=_scalar_params(params),
        use_query_cache=True,
    )
    job = client.query(sql, job_config=job_config, location=location or config.BQ_LOCATION)
    arrow_table = job.result().to_arrow(create_bqstorage_client=True)
    return pl.from_arrow(arrow_table)
