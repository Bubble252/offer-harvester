"""Execute public-only Agentic RL rollouts through the local control plane.

The collector deliberately uses the existing deterministic agent harness:

    QueryPlanner -> Retriever -> EvidenceAudit -> FixAgent -> RewardV2

It does not fetch web-page bodies or call an LLM.  Its purpose is to collect
replayable tool traces from verified public-source metadata before a later
model-backed rollout service is introduced.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from agentic_rl import (
    AgentTrajectory,
    RewardV2Breakdown,
    TrainReadyDatasetExporter,
    TrajectoryObservation,
)
from agents.agentic_rl import (
    EvidenceAuditFixAgent,
    QueryPlannerAgent,
    RewardJudgeAgent,
    SafetyGateAgent,
    TrajectoryBuilderAgent,
)
from agents.evidence_audit_agent import EvidenceAuditAgent, EvidenceAuditResult
from feedback_loop import record_evidence_audit_feedback
from models import KnowledgeBaseSourceCreate
from public_kb import PublicKBRecord, PublicKBSource, PublicKBStore, seed_real_public_samples
from rag import Claim, EvidenceBundle, KnowledgeBaseIndex, KnowledgeBaseRetriever
from rag.embeddings import HashEmbeddingProvider
from rag.evidence_graph import LocalEvidenceGraphStore
from storage import Workspace

TASK_TYPES = ("rag_query_plan", "evidence_audit_fix", "policy_advisor_qa")
SCENARIOS = (
    "official_source",
    "summary_only",
    "authority_boundary",
    "audit_repair",
)


@dataclass
class CollectionResult:
    trajectories: List[AgentTrajectory]
    rewards: List[RewardV2Breakdown]
    report: Dict[str, Any]


def collect_public_agentic_rollouts(
    workspace: Workspace,
    output_dir: Path,
    *,
    record_feedback: bool = True,
) -> CollectionResult:
    """Collect real harness traces using summary-only verified public records."""

    store = PublicKBStore(workspace)
    seed_real_public_samples(store)
    source_by_id = {source.source_id: source for source in store.sources()}
    records = [
        record
        for record in store.records()
        if record.record_id.startswith("pubrec_real_")
        and record.record_kind in {"policy", "advisor"}
        and record.audit_status == "passed"
    ]
    if not records:
        raise ValueError("No verified public policy/advisor records are available for rollout.")

    retriever = _prepare_summary_only_index(workspace, records, source_by_id)
    planner = QueryPlannerAgent()
    auditor = EvidenceAuditAgent()
    fixer = EvidenceAuditFixAgent()
    builder = TrajectoryBuilderAgent()
    judge = RewardJudgeAgent()
    gate = SafetyGateAgent()
    evidence_store = LocalEvidenceGraphStore(workspace)

    trajectories: List[AgentTrajectory] = []
    rewards: List[RewardV2Breakdown] = []
    feedback_count = 0
    for record in records:
        source = _source_for_record(record, source_by_id)
        for task_type in TASK_TYPES:
            for scenario in SCENARIOS:
                group, group_rewards, feedback_written = _execute_group(
                    workspace=workspace,
                    retriever=retriever,
                    planner=planner,
                    auditor=auditor,
                    fixer=fixer,
                    builder=builder,
                    judge=judge,
                    gate=gate,
                    evidence_store=evidence_store,
                    record=record,
                    source=source,
                    task_type=task_type,
                    scenario=scenario,
                    record_feedback=record_feedback,
                )
                trajectories.extend(group)
                rewards.extend(group_rewards)
                feedback_count += feedback_written

    exporter = TrainReadyDatasetExporter(output_dir)
    file_counts = exporter.export(trajectories, rewards)
    report = {
        "schema_version": "agentic-rl-executed-public-rollouts.v1",
        "execution_mode": "offline_real_agent_chain",
        "body_storage": "summary_only_metadata",
        "network_access": False,
        "privacy_scope": "public_only",
        "record_count": len(records),
        "record_kind_counts": dict(
            sorted(Counter(str(record.record_kind) for record in records).items())
        ),
        "scenario_count": len(SCENARIOS),
        "task_types": list(TASK_TYPES),
        "candidate_groups": len(records) * len(TASK_TYPES) * len(SCENARIOS),
        "candidate_count_per_group": 4,
        "trajectory_count": len(trajectories),
        "task_type_counts": dict(
            sorted(Counter(trajectory.task_type for trajectory in trajectories).items())
        ),
        "reward_summary": {
            "min": min((item.total for item in rewards), default=0.0),
            "max": max((item.total for item in rewards), default=0.0),
            "avg": round(sum(item.total for item in rewards) / max(len(rewards), 1), 4),
            "hard_failure_count": sum(bool(item.hard_failures) for item in rewards),
        },
        "feedback_records_written": feedback_count,
        "files": file_counts,
    }
    (output_dir / "rollout_collection_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return CollectionResult(trajectories=trajectories, rewards=rewards, report=report)


def _prepare_summary_only_index(
    workspace: Workspace,
    records: Iterable[PublicKBRecord],
    source_by_id: Dict[str, PublicKBSource],
) -> KnowledgeBaseRetriever:
    index = KnowledgeBaseIndex(
        workspace,
        embedding_provider=HashEmbeddingProvider(),
        storage_backend="sqlite",
    )
    existing = {source.source_ref: source for source in index.list_sources()}
    for record in records:
        source_ref = _public_record_ref(record)
        if source_ref in existing:
            continue
        source = _source_for_record(record, source_by_id)
        source_kind = "policy" if record.record_kind == "policy" else "advisor_source"
        index.add_source(
            KnowledgeBaseSourceCreate(
                source_kind=source_kind,
                source_subtype="policy" if source_kind == "policy" else "advisor_homepage",
                title=record.name,
                text=_summary_index_text(record, source),
                source_ref=source_ref,
                valid_for_year=record.valid_for_year,
                trusted=True,
                confirmed=True,
                notes=json.dumps(
                    {
                        "authority": source.authority_level,
                        "publisher": source.publisher,
                        "public_url": source.url,
                        "summary_only": True,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )
    index.rebuild()
    return KnowledgeBaseRetriever(
        workspace,
        embedding_provider=HashEmbeddingProvider(),
        storage_backend="sqlite",
    )


def _execute_group(
    *,
    workspace: Workspace,
    retriever: KnowledgeBaseRetriever,
    planner: QueryPlannerAgent,
    auditor: EvidenceAuditAgent,
    fixer: EvidenceAuditFixAgent,
    builder: TrajectoryBuilderAgent,
    judge: RewardJudgeAgent,
    gate: SafetyGateAgent,
    evidence_store: LocalEvidenceGraphStore,
    record: PublicKBRecord,
    source: PublicKBSource,
    task_type: str,
    scenario: str,
    record_feedback: bool,
) -> tuple[List[AgentTrajectory], List[RewardV2Breakdown], int]:
    prompt = _prompt_for(record, source, task_type, scenario)
    plan = planner.plan(
        prompt,
        missing_evidence=["官方原始页面或适用年份"] if scenario == "audit_repair" else [],
    )
    query = plan.queries[0] if plan.queries else record.name
    retrieval = retriever.search(
        query,
        source_kinds=["policy"] if record.record_kind == "policy" else ["advisor_source"],
        limit=3,
        include_historical=True,
        as_of_year=record.valid_for_year,
    )
    if not retrieval.hits or retrieval.evidence_bundle is None:
        raise RuntimeError(f"Retrieval unexpectedly returned no evidence for {record.record_id}")

    base_bundle = retrieval.evidence_bundle.model_copy(deep=True)
    base_bundle.metadata.update(
        {
            "rollout_record_id": record.record_id,
            "scenario": scenario,
            "summary_only": True,
            "source_authority": source.authority_level,
        }
    )
    evidence_refs = list(base_bundle.retrieval_refs)
    working_bundle = _bundle_for_scenario(base_bundle, record, scenario)
    initial_audit = auditor.audit_evidence_bundle(working_bundle)
    fixes = fixer.propose(
        initial_audit.unsupported_claims + initial_audit.needs_confirmation,
        available_evidence=evidence_refs,
    )
    final_bundle = _repair_bundle_if_needed(working_bundle, scenario)
    final_audit = auditor.audit_evidence_bundle(final_bundle)
    evidence_store.save(final_bundle)

    feedback_written = 0
    if record_feedback and (initial_audit.unsupported_claims or initial_audit.needs_confirmation):
        feedback_result = record_evidence_audit_feedback(
            workspace,
            initial_audit,
            bundle=working_bundle,
            subject_ref=f"agentic_rl:{record.record_id}:{task_type}:{scenario}",
            run_id=f"rollout:{record.record_id}:{task_type}:{scenario}",
        )
        feedback_written = len(feedback_result.feedback_memory_ids)

    group_id = f"{task_type}:{record.record_id}:{scenario}"
    shared = {
        "prompt": prompt,
        "record": record,
        "source": source,
        "plan": plan,
        "retrieval": retrieval,
        "initial_audit": initial_audit,
        "final_audit": final_audit,
        "fixes": fixes,
        "evidence_refs": evidence_refs,
        "group_id": group_id,
        "scenario": scenario,
    }
    verified = _build_candidate(
        builder,
        gate,
        task_type,
        shared,
        candidate="verified",
        audit=final_audit,
    )
    review = _build_candidate(
        builder,
        gate,
        task_type,
        shared,
        candidate="needs_review",
        audit=final_audit,
    )
    partial = _build_candidate(
        builder,
        gate,
        task_type,
        shared,
        candidate="partial",
        audit=final_audit,
    )
    unsafe = _build_candidate(
        builder,
        gate,
        task_type,
        shared,
        candidate="unsafe",
        audit=initial_audit,
    )
    trajectories = [verified, review, partial, unsafe]
    rewards = [judge.score(trajectory) for trajectory in trajectories]
    for trajectory, reward in zip(trajectories, rewards):
        trajectory.observations.append(
            TrajectoryObservation(
                kind="reward_v2",
                refs=list(trajectory.evidence_refs),
                value=reward.model_dump(),
            )
        )
    return trajectories, rewards, feedback_written


def _build_candidate(
    builder: TrajectoryBuilderAgent,
    gate: SafetyGateAgent,
    task_type: str,
    shared: Dict[str, Any],
    *,
    candidate: str,
    audit: EvidenceAuditResult,
) -> AgentTrajectory:
    record: PublicKBRecord = shared["record"]
    source: PublicKBSource = shared["source"]
    evidence_refs = list(shared["evidence_refs"]) if candidate not in {"partial", "unsafe"} else []
    if candidate == "partial":
        audit_status = "needs_review"
    else:
        audit_status = "passed" if audit.passed and candidate != "unsafe" else "failed"
    actions = ["plan_query", "retrieve", "rerank"]
    if candidate != "partial":
        actions.append("audit")
    if shared["fixes"] and candidate != "partial":
        actions.append("fix_audit")
    if candidate == "needs_review":
        actions.append("ask_user")
    actions.extend(["judge_reward", "safety_check"])
    feedback = _feedback_for_candidate(candidate, source, shared["scenario"])
    output = _candidate_output(task_type, record, source, shared, candidate)
    trajectory = builder.build(
        task_type=task_type,
        input_summary=shared["prompt"],
        prompt=shared["prompt"],
        output=output,
        evidence_refs=evidence_refs,
        audit_status=audit_status,
        privacy_route="public_external_allowed",
        actions=actions,
        run_id=f"rollout:{record.record_id}:{task_type}:{shared['scenario']}",
        target_id=record.university_id or record.record_id,
        candidate_group_id=shared["group_id"],
    ).model_copy(
        update={
            "source_records": [record.record_id],
            "policy_version": "executed-public-harness-v1",
            "prompt_version": f"{task_type}:{shared['scenario']}:v1",
            "user_feedback": feedback,
        }
    )
    trajectory.observations.extend(
        [
            TrajectoryObservation(
                kind="query_plan",
                value={
                    "queries": shared["plan"].queries,
                    "source_filters": shared["plan"].source_filters,
                    "reason": shared["plan"].reason,
                },
            ),
            TrajectoryObservation(
                kind="retrieval",
                refs=list(shared["evidence_refs"]),
                value={
                    "query": shared["retrieval"].query,
                    "hit_count": len(shared["retrieval"].hits),
                    "hit_source_ids": [hit.source_id for hit in shared["retrieval"].hits],
                    "bundle_id": shared["retrieval"].evidence_bundle.bundle_id,
                },
            ),
            TrajectoryObservation(
                kind="evidence_audit",
                refs=list(shared["evidence_refs"]),
                value={
                    "passed": audit.passed,
                    "unsupported_claims": audit.unsupported_claims,
                    "needs_confirmation": audit.needs_confirmation,
                },
            ),
            TrajectoryObservation(
                kind="audit_fix",
                refs=list(shared["evidence_refs"]),
                value={"proposals": shared["fixes"]},
            ),
        ]
    )
    safety = gate.check(trajectory)
    trajectory.observations.append(TrajectoryObservation(kind="safety_gate", value=safety))
    return trajectory


def _bundle_for_scenario(
    bundle: EvidenceBundle,
    record: PublicKBRecord,
    scenario: str,
) -> EvidenceBundle:
    result = bundle.model_copy(deep=True)
    refs = list(result.retrieval_refs)
    if scenario == "summary_only":
        result.claims.append(
            Claim(
                claim_key=f"summary_only:{record.record_id}",
                claim_type="source_detail_boundary",
                text="该公开记录仅保存来源摘要，具体政策条款或招生资格仍需打开原始页面核验。",
                status="needs_confirmation",
                source_refs=refs,
                needs_confirmation=True,
            )
        )
    elif scenario == "authority_boundary":
        result.claims.append(
            Claim(
                claim_key=f"authority_boundary:{record.record_id}",
                claim_type="source_authority_boundary",
                text="回答必须按来源 authority 使用，转载或目录页不能替代原始年度政策页面。",
                status="needs_confirmation",
                source_refs=refs,
                needs_confirmation=True,
            )
        )
    elif scenario == "audit_repair":
        result.claims.append(
            Claim(
                claim_key=f"missing_official_detail:{record.record_id}",
                claim_type="unsupported_policy_detail",
                text="缺少官方证据：不能从摘要直接推出具体申请条件、截止日期或招生名额。",
                status="unsupported",
                source_refs=[],
            )
        )
    return result


def _repair_bundle_if_needed(bundle: EvidenceBundle, scenario: str) -> EvidenceBundle:
    if scenario != "audit_repair":
        return bundle
    result = bundle.model_copy(deep=True)
    for claim in result.claims:
        if claim.claim_type == "unsupported_policy_detail":
            claim.status = "needs_confirmation"
            claim.needs_confirmation = True
            claim.text = "原 claim 已降级为待用户确认，等待补充官方原始页面后再恢复。"
    return result


def _candidate_output(
    task_type: str,
    record: PublicKBRecord,
    source: PublicKBSource,
    shared: Dict[str, Any],
    candidate: str,
) -> str:
    if candidate == "unsafe":
        return (
            f"{record.name} 的具体政策和导师情况已经明确，可以直接按常见经验填写"
            "截止日期、名额和录取结论，无需再核对来源。"
        )
    source_line = (
        f"已命中公开来源摘要：{record.name}；publisher={source.publisher or 'unknown'}；"
        f"authority={source.authority_level}。"
    )
    if candidate == "needs_review":
        return (
            f"{source_line} 当前只把它作为原始页面定位线索，不把摘要扩写为具体政策事实；"
            "请在原页面确认年份、院系要求和招生状态后，再将结论写入申请建议。"
        )
    if candidate == "partial":
        if task_type == "rag_query_plan":
            return (
                f"{source_line} Query plan 先检索学校、年份和推免或导师主页，"
                "并记录来源与适用年份；其余处理放入后续步骤。"
            )
        if task_type == "evidence_audit_fix":
            return f"{source_line} 初始审计问题保留在轨迹中，先记录为待处理事项；具体结论暂不扩写。"
        return f"{source_line} 该来源可用于定位公开政策或导师候选信息；其余细节暂不展开。"
    header = (
        "[PUBLIC_RAG_CONTROL]\n"
        f"task={task_type}\n"
        f"scenario={shared['scenario']}\n"
        "source_scope=public_summary_metadata\n"
        "fact_write=blocked\n"
    )
    if task_type == "rag_query_plan":
        return (
            f"{header}"
            "任务：RAG 查询计划。\n"
            "1. 查询：检索学校、年份、推免或导师主页，并过滤 policy/advisor_source。\n"
            "2. 证据：保留命中 chunk、URL、hash 和适用年份。\n"
            "3. 核验：将关键结论交给 EvidenceAudit，未核验不写入事实。"
            f"{_verified_scenario_instruction(task_type, shared['scenario'])}"
        )
    if task_type == "evidence_audit_fix":
        return (
            f"{header}"
            "任务：EvidenceAudit 修复。\n"
            "1. 审计：保留初始问题并执行必要的修复动作。\n"
            "2. 修复：重新检索官方原始页面并重新审计。\n"
            "3. 降级：找不到证据时设为 needs_review，不能编造或补写具体条件。"
            f"{_verified_scenario_instruction(task_type, shared['scenario'])}"
        )
    return (
        f"{header}"
        "任务：政策或导师答复。\n"
        "1. 可确认：该来源可定位公开政策或导师候选信息。\n"
        "2. 不可确认：截止日期、名额、招生资格和录取承诺不能由摘要推出。\n"
        "3. 下一步：以原始年度页面或用户确认补足后，再由 EvidenceAudit 审核。"
        f"{_verified_scenario_instruction(task_type, shared['scenario'])}"
    )


def _verified_scenario_instruction(task_type: str, scenario: str) -> str:
    if scenario == "summary_only":
        return (
            "\n场景约束：当前只保存摘要，必须打开原始页面核验；不能把摘要写成具体政策或导师事实。"
        )
    if scenario == "authority_boundary":
        return "\n场景约束：标明学校、学院、导师主页和转载页的 authority；低 authority 页面不能替代年度官方通知。"
    if scenario == "audit_repair":
        if task_type == "evidence_audit_fix":
            return "\n场景约束：先将缺少官方细节的 claim 降级为 needs_review，再补检索原始年度页面并重新审计。"
        return (
            "\n场景约束：缺少官方细节的 claim 先标记 needs_review，补到原始年度页面后再恢复结论。"
        )
    return "\n场景约束：核验来源的适用年份和招生范围，不能据此自动写入申请状态或材料。"


def _feedback_for_candidate(
    candidate: str,
    source: PublicKBSource,
    scenario: str,
) -> Dict[str, Any]:
    if candidate == "unsafe":
        return {
            "accepted": False,
            "citation_correct": False,
            "factuality_confirmed": False,
            "authority_score": 0.0,
            "expired_policy_used": scenario == "audit_repair",
            "private_safe": True,
        }
    if candidate == "partial":
        return {
            "accepted": False,
            "citation_correct": True,
            "factuality_confirmed": True,
            "authority_score": _authority_score(source.authority_level),
            "needs_user_confirmation": True,
            "evidence_conflict_open": True,
            "private_safe": True,
            "preference_negative": True,
        }
    return {
        "accepted": candidate == "verified",
        "citation_correct": True,
        "factuality_confirmed": True,
        "authority_score": _authority_score(source.authority_level),
        "needs_user_confirmation": candidate == "needs_review"
        or scenario in {"summary_only", "authority_boundary", "audit_repair"},
        "private_safe": True,
    }


def _prompt_for(
    record: PublicKBRecord,
    source: PublicKBSource,
    task_type: str,
    scenario: str,
) -> str:
    label = {
        "rag_query_plan": "制定 RAG 检索计划",
        "evidence_audit_fix": "修复 EvidenceAudit 问题",
        "policy_advisor_qa": "回答政策或导师画像问题",
    }[task_type]
    scenario_hint = {
        "official_source": "优先官方来源并保留证据链。",
        "summary_only": "来源只保存摘要，不能把摘要当作具体政策全文。",
        "authority_boundary": "必须区分学校、学院、导师主页和转载平台的 authority。",
        "audit_repair": "已有 claim 缺少官方细节证据，先修复再回答。",
    }[scenario]
    return (
        f"基于公开记录《{record.name}》{label}。"
        f"来源 publisher={source.publisher or 'unknown'}，authority={source.authority_level}。"
        f"{scenario_hint}"
    )


def _summary_index_text(record: PublicKBRecord, source: PublicKBSource) -> str:
    return (
        f"{record.name}\n{record.summary}\n"
        f"publisher: {source.publisher}\n"
        f"authority: {source.authority_level}\n"
        f"valid_for_year: {record.valid_for_year or 'unknown'}\n"
        "本条仅为公开来源摘要和定位信息，不能替代原始网页正文。"
    )


def _source_for_record(
    record: PublicKBRecord,
    source_by_id: Dict[str, PublicKBSource],
) -> PublicKBSource:
    for source_ref in record.source_refs:
        source = source_by_id.get(source_ref)
        if source:
            return source
    raise ValueError(f"Record {record.record_id} is missing a linked public source.")


def _public_record_ref(record: PublicKBRecord) -> str:
    return f"public_kb:{record.record_id}"


def _authority_score(authority: str) -> float:
    return {
        "university_official": 1.0,
        "graduate_school_official": 0.95,
        "college_official": 0.85,
        "advisor_official": 0.8,
        "admissions_platform": 0.6,
    }.get(authority, 0.4)


__all__ = [
    "CollectionResult",
    "SCENARIOS",
    "TASK_TYPES",
    "collect_public_agentic_rollouts",
]
