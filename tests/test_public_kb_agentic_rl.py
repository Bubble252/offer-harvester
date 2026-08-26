from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agentic_rl import (  # noqa: E402
    AgentTrajectory,
    RewardV2,
    TrainReadyDatasetExporter,
    trajectory_to_rl_sample,
)
from agents.agentic_rl import (  # noqa: E402
    EvidenceAuditFixAgent,
    QueryPlannerAgent,
    SafetyGateAgent,
    TrajectoryBuilderAgent,
)
from public_kb import (  # noqa: E402
    PublicKBRecord,
    PublicKBSource,
    PublicKBStore,
    seed_real_public_samples,
    seed_target_universities,
)
from storage import Workspace  # noqa: E402
from supabase_sync import SupabasePublicKBSync  # noqa: E402


def test_public_kb_seed_validate_and_search(tmp_path):
    store = PublicKBStore(Workspace(str(tmp_path)))
    result = seed_target_universities(store, replace=True)
    report = store.validate()

    assert result.university_count >= 40
    assert report.valid is True
    assert report.record_count == result.record_count
    assert store.search("北京 邮电")[0].name == "北京邮电大学"
    assert store.load_manifest().scope == "public_only"


def test_public_kb_real_public_samples_are_summary_only(tmp_path):
    store = PublicKBStore(Workspace(str(tmp_path)))
    seed_target_universities(store, replace=True)
    result = seed_real_public_samples(store)
    report = store.validate()

    assert result.record_count >= 16
    assert report.valid is True
    records = [item for item in store.records() if item.record_id.startswith("pubrec_real_")]
    chunks = [item for item in store.chunks() if item.chunk_id.startswith("pubchunk_real_")]
    assert {item.record_kind for item in records} >= {"policy", "advisor"}
    assert all(item.privacy_scope == "public" for item in store.sources())
    assert all(chunk.embedding_route == "external_public" for chunk in chunks)
    assert all(chunk.metadata.get("summary_only") is True for chunk in chunks)
    assert any(item.valid_for_year == 2027 for item in records)


def test_public_kb_validation_rejects_unlinked_record(tmp_path):
    store = PublicKBStore(Workspace(str(tmp_path)))
    store.append_record(
        PublicKBRecord(
            record_kind="policy",
            name="无来源政策",
            summary="缺少来源的政策不允许进入同步。",
        )
    )

    report = store.validate()

    assert report.valid is False
    assert any(issue.code == "missing_source_ref" for issue in report.issues)


def test_supabase_sync_dry_run_and_schema(tmp_path):
    store = PublicKBStore(Workspace(str(tmp_path)))
    seed_target_universities(store, replace=True)
    syncer = SupabasePublicKBSync(dry_run=True)
    result = syncer.sync(store)

    assert result.mode == "dry-run"
    assert result.record_count >= 40
    assert result.errors == []
    assert "create extension if not exists vector" in syncer.schema_sql()
    assert len(syncer.schema_statements()) >= 4
    data_sql = syncer.data_sql(store)
    assert "insert into public.public_kb_records" in data_sql
    assert "北京邮电大学" in data_sql


def test_supabase_sync_blocks_invalid_public_kb(tmp_path):
    store = PublicKBStore(Workspace(str(tmp_path)))
    source = store.append_source(
        PublicKBSource(
            source_kind="public_web",
            title="missing url",
            authority_level="college_official",
        )
    )
    store.append_record(
        PublicKBRecord(
            record_kind="policy",
            name="政策",
            summary="存在来源但 URL 无效。",
            source_refs=[source.source_id],
        )
    )

    result = SupabasePublicKBSync(dry_run=True).sync(store)

    assert result.errors
    assert result.uploaded == 0


def test_agentic_rl_exporter_writes_train_ready_files(tmp_path):
    good = AgentTrajectory(
        task_type="rag_query_plan",
        input_summary="公开政策检索",
        prompt="检索北京邮电大学推免政策，要求优先官方来源。",
        target_id="bupt",
        candidate_group_id="g1",
        privacy_route="public_external_allowed",
        output="使用研究生院官网、学院通知和发布时间过滤，召回后交给 EvidenceAudit。",
        evidence_refs=["public_kb:pubrec_university_bupt"],
        audit_status="passed",
        user_feedback={"accepted": True},
    )
    weak = good.model_copy(
        update={
            "trajectory_id": "trajectory_weak",
            "output": "搜索经验帖后直接写结论。",
            "evidence_refs": [],
            "audit_status": "needs_review",
            "user_feedback": {"expired_policy_used": True},
        }
    )
    reward = RewardV2()
    rewards = [reward.score(good), reward.score(weak)]
    counts = TrainReadyDatasetExporter(tmp_path).export([good, weak], rewards)

    assert counts["trajectories"] == 2
    assert counts["sft_messages"] == 1
    assert counts["preference_pairs"] == 1
    assert counts["grpo_rollouts"] == 1
    preference = json.loads((tmp_path / "preference_pairs.jsonl").read_text().splitlines()[0])
    assert preference["chosen_reward"] > preference["rejected_reward"]


def test_agentic_rl_agents_build_fix_gate_and_bridge():
    planner = QueryPlannerAgent()
    plan = planner.plan("北邮 推免 截止日期", missing_evidence=["官方通知"])
    fixes = EvidenceAuditFixAgent().propose(["缺少官方证据"], available_evidence=["bundle_1"])
    trajectory = TrajectoryBuilderAgent().build(
        task_type="evidence_audit_fix",
        input_summary="修复缺少官方证据的政策 claim",
        output="补检索研究生院官网并降低未审计 claim 的确定性。",
        evidence_refs=["bundle_1"],
        audit_status="passed",
        privacy_route="public_external_allowed",
        actions=["plan_query", "retrieve", "audit", "fix_audit"],
        run_id="run_1",
    )
    safety = SafetyGateAgent().check(trajectory)
    sample = trajectory_to_rl_sample(trajectory)

    assert plan.queries
    assert fixes[0]["action"] == "retrieve"
    assert safety["allowed"] is True
    assert sample.anonymized is True
    assert sample.prompt == "修复缺少官方证据的政策 claim"


def test_build_public_kb_trajectories_adds_trainable_task_types(tmp_path):
    from tools.build_agentic_rl_dataset import build_public_kb_trajectories  # noqa: E402

    store = PublicKBStore(Workspace(str(tmp_path)))
    seed_target_universities(store, replace=True)
    seed_real_public_samples(store)
    records = store.records()[:3]

    trajectories = build_public_kb_trajectories(records)

    assert len(trajectories) >= 12
    assert {item.task_type for item in trajectories} >= {"rag_query_plan", "evidence_audit_fix"}
    assert any(item.user_feedback.get("accepted") is True for item in trajectories)
    assert any(item.audit_status in {"failed", "needs_review"} for item in trajectories)
