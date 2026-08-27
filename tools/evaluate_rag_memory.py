#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from evaluation import run_rag_memory_evaluation  # noqa: E402
from llm_client import load_local_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local RAG + memory feedback evaluation.")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=ROOT / "tests" / "fixtures" / "evaluation_set",
        help="Path to evaluation fixture set.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT / "workspace.eval",
        help="Workspace directory used for evaluation outputs.",
    )
    parser.add_argument(
        "--storage-backend",
        default="sqlite",
        choices=["json", "sqlite", "chroma"],
        help="RAG storage backend to evaluate.",
    )
    parser.add_argument(
        "--reranker",
        default="noop",
        choices=["noop", "lexical", "env", "siliconflow", "api", "local"],
        help="Local reranker baseline to evaluate.",
    )
    parser.add_argument(
        "--embedding-provider",
        default="hash",
        choices=["hash", "env", "siliconflow", "api", "local"],
        help="Embedding provider to evaluate.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional report output path. Defaults to <workspace>/reports/rag_memory_eval_2026_q3.json.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Do not reset the evaluation workspace before indexing fixtures.",
    )
    args = parser.parse_args()
    load_local_env()
    report = run_rag_memory_evaluation(
        args.fixtures,
        workspace_dir=args.workspace,
        storage_backend=args.storage_backend,
        embedding_provider_name=args.embedding_provider,
        reranker_name=args.reranker,
        reset_workspace=not args.keep_workspace,
        report_path=args.report,
    )
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "embedding": report["embedding"],
                "reranker": report["reranker"],
                "report_path": report["report_path"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
