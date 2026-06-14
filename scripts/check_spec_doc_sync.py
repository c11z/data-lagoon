#!/usr/bin/env python
"""Staleness guard: every DomainSpec dataset must have a reference doc, kept up to date.

The article's #1 maintenance lesson: offline accuracy drifted ~95% -> ~65% in a month
because docs went stale. This check (wire it into CI / pre-commit) fails when a
domainspec/<name>.yaml has no matching reference doc, or when the YAML is newer than its
doc (a likely-stale doc).

  uv run python scripts/check_spec_doc_sync.py
"""

from __future__ import annotations

import json
import sys

from data_lagoon import config

REFERENCES_DIR = config.REPO_ROOT / ".claude" / "skills" / "bigquery-metadata" / "references"


def main() -> int:
    issues: list[dict] = []
    for yaml_path in sorted(config.DOMAINSPEC_DIR.glob("*.yaml")):
        doc = REFERENCES_DIR / f"{yaml_path.stem}.md"
        if not doc.exists():
            issues.append(
                {
                    "dataset": yaml_path.stem,
                    "problem": "missing reference doc",
                    "expected": str(doc),
                }
            )
        elif yaml_path.stat().st_mtime > doc.stat().st_mtime:
            issues.append(
                {
                    "dataset": yaml_path.stem,
                    "problem": "reference doc older than spec (likely stale)",
                    "doc": str(doc),
                }
            )
    result = {"ok": not issues, "issue_count": len(issues), "issues": issues}
    print(json.dumps(result, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
