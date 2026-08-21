import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agents import run_contact_email_workflow
from agents.evidence_audit_agent import EvidenceAuditAgent
from models import AdvisorSourceCreate, GeneratedMaterial, Target
from services import (
    audit_material,
    build_profile_from_text,
    build_workspace_report,
    create_advisor_source,
    make_contact_email,
    make_interview_questions,
    make_match,
    make_ppt_outline,
    merge_advisor_profile_with_llm,
    parse_advisor_profile,
    validate_public_url,
)
from storage import Workspace


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


def test_contact_email_agent_workflow_records_review_audit_and_versions():
    profile = build_profile_from_text(
        """
        匿名学生
        某大学计算机学院
        项目：多模态论文问答系统，使用 Python 和 PyTorch 实现检索增强问答。
        """
    )
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="张三教授，研究方向包括多模态学习和大模型推理，招收硕士学生。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学张三教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=[source.source_id],
    )
    match = make_match(profile, target, advisor)

    result = run_contact_email_workflow(profile, target, advisor, match)

    assert result.material.material_type == "contact_email"
    assert result.review.reviewer == "MaterialReviewAgent"
    assert result.evidence_audit.auditor == "EvidenceAuditAgent"
    assert result.evidence_audit.passed
    assert result.quality.passed
    assert result.agent_run.status == "completed"
    assert result.agent_run.output_summary["material_id"] == result.material.material_id
    assert [version.stage for version in result.versions] == ["draft", "final"]
    assert result.versions[0].source_run_id == result.agent_run.run_id


def test_contact_email_agent_flags_missing_advisor_source():
    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：智能体系统原型开发")
    advisor = parse_advisor_profile([])
    advisor.research_directions = ["智能体系统"]
    target = Target(name="未知导师课题组", advisor_id=advisor.advisor_id)

    result = run_contact_email_workflow(profile, target, advisor, None)

    assert not result.review.passed
    assert "review_required" in result.agent_run.risk_tags
    assert result.evidence_audit.needs_confirmation


def test_evidence_audit_fails_when_required_sources_are_missing():
    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：智能体系统原型开发")
    target = Target(name="样例目标")
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="缺少证据的套磁邮件",
        content="老师您好，我关注智能体系统方向。",
        evidence=[],
    )

    audit = EvidenceAuditAgent().audit_contact_email(material, profile, target, None, None)

    assert not audit.passed
    assert audit.unsupported_claims


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


def test_workspace_creates_agent_and_version_directories(tmp_path):
    workspace = Workspace(str(tmp_path))

    assert (workspace.root / "agent_runs").is_dir()
    assert (workspace.root / "material_versions").is_dir()
    assert (workspace.root / "user_documents").is_dir()


def test_workspace_saves_user_document_manifest(tmp_path):
    workspace = Workspace(str(tmp_path))
    record = workspace.save_user_document(
        "匿名学生\n项目：智能体系统原型开发".encode("utf-8"),
        "resume.txt",
        category="resumes",
        source_type="local_upload",
        notes="test upload",
    )
    manifest = workspace.read_user_document_manifest()

    assert record.document_id
    assert record.content_hash.startswith("sha256:")
    assert record.path.startswith("user_documents/resumes/")
    assert (workspace.root / record.path).read_text(encoding="utf-8").startswith("匿名学生")
    assert manifest["documents"][0]["document_id"] == record.document_id
    assert manifest["documents"][0]["notes"] == "test upload"


def test_workspace_rejects_unsupported_user_document_format(tmp_path):
    workspace = Workspace(str(tmp_path))

    try:
        workspace.save_user_document(b"secret", "profile.exe", category="resumes")
        assert False, "unsupported format should be rejected"
    except ValueError as exc:
        assert "Unsupported user document format" in str(exc)


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


def test_llm_advisor_merge_requires_evidence_for_list_fields():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="孙七教授，研究方向包括可信机器学习。",
        )
    )
    advisor = parse_advisor_profile([source])
    enriched = merge_advisor_profile_with_llm(
        advisor,
        {
            "school": "样例大学",
            "research_directions": [
                {
                    "value": "可信机器学习",
                    "evidence": "研究方向包括可信机器学习",
                    "confidence": 0.9,
                },
                {"value": "量子计算", "evidence": "", "confidence": 0.9},
                {"value": "机器人", "evidence": "没有足够证据", "confidence": 0.2},
            ],
            "admission_requirements": [
                {
                    "value": "欢迎有机器学习基础的同学申请",
                    "evidence": "欢迎有机器学习基础的同学申请",
                    "confidence": 0.8,
                }
            ],
            "recruiting_status": "open",
        },
        [source.source_id],
    )

    assert enriched.school == "样例大学"
    assert "可信机器学习" in enriched.research_directions
    assert "量子计算" not in enriched.research_directions
    assert "机器人" not in enriched.research_directions
    assert enriched.admission_requirements == ["欢迎有机器学习基础的同学申请"]
    assert enriched.evidence_map["admission_requirements"] == [source.source_id]


def test_updated_advisor_fields_can_feed_target_creation():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="周八教授，研究方向包括多模态学习。",
        )
    )
    advisor = parse_advisor_profile([source])
    advisor.school = "修正大学"
    advisor.college = "人工智能学院"
    advisor.lab_name = "可信智能实验室"
    advisor.research_directions = ["多模态学习", "可信 AI"]
    advisor.identity_confirmed = True

    target = Target(
        name=f"{advisor.school} {advisor.college} {advisor.name_zh} 课题组",
        advisor_id=advisor.advisor_id,
        school=advisor.school,
        college=advisor.college,
        program_name=advisor.lab_name,
        source_ids=advisor.source_ids,
    )

    assert target.school == "修正大学"
    assert target.college == "人工智能学院"
    assert target.program_name == "可信智能实验室"
    assert source.source_id in target.source_ids
