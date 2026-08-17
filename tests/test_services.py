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
