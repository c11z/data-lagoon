"""Central configuration: project, location, cost caps, the curated allowlist.

Everything here is overridable by environment variable so the same code runs against a
different project/sandbox without edits. The cost constants are the single source of truth
for the byte caps enforced in :mod:`data_lagoon.bq` and surfaced by the skills.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- GCP targets --------------------------------------------------------------
PROJECT_ID = os.environ.get("DATA_LAGOON_PROJECT", "c11z-data-lagoon")
PUBLIC_PROJECT = "bigquery-public-data"
BQ_LOCATION = os.environ.get("DATA_LAGOON_LOCATION", "US")  # public data is US multi-region
SCRATCH_DATASET = os.environ.get("DATA_LAGOON_SCRATCH", "scratch")

# --- Cost guardrails ----------------------------------------------------------
GIB = 1024**3  # bytes in a gibibyte; off-by-1000x (GB vs GiB) is an easy, expensive mistake
TIB = 1024**4
# Soft = dry-run warning threshold. Hard = maximum_bytes_billed (job FAILS, no charge, above it).
SOFT_GIB = float(os.environ.get("DATA_LAGOON_SOFT_GIB", "1.0"))
HARD_GIB = float(os.environ.get("DATA_LAGOON_HARD_GIB", "5.0"))
ON_DEMAND_USD_PER_TIB = 6.25  # approximate BigQuery on-demand price; 1 TiB/month is free

# --- Curated allowlist --------------------------------------------------------
# Datasets that get the full treatment: DomainSpec semantic layer + reference doc +
# query enablement. The metadata scripts still introspect ANY bigquery-public-data
# dataset for free (metadata reads scan no bytes) — this only gates curation.
ALLOWLIST: tuple[str, ...] = ("google_trends", "google_analytics_sample")

# --- Repo paths ---------------------------------------------------------------
# parents[2] of src/data_lagoon/config.py is the repo root (editable install keeps source here).
REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAINSPEC_DIR = REPO_ROOT / "domainspec"
ANALYSES_DIR = REPO_ROOT / "analyses"
TEMPLATES_DIR = REPO_ROOT / "templates"


def gib_to_bytes(gib: float) -> int:
    """Convert gibibytes to an integer byte count (for maximum_bytes_billed)."""
    return int(gib * GIB)


def bytes_to_gib(n: int) -> float:
    """Convert a byte count to gibibytes."""
    return n / GIB


def est_usd(bytes_scanned: int) -> float:
    """Estimate the on-demand USD cost of scanning ``bytes_scanned`` (ignores the free tier)."""
    return bytes_scanned / TIB * ON_DEMAND_USD_PER_TIB
