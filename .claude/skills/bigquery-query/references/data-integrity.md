# Data integrity & the provenance footer

## Integrity rules

- **NEVER**: invent data, columns, or tables; make assertions beyond what the data shows;
  present a relative `score` as if it were absolute search volume.
- **ALWAYS**: use safe division (`SAFE_DIVIDE(a, b)`); differentiate **observations**
  ("the data shows X") from **interpretation** ("this suggests Y"); flag limitations
  (relative scores, rolling window, latest-refresh dedup applied or not).
- **Out of scope** → say so, don't guess: requests for non-public/PII data, pipeline
  troubleshooting, or product/pricing recommendations. Surface the data; don't take a
  position the data can't support.

## Provenance footer (end every delivered analysis)

Build it with `data_lagoon.render.provenance_footer(...)`. Format:

```text
> **Source:** semantic layer | curated table | raw exploration ·
> **Confidence:** high | medium | low ·
> **Bytes scanned:** <human bytes> (~$<cost>) ·
> **Freshness:** MAX(refresh_date) = <date> ·
> **Owner:** Google (bigquery-public-data.google_trends) ·
> **Reviewed:** N/A — adversarial reviewer disabled
```

- **Source** tier reflects trust: a compiled metric = "semantic layer"; a curated table
  queried directly = "curated table"; a non-allowlisted dataset = "raw exploration".
- A `raw exploration, freshness unknown` footer is a signal to **verify before forwarding** —
  the one cheap mitigation for the unsolved silent-failure mode.
