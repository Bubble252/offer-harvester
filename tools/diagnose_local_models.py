#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from local_model_runtime import (  # noqa: E402
    LocalRuntimeEndpoint,
    check_openai_compatible_service,
    diagnose_hardware,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose optional local model runtime readiness.")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("WORKSPACE_DIR", str(ROOT)),
        help="Path used for disk-space checks.",
    )
    parser.add_argument(
        "--min-free-gb",
        type=float,
        default=30.0,
        help="Minimum free disk space recommended before downloading local models.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LOCAL_LLM_BASE_URL", ""),
        help="Optional local OpenAI-compatible base URL to probe, e.g. http://127.0.0.1:11434/v1.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LOCAL_LLM_API_KEY", ""),
        help="Optional local service API key. The value is not printed.",
    )
    args = parser.parse_args()

    report = {
        "hardware": diagnose_hardware(
            workspace_path=args.workspace,
            min_free_gb=args.min_free_gb,
        ),
        "openai_compatible_service": check_openai_compatible_service(
            LocalRuntimeEndpoint(
                base_url=args.base_url,
                api_key=args.api_key,
                timeout=5,
            )
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
