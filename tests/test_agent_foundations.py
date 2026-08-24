import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agents.swarm import LeadAgent, SwarmTask  # noqa: E402
from memory import LocalMemoryManager  # noqa: E402
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

    exported = manager.export_records()
    assert exported[0]["redacted"] is True
    assert exported[0]["value"] == {}

    tombstone = manager.delete(second.memory_id, reason="user deletion")
    assert tombstone.status == "tombstone"
    assert tombstone.value == {}
    assert all(item["memory_id"] != second.memory_id for item in manager.export_records())
    assert any(item["status"] == "tombstone" for item in manager.replay())
