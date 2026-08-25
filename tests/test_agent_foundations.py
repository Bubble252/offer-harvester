import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agents.swarm import LeadAgent, SwarmTask  # noqa: E402
from memory import FeedbackRecord, LocalMemoryManager, SessionSummary  # noqa: E402
from storage import Workspace  # noqa: E402


def test_swarm_runs_independent_workers_and_preserves_failures():
    async def worker(task, context):
        await asyncio.sleep(0.01)
        if task.task_id == "failed":
            raise RuntimeError("fixture failure")
        return {"value": task.payload["value"]}

    decision, context, synthesis = asyncio.run(
        LeadAgent(timeout_seconds=1).run(
            "run_swarm_demo",
            [
                SwarmTask(task_id="one", role="advisor", payload={"value": 1}),
                SwarmTask(task_id="failed", role="policy", payload={"value": 2}),
            ],
            worker,
        )
    )

    assert decision.use_swarm is True
    assert len(context.contributions) == 2
    assert context.failures[0]["task_id"] == "failed"
    assert synthesis["status"] == "needs_review"
    assert synthesis["requires_evidence_audit"] is True


def test_swarm_keeps_serial_dependencies_in_order():
    seen = []

    def worker(task, context):
        seen.append(task.task_id)
        return {"ok": True}

    decision, _, _ = asyncio.run(
        LeadAgent().run(
            "run_serial_demo",
            [
                SwarmTask(task_id="first", role="lead"),
                SwarmTask(task_id="second", role="reviewer", depends_on=["first"]),
            ],
            worker,
        )
    )

    assert decision.use_swarm is True
    assert seen == ["first", "second"]


def test_layered_memory_requires_explicit_confirmation(tmp_path):
    manager = LocalMemoryManager(Workspace(str(tmp_path)))
    candidate = manager.write_candidate(
        kind="semantic",
        key="preferred_material_tone",
        value={"tone": "克制、具体"},
        source_ref="user_feedback_demo",
        confidence=0.8,
    )
    assert candidate.status == "candidate"
    assert manager.search("preferred_material_tone", include_candidates=False) == []

    confirmed = manager.confirm(candidate.memory_id)
    assert confirmed.status == "confirmed"
    assert manager.search("preferred_material_tone", include_candidates=False)[0].memory_id == (
        candidate.memory_id
    )

    rejected = manager.reject(candidate.memory_id)
    assert rejected.status == "rejected"
    assert manager.search("preferred_material_tone", include_rejected=False) == []
    summary = manager.summarize()
    assert summary.by_kind["semantic"] == 1
    assert summary.by_status["rejected"] == 1


def test_memory_governance_lifecycle_conflict_export_and_tombstone(tmp_path):
    manager = LocalMemoryManager(Workspace(str(tmp_path)))
    first = manager.write_candidate(
        kind="fact",
        key="policy.deadline.demo",
        value={"deadline": "2026-09-10"},
        source_ref="src_a#chunk_a",
        confidence=0.9,
        sensitivity="high",
    )
    second = manager.write_candidate(
        kind="fact",
        key="policy.deadline.demo",
        value={"deadline": "2026-09-20"},
        source_ref="src_b#chunk_b",
        confidence=0.8,
    )

    conflicted = manager.mark_conflict(
        first.memory_id, second.memory_id, reason="deadline mismatch"
    )
    assert second.memory_id in conflicted.conflicts_with
    assert first.memory_id in manager.records()[1].conflicts_with

    replacement = manager.supersede(
        first.memory_id,
        kind="fact",
        key="policy.deadline.demo",
        value={"deadline": "2026-09-15"},
        source_ref="src_official#chunk_1",
        confidence=0.95,
    )
    assert replacement.supersedes == [first.memory_id]
    assert manager.records()[0].status == "superseded"
    assert manager.records()[0].superseded_by == replacement.memory_id

    archived = manager.archive(second.memory_id, reason="older college page")
    assert archived.status == "archived"
    expired = manager.expire(replacement.memory_id, reason="year changed")
    assert expired.status == "expired"
    assert manager.search("policy.deadline.demo") == []
    assert manager.search("policy.deadline.demo", include_historical=True)

    exported = manager.export_records()
    assert exported[0]["redacted"] is True
    assert exported[0]["value"] == {}

    tombstone = manager.delete(second.memory_id, reason="user deletion")
    assert tombstone.status == "tombstone"
    assert tombstone.value == {}
    assert all(item["memory_id"] != second.memory_id for item in manager.export_records())
    assert any(item["status"] == "tombstone" for item in manager.replay())


def test_memory_writes_layer_files_index_and_filtered_exports(tmp_path):
    manager = LocalMemoryManager(Workspace(str(tmp_path)))
    fact = manager.write_candidate(
        kind="fact",
        scope="student:demo",
        key="student.gpa",
        value={"gpa": "3.8/4.0"},
        source_ref="doc_profile#field_gpa",
        authority="local_upload",
        confidence=0.8,
    )
    semantic = manager.write_candidate(
        kind="semantic",
        scope="student:demo",
        key="preferred_target",
        value={"direction": "多模态学习"},
        source_ref="user_note#1",
        confidence=0.7,
    )

    assert (tmp_path / "memory" / "layers" / "fact" / "records.jsonl").exists()
    assert (tmp_path / "memory" / "layers" / "semantic" / "records.jsonl").exists()
    assert (tmp_path / "memory" / "index.json").exists()

    exported = manager.export_records(kinds=["fact"], scopes=["student:demo"])
    assert [item["memory_id"] for item in exported] == [fact.memory_id]
    assert manager.replay(source_refs=["user_note#1"])[0]["memory_id"] == semantic.memory_id

    deleted = manager.delete_matching(
        scopes=["student:demo"], source_refs=["doc_profile#field_gpa"]
    )
    assert [item.memory_id for item in deleted] == [fact.memory_id]
    assert manager.get(fact.memory_id).status == "tombstone"


def test_working_memory_session_summary_feedback_and_negative_memory(tmp_path):
    manager = LocalMemoryManager(Workspace(str(tmp_path)))
    working = manager.write_working_memory(
        run_id="run_demo",
        key="query_plan",
        value={"query": "导师截止日期"},
        source_refs=["bundle_1"],
    )
    assert working.kind == "working"
    assert working.scope == "workflow:run_demo"

    summary = manager.create_session_summary(
        SessionSummary(
            run_id="run_demo",
            goal="复核导师网页",
            key_facts=["截止日期需要官方来源确认"],
            unconfirmed_items=["deadline"],
            evidence_refs=["bundle_1"],
        )
    )
    assert summary.kind == "episodic"
    assert "bundle_1" in summary.source_refs

    negative = manager.write_negative_memory(
        key="style.too_marketing",
        value={"avoid": "营销化套话"},
        blocked_patterns=["营销化"],
        reason="用户明确否认",
    )
    assert negative.negative is True
    assert manager.is_blocked_by_negative_memory("请生成更营销化的套磁邮件") is True
    assert manager.search("style.too_marketing") == []
    assert manager.search("style.too_marketing", include_negative=True)

    feedback = manager.write_feedback(
        FeedbackRecord(
            feedback_type="material_edit",
            subject_ref="material_1",
            issue_category="tone_mismatch",
            accepted=True,
            evidence_refs=["quality_1"],
            suggested_candidate_type="rule",
        )
    )
    assert feedback.kind == "feedback"
    assert feedback.value["suggested_candidate_type"] == "rule"


def test_confirmed_memory_can_create_promotion_candidate_without_applying_it(tmp_path):
    manager = LocalMemoryManager(Workspace(str(tmp_path)))
    memory = manager.write_candidate(
        kind="fact",
        scope="student:demo",
        key="student.project",
        value={"project": "RAG 保研政策问答系统"},
        source_ref="doc_project#1",
        confidence=0.8,
    )

    try:
        manager.create_promotion_candidate(memory.memory_id, target="profile")
    except ValueError as exc:
        assert "Only confirmed memory" in str(exc)
    else:
        raise AssertionError("unconfirmed memory should not create promotion candidates")

    confirmed = manager.confirm(memory.memory_id)
    candidate = manager.create_promotion_candidate(
        confirmed.memory_id,
        target="profile",
        reason="用户确认该项目可以进入画像",
    )

    assert candidate.status == "candidate"
    assert candidate.requires_user_confirmation is True
    assert candidate.payload["key"] == "student.project"
    assert manager.promotion_candidates(target="profile")[0].candidate_id == candidate.candidate_id
