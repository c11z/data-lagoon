#!/usr/bin/env python
"""List BigQuery datasets/tables via free metadata operations (zero bytes scanned).

  uv run python scripts/bq_list.py --allowlist            # curated datasets
  uv run python scripts/bq_list.py                        # all public datasets
  uv run python scripts/bq_list.py --dataset google_trends --with-size

Requires Application Default Credentials (gcloud auth application-default login).
"""

from __future__ import annotations

import argparse
import json
import sys

from data_lagoon import catalog


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", help="list tables in this dataset instead of listing datasets")
    p.add_argument("--allowlist", action="store_true", help="only curated (allowlisted) datasets")
    p.add_argument("--with-size", action="store_true", help="include row/byte counts (free)")
    p.add_argument("--pretty", action="store_true", help="also render a rich table to stderr")
    args = p.parse_args()

    if args.dataset:
        rows = catalog.list_tables(args.dataset, with_size=args.with_size)
        result = {"dataset": args.dataset, "table_count": len(rows), "tables": rows}
    else:
        rows = catalog.list_public_datasets(allowlist_only=args.allowlist)
        result = {"dataset_count": len(rows), "datasets": rows}

    print(json.dumps(result, indent=2))
    if args.pretty and not args.dataset:
        from data_lagoon.render import datasets_table, log_console

        log_console.print(datasets_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
