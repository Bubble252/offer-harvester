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
    DEFAULT_DPO_OUTPUT_DIR_NAME,
    DEFAULT_GRPO_OUTPUT_DIR_NAME,
    DEFAULT_OUTPUT_DIR_NAME,
    DEFAULT_TINY_MODEL_ID,
    SFTTrainingConfig,
    check_training_dependencies,
    prepare_dpo_training_run,
    prepare_grpo_training_run,
    prepare_training_run,
    run_local_dpo_training,
    run_local_grpo_training,
    run_local_sft_training,
)
from agentic_training_readiness import (  # noqa: E402
    evaluate_formal_training_readiness,
    write_formal_training_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or run Agentic RL SFT/DPO with a default Qwen 0.5B LoRA target."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "workspace" / "rl" / "train_ready",
        help="Directory containing sft_messages.jsonl and/or preference_pairs.jsonl.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for split data, config, reports, and optional adapters.",
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "sft", "dpo", "grpo"],
        default="dry-run",
        help="dry-run prepares SFT data only; sft/dpo/grpo can train only with --allow-actual-training.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_TINY_MODEL_ID,
        help="Base model id. Default is the 0.5B Qwen smoke-test target.",
    )
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--max-prompt-length", type=int, default=384)
    parser.add_argument("--max-completion-length", type=int, default=96)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument(
        "--warmup-ratio",
        type=float,
        default=0.05,
        help="Linear warmup ratio. Default 0.05.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=-1,
        help="Override total optimizer steps for smoke training. -1 means epoch-based.",
    )
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--dpo-beta", type=float, default=0.1)
    parser.add_argument("--dpo-loss-type", default="sigmoid")
    parser.add_argument("--grpo-beta", type=float, default=0.04)
    parser.add_argument("--grpo-num-generations", type=int, default=2)
    parser.add_argument("--grpo-temperature", type=float, default=0.7)
    parser.add_argument(
        "--sft-adapter-dir",
        type=Path,
        default=ROOT / "workspace" / "rl" / "training_runs" / DEFAULT_OUTPUT_DIR_NAME / "adapter",
        help="Optional prior SFT adapter for SFT vs DPO smoke evaluation.",
    )
    parser.add_argument(
        "--dpo-adapter-dir",
        type=Path,
        default=ROOT
        / "workspace"
        / "rl"
        / "training_runs"
        / DEFAULT_DPO_OUTPUT_DIR_NAME
        / "adapter",
        help="Optional prior DPO adapter for base/SFT/DPO/GRPO smoke evaluation.",
    )
    parser.add_argument(
        "--allow-actual-training",
        action="store_true",
        help="Required to start local model training in --mode sft, --mode dpo, or --mode grpo.",
    )
    parser.add_argument(
        "--require-formal-readiness",
        action="store_true",
        help=(
            "Before actual training, require executed public rollout provenance, "
            "source-disjoint splits, privacy checks, and per-task data thresholds."
        ),
    )
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow CPU training if CUDA is unavailable. This is usually slow.",
    )
    parser.add_argument(
        "--trainer-backend",
        choices=["auto", "trl-sft", "trl-dpo", "trl-grpo", "hf-trainer"],
        default="auto",
        help="Prefer TRL Trainer when available; fallback to HuggingFace Trainer for SFT in auto mode.",
    )
    parser.add_argument(
        "--skip-eval-after-training",
        action="store_true",
        help="Skip base vs adapter smoke generation after SFT.",
    )
    parser.add_argument("--max-eval-samples", type=int, default=3)
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Only print optional ML dependency readiness.",
    )
    args = parser.parse_args()

    if args.check_deps:
        print(json.dumps(check_training_dependencies().model_dump(), ensure_ascii=False, indent=2))
        return 0

    output_dir = args.output_dir
    if output_dir is None:
        name = {
            "dpo": DEFAULT_DPO_OUTPUT_DIR_NAME,
            "grpo": DEFAULT_GRPO_OUTPUT_DIR_NAME,
        }.get(args.mode, DEFAULT_OUTPUT_DIR_NAME)
        output_dir = ROOT / "workspace" / "rl" / "training_runs" / name

    trainer_backend = args.trainer_backend
    if args.mode == "dpo" and trainer_backend == "auto":
        trainer_backend = "trl-dpo"
    if args.mode == "grpo" and trainer_backend == "auto":
        trainer_backend = "trl-grpo"
    batch_size = args.batch_size
    if args.mode == "grpo" and batch_size < args.grpo_num_generations:
        batch_size = args.grpo_num_generations
    learning_rate = args.learning_rate
    if learning_rate is None:
        if args.mode == "dpo":
            learning_rate = 5e-6
        elif args.mode == "grpo":
            learning_rate = 1e-6
        else:
            learning_rate = 2e-4
    config = SFTTrainingConfig(
        model_id=args.model_id,
        trainer_backend=trainer_backend,
        max_seq_length=args.max_seq_length,
        max_prompt_length=args.max_prompt_length,
        max_completion_length=args.max_completion_length,
        learning_rate=learning_rate,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        dpo_beta=args.dpo_beta,
        dpo_loss_type=args.dpo_loss_type,
        grpo_beta=args.grpo_beta,
        grpo_num_generations=args.grpo_num_generations,
        grpo_temperature=args.grpo_temperature,
        warmup_ratio=args.warmup_ratio,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=args.grad_accum,
    )
    config.lora.r = args.lora_r
    config.lora.lora_alpha = args.lora_alpha
    config.lora.lora_dropout = args.lora_dropout
    if args.mode == "dpo":
        prepared = prepare_dpo_training_run(
            args.dataset_dir,
            output_dir,
            model_id=args.model_id,
            training_config=config,
        )
    elif args.mode == "grpo":
        prepared = prepare_grpo_training_run(
            args.dataset_dir,
            output_dir,
            model_id=args.model_id,
            training_config=config,
        )
    else:
        prepared = prepare_training_run(
            args.dataset_dir,
            output_dir,
            mode=args.mode,
            model_id=args.model_id,
            training_config=config,
        )

    readiness_report = None
    if args.require_formal_readiness:
        readiness_report = evaluate_formal_training_readiness(args.dataset_dir)
        write_formal_training_readiness(
            readiness_report,
            output_dir / "formal_training_readiness.json",
        )
        prepared = prepared.model_copy(
            update={
                "model_eval_report": {
                    **prepared.model_eval_report,
                    "formal_training_readiness": readiness_report.model_dump(),
                }
            }
        )

    if (
        args.mode in {"sft", "dpo", "grpo"}
        and args.allow_actual_training
        and readiness_report is not None
        and not readiness_report.ready
    ):
        prepared = prepared.model_copy(update={"training_status": "formal_readiness_failed"})
    elif args.mode == "sft" and args.allow_actual_training:
        prepared = run_local_sft_training(
            prepared,
            allow_cpu=args.allow_cpu,
            evaluate_after_training=not args.skip_eval_after_training,
            max_eval_samples=args.max_eval_samples,
        )
    elif args.mode == "sft":
        prepared = prepared.model_copy(update={"training_status": "requires_allow_actual_training"})
    elif args.mode == "dpo" and args.allow_actual_training:
        prepared = run_local_dpo_training(
            prepared,
            sft_adapter_dir=args.sft_adapter_dir,
            allow_cpu=args.allow_cpu,
            evaluate_after_training=not args.skip_eval_after_training,
            max_eval_samples=args.max_eval_samples,
        )
    elif args.mode == "dpo":
        prepared = prepared.model_copy(update={"training_status": "requires_allow_actual_training"})
    elif args.mode == "grpo" and args.allow_actual_training:
        prepared = run_local_grpo_training(
            prepared,
            sft_adapter_dir=args.sft_adapter_dir,
            dpo_adapter_dir=args.dpo_adapter_dir,
            allow_cpu=args.allow_cpu,
            evaluate_after_training=not args.skip_eval_after_training,
            max_eval_samples=args.max_eval_samples,
        )
    elif args.mode == "grpo":
        prepared = prepared.model_copy(update={"training_status": "requires_allow_actual_training"})

    print(
        json.dumps(
            prepared.model_dump(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if prepared.dataset_report.valid and prepared.training_status != "formal_readiness_failed"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
