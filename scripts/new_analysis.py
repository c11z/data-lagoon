#!/usr/bin/env python
"""Scaffold a new analysis folder from the two-phase notebook template (no network).

  uv run python scripts/new_analysis.py --slug trends-demo --dataset google_trends

Creates analyses/<YYYYMMDD-or-date>-<slug>/ with notebook.py, data/, queries/, out/.
Then:  uv run marimo edit analyses/<...>/notebook.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

from data_lagoon import config


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slug", required=True, help="short kebab-case name, e.g. trends-demo")
    p.add_argument(
        "--dataset", default="google_trends", help="curated dataset (default google_trends)"
    )
    p.add_argument("--date", help="override the date prefix (default: today, YYYY-MM-DD)")
    args = p.parse_args()

    slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")
    if not slug:
        p.error("--slug must contain at least one alphanumeric character")
    date = args.date or dt.date.today().isoformat()

    analysis_dir = config.ANALYSES_DIR / f"{date}-{slug}"
    if analysis_dir.exists():
        print(json.dumps({"created": False, "error": f"{analysis_dir} already exists"}, indent=2))
        return 1

    for sub in ("data", "queries", "out"):
        (analysis_dir / sub).mkdir(parents=True, exist_ok=True)

    template = (config.TEMPLATES_DIR / "notebook_template.py").read_text()
    notebook = analysis_dir / "notebook.py"
    notebook.write_text(template)
    # Keep gitignored dirs in git so the structure is visible; data/ & out/ stay empty.
    (analysis_dir / "data" / ".gitkeep").touch()
    (analysis_dir / "out" / ".gitkeep").touch()

    result = {
        "created": True,
        "path": str(analysis_dir),
        "notebook": str(notebook),
        "dataset": args.dataset,
        "next": f"uv run marimo edit {notebook}",
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
