"""data-lagoon — LLM context harness for analytics over BigQuery public datasets.

The package is the implementation layer that the ``.claude/skills`` tree and the
``scripts/`` CLIs build on:

- :mod:`data_lagoon.config`  — central constants (project, location, cost caps, allowlist).
- :mod:`data_lagoon.spec`    — the DomainSpec semantic layer (pydantic models + compile-to-SQL).
- :mod:`data_lagoon.bq`      — the single BigQuery choke point (dry-run + maximum_bytes_billed).
- :mod:`data_lagoon.catalog` — free metadata introspection (no bytes scanned).
- :mod:`data_lagoon.render`  — rich CLI tables + the provenance footer.
"""

__version__ = "0.1.0"
