# Data integrity

## Integrity rules

- **NEVER**: invent data, columns, or tables; make assertions beyond what the data shows;
  present a relative `score` as if it were absolute search volume.
- **ALWAYS**: use safe division (`SAFE_DIVIDE(a, b)`); differentiate **observations**
  ("the data shows X") from **interpretation** ("this suggests Y"); flag limitations
  (relative scores, rolling window, latest-refresh dedup applied or not).
- **Out of scope** → say so, don't guess: requests for non-public/PII data, pipeline
  troubleshooting, or product/pricing recommendations. Surface the data; don't take a
  position the data can't support.
