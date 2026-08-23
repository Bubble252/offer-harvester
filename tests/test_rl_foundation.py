import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from models import now_iso  # noqa: E402
from rl_foundation import (  # noqa: E402
    CallableJudgeClient,
    DatasetBuilder,
    ExperimentTracker,
    OfflineRLBoundary,
    RuleBasedReward,
    evaluate_sample,
)
from storage import Workspace  # noqa: E402


def test_rl_sample_is_anonymized_and_reward_is_explainable(tmp_path):
    workspace = Workspace(str(tmp_path))
    builder = DatasetBuilder(workspace)
    sample = builder.build_sample(
        task_type="contact_email",
        student_summary="姓名：张三，邮箱 zhangsan@example.com，电话 13800138000",
        model_output="老师您好，我关注多模态学习。",
        evidence_refs=["kb_demo#chunk_demo"],
        evidence_status="audited",
        quality_score=88,
        accepted=True,
        created_at=now_iso(),
    )
    builder.append(sample)
    breakdown = evaluate_sample(
        sample,
        reward=RuleBasedReward(),
        judge=CallableJudgeClient(lambda _: 0.8),
    )

    assert sample.anonymized is True
    assert "[EMAIL]" in sample.student_summary
    assert "[PHONE]" in sample.student_summary
    assert breakdown.total > 0
    assert "evidence_coverage" in breakdown.terms
    assert breakdown.judge_score == 0.8
    assert builder.records()[0].sample_id == sample.sample_id


def test_experiment_tracker_records_baseline_delta_without_training(tmp_path):
    tracker = ExperimentTracker(Workspace(str(tmp_path)))
    record = tracker.compare(
        task_type="ppt_outline",
        baseline_version="baseline-v1",
        candidate_version="candidate-v2",
        baseline_score=0.62,
        candidate_score=0.74,
        notes=["offline fixture only"],
    )
    assert record.delta == 0.12
    assert tracker.records()[0].candidate_version == "candidate-v2"
    assert OfflineRLBoundary().training_enabled is False
