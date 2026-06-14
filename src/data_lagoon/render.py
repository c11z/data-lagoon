"""Presentation helpers: human-readable bytes, the provenance footer, and rich tables.

The provenance footer is the article's cheapest trust mechanism — every delivered answer
ends with one so a reader can see the source tier and freshness at a glance.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table as RichTable

from . import config

# A stderr console: status/cost logs go here so stdout stays clean for JSON / piped data.
log_console = Console(stderr=True)


def human_bytes(n: int | None) -> str:
    """Format a byte count as B / KiB / MiB / GiB / TiB."""
    if n is None:
        return "unknown"
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TiB"  # unreachable; satisfies the type checker


def provenance_footer(
    *,
    source: str,
    confidence: str = "medium",
    bytes_scanned: int | None = None,
    freshness: str | None = None,
    owner: str | None = None,
    reviewed: str = "N/A — adversarial reviewer disabled",
) -> str:
    """Build the markdown provenance footer required at the end of every analysis.

    Args:
        source: one of "semantic layer", "curated table", "raw exploration".
        confidence: a tier label, e.g. "high" / "medium" / "low".
        bytes_scanned: bytes billed by the underlying query, if known.
        freshness: the recency anchor, e.g. "MAX(refresh_date) = 2026-06-09".
        owner: the dataset publisher.
        reviewed: review status (default reflects the deferred adversarial reviewer).
    """
    parts = [f"**Source:** {source}", f"**Confidence:** {confidence}"]
    if bytes_scanned is not None:
        cost = config.est_usd(bytes_scanned)
        parts.append(f"**Bytes scanned:** {human_bytes(bytes_scanned)} (~${cost:.4f})")
    if freshness:
        parts.append(f"**Freshness:** {freshness}")
    if owner:
        parts.append(f"**Owner:** {owner}")
    parts.append(f"**Reviewed:** {reviewed}")
    return "> " + " · ".join(parts)


def datasets_table(rows: list[dict], title: str = "BigQuery datasets") -> RichTable:
    """Render a list of dataset dicts (from catalog.list_public_datasets) as a rich table."""
    table = RichTable(title=title)
    table.add_column("dataset_id", style="cyan")
    table.add_column("project", style="dim")
    for r in rows:
        table.add_row(r.get("dataset_id", ""), r.get("project", ""))
    return table


def schema_table(describe: dict) -> RichTable:
    """Render the column schema from catalog.describe_table as a rich table."""
    table = RichTable(title=f"{describe.get('table', '')}  ({human_bytes(describe.get('bytes'))})")
    table.add_column("column", style="cyan")
    table.add_column("type", style="green")
    table.add_column("mode", style="dim")
    table.add_column("description")
    for c in describe.get("columns", []):
        table.add_row(c["name"], c["type"], c.get("mode") or "", c.get("description") or "")
    return table
