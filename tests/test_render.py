"""Tests for presentation helpers."""

from __future__ import annotations

from data_lagoon.render import human_bytes, provenance_footer


def test_human_bytes():
    assert human_bytes(0) == "0 B"
    assert human_bytes(1536) == "1.50 KiB"
    assert human_bytes(1024**3) == "1.00 GiB"
    assert human_bytes(1024**4) == "1.00 TiB"
    assert human_bytes(None) == "unknown"


def test_provenance_footer_minimal():
    footer = provenance_footer(source="semantic layer", confidence="high")
    assert footer.startswith("> ")
    assert "**Source:** semantic layer" in footer
    assert "**Confidence:** high" in footer
    assert "**Reviewed:**" in footer


def test_provenance_footer_with_bytes_and_freshness():
    footer = provenance_footer(
        source="curated table",
        bytes_scanned=1024**3,
        freshness="MAX(refresh_date) = 2026-06-09",
        owner="Google",
    )
    assert "Bytes scanned:** 1.00 GiB" in footer
    assert "Freshness:** MAX(refresh_date) = 2026-06-09" in footer
    assert "Owner:** Google" in footer
