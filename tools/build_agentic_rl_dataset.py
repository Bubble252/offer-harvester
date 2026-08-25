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
from public_kb import PublicKBStore, seed_target_universities  # noqa: E402
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
    args = parser.parse_args()

    workspace = Workspace(str(args.workspace))
    store = PublicKBStore(workspace)
    if args.replace_public_kb_seed or not store.records():
        seed_target_universities(store, replace=args.replace_public_kb_seed)

    records = [record for record in store.records() if record.record_kind == "university"]
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
        uid = record.university_id or record.record_id
        group_id = f"rag_query_plan:{uid}:policy_freshness"
        prompt = (
            f"为 {record.name} 的推免/研究生招生政策检索制定 query plan，"
            "要求优先官方来源、记录年份、避免使用未审计网页正文。"
        )
        evidence_ref = f"public_kb:{record.record_id}"
        good_output = (
            f"查询 {record.name} 时先使用研究生院/学院官网限定词，"
            "再补充推免、预报名、复试、招生简章、夏令营和截止日期等关键词；"
            "仅把可追溯到官方 URL、发布时间和内容 hash 的条目交给 EvidenceAudit。"
        )
        trajectories.append(
            builder.build(
                task_type="rag_query_plan",
                input_summary=f"{record.name} 官方政策检索规划",
                prompt=prompt,
                output=good_output,
                evidence_refs=[evidence_ref],
                audit_status="passed",
                privacy_route="public_external_allowed",
                actions=["plan_query", "retrieve", "rerank", "audit"],
                target_id=uid,
                candidate_group_id=group_id,
            ).model_copy(update={"user_feedback": {"accepted": True}})
        )
        weak_output = f"直接搜索 {record.name} 保研经验帖，并把看到的要求写入材料建议。"
        trajectories.append(
            builder.build(
                task_type="rag_query_plan",
                input_summary=f"{record.name} 官方政策检索规划",
                prompt=prompt,
                output=weak_output,
                evidence_refs=[],
                audit_status="needs_review",
                privacy_route="public_external_allowed",
                actions=["plan_query"],
                target_id=uid,
                candidate_group_id=group_id,
            ).model_copy(
                update={
                    "user_feedback": {
                        "accepted": False,
                        "expired_policy_used": True,
                        "needs_user_confirmation": True,
                    }
                }
            )
        )
    return trajectories


if __name__ == "__main__":
    raise SystemExit(main())
