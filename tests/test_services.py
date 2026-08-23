import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agents import run_contact_email_workflow
from agents.advisor_extraction_agent import AdvisorExtractionAgent
from agents.evidence_audit_agent import EvidenceAuditAgent
from agents.match_analysis_agent import MatchAnalysisAgent
from lifecycle import (  # noqa: E402
    apply_email_signal_candidate,
    build_application_archive,
    email_signal_sync_status,
    generate_communication_draft,
    import_email_signal_candidates,
    pipeline_sync_status,
    reject_email_signal_candidate,
    update_outcome,
)
from models import (
    AdvisorSource,
    AdvisorSourceCreate,
    ApplicationRecord,
    CommunicationDraftRequest,
    EmailSignalDecisionRequest,
    GeneratedMaterial,
    KnowledgeBaseSourceCreate,
    OutcomeUpdate,
    PipelineSyncRequest,
    Target,
)
from rag import KnowledgeBaseIndex, KnowledgeBaseRetriever
from services import (
    audit_material,
    build_profile_from_text,
    build_readiness_score_report,
    build_workspace_report,
    create_advisor_source,
    ensure_application,
    make_contact_email,
    make_interview_questions,
    make_match,
    make_ppt_outline,
    merge_advisor_profile_with_llm,
    parse_advisor_profile,
    validate_public_url,
)
from source_connector_registry import scan_source_connector_registry
from storage import Workspace
from strategy import build_batch_triage_report, build_gap_plan, build_profile_expansion_report
from template_registry import scan_template_registry


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


def test_rag_context_flows_into_match_questions_and_outline(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="预推免通知",
            text="预推免材料包括简历、成绩单和科研项目摘要，截止日期为 2026 年 9 月 10 日。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    advisor_source = AdvisorSource(
        source_type="manual_text",
        title="王教授主页",
        raw_text="王教授研究方向包括多模态学习和大模型推理，欢迎关注预推免。",
        cleaned_text="王教授研究方向包括多模态学习和大模型推理，欢迎关注预推免。",
        trusted=True,
    )
    workspace.write(
        "advisor_sources",
        advisor_source.model_dump()
        if hasattr(advisor_source, "model_dump")
        else advisor_source.dict(),
        "source_id",
    )
    index.rebuild()

    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统，使用 Python 和 PyTorch 实现。",
        source_document_ids=["doc_resume"],
    )
    advisor = parse_advisor_profile([advisor_source])
    target = Target(
        name="某大学王教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=advisor.source_ids,
    )
    retriever = KnowledgeBaseRetriever(workspace)

    questions = make_interview_questions(profile, target, advisor, retriever=retriever)
    outline = make_ppt_outline(profile, target, advisor, retriever=retriever)
    result = MatchAnalysisAgent().analyze(profile, target, advisor, retriever=retriever)

    assert "申请流程和材料要求" in questions.content
    assert "可引用证据" in outline.content
    assert any(event.event_type == "retrieval_completed" for event in result.events)
    assert any(strength.get("dimension") == "rag_evidence" for strength in result.report.strengths)


def test_review_and_audit_use_current_policy_rag(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="2026 预推免通知",
            text="预推免材料包括简历、成绩单和科研项目摘要，截止日期为 2026 年 9 月 10 日。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    advisor_source = AdvisorSource(
        source_type="manual_text",
        title="王教授主页",
        raw_text="王教授研究方向包括多模态学习和大模型推理，欢迎关注预推免。",
        cleaned_text="王教授研究方向包括多模态学习和大模型推理，欢迎关注预推免。",
        trusted=True,
    )
    workspace.write(
        "advisor_sources",
        advisor_source.model_dump()
        if hasattr(advisor_source, "model_dump")
        else advisor_source.dict(),
        "source_id",
    )
    index.rebuild()

    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统，使用 Python 和 PyTorch 实现。",
        source_document_ids=["doc_resume"],
    )
    advisor = parse_advisor_profile([advisor_source])
    target = Target(
        name="某大学王教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=advisor.source_ids,
    )
    retriever = KnowledgeBaseRetriever(workspace)

    result = run_contact_email_workflow(profile, target, advisor, None, retriever=retriever)

    assert result.review.passed
    assert any("截止日期" in item for item in result.review.optional_improvements)
    assert any(
        claim.get("claim_type") == "policy_fact" and claim.get("status") == "supported"
        for claim in result.evidence_audit.claims
    )


def test_review_and_audit_flag_expired_policy_rag(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="旧版预推免通知",
            text="旧版通知写明 2024 年截止日期为 9 月 1 日。",
            valid_for_year=2024,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()

    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统，使用 Python 和 PyTorch 实现。",
        source_document_ids=["doc_resume"],
    )
    advisor = parse_advisor_profile([])
    advisor.research_directions = ["多模态学习"]
    target = Target(name="某大学王教授课题组", advisor_id=advisor.advisor_id)
    retriever = KnowledgeBaseRetriever(workspace)

    result = run_contact_email_workflow(profile, target, advisor, None, retriever=retriever)

    assert not result.review.passed
    assert not result.evidence_audit.passed
    assert any("过期" in item for item in result.review.required_revisions)
    assert any("过期" in item for item in result.evidence_audit.unsupported_claims)


def test_profile_evidence_map_tracks_source_documents():
    profile = build_profile_from_text(
        """
        匿名学生
        某大学计算机学院
        GPA 3.85/4.00，排名前 10%
        项目：多模态论文问答系统，使用 Python 和 PyTorch 实现检索增强问答。
        论文：某会议在投。
        """,
        source_document_ids=["doc_resume", "doc_project"],
    )

    assert profile.source_document_ids == ["doc_resume", "doc_project"]
    assert profile.gpa == "GPA 3.85/4.00"
    assert profile.rank == "排名前 10%"
    assert profile.evidence_map["education"] == ["doc_resume", "doc_project"]
    assert profile.evidence_map["gpa"] == ["doc_resume", "doc_project"]
    assert profile.evidence_map["rank"] == ["doc_resume", "doc_project"]
    assert profile.evidence_map["projects"] == ["doc_resume", "doc_project"]
    assert profile.evidence_map["publications"] == ["doc_resume", "doc_project"]
    assert profile.confirmation_map["gpa"] == "unconfirmed"
    assert profile.confirmation_map["projects"] == "unconfirmed"


def test_contact_email_respects_rejected_profile_fields():
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：智能体系统原型开发",
        source_document_ids=["doc_resume"],
    )
    profile.confirmation_map["projects"] = "rejected"
    target = Target(name="样例目标")

    material = make_contact_email(profile, target, None, None)

    assert "智能体系统原型开发" not in material.content
    assert "相关科研项目" in material.content


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
    assert [event.event_type for event in result.events] == [
        "workflow_started",
        "draft_started",
        "draft_completed",
        "review_started",
        "review_completed",
        "audit_started",
        "audit_completed",
        "quality_completed",
        "final_saved",
    ]
    assert all(event.run_id == result.agent_run.run_id for event in result.events)
    assert result.events[2].payload["material_id"] == result.material.material_id
    assert "content" not in result.events[2].payload


def test_advisor_extraction_agent_records_events_and_risks():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="张三教授，研究方向包括多模态学习和大模型推理，招收硕士学生。",
        )
    )

    result = AdvisorExtractionAgent().extract([source])

    assert result.advisor.source_ids == [source.source_id]
    assert result.agent_run.workflow == "advisor_intake.extraction"
    assert result.agent_run.status == "completed"
    assert result.agent_run.output_summary["advisor_id"] == result.advisor.advisor_id
    assert [event.event_type for event in result.events] == [
        "workflow_started",
        "extraction_started",
        "extraction_completed",
    ]


def test_match_analysis_agent_adds_evidence_and_risk_summary():
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统",
        source_document_ids=["doc_resume"],
    )
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="李四教授，研究方向包括多模态学习，招收硕士学生。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学李四教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=advisor.source_ids,
    )

    result = MatchAnalysisAgent().analyze(profile, target, advisor)

    assert result.report.target_id == target.target_id
    assert result.agent_run.workflow == "advisor_match.analysis"
    assert result.agent_run.output_summary["match_id"] == result.report.match_id
    assert [event.event_type for event in result.events] == [
        "workflow_started",
        "match_started",
        "match_completed",
    ]
    assert any(gap.get("dimension") == "student_confirmation" for gap in result.report.gaps)


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


def test_evidence_audit_uses_profile_field_document_ids():
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\nGPA 3.8/4.0，排名前 10%\n项目：智能体系统原型开发",
        source_document_ids=["doc_transcript"],
    )
    target = Target(name="样例目标")
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="含成绩的套磁邮件",
        content="老师您好，我的 GPA 3.8/4.0，排名前 10%。",
        evidence=[profile.profile_id, target.target_id],
    )

    audit = EvidenceAuditAgent().audit_contact_email(material, profile, target, None, None)
    grade_claim = next(claim for claim in audit.claims if claim["claim_type"] == "grade_or_rank")

    assert audit.passed
    assert grade_claim["source_ids"] == ["doc_transcript"]
    assert audit.needs_confirmation


def test_evidence_audit_flags_unconfirmed_and_rejected_profile_fields():
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：智能体系统原型开发",
        source_document_ids=["doc_resume"],
    )
    target = Target(name="样例目标")
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="含未确认字段的套磁邮件",
        content="老师您好，我来自某大学计算机学院，做过项目：智能体系统原型开发。",
        evidence=[profile.profile_id, target.target_id],
    )

    audit = EvidenceAuditAgent().audit_contact_email(material, profile, target, None, None)

    assert audit.passed
    assert any("未确认学生字段" in item for item in audit.needs_confirmation)

    profile.confirmation_map["projects"] = "rejected"
    audit = EvidenceAuditAgent().audit_contact_email(material, profile, target, None, None)

    assert not audit.passed
    assert any("已否认字段" in item for item in audit.unsupported_claims)


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


def test_readiness_score_report_rolls_up_existing_workflow_state():
    profile = build_profile_from_text(
        """
        匿名学生
        某大学计算机学院
        GPA 3.85/4.00，排名前 10%
        项目：多模态论文问答系统，使用 Python 和 PyTorch 实现检索增强问答。
        竞赛：大学生创新训练计划。
        """,
        source_document_ids=["doc_profile"],
    )
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="李四教授，研究方向包括多模态学习和大模型推理，招收硕士学生。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学李四教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=[source.source_id],
        deadline="2026-09-10",
    )
    match = make_match(profile, target, advisor)
    app_record = ensure_application(target)
    app_record.status = "contacted"
    email = make_contact_email(profile, target, advisor, match)
    questions = make_interview_questions(profile, target, advisor)
    outline = make_ppt_outline(profile, target, advisor)
    quality_reports = [
        audit_material(item, profile, advisor) for item in [email, questions, outline]
    ]

    report = build_readiness_score_report(
        profile,
        [target],
        [app_record],
        matches=[match],
        materials=[email, questions, outline],
        quality_reports=quality_reports,
        advisors=[advisor],
    )
    workspace_report = build_workspace_report(profile, [target], [app_record])

    assert report.total_score > 0
    assert report.target_scores[0].target_id == target.target_id
    assert any(item.name == "profile_completeness" for item in report.dimensions)
    assert any(item.name == "material_quality" for item in report.target_scores[0].dimensions)
    assert "申请准备度" in workspace_report["content"]


def test_application_lifecycle_archive_outcome_and_sync_skeletons(tmp_path):
    workspace = Workspace(str(tmp_path))
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统",
        source_document_ids=["doc_profile"],
    )
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="李四教授，研究方向包括多模态学习，招收硕士学生。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学李四教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=[source.source_id],
        deadline="2026-09-10",
    )
    application = ApplicationRecord(
        target_id=target.target_id,
        status="contacted",
        deadline=target.deadline,
        last_contact_at="2026-08-01T12:00:00+08:00",
    )
    match = make_match(profile, target, advisor)
    material = make_contact_email(profile, target, advisor, match)

    archive = build_application_archive(
        workspace,
        target,
        application,
        [material],
        stage="drafted",
        notes="测试归档",
    )
    outcome_archive = update_outcome(
        workspace,
        target,
        application,
        OutcomeUpdate(
            stage="replied",
            outcome_date="2026-08-23",
            feedback="导师回复可继续沟通。",
            user_reflection="需要补充项目摘要。",
            calibration_signals=["导师回复"],
            next_steps=["准备项目摘要"],
        ),
    )
    draft = generate_communication_draft(
        workspace,
        target,
        application,
        profile,
        advisor,
        [material],
        CommunicationDraftRequest(kind="follow_up"),
    )
    thanks = generate_communication_draft(
        workspace,
        target,
        application,
        profile,
        advisor,
        [material],
        CommunicationDraftRequest(kind="thank_you"),
    )
    email_status = email_signal_sync_status("gmail")
    pipeline_status = pipeline_sync_status(PipelineSyncRequest(provider="notion"))

    assert (workspace.root / archive.target_snapshot_path).exists()
    assert archive.submitted_material_paths
    assert "Outcome 不直接修改评分规则" in (
        workspace.root / outcome_archive.outcome_path
    ).read_text(encoding="utf-8")
    assert draft.kind == "follow_up"
    assert "自动发送" not in draft.content
    assert "多模态论文问答系统" not in draft.content
    assert (workspace.root / draft.archive_path).exists()
    assert thanks.kind == "thank_you"
    assert email_status.read_only
    assert not email_status.candidates
    assert pipeline_status.direction == "one_way_export"
    assert "material_content" in pipeline_status.skipped_fields


def test_email_signal_candidates_require_confirmation_before_tracker_update(tmp_path):
    workspace = Workspace(str(tmp_path))
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="李四教授，邮箱 lisi@example.edu，研究方向包括多模态学习。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学李四教授课题组",
        advisor_id=advisor.advisor_id,
        school="某大学",
        deadline="2026-09-10",
    )
    application = ApplicationRecord(
        target_id=target.target_id,
        status="contacted",
        deadline=target.deadline,
    )

    result = import_email_signal_candidates(
        workspace,
        "gmail",
        """Subject: 某大学李四教授课题组 面试通知
From: lisi@example.edu
Date: 2026-08-23
同学你好，请参加预推免面试，并准备成绩单和项目介绍。
""",
        [target],
        [application],
        [advisor],
    )

    candidate = result.candidates[0]
    assert candidate.status == "needs_user_confirmation"
    assert candidate.target_id == target.target_id
    assert candidate.signal_type == "interview_invitation"
    assert candidate.proposed_status == "interview_scheduled"
    assert application.status == "contacted"

    applied = apply_email_signal_candidate(
        workspace,
        candidate,
        target,
        application,
        EmailSignalDecisionRequest(user_note="已确认邮件来自导师。"),
    )

    saved_application = workspace.read("applications", application.application_id)
    assert applied.status == "approved"
    assert saved_application["status"] == "interview_scheduled"
    assert workspace.list("application_archives")
    assert workspace.read("email_signal_candidates", candidate.candidate_id)["status"] == "approved"


def test_email_signal_reject_does_not_update_tracker(tmp_path):
    workspace = Workspace(str(tmp_path))
    target = Target(name="某大学王教授课题组")
    application = ApplicationRecord(target_id=target.target_id, status="contacted")
    result = import_email_signal_candidates(
        workspace,
        "qq",
        """主题：某大学王教授课题组 offer
发件人：wang@example.edu
日期：2026-08-23
恭喜，你已获得拟录取资格。
""",
        [target],
        [application],
        [],
    )

    candidate = result.candidates[0]
    rejected = reject_email_signal_candidate(
        workspace,
        candidate,
        EmailSignalDecisionRequest(user_note="测试中拒绝候选。"),
    )

    assert rejected.status == "rejected"
    assert application.status == "contacted"


def test_quality_audit_flags_false_publication_claim():
    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：智能体系统原型开发")
    target = Target(name="样例目标")
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="虚构论文风险",
        content="老师您好，我的论文成果已发表在某顶级会议。",
        evidence=[profile.profile_id, target.target_id],
    )

    quality = audit_material(material, profile, None)

    assert not quality.passed
    assert any(check["name"] == "student_fact_consistency" for check in quality.checks)
    assert any("论文成果表述缺少学生画像字段" in check["message"] for check in quality.checks)


def test_quality_audit_flags_missing_advisor_evidence_and_direction_mismatch():
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="李四教授，研究方向包括多模态学习，招收硕士学生。",
        )
    )
    advisor = parse_advisor_profile([source])
    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：智能体系统原型开发")
    target = Target(name="样例目标", advisor_id=advisor.advisor_id)
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="缺少导师证据",
        content="老师您好，我关注智能体系统方向，希望进一步交流。",
        evidence=[profile.profile_id, target.target_id],
    )

    quality = audit_material(material, profile, advisor)

    assert not quality.passed
    assert any(
        check["name"] == "advisor_source_present" and not check["passed"]
        for check in quality.checks
    )
    assert any(
        check["name"] == "advisor_direction_match" and not check["passed"]
        for check in quality.checks
    )


def test_quality_audit_flags_overclaim():
    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：智能体系统原型开发")
    target = Target(name="样例目标")
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="过度承诺",
        content="老师您好，我认为自己一定适合贵组，并且可以保证录取后快速产出。",
        evidence=[profile.profile_id, target.target_id],
    )

    quality = audit_material(material, profile, None)

    assert not quality.passed
    assert any(check["name"] == "no_admission_claim" for check in quality.checks)


def test_workspace_creates_agent_and_version_directories(tmp_path):
    workspace = Workspace(str(tmp_path))

    assert (workspace.root / "agent_runs").is_dir()
    assert (workspace.root / "workflow_events").is_dir()
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


def test_stage16_strategy_triage_profile_expand_and_gap_plan(tmp_path):
    workspace = Workspace(str(tmp_path))
    document = workspace.save_user_document(
        "补充项目：RAG 保研政策问答系统，使用 FastAPI 和 Python 实现。".encode("utf-8"),
        "project.md",
        category="research_projects",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
    )
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\nGPA 3.8/4.0\n项目：多模态论文问答系统",
        source_document_ids=["doc_profile"],
    )
    source = create_advisor_source(
        AdvisorSourceCreate(
            source_type="manual_text",
            manual_text="王教授，研究方向包括多模态学习和 RAG，要求学生熟悉 Python。",
        )
    )
    advisor = parse_advisor_profile([source])
    target = Target(
        name="某大学王教授课题组",
        advisor_id=advisor.advisor_id,
        deadline="2026-09-10",
        source_ids=advisor.source_ids,
    )
    match = make_match(profile, target, advisor)
    app_record = ensure_application(target)

    triage = build_batch_triage_report(
        workspace,
        profile,
        [target],
        [advisor],
        [app_record],
        [match],
        None,
    )
    expansion = build_profile_expansion_report(workspace, profile)
    gap_plan = build_gap_plan(
        workspace,
        target,
        profile,
        advisor,
        app_record,
        match,
        None,
        quality_reports=[],
        materials=[],
    )
    template_status = scan_template_registry(ROOT)
    connector_status = scan_source_connector_registry(ROOT)

    assert triage.items[0].preliminary is True
    assert triage.items[0].target_id == target.target_id
    assert triage.items[0].triage_score > 0
    assert any(
        document.document_id in candidate.evidence_refs for candidate in expansion.candidates
    )
    assert all(candidate.status == "unconfirmed" for candidate in expansion.candidates)
    assert any(gap.category == "interview_prep" for gap in gap_plan.gaps)
    assert workspace.list("target_triage_reports")
    assert workspace.list("profile_expansion_candidates")
    assert workspace.list("gap_plans")
    assert template_status.implemented is True
    assert template_status.template_count >= 2
    assert template_status.active_count >= 2
    assert all(template.render_preview.passed for template in template_status.templates)
    assert connector_status.implemented is True
    assert connector_status.connector_count >= 2
    assert connector_status.active_count >= 2
    assert all(connector.field_mapping for connector in connector_status.connectors)
