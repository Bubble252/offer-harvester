from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from models import (
    AdvisorProfile,
    ApplicationArchive,
    ApplicationRecord,
    CommunicationDraft,
    CommunicationDraftRequest,
    EmailSignalSyncResult,
    GeneratedMaterial,
    OutcomeUpdate,
    PipelineSyncRequest,
    PipelineSyncResult,
    StudentProfile,
    Target,
    now_iso,
)
from storage import Workspace, safe_filename

FOLLOW_UP_INTERVAL_DAYS = 3
FOLLOW_UP_MAX_ATTEMPTS = 3
PUBLIC_SYNC_FIELDS = [
    "target_name",
    "status",
    "deadline",
    "readiness_score",
    "next_action",
    "local_file_names",
]
PRIVATE_SYNC_FIELDS = [
    "material_content",
    "transcripts",
    "recommendation_letters",
    "contact_details",
    "email_body",
]


def build_application_archive(
    workspace: Workspace,
    target: Target,
    application: ApplicationRecord,
    materials: List[GeneratedMaterial],
    *,
    stage: str = "drafted",
    notes: str = "",
) -> ApplicationArchive:
    archive = _existing_archive(workspace, target.target_id) or ApplicationArchive(
        target_id=target.target_id,
        target_name=target.name,
        stage=stage,  # type: ignore[arg-type]
        notes=notes,
    )
    archive.stage = stage  # type: ignore[assignment]
    archive.target_name = target.name
    archive.notes = notes or archive.notes
    archive.updated_at = now_iso()

    archive_dir = _archive_dir(workspace, target, archive.archive_id)
    submitted_dir = archive_dir / "submitted_materials"
    communications_dir = archive_dir / "communications"
    submitted_dir.mkdir(parents=True, exist_ok=True)
    communications_dir.mkdir(parents=True, exist_ok=True)

    target_path = archive_dir / "target_snapshot.json"
    app_path = archive_dir / "application_snapshot.json"
    outcome_path = archive_dir / "outcome.md"
    lessons_path = archive_dir / "lessons.md"
    target_path.write_text(_json(target), encoding="utf-8")
    app_path.write_text(_json(application), encoding="utf-8")
    if not outcome_path.exists():
        outcome_path.write_text(_default_outcome(target, stage), encoding="utf-8")
    if not lessons_path.exists():
        lessons_path.write_text("# Lessons\n\n- 待复盘。\n", encoding="utf-8")

    material_paths = []
    for material in materials:
        filename = f"{safe_filename(material.material_type or material.material_id)}.md"
        material_path = submitted_dir / filename
        material_path.write_text(material.content, encoding="utf-8")
        material_paths.append(_relative(workspace, material_path))

    archive.archive_path = _relative(workspace, archive_dir)
    archive.target_snapshot_path = _relative(workspace, target_path)
    archive.application_snapshot_path = _relative(workspace, app_path)
    archive.submitted_material_paths = material_paths
    archive.communication_paths = _list_markdown_paths(workspace, communications_dir)
    archive.outcome_path = _relative(workspace, outcome_path)
    archive.lessons_path = _relative(workspace, lessons_path)
    workspace.write("application_archives", _dump(archive), "archive_id")
    return archive


def update_outcome(
    workspace: Workspace,
    target: Target,
    application: ApplicationRecord,
    outcome: OutcomeUpdate,
) -> ApplicationArchive:
    archive = _existing_archive(workspace, target.target_id) or build_application_archive(
        workspace,
        target,
        application,
        [],
        stage=outcome.stage,
    )
    archive_dir = workspace.root / archive.archive_path
    archive_dir.mkdir(parents=True, exist_ok=True)
    outcome_path = archive_dir / "outcome.md"
    outcome_path.write_text(_render_outcome(target, outcome), encoding="utf-8")
    archive.stage = outcome.stage
    archive.outcome_path = _relative(workspace, outcome_path)
    archive.updated_at = now_iso()
    workspace.write("application_archives", _dump(archive), "archive_id")
    return archive


def generate_communication_draft(
    workspace: Workspace,
    target: Target,
    application: ApplicationRecord,
    profile: Optional[StudentProfile],
    advisor: Optional[AdvisorProfile],
    materials: List[GeneratedMaterial],
    request: CommunicationDraftRequest,
) -> CommunicationDraft:
    archive = _existing_archive(workspace, target.target_id) or build_application_archive(
        workspace,
        target,
        application,
        materials,
        stage=application.status,
    )
    communication = CommunicationDraft(
        target_id=target.target_id,
        kind=request.kind,
        title=_communication_title(request.kind, advisor),
        content=_communication_content(target, application, profile, advisor, materials, request),
        source_material_ids=[item.material_id for item in materials],
        evidence_refs=_communication_evidence(profile, advisor, materials),
    )
    archive_dir = workspace.root / archive.archive_path
    comm_dir = archive_dir / "communications"
    comm_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{request.kind}_{datetime.now().date().isoformat()}_{communication.communication_id}.md"
    )
    path = comm_dir / filename
    path.write_text(communication.content, encoding="utf-8")
    communication.archive_path = _relative(workspace, path)

    archive.communication_paths = _list_markdown_paths(workspace, comm_dir)
    archive.updated_at = now_iso()
    workspace.write("application_archives", _dump(archive), "archive_id")
    workspace.write("communications", _dump(communication), "communication_id")

    note = f"{datetime.now().date().isoformat()} 生成 {request.kind} 草稿：{communication.archive_path}"
    application.notes = list(dict.fromkeys(application.notes + [note]))
    application.next_action = _next_action_after_communication(request.kind)
    application.updated_at = now_iso()
    workspace.write("applications", _dump(application), "application_id")
    return communication


def email_signal_sync_status(provider: str = "unknown") -> EmailSignalSyncResult:
    provider = provider if provider in {"gmail", "qq"} else "unknown"
    configured = bool(os.environ.get("EMAIL_SYNC_READONLY_TOKEN"))
    message = (
        "只读邮箱同步已配置，但当前骨架不会自动写入 tracker。"
        if configured
        else "邮箱同步未配置；骨架保持只读，不发信、不删信、不改标签。"
    )
    return EmailSignalSyncResult(
        provider=provider,  # type: ignore[arg-type]
        configured=configured,
        read_only=True,
        candidates=[],
        message=message,
    )


def pipeline_sync_status(request: PipelineSyncRequest) -> PipelineSyncResult:
    env_name = {
        "notion": "NOTION_SYNC_TOKEN",
        "feishu": "FEISHU_SYNC_TOKEN",
        "google_sheets": "GOOGLE_SHEETS_SYNC_TOKEN",
    }[request.provider]
    configured = bool(os.environ.get(env_name))
    return PipelineSyncResult(
        provider=request.provider,
        configured=configured,
        direction="one_way_export",
        exported_fields=PUBLIC_SYNC_FIELDS,
        skipped_fields=PRIVATE_SYNC_FIELDS,
        message=(
            "外部看板单向同步已配置；当前骨架只同步状态类字段。"
            if configured
            else "外部看板未配置；本地 workspace 仍是唯一事实源。"
        ),
    )


def should_generate_follow_up(application: ApplicationRecord) -> bool:
    if application.status not in {"contacted", "no_response"}:
        return False
    attempts = sum("follow_up" in note for note in application.notes)
    if attempts >= FOLLOW_UP_MAX_ATTEMPTS:
        return False
    last_contact = _parse_datetime(application.last_contact_at)
    if not last_contact:
        return True
    return datetime.now().astimezone() - last_contact >= timedelta(days=FOLLOW_UP_INTERVAL_DAYS)


def _existing_archive(workspace: Workspace, target_id: str) -> Optional[ApplicationArchive]:
    archives = [
        ApplicationArchive(**item)
        for item in workspace.list("application_archives")
        if item.get("target_id") == target_id
    ]
    return archives[-1] if archives else None


def _archive_dir(workspace: Workspace, target: Target, archive_id: str) -> Path:
    dirname = safe_filename(f"{target.school or 'target'}_{target.name}_{archive_id}")
    return workspace.root / "application_archives" / dirname


def _default_outcome(target: Target, stage: str) -> str:
    return "\n".join(
        [
            f"# Outcome - {target.name}",
            "",
            f"- 当前阶段：{stage}",
            f"- 创建时间：{now_iso()}",
            "- 反馈：待记录",
            "- 用户复盘：待记录",
            "- 后续校准信号：仅供 readiness score / RL 后续读取，不直接修改评分规则",
            "",
        ]
    )


def _render_outcome(target: Target, outcome: OutcomeUpdate) -> str:
    signals = "\n".join(f"- {item}" for item in outcome.calibration_signals) or "- 待补充"
    next_steps = "\n".join(f"- {item}" for item in outcome.next_steps) or "- 待补充"
    return "\n".join(
        [
            f"# Outcome - {target.name}",
            "",
            f"- 阶段：{outcome.stage}",
            f"- 日期：{outcome.outcome_date or datetime.now().date().isoformat()}",
            "",
            "## 反馈",
            outcome.feedback or "待补充",
            "",
            "## 用户复盘",
            outcome.user_reflection or "待补充",
            "",
            "## 后续可校准信号",
            signals,
            "",
            "## 下一步",
            next_steps,
            "",
            "说明：Outcome 不直接修改评分规则，只作为后续 readiness score / RL 校准输入。",
            "",
        ]
    )


def _communication_title(kind: str, advisor: Optional[AdvisorProfile]) -> str:
    advisor_name = advisor.name_zh or advisor.name_en or "老师" if advisor else "老师"
    if kind == "thank_you":
        return f"感谢交流 - {advisor_name}"
    return f"保研申请跟进 - {advisor_name}"


def _communication_content(
    target: Target,
    application: ApplicationRecord,
    profile: Optional[StudentProfile],
    advisor: Optional[AdvisorProfile],
    materials: List[GeneratedMaterial],
    request: CommunicationDraftRequest,
) -> str:
    advisor_name = advisor.name_zh or advisor.name_en or "老师" if advisor else "老师"
    display_name = _confirmed_scalar(profile, "name", "学生")
    project = _confirmed_project(profile) or "已发送材料中的科研经历"
    material_names = "、".join(item.title for item in materials[:3]) or "前次材料"
    if request.kind == "thank_you":
        body = [
            f"{advisor_name}老师您好：",
            "",
            "感谢您前次抽时间交流和指导。我会按照您的建议继续完善申请材料和科研准备。",
            f"我会重点复盘 {project} 的问题定义、方法细节和可解释结果，避免在后续沟通中泛泛表述。",
            "后续如需要补充简历、成绩单、项目摘要或其他材料，我会及时整理后发送给您。",
        ]
    else:
        body = [
            f"{advisor_name}老师您好：",
            "",
            f"我是{display_name}，此前就 {target.name} 的保研/硕博申请向您咨询过。",
            f"我想温和跟进一下前次沟通，并确认是否还需要我补充 {material_names}。",
            f"目前我仍主要围绕 {project} 做申请准备，后续会继续保持材料表述克制且可核验。",
        ]
    if request.note.strip():
        body.extend(["", f"补充说明：{request.note.strip()}"])
    body.extend(["", "感谢老师阅读。", "", display_name])
    return "\n".join(body)


def _communication_evidence(
    profile: Optional[StudentProfile],
    advisor: Optional[AdvisorProfile],
    materials: List[GeneratedMaterial],
) -> List[str]:
    refs = []
    if profile:
        refs.append(profile.profile_id)
        refs.extend(profile.source_document_ids)
    if advisor:
        refs.extend(advisor.source_ids)
    for material in materials:
        refs.append(material.material_id)
        refs.extend(material.evidence)
    return list(dict.fromkeys(ref for ref in refs if ref))


def _confirmed_scalar(
    profile: Optional[StudentProfile],
    field: str,
    fallback: str,
) -> str:
    if not profile:
        return fallback
    if profile.confirmation_map.get(field) != "confirmed":
        return fallback
    return str(getattr(profile, field, "") or fallback)


def _confirmed_project(profile: Optional[StudentProfile]) -> str:
    if not profile or profile.confirmation_map.get("projects") != "confirmed":
        return ""
    return "；".join(profile.projects[:1])


def _next_action_after_communication(kind: str) -> str:
    if kind == "thank_you":
        return "等待导师后续反馈，并整理 outcome 复盘"
    return "等待 3 天后视情况再次跟进，最多 3 次"


def _list_markdown_paths(workspace: Workspace, directory: Path) -> List[str]:
    return [_relative(workspace, path) for path in sorted(directory.glob("*.md"))]


def _relative(workspace: Workspace, path: Path) -> str:
    return path.resolve().relative_to(workspace.root).as_posix()


def _json(model) -> str:
    return json.dumps(_dump(model), ensure_ascii=False, indent=2)


def _dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
