from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from models import (
    AdvisorProfile,
    ApplicationArchive,
    ApplicationRecord,
    CommunicationDraft,
    CommunicationDraftRequest,
    EmailSignalCandidate,
    EmailSignalDecisionRequest,
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

SIGNAL_RULES = [
    (
        "offer",
        "offer",
        ["拟录取", "录取", "offer", "admitted", "congratulations"],
        "记录 offer，并准备确认录取或后续沟通。",
    ),
    ("waitlist", "waitlist", ["候补", "waitlist"], "记录候补状态，并准备补充材料或礼貌跟进。"),
    (
        "rejection",
        "rejected",
        ["未通过", "遗憾", "拒信", "reject", "not selected", "unable to offer"],
        "记录未录取结果，并沉淀复盘。",
    ),
    (
        "interview_invitation",
        "interview_scheduled",
        ["面试", "复试", "考核", "interview"],
        "确认面试安排，并准备面试材料。",
    ),
    (
        "material_request",
        "materials_preparing",
        ["补充材料", "补材料", "材料", "成绩单", "推荐信", "简历"],
        "整理对方要求的补充材料，确认后回复。",
    ),
    (
        "summer_camp_notice",
        "shortlisted",
        ["夏令营", "summer camp"],
        "记录夏令营通知，并准备参营材料。",
    ),
    (
        "pre_recommendation_interview",
        "interview",
        ["预推免", "推免面试"],
        "记录预推免信号，并准备面试或系统填报。",
    ),
    (
        "advisor_reply",
        "replied",
        ["收到", "回复", "欢迎", "可以", "保持联系", "thank", "thanks"],
        "记录导师回复，并准备下一轮沟通。",
    ),
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


def import_email_signal_candidates(
    workspace: Workspace,
    provider: str,
    raw_text: str,
    targets: List[Target],
    applications: List[ApplicationRecord],
    advisors: List[AdvisorProfile],
) -> EmailSignalSyncResult:
    provider = provider if provider in {"gmail", "qq"} else "unknown"
    messages = _split_email_messages(raw_text)
    candidates: List[EmailSignalCandidate] = []
    existing_hashes = {
        item.get("source_hash", "")
        for item in workspace.list("email_signal_candidates")
        if item.get("source_hash", "")
    }
    skipped_duplicates = 0
    for message in messages:
        candidate = _candidate_from_message(provider, message, targets, advisors)
        if not candidate:
            continue
        if candidate.source_hash in existing_hashes:
            skipped_duplicates += 1
            continue
        if candidate.target_id and _has_application(applications, candidate.target_id):
            candidate.status = "needs_user_confirmation"
        else:
            candidate.status = "needs_review"
            if not candidate.action_summary:
                candidate.action_summary = "无法稳定匹配申请目标，请人工复核。"
        workspace.write("email_signal_candidates", _dump(candidate), "candidate_id")
        candidates.append(candidate)

    return EmailSignalSyncResult(
        provider=provider,  # type: ignore[arg-type]
        configured=False,
        read_only=True,
        candidates=candidates,
        scanned_messages=len(messages),
        skipped_duplicates=skipped_duplicates,
        message=(
            f"已从粘贴/导入邮件文本中识别 {len(candidates)} 条候选信号"
            f"（跳过 {skipped_duplicates} 条重复项）；"
            "需要用户确认后才会写入 tracker / archive / outcome。"
        ),
    )


def apply_email_signal_candidate(
    workspace: Workspace,
    candidate: EmailSignalCandidate,
    target: Target,
    application: ApplicationRecord,
    decision: EmailSignalDecisionRequest,
) -> EmailSignalCandidate:
    if candidate.status == "approved":
        return candidate
    status = decision.override_status or candidate.proposed_status
    application.status = status  # type: ignore[assignment]
    application.updated_at = now_iso()
    application.next_action = candidate.action_summary or _next_action_for_signal(
        candidate.signal_type
    )
    note = (
        f"{candidate.received_at or now_iso()} 邮箱信号确认："
        f"{candidate.signal_type} / {candidate.subject} / {candidate.sender}"
    )
    if decision.user_note:
        note = f"{note}；{decision.user_note}"
    application.notes = list(dict.fromkeys(application.notes + [note]))
    workspace.write("applications", _dump(application), "application_id")

    archive = build_application_archive(
        workspace,
        target,
        application,
        [],
        stage=status,
        notes=f"邮箱候选信号确认：{candidate.subject}",
    )
    if decision.apply_to_outcome and status in {"offer", "accepted", "rejected", "waitlist"}:
        update_outcome(
            workspace,
            target,
            application,
            OutcomeUpdate(
                stage=status,
                outcome_date=candidate.received_at or datetime.now().date().isoformat(),
                feedback=candidate.evidence_summary or candidate.subject,
                user_reflection=decision.user_note,
                calibration_signals=[
                    f"email:{candidate.signal_type}:{candidate.subject}:{candidate.sender}"
                ],
                next_steps=[
                    candidate.action_summary or _next_action_for_signal(candidate.signal_type)
                ],
            ),
        )
    else:
        workspace.write("application_archives", _dump(archive), "archive_id")

    candidate.status = "approved"
    candidate.user_note = decision.user_note
    candidate.decided_at = now_iso()
    candidate.proposed_status = status
    workspace.write("email_signal_candidates", _dump(candidate), "candidate_id")
    return candidate


def reject_email_signal_candidate(
    workspace: Workspace,
    candidate: EmailSignalCandidate,
    decision: EmailSignalDecisionRequest,
) -> EmailSignalCandidate:
    candidate.status = "rejected"
    candidate.user_note = decision.user_note
    candidate.decided_at = now_iso()
    workspace.write("email_signal_candidates", _dump(candidate), "candidate_id")
    return candidate


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


def _split_email_messages(raw_text: str) -> List[dict]:
    chunks = [
        item.strip()
        for item in re.split(r"\n(?=(?:Subject|主题)\s*[:：])", raw_text or "", flags=re.I)
        if item.strip()
    ]
    if not chunks and raw_text.strip():
        chunks = [raw_text.strip()]
    return [_parse_email_message(chunk) for chunk in chunks]


def _parse_email_message(chunk: str) -> dict:
    headers = {"subject": "", "sender": "", "received_at": ""}
    body_lines = []
    for line in chunk.splitlines():
        key, value = _parse_email_header(line)
        if key:
            headers[key] = value
        else:
            body_lines.append(line)
    headers["body"] = "\n".join(body_lines).strip()
    if not headers["subject"]:
        first = next((line.strip() for line in body_lines if line.strip()), "")
        headers["subject"] = first[:80] or "未命名邮件"
    return headers


def _parse_email_header(line: str) -> tuple:
    match = re.match(r"^\s*(Subject|主题)\s*[:：]\s*(.+)$", line, flags=re.I)
    if match:
        return "subject", match.group(2).strip()
    match = re.match(r"^\s*(From|发件人)\s*[:：]\s*(.+)$", line, flags=re.I)
    if match:
        return "sender", match.group(2).strip()
    match = re.match(r"^\s*(Date|日期|时间)\s*[:：]\s*(.+)$", line, flags=re.I)
    if match:
        return "received_at", match.group(2).strip()
    return "", ""


def _candidate_from_message(
    provider: str,
    message: dict,
    targets: List[Target],
    advisors: List[AdvisorProfile],
) -> Optional[EmailSignalCandidate]:
    searchable = " ".join(
        [
            message.get("subject", ""),
            message.get("sender", ""),
            message.get("body", ""),
        ]
    ).lower()
    rule = _match_signal_rule(searchable)
    if not rule:
        return None
    signal_type, proposed_status, _keywords, action = rule
    target = _match_target(searchable, targets, advisors)
    confidence = 0.58
    if target:
        confidence += 0.25
    if message.get("subject"):
        confidence += 0.08
    if message.get("sender"):
        confidence += 0.04
    body = message.get("body", "")
    digest = hashlib.sha256(
        "\n".join(
            [
                message.get("subject", ""),
                message.get("sender", ""),
                message.get("received_at", ""),
                body,
            ]
        ).encode("utf-8")
    ).hexdigest()
    return EmailSignalCandidate(
        provider=provider,  # type: ignore[arg-type]
        target_id=target.target_id if target else "",
        target_name=target.name if target else "",
        signal_type=signal_type,
        proposed_status=proposed_status,  # type: ignore[arg-type]
        subject=message.get("subject", ""),
        sender=message.get("sender", ""),
        received_at=message.get("received_at", ""),
        body_excerpt=_excerpt(body),
        source_hash=f"sha256:{digest}",
        evidence_summary=_evidence_summary(message, signal_type),
        action_summary=action,
        confidence=min(confidence, 0.95),
    )


def _match_signal_rule(text: str):
    for rule in SIGNAL_RULES:
        if any(keyword.lower() in text for keyword in rule[2]):
            return rule
    return None


def _match_target(
    text: str,
    targets: List[Target],
    advisors: List[AdvisorProfile],
) -> Optional[Target]:
    advisor_by_id = {advisor.advisor_id: advisor for advisor in advisors}
    scored = []
    for target in targets:
        score = 0
        tokens = [
            target.name,
            target.school,
            target.college,
            target.program_name,
        ]
        advisor = advisor_by_id.get(target.advisor_id)
        if advisor:
            tokens.extend([advisor.name_zh, advisor.name_en, advisor.email, advisor.school])
        for token in tokens:
            token = (token or "").strip().lower()
            if token and token in text:
                score += max(1, min(4, len(token) // 4))
        if score:
            scored.append((score, target))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored else None


def _has_application(applications: List[ApplicationRecord], target_id: str) -> bool:
    return any(item.target_id == target_id for item in applications)


def _excerpt(body: str) -> str:
    text = re.sub(r"\s+", " ", body or "").strip()
    return text[:240]


def _evidence_summary(message: dict, signal_type: str) -> str:
    parts = [
        f"signal={signal_type}",
        f"subject={message.get('subject', '')}",
        f"from={message.get('sender', '')}",
        f"date={message.get('received_at', '')}",
    ]
    return "；".join(item for item in parts if not item.endswith("="))


def _next_action_for_signal(signal_type: str) -> str:
    for item in SIGNAL_RULES:
        if item[0] == signal_type:
            return item[3]
    return "人工复核邮件信号后更新申请状态。"


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
