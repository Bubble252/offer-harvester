import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from models import AdvisorSourceCreate, Target
from services import (
    audit_material,
    build_profile_from_text,
    build_workspace_report,
    create_advisor_source,
    make_contact_email,
    make_interview_questions,
    make_match,
    make_ppt_outline,
    parse_advisor_profile,
    validate_public_url,
)


def test_mvp_generation_flow_with_manual_advisor_text():
    profile = build_profile_from_text(
        """
        匿名学生
        某大学计算机学院
        GPA 3.85/4.00，排名前 10%
        项目：多模态论文问答系统，使用 Python 和 PyTorch 实现检索增强问答。
        竞赛：大学生创新训练计划。
        """
    )
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="张三教授，研究方向包括多模态学习、大模型推理和智能体系统，招收硕士和直博学生。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学计算机学院张三教授课题组",
        advisor_id=advisor.advisor_id,
        degree_track="direct_phd",
        source_ids=[source.source_id],
    )

    report = make_match(profile, target, advisor)
    email = make_contact_email(profile, target, advisor, report)
    questions = make_interview_questions(profile, target, advisor)
    outline = make_ppt_outline(profile, target, advisor)

    assert report.tier in {"strong_fit", "reasonable_fit", "weak_fit", "unknown"}
    assert "张三" in email.content
    assert "多模态" in questions.content
    assert "5 分钟" in outline.content


def test_source_hash_url_guard_quality_audit_and_progress_report():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="李四教授，研究方向包括智能体系统，招收硕士学生。",
        )
    )
    assert source.content_hash.startswith("sha256:")

    try:
        validate_public_url("http://127.0.0.1:8000")
        assert False, "private URL should be rejected"
    except ValueError:
        pass

    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：智能体系统原型开发")
    advisor = parse_advisor_profile([source])
    target = Target(name="某大学李四教授课题组", advisor_id=advisor.advisor_id)
    material = make_contact_email(profile, target, advisor, None)
    quality = audit_material(material, profile, advisor)
    report = build_workspace_report(profile, [target], [])

    assert quality.passed
    assert quality.risk_level == "low"
    assert source.source_id in material.evidence
    assert "不预测录取结果" in report["content"]


def test_advisor_profile_keeps_detailed_fields_and_evidence():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="""
            王五教授，北京样例大学计算机学院智能系统实验室。
            研究方向包括大模型、多模态和知识图谱。
            招收硕士和直博学生，欢迎有 Python、PyTorch 和数学基础的同学申请。
            代表论文：面向科研问答的大模型系统，发表于某人工智能会议。
            项目：国家自然科学基金智能体系统课题。
            邮箱 wangwu@example.edu.cn
            """,
        )
    )
    advisor = parse_advisor_profile([source])

    assert advisor.name_zh == "王五"
    assert advisor.school == "北京样例大学"
    assert advisor.college == "计算机学院"
    assert advisor.lab_name == "智能系统实验室"
    assert advisor.email == "wangwu@example.edu.cn"
    assert "大模型" in advisor.research_directions
    assert advisor.recruiting_status == "open"
    assert advisor.representative_papers
    assert advisor.research_projects
    assert advisor.admission_requirements
    assert advisor.evidence_map["research_directions"] == [source.source_id]


def test_failed_url_source_records_reason_and_manual_fallback():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="advisor_homepage",
            url="http://127.0.0.1:8000/private",
            manual_text="赵六副教授，研究方向包括数据挖掘，招收硕士学生。",
        )
    )
    advisor = parse_advisor_profile([source])

    assert source.fetch_status == "manual"
    assert source.fetch_error
    assert source.content_hash.startswith("sha256:")
    assert advisor.name_zh == "赵六"
    assert "数据挖掘" in advisor.research_directions
