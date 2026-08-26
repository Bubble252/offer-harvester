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
    schema_version: str = "agentic-rl-sft-training.v1"
    model_id: str = DEFAULT_TINY_MODEL_ID
    method: Literal["lora"] = "lora"
    trainer_backend: Literal["auto", "trl-sft", "hf-trainer"] = "auto"
    max_seq_length: int = 1024
    learning_rate: float = 2e-4
    num_train_epochs: float = 1.0
    max_steps: int = -1
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

    @property
    def ready_for_sft(self) -> bool:
        return self.torch and self.transformers and self.peft and self.accelerate

    @property
    def ready_for_trl_sft(self) -> bool:
        return self.ready_for_sft and self.datasets and self.trl


class PreparedTrainingRun(BaseModel):
    mode: Literal["dry-run", "sft"]
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


def load_sft_messages(dataset_dir: Path) -> List[Dict[str, Any]]:
    path = dataset_dir / "sft_messages.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Missing SFT dataset: {path}")
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


def split_rows(
    rows: List[Dict[str, Any]],
    split_config: DatasetSplitConfig,
) -> Dict[str, List[Dict[str, Any]]]:
    ordered = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{split_config.seed}:{row.get('id', '')}:{_json(row.get('messages', []))}".encode(
                "utf-8"
            )
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


def check_training_dependencies() -> TrainingDependencyReport:
    return TrainingDependencyReport(
        torch=importlib.util.find_spec("torch") is not None,
        transformers=importlib.util.find_spec("transformers") is not None,
        peft=importlib.util.find_spec("peft") is not None,
        accelerate=importlib.util.find_spec("accelerate") is not None,
        datasets=importlib.util.find_spec("datasets") is not None,
        trl=importlib.util.find_spec("trl") is not None,
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
        "# Agentic RL SFT Training Dry Run\n\n"
        f"- model: `{config.model_id}`\n"
        f"- method: `{config.method}`\n"
        f"- trainer_backend: `{config.trainer_backend}`\n"
        f"- max_seq_length: `{config.max_seq_length}`\n"
        f"- max_steps: `{config.max_steps}`\n"
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


def _select_trainer_backend(prepared: PreparedTrainingRun) -> str:
    requested = prepared.config.trainer_backend
    if requested == "trl-sft":
        return "trl-sft"
    if requested == "hf-trainer":
        return "hf-trainer"
    if prepared.dependencies.ready_for_trl_sft:
        return "trl-sft"
    return "hf-trainer"


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
    if prepared.config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=prepared.config.lora.r,
        lora_alpha=prepared.config.lora.lora_alpha,
        lora_dropout=prepared.config.lora.lora_dropout,
        target_modules=prepared.config.lora.target_modules,
        bias="none",
    )
    model = get_peft_model(model, lora)
    training_args = TrainingArguments(
        output_dir=str(output_dir / "trainer"),
        overwrite_output_dir=True,
        num_train_epochs=prepared.config.num_train_epochs,
        max_steps=prepared.config.max_steps,
        per_device_train_batch_size=prepared.config.per_device_train_batch_size,
        gradient_accumulation_steps=prepared.config.gradient_accumulation_steps,
        learning_rate=prepared.config.learning_rate,
        fp16=bool(prepared.config.fp16_if_cuda and torch.cuda.is_available()),
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
        "fp16": bool(prepared.config.fp16_if_cuda and torch.cuda.is_available()),
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
    prompt = _message_content(row.get("messages", []), "user")
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
