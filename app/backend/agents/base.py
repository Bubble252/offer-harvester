from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import (
    AdvisorProfile,
    AgentRun,
    GeneratedMaterial,
    MatchReport,
    MaterialQualityReport,
    MaterialVersion,
    StudentProfile,
    Target,
    now_iso,
)


def dump_model(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def compact_list(values: List[str], limit: int = 3) -> List[str]:
    return [value for value in values if value][:limit]


def make_agent_run(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
) -> AgentRun:
    return AgentRun(
        target_id=target.target_id,
        workflow="contact_email.drafter_reviewer_auditor",
        status="running",
        input_summary={
            "profile_id": profile.profile_id,
            "target_id": target.target_id,
            "advisor_id": advisor.advisor_id if advisor else "",
            "match_id": match.match_id if match else "",
            "profile_projects": compact_list(profile.projects),
            "advisor_directions": compact_list(advisor.research_directions if advisor else []),
        },
    )


def make_material_version(
    material: GeneratedMaterial,
    stage: str,
    source_run_id: str,
    notes: Optional[List[Dict[str, Any]]] = None,
) -> MaterialVersion:
    return MaterialVersion(
        material_id=material.material_id,
        target_id=material.target_id,
        material_type=material.material_type,
        stage=stage,
        content=material.content,
        source_run_id=source_run_id,
        notes=notes or [],
    )


def finish_agent_run(
    run: AgentRun,
    material: GeneratedMaterial,
    quality: MaterialQualityReport,
    review_passed: bool,
    audit_passed: bool,
    risk_tags: List[str],
) -> AgentRun:
    run.status = "completed"
    run.output_summary = {
        "material_id": material.material_id,
        "material_type": material.material_type,
        "quality_id": quality.quality_id,
        "quality_passed": quality.passed,
        "quality_risk_level": quality.risk_level,
        "review_passed": review_passed,
        "audit_passed": audit_passed,
    }
    run.risk_tags = list(dict.fromkeys(risk_tags))
    run.ended_at = now_iso()
    return run
