from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agentic_evaluation import (  # noqa: E402
    evaluate_agentic_dataset,
    render_evaluation_markdown,
    write_evaluation_report,
)
from agentic_rl import AgentTrajectory, RewardV2, TrainReadyDatasetExporter  # noqa: E402


def test_agentic_evaluation_scores_and_writes_reports(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    good = AgentTrajectory(
        task_type="rag_query_plan",
        target_id="bupt",
        candidate_group_id="g1",
        policy_version="candidate",
        prompt_version="query-v2",
        privacy_route="public_external_allowed",
        prompt="检索北邮推免政策。",
        output="优先使用研究生院官网和学院通知，记录 URL、年份、发布时间和 hash。",
        evidence_refs=["bundle_1"],
        audit_status="passed",
        user_feedback={"accepted": True},
    )
    bad = good.model_copy(
        update={
            "trajectory_id": "trajectory_bad",
            "policy_version": "baseline",
            "prompt_version": "query-v1",
            "output": "直接参考经验帖给结论。",
            "evidence_refs": [],
            "audit_status": "needs_review",
            "user_feedback": {"expired_policy_used": True},
        }
    )
    rewards = [RewardV2().score(good), RewardV2().score(bad)]
    TrainReadyDatasetExporter(dataset_dir).export([good, bad], rewards)

    report = evaluate_agentic_dataset(dataset_dir, judge_provider="mock")
    paths = write_evaluation_report(report, tmp_path / "reports")
    markdown = render_evaluation_markdown(report)

    assert report.trajectory_count == 2
    assert report.preference_evaluation.pair_count == 1
    assert report.global_failure_modes["expired_policy_used"] == 1
    assert "candidate/query-v2" in markdown
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()


def test_evaluate_agentic_rl_cli(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    trajectory = AgentTrajectory(
        task_type="rag_query_plan",
        privacy_route="public_external_allowed",
        prompt="检索官方政策。",
        output="使用官方来源并交给 EvidenceAudit。",
        evidence_refs=["bundle_1"],
        audit_status="passed",
        user_feedback={"accepted": True},
    )
    reward = RewardV2().score(trajectory)
    TrainReadyDatasetExporter(dataset_dir).export([trajectory], [reward])
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "evaluate_agentic_rl.py"),
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

    assert payload["trajectory_count"] == 1
    assert payload["reports"]["json"].endswith("agentic_rl_evaluation.json")
    assert (output_dir / "agentic_rl_evaluation.md").exists()
