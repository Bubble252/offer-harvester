from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import (  # noqa: E402
    AdvisorExtractionAgent,
    MatchAnalysisAgent,
    run_contact_email_workflow,
)
from models import (  # noqa: E402
    AdvisorSource,
    GeneratedMaterial,
    PresentationTaskRecord,
    Target,
    now_iso,
)
from quality import audit_material  # noqa: E402
from services import (  # noqa: E402
    build_profile_from_text,
    build_workspace_report,
    ensure_application,
    make_interview_questions,
    make_ppt_outline,
)
from storage import Workspace  # noqa: E402

from integrations.presentation_engine import LocalPptxAdapter, PresentationRequest  # noqa: E402

DEMO_STUDENT_TEXT = """匿名学生
某大学计算机科学与技术专业
GPA 3.86/4.00，排名前 8%
研究兴趣：多模态学习、大模型应用、科研智能体
项目：多模态论文问答系统，负责检索增强问答、图文段落对齐和 FastAPI 原型开发。
项目：科研文献检索工具，使用 Python、PyTorch 和向量检索组织论文证据。
论文：多模态科研问答系统技术报告，校级科研训练项目结题材料。
竞赛：大学生创新训练计划优秀结题。
技能：Python、PyTorch、FastAPI、LaTeX、信息检索、数据分析。
"""

ADVISOR_SOURCE_URL = "https://air.tsinghua.edu.cn/info/1046/1201.htm"

ADVISOR_SOURCE_SUMMARY = f"""刘菁菁教授，清华大学智能产业研究院首席研究员、博士生导师。
公开页面显示其研究领域包括多模态大模型、AI for Science、强化学习，并列出多模态大模型、强化学习和 AI for Science 相关论文。
本 demo 只保存公开页面短摘要和来源链接，不复制长篇页面正文。
来源：{ADVISOR_SOURCE_URL}
"""


def dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def reset_workspace(root: Path) -> None:
    protected = {ROOT, ROOT.parent, Path.home(), ROOT / "workspace"}
    resolved = root.resolve()
    if resolved in protected or resolved == Path("/"):
        raise ValueError(f"Refusing to reset protected path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def build_demo_workspace(root: Path, reset: bool = False) -> dict:
    if reset:
        reset_workspace(root)
    workspace = Workspace(str(root))

    profile_doc = workspace.save_user_document(
        DEMO_STUDENT_TEXT.encode("utf-8"),
        "anonymous_student_profile.txt",
        category="resumes",
        source_type="manual_input",
        trusted=True,
        confirmed=True,
        notes="阶段 9 匿名 Demo 学生资料。",
    )
    profile = build_profile_from_text(
        DEMO_STUDENT_TEXT,
        source_document_ids=[profile_doc.document_id],
    )
    for field in list(profile.confirmation_map):
        profile.confirmation_map[field] = "confirmed"
    workspace.write("profiles", dump(profile), "profile_id")

    advisor_source = AdvisorSource(
        source_type="school_profile",
        url=ADVISOR_SOURCE_URL,
        title="清华大学智能产业研究院刘菁菁公开主页短摘要",
        fetch_status="manual",
        content_hash=f"sha256:{hashlib.sha256(ADVISOR_SOURCE_SUMMARY.encode('utf-8')).hexdigest()}",
        raw_text=ADVISOR_SOURCE_SUMMARY,
        cleaned_text=ADVISOR_SOURCE_SUMMARY,
        trusted=True,
        notes="阶段 9 Demo：仅保存公开页面短摘要和来源链接。",
    )
    workspace.write("advisor_sources", dump(advisor_source), "source_id")

    extraction = AdvisorExtractionAgent().extract([advisor_source])
    advisor = extraction.advisor
    workspace.write("advisors", dump(advisor), "advisor_id")
    workspace.write("agent_runs", dump(extraction.agent_run), "run_id")
    for event in extraction.events:
        workspace.write("workflow_events", dump(event), "event_id")

    target = Target(
        name="清华大学智能产业研究院刘菁菁课题组",
        target_type="advisor",
        advisor_id=advisor.advisor_id,
        school=advisor.school or "清华大学",
        college=advisor.college or "智能产业研究院",
        degree_track="direct_phd",
        application_round="summer_camp",
        deadline="2026-09-15",
        priority="high",
        source_ids=advisor.source_ids,
    )
    workspace.write("targets", dump(target), "target_id")

    application = ensure_application(target)
    application.status = "materials_preparing"
    application.next_action = "复核导师来源证据，确认套磁邮件后准备 5 分钟面试展示。"
    workspace.write("applications", dump(application), "application_id")

    match = MatchAnalysisAgent().analyze(profile, target, advisor)
    workspace.write("matches", dump(match.report), "match_id")
    workspace.write("agent_runs", dump(match.agent_run), "run_id")
    for event in match.events:
        workspace.write("workflow_events", dump(event), "event_id")

    contact = run_contact_email_workflow(profile, target, advisor, match.report)
    for version in contact.versions:
        workspace.write("material_versions", dump(version), "version_id")
    for event in contact.events:
        workspace.write("workflow_events", dump(event), "event_id")
    workspace.write("generated", dump(contact.material), "material_id")
    workspace.write("quality_reports", dump(contact.quality), "quality_id")
    workspace.write("agent_runs", dump(contact.agent_run), "run_id")

    interview = make_interview_questions(profile, target, advisor)
    save_material(workspace, interview, profile, advisor)

    outline = make_ppt_outline(profile, target, advisor)
    save_material(workspace, outline, profile, advisor)
    presentation_task = generate_pptx(workspace, target, outline)
    workspace.write("presentation_tasks", dump(presentation_task), "task_id")

    report = build_workspace_report(profile, [target], [application])
    workspace.write("reports", report, "report_id")
    write_demo_summary(workspace, profile.profile_id, target.target_id, report["report_id"])

    return {
        "workspace": str(workspace.root),
        "profile_id": profile.profile_id,
        "advisor_id": advisor.advisor_id,
        "target_id": target.target_id,
        "match_id": match.report.match_id,
        "contact_email_id": contact.material.material_id,
        "interview_questions_id": interview.material_id,
        "ppt_outline_id": outline.material_id,
        "presentation_task_id": presentation_task.task_id,
        "report_id": report["report_id"],
    }


def save_material(
    workspace: Workspace,
    material: GeneratedMaterial,
    profile,
    advisor,
) -> None:
    workspace.write("generated", dump(material), "material_id")
    quality = audit_material(material, profile, advisor)
    workspace.write("quality_reports", dump(quality), "quality_id")


def generate_pptx(
    workspace: Workspace,
    target: Target,
    outline: GeneratedMaterial,
) -> PresentationTaskRecord:
    task = PresentationTaskRecord(
        target_id=target.target_id,
        outline_material_id=outline.material_id,
        status="running",
        progress=15,
        message="阶段 9 Demo 正在生成可编辑 PPTX。",
        updated_at=now_iso(),
    )
    try:
        result = LocalPptxAdapter().generate(
            PresentationRequest(
                title=f"{target.name}_面试展示",
                outline=outline.content,
                output_dir=workspace.root / "generated" / "presentations",
                metadata={"target_id": target.target_id},
            )
        )
        if not result.output_path:
            raise RuntimeError(result.message or "未生成 PPTX 文件")
        task.status = "completed"
        task.progress = 100
        task.output_filename = result.output_path.name
        task.message = result.message
    except Exception as exc:
        task.status = "failed"
        task.progress = 100
        task.message = "PPTX 生成失败。"
        task.error = str(exc)
    task.updated_at = now_iso()
    return task


def write_demo_summary(
    workspace: Workspace,
    profile_id: str,
    target_id: str,
    report_id: str,
) -> None:
    summary = f"""# 阶段 9 Demo 摘要

- Workspace: `{workspace.root}`
- 匿名学生画像: `{profile_id}`
- 申请目标: `{target_id}`
- 进度报告: `{report_id}`
- 真实公开导师来源: {ADVISOR_SOURCE_URL}

演示路径：

```text
学生资料 -> 学生画像确认 -> 导师来源 -> 申请目标 -> 匹配分析
-> 套磁邮件 D-R-A -> 面试问题 -> PPT 大纲 -> 可编辑 PPTX -> 进度报告
```

隐私边界：

- 学生资料为匿名虚构材料。
- 导师来源只保存公开页面短摘要和链接。
- 不保存真实学生联系方式、证件、成绩单原件或私密申请记录。
"""
    (workspace.root / "reports" / "demo_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a reproducible stage 9 demo workspace.")
    parser.add_argument(
        "--workspace",
        default=str(ROOT / "workspace.demo"),
        help="Workspace directory to create. Defaults to ./workspace.demo.",
    )
    parser.add_argument("--reset", action="store_true", help="Delete the demo workspace first.")
    args = parser.parse_args()

    result = build_demo_workspace(Path(args.workspace), reset=args.reset)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
