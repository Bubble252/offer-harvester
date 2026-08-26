#!/usr/bin/env python3
"""Collect replayable public-only RAG -> audit -> reward Agentic RL traces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agentic_rollout_collector import collect_public_agentic_rollouts  # noqa: E402
from storage import Workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute public-only RAG/Audit/Reward Agentic RL rollout collection."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT / "workspace.eval" / "agentic_rl_rollouts",
        help="Local workspace for public summary index, traces, feedback, and output.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to <workspace>/rl/formal_rollouts.",
    )
    parser.add_argument(
        "--skip-feedback-memory",
        action="store_true",
        help="Do not persist audit feedback/procedural candidates in the local rollout workspace.",
    )
    args = parser.parse_args()

    workspace = Workspace(str(args.workspace))
    output_dir = args.output_dir or (workspace.root / "rl" / "formal_rollouts")
    result = collect_public_agentic_rollouts(
        workspace,
        output_dir,
        record_feedback=not args.skip_feedback_memory,
    )
    payload = dict(result.report)
    payload.update({"workspace": str(workspace.root), "output_dir": str(output_dir)})
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
