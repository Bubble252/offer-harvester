#!/usr/bin/env python3
"""Run source-disjoint task-level evaluation for base and LoRA adapters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agentic_task_evaluation import (  # noqa: E402
    run_model_task_level_evaluation,
    write_task_level_report,
)
from agentic_training import DEFAULT_TINY_MODEL_ID, DatasetSplitConfig  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate public RAG/Audit LoRA adapters by source-disjoint task behavior."
    )
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-id", default=DEFAULT_TINY_MODEL_ID)
    parser.add_argument("--sft-adapter", type=Path)
    parser.add_argument("--dpo-adapter", type=Path)
    parser.add_argument("--grpo-adapter", type=Path)
    parser.add_argument("--min-valid-sources", type=int, default=2)
    parser.add_argument("--min-test-sources", type=int, default=10)
    parser.add_argument("--max-cases", type=int, default=120)
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument(
        "--prompt-format",
        choices=["chat", "instruction"],
        default="chat",
        help="Use the same prompt format used by the SFT trainer.",
    )
    args = parser.parse_args()

    adapters = {"base": None}
    for name, path in (
        ("sft", args.sft_adapter),
        ("dpo", args.dpo_adapter),
        ("grpo", args.grpo_adapter),
    ):
        if path and path.exists():
            adapters[name] = path
    report = run_model_task_level_evaluation(
        args.dataset_dir,
        model_id=args.model_id,
        adapters=adapters,
        split_config=DatasetSplitConfig(
            min_valid=args.min_valid_sources,
            min_test=args.min_test_sources,
        ),
        max_cases=args.max_cases,
        max_new_tokens=args.max_new_tokens,
        prompt_format=args.prompt_format,
    )
    paths = write_task_level_report(report, args.output_dir)
    payload = report.model_dump(exclude={"rows"})
    payload["reports"] = paths
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.case_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
