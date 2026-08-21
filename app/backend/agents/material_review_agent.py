from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import AdvisorProfile, GeneratedMaterial, MatchReport, StudentProfile
from pydantic import BaseModel, Field


class MaterialReviewResult(BaseModel):
    reviewer: str = "MaterialReviewAgent"
    passed: bool
    risk_level: str = "low"
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    required_revisions: List[str] = Field(default_factory=list)
    optional_improvements: List[str] = Field(default_factory=list)


class MaterialReviewAgent:
    name = "MaterialReviewAgent"

    def review_contact_email(
        self,
        material: GeneratedMaterial,
        profile: StudentProfile,
        advisor: Optional[AdvisorProfile],
        match: Optional[MatchReport],
    ) -> MaterialReviewResult:
        issues: List[Dict[str, Any]] = []
        required: List[str] = []
        optional: List[str] = []

        prohibited = ["保证录取", "稳上", "必然录取", "百分之百", "一定录取"]
        found = [phrase for phrase in prohibited if phrase in material.content]
        if found:
            issues.append(
                {
                    "type": "overclaim",
                    "message": f"发现不稳妥录取承诺表达：{'、'.join(found)}",
                }
            )
            required.append("删除录取承诺或概率判断，只保留事实和申请意向。")

        advisor_directions = advisor.research_directions if advisor else []
        if advisor_directions and not any(
            direction in material.content for direction in advisor_directions
        ):
            issues.append(
                {
                    "type": "advisor_fit_too_generic",
                    "message": "邮件没有具体引用导师研究方向，容易显得模板化。",
                }
            )
            required.append("补充一个来自导师来源的具体研究方向，并说明学生经历的对应关系。")

        profile_anchors = profile.projects + profile.publications + profile.competitions
        if profile_anchors and not any(
            anchor and anchor in material.content for anchor in profile_anchors
        ):
            issues.append(
                {
                    "type": "missing_student_anchor",
                    "message": "邮件没有引用学生已记录的项目、论文或竞赛证据。",
                }
            )
            required.append("至少加入一条用户已确认的项目、论文或竞赛经历。")

        generic_phrases = ["很感兴趣", "深入学习", "进一步交流"]
        generic_hits = [phrase for phrase in generic_phrases if phrase in material.content]
        if len(generic_hits) >= 3 and not match:
            optional.append("当前表达偏通用；生成匹配报告后，可把套磁动机写得更具体。")

        if advisor and not advisor.source_ids:
            issues.append(
                {
                    "type": "missing_advisor_source",
                    "message": "导师画像缺少来源 ID，发送前需要人工复核导师方向和招生信息。",
                }
            )
            required.append("补充导师主页、实验室主页、招生通知或手动来源。")

        risk_level = "high" if len(required) >= 2 else "medium" if required else "low"
        return MaterialReviewResult(
            passed=not required,
            risk_level=risk_level,
            issues=issues,
            required_revisions=required,
            optional_improvements=optional,
        )
