#!/usr/bin/env python
"""Estimate bytes scanned for a query WITHOUT running it (free dry-run).

  uv run python scripts/bq_dry_run.py --file analyses/<slug>/queries/q1.sql
  uv run python scripts/bq_dry_run.py --sql "SELECT 1"

Prints a JSON cost estimate. Exit code is non-zero if the query is invalid or would
exceed the hard cap — handy as a pre-execution gate. Requires ADC.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_lagoon import config


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--sql", help="inline SQL string")
    src.add_argument("--file", help="path to a .sql file")
    p.add_argument("--location", default=config.BQ_LOCATION, help="job location (default US)")
    args = p.parse_args()

    sql = Path(args.file).read_text() if args.file else args.sql

    # Import here so --help works without credentials/the bigquery client.
    from data_lagoon.bq import dry_run

    try:
        est = dry_run(sql, location=args.location)
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 2

    result = {
        "valid": True,
        "total_bytes_processed": est.total_bytes_processed,
        "gib": round(est.gib, 4),
        "est_usd": round(est.est_usd, 6),
        "over_soft_threshold": est.over_soft,
        "over_hard_cap": est.over_hard,
        "soft_gib": config.SOFT_GIB,
        "hard_gib": config.HARD_GIB,
    }
    print(json.dumps(result, indent=2))
    return 1 if est.over_hard else 0


if __name__ == "__main__":
    sys.exit(main())
