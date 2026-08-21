from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import AdvisorProfile, GeneratedMaterial, MatchReport, StudentProfile, Target
from pydantic import BaseModel, Field


class EvidenceAuditResult(BaseModel):
    auditor: str = "EvidenceAuditAgent"
    passed: bool
    claims: List[Dict[str, Any]] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    needs_confirmation: List[str] = Field(default_factory=list)


class EvidenceAuditAgent:
    name = "EvidenceAuditAgent"

    def audit_contact_email(
        self,
        material: GeneratedMaterial,
        profile: StudentProfile,
        target: Target,
        advisor: Optional[AdvisorProfile],
        match: Optional[MatchReport],
    ) -> EvidenceAuditResult:
        claims: List[Dict[str, Any]] = []
        unsupported: List[str] = []
        needs_confirmation: List[str] = []

        evidence = set(material.evidence)
        self._check_required_evidence(
            "student_profile",
            profile.profile_id,
            "学生事实需要关联已确认学生画像。",
            evidence,
            claims,
            unsupported,
        )
        self._check_required_evidence(
            "target",
            target.target_id,
            "申请目标需要关联目标记录。",
            evidence,
            claims,
            unsupported,
        )
        if advisor and advisor.source_ids:
            has_advisor_source = bool(evidence.intersection(advisor.source_ids))
            claims.append(
                {
                    "claim_type": "advisor_fact",
                    "status": "supported" if has_advisor_source else "unsupported",
                    "source_ids": sorted(evidence.intersection(advisor.source_ids)),
                    "message": "导师方向或招生信息已关联来源。"
                    if has_advisor_source
                    else "导师相关事实缺少来源 ID。",
                }
            )
            if not has_advisor_source:
                unsupported.append("导师相关事实缺少来源 ID。")
        elif advisor:
            needs_confirmation.append("导师画像没有来源 ID，导师相关表述需要人工确认。")

        if match:
            has_match = match.match_id in evidence
            claims.append(
                {
                    "claim_type": "match_interpretation",
                    "status": "supported" if has_match else "needs_confirmation",
                    "source_ids": [match.match_id] if has_match else [],
                    "message": "匹配解释已关联匹配报告。"
                    if has_match
                    else "匹配解释未关联匹配报告。",
                }
            )
            if not has_match:
                needs_confirmation.append("匹配解释未关联匹配报告。")

        self._scan_text_risks(material.content, profile, advisor, claims, unsupported)

        return EvidenceAuditResult(
            passed=not unsupported,
            claims=claims,
            unsupported_claims=unsupported,
            needs_confirmation=needs_confirmation,
        )

    def _check_required_evidence(
        self,
        claim_type: str,
        source_id: str,
        message: str,
        evidence: set,
        claims: List[Dict[str, Any]],
        unsupported: List[str],
    ) -> None:
        supported = source_id in evidence
        claims.append(
            {
                "claim_type": claim_type,
                "status": "supported" if supported else "unsupported",
                "source_ids": [source_id] if supported else [],
                "message": message if not supported else "已关联必要来源。",
            }
        )
        if not supported:
            unsupported.append(message)

    def _scan_text_risks(
        self,
        content: str,
        profile: StudentProfile,
        advisor: Optional[AdvisorProfile],
        claims: List[Dict[str, Any]],
        unsupported: List[str],
    ) -> None:
        if any(token in content for token in ["GPA", "绩点", "排名"]):
            source_ids = list(
                dict.fromkeys(
                    profile.evidence_map.get("gpa", []) + profile.evidence_map.get("rank", [])
                )
            )
            has_grade_source = bool(source_ids) or bool(
                profile.gpa
                or profile.rank
                or "GPA" in profile.raw_text
                or "排名" in profile.raw_text
            )
            claims.append(
                {
                    "claim_type": "grade_or_rank",
                    "status": "supported" if has_grade_source else "unsupported",
                    "source_ids": source_ids or ([profile.profile_id] if has_grade_source else []),
                    "message": "成绩或排名表述已关联字段级来源。"
                    if source_ids
                    else (
                        "成绩或排名表述已在学生画像中出现。"
                        if has_grade_source
                        else "成绩或排名表述缺少学生画像证据。"
                    ),
                }
            )
            if not has_grade_source:
                unsupported.append("成绩或排名表述缺少学生画像证据。")

        if advisor and advisor.research_directions:
            mentioned = [
                direction for direction in advisor.research_directions if direction in content
            ]
            claims.append(
                {
                    "claim_type": "advisor_direction",
                    "status": "supported" if mentioned else "too_broad",
                    "source_ids": advisor.source_ids if mentioned else [],
                    "message": f"已引用导师方向：{'、'.join(mentioned)}"
                    if mentioned
                    else "导师方向表述过泛。",
                }
            )
