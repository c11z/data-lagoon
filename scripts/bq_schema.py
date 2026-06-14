#!/usr/bin/env python
"""Show schema + size + partitioning + freshness for one table (free metadata).

  uv run python scripts/bq_schema.py --table bigquery-public-data.google_trends.top_terms

Requires Application Default Credentials.
"""

from __future__ import annotations

import argparse
import json
import sys

from data_lagoon import catalog


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--table", required=True, help="fully-qualified project.dataset.table")
    p.add_argument(
        "--pretty", action="store_true", help="also render a rich schema table to stderr"
    )
    args = p.parse_args()

    result = catalog.describe_table(args.table)
    print(json.dumps(result, indent=2, default=str))
    if args.pretty:
        from data_lagoon.render import log_console, schema_table

        log_console.print(schema_table(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
