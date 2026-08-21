from __future__ import annotations

from typing import List, Optional

from models import (
    AdvisorProfile,
    AgentRun,
    MatchReport,
    StudentProfile,
    Target,
    WorkflowEvent,
    now_iso,
)
from pydantic import BaseModel, Field
from quality.checks import usable_list_profile_field
from services import make_match

from agents.base import compact_list
from agents.workflow_events import WorkflowEventRecorder


class MatchAnalysisResult(BaseModel):
    report: MatchReport
    agent_run: AgentRun
    events: List[WorkflowEvent] = Field(default_factory=list)


class MatchAnalysisAgent:
    name = "MatchAnalysisAgent"

    def analyze(
        self,
        profile: Optional[StudentProfile],
        target: Target,
        advisor: Optional[AdvisorProfile],
    ) -> MatchAnalysisResult:
        run = AgentRun(
            target_id=target.target_id,
            workflow="advisor_match.analysis",
            status="running",
            input_summary={
                "profile_id": profile.profile_id if profile else "",
                "target_id": target.target_id,
                "advisor_id": advisor.advisor_id if advisor else "",
                "profile_projects": compact_list(profile.projects if profile else []),
                "advisor_directions": compact_list(advisor.research_directions if advisor else []),
            },
        )
        recorder = WorkflowEventRecorder(run)
        recorder.record(
            "workflow_started",
            status="started",
            agent_name=self.name,
            payload={
                "profile_id": profile.profile_id if profile else "",
                "target_id": target.target_id,
                "advisor_id": advisor.advisor_id if advisor else "",
            },
        )
        recorder.record("match_started", status="started", agent_name=self.name)

        report = make_match(profile, target, advisor)
        if profile:
            report = enrich_match_report(report, profile, advisor)

        run.status = "completed"
        run.output_summary = {
            "match_id": report.match_id,
            "fit_score": report.fit_score,
            "tier": report.tier,
            "strength_count": len(report.strengths),
            "gap_count": len(report.gaps),
        }
        run.risk_tags = match_risk_tags(report, profile, advisor)
        run.ended_at = now_iso()
        recorder.record(
            "match_completed",
            agent_name=self.name,
            payload={
                "match_id": report.match_id,
                "fit_score": report.fit_score,
                "tier": report.tier,
                "risk_tags": run.risk_tags,
            },
        )
        return MatchAnalysisResult(report=report, agent_run=run, events=recorder.events)


def enrich_match_report(
    report: MatchReport,
    profile: StudentProfile,
    advisor: Optional[AdvisorProfile],
) -> MatchReport:
    profile_terms = (
        usable_list_profile_field(profile, "research_interests")
        + usable_list_profile_field(profile, "projects")
        + usable_list_profile_field(profile, "publications")
        + usable_list_profile_field(profile, "skills")
    )
    advisor_terms = advisor.research_directions if advisor else []
    overlaps = [
        term
        for term in advisor_terms
        if term and any(term in profile_term for profile_term in profile_terms)
    ]
    if overlaps and not report.strengths:
        report.strengths.append(
            {
                "dimension": "research_direction_overlap",
                "point": f"学生经历与导师方向存在交集：{'、'.join(overlaps)}",
                "student_evidence_ids": profile.source_document_ids or [profile.profile_id],
                "advisor_evidence_ids": advisor.source_ids if advisor else [],
            }
        )
    if advisor and not advisor.source_ids:
        report.gaps.append(
            {
                "dimension": "advisor_evidence",
                "point": "导师匹配结论缺少导师来源证据。",
                "severity": "high",
                "suggestion": "补充导师主页、实验室主页、招生通知或手动来源。",
            }
        )
    unconfirmed_fields = [
        field
        for field in ["research_interests", "projects", "publications", "skills"]
        if profile.confirmation_map.get(field, "unconfirmed") in {"unconfirmed", "needs_review"}
        and getattr(profile, field, None)
    ]
    if unconfirmed_fields:
        report.gaps.append(
            {
                "dimension": "student_confirmation",
                "point": f"匹配分析使用了未确认学生字段：{'、'.join(unconfirmed_fields)}",
                "severity": "medium",
                "suggestion": "先在学生画像页确认字段，再把匹配结论用于正式材料。",
            }
        )
    report.recommended_actions = list(
        dict.fromkeys(
            report.recommended_actions
            + [
                "复核匹配报告中的学生证据和导师来源证据",
                "把高匹配点转化为套磁邮件中的一条具体动机",
            ]
        )
    )
    return report


def match_risk_tags(
    report: MatchReport,
    profile: Optional[StudentProfile],
    advisor: Optional[AdvisorProfile],
) -> List[str]:
    tags = []
    if profile is None:
        tags.append("profile_missing")
    if advisor is None:
        tags.append("advisor_missing")
    elif not advisor.source_ids:
        tags.append("advisor_evidence_missing")
    if report.tier in {"weak_fit", "unknown"}:
        tags.append(f"match_{report.tier}")
    if any(gap.get("severity") == "high" for gap in report.gaps):
        tags.append("high_gap")
    return list(dict.fromkeys(tags))
