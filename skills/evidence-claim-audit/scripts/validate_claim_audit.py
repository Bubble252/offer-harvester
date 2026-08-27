#!/usr/bin/env python3
"""Validate a portable evidence-claim-audit fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED = {"supported", "unsupported", "stale", "needs_confirmation"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims:
        raise SystemExit("claims must be a non-empty array")
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or not str(claim.get("text", "")).strip():
            raise SystemExit(f"claims[{index}] requires text")
        status = claim.get("status", "needs_confirmation")
        if status not in ALLOWED:
            raise SystemExit(f"claims[{index}] has unsupported status: {status}")
        if not isinstance(claim.get("source_refs", []), list):
            raise SystemExit(f"claims[{index}].source_refs must be an array")
    print(json.dumps({"valid": True, "claim_count": len(claims)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
