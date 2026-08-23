from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from models import AdvisorProfile, GeneratedMaterial, MatchReport, StudentProfile, Target
from pydantic import BaseModel, Field
from quality.checks import profile_confirmation_issues
from rag import KnowledgeBaseRetriever


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
        retriever: Optional[KnowledgeBaseRetriever] = None,
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
        self._check_profile_confirmations(
            material.content,
            profile,
            claims,
            unsupported,
            needs_confirmation,
        )
        self._check_policy_risks(
            material.content,
            target,
            advisor,
            retriever,
            claims,
            unsupported,
            needs_confirmation,
        )

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

    def _check_profile_confirmations(
        self,
        content: str,
        profile: StudentProfile,
        claims: List[Dict[str, Any]],
        unsupported: List[str],
        needs_confirmation: List[str],
    ) -> None:
        rejected_fields, confirmation_fields = profile_confirmation_issues(profile, content)
        if rejected_fields:
            message = f"材料使用了用户已否认字段：{'、'.join(rejected_fields)}"
            claims.append(
                {
                    "claim_type": "profile_field_confirmation",
                    "status": "unsupported",
                    "source_ids": [],
                    "message": message,
                }
            )
            unsupported.append(message)
        if confirmation_fields:
            message = f"材料使用了未确认学生字段，发送前需确认：{'、'.join(confirmation_fields)}"
            claims.append(
                {
                    "claim_type": "profile_field_confirmation",
                    "status": "needs_confirmation",
                    "source_ids": profile.source_document_ids,
                    "message": message,
                }
            )
            needs_confirmation.append(message)

    def _check_policy_risks(
        self,
        content: str,
        target: Target,
        advisor: Optional[AdvisorProfile],
        retriever: Optional[KnowledgeBaseRetriever],
        claims: List[Dict[str, Any]],
        unsupported: List[str],
        needs_confirmation: List[str],
    ) -> None:
        policy_terms = [
            "招生信息",
            "申请要求",
            "截止",
            "材料",
            "报名",
            "预推免",
            "夏令营",
            "九推",
            "系统",
            "通知",
        ]
        if not any(term in content for term in policy_terms):
            return
        if not retriever:
            message = "材料提到招生流程或截止日期，但当前没有接入可审计的政策检索。"
            claims.append(
                {
                    "claim_type": "policy_fact",
                    "status": "needs_confirmation",
                    "source_ids": [],
                    "message": message,
                }
            )
            needs_confirmation.append(message)
            return

        query_terms = [
            target.name,
            target.school,
            target.college,
            target.program_name,
            content[:240],
        ]
        if advisor:
            query_terms.extend(advisor.research_directions[:3])
            query_terms.extend(advisor.admission_requirements[:3])
        query = " ".join(
            item
            for item in [
                "招生信息",
                "申请要求",
                "截止日期",
                "材料",
                "报名",
                "预推免",
                "夏令营",
                "九推",
                "系统",
                "通知",
                *query_terms,
            ]
            if item
        )
        retrieval = retriever.search(
            query,
            source_kinds=["policy"],
            include_historical=True,
            as_of_year=current_year(),
            limit=3,
        )
        current_hits = [hit for hit in retrieval.hits if not getattr(hit, "historical", False)]
        if current_hits:
            claims.append(
                {
                    "claim_type": "policy_fact",
                    "status": "supported",
                    "source_ids": [hit.evidence_ref for hit in current_hits if hit.evidence_ref],
                    "message": "招生流程或截止日期已关联当前年份政策来源。",
                }
            )
            return
        if retrieval.hits:
            message = "材料引用的政策来源已过期，不能直接作为当前建议。"
            claims.append(
                {
                    "claim_type": "policy_fact",
                    "status": "unsupported",
                    "source_ids": [hit.evidence_ref for hit in retrieval.hits if hit.evidence_ref],
                    "message": message,
                }
            )
            unsupported.append(message)
            needs_confirmation.append("材料中的流程或截止日期需要换成当前年份来源。")
            return
        message = "材料提到招生流程或截止日期，但没有检索到当前年份政策来源。"
        claims.append(
            {
                "claim_type": "policy_fact",
                "status": "unsupported",
                "source_ids": [],
                "message": message,
            }
        )
        unsupported.append(message)


def current_year() -> int:
    return datetime.now().year
