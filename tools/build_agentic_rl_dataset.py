#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agentic_rl import AgentTrajectory, RewardV2, TrainReadyDatasetExporter  # noqa: E402
from agents.agentic_rl import TrajectoryBuilderAgent  # noqa: E402
from public_kb import (  # noqa: E402
    PublicKBStore,
    seed_real_public_samples,
    seed_target_universities,
)
from storage import Workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build train-ready Agentic RL JSONL datasets without starting training."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT / "workspace",
        help="Workspace containing public_kb/ and rl/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <workspace>/rl/train_ready.",
    )
    parser.add_argument(
        "--limit-universities",
        type=int,
        default=0,
        help="Limit universities for quick tests. 0 means all seeded targets.",
    )
    parser.add_argument(
        "--replace-public-kb-seed",
        action="store_true",
        help="Rebuild the local public KB university seed before exporting.",
    )
    parser.add_argument(
        "--include-real-public-samples",
        action="store_true",
        help="Seed verified public policy/advisor URL samples before exporting.",
    )
    args = parser.parse_args()

    workspace = Workspace(str(args.workspace))
    store = PublicKBStore(workspace)
    if args.replace_public_kb_seed or not store.records():
        seed_target_universities(store, replace=args.replace_public_kb_seed)
    if args.include_real_public_samples:
        seed_real_public_samples(store)

    records = [
        record
        for record in store.records()
        if record.record_kind in {"university", "policy", "advisor"}
    ]
    if args.limit_universities > 0:
        records = records[: args.limit_universities]

    trajectories = build_public_kb_trajectories(records)
    reward = RewardV2()
    rewards = [reward.score(item) for item in trajectories]
    output_dir = args.output_dir or (workspace.root / "rl" / "train_ready")
    counts = TrainReadyDatasetExporter(output_dir).export(trajectories, rewards)
    report = {
        "workspace": str(workspace.root),
        "output_dir": str(output_dir),
        "source_record_count": len(records),
        "trajectory_count": len(trajectories),
        "reward_summary": {
            "min": min((item.total for item in rewards), default=0.0),
            "max": max((item.total for item in rewards), default=0.0),
            "avg": round(
                sum(item.total for item in rewards) / len(rewards),
                4,
            )
            if rewards
            else 0.0,
        },
        "files": counts,
    }
    (output_dir / "dataset_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_public_kb_trajectories(records: List[Any]) -> List[AgentTrajectory]:
    builder = TrajectoryBuilderAgent()
    trajectories: List[AgentTrajectory] = []
    for record in records:
        trajectories.extend(build_record_trajectories(builder, record))
    return trajectories


def build_record_trajectories(
    builder: TrajectoryBuilderAgent, record: Any
) -> List[AgentTrajectory]:
    uid = record.university_id or record.record_id
    evidence_ref = f"public_kb:{record.record_id}"
    outputs: List[AgentTrajectory] = []
    outputs.extend(_query_plan_pair(builder, record, uid, evidence_ref))
    outputs.extend(_audit_fix_pair(builder, record, uid, evidence_ref))
    if record.record_kind in {"policy", "advisor"}:
        outputs.extend(_policy_advisor_qa_pair(builder, record, uid, evidence_ref))
    return outputs


def _query_plan_pair(
    builder: TrajectoryBuilderAgent,
    record: Any,
    uid: str,
    evidence_ref: str,
) -> List[AgentTrajectory]:
    group_id = f"rag_query_plan:{record.record_id}:official_source"
    prompt = (
        f"为 {record.name} 制定 RAG query plan，"
        "要求优先官方来源、记录年份、authority、URL 和 hash。"
    )
    good_output = (
        f"先用 {record.name}、推免、研究生招生、学院官网、通知、招生简章和年份组合检索；"
        "只保留官方研究生院、学院或导师主页来源，记录 URL、publisher、发布时间、适用年份和 hash；"
        "若缺少原文或年份，则把结论降级为 needs_review 并交给 EvidenceAudit。"
    )
    weak_output = f"直接搜索 {record.name} 经验帖，汇总看到的申请要求。"
    return [
        _trajectory(
            builder,
            "rag_query_plan",
            prompt,
            good_output,
            uid,
            group_id,
            [evidence_ref],
            ["plan_query", "retrieve", "rerank", "audit"],
            {"accepted": True},
            audit_status="passed",
        ),
        _trajectory(
            builder,
            "rag_query_plan",
            prompt,
            weak_output,
            uid,
            group_id,
            [],
            ["plan_query"],
            {
                "accepted": False,
                "expired_policy_used": True,
                "needs_user_confirmation": True,
            },
            audit_status="needs_review",
        ),
    ]


def _audit_fix_pair(
    builder: TrajectoryBuilderAgent,
    record: Any,
    uid: str,
    evidence_ref: str,
) -> List[AgentTrajectory]:
    group_id = f"evidence_audit_fix:{record.record_id}:missing_authority"
    prompt = (
        f"EvidenceAudit 指出 {record.name} 的申请建议缺少官方证据，"
        "请给出修复动作，不能编造政策细节。"
    )
    good_output = (
        "先保留原 claim 为 candidate，补检索研究生院、学院官网或导师官方主页；"
        "如果找到官方页面，则绑定 source/chunk/hash 后再恢复 claim；"
        "如果只找到论坛或过期通知，则删除结论或改成需要用户确认的问题。"
    )
    weak_output = "根据常见保研经验补齐缺失信息，让材料看起来更完整。"
    return [
        _trajectory(
            builder,
            "evidence_audit_fix",
            prompt,
            good_output,
            uid,
            group_id,
            [evidence_ref],
            ["plan_query", "retrieve", "audit", "fix_audit"],
            {"accepted": True},
            audit_status="passed",
        ),
        _trajectory(
            builder,
            "evidence_audit_fix",
            prompt,
            weak_output,
            uid,
            group_id,
            [],
            ["fix_audit"],
            {"accepted": False, "rejected_fact_used": True},
            audit_status="failed",
        ),
    ]


def _policy_advisor_qa_pair(
    builder: TrajectoryBuilderAgent,
    record: Any,
    uid: str,
    evidence_ref: str,
) -> List[AgentTrajectory]:
    task_name = "政策" if record.record_kind == "policy" else "导师画像"
    group_id = f"policy_advisor_qa:{record.record_id}:grounded_answer"
    prompt = f"基于公开 KB 回答一个关于 {record.name} 的{task_name}问题，要求说明证据状态。"
    good_output = (
        f"{record.name} 已有公开来源摘要，可用于定位原始页面；"
        "回答时只能复述已绑定证据的来源类型、publisher、年份或研究方向摘要，"
        "不能把 summary-only 记录扩写成未核验的具体截止日期、录取名额或导师承诺。"
    )
    weak_output = f"{record.name} 条件很好，建议直接按网上常见说法准备申请材料。"
    return [
        _trajectory(
            builder,
            "policy_advisor_qa",
            prompt,
            good_output,
            uid,
            group_id,
            [evidence_ref],
            ["retrieve", "rerank", "audit"],
            {"accepted": True},
            audit_status="passed",
        ),
        _trajectory(
            builder,
            "policy_advisor_qa",
            prompt,
            weak_output,
            uid,
            group_id,
            [],
            ["retrieve"],
            {"accepted": False, "needs_user_confirmation": True},
            audit_status="needs_review",
        ),
    ]


def _trajectory(
    builder: TrajectoryBuilderAgent,
    task_type: str,
    prompt: str,
    output: str,
    target_id: str,
    candidate_group_id: str,
    evidence_refs: List[str],
    actions: List[str],
    feedback: dict,
    *,
    audit_status: str,
) -> AgentTrajectory:
    return builder.build(
        task_type=task_type,
        input_summary=prompt,
        prompt=prompt,
        output=output,
        evidence_refs=evidence_refs,
        audit_status=audit_status,
        privacy_route="public_external_allowed",
        actions=actions,
        target_id=target_id,
        candidate_group_id=candidate_group_id,
    ).model_copy(update={"user_feedback": feedback})


if __name__ == "__main__":
    raise SystemExit(main())
