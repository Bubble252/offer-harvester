"""Agentic RL training preparation and optional local SFT entry points.

The default path is dry-run data governance.  Actual model training is optional
and requires explicit CLI confirmation plus external ML dependencies.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

from models import now_iso
from pydantic import BaseModel, Field

DEFAULT_TINY_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_OUTPUT_DIR_NAME = "qwen2_5_0_5b_lora"
DEFAULT_DPO_OUTPUT_DIR_NAME = "qwen2_5_0_5b_dpo_lora"
DEFAULT_GRPO_OUTPUT_DIR_NAME = "qwen2_5_0_5b_grpo_lora"


class TrainingDatasetIssue(BaseModel):
    level: Literal["error", "warning"]
    code: str
    message: str
    row_id: str = ""


class DatasetSplitConfig(BaseModel):
    train_ratio: float = 0.8
    valid_ratio: float = 0.1
    test_ratio: float = 0.1
    min_valid: int = 1
    min_test: int = 1
    seed: int = 20260826


class LoRAConfigSpec(BaseModel):
    r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    target_modules: List[str] = Field(
        default_factory=lambda: [
            "q_proj",
            "v_proj",
            "k_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )


class SFTTrainingConfig(BaseModel):
    schema_version: str = "agentic-rl-local-training.v1"
    model_id: str = DEFAULT_TINY_MODEL_ID
    method: Literal["lora"] = "lora"
    trainer_backend: Literal["auto", "trl-sft", "trl-dpo", "trl-grpo", "hf-trainer"] = "auto"
    max_seq_length: int = 1024
    max_prompt_length: int = 384
    max_completion_length: int = 96
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    num_train_epochs: float = 1.0
    max_steps: int = -1
    dpo_beta: float = 0.1
    dpo_loss_type: str = "sigmoid"
    grpo_beta: float = 0.04
    grpo_num_generations: int = 2
    grpo_temperature: float = 0.7
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8
    fp16_if_cuda: bool = True
    gradient_checkpointing: bool = True
    save_adapter_only: bool = True
    lora: LoRAConfigSpec = Field(default_factory=LoRAConfigSpec)
    created_at: str = Field(default_factory=now_iso)


class TrainingDatasetReport(BaseModel):
    valid: bool
    source_file: str
    total_rows: int = 0
    usable_rows: int = 0
    duplicate_rows: int = 0
    split_counts: Dict[str, int] = Field(default_factory=dict)
    approx_token_stats: Dict[str, float] = Field(default_factory=dict)
    reward_stats: Dict[str, float] = Field(default_factory=dict)
    task_type_counts: Dict[str, int] = Field(default_factory=dict)
    privacy_scan_hits: List[str] = Field(default_factory=list)
    issues: List[TrainingDatasetIssue] = Field(default_factory=list)


class TrainingDependencyReport(BaseModel):
    torch: bool = False
    transformers: bool = False
    peft: bool = False
    accelerate: bool = False
    datasets: bool = False
    trl: bool = False
    grpo_trainer: bool = False

    @property
    def ready_for_sft(self) -> bool:
        return self.torch and self.transformers and self.peft and self.accelerate

    @property
    def ready_for_trl_sft(self) -> bool:
        return self.ready_for_sft and self.datasets and self.trl

    @property
    def ready_for_trl_dpo(self) -> bool:
        return self.ready_for_trl_sft

    @property
    def ready_for_trl_grpo(self) -> bool:
        return self.ready_for_trl_sft and self.grpo_trainer


class PreparedTrainingRun(BaseModel):
    mode: Literal["dry-run", "sft", "dpo", "grpo"]
    output_dir: str
    config: SFTTrainingConfig
    dataset_report: TrainingDatasetReport
    dependencies: TrainingDependencyReport
    split_files: Dict[str, str] = Field(default_factory=dict)
    training_started: bool = False
    training_status: str = "not_started"
    trainer_backend_used: str = ""
    model_eval_report: Dict[str, Any] = Field(default_factory=dict)


def prepare_training_run(
    dataset_dir: Path,
    output_dir: Path,
    *,
    mode: Literal["dry-run", "sft"] = "dry-run",
    model_id: str = DEFAULT_TINY_MODEL_ID,
    split_config: Optional[DatasetSplitConfig] = None,
    training_config: Optional[SFTTrainingConfig] = None,
) -> PreparedTrainingRun:
    rows = load_sft_messages(dataset_dir)
    split_config = split_config or DatasetSplitConfig()
    config = training_config or SFTTrainingConfig(model_id=model_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    unique_rows, duplicate_count = dedupe_rows(rows)
    splits = split_rows(unique_rows, split_config)
    split_files = write_splits(output_dir, splits)
    report = build_dataset_report(dataset_dir / "sft_messages.jsonl", rows, unique_rows, splits)
    report.duplicate_rows = duplicate_count
    config_path = output_dir / "training_config.json"
    config_path.write_text(_json(config.model_dump()) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "agentic-rl-training-run.v1",
        "mode": mode,
        "created_at": now_iso(),
        "config_file": str(config_path),
        "split_files": split_files,
        "dataset_report": report.model_dump(),
        "default_model_reason": "0.5B Qwen is the conservative 8GB-GPU smoke-test target.",
    }
    (output_dir / "training_manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_training_report(config, report), encoding="utf-8")
    dependencies = check_training_dependencies()
    return PreparedTrainingRun(
        mode=mode,
        output_dir=str(output_dir),
        config=config,
        dataset_report=report,
        dependencies=dependencies,
        split_files=split_files,
        training_status="ready" if report.valid else "invalid_dataset",
    )


def prepare_dpo_training_run(
    dataset_dir: Path,
    output_dir: Path,
    *,
    model_id: str = DEFAULT_TINY_MODEL_ID,
    split_config: Optional[DatasetSplitConfig] = None,
    training_config: Optional[SFTTrainingConfig] = None,
) -> PreparedTrainingRun:
    rows = load_preference_pairs(dataset_dir)
    split_config = split_config or DatasetSplitConfig()
    config = training_config or SFTTrainingConfig(
        model_id=model_id,
        trainer_backend="trl-dpo",
        learning_rate=5e-6,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    unique_rows, duplicate_count = dedupe_preference_rows(rows)
    splits = split_rows(unique_rows, split_config)
    split_files = write_splits(output_dir, splits)
    report = build_preference_dataset_report(
        dataset_dir / "preference_pairs.jsonl", rows, unique_rows, splits
    )
    report.duplicate_rows = duplicate_count
    config_path = output_dir / "training_config.json"
    config_path.write_text(_json(config.model_dump()) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "agentic-rl-dpo-training-run.v1",
        "mode": "dpo",
        "created_at": now_iso(),
        "config_file": str(config_path),
        "split_files": split_files,
        "dataset_report": report.model_dump(),
        "default_model_reason": "0.5B Qwen is the conservative 8GB-GPU DPO smoke-test target.",
    }
    (output_dir / "training_manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_training_report(config, report), encoding="utf-8")
    dependencies = check_training_dependencies()
    return PreparedTrainingRun(
        mode="dpo",
        output_dir=str(output_dir),
        config=config,
        dataset_report=report,
        dependencies=dependencies,
        split_files=split_files,
        training_status="ready" if report.valid else "invalid_dataset",
    )


def prepare_grpo_training_run(
    dataset_dir: Path,
    output_dir: Path,
    *,
    model_id: str = DEFAULT_TINY_MODEL_ID,
    split_config: Optional[DatasetSplitConfig] = None,
    training_config: Optional[SFTTrainingConfig] = None,
) -> PreparedTrainingRun:
    rows = load_grpo_rollouts(dataset_dir)
    split_config = split_config or DatasetSplitConfig()
    config = training_config or SFTTrainingConfig(
        model_id=model_id,
        trainer_backend="trl-grpo",
        learning_rate=1e-6,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    unique_rows, duplicate_count = dedupe_grpo_rows(rows)
    splits = split_rows(unique_rows, split_config)
    split_files = write_splits(output_dir, splits)
    report = build_grpo_dataset_report(
        dataset_dir / "grpo_rollouts.jsonl", rows, unique_rows, splits
    )
    report.duplicate_rows = duplicate_count
    config_path = output_dir / "training_config.json"
    config_path.write_text(_json(config.model_dump()) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "agentic-rl-grpo-training-run.v1",
        "mode": "grpo",
        "created_at": now_iso(),
        "config_file": str(config_path),
        "split_files": split_files,
        "dataset_report": report.model_dump(),
        "default_model_reason": "0.5B Qwen is the conservative 8GB-GPU GRPO smoke-test target.",
        "training_boundary": (
            "TRL GRPOTrainer generates fresh completions; stored rollouts provide reward "
            "references and regression context rather than direct supervised targets."
        ),
    }
    (output_dir / "training_manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_training_report(config, report), encoding="utf-8")
    dependencies = check_training_dependencies()
    return PreparedTrainingRun(
        mode="grpo",
        output_dir=str(output_dir),
        config=config,
        dataset_report=report,
        dependencies=dependencies,
        split_files=split_files,
        training_status="ready" if report.valid else "invalid_dataset",
    )


def load_sft_messages(dataset_dir: Path) -> List[Dict[str, Any]]:
    path = dataset_dir / "sft_messages.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Missing SFT dataset: {path}")
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_preference_pairs(dataset_dir: Path) -> List[Dict[str, Any]]:
    path = dataset_dir / "preference_pairs.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Missing DPO preference dataset: {path}")
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_grpo_rollouts(dataset_dir: Path) -> List[Dict[str, Any]]:
    path = dataset_dir / "grpo_rollouts.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Missing GRPO rollout dataset: {path}")
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def dedupe_rows(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    duplicate_count = 0
    for row in rows:
        digest = hashlib.sha256(_json(row.get("messages", [])).encode("utf-8")).hexdigest()
        if digest in seen:
            duplicate_count += 1
            continue
        seen.add(digest)
        unique.append(row)
    return unique, duplicate_count


def dedupe_preference_rows(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    duplicate_count = 0
    for row in rows:
        digest = hashlib.sha256(
            _json([row.get("prompt", ""), row.get("chosen", ""), row.get("rejected", "")]).encode(
                "utf-8"
            )
        ).hexdigest()
        if digest in seen:
            duplicate_count += 1
            continue
        seen.add(digest)
        unique.append(row)
    return unique, duplicate_count


def dedupe_grpo_rows(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    duplicate_count = 0
    for row in rows:
        rollout_outputs = [
            rollout.get("output", "")
            for rollout in row.get("rollouts", [])
            if isinstance(rollout, dict)
        ]
        digest = hashlib.sha256(
            _json([row.get("prompt", ""), row.get("task_type", ""), rollout_outputs]).encode(
                "utf-8"
            )
        ).hexdigest()
        if digest in seen:
            duplicate_count += 1
            continue
        seen.add(digest)
        unique.append(row)
    return unique, duplicate_count


def split_rows(
    rows: List[Dict[str, Any]],
    split_config: DatasetSplitConfig,
) -> Dict[str, List[Dict[str, Any]]]:
    source_grouped = _split_rows_by_source_records(rows, split_config)
    if source_grouped is not None:
        return source_grouped

    ordered = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{split_config.seed}:{_json(_split_fingerprint(row))}".encode("utf-8")
        ).hexdigest(),
    )
    total = len(ordered)
    if total < 3:
        return {"train": ordered, "valid": [], "test": []}
    valid_count = max(split_config.min_valid, math.floor(total * split_config.valid_ratio))
    test_count = max(split_config.min_test, math.floor(total * split_config.test_ratio))
    if valid_count + test_count >= total:
        valid_count = 1
        test_count = 1
    train_count = total - valid_count - test_count
    return {
        "train": ordered[:train_count],
        "valid": ordered[train_count : train_count + valid_count],
        "test": ordered[train_count + valid_count :],
    }


def _split_rows_by_source_records(
    rows: List[Dict[str, Any]],
    split_config: DatasetSplitConfig,
) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """Keep rows from the same public source out of different data splits.

    This only activates when every row declares provenance.  Legacy fixture
    data without ``source_records`` keeps the deterministic row-level split.
    """

    if not rows or any(not _source_group_key(row) for row in rows):
        return None

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_source_group_key(row), []).append(row)
    if len(grouped) < 3:
        return None

    ordered_keys = sorted(
        grouped,
        key=lambda key: hashlib.sha256(
            f"{split_config.seed}:source:{key}".encode("utf-8")
        ).hexdigest(),
    )
    total_groups = len(ordered_keys)
    valid_groups = max(split_config.min_valid, math.floor(total_groups * split_config.valid_ratio))
    test_groups = max(split_config.min_test, math.floor(total_groups * split_config.test_ratio))
    if valid_groups + test_groups >= total_groups:
        valid_groups = 1
        test_groups = 1
    train_groups = total_groups - valid_groups - test_groups
    if train_groups < 1:
        return None

    train_keys = ordered_keys[:train_groups]
    valid_keys = ordered_keys[train_groups : train_groups + valid_groups]
    test_keys = ordered_keys[train_groups + valid_groups :]
    return {
        "train": [row for key in train_keys for row in grouped[key]],
        "valid": [row for key in valid_keys for row in grouped[key]],
        "test": [row for key in test_keys for row in grouped[key]],
    }


def _source_group_key(row: Dict[str, Any]) -> str:
    source_records = row.get("source_records", [])
    if not isinstance(source_records, list):
        return ""
    values = sorted({str(item).strip() for item in source_records if str(item).strip()})
    return "|".join(values)


def _split_fingerprint(row: Dict[str, Any]) -> List[Any]:
    rollouts = row.get("rollouts", [])
    rollout_outputs = []
    if isinstance(rollouts, list):
        rollout_outputs = [
            rollout.get("output", "") for rollout in rollouts if isinstance(rollout, dict)
        ]
    return [
        row.get("id", ""),
        row.get("task_type", ""),
        row.get("messages", []),
        row.get("prompt", ""),
        row.get("chosen", ""),
        row.get("rejected", ""),
        rollout_outputs,
    ]


def write_splits(output_dir: Path, splits: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
    split_files: Dict[str, str] = {}
    for name, rows in splits.items():
        path = output_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(_json(row) + "\n")
        split_files[name] = str(path)
    return split_files


def build_dataset_report(
    source_file: Path,
    original_rows: List[Dict[str, Any]],
    unique_rows: List[Dict[str, Any]],
    splits: Dict[str, List[Dict[str, Any]]],
) -> TrainingDatasetReport:
    issues: List[TrainingDatasetIssue] = []
    privacy_hits: List[str] = []
    token_counts: List[int] = []
    rewards: List[float] = []
    task_type_counts: Dict[str, int] = {}
    for row in unique_rows:
        row_id = str(row.get("id", ""))
        messages = row.get("messages", [])
        if not isinstance(messages, list) or len(messages) < 2:
            issues.append(
                _issue("error", "invalid_messages", "SFT row must contain messages.", row_id)
            )
            continue
        prompt = _message_content(messages, "user")
        answer = _message_content(messages, "assistant")
        if not prompt or not answer:
            issues.append(
                _issue("error", "empty_prompt_or_answer", "Prompt and answer are required.", row_id)
            )
        combined = f"{prompt}\n{answer}"
        token_counts.append(estimate_tokens(combined))
        privacy_hits.extend(scan_privacy(combined, row_id=row_id))
        reward = row.get("reward")
        if isinstance(reward, (int, float)):
            rewards.append(float(reward))
        task_type = str(row.get("task_type", "unknown") or "unknown")
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
    if privacy_hits:
        issues.append(
            _issue(
                "error",
                "privacy_scan_hit",
                "Dataset contains unmasked email, phone, API key, or connection string pattern.",
            )
        )
    if len(unique_rows) < 50:
        issues.append(
            _issue(
                "warning",
                "small_dataset",
                "Fewer than 50 unique SFT rows; use only for smoke tests.",
            )
        )
    return TrainingDatasetReport(
        valid=not any(issue.level == "error" for issue in issues),
        source_file=str(source_file),
        total_rows=len(original_rows),
        usable_rows=len(unique_rows),
        split_counts={name: len(rows) for name, rows in splits.items()},
        approx_token_stats=_numeric_stats(token_counts),
        reward_stats=_numeric_stats(rewards),
        task_type_counts=task_type_counts,
        privacy_scan_hits=privacy_hits,
        issues=issues,
    )


def build_preference_dataset_report(
    source_file: Path,
    original_rows: List[Dict[str, Any]],
    unique_rows: List[Dict[str, Any]],
    splits: Dict[str, List[Dict[str, Any]]],
) -> TrainingDatasetReport:
    issues: List[TrainingDatasetIssue] = []
    privacy_hits: List[str] = []
    token_counts: List[int] = []
    margins: List[float] = []
    task_type_counts: Dict[str, int] = {}
    for row in unique_rows:
        row_id = str(row.get("id", ""))
        prompt = str(row.get("prompt", "") or "")
        chosen = str(row.get("chosen", "") or "")
        rejected = str(row.get("rejected", "") or "")
        if not prompt or not chosen or not rejected:
            issues.append(
                _issue(
                    "error",
                    "invalid_preference_pair",
                    "DPO row must contain prompt, chosen, and rejected.",
                    row_id,
                )
            )
        if chosen == rejected:
            issues.append(
                _issue(
                    "error",
                    "identical_chosen_rejected",
                    "Chosen and rejected responses must differ.",
                    row_id,
                )
            )
        token_counts.append(estimate_tokens(f"{prompt}\n{chosen}\n{rejected}"))
        privacy_hits.extend(scan_privacy(f"{prompt}\n{chosen}\n{rejected}", row_id=row_id))
        chosen_reward = row.get("chosen_reward")
        rejected_reward = row.get("rejected_reward")
        if isinstance(chosen_reward, (int, float)) and isinstance(rejected_reward, (int, float)):
            margin = float(chosen_reward) - float(rejected_reward)
            margins.append(margin)
            if margin <= 0:
                issues.append(
                    _issue(
                        "warning",
                        "non_positive_reward_margin",
                        "Chosen reward is not greater than rejected reward.",
                        row_id,
                    )
                )
        task_type = str(row.get("task_type", "unknown") or "unknown")
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
    if privacy_hits:
        issues.append(
            _issue(
                "error",
                "privacy_scan_hit",
                "Preference dataset contains unmasked email, phone, API key, or connection string pattern.",
            )
        )
    if len(unique_rows) < 50:
        issues.append(
            _issue(
                "warning",
                "small_dataset",
                "Fewer than 50 unique DPO rows; use only for smoke tests.",
            )
        )
    return TrainingDatasetReport(
        valid=not any(issue.level == "error" for issue in issues),
        source_file=str(source_file),
        total_rows=len(original_rows),
        usable_rows=len(unique_rows),
        split_counts={name: len(rows) for name, rows in splits.items()},
        approx_token_stats=_numeric_stats(token_counts),
        reward_stats=_numeric_stats(margins),
        task_type_counts=task_type_counts,
        privacy_scan_hits=privacy_hits,
        issues=issues,
    )


def build_grpo_dataset_report(
    source_file: Path,
    original_rows: List[Dict[str, Any]],
    unique_rows: List[Dict[str, Any]],
    splits: Dict[str, List[Dict[str, Any]]],
) -> TrainingDatasetReport:
    issues: List[TrainingDatasetIssue] = []
    privacy_hits: List[str] = []
    token_counts: List[int] = []
    reward_spreads: List[float] = []
    task_type_counts: Dict[str, int] = {}
    for row in unique_rows:
        row_id = str(row.get("id", row.get("prompt", "")) or "")
        prompt = str(row.get("prompt", "") or "")
        rollouts = row.get("rollouts", [])
        if not prompt or not isinstance(rollouts, list) or len(rollouts) < 2:
            issues.append(
                _issue(
                    "error",
                    "invalid_grpo_rollout_group",
                    "GRPO row must contain a prompt and at least two rollout candidates.",
                    row_id,
                )
            )
            continue
        outputs = []
        rewards = []
        for rollout in rollouts:
            if not isinstance(rollout, dict):
                issues.append(
                    _issue(
                        "error",
                        "invalid_rollout",
                        "Each rollout must be an object with output and reward.",
                        row_id,
                    )
                )
                continue
            output = str(rollout.get("output", "") or "")
            outputs.append(output)
            reward = _rollout_reward_total(rollout)
            rewards.append(reward)
            if not output:
                issues.append(
                    _issue("error", "empty_rollout_output", "Rollout output is required.", row_id)
                )
        if rewards:
            reward_spread = max(rewards) - min(rewards)
            reward_spreads.append(reward_spread)
            if reward_spread <= 0:
                issues.append(
                    _issue(
                        "warning",
                        "zero_reward_spread",
                        "GRPO group has no reward spread; it is weak for group-relative training.",
                        row_id,
                    )
                )
            if max(rewards) <= 0:
                issues.append(
                    _issue(
                        "warning",
                        "no_positive_rollout",
                        "GRPO group has no positive reward rollout.",
                        row_id,
                    )
                )
        combined = "\n".join([prompt, *outputs])
        token_counts.append(estimate_tokens(combined))
        privacy_hits.extend(scan_privacy(combined, row_id=row_id))
        task_type = str(row.get("task_type", "unknown") or "unknown")
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
    if privacy_hits:
        issues.append(
            _issue(
                "error",
                "privacy_scan_hit",
                "GRPO rollout dataset contains unmasked email, phone, API key, or connection string pattern.",
            )
        )
    if len(unique_rows) < 50:
        issues.append(
            _issue(
                "warning",
                "small_dataset",
                "Fewer than 50 unique GRPO groups; use only for smoke tests.",
            )
        )
    return TrainingDatasetReport(
        valid=not any(issue.level == "error" for issue in issues),
        source_file=str(source_file),
        total_rows=len(original_rows),
        usable_rows=len(unique_rows),
        split_counts={name: len(rows) for name, rows in splits.items()},
        approx_token_stats=_numeric_stats(token_counts),
        reward_stats=_numeric_stats(reward_spreads),
        task_type_counts=task_type_counts,
        privacy_scan_hits=privacy_hits,
        issues=issues,
    )


def check_training_dependencies() -> TrainingDependencyReport:
    grpo_trainer = False
    if importlib.util.find_spec("trl") is not None:
        try:
            from trl import GRPOConfig, GRPOTrainer  # noqa: F401

            grpo_trainer = True
        except Exception:
            grpo_trainer = False
    return TrainingDependencyReport(
        torch=importlib.util.find_spec("torch") is not None,
        transformers=importlib.util.find_spec("transformers") is not None,
        peft=importlib.util.find_spec("peft") is not None,
        accelerate=importlib.util.find_spec("accelerate") is not None,
        datasets=importlib.util.find_spec("datasets") is not None,
        trl=importlib.util.find_spec("trl") is not None,
        grpo_trainer=grpo_trainer,
    )


def estimate_tokens(text: str) -> int:
    ascii_count = len(re.findall(r"[A-Za-z0-9_]+", text or ""))
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text or ""))
    other_count = max(0, len(text or "") - ascii_count - cjk_count)
    return max(1, math.ceil(ascii_count / 4 + cjk_count * 0.8 + other_count / 6))


def scan_privacy(text: str, *, row_id: str = "") -> List[str]:
    patterns = {
        "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
        "cn_phone": r"(?<!\d)(?:\+?86[-\s]?)?1\d{10}(?!\d)",
        "api_key": r"sk-[A-Za-z0-9_-]{16,}",
        "postgres_url": r"postgres(?:ql)?://[^\s]+",
    }
    hits = []
    for name, pattern in patterns.items():
        if re.search(pattern, text or ""):
            hits.append(f"{row_id}:{name}" if row_id else name)
    return hits


def render_training_report(config: SFTTrainingConfig, report: TrainingDatasetReport) -> str:
    issues = "\n".join(
        f"- {issue.level}: {issue.code} - {issue.message}" for issue in report.issues
    )
    if not issues:
        issues = "- none"
    return (
        "# Agentic RL Training Dry Run\n\n"
        f"- model: `{config.model_id}`\n"
        f"- method: `{config.method}`\n"
        f"- trainer_backend: `{config.trainer_backend}`\n"
        f"- max_seq_length: `{config.max_seq_length}`\n"
        f"- max_steps: `{config.max_steps}`\n"
        f"- warmup_ratio: `{config.warmup_ratio}`\n"
        f"- LoRA: r={config.lora.r}, alpha={config.lora.lora_alpha}, "
        f"dropout={config.lora.lora_dropout}\n"
        f"- rows: total={report.total_rows}, usable={report.usable_rows}, "
        f"duplicates={report.duplicate_rows}\n"
        f"- splits: {report.split_counts}\n"
        f"- reward_stats: {report.reward_stats}\n"
        f"- approx_token_stats: {report.approx_token_stats}\n"
        f"- valid: `{report.valid}`\n\n"
        "## Issues\n\n"
        f"{issues}\n"
    )


def run_local_sft_training(
    prepared: PreparedTrainingRun,
    *,
    allow_cpu: bool = False,
    evaluate_after_training: bool = True,
    max_eval_samples: int = 3,
) -> PreparedTrainingRun:
    """Run a minimal TRL/HuggingFace LoRA SFT if optional deps are installed."""

    if not prepared.dataset_report.valid:
        return prepared.model_copy(update={"training_status": "invalid_dataset"})
    backend = _select_trainer_backend(prepared)
    if backend == "trl-sft" and not prepared.dependencies.ready_for_trl_sft:
        return prepared.model_copy(update={"training_status": "missing_trl_dependencies"})
    if backend == "hf-trainer" and not prepared.dependencies.ready_for_sft:
        return prepared.model_copy(update={"training_status": "missing_dependencies"})

    import torch

    if not torch.cuda.is_available() and not allow_cpu:
        return prepared.model_copy(update={"training_status": "cuda_unavailable"})

    if backend == "trl-sft":
        return _run_trl_sft_training(
            prepared,
            evaluate_after_training=evaluate_after_training,
            max_eval_samples=max_eval_samples,
        )
    return _run_hf_sft_training(
        prepared,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )


def run_local_dpo_training(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path] = None,
    allow_cpu: bool = False,
    evaluate_after_training: bool = True,
    max_eval_samples: int = 3,
) -> PreparedTrainingRun:
    """Run a minimal TRL DPOTrainer LoRA preference optimization."""

    if not prepared.dataset_report.valid:
        return prepared.model_copy(update={"training_status": "invalid_dataset"})
    if not prepared.dependencies.ready_for_trl_dpo:
        return prepared.model_copy(update={"training_status": "missing_dpo_dependencies"})

    import torch

    if not torch.cuda.is_available() and not allow_cpu:
        return prepared.model_copy(update={"training_status": "cuda_unavailable"})

    return _run_trl_dpo_training(
        prepared,
        sft_adapter_dir=sft_adapter_dir,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )


def run_local_grpo_training(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path] = None,
    dpo_adapter_dir: Optional[Path] = None,
    allow_cpu: bool = False,
    evaluate_after_training: bool = True,
    max_eval_samples: int = 3,
) -> PreparedTrainingRun:
    """Run a minimal TRL GRPOTrainer LoRA smoke optimization."""

    if not prepared.dataset_report.valid:
        return prepared.model_copy(update={"training_status": "invalid_dataset"})
    if not prepared.dependencies.ready_for_trl_grpo:
        return prepared.model_copy(update={"training_status": "missing_grpo_dependencies"})

    import torch

    if not torch.cuda.is_available() and not allow_cpu:
        return prepared.model_copy(update={"training_status": "cuda_unavailable"})

    return _run_trl_grpo_training(
        prepared,
        sft_adapter_dir=sft_adapter_dir,
        dpo_adapter_dir=dpo_adapter_dir,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )


def _select_trainer_backend(prepared: PreparedTrainingRun) -> str:
    requested = prepared.config.trainer_backend
    if requested == "trl-sft":
        return "trl-sft"
    if requested == "hf-trainer":
        return "hf-trainer"
    if prepared.dependencies.ready_for_trl_sft:
        return "trl-sft"
    return "hf-trainer"


def _prepare_lora_model_for_training(model: Any, *, gradient_checkpointing: bool) -> Any:
    """Make LoRA models trainable when checkpointed forward passes are enabled."""

    if not gradient_checkpointing:
        return model

    enable_checkpointing = getattr(model, "gradient_checkpointing_enable", None)
    if callable(enable_checkpointing):
        enable_checkpointing()

    enable_input_grads = getattr(model, "enable_input_require_grads", None)
    if callable(enable_input_grads):
        enable_input_grads()
        return model

    get_embeddings = getattr(model, "get_input_embeddings", None)
    if not callable(get_embeddings):
        return model
    embeddings = get_embeddings()
    if embeddings is None:
        return model

    def require_grad(_module: Any, _inputs: Any, output: Any) -> None:
        if hasattr(output, "requires_grad_"):
            output.requires_grad_(True)

    embeddings.register_forward_hook(require_grad)
    return model


def _run_hf_sft_training(
    prepared: PreparedTrainingRun,
    *,
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> PreparedTrainingRun:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    output_dir = Path(prepared.output_dir)
    train_rows = _read_jsonl(Path(prepared.split_files["train"]))
    valid_rows = _read_jsonl(Path(prepared.split_files["valid"]))
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        prepared.config.model_id,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=prepared.config.lora.r,
        lora_alpha=prepared.config.lora.lora_alpha,
        lora_dropout=prepared.config.lora.lora_dropout,
        target_modules=prepared.config.lora.target_modules,
        bias="none",
    )
    model = get_peft_model(model, lora)
    model = _prepare_lora_model_for_training(
        model,
        gradient_checkpointing=prepared.config.gradient_checkpointing,
    )
    training_args = TrainingArguments(
        output_dir=str(output_dir / "trainer"),
        overwrite_output_dir=True,
        num_train_epochs=prepared.config.num_train_epochs,
        max_steps=prepared.config.max_steps,
        per_device_train_batch_size=prepared.config.per_device_train_batch_size,
        gradient_accumulation_steps=prepared.config.gradient_accumulation_steps,
        learning_rate=prepared.config.learning_rate,
        warmup_ratio=prepared.config.warmup_ratio,
        fp16=bool(prepared.config.fp16_if_cuda and torch.cuda.is_available()),
        gradient_checkpointing=prepared.config.gradient_checkpointing,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=1,
        report_to=[],
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=_SFTDataset(train_rows, tokenizer, prepared.config.max_seq_length, torch),
        eval_dataset=_SFTDataset(valid_rows, tokenizer, prepared.config.max_seq_length, torch)
        if valid_rows
        else None,
    )
    trainer.train()
    adapter_dir = output_dir / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    eval_report = _safe_evaluate_base_vs_adapter(
        prepared,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )
    result = prepared.model_copy(
        update={
            "training_started": True,
            "training_status": "completed",
            "trainer_backend_used": "hf-trainer",
            "model_eval_report": eval_report,
        }
    )
    write_training_result(result)
    return result


def _run_trl_sft_training(
    prepared: PreparedTrainingRun,
    *,
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> PreparedTrainingRun:
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    output_dir = Path(prepared.output_dir)
    train_rows = _read_jsonl(Path(prepared.split_files["train"]))
    valid_rows = _read_jsonl(Path(prepared.split_files["valid"]))
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        prepared.config.model_id,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    lora = LoraConfig(
        task_type="CAUSAL_LM",
        r=prepared.config.lora.r,
        lora_alpha=prepared.config.lora.lora_alpha,
        lora_dropout=prepared.config.lora.lora_dropout,
        target_modules=prepared.config.lora.target_modules,
        bias="none",
    )
    model = _prepare_lora_model_for_training(
        model,
        gradient_checkpointing=prepared.config.gradient_checkpointing,
    )
    train_dataset = Dataset.from_list([{"text": format_sft_row(row)} for row in train_rows])
    eval_dataset = (
        Dataset.from_list([{"text": format_sft_row(row)} for row in valid_rows])
        if valid_rows
        else None
    )
    config_kwargs = {
        "output_dir": str(output_dir / "trainer"),
        "overwrite_output_dir": True,
        "num_train_epochs": prepared.config.num_train_epochs,
        "max_steps": prepared.config.max_steps,
        "per_device_train_batch_size": prepared.config.per_device_train_batch_size,
        "gradient_accumulation_steps": prepared.config.gradient_accumulation_steps,
        "learning_rate": prepared.config.learning_rate,
        "warmup_ratio": prepared.config.warmup_ratio,
        "fp16": bool(prepared.config.fp16_if_cuda and torch.cuda.is_available()),
        "gradient_checkpointing": prepared.config.gradient_checkpointing,
        "logging_steps": 1,
        "save_strategy": "epoch",
        "save_total_limit": 1,
        "report_to": [],
        "dataset_text_field": "text",
        "max_length": prepared.config.max_seq_length,
    }
    training_args = _build_sft_config(SFTConfig, config_kwargs)
    trainer = _build_sft_trainer(
        SFTTrainer,
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=lora,
        tokenizer=tokenizer,
    )
    trainer.train()
    adapter_dir = output_dir / "adapter"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    eval_report = _safe_evaluate_base_vs_adapter(
        prepared,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )
    result = prepared.model_copy(
        update={
            "training_started": True,
            "training_status": "completed",
            "trainer_backend_used": "trl-sft",
            "model_eval_report": eval_report,
        }
    )
    write_training_result(result)
    return result


def _run_trl_dpo_training(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path],
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> PreparedTrainingRun:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import DPOConfig, DPOTrainer

    output_dir = Path(prepared.output_dir)
    train_rows = _read_jsonl(Path(prepared.split_files["train"]))
    valid_rows = _read_jsonl(Path(prepared.split_files["valid"]))
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        prepared.config.model_id,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    lora = LoraConfig(
        task_type="CAUSAL_LM",
        r=prepared.config.lora.r,
        lora_alpha=prepared.config.lora.lora_alpha,
        lora_dropout=prepared.config.lora.lora_dropout,
        target_modules=prepared.config.lora.target_modules,
        bias="none",
    )
    initial_adapter = sft_adapter_dir if sft_adapter_dir and sft_adapter_dir.exists() else None
    peft_config = lora
    if initial_adapter:
        model = PeftModel.from_pretrained(model, initial_adapter, is_trainable=True)
        peft_config = None
    model = _prepare_lora_model_for_training(
        model,
        gradient_checkpointing=prepared.config.gradient_checkpointing,
    )
    train_dataset = Dataset.from_list([format_dpo_row(row) for row in train_rows])
    eval_dataset = (
        Dataset.from_list([format_dpo_row(row) for row in valid_rows]) if valid_rows else None
    )
    config_kwargs = {
        "output_dir": str(output_dir / "trainer"),
        "overwrite_output_dir": True,
        "num_train_epochs": prepared.config.num_train_epochs,
        "max_steps": prepared.config.max_steps,
        "per_device_train_batch_size": prepared.config.per_device_train_batch_size,
        "per_device_eval_batch_size": prepared.config.per_device_train_batch_size,
        "gradient_accumulation_steps": prepared.config.gradient_accumulation_steps,
        "learning_rate": prepared.config.learning_rate,
        "warmup_ratio": prepared.config.warmup_ratio,
        "fp16": bool(prepared.config.fp16_if_cuda and torch.cuda.is_available()),
        "gradient_checkpointing": prepared.config.gradient_checkpointing,
        "logging_steps": 1,
        "save_strategy": "epoch",
        "save_total_limit": 1,
        "report_to": [],
        "max_length": prepared.config.max_seq_length,
        "max_prompt_length": prepared.config.max_prompt_length,
        "beta": prepared.config.dpo_beta,
        "loss_type": prepared.config.dpo_loss_type,
        "remove_unused_columns": False,
    }
    training_args = _build_sft_config(DPOConfig, config_kwargs)
    trainer = _build_dpo_trainer(
        DPOTrainer,
        model=model,
        ref_model=None,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=peft_config,
        tokenizer=tokenizer,
    )
    trainer.train()
    adapter_dir = output_dir / "adapter"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    eval_report = _safe_evaluate_base_sft_dpo(
        prepared,
        sft_adapter_dir=sft_adapter_dir,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )
    eval_report["initial_policy_adapter"] = str(initial_adapter) if initial_adapter else ""
    result = prepared.model_copy(
        update={
            "training_started": True,
            "training_status": "completed",
            "trainer_backend_used": "trl-dpo",
            "model_eval_report": eval_report,
        }
    )
    write_training_result(result)
    return result


def _run_trl_grpo_training(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path],
    dpo_adapter_dir: Optional[Path],
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> PreparedTrainingRun:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    output_dir = Path(prepared.output_dir)
    train_rows = _read_jsonl(Path(prepared.split_files["train"]))
    valid_rows = _read_jsonl(Path(prepared.split_files["valid"]))
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        prepared.config.model_id,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    lora = LoraConfig(
        task_type="CAUSAL_LM",
        r=prepared.config.lora.r,
        lora_alpha=prepared.config.lora.lora_alpha,
        lora_dropout=prepared.config.lora.lora_dropout,
        target_modules=prepared.config.lora.target_modules,
        bias="none",
    )
    initial_adapter = None
    if dpo_adapter_dir and dpo_adapter_dir.exists():
        initial_adapter = dpo_adapter_dir
    elif sft_adapter_dir and sft_adapter_dir.exists():
        initial_adapter = sft_adapter_dir
    peft_config = lora
    if initial_adapter:
        model = PeftModel.from_pretrained(model, initial_adapter, is_trainable=True)
        peft_config = None
    model = _prepare_lora_model_for_training(
        model,
        gradient_checkpointing=prepared.config.gradient_checkpointing,
    )
    train_dataset = Dataset.from_list([format_grpo_row(row) for row in train_rows])
    eval_dataset = (
        Dataset.from_list([format_grpo_row(row) for row in valid_rows]) if valid_rows else None
    )
    config_kwargs = {
        "output_dir": str(output_dir / "trainer"),
        "overwrite_output_dir": True,
        "num_train_epochs": prepared.config.num_train_epochs,
        "max_steps": prepared.config.max_steps,
        "per_device_train_batch_size": prepared.config.per_device_train_batch_size,
        "per_device_eval_batch_size": prepared.config.per_device_train_batch_size,
        "gradient_accumulation_steps": prepared.config.gradient_accumulation_steps,
        "learning_rate": prepared.config.learning_rate,
        "warmup_ratio": prepared.config.warmup_ratio,
        "fp16": bool(prepared.config.fp16_if_cuda and torch.cuda.is_available()),
        "gradient_checkpointing": prepared.config.gradient_checkpointing,
        "logging_steps": 1,
        "save_strategy": "epoch",
        "save_total_limit": 1,
        "report_to": [],
        "remove_unused_columns": False,
        "max_prompt_length": prepared.config.max_prompt_length,
        "max_completion_length": prepared.config.max_completion_length,
        "num_generations": prepared.config.grpo_num_generations,
        "temperature": prepared.config.grpo_temperature,
        "beta": prepared.config.grpo_beta,
        "use_vllm": False,
    }
    training_args = _build_sft_config(GRPOConfig, config_kwargs)
    reward_func = _make_grpo_reward_func()
    trainer = _build_grpo_trainer(
        GRPOTrainer,
        model=model,
        reward_funcs=reward_func,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=peft_config,
        processing_class=tokenizer,
    )
    trainer.train()
    adapter_dir = output_dir / "adapter"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    eval_report = _safe_evaluate_base_sft_dpo_grpo(
        prepared,
        sft_adapter_dir=sft_adapter_dir,
        dpo_adapter_dir=dpo_adapter_dir,
        evaluate_after_training=evaluate_after_training,
        max_eval_samples=max_eval_samples,
    )
    eval_report["initial_policy_adapter"] = str(initial_adapter) if initial_adapter else ""
    result = prepared.model_copy(
        update={
            "training_started": True,
            "training_status": "completed",
            "trainer_backend_used": "trl-grpo",
            "model_eval_report": eval_report,
        }
    )
    write_training_result(result)
    return result


def _build_sft_config(config_type: Any, kwargs: Dict[str, Any]) -> Any:
    parameters = set(inspect.signature(config_type.__init__).parameters)
    adapted = dict(kwargs)
    if "max_length" not in parameters and "max_seq_length" in parameters:
        adapted["max_seq_length"] = adapted.pop("max_length")
    filtered = {key: value for key, value in adapted.items() if key in parameters}
    return config_type(**filtered)


def _build_sft_trainer(trainer_type: Any, **kwargs: Any) -> Any:
    parameters = set(inspect.signature(trainer_type.__init__).parameters)
    adapted = dict(kwargs)
    tokenizer = adapted.pop("tokenizer")
    if "processing_class" in parameters:
        adapted["processing_class"] = tokenizer
    elif "tokenizer" in parameters:
        adapted["tokenizer"] = tokenizer
    return trainer_type(**{key: value for key, value in adapted.items() if key in parameters})


def _build_dpo_trainer(trainer_type: Any, **kwargs: Any) -> Any:
    parameters = set(inspect.signature(trainer_type.__init__).parameters)
    adapted = dict(kwargs)
    tokenizer = adapted.pop("tokenizer")
    if "processing_class" in parameters:
        adapted["processing_class"] = tokenizer
    elif "tokenizer" in parameters:
        adapted["tokenizer"] = tokenizer
    return trainer_type(**{key: value for key, value in adapted.items() if key in parameters})


def _build_grpo_trainer(trainer_type: Any, **kwargs: Any) -> Any:
    parameters = set(inspect.signature(trainer_type.__init__).parameters)
    return trainer_type(**{key: value for key, value in kwargs.items() if key in parameters})


def evaluate_base_vs_adapter(
    prepared: PreparedTrainingRun,
    *,
    max_eval_samples: int = 3,
) -> Dict[str, Any]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output_dir = Path(prepared.output_dir)
    adapter_dir = output_dir / "adapter"
    test_rows = _read_jsonl(Path(prepared.split_files["test"]))[:max_eval_samples]
    if not adapter_dir.exists() or not test_rows:
        return {}
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_kwargs = {
        "device_map": "auto" if torch.cuda.is_available() else None,
        "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
        "trust_remote_code": True,
    }
    base_model = AutoModelForCausalLM.from_pretrained(prepared.config.model_id, **model_kwargs)
    base_outputs = [_generate_text(base_model, tokenizer, row, torch) for row in test_rows]
    del base_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    adapter_base = AutoModelForCausalLM.from_pretrained(prepared.config.model_id, **model_kwargs)
    adapter_model = PeftModel.from_pretrained(adapter_base, adapter_dir)
    adapter_outputs = [_generate_text(adapter_model, tokenizer, row, torch) for row in test_rows]
    del adapter_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    rows = []
    privacy_hits: List[str] = []
    for row, base_text, adapter_text in zip(test_rows, base_outputs, adapter_outputs):
        expected = _message_content(row.get("messages", []), "assistant")
        row_id = str(row.get("id", ""))
        privacy_hits.extend(scan_privacy(base_text, row_id=f"{row_id}:base"))
        privacy_hits.extend(scan_privacy(adapter_text, row_id=f"{row_id}:adapter"))
        masked_base = _safe_generated_text(base_text)
        masked_adapter = _safe_generated_text(adapter_text)
        rows.append(
            {
                "id": row_id,
                "task_type": row.get("task_type", ""),
                "base_score": _heuristic_generation_score(masked_base, expected),
                "adapter_score": _heuristic_generation_score(masked_adapter, expected),
                "base_output": masked_base,
                "adapter_output": masked_adapter,
                "expected_excerpt": expected[:240],
            }
        )
    base_avg = _avg([item["base_score"] for item in rows])
    adapter_avg = _avg([item["adapter_score"] for item in rows])
    report = {
        "schema_version": "agentic-rl-base-vs-adapter.v1",
        "model_id": prepared.config.model_id,
        "adapter_dir": str(adapter_dir),
        "sample_count": len(rows),
        "base_avg_score": base_avg,
        "adapter_avg_score": adapter_avg,
        "delta": round(adapter_avg - base_avg, 4),
        "privacy_scan_hits": privacy_hits,
        "rows": rows,
        "notes": [
            "Smoke report uses a lightweight lexical heuristic; it proves adapter load/generation, not final task quality."
        ],
    }
    (output_dir / "base_vs_adapter_eval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "base_vs_adapter_eval.md").write_text(
        render_base_vs_adapter_report(report), encoding="utf-8"
    )
    return report


def evaluate_base_sft_dpo(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path] = None,
    max_eval_samples: int = 3,
) -> Dict[str, Any]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output_dir = Path(prepared.output_dir)
    dpo_adapter_dir = output_dir / "adapter"
    test_rows = _read_jsonl(Path(prepared.split_files["test"]))[:max_eval_samples]
    if not dpo_adapter_dir.exists() or not test_rows:
        return {}
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_kwargs = {
        "device_map": "auto" if torch.cuda.is_available() else None,
        "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
        "trust_remote_code": True,
    }
    variant_outputs: Dict[str, List[str]] = {}
    base_model = AutoModelForCausalLM.from_pretrained(prepared.config.model_id, **model_kwargs)
    variant_outputs["base"] = [
        _generate_text(base_model, tokenizer, row, torch) for row in test_rows
    ]
    del base_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if sft_adapter_dir and sft_adapter_dir.exists():
        sft_base = AutoModelForCausalLM.from_pretrained(prepared.config.model_id, **model_kwargs)
        sft_model = PeftModel.from_pretrained(sft_base, sft_adapter_dir)
        variant_outputs["sft_adapter"] = [
            _generate_text(sft_model, tokenizer, row, torch) for row in test_rows
        ]
        del sft_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    dpo_base = AutoModelForCausalLM.from_pretrained(prepared.config.model_id, **model_kwargs)
    dpo_model = PeftModel.from_pretrained(dpo_base, dpo_adapter_dir)
    variant_outputs["dpo_adapter"] = [
        _generate_text(dpo_model, tokenizer, row, torch) for row in test_rows
    ]
    del dpo_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    privacy_hits: List[str] = []
    rows = []
    for index, row in enumerate(test_rows):
        expected = _row_expected(row)
        row_payload: Dict[str, Any] = {
            "id": row.get("id", ""),
            "task_type": row.get("task_type", ""),
            "chosen_reward": row.get("chosen_reward"),
            "rejected_reward": row.get("rejected_reward"),
            "expected_excerpt": expected[:240],
        }
        for variant, outputs in variant_outputs.items():
            generated = outputs[index]
            privacy_hits.extend(scan_privacy(generated, row_id=f"{row_payload['id']}:{variant}"))
            masked = _safe_generated_text(generated)
            row_payload[f"{variant}_score"] = _heuristic_generation_score(masked, expected)
            row_payload[f"{variant}_output"] = masked
        rows.append(row_payload)
    variant_scores = {}
    for variant in variant_outputs:
        variant_scores[variant] = _avg([row[f"{variant}_score"] for row in rows])
    report = {
        "schema_version": "agentic-rl-sft-dpo-eval.v1",
        "model_id": prepared.config.model_id,
        "sft_adapter_dir": str(sft_adapter_dir) if sft_adapter_dir else "",
        "dpo_adapter_dir": str(dpo_adapter_dir),
        "sample_count": len(rows),
        "variant_scores": variant_scores,
        "dpo_delta_vs_base": round(
            variant_scores.get("dpo_adapter", 0.0) - variant_scores.get("base", 0.0), 4
        ),
        "dpo_delta_vs_sft": round(
            variant_scores.get("dpo_adapter", 0.0) - variant_scores.get("sft_adapter", 0.0), 4
        )
        if "sft_adapter" in variant_scores
        else None,
        "privacy_scan_hits": privacy_hits,
        "rows": rows,
        "notes": [
            "Smoke report uses a lightweight lexical heuristic; it proves DPO adapter load/generation, not final task quality."
        ],
    }
    (output_dir / "sft_dpo_eval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "sft_dpo_eval.md").write_text(render_sft_dpo_report(report), encoding="utf-8")
    return report


def evaluate_base_sft_dpo_grpo(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path] = None,
    dpo_adapter_dir: Optional[Path] = None,
    max_eval_samples: int = 3,
) -> Dict[str, Any]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output_dir = Path(prepared.output_dir)
    grpo_adapter_dir = output_dir / "adapter"
    test_rows = _read_jsonl(Path(prepared.split_files["test"]))[:max_eval_samples]
    if not grpo_adapter_dir.exists() or not test_rows:
        return {}
    tokenizer = AutoTokenizer.from_pretrained(prepared.config.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_kwargs = {
        "device_map": "auto" if torch.cuda.is_available() else None,
        "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
        "trust_remote_code": True,
    }
    variant_adapters: List[Tuple[str, Optional[Path]]] = [
        ("base", None),
    ]
    if sft_adapter_dir and sft_adapter_dir.exists():
        variant_adapters.append(("sft_adapter", sft_adapter_dir))
    if dpo_adapter_dir and dpo_adapter_dir.exists():
        variant_adapters.append(("dpo_adapter", dpo_adapter_dir))
    variant_adapters.append(("grpo_adapter", grpo_adapter_dir))

    variant_outputs: Dict[str, List[str]] = {}
    for name, adapter_dir in variant_adapters:
        model = AutoModelForCausalLM.from_pretrained(prepared.config.model_id, **model_kwargs)
        if adapter_dir is not None:
            model = PeftModel.from_pretrained(model, adapter_dir)
        variant_outputs[name] = [_generate_text(model, tokenizer, row, torch) for row in test_rows]
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    privacy_hits: List[str] = []
    rows = []
    for index, row in enumerate(test_rows):
        expected = _row_expected(row)
        row_payload: Dict[str, Any] = {
            "id": row.get("id", hashlib.sha256(_row_prompt(row).encode("utf-8")).hexdigest()[:12]),
            "task_type": row.get("task_type", ""),
            "expected_reward": _rollout_reward_total(_best_rollout(row)),
            "expected_excerpt": expected[:240],
        }
        for variant, outputs in variant_outputs.items():
            generated = outputs[index]
            privacy_hits.extend(scan_privacy(generated, row_id=f"{row_payload['id']}:{variant}"))
            masked = _safe_generated_text(generated)
            row_payload[f"{variant}_score"] = _grpo_reference_reward(
                masked,
                expected,
                task_type=str(row.get("task_type", "")),
            )
            row_payload[f"{variant}_output"] = masked
        rows.append(row_payload)
    variant_scores = {}
    for variant in variant_outputs:
        variant_scores[variant] = _avg([row[f"{variant}_score"] for row in rows])
    report = {
        "schema_version": "agentic-rl-sft-dpo-grpo-eval.v1",
        "model_id": prepared.config.model_id,
        "sft_adapter_dir": str(sft_adapter_dir) if sft_adapter_dir else "",
        "dpo_adapter_dir": str(dpo_adapter_dir) if dpo_adapter_dir else "",
        "grpo_adapter_dir": str(grpo_adapter_dir),
        "sample_count": len(rows),
        "variant_scores": variant_scores,
        "grpo_delta_vs_base": round(
            variant_scores.get("grpo_adapter", 0.0) - variant_scores.get("base", 0.0), 4
        ),
        "grpo_delta_vs_sft": round(
            variant_scores.get("grpo_adapter", 0.0) - variant_scores.get("sft_adapter", 0.0), 4
        )
        if "sft_adapter" in variant_scores
        else None,
        "grpo_delta_vs_dpo": round(
            variant_scores.get("grpo_adapter", 0.0) - variant_scores.get("dpo_adapter", 0.0), 4
        )
        if "dpo_adapter" in variant_scores
        else None,
        "privacy_scan_hits": privacy_hits,
        "rows": rows,
        "notes": [
            "Smoke report uses a lightweight reference reward; it proves GRPO adapter load/generation, not final task quality."
        ],
    }
    (output_dir / "sft_dpo_grpo_eval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "sft_dpo_grpo_eval.md").write_text(
        render_sft_dpo_grpo_report(report), encoding="utf-8"
    )
    return report


def render_sft_dpo_report(report: Dict[str, Any]) -> str:
    lines = [
        "# SFT vs DPO Smoke Evaluation",
        "",
        f"- model: `{report.get('model_id', '')}`",
        f"- sft_adapter: `{report.get('sft_adapter_dir', '')}`",
        f"- dpo_adapter: `{report.get('dpo_adapter_dir', '')}`",
        f"- initial_policy_adapter: `{report.get('initial_policy_adapter', '')}`",
        f"- samples: `{report.get('sample_count', 0)}`",
        f"- variant_scores: `{report.get('variant_scores', {})}`",
        f"- dpo_delta_vs_base: `{report.get('dpo_delta_vs_base', 0)}`",
        f"- dpo_delta_vs_sft: `{report.get('dpo_delta_vs_sft', None)}`",
        f"- privacy_scan_hits: `{len(report.get('privacy_scan_hits', []))}`",
        "",
        "## Samples",
        "",
    ]
    for row in report.get("rows", []):
        lines.extend(
            [
                f"### {row.get('id', '')}",
                "",
                f"- task_type: `{row.get('task_type', '')}`",
                f"- base_score: `{row.get('base_score', 0)}`",
                f"- sft_score: `{row.get('sft_adapter_score', 'n/a')}`",
                f"- dpo_score: `{row.get('dpo_adapter_score', 0)}`",
                f"- expected_excerpt: {row.get('expected_excerpt', '')}",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    lines.extend(f"- {note}" for note in report.get("notes", []))
    return "\n".join(lines) + "\n"


def render_sft_dpo_grpo_report(report: Dict[str, Any]) -> str:
    lines = [
        "# Base vs SFT vs DPO vs GRPO Smoke Evaluation",
        "",
        f"- model: `{report.get('model_id', '')}`",
        f"- sft_adapter: `{report.get('sft_adapter_dir', '')}`",
        f"- dpo_adapter: `{report.get('dpo_adapter_dir', '')}`",
        f"- grpo_adapter: `{report.get('grpo_adapter_dir', '')}`",
        f"- initial_policy_adapter: `{report.get('initial_policy_adapter', '')}`",
        f"- samples: `{report.get('sample_count', 0)}`",
        f"- variant_scores: `{report.get('variant_scores', {})}`",
        f"- grpo_delta_vs_base: `{report.get('grpo_delta_vs_base', 0)}`",
        f"- grpo_delta_vs_sft: `{report.get('grpo_delta_vs_sft', None)}`",
        f"- grpo_delta_vs_dpo: `{report.get('grpo_delta_vs_dpo', None)}`",
        f"- privacy_scan_hits: `{len(report.get('privacy_scan_hits', []))}`",
        "",
        "## Samples",
        "",
    ]
    for row in report.get("rows", []):
        lines.extend(
            [
                f"### {row.get('id', '')}",
                "",
                f"- task_type: `{row.get('task_type', '')}`",
                f"- base_score: `{row.get('base_score', 0)}`",
                f"- sft_score: `{row.get('sft_adapter_score', 'n/a')}`",
                f"- dpo_score: `{row.get('dpo_adapter_score', 'n/a')}`",
                f"- grpo_score: `{row.get('grpo_adapter_score', 0)}`",
                f"- expected_excerpt: {row.get('expected_excerpt', '')}",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    lines.extend(f"- {note}" for note in report.get("notes", []))
    return "\n".join(lines) + "\n"


def _safe_evaluate_base_vs_adapter(
    prepared: PreparedTrainingRun,
    *,
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> Dict[str, Any]:
    if not evaluate_after_training:
        return {}
    try:
        return evaluate_base_vs_adapter(prepared, max_eval_samples=max_eval_samples)
    except Exception as exc:  # pragma: no cover - hardware/model failures are environment-specific
        return {
            "schema_version": "agentic-rl-base-vs-adapter.v1",
            "error": type(exc).__name__,
            "message": str(exc),
            "notes": ["Adapter training completed, but smoke generation evaluation failed."],
        }


def _safe_evaluate_base_sft_dpo(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path],
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> Dict[str, Any]:
    if not evaluate_after_training:
        return {}
    try:
        return evaluate_base_sft_dpo(
            prepared,
            sft_adapter_dir=sft_adapter_dir,
            max_eval_samples=max_eval_samples,
        )
    except Exception as exc:  # pragma: no cover - hardware/model failures are environment-specific
        return {
            "schema_version": "agentic-rl-sft-dpo-eval.v1",
            "error": type(exc).__name__,
            "message": str(exc),
            "notes": ["DPO adapter training completed, but smoke generation evaluation failed."],
        }


def _safe_evaluate_base_sft_dpo_grpo(
    prepared: PreparedTrainingRun,
    *,
    sft_adapter_dir: Optional[Path],
    dpo_adapter_dir: Optional[Path],
    evaluate_after_training: bool,
    max_eval_samples: int,
) -> Dict[str, Any]:
    if not evaluate_after_training:
        return {}
    try:
        return evaluate_base_sft_dpo_grpo(
            prepared,
            sft_adapter_dir=sft_adapter_dir,
            dpo_adapter_dir=dpo_adapter_dir,
            max_eval_samples=max_eval_samples,
        )
    except Exception as exc:  # pragma: no cover - hardware/model failures are environment-specific
        return {
            "schema_version": "agentic-rl-sft-dpo-grpo-eval.v1",
            "error": type(exc).__name__,
            "message": str(exc),
            "notes": ["GRPO adapter training completed, but smoke generation evaluation failed."],
        }


def write_training_result(prepared: PreparedTrainingRun) -> Dict[str, str]:
    output_dir = Path(prepared.output_dir)
    adapter_dir = output_dir / "adapter"
    trainer_dir = output_dir / "trainer"
    checkpoint_dirs = sorted(
        [path for path in trainer_dir.glob("checkpoint-*") if path.is_dir()],
        key=lambda path: path.name,
    )
    payload = {
        "schema_version": "agentic-rl-training-result.v1",
        "created_at": now_iso(),
        "mode": prepared.mode,
        "training_started": prepared.training_started,
        "training_status": prepared.training_status,
        "trainer_backend_used": prepared.trainer_backend_used,
        "model_id": prepared.config.model_id,
        "adapter_dir": str(adapter_dir) if adapter_dir.exists() else "",
        "checkpoint_dirs": [str(path) for path in checkpoint_dirs],
        "dataset_report": prepared.dataset_report.model_dump(),
        "dependencies": prepared.dependencies.model_dump(),
        "model_eval_report": prepared.model_eval_report,
    }
    json_path = output_dir / "training_result.json"
    md_path = output_dir / "training_result.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_training_result_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_training_result_markdown(payload: Dict[str, Any]) -> str:
    eval_report = payload.get("model_eval_report") or {}
    lines = [
        "# Agentic RL Training Result",
        "",
        f"- status: `{payload.get('training_status', '')}`",
        f"- backend: `{payload.get('trainer_backend_used', '')}`",
        f"- model: `{payload.get('model_id', '')}`",
        f"- adapter: `{payload.get('adapter_dir', '')}`",
        f"- checkpoints: `{len(payload.get('checkpoint_dirs', []))}`",
        f"- eval_samples: `{eval_report.get('sample_count', 0)}`",
        f"- base_avg_score: `{eval_report.get('base_avg_score', 0)}`",
        f"- adapter_avg_score: `{eval_report.get('adapter_avg_score', 0)}`",
        f"- eval_delta: `{eval_report.get('delta', 0)}`",
        f"- variant_scores: `{eval_report.get('variant_scores', {})}`",
        f"- dpo_delta_vs_base: `{eval_report.get('dpo_delta_vs_base', None)}`",
        f"- dpo_delta_vs_sft: `{eval_report.get('dpo_delta_vs_sft', None)}`",
        f"- grpo_delta_vs_base: `{eval_report.get('grpo_delta_vs_base', None)}`",
        f"- grpo_delta_vs_sft: `{eval_report.get('grpo_delta_vs_sft', None)}`",
        f"- grpo_delta_vs_dpo: `{eval_report.get('grpo_delta_vs_dpo', None)}`",
        f"- eval_privacy_scan_hits: `{len(eval_report.get('privacy_scan_hits', []))}`",
        "",
        "## Notes",
        "",
    ]
    notes = eval_report.get("notes") or []
    if not notes:
        notes = [
            "Smoke training proves the adapter can be produced and loaded; it is not a final quality claim."
        ]
    lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines) + "\n"


def render_base_vs_adapter_report(report: Dict[str, Any]) -> str:
    lines = [
        "# Base vs Adapter Smoke Evaluation",
        "",
        f"- model: `{report.get('model_id', '')}`",
        f"- adapter: `{report.get('adapter_dir', '')}`",
        f"- samples: `{report.get('sample_count', 0)}`",
        f"- base_avg_score: `{report.get('base_avg_score', 0)}`",
        f"- adapter_avg_score: `{report.get('adapter_avg_score', 0)}`",
        f"- delta: `{report.get('delta', 0)}`",
        f"- privacy_scan_hits: `{len(report.get('privacy_scan_hits', []))}`",
        "",
        "## Samples",
        "",
    ]
    for row in report.get("rows", []):
        lines.extend(
            [
                f"### {row.get('id', '')}",
                "",
                f"- task_type: `{row.get('task_type', '')}`",
                f"- base_score: `{row.get('base_score', 0)}`",
                f"- adapter_score: `{row.get('adapter_score', 0)}`",
                f"- expected_excerpt: {row.get('expected_excerpt', '')}",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    lines.extend(f"- {note}" for note in report.get("notes", []))
    return "\n".join(lines) + "\n"


def _generate_text(model: Any, tokenizer: Any, row: Dict[str, Any], torch_module: Any) -> str:
    prompt = _row_prompt(row)
    text = f"### Instruction:\n{prompt}\n\n### Response:\n"
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    device = next(model.parameters()).device
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch_module.no_grad():
        output = model.generate(
            **encoded,
            max_new_tokens=96,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    decoded = tokenizer.decode(output[0], skip_special_tokens=True)
    return decoded.split("### Response:", 1)[-1].strip()


def _heuristic_generation_score(generated: str, expected: str) -> float:
    required_terms = ["官方", "证据", "URL", "hash", "EvidenceAudit"]
    term_score = sum(term in generated for term in required_terms) / len(required_terms)
    expected_terms = {term for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", expected)}
    generated_terms = {term for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", generated)}
    overlap = len(expected_terms & generated_terms) / max(1, len(expected_terms))
    length_ok = 1.0 if 40 <= len(generated) <= 600 else 0.0
    return round(0.45 * term_score + 0.4 * overlap + 0.15 * length_ok, 4)


def _safe_generated_text(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text or "")
    text = re.sub(r"(?<!\d)(?:\+?86[-\s]?)?1\d{10}(?!\d)", "[PHONE]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{16,}", "[API_KEY]", text)
    text = re.sub(r"postgres(?:ql)?://[^\s]+", "[POSTGRES_URL]", text)
    return text


def format_dpo_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        "prompt": _row_prompt(row),
        "chosen": str(row.get("chosen", "") or ""),
        "rejected": str(row.get("rejected", "") or ""),
    }


def format_grpo_row(row: Dict[str, Any]) -> Dict[str, Any]:
    best = _best_rollout(row)
    return {
        "prompt": _row_prompt(row),
        "reference_output": str(best.get("output", "") or ""),
        "reference_reward": _rollout_reward_total(best),
        "task_type": str(row.get("task_type", "") or ""),
        "negative_terms": _negative_terms_for_rollouts(row.get("rollouts", [])),
    }


def _row_prompt(row: Dict[str, Any]) -> str:
    if "prompt" in row:
        return str(row.get("prompt", "") or "")
    return _message_content(row.get("messages", []), "user")


def _row_expected(row: Dict[str, Any]) -> str:
    if "chosen" in row:
        return str(row.get("chosen", "") or "")
    if "rollouts" in row:
        return str(_best_rollout(row).get("output", "") or "")
    return _message_content(row.get("messages", []), "assistant")


def _best_rollout(row: Dict[str, Any]) -> Dict[str, Any]:
    rollouts = [rollout for rollout in row.get("rollouts", []) if isinstance(rollout, dict)]
    if not rollouts:
        return {}
    return max(rollouts, key=_rollout_reward_total)


def _rollout_reward_total(rollout: Dict[str, Any]) -> float:
    reward = rollout.get("reward", {}) if isinstance(rollout, dict) else {}
    if isinstance(reward, dict) and isinstance(reward.get("total"), (int, float)):
        return float(reward["total"])
    if isinstance(rollout.get("reward"), (int, float)):
        return float(rollout["reward"])
    return 0.0


def _negative_terms_for_rollouts(rollouts: Any) -> List[str]:
    negative_terms = []
    for rollout in rollouts if isinstance(rollouts, list) else []:
        if not isinstance(rollout, dict) or _rollout_reward_total(rollout) >= 0:
            continue
        text = str(rollout.get("output", "") or "")
        for term in ["经验帖", "根据经验", "补齐结论", "更完整", "直接搜索"]:
            if term in text and term not in negative_terms:
                negative_terms.append(term)
    return negative_terms


def _make_grpo_reward_func():
    def reward_func(
        prompts: Optional[List[Any]] = None,
        completions: Optional[List[Any]] = None,
        reference_output: Optional[List[str]] = None,
        task_type: Optional[List[str]] = None,
        negative_terms: Optional[List[List[str]]] = None,
        **kwargs: Any,
    ) -> List[float]:
        prompt_values = prompts or kwargs.get("prompt") or []
        completion_values = completions or kwargs.get("completion") or []
        reference_values = reference_output or kwargs.get("reference_output") or []
        task_values = task_type or kwargs.get("task_type") or []
        negative_values = negative_terms or kwargs.get("negative_terms") or []
        rewards = []
        for index, completion in enumerate(completion_values):
            generated = _completion_to_text(completion)
            reference = str(_cyclic_get(reference_values, index, ""))
            task = str(_cyclic_get(task_values, index, ""))
            negatives = _cyclic_get(negative_values, index, [])
            reward = _grpo_reference_reward(generated, reference, task_type=task)
            if any(str(term) and str(term) in generated for term in negatives):
                reward -= 0.25
            if not reference and index < len(prompt_values):
                reward += 0.05 if str(prompt_values[index])[:20] in generated else 0.0
            rewards.append(round(max(-1.0, min(1.0, reward)), 4))
        return rewards

    return reward_func


def _cyclic_get(values: Any, index: int, default: Any) -> Any:
    if not isinstance(values, list) or not values:
        return default
    return values[index % len(values)]


def _completion_to_text(completion: Any) -> str:
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        parts = []
        for item in completion:
            if isinstance(item, dict):
                parts.append(str(item.get("content", "") or ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(completion, dict):
        return str(completion.get("content", "") or completion.get("text", "") or completion)
    return str(completion)


def _grpo_reference_reward(generated: str, reference: str, *, task_type: str = "") -> float:
    masked = _safe_generated_text(generated)
    score = _heuristic_generation_score(masked, reference)
    if "官方" in masked and ("URL" in masked or "hash" in masked):
        score += 0.15
    if "EvidenceAudit" in masked or "needs_review" in masked:
        score += 0.1
    if task_type == "rag_query_plan" and "检索" in masked:
        score += 0.05
    if task_type == "evidence_audit_fix" and ("修复" in masked or "claim" in masked):
        score += 0.05
    for bad_term in ["经验帖", "根据经验", "编造", "直接补齐", "看起来更完整"]:
        if bad_term in masked:
            score -= 0.2
    if scan_privacy(generated):
        score = -1.0
    return round(max(-1.0, min(1.0, score)), 4)


class _SFTDataset:
    def __init__(
        self, rows: List[Dict[str, Any]], tokenizer: Any, max_length: int, torch_module: Any
    ):
        self.rows = rows
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.torch = torch_module

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        text = format_sft_row(self.rows[index])
        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"][0]
        attention_mask = encoded["attention_mask"][0]
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": input_ids.clone(),
        }


def format_sft_row(row: Dict[str, Any]) -> str:
    messages = row.get("messages", [])
    prompt = _message_content(messages, "user")
    answer = _message_content(messages, "assistant")
    return f"### Instruction:\n{prompt}\n\n### Response:\n{answer}"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _message_content(messages: Any, role: str) -> str:
    if not isinstance(messages, list):
        return ""
    for message in messages:
        if isinstance(message, dict) and message.get("role") == role:
            return str(message.get("content", "") or "")
    return ""


def _numeric_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0}
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "avg": round(sum(values) / len(values), 4),
    }


def _avg(values: List[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _issue(level: Literal["error", "warning"], code: str, message: str, row_id: str = ""):
    return TrainingDatasetIssue(level=level, code=code, message=message, row_id=row_id)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
