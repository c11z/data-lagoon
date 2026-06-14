#!/usr/bin/env python
"""Emit domainspec/_schema.json from the pydantic Dataset model.

Run: uv run python scripts/gen_schema.py
The generated schema gives editors (yaml-language-server) live validation of the
hand-authored domainspec/*.yaml files.
"""

from __future__ import annotations

import json

from data_lagoon.config import DOMAINSPEC_DIR
from data_lagoon.spec import Dataset


def main() -> None:
    schema = Dataset.model_json_schema()
    out = DOMAINSPEC_DIR / "_schema.json"
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
