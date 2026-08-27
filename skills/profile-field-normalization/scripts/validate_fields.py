#!/usr/bin/env python3
"""Validate a portable profile normalization fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

STATUSES = {"unconfirmed", "confirmed", "rejected", "needs_review"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    fields = payload.get("fields")
    if not isinstance(fields, list) or not fields:
        raise SystemExit("fields must be a non-empty array")
    for index, field in enumerate(fields):
        for key in ("field_name", "value", "source_refs", "status", "source_type"):
            if key not in field:
                raise SystemExit(f"fields[{index}] missing {key}")
        if field["status"] not in STATUSES:
            raise SystemExit(f"fields[{index}] has invalid status")
        if field["status"] == "confirmed" and field["source_type"] in {"web_supplement", "ocr"}:
            raise SystemExit("web and OCR fields require explicit control-plane confirmation")
    print(json.dumps({"valid": True, "field_count": len(fields)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
