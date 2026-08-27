from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from models import SourceConnectorLiveTestResult  # noqa: E402
from source_connector_registry import (  # noqa: E402
    merge_live_test_results,
    run_source_connector_live_test,
    scan_source_connector_registry,
)
from storage import Workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded public source connector refresh.")
    parser.add_argument("--workspace", default=str(ROOT / "workspace"))
    parser.add_argument("--connector-id")
    parser.add_argument("--url")
    parser.add_argument("--query")
    parser.add_argument("--ack-tos", action="store_true")
    parser.add_argument("--list-due", action="store_true")
    args = parser.parse_args()

    workspace = Workspace(args.workspace)
    if args.list_due:
        status = scan_source_connector_registry(ROOT)
        results = []
        for item in workspace.list("source_connector_live_tests"):
            results.append(item)
        status = merge_live_test_results(
            status, [SourceConnectorLiveTestResult(**item) for item in results]
        )
        print(
            json.dumps(
                [
                    {
                        "connector_id": item.connector_id,
                        "refresh_state": item.refresh_state,
                        "refresh_due": item.refresh_due,
                        "next_refresh_at": item.next_refresh_at,
                    }
                    for item in status.connectors
                    if item.refresh_due or item.refresh_state in {"not_tested", "needs_review"}
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not args.connector_id or not args.url:
        parser.error("刷新时必须提供 --connector-id 和 --url；仅查看到期项请使用 --list-due。")
    result = run_source_connector_live_test(
        ROOT,
        args.connector_id,
        args.url,
        query=args.query or "",
        tos_acknowledged=args.ack_tos,
    )
    data = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    workspace.write("source_connector_live_tests", data, "result_id")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
