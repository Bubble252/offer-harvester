"""Controlled execution adapters for standalone Offer Harvester Skills."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents import MatchAnalysisAgent, run_contact_email_workflow
from agents.base import dump_model
from agents.evidence_audit_agent import EvidenceAuditAgent
from agents.material_review_agent import MaterialReviewAgent
from agents.workflow_events import WorkflowEventRecorder
from models import (
    AdvisorProfile,
    AgentRun,
    GeneratedMaterial,
    MatchReport,
    StudentProfile,
    Target,
    WorkflowEvent,
    new_id,
    now_iso,
)
from pydantic import BaseModel, Field
from quality import audit_material
from quality.checks import PROFILE_FIELD_LABELS, profile_field_status, usable_list_profile_field
from skill_registry import get_skill_catalog_item

PRODUCT_SKILLS = {
    "contact-email-coach",
    "advisor-due-diligence",
    "recommendation-letter-helper",
}


class SkillExecutionRequest(BaseModel):
    target_id: str = ""
    advisor_id: str = ""
    mode: str = "new"
    recommender_name: str = ""
    relationship: str = ""
    notes: str = ""


class MaterialAuditRequest(BaseModel):
    material_id: str


class SkillExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: new_id("skillrun"))
    skill_id: str
    status: str = "candidate"
    candidate_status: str = "candidate"
    requires_user_confirmation: bool = True
    no_send: bool = True
    truth_source_refs: List[str] = Field(default_factory=list)
    derived_view_refs: List[str] = Field(default_factory=list)
    risk_tags: List[str] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)
    output: Dict[str, Any] = Field(default_factory=dict)
    agent_run: Optional[AgentRun] = None
    events: List[WorkflowEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


def execute_product_skill(
    skill_id: str,
    request: SkillExecutionRequest,
    *,
    workspace,
    profile: Optional[StudentProfile],
    target: Optional[Target],
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
    retriever=None,
) -> SkillExecutionResult:
    item = get_skill_catalog_item(skill_id)
    if item.get("category") != "product" or skill_id not in PRODUCT_SKILLS:
        raise ValueError(f"Skill is not an executable product skill: {skill_id}")
    if skill_id == "contact-email-coach":
        result = _run_contact_email(
            request,
            workspace=workspace,
            profile=profile,
            target=target,
            advisor=advisor,
            match=match,
            retriever=retriever,
        )
    elif skill_id == "advisor-due-diligence":
        result = _run_advisor_due_diligence(
            request,
            profile=profile,
            target=target,
            advisor=advisor,
            retriever=retriever,
        )
    else:
        result = _run_recommendation_helper(
            request,
            profile=profile,
            target=target,
            advisor=advisor,
            retriever=retriever,
        )
    workspace.write("skill_executions", dump_model(result), "execution_id")
    if result.agent_run:
        workspace.write("agent_runs", dump_model(result.agent_run), "run_id")
    for event in result.events:
        workspace.write("workflow_events", dump_model(event), "event_id")
    return result


def execute_material_audit(
    request: MaterialAuditRequest,
    *,
    workspace,
    profile: Optional[StudentProfile],
    retriever=None,
) -> SkillExecutionResult:
    """Audit an existing material without changing the material or tracker state."""

    item = workspace.read("generated", request.material_id)
    if not item:
        raise ValueError("Generated material not found")
    if not profile:
        return SkillExecutionResult(
            skill_id="evidence-claim-audit",
            status="blocked",
            candidate_status="blocked",
            blocked_reasons=["A student profile is required"],
        )

    material = GeneratedMaterial(**item)
    target_item = workspace.read("targets", material.target_id)
    target = Target(**target_item) if target_item else None
    advisor = None
    if target and target.advisor_id:
        advisor_item = workspace.read("advisors", target.advisor_id)
        advisor = AdvisorProfile(**advisor_item) if advisor_item else None

    run = AgentRun(
        target_id=material.target_id,
        workflow="skill.evidence_claim_audit",
        status="running",
        input_summary={
            "material_id": material.material_id,
            "material_type": material.material_type,
        },
    )
    recorder = WorkflowEventRecorder(run)
    recorder.record("workflow_started", status="started", agent_name="EvidenceClaimAuditSkill")
    review = MaterialReviewAgent().review_contact_email(
        material, profile, advisor, None, retriever=retriever
    )
    recorder.record(
        "review_completed",
        agent_name="MaterialReviewAgent",
        payload={"passed": review.passed},
    )
    audit = EvidenceAuditAgent().audit_contact_email(
        material, profile, target, advisor, None, retriever=retriever
    )
    recorder.record(
        "audit_completed",
        agent_name="EvidenceAuditAgent",
        payload={"passed": audit.passed, "unsupported_claim_count": len(audit.unsupported_claims)},
    )
    quality = audit_material(material, profile, advisor)
    recorder.record(
        "quality_completed",
        agent_name="MaterialQualityAudit",
        payload={"passed": quality.passed, "risk_level": quality.risk_level},
    )
    risk_tags = []
    if not review.passed:
        risk_tags.append("review_required")
    if not audit.passed:
        risk_tags.append("evidence_required")
    if not quality.passed:
        risk_tags.append(f"quality_{quality.risk_level}")
    run.status = "completed"
    run.output_summary = {
        "material_id": material.material_id,
        "review_passed": review.passed,
        "audit_passed": audit.passed,
        "quality_passed": quality.passed,
    }
    run.risk_tags = risk_tags
    run.ended_at = now_iso()
    recorder.record(
        "final_saved",
        agent_name="EvidenceClaimAuditSkill",
        payload={"candidate_only": True, "material_mutated": False, "no_send": True},
    )
    result = SkillExecutionResult(
        skill_id="evidence-claim-audit",
        candidate_status="needs_review" if risk_tags or audit.needs_confirmation else "candidate",
        truth_source_refs=list(dict.fromkeys(material.evidence)),
        derived_view_refs=[material.material_id, quality.quality_id, run.run_id],
        risk_tags=risk_tags,
        blocked_reasons=list(dict.fromkeys(audit.unsupported_claims)),
        output={
            "material": dump_model(material),
            "review": dump_model(review),
            "evidence_audit": dump_model(audit),
            "quality": dump_model(quality),
            "mutation_policy": "Audit output is candidate-only and never changes the source material.",
        },
        agent_run=run,
        events=recorder.events,
    )
    workspace.write("skill_executions", dump_model(result), "execution_id")
    workspace.write("agent_runs", dump_model(run), "run_id")
    for event in recorder.events:
        workspace.write("workflow_events", dump_model(event), "event_id")
    return result


def _run_contact_email(
    request: SkillExecutionRequest,
    *,
    workspace,
    profile: Optional[StudentProfile],
    target: Optional[Target],
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
    retriever,
) -> SkillExecutionResult:
    blocked = _require(profile, target)
    if blocked:
        return SkillExecutionResult(
            skill_id="contact-email-coach",
            status="blocked",
            candidate_status="blocked",
            blocked_reasons=blocked,
        )
    workflow = run_contact_email_workflow(
        profile,
        target,
        advisor,
        match,
        retriever=retriever,
        workspace=workspace,
    )
    risk_tags = list(dict.fromkeys(workflow.agent_run.risk_tags + _mode_risk_tags(request.mode)))
    return SkillExecutionResult(
        skill_id="contact-email-coach",
        candidate_status="needs_review" if risk_tags else "candidate",
        truth_source_refs=list(dict.fromkeys(workflow.material.evidence)),
        derived_view_refs=[
            workflow.material.material_id,
            workflow.quality.quality_id,
            workflow.agent_run.run_id,
        ],
        risk_tags=risk_tags,
        output={
            "mode": _supported_contact_mode(request.mode),
            "material": dump_model(workflow.material),
            "review": dump_model(workflow.review),
            "evidence_audit": dump_model(workflow.evidence_audit),
            "quality": dump_model(workflow.quality),
        },
        agent_run=workflow.agent_run,
        events=workflow.events,
    )


def _run_advisor_due_diligence(
    request: SkillExecutionRequest,
    *,
    profile: Optional[StudentProfile],
    target: Optional[Target],
    advisor: Optional[AdvisorProfile],
    retriever,
) -> SkillExecutionResult:
    if not advisor:
        return SkillExecutionResult(
            skill_id="advisor-due-diligence",
            status="blocked",
            candidate_status="blocked",
            blocked_reasons=["advisor_id is required"],
        )
    run = AgentRun(
        target_id=target.target_id if target else advisor.advisor_id,
        workflow="skill.advisor_due_diligence",
        status="running",
        input_summary={
            "advisor_id": advisor.advisor_id,
            "target_id": target.target_id if target else "",
            "profile_id": profile.profile_id if profile else "",
        },
    )
    recorder = WorkflowEventRecorder(run)
    recorder.record("workflow_started", status="started", agent_name="AdvisorDueDiligenceSkill")
    evidence_refs = list(dict.fromkeys(advisor.source_ids + (target.source_ids if target else [])))
    gaps: List[str] = []
    if not advisor.identity_confirmed:
        gaps.append("导师身份尚未由来源充分确认。")
    if not advisor.source_ids:
        gaps.append("导师画像缺少可追溯来源。")
    if not advisor.research_directions:
        gaps.append("研究方向缺失，不能给出可靠匹配判断。")
    retrieval_summary: Dict[str, Any] = {}
    if retriever:
        query = " ".join(
            item
            for item in [
                advisor.name_zh,
                advisor.name_en,
                advisor.school,
                advisor.college,
                *advisor.research_directions[:4],
            ]
            if item
        )
        if query:
            retrieval = retriever.search(
                query,
                source_kinds=["advisor_source", "policy"],
                limit=5,
                profile=profile,
            )
            evidence_refs.extend(
                hit.evidence_ref for hit in retrieval.hits if getattr(hit, "evidence_ref", "")
            )
            retrieval_summary = {
                "query": query,
                "hit_count": len(retrieval.hits),
                "evidence_bundle_id": retrieval.evidence_bundle.bundle_id,
            }
            recorder.record(
                "retrieval_completed",
                agent_name="KnowledgeBaseRetriever",
                payload=retrieval_summary,
            )
    match_summary = None
    if profile and target:
        match_result = MatchAnalysisAgent().analyze(profile, target, advisor, retriever=retriever)
        match_summary = dump_model(match_result.report)
        evidence_refs.append(match_result.report.match_id)
    risk_tags = list(dict.fromkeys(advisor.risk_notes))
    if gaps:
        risk_tags.append("evidence_gap")
    report = {
        "advisor_id": advisor.advisor_id,
        "identity_confirmed": advisor.identity_confirmed,
        "research_directions": advisor.research_directions,
        "recruiting_status": advisor.recruiting_status,
        "official_source_refs": advisor.source_ids,
        "evidence_map": advisor.evidence_map,
        "gaps": gaps,
        "review_questions": _advisor_questions(advisor, gaps),
        "risk_signal_policy": "Community content is a reviewable risk signal, not a confirmed fact.",
        "retrieval": retrieval_summary,
        "match": match_summary,
    }
    run.status = "completed"
    run.output_summary = {
        "advisor_id": advisor.advisor_id,
        "source_count": len(advisor.source_ids),
        "gap_count": len(gaps),
        "risk_count": len(risk_tags),
    }
    run.risk_tags = risk_tags
    run.ended_at = now_iso()
    recorder.record(
        "audit_completed",
        agent_name="AdvisorDueDiligenceSkill",
        payload={"gap_count": len(gaps), "risk_tags": risk_tags},
    )
    recorder.record(
        "final_saved",
        agent_name="AdvisorDueDiligenceSkill",
        payload={"candidate_only": True, "no_send": True},
    )
    return SkillExecutionResult(
        skill_id="advisor-due-diligence",
        candidate_status="needs_review" if gaps or risk_tags else "candidate",
        truth_source_refs=list(dict.fromkeys(evidence_refs)),
        derived_view_refs=[run.run_id],
        risk_tags=risk_tags,
        blocked_reasons=gaps,
        output=report,
        agent_run=run,
        events=recorder.events,
    )


def _run_recommendation_helper(
    request: SkillExecutionRequest,
    *,
    profile: Optional[StudentProfile],
    target: Optional[Target],
    advisor: Optional[AdvisorProfile],
    retriever,
) -> SkillExecutionResult:
    if not profile:
        return SkillExecutionResult(
            skill_id="recommendation-letter-helper",
            status="blocked",
            candidate_status="blocked",
            blocked_reasons=["A student profile is required"],
        )
    review_target = target or Target(
        target_id="recommendation_candidate",
        name="Graduate application recommendation",
        contact_required=False,
    )
    run = AgentRun(
        target_id=review_target.target_id,
        workflow="skill.recommendation_letter_helper",
        status="running",
        input_summary={
            "profile_id": profile.profile_id,
            "target_id": review_target.target_id,
            "advisor_id": advisor.advisor_id if advisor else "",
        },
    )
    recorder = WorkflowEventRecorder(run)
    recorder.record(
        "workflow_started",
        status="started",
        agent_name="RecommendationLetterHelperSkill",
    )
    evidence = [profile.profile_id] + _profile_evidence_refs(profile)
    achievements, flags = _profile_achievements(profile)
    recommender = request.recommender_name.strip() or "推荐人"
    relationship = request.relationship.strip() or "请补充与学生的关系"
    target_name = review_target.name
    highlight_lines = [f"- {item}" for item in achievements] or [
        "- 暂无可用亮点，请补充已确认资料。"
    ]
    content = "\n".join(
        [
            "# 推荐信素材包（候选）",
            "",
            f"- 推荐人：{recommender}",
            f"- 关系：{relationship}",
            f"- 申请目标：{target_name}",
            "",
            "## 可核验亮点",
            *highlight_lines,
            "",
            "## 给推荐人的请求说明",
            f"老师您好，我正在申请 {target_name}。附件素材仅供您核对和选择，请以您亲自了解的事实为准。",
            "",
            "## 推荐人视角参考草稿",
            "以下内容仅供推荐人参考、修改和确认，不能冒充推荐人提交。",
            "我了解该学生在相关学习和项目中的投入。建议结合上述可核验材料，由推荐人补充亲自观察到的能力与表现。",
        ]
    )
    material = GeneratedMaterial(
        target_id=review_target.target_id,
        material_type="recommendation_packet",
        title="推荐信请求与素材包（候选）",
        content=content,
        evidence=list(dict.fromkeys(evidence + (advisor.source_ids if advisor else []))),
    )
    recorder.record(
        "draft_completed",
        agent_name="RecommendationLetterHelperSkill",
        payload={"candidate_only": True, "material_id": material.material_id},
    )
    review = MaterialReviewAgent().review_contact_email(
        material, profile, advisor, None, retriever=retriever
    )
    recorder.record(
        "review_completed",
        agent_name="MaterialReviewAgent",
        payload={"passed": review.passed},
    )
    audit = EvidenceAuditAgent().audit_contact_email(
        material, profile, review_target, advisor, None, retriever=retriever
    )
    recorder.record(
        "audit_completed",
        agent_name="EvidenceAuditAgent",
        payload={"passed": audit.passed, "unsupported_claim_count": len(audit.unsupported_claims)},
    )
    quality = audit_material(material, profile, advisor)
    recorder.record(
        "quality_completed",
        agent_name="MaterialQualityAudit",
        payload={"passed": quality.passed, "risk_level": quality.risk_level},
    )
    risk_tags = list(dict.fromkeys(flags + (["review_required"] if not review.passed else [])))
    if not audit.passed:
        risk_tags.append("evidence_required")
    run.status = "completed"
    run.output_summary = {
        "material_id": material.material_id,
        "review_passed": review.passed,
        "audit_passed": audit.passed,
        "quality_passed": quality.passed,
    }
    run.risk_tags = risk_tags
    run.ended_at = now_iso()
    recorder.record(
        "final_saved",
        agent_name="RecommendationLetterHelperSkill",
        payload={"candidate_only": True, "no_send": True},
    )
    return SkillExecutionResult(
        skill_id="recommendation-letter-helper",
        candidate_status="needs_review" if risk_tags or audit.needs_confirmation else "candidate",
        truth_source_refs=material.evidence,
        derived_view_refs=[material.material_id, quality.quality_id, run.run_id],
        risk_tags=risk_tags,
        blocked_reasons=list(dict.fromkeys(audit.unsupported_claims)),
        output={
            "mode": request.mode or "request_and_packet",
            "material": dump_model(material),
            "review": dump_model(review),
            "evidence_audit": dump_model(audit),
            "quality": dump_model(quality),
            "reference_only_notice": "The recommender must review, rewrite, approve, and submit any letter.",
        },
        agent_run=run,
        events=recorder.events,
    )


def _require(profile: Optional[StudentProfile], target: Optional[Target]) -> List[str]:
    reasons = []
    if not profile:
        reasons.append("A student profile is required")
    if not target:
        reasons.append("target_id is required")
    return reasons


def _supported_contact_mode(mode: str) -> str:
    allowed = {"new", "rewrite", "advisor_alignment", "reduce_exaggeration", "follow_up"}
    return mode if mode in allowed else "new"


def _mode_risk_tags(mode: str) -> List[str]:
    return ["mode_normalized"] if mode and mode != _supported_contact_mode(mode) else []


def _advisor_questions(advisor: AdvisorProfile, gaps: List[str]) -> List[str]:
    questions = list(gaps)
    if advisor.recruiting_status == "unknown":
        questions.append("当前是否招收对应学位类型的学生？")
    if not advisor.admission_requirements:
        questions.append("是否有可核验的招生要求、材料偏好或截止日期？")
    if not advisor.source_ids:
        questions.append("请补充学校主页、实验室主页或招生通知来源。")
    return list(dict.fromkeys(questions))


def _profile_evidence_refs(profile: StudentProfile) -> List[str]:
    return list(
        dict.fromkeys(ref for refs in profile.evidence_map.values() for ref in refs)
    ) or list(profile.source_document_ids)


def _profile_achievements(profile: StudentProfile) -> tuple[List[str], List[str]]:
    achievements: List[str] = []
    flags: List[str] = []
    for field in ("projects", "publications", "competitions", "research_interests", "skills"):
        status = profile_field_status(profile, field)
        label = PROFILE_FIELD_LABELS.get(field, field)
        if status == "rejected":
            continue
        values = usable_list_profile_field(profile, field)
        achievements.extend(f"{label}：{value}" for value in values[:3])
        if values and status != "confirmed":
            flags.append(f"unconfirmed_{field}")
    return achievements, flags
