#!/usr/bin/env python
"""Run the offline evals: grade each case's compiled/candidate SQL shape and log telemetry.

  uv run python evals/run_evals.py

We grade the QUERY (deterministic, offline) rather than a live number. Every run appends a
row per case to a telemetry parquet under evals/runs/ with skill version, git SHA, model id,
per-case pass/fail, assertion counts, and wall-clock — so "did that change help?" is a query.
Exit code is non-zero if any case fails.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import time

import polars as pl
import yaml

from data_lagoon import __version__, config
from data_lagoon.spec import TimeWindow, compile_metric, load_domainspec

CASES_PATH = config.REPO_ROOT / "evals" / "cases.yaml"
RUNS_DIR = config.REPO_ROOT / "evals" / "runs"


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=config.REPO_ROOT, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def _sql_for_case(spec, case: dict) -> str:
    """Compile the metric, or return the candidate SQL — whatever the case provides."""
    if case.get("metric"):
        c = case.get("compile", {})
        tw = None
        if "last_n_days" in c or "start" in c:
            tw = TimeWindow(
                last_n_days=c.get("last_n_days"), start=c.get("start"), end=c.get("end")
            )
        return compile_metric(
            spec.dataset(case["dataset"]),
            case["metric"],
            dimensions=c.get("dimensions", []),
            segments=c.get("segments", []),
            time_window=tw,
            limit=c.get("limit"),
        )
    return case["candidate_sql"]


def _grade(sql: str, case: dict) -> list[dict]:
    checks = []
    for needle in case.get("must_contain", []):
        checks.append({"kind": "contains", "needle": needle, "passed": needle in sql})
    for needle in case.get("must_not_contain", []):
        checks.append({"kind": "absent", "needle": needle, "passed": needle not in sql})
    return checks


def main() -> int:
    spec = load_domainspec(config.DOMAINSPEC_DIR)
    cases = yaml.safe_load(CASES_PATH.read_text())
    run_ts = dt.datetime.now(dt.UTC).isoformat()
    git_sha = _git_sha()

    rows: list[dict] = []
    all_passed = True
    for case in cases:
        t0 = time.perf_counter()
        try:
            sql = _sql_for_case(spec, case)
            checks = _grade(sql, case)
            passed = all(c["passed"] for c in checks)
        except Exception as exc:
            sql, checks, passed = (
                "",
                [{"kind": "compile", "error": str(exc), "passed": False}],
                False,
            )
        all_passed = all_passed and passed
        rows.append(
            {
                "run_ts": run_ts,
                "case_id": case["id"],
                "passed": passed,
                "n_assert": len(checks),
                "n_passed": sum(c["passed"] for c in checks),
                "git_sha": git_sha,
                "skill_version": __version__,
                "wall_ms": round((time.perf_counter() - t0) * 1000, 2),
                "sql": sql,
            }
        )
        mark = "PASS" if passed else "FAIL"
        print(
            f"[{mark}] {case['id']} ({sum(c['passed'] for c in checks)}/{len(checks)} assertions)"
        )
        for c in checks:
            if not c["passed"]:
                print(f"        ✗ {c}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out = RUNS_DIR / f"{run_ts.replace(':', '-')}.parquet"
    pl.DataFrame(rows).write_parquet(out)

    summary = {
        "ok": all_passed,
        "cases": len(rows),
        "failed": sum(not r["passed"] for r in rows),
        "telemetry": str(out),
    }
    print(json.dumps(summary, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
