from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agentic_rollout_collector import collect_public_agentic_rollouts  # noqa: E402
from agentic_training_readiness import evaluate_formal_training_readiness  # noqa: E402
from storage import Workspace  # noqa: E402


def test_collect_public_rollouts_are_traceable_and_formally_trainable(tmp_path):
    workspace = Workspace(str(tmp_path / "workspace"))
    output_dir = tmp_path / "dataset"

    result = collect_public_agentic_rollouts(workspace, output_dir)
    readiness = evaluate_formal_training_readiness(output_dir)
    grpo_rows = _read_jsonl(output_dir / "grpo_rollouts.jsonl")
    sft_rows = _read_jsonl(output_dir / "sft_messages.jsonl")

    assert result.report["execution_mode"] == "offline_real_agent_chain"
    assert result.report["record_count"] >= 17
    assert result.report["candidate_groups"] >= 200
    assert result.report["candidate_count_per_group"] == 4
    assert result.report["trajectory_count"] == result.report["candidate_groups"] * 4
    assert len(sft_rows) == result.report["candidate_groups"]
    assert readiness.ready is True
    assert readiness.source_split_overlaps == {"sft": [], "dpo": [], "grpo": []}
    assert readiness.train_task_counts["grpo"]["rag_query_plan"] >= 50
    assert all(len(row["rollouts"]) == 4 for row in grpo_rows)
    assert all(row["source_records"] for row in grpo_rows)
    assert any(
        "摘要" in _assistant_content(row) and "原始页面核验" in _assistant_content(row)
        for row in sft_rows
        if "只保存摘要" in _user_content(row)
    )
    assert any(
        "authority" in _assistant_content(row) and "不能替代年度官方通知" in _assistant_content(row)
        for row in sft_rows
        if "必须区分" in _user_content(row)
    )
    assert any(
        "needs_review" in _assistant_content(row) and "重新审计" in _assistant_content(row)
        for row in sft_rows
        if "缺少官方细节证据" in _user_content(row)
    )
    assert all("任务：" in _assistant_content(row) for row in sft_rows)
    assert all("[PUBLIC_RAG_CONTROL]" in _assistant_content(row) for row in sft_rows)
    assert all("fact_write=blocked" in _assistant_content(row) for row in sft_rows)
    assert any(
        observation.kind == "retrieval"
        for trajectory in result.trajectories
        for observation in trajectory.observations
    )


def test_formal_readiness_rejects_missing_source_provenance(tmp_path):
    workspace = Workspace(str(tmp_path / "workspace"))
    output_dir = tmp_path / "dataset"
    collect_public_agentic_rollouts(workspace, output_dir, record_feedback=False)

    path = output_dir / "sft_messages.jsonl"
    rows = _read_jsonl(path)
    rows[0]["source_records"] = []
    _write_jsonl(path, rows)

    readiness = evaluate_formal_training_readiness(output_dir)

    assert readiness.ready is False
    assert any(issue.code == "missing_source_provenance" for issue in readiness.issues)


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _user_content(row) -> str:
    return next(
        (
            str(message.get("content", ""))
            for message in row.get("messages", [])
            if message.get("role") == "user"
        ),
        "",
    )


def _assistant_content(row) -> str:
    return next(
        (
            str(message.get("content", ""))
            for message in row.get("messages", [])
            if message.get("role") == "assistant"
        ),
        "",
    )
