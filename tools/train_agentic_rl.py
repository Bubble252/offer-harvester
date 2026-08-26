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

from agentic_training import (  # noqa: E402
    DEFAULT_OUTPUT_DIR_NAME,
    DEFAULT_TINY_MODEL_ID,
    SFTTrainingConfig,
    check_training_dependencies,
    prepare_training_run,
    run_local_sft_training,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or run Agentic RL SFT with a default Qwen 0.5B LoRA target."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "workspace" / "rl" / "train_ready",
        help="Directory containing sft_messages.jsonl.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "workspace" / "rl" / "training_runs" / DEFAULT_OUTPUT_DIR_NAME,
        help="Directory for split data, config, reports, and optional adapters.",
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "sft"],
        default="dry-run",
        help="dry-run prepares data only; sft can train only with --allow-actual-training.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_TINY_MODEL_ID,
        help="Base model id. Default is the 0.5B Qwen smoke-test target.",
    )
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--allow-actual-training",
        action="store_true",
        help="Required to start local model training in --mode sft.",
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow CPU training if CUDA is unavailable. This is usually slow.",
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Only print optional ML dependency readiness.",
    )
    args = parser.parse_args()

    if args.check_deps:
        print(json.dumps(check_training_dependencies().model_dump(), ensure_ascii=False, indent=2))
        return 0

    config = SFTTrainingConfig(
        model_id=args.model_id,
        max_seq_length=args.max_seq_length,
        learning_rate=args.learning_rate,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
    )
    config.lora.r = args.lora_r
    config.lora.lora_alpha = args.lora_alpha
    config.lora.lora_dropout = args.lora_dropout
    prepared = prepare_training_run(
        args.dataset_dir,
        args.output_dir,
        mode=args.mode,
        model_id=args.model_id,
        training_config=config,
    )

    if args.mode == "sft" and args.allow_actual_training:
        prepared = run_local_sft_training(prepared, allow_cpu=args.allow_cpu)
    elif args.mode == "sft":
        prepared = prepared.model_copy(update={"training_status": "requires_allow_actual_training"})

    print(
        json.dumps(
            prepared.model_dump(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if prepared.dataset_report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
