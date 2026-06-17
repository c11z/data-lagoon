"""DomainSpec — the semantic layer.

The article's highest-trust source of truth is a human-curated semantic layer: compiled
metric and dimension definitions the agent is *structurally required* to use first. This
module is that layer for data-lagoon.

- Pydantic v2 models (``extra="forbid"`` to catch typos in the hand-authored YAML).
- One YAML file per dataset under ``domainspec/`` validates against :class:`Dataset`.
- :func:`compile_metric` is the "build the spec -> compile to SQL" step: it turns a metric
  name + chosen segments + dimensions + a time window into cost-safe BigQuery SQL, always
  emitting a filter on the partition column so a compiled query can never full-scan.

Humans own every metric and segment definition. Claude may draft the prose; it must not
invent the numbers (the article's failed auto-generation experiment).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Column(_Base):
    """A single column in a governed table."""

    name: str
    dtype: str
    description: str | None = None


class Table(_Base):
    """A governed table. ``name`` is fully qualified: ``project.dataset.table``."""

    name: str
    grain: str = Field(description="what exactly one row represents")
    description: str | None = None
    hygiene_filter: str | None = Field(
        default=None, description="WHERE predicate applied to every query in this domain"
    )
    partition_column: str | None = Field(
        default=None, description="the cost-relevant partition; queries MUST filter it"
    )
    shard_suffix: str | None = Field(
        default=None,
        description=(
            "for date-SHARDED wildcard tables (e.g. ga_sessions_*): the pseudo-column "
            "to filter for cost pruning, almost always '_TABLE_SUFFIX'. Filtered with "
            "YYYYMMDD string literals, not DATE literals. Mutually exclusive with "
            "partition_column."
        ),
    )
    time_column: str | None = Field(
        default=None, description="freshness/recency anchor (often == partition_column)"
    )
    columns: list[Column] = []
    join_keys: list[str] = []
    scope_exclusions: str | None = None

    @model_validator(mode="after")
    def _one_cost_anchor(self) -> Table:
        if self.partition_column and self.shard_suffix:
            raise ValueError(
                f"table {self.name!r} sets both partition_column and shard_suffix; "
                "a table is either DATE-partitioned or date-sharded, not both"
            )
        return self


class Segment(_Base):
    """A named canonical population filter.

    Hand-rolled WHERE clauses for these are, per the article, "the dominant wrong-answer
    mode" — so we name them once and reuse them.
    """

    name: str
    sql_predicate: str = Field(description='a boolean SQL expression, e.g. "rank <= 10"')
    description: str


class Metric(_Base):
    """A compiled metric: an aggregation expression bound to a table."""

    name: str
    table: str = Field(description="must match a Table.name in this dataset")
    sql: str = Field(description='the aggregation expression, e.g. "AVG(score)"')
    grain: str
    description: str
    default_segments: list[str] = []
    unnest: list[str] = Field(
        default=[],
        description=(
            "ordered UNNEST sources for metrics over REPEATED records (e.g. "
            '["hits"] or ["hits", "hits.product"]). Each is cross-joined as '
            "UNNEST(<src>) AS <leaf>, where <leaf> is the last path segment; the "
            "metric sql, dimensions, and any segments may reference those aliases."
        ),
    )


class Dataset(_Base):
    """One curated public dataset = one ``domainspec/<name>.yaml`` file."""

    name: str
    location: str = "US"
    business_context: str
    tables: list[Table]
    metrics: list[Metric] = []
    segments: list[Segment] = []
    gotchas: list[str] = []

    @model_validator(mode="after")
    def _check_references(self) -> Dataset:
        table_names = {t.name for t in self.tables}
        segment_names = {s.name for s in self.segments}
        for m in self.metrics:
            if m.table not in table_names:
                raise ValueError(f"metric {m.name!r} references unknown table {m.table!r}")
            for seg in m.default_segments:
                if seg not in segment_names:
                    raise ValueError(f"metric {m.name!r} references unknown segment {seg!r}")
        return self

    # -- lookups ---------------------------------------------------------------
    def table(self, name: str) -> Table:
        for t in self.tables:
            if t.name == name or t.name.endswith(f".{name}"):
                return t
        raise KeyError(f"no table {name!r} in dataset {self.name!r}")

    def metric(self, name: str) -> Metric:
        for m in self.metrics:
            if m.name == name:
                return m
        raise KeyError(f"no metric {name!r} in dataset {self.name!r}")

    def segment(self, name: str) -> Segment:
        for s in self.segments:
            if s.name == name:
                return s
        raise KeyError(f"no segment {name!r} in dataset {self.name!r}")


class DomainSpec(_Base):
    """The aggregate of every curated dataset."""

    datasets: list[Dataset]

    def dataset(self, name: str) -> Dataset:
        for d in self.datasets:
            if d.name == name:
                return d
        raise KeyError(f"no dataset {name!r} in spec")


class TimeWindow(_Base):
    """A cost-safe time filter. Targets the table's partition column unless ``column`` is set.

    Provide exactly one of ``last_n_days`` or (``start`` [and ``end``]).
    """

    column: str | None = None
    last_n_days: int | None = Field(default=None, ge=1)
    start: str | None = Field(default=None, description="inclusive 'YYYY-MM-DD'")
    end: str | None = Field(default=None, description="inclusive 'YYYY-MM-DD'; defaults to today")

    @model_validator(mode="after")
    def _exactly_one(self) -> TimeWindow:
        has_rolling = self.last_n_days is not None
        has_explicit = self.start is not None
        if has_rolling == has_explicit:
            raise ValueError("provide exactly one of last_n_days OR start[/end]")
        return self


# --- loading ------------------------------------------------------------------
def load_dataset(path: str | Path) -> Dataset:
    """Load and validate a single ``domainspec/<name>.yaml`` file."""
    data = yaml.safe_load(Path(path).read_text())
    return Dataset.model_validate(data)


def load_domainspec(directory: str | Path) -> DomainSpec:
    """Load every ``*.yaml`` under ``directory`` into a :class:`DomainSpec`."""
    paths = sorted(p for p in Path(directory).glob("*.yaml"))
    return DomainSpec(datasets=[load_dataset(p) for p in paths])


# --- search (powers spec_lookup.py) -------------------------------------------
def search_dataset(dataset: Dataset, query: str) -> list[dict]:
    """Case-insensitive substring search over metrics, segments, tables, and columns."""
    q = query.lower().strip()
    matches: list[dict] = []

    def hit(*fields: str | None) -> bool:
        return any(f and q in f.lower() for f in fields)

    for m in dataset.metrics:
        if hit(m.name, m.description, m.sql):
            matches.append(
                {
                    "kind": "metric",
                    "name": m.name,
                    "table": m.table,
                    "sql": m.sql,
                    "grain": m.grain,
                    "description": m.description,
                    "default_segments": m.default_segments,
                }
            )
    for s in dataset.segments:
        if hit(s.name, s.description, s.sql_predicate):
            matches.append(
                {
                    "kind": "segment",
                    "name": s.name,
                    "sql_predicate": s.sql_predicate,
                    "description": s.description,
                }
            )
    for t in dataset.tables:
        if hit(t.name, t.grain, t.description):
            matches.append(
                {
                    "kind": "table",
                    "name": t.name,
                    "grain": t.grain,
                    "partition_column": t.partition_column,
                    "description": t.description,
                }
            )
        for c in t.columns:
            if hit(c.name, c.description):
                matches.append(
                    {
                        "kind": "column",
                        "name": c.name,
                        "table": t.name,
                        "dtype": c.dtype,
                        "description": c.description,
                    }
                )
    return matches


# --- the compiler -------------------------------------------------------------
def _time_predicate(table: Table, tw: TimeWindow) -> str:
    col = tw.column or table.partition_column or table.shard_suffix or table.time_column
    if not col:
        raise ValueError(
            f"table {table.name!r} has no partition/time column to filter; "
            "set TimeWindow.column explicitly"
        )
    # Date-sharded wildcard tables prune only on the suffix pseudo-column compared to
    # YYYYMMDD *string* literals; DATE literals or a function wrapper defeat pruning.
    if col == table.shard_suffix and tw.column is None:
        return _shard_predicate(col, tw)
    if tw.last_n_days is not None:
        return f"{col} >= DATE_SUB(CURRENT_DATE(), INTERVAL {tw.last_n_days} DAY)"
    end = tw.end or "CURRENT_DATE()"
    end_sql = "CURRENT_DATE()" if end == "CURRENT_DATE()" else f"DATE '{end}'"
    return f"{col} BETWEEN DATE '{tw.start}' AND {end_sql}"


def _shard_predicate(col: str, tw: TimeWindow) -> str:
    """Cost-pruning filter for a date-sharded table's suffix pseudo-column (YYYYMMDD)."""
    fmt = "FORMAT_DATE('%Y%m%d', {})"
    if tw.last_n_days is not None:
        lower = fmt.format(f"DATE_SUB(CURRENT_DATE(), INTERVAL {tw.last_n_days} DAY)")
        return f"{col} >= {lower}"
    start = tw.start.replace("-", "")  # 'YYYY-MM-DD' -> 'YYYYMMDD'
    end_sql = f"'{tw.end.replace('-', '')}'" if tw.end else fmt.format("CURRENT_DATE()")
    return f"{col} BETWEEN '{start}' AND {end_sql}"


def compile_metric(
    dataset: Dataset,
    metric_name: str,
    *,
    segments: list[str] | None = None,
    dimensions: list[str] | None = None,
    time_window: TimeWindow | None = None,
    limit: int | None = None,
    order_desc: bool = True,
) -> str:
    """Compile a metric request into cost-safe BigQuery SQL.

    Always emits a partition filter when the table is partitioned: a partitioned table
    requested without a ``time_window`` raises rather than silently full-scanning.
    """
    metric = dataset.metric(metric_name)
    table = dataset.table(metric.table)
    dimensions = list(dimensions or [])

    cost_anchor = table.partition_column or table.shard_suffix
    if cost_anchor and time_window is None:
        raise ValueError(
            f"table {table.name!r} is cost-anchored on {cost_anchor!r}; a time_window "
            "is required so the compiled query cannot full-scan"
        )

    # WHERE: time filter (first, for partition pruning) + hygiene + segment predicates.
    seg_names: list[str] = []
    for name in list(metric.default_segments) + list(segments or []):
        if name not in seg_names:
            seg_names.append(name)
    where: list[str] = []
    if time_window is not None:
        where.append(_time_predicate(table, time_window))
    if table.hygiene_filter:
        where.append(table.hygiene_filter)
    where.extend(dataset.segment(name).sql_predicate for name in seg_names)

    # SELECT
    select_items = [*dimensions, f"{metric.sql} AS {metric.name}"]
    lines = ["SELECT"]
    lines.append(",\n".join(f"    {item}" for item in select_items))
    from_line = f"FROM `{table.name}`"
    for src in metric.unnest:
        from_line += f", UNNEST({src}) AS {src.rsplit('.', 1)[-1]}"
    lines.append(from_line)
    if where:
        lines.append("WHERE")
        lines.append(f"    {where[0]}")
        lines.extend(f"    AND {clause}" for clause in where[1:])
    if dimensions:
        lines.append("GROUP BY " + ", ".join(dimensions))
    lines.append(f"ORDER BY {metric.name} {'DESC' if order_desc else 'ASC'}")
    if limit is not None:
        lines.append(f"LIMIT {limit}")
    return "\n".join(lines) + "\n"
