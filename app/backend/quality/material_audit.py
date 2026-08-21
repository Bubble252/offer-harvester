from __future__ import annotations

from typing import Optional

from models import AdvisorProfile, GeneratedMaterial, MaterialQualityReport, StudentProfile

from quality.base import make_check
from quality.checks import (
    profile_confirmation_issues,
    usable_list_profile_field,
)

PROHIBITED_ADMISSION_CLAIMS = [
    "保证录取",
    "稳上",
    "必然录取",
    "百分之百",
    "一定录取",
    "一定适合",
]

GENERIC_MOTIVATION_PHRASES = ["很感兴趣", "深入学习", "进一步交流", "希望咨询"]


def audit_material(
    material: GeneratedMaterial,
    profile: StudentProfile,
    advisor: Optional[AdvisorProfile],
) -> MaterialQualityReport:
    """Run evidence-oriented checks before material is treated as reviewed."""

    checks = [
        check_evidence_present(material),
        check_advisor_source_present(material, advisor),
        check_no_admission_claim(material),
        check_student_fact_anchor(material, profile),
        check_profile_confirmations(material, profile),
        check_student_fact_consistency(material, profile),
        check_advisor_direction_match(material, advisor),
        check_template_specificity(material, profile, advisor),
        check_ppt_readability(material),
        check_interview_explainability(material, profile),
    ]
    failed_count = len([item for item in checks if not item["passed"]])
    risk_level = "high" if failed_count >= 2 else "medium" if failed_count else "low"
    return MaterialQualityReport(
        material_id=material.material_id,
        target_id=material.target_id,
        passed=failed_count == 0,
        checks=checks,
        risk_level=risk_level,
    )


def check_evidence_present(material: GeneratedMaterial) -> dict:
    return make_check(
        "evidence_present",
        bool(material.evidence),
        "材料已关联证据。" if material.evidence else "材料缺少可追溯证据。",
    )


def check_advisor_source_present(
    material: GeneratedMaterial, advisor: Optional[AdvisorProfile]
) -> dict:
    advisor_sources = advisor.source_ids if advisor else []
    passed = not advisor_sources or any(item in advisor_sources for item in material.evidence)
    return make_check(
        "advisor_source_present",
        passed,
        "导师相关内容已关联来源。"
        if advisor_sources and passed
        else "导师资料不足，需人工核对方向表述。"
        if not advisor_sources
        else "导师相关内容缺少来源 ID。",
    )


def check_no_admission_claim(material: GeneratedMaterial) -> dict:
    found = [phrase for phrase in PROHIBITED_ADMISSION_CLAIMS if phrase in material.content]
    return make_check(
        "no_admission_claim",
        not found,
        "未发现录取承诺。" if not found else f"发现高风险表达：{'、'.join(found)}",
    )


def check_student_fact_anchor(material: GeneratedMaterial, profile: StudentProfile) -> dict:
    profile_terms = student_anchor_terms(profile)
    passed = not profile_terms or any(term and term in material.content for term in profile_terms)
    return make_check(
        "student_fact_anchor",
        passed,
        "材料引用了学生已记录经历。"
        if passed and profile_terms
        else "学生经历较少，建议人工核对材料。"
        if not profile_terms
        else "材料没有引用学生已记录经历。",
    )


def check_profile_confirmations(material: GeneratedMaterial, profile: StudentProfile) -> dict:
    rejected_fields, confirmation_fields = profile_confirmation_issues(profile, material.content)
    passed = not rejected_fields
    message_parts = []
    if rejected_fields:
        message_parts.append(f"材料使用了用户已否认字段：{'、'.join(rejected_fields)}")
    if confirmation_fields:
        message_parts.append(
            f"材料使用了未确认学生字段，发送前需确认：{'、'.join(confirmation_fields)}"
        )
    return make_check(
        "profile_field_confirmation",
        passed,
        "；".join(message_parts) if message_parts else "未使用未确认或已否认学生字段。",
        rejected_fields=rejected_fields,
        needs_confirmation=confirmation_fields,
    )


def check_student_fact_consistency(material: GeneratedMaterial, profile: StudentProfile) -> dict:
    issues = []
    content = material.content
    if any(token in content for token in ["GPA", "绩点", "排名", "前 10%", "前10%"]):
        if not (usable_list_or_scalar(profile.gpa) or usable_list_or_scalar(profile.rank)):
            issues.append("成绩或排名表述缺少学生画像字段。")
    if any(token in content for token in ["发表", "投稿", "论文成果", "我的论文"]):
        if not usable_list_profile_field(profile, "publications"):
            issues.append("论文成果表述缺少学生画像字段。")
    if any(token in content for token in ["竞赛", "奖项", "获奖"]):
        if not usable_list_profile_field(profile, "competitions"):
            issues.append("竞赛奖项表述缺少学生画像字段。")
    return make_check(
        "student_fact_consistency",
        not issues,
        "学生事实表述与画像一致。" if not issues else "；".join(issues),
        issues=issues,
    )


def check_advisor_direction_match(
    material: GeneratedMaterial, advisor: Optional[AdvisorProfile]
) -> dict:
    directions = advisor.research_directions if advisor else []
    if not directions:
        return make_check(
            "advisor_direction_match",
            True,
            "导师方向不足，暂不做方向匹配强约束。",
        )
    mentioned = [
        direction for direction in directions if direction and direction in material.content
    ]
    return make_check(
        "advisor_direction_match",
        bool(mentioned),
        f"材料引用了导师方向：{'、'.join(mentioned)}"
        if mentioned
        else "材料没有引用具体导师方向。",
        mentioned_directions=mentioned,
    )


def check_template_specificity(
    material: GeneratedMaterial,
    profile: StudentProfile,
    advisor: Optional[AdvisorProfile],
) -> dict:
    generic_hits = [phrase for phrase in GENERIC_MOTIVATION_PHRASES if phrase in material.content]
    has_student_anchor = any(
        term and term in material.content for term in student_anchor_terms(profile)
    )
    directions = advisor.research_directions if advisor else []
    has_advisor_anchor = not directions or any(
        direction and direction in material.content for direction in directions
    )
    passed = len(generic_hits) < 3 or (has_student_anchor and has_advisor_anchor)
    return make_check(
        "template_specificity",
        passed,
        "材料包含学生经历和导师方向，模板化风险可控。"
        if passed
        else "材料偏通用，缺少学生经历或导师方向锚点。",
        generic_hits=generic_hits,
    )


def check_ppt_readability(material: GeneratedMaterial) -> dict:
    if material.material_type != "ppt_outline":
        return make_check("ppt_readability", True, "非 PPT 材料，跳过 PPT 可读性检查。")
    headings = [line for line in material.content.splitlines() if line.startswith("## ")]
    long_lines = [line for line in material.content.splitlines() if len(line) > 90]
    passed = 3 <= len(headings) <= 8 and not long_lines
    return make_check(
        "ppt_readability",
        passed,
        "PPT 大纲页数和单行文字量可控。" if passed else "PPT 大纲页数或单行文字量需要压缩。",
        page_count=len(headings),
        long_line_count=len(long_lines),
    )


def check_interview_explainability(material: GeneratedMaterial, profile: StudentProfile) -> dict:
    project_terms = usable_list_profile_field(profile, "projects")
    publication_terms = usable_list_profile_field(profile, "publications")
    if not any(term and term in material.content for term in project_terms + publication_terms):
        return make_check(
            "interview_explainability",
            True,
            "材料没有展开具体项目或论文，暂不做口头解释强约束。",
        )
    rejected_fields, confirmation_fields = profile_confirmation_issues(profile, material.content)
    passed = not rejected_fields
    return make_check(
        "interview_explainability",
        passed,
        "材料中的项目或论文表述可追溯，面试前需准备口头解释。"
        if passed and not confirmation_fields
        else "材料包含未确认项目或论文，面试前需先确认并准备解释。"
        if passed
        else f"材料使用已否认字段，不能作为面试解释材料：{'、'.join(rejected_fields)}",
    )


def student_anchor_terms(profile: StudentProfile) -> list[str]:
    return (
        usable_list_profile_field(profile, "projects")
        + usable_list_profile_field(profile, "publications")
        + usable_list_profile_field(profile, "competitions")
    )


def usable_list_or_scalar(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(str(value or "").strip())
