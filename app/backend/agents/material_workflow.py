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
)
from pydantic import BaseModel, Field
from services import audit_material

from agents.base import dump_model, finish_agent_run, make_agent_run, make_material_version
from agents.evidence_audit_agent import EvidenceAuditAgent, EvidenceAuditResult
from agents.material_draft_agent import MaterialDraftAgent
from agents.material_review_agent import MaterialReviewAgent, MaterialReviewResult


class MaterialWorkflowResult(BaseModel):
    material: GeneratedMaterial
    quality: MaterialQualityReport
    draft: GeneratedMaterial
    review: MaterialReviewResult
    evidence_audit: EvidenceAuditResult
    revision: GeneratedMaterial
    versions: List[MaterialVersion] = Field(default_factory=list)
    agent_run: AgentRun


def run_contact_email_workflow(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
) -> MaterialWorkflowResult:
    agent_run = make_agent_run(profile, target, advisor, match)
    draft = MaterialDraftAgent().draft_contact_email(profile, target, advisor, match)
    draft_version = make_material_version(draft, "draft", agent_run.run_id)

    review = MaterialReviewAgent().review_contact_email(draft, profile, advisor, match)
    audit = EvidenceAuditAgent().audit_contact_email(draft, profile, target, advisor, match)

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
    risk_tags = _risk_tags(review, audit, quality)
    agent_run = finish_agent_run(
        agent_run,
        revision,
        quality,
        review.passed,
        audit.passed,
        risk_tags,
    )

    return MaterialWorkflowResult(
        material=revision,
        quality=quality,
        draft=draft,
        review=review,
        evidence_audit=audit,
        revision=revision,
        versions=[draft_version, final_version],
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
