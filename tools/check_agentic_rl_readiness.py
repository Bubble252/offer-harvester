#!/usr/bin/env python3
"""Evaluate whether an Agentic RL dataset may start its first formal LoRA run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agentic_training import DatasetSplitConfig  # noqa: E402
from agentic_training_readiness import (  # noqa: E402
    evaluate_formal_training_readiness,
    write_formal_training_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check public Agentic RL data before the first formal SFT/DPO/GRPO run."
    )
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Defaults to <dataset-dir>/formal_training_readiness.json.",
    )
    parser.add_argument("--min-train-samples-per-task", type=int, default=50)
    parser.add_argument("--min-source-records", type=int, default=15)
    parser.add_argument("--min-rollouts-per-group", type=int, default=3)
    parser.add_argument(
        "--min-valid-sources",
        type=int,
        default=1,
        help="Minimum source-record groups in validation after source-disjoint splitting.",
    )
    parser.add_argument(
        "--min-test-sources",
        type=int,
        default=1,
        help="Minimum source-record groups in test after source-disjoint splitting.",
    )
    args = parser.parse_args()

    report = evaluate_formal_training_readiness(
        args.dataset_dir,
        min_train_samples_per_task=args.min_train_samples_per_task,
        min_source_records=args.min_source_records,
        min_rollouts_per_group=args.min_rollouts_per_group,
        min_valid_source_records=args.min_valid_sources,
        min_test_source_records=args.min_test_sources,
        split_config=DatasetSplitConfig(
            min_valid=args.min_valid_sources,
            min_test=args.min_test_sources,
        ),
    )
    output = args.output or (args.dataset_dir / "formal_training_readiness.json")
    write_formal_training_readiness(report, output)
    payload = report.model_dump()
    payload["report_file"] = str(output)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
