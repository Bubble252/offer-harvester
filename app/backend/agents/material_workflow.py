from __future__ import annotations

from typing import List, Optional

from models import (
    AdvisorProfile,
    AgentRun,
    GeneratedMaterial,
    MatchReport,
    MaterialQualityReport,
    MaterialVersion,
    StudentProfile,
    Target,
    WorkflowEvent,
)
from pydantic import BaseModel, Field
from quality import audit_material
from rag import KnowledgeBaseRetriever, evidence_refs

from agents.base import dump_model, finish_agent_run, make_agent_run, make_material_version
from agents.evidence_audit_agent import EvidenceAuditAgent, EvidenceAuditResult
from agents.material_draft_agent import MaterialDraftAgent
from agents.material_review_agent import MaterialReviewAgent, MaterialReviewResult
from agents.workflow_events import WorkflowEventRecorder


class MaterialWorkflowResult(BaseModel):
    material: GeneratedMaterial
    quality: MaterialQualityReport
    draft: GeneratedMaterial
    review: MaterialReviewResult
    evidence_audit: EvidenceAuditResult
    revision: GeneratedMaterial
    versions: List[MaterialVersion] = Field(default_factory=list)
    events: List[WorkflowEvent] = Field(default_factory=list)
    agent_run: AgentRun


def run_contact_email_workflow(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
    retriever: Optional[KnowledgeBaseRetriever] = None,
) -> MaterialWorkflowResult:
    agent_run = make_agent_run(profile, target, advisor, match)
    recorder = WorkflowEventRecorder(agent_run)
    recorder.record(
        "workflow_started",
        status="started",
        payload={
            "profile_id": profile.profile_id,
            "target_id": target.target_id,
            "advisor_id": advisor.advisor_id if advisor else "",
            "match_id": match.match_id if match else "",
        },
    )

    draft_agent = MaterialDraftAgent()
    recorder.record("draft_started", status="started", agent_name=draft_agent.name)
    draft = draft_agent.draft_contact_email(profile, target, advisor, match)
    retrieval_hits = []
    if retriever:
        query = _contact_email_retrieval_query(profile, target, advisor)
        retrieval = retriever.search(query, limit=6, profile=profile)
        retrieval_hits = retrieval.hits
        draft.evidence = list(dict.fromkeys(draft.evidence + evidence_refs(retrieval_hits)))
        recorder.record(
            "retrieval_completed",
            agent_name="KnowledgeBaseRetriever",
            payload={
                "query": query,
                "hit_count": len(retrieval_hits),
                "evidence_refs": evidence_refs(retrieval_hits),
                "rebuilt": retrieval.rebuilt,
            },
        )
    draft_version = make_material_version(draft, "draft", agent_run.run_id)
    recorder.record(
        "draft_completed",
        agent_name=draft_agent.name,
        payload={
            "material_id": draft.material_id,
            "material_type": draft.material_type,
            "title": draft.title,
            "evidence_count": len(draft.evidence),
            "version_id": draft_version.version_id,
        },
    )

    review_agent = MaterialReviewAgent()
    recorder.record("review_started", status="started", agent_name=review_agent.name)
    review = review_agent.review_contact_email(
        draft,
        profile,
        advisor,
        match,
        retriever=retriever,
    )
    recorder.record(
        "review_completed",
        agent_name=review_agent.name,
        payload={
            "passed": review.passed,
            "risk_level": review.risk_level,
            "issue_count": len(review.issues),
            "required_revision_count": len(review.required_revisions),
        },
    )

    audit_agent = EvidenceAuditAgent()
    recorder.record("audit_started", status="started", agent_name=audit_agent.name)
    audit = audit_agent.audit_contact_email(
        draft,
        profile,
        target,
        advisor,
        match,
        retriever=retriever,
    )
    recorder.record(
        "audit_completed",
        agent_name=audit_agent.name,
        payload={
            "passed": audit.passed,
            "claim_count": len(audit.claims),
            "unsupported_count": len(audit.unsupported_claims),
            "needs_confirmation_count": len(audit.needs_confirmation),
        },
    )

    revision = GeneratedMaterial(**dump_model(draft))
    final_version = make_material_version(
        revision,
        "final",
        agent_run.run_id,
        notes=[
            {"stage": "review", "passed": review.passed, "risk_level": review.risk_level},
            {"stage": "evidence_audit", "passed": audit.passed},
        ],
    )
    quality = audit_material(revision, profile, advisor)
    recorder.record(
        "quality_completed",
        payload={
            "quality_id": quality.quality_id,
            "passed": quality.passed,
            "risk_level": quality.risk_level,
            "check_count": len(quality.checks),
        },
    )
    risk_tags = _risk_tags(review, audit, quality)
    agent_run = finish_agent_run(
        agent_run,
        revision,
        quality,
        review.passed,
        audit.passed,
        risk_tags,
    )
    recorder.record(
        "final_saved",
        payload={
            "material_id": revision.material_id,
            "quality_id": quality.quality_id,
            "final_version_id": final_version.version_id,
            "risk_tags": agent_run.risk_tags,
        },
    )

    return MaterialWorkflowResult(
        material=revision,
        quality=quality,
        draft=draft,
        review=review,
        evidence_audit=audit,
        revision=revision,
        versions=[draft_version, final_version],
        events=recorder.events,
        agent_run=agent_run,
    )


def _risk_tags(
    review: MaterialReviewResult,
    audit: EvidenceAuditResult,
    quality: MaterialQualityReport,
) -> List[str]:
    tags: List[str] = []
    if not review.passed:
        tags.append("review_required")
    if not audit.passed:
        tags.append("evidence_required")
    if not quality.passed:
        tags.append("quality_required")
    if quality.risk_level != "low":
        tags.append(f"risk_{quality.risk_level}")
    return tags


def _contact_email_retrieval_query(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
) -> str:
    terms = [target.name, target.school, target.college, target.program_name]
    if advisor:
        terms.extend(advisor.research_directions[:4])
        terms.extend(advisor.admission_requirements[:3])
    terms.extend(profile.research_interests[:4])
    terms.extend(profile.projects[:2])
    return " ".join(item for item in terms if item)
