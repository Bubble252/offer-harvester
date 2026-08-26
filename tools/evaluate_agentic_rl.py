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

from agentic_evaluation import evaluate_agentic_dataset, write_evaluation_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run offline Agentic RL evaluation without network or training."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "workspace" / "rl" / "train_ready",
        help="Directory containing trajectories.jsonl and optional preference_pairs.jsonl.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "workspace.eval" / "agentic_rl",
        help="Directory for JSON and Markdown evaluation reports.",
    )
    parser.add_argument("--task-type", default="", help="Optional task_type filter.")
    parser.add_argument("--strategy", default="", help="Optional strategy id filter.")
    parser.add_argument(
        "--judge-provider",
        choices=["disabled", "mock"],
        default="disabled",
        help="disabled uses only RewardV2 rules; mock adds deterministic local judge scores.",
    )
    parser.add_argument("--min-samples-for-promotion", type=int, default=20)
    parser.add_argument("--min-reward-for-promotion", type=float, default=0.6)
    args = parser.parse_args()

    report = evaluate_agentic_dataset(
        args.dataset_dir,
        task_type=args.task_type,
        strategy=args.strategy,
        judge_provider=args.judge_provider,
        min_samples_for_promotion=args.min_samples_for_promotion,
        min_reward_for_promotion=args.min_reward_for_promotion,
    )
    paths = write_evaluation_report(report, args.output_dir)
    payload = {
        "trajectory_count": report.trajectory_count,
        "recommendation": report.recommendation,
        "global_failure_modes": report.global_failure_modes,
        "preference_evaluation": report.preference_evaluation.model_dump(),
        "reports": paths,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.trajectory_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
