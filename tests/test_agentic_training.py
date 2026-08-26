from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agentic_training import (  # noqa: E402
    DEFAULT_DPO_OUTPUT_DIR_NAME,
    DEFAULT_GRPO_OUTPUT_DIR_NAME,
    DEFAULT_TINY_MODEL_ID,
    DatasetSplitConfig,
    SFTTrainingConfig,
    _prepare_lora_model_for_training,
    check_training_dependencies,
    estimate_tokens,
    prepare_dpo_training_run,
    prepare_grpo_training_run,
    prepare_training_run,
    render_base_vs_adapter_report,
    render_sft_dpo_grpo_report,
    render_sft_dpo_report,
    render_training_result_markdown,
    scan_privacy,
)


def test_prepare_training_run_splits_and_reports_default_qwen_0_5b(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    rows = [_sft_row(index) for index in range(10)]
    _write_jsonl(dataset_dir / "sft_messages.jsonl", rows)

    prepared = prepare_training_run(
        dataset_dir,
        tmp_path / "run",
        split_config=DatasetSplitConfig(train_ratio=0.8, valid_ratio=0.1, test_ratio=0.1),
    )

    assert prepared.config.model_id == DEFAULT_TINY_MODEL_ID
    assert prepared.dataset_report.valid is True
    assert prepared.dataset_report.split_counts == {"train": 8, "valid": 1, "test": 1}
    assert Path(prepared.split_files["train"]).exists()
    assert "Qwen/Qwen2.5-0.5B-Instruct" in (tmp_path / "run" / "report.md").read_text()


def test_training_run_dedupes_and_flags_privacy(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    row = _sft_row(1)
    private = _sft_row(2)
    fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz"
    private["messages"][0]["content"] = f"联系我 test@example.com，密钥 {fake_key}"
    _write_jsonl(dataset_dir / "sft_messages.jsonl", [row, row, private])

    prepared = prepare_training_run(dataset_dir, tmp_path / "run")

    assert prepared.dataset_report.duplicate_rows == 1
    assert prepared.dataset_report.valid is False
    assert any(issue.code == "privacy_scan_hit" for issue in prepared.dataset_report.issues)
    assert any("email" in hit for hit in prepared.dataset_report.privacy_scan_hits)


def test_prepare_dpo_training_run_splits_and_reports_preferences(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_jsonl(
        dataset_dir / "preference_pairs.jsonl", [_preference_row(index) for index in range(10)]
    )

    prepared = prepare_dpo_training_run(
        dataset_dir,
        tmp_path / DEFAULT_DPO_OUTPUT_DIR_NAME,
        split_config=DatasetSplitConfig(train_ratio=0.8, valid_ratio=0.1, test_ratio=0.1),
    )

    assert prepared.mode == "dpo"
    assert prepared.config.trainer_backend == "trl-dpo"
    assert prepared.dataset_report.valid is True
    assert prepared.dataset_report.split_counts == {"train": 8, "valid": 1, "test": 1}
    assert Path(prepared.split_files["train"]).exists()
    assert "qwen2_5_0_5b_dpo_lora" in prepared.output_dir


def test_dpo_training_run_flags_privacy(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    row = _preference_row(1)
    row["chosen"] = "联系 +8613520978645"
    _write_jsonl(dataset_dir / "preference_pairs.jsonl", [row])

    prepared = prepare_dpo_training_run(dataset_dir, tmp_path / "run")

    assert prepared.dataset_report.valid is False
    assert any(issue.code == "privacy_scan_hit" for issue in prepared.dataset_report.issues)


def test_prepare_grpo_training_run_splits_and_reports_rollouts(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_jsonl(dataset_dir / "grpo_rollouts.jsonl", [_grpo_row(index) for index in range(10)])

    prepared = prepare_grpo_training_run(
        dataset_dir,
        tmp_path / DEFAULT_GRPO_OUTPUT_DIR_NAME,
        split_config=DatasetSplitConfig(train_ratio=0.8, valid_ratio=0.1, test_ratio=0.1),
    )

    assert prepared.mode == "grpo"
    assert prepared.config.trainer_backend == "trl-grpo"
    assert prepared.dataset_report.valid is True
    assert prepared.dataset_report.split_counts == {"train": 8, "valid": 1, "test": 1}
    assert prepared.dataset_report.reward_stats["avg"] == 2.0
    assert Path(prepared.split_files["train"]).exists()
    assert "qwen2_5_0_5b_grpo_lora" in prepared.output_dir


def test_training_split_keeps_source_records_in_one_partition(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    rows = []
    for source_index in range(6):
        for variant in range(2):
            row = _grpo_row(source_index * 10 + variant)
            row["source_records"] = [f"pubrec_{source_index}"]
            rows.append(row)
    _write_jsonl(dataset_dir / "grpo_rollouts.jsonl", rows)

    prepared = prepare_grpo_training_run(dataset_dir, tmp_path / "run")
    source_splits = {}
    for split, path in prepared.split_files.items():
        for row in _read_jsonl(Path(path)):
            source_splits.setdefault(row["source_records"][0], set()).add(split)

    assert all(len(splits) == 1 for splits in source_splits.values())


def test_grpo_training_run_flags_privacy(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    row = _grpo_row(1)
    row["rollouts"][0]["output"] = "联系 +8613520978645"
    _write_jsonl(dataset_dir / "grpo_rollouts.jsonl", [row])

    prepared = prepare_grpo_training_run(dataset_dir, tmp_path / "run")

    assert prepared.dataset_report.valid is False
    assert any(issue.code == "privacy_scan_hit" for issue in prepared.dataset_report.issues)


def test_training_dependency_report_is_non_throwing():
    report = check_training_dependencies()

    assert isinstance(report.ready_for_sft, bool)
    assert isinstance(report.ready_for_trl_sft, bool)
    assert isinstance(report.ready_for_trl_dpo, bool)
    assert isinstance(report.ready_for_trl_grpo, bool)
    assert isinstance(report.grpo_trainer, bool)
    assert isinstance(report.trl, bool)


def test_prepare_lora_model_enables_input_grads_for_checkpointing():
    class _Embeddings:
        def __init__(self):
            self.hooks = []

        def register_forward_hook(self, hook):
            self.hooks.append(hook)

    class _Model:
        def __init__(self):
            self.checkpointing_enabled = False
            self.input_grads_enabled = False

        def gradient_checkpointing_enable(self):
            self.checkpointing_enabled = True

        def enable_input_require_grads(self):
            self.input_grads_enabled = True

    model = _Model()

    result = _prepare_lora_model_for_training(model, gradient_checkpointing=True)

    assert result is model
    assert model.checkpointing_enabled is True
    assert model.input_grads_enabled is True


def test_prepare_lora_model_uses_embedding_hook_when_needed():
    class _Embeddings:
        def __init__(self):
            self.hooks = []

        def register_forward_hook(self, hook):
            self.hooks.append(hook)

    class _Model:
        def __init__(self):
            self.embeddings = _Embeddings()

        def get_input_embeddings(self):
            return self.embeddings

    model = _Model()

    _prepare_lora_model_for_training(model, gradient_checkpointing=True)

    assert len(model.embeddings.hooks) == 1


def test_train_agentic_rl_cli_dry_run(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_jsonl(dataset_dir / "sft_messages.jsonl", [_sft_row(index) for index in range(5)])
    output_dir = tmp_path / "run"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "train_agentic_rl.py"),
            "--dataset-dir",
            str(dataset_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["mode"] == "dry-run"
    assert payload["config"]["model_id"] == DEFAULT_TINY_MODEL_ID
    assert payload["training_status"] == "ready"
    assert (output_dir / "training_manifest.json").exists()


def test_train_agentic_rl_cli_sft_requires_explicit_training_flag(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_jsonl(dataset_dir / "sft_messages.jsonl", [_sft_row(index) for index in range(5)])

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "train_agentic_rl.py"),
            "--dataset-dir",
            str(dataset_dir),
            "--output-dir",
            str(tmp_path / "run"),
            "--mode",
            "sft",
            "--trainer-backend",
            "trl-sft",
            "--max-steps",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["training_started"] is False
    assert payload["training_status"] == "requires_allow_actual_training"
    assert payload["config"]["trainer_backend"] == "trl-sft"
    assert payload["config"]["max_steps"] == 1


def test_train_agentic_rl_cli_dpo_requires_explicit_training_flag(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_jsonl(
        dataset_dir / "preference_pairs.jsonl", [_preference_row(index) for index in range(5)]
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "train_agentic_rl.py"),
            "--dataset-dir",
            str(dataset_dir),
            "--output-dir",
            str(tmp_path / "run"),
            "--mode",
            "dpo",
            "--max-steps",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["mode"] == "dpo"
    assert payload["training_started"] is False
    assert payload["training_status"] == "requires_allow_actual_training"
    assert payload["config"]["trainer_backend"] == "trl-dpo"
    assert payload["config"]["learning_rate"] == 5e-6


def test_train_agentic_rl_cli_grpo_requires_explicit_training_flag(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_jsonl(dataset_dir / "grpo_rollouts.jsonl", [_grpo_row(index) for index in range(5)])

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "train_agentic_rl.py"),
            "--dataset-dir",
            str(dataset_dir),
            "--output-dir",
            str(tmp_path / "run"),
            "--mode",
            "grpo",
            "--max-steps",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["mode"] == "grpo"
    assert payload["training_started"] is False
    assert payload["training_status"] == "requires_allow_actual_training"
    assert payload["config"]["trainer_backend"] == "trl-grpo"
    assert payload["config"]["learning_rate"] == 1e-6
    assert payload["config"]["per_device_train_batch_size"] == 2


def test_token_and_privacy_helpers():
    assert estimate_tokens("北京邮电大学 policy query") > 1
    assert scan_privacy("postgresql://user:pass@example.com/db")
    assert scan_privacy("联系方式 +8613520978645")


def test_training_config_and_base_vs_adapter_report_render():
    config = SFTTrainingConfig(trainer_backend="trl-sft", max_steps=3, warmup_ratio=0.05)

    assert config.trainer_backend == "trl-sft"
    assert config.max_steps == 3
    assert config.warmup_ratio == 0.05
    report = render_base_vs_adapter_report(
        {
            "model_id": DEFAULT_TINY_MODEL_ID,
            "adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_lora/adapter",
            "sample_count": 1,
            "base_avg_score": 0.1,
            "adapter_avg_score": 0.2,
            "delta": 0.1,
            "rows": [{"id": "row1", "task_type": "rag_query_plan"}],
            "notes": ["smoke"],
        }
    )

    assert "Base vs Adapter" in report
    assert "qwen2_5_0_5b_lora" in report

    result_report = render_training_result_markdown(
        {
            "training_status": "completed",
            "trainer_backend_used": "trl-sft",
            "model_id": DEFAULT_TINY_MODEL_ID,
            "adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_lora/adapter",
            "checkpoint_dirs": ["checkpoint-3"],
            "model_eval_report": {"sample_count": 1, "delta": 0.1},
        }
    )

    assert "Agentic RL Training Result" in result_report
    assert "completed" in result_report

    dpo_report = render_sft_dpo_report(
        {
            "model_id": DEFAULT_TINY_MODEL_ID,
            "sft_adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_lora/adapter",
            "dpo_adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_dpo_lora/adapter",
            "sample_count": 1,
            "variant_scores": {"base": 0.1, "sft_adapter": 0.2, "dpo_adapter": 0.3},
            "dpo_delta_vs_base": 0.2,
            "dpo_delta_vs_sft": 0.1,
            "initial_policy_adapter": "workspace/rl/training_runs/qwen2_5_0_5b_lora/adapter",
            "privacy_scan_hits": [],
            "rows": [{"id": "row1", "task_type": "evidence_audit_fix"}],
            "notes": ["smoke"],
        }
    )

    assert "SFT vs DPO" in dpo_report
    assert "dpo_delta_vs_sft" in dpo_report

    grpo_report = render_sft_dpo_grpo_report(
        {
            "model_id": DEFAULT_TINY_MODEL_ID,
            "sft_adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_lora/adapter",
            "dpo_adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_dpo_lora/adapter",
            "grpo_adapter_dir": "workspace/rl/training_runs/qwen2_5_0_5b_grpo_lora/adapter",
            "sample_count": 1,
            "variant_scores": {
                "base": 0.1,
                "sft_adapter": 0.2,
                "dpo_adapter": 0.3,
                "grpo_adapter": 0.4,
            },
            "grpo_delta_vs_base": 0.3,
            "grpo_delta_vs_sft": 0.2,
            "grpo_delta_vs_dpo": 0.1,
            "initial_policy_adapter": "workspace/rl/training_runs/qwen2_5_0_5b_dpo_lora/adapter",
            "privacy_scan_hits": [],
            "rows": [{"id": "row1", "task_type": "rag_query_plan"}],
            "notes": ["smoke"],
        }
    )

    assert "Base vs SFT vs DPO vs GRPO" in grpo_report
    assert "grpo_delta_vs_dpo" in grpo_report


def _sft_row(index: int):
    return {
        "id": f"sample_{index}",
        "task_type": "rag_query_plan",
        "messages": [
            {
                "role": "user",
                "content": f"为第 {index} 所学校制定官方推免政策检索计划。",
            },
            {
                "role": "assistant",
                "content": "优先检索研究生院和学院官网，记录发布时间、URL 和证据 hash。",
            },
        ],
        "evidence_refs": [f"public_kb:{index}"],
        "reward": 0.8,
    }


def _preference_row(index: int):
    return {
        "id": f"pref_{index}",
        "task_type": "evidence_audit_fix",
        "prompt": f"修复第 {index} 个缺少官方证据的 claim。",
        "chosen": "补检索官方来源，绑定 URL 和 hash，无法核验时降级为 needs_review。",
        "rejected": "根据经验直接补齐结论。",
        "chosen_reward": 1.0,
        "rejected_reward": -1.0,
    }


def _grpo_row(index: int):
    return {
        "task_type": "rag_query_plan",
        "prompt": f"为第 {index} 所学校制定官方推免政策检索计划。",
        "rollouts": [
            {
                "trajectory_id": f"good_{index}",
                "actions": ["plan_query", "retrieve", "audit"],
                "evidence_refs": [f"public_kb:{index}"],
                "output": "优先检索官方研究生院和学院官网，记录 URL、年份和 hash。",
                "reward": {"total": 1.0, "hard_failures": [], "terms": {}},
            },
            {
                "trajectory_id": f"bad_{index}",
                "actions": ["plan_query"],
                "evidence_refs": [],
                "output": "直接搜索经验帖并补齐结论。",
                "reward": {"total": -1.0, "hard_failures": ["missing_evidence"], "terms": {}},
            },
        ],
    }


def _write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
