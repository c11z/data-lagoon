#!/usr/bin/env python
"""Resolve a concept against the DomainSpec semantic layer (no network, no cost).

This is the "Discover" + "Compile" steps of the semantic-layer-first workflow:

  # search for relevant metrics/segments/tables/columns
  uv run python scripts/spec_lookup.py --query "rising terms"

  # compile a metric into cost-safe SQL
  uv run python scripts/spec_lookup.py --dataset google_trends --metric avg_score \\
      --dimensions term --segments top_10 --last-n-days 7 --limit 20 --compile

Output is JSON on stdout (use --pretty for a rich rendering on stderr).
"""

from __future__ import annotations

import argparse
import json
import sys

from data_lagoon import config
from data_lagoon.spec import TimeWindow, compile_metric, load_domainspec, search_dataset


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", help="limit to one dataset (e.g. google_trends)")
    p.add_argument("--query", help="substring search over metrics/segments/tables/columns")
    p.add_argument("--metric", help="metric name to compile")
    p.add_argument("--compile", action="store_true", help="compile --metric into SQL")
    p.add_argument("--dimensions", help="comma-separated GROUP BY columns")
    p.add_argument("--segments", help="comma-separated extra segment names")
    p.add_argument("--last-n-days", type=int, help="time window: trailing N days of partitions")
    p.add_argument("--start", help="time window start 'YYYY-MM-DD'")
    p.add_argument("--end", help="time window end 'YYYY-MM-DD' (default today)")
    p.add_argument("--limit", type=int, help="LIMIT for the compiled query")
    p.add_argument("--pretty", action="store_true", help="also pretty-print to stderr")
    args = p.parse_args()

    spec = load_domainspec(config.DOMAINSPEC_DIR)
    datasets = [spec.dataset(args.dataset)] if args.dataset else spec.datasets

    if args.compile or args.metric:
        if not (args.dataset and args.metric):
            p.error("--compile requires --dataset and --metric")
        tw = None
        if args.last_n_days is not None or args.start is not None:
            tw = TimeWindow(last_n_days=args.last_n_days, start=args.start, end=args.end)
        sql = compile_metric(
            spec.dataset(args.dataset),
            args.metric,
            dimensions=_csv(args.dimensions),
            segments=_csv(args.segments),
            time_window=tw,
            limit=args.limit,
        )
        result = {"dataset": args.dataset, "metric": args.metric, "sql": sql}
    elif args.query:
        matches: list[dict] = []
        for ds in datasets:
            for m in search_dataset(ds, args.query):
                matches.append({"dataset": ds.name, **m})
        result = {"query": args.query, "match_count": len(matches), "matches": matches}
    else:
        result = {
            "datasets": [
                {
                    "name": ds.name,
                    "tables": [t.name for t in ds.tables],
                    "metrics": [m.name for m in ds.metrics],
                    "segments": [s.name for s in ds.segments],
                }
                for ds in datasets
            ]
        }

    print(json.dumps(result, indent=2))
    if args.pretty:
        from rich.console import Console

        Console(stderr=True).print_json(data=result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
