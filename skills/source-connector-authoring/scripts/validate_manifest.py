#!/usr/bin/env python3
"""Validate a portable source connector manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {
    "connector_id",
    "name",
    "version",
    "url_patterns",
    "field_mapping",
    "access_method",
    "robots_checked_at",
    "tos_checked_at",
    "rate_limit_per_minute",
    "refresh_interval_days",
    "fallback",
}
ACCESS = {"public_http", "official_api", "authorized_export", "authorized_oauth"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    missing = sorted(field for field in REQUIRED if field not in payload)
    if missing:
        raise SystemExit(f"missing required fields: {', '.join(missing)}")
    if payload["access_method"] not in ACCESS:
        raise SystemExit("access_method must use an approved access path")
    if int(payload["rate_limit_per_minute"]) < 1 or int(payload["refresh_interval_days"]) < 1:
        raise SystemExit("rate limit and refresh interval must be positive")
    print(json.dumps({"valid": True, "connector_id": payload["connector_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
