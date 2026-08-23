from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from models import (
    AdvisorProfile,
    ApplicationRecord,
    BatchTriageReport,
    GapPlan,
    GapPlanItem,
    GeneratedMaterial,
    MatchReport,
    MaterialQualityReport,
    ProfileExpansionCandidate,
    ProfileExpansionReport,
    ReadinessScoreReport,
    SourceConnectorRegistryStatus,
    StudentProfile,
    Target,
    TargetTriageItem,
)
from rag import KnowledgeBaseRetriever
from storage import Workspace

KEYWORD_POOL = [
    "大模型",
    "多模态",
    "机器学习",
    "深度学习",
    "计算机视觉",
    "自然语言处理",
    "智能体",
    "数据挖掘",
    "推荐系统",
    "RAG",
    "强化学习",
    "PyTorch",
    "Python",
    "FastAPI",
    "LaTeX",
    "SQL",
    "Linux",
]


def dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def build_batch_triage_report(
    workspace: Workspace,
    profile: Optional[StudentProfile],
    targets: list[Target],
    advisors: list[AdvisorProfile],
    applications: list[ApplicationRecord],
    matches: list[MatchReport],
    readiness: Optional[ReadinessScoreReport],
    *,
    target_ids: Optional[list[str]] = None,
) -> BatchTriageReport:
    selected_ids = set(target_ids or [])
    if selected_ids:
        targets = [target for target in targets if target.target_id in selected_ids]

    advisor_by_id = {advisor.advisor_id: advisor for advisor in advisors}
    application_by_target = {item.target_id: item for item in applications}
    match_by_target = {item.target_id: item for item in matches}
    readiness_by_target = {
        item.target_id: item for item in (readiness.target_scores if readiness else [])
    }

    items = [
        triage_target(
            profile,
            target,
            advisor_by_id.get(target.advisor_id),
            application_by_target.get(target.target_id),
            match_by_target.get(target.target_id),
            readiness_by_target.get(target.target_id),
        )
        for target in targets
    ]
    items.sort(key=lambda item: item.triage_score, reverse=True)

    report = BatchTriageReport(
        target_count=len(items),
        summary=triage_summary(items),
        items=items,
    )
    workspace.write("target_triage_reports", dump(report), "report_id")
    return report


def triage_target(
    profile: Optional[StudentProfile],
    target: Target,
    advisor: Optional[AdvisorProfile],
    application: Optional[ApplicationRecord],
    match: Optional[MatchReport],
    readiness_target,
) -> TargetTriageItem:
    strengths: list[str] = []
    gaps: list[str] = []
    hard_gates: list[str] = []
    evidence_summary: list[str] = []
    evidence_refs: list[str] = []
    actions: list[str] = []

    score = 0
    direction_score, direction_hits = direction_relevance(profile, target, advisor)
    score += direction_score
    if direction_hits:
        strengths.append(f"方向关键词有交集：{'、'.join(direction_hits[:5])}")
    else:
        gaps.append("学生兴趣/项目与目标方向暂无明显关键词交集")
        actions.append("补充目标导师方向或学生项目关键词后重新粗排")

    gate_score = 20
    if advisor and advisor.recruiting_status == "closed":
        hard_gates.append("导师招生状态为 closed")
        gate_score -= 20
    if deadline_state(target.deadline) == "passed":
        hard_gates.append("目标截止日期已过")
        gate_score -= 20
    if target.degree_track == "unknown":
        gaps.append("申请类型不确定")
        gate_score -= 5
    score += max(0, gate_score)

    urgency = deadline_state(target.deadline)
    score += {"future": 15, "soon": 9, "unknown": 7, "passed": 0}.get(urgency, 5)
    if urgency == "soon":
        gaps.append("deadline 接近，需要优先推进材料")
        actions.append("确认截止日期和材料清单")
    elif urgency == "unknown":
        gaps.append("截止日期待确认")
        actions.append("用 RAG/导师来源补齐截止日期")

    source_count = len(set((target.source_ids or []) + (advisor.source_ids if advisor else [])))
    if source_count >= 2:
        score += 15
        strengths.append("导师/项目来源证据较完整")
    elif source_count == 1:
        score += 9
        gaps.append("只有一条来源证据，建议补充学院通知或导师主页")
    else:
        gaps.append("缺少导师/项目来源证据")
        actions.append("先登记导师主页、学院通知或手动来源正文")
    evidence_refs.extend(target.source_ids or [])
    if advisor:
        evidence_refs.extend(advisor.source_ids)
    evidence_summary.append(f"来源证据 {source_count} 条")

    if match:
        score += round(match.fit_score * 0.2)
        evidence_refs.append(match.match_id)
        if match.fit_score >= 75:
            strengths.append("已有正式匹配报告显示较高匹配度")
        elif match.gaps:
            gaps.extend(
                str(gap.get("point") or gap.get("dimension") or "匹配报告存在缺口")
                for gap in match.gaps[:2]
            )
    elif readiness_target:
        score += round(readiness_target.score * 0.15)
        evidence_refs.append(readiness_target.target_id)
        evidence_summary.append("引用了目标准备度评分")
    else:
        gaps.append("尚未生成正式匹配报告")
        actions.append("对优先目标运行单目标匹配分析")

    if application and application.next_action:
        actions.append(application.next_action)

    score = max(0, min(100, score))
    if hard_gates:
        tier = "blocked"
    elif score >= 75:
        tier = "priority"
    elif score >= 55:
        tier = "watch"
    else:
        tier = "hold"

    if not actions:
        actions.append("进入单目标详情页复核证据并准备材料")

    return TargetTriageItem(
        target_id=target.target_id,
        target_name=target.name,
        triage_score=score,
        tier=tier,
        strengths=list(dict.fromkeys(strengths)),
        gaps=list(dict.fromkeys(gaps)),
        hard_gates=list(dict.fromkeys(hard_gates)),
        deadline_urgency=urgency,
        evidence_summary=evidence_summary,
        evidence_refs=list(dict.fromkeys(evidence_refs)),
        recommended_next_actions=list(dict.fromkeys(actions))[:5],
    )


def direction_relevance(
    profile: Optional[StudentProfile], target: Target, advisor: Optional[AdvisorProfile]
) -> tuple[int, list[str]]:
    profile_text = " ".join(
        (profile.research_interests if profile else [])
        + (profile.projects if profile else [])
        + (profile.skills if profile else [])
    )
    target_text = " ".join(
        [
            target.name,
            target.program_name,
            target.school,
            target.college,
            " ".join(advisor.research_directions if advisor else []),
            " ".join(advisor.keywords if advisor else []),
            " ".join(advisor.preferred_student_profile if advisor else []),
        ]
    )
    hits = [
        kw
        for kw in KEYWORD_POOL
        if kw.lower() in profile_text.lower() and kw.lower() in target_text.lower()
    ]
    score = min(30, len(hits) * 9)
    if score == 0 and profile_text and target_text:
        shared = set(tokenize_terms(profile_text)) & set(tokenize_terms(target_text))
        hits = sorted(shared)[:5]
        score = min(18, len(hits) * 4)
    return score, hits


def deadline_state(value: str) -> str:
    if not value:
        return "unknown"
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return "unknown"
    days = (parsed - datetime.now().date()).days
    if days < 0:
        return "passed"
    if days <= 14:
        return "soon"
    return "future"


def triage_summary(items: list[TargetTriageItem]) -> str:
    if not items:
        return "目标池为空，先新增导师、实验室或项目目标。"
    counts = Counter(item.tier for item in items)
    return (
        f"共粗排 {len(items)} 个目标：priority {counts['priority']} 个，"
        f"watch {counts['watch']} 个，hold {counts['hold']} 个，blocked {counts['blocked']} 个。"
        "该结果仅用于初筛，不能替代单目标深度匹配。"
    )


def build_profile_expansion_report(
    workspace: Workspace,
    profile: Optional[StudentProfile],
) -> ProfileExpansionReport:
    candidates: list[ProfileExpansionCandidate] = []
    profile_id = profile.profile_id if profile else ""
    existing = current_profile_values(profile)
    sources = profile_expansion_sources(workspace, profile)

    for source_type, source_ref, text in sources:
        parsed = parse_candidate_fields(text)
        for field_name, values in parsed.items():
            for value in values:
                if value in existing.get(field_name, set()):
                    continue
                inferred = field_name in {"skills", "research_interests"}
                candidate = ProfileExpansionCandidate(
                    profile_id=profile_id,
                    field_name=field_name,
                    value=value,
                    source_type=source_type,
                    source_ref=source_ref,
                    inference_method="keyword_extract" if inferred else "line_extract",
                    confidence=0.58 if inferred else 0.72,
                    status="unconfirmed",
                    inferred=inferred,
                    evidence_refs=[source_ref] if source_ref else [],
                    notes="候选字段不会自动写入正式 profile，需要用户确认。",
                )
                candidates.append(candidate)

    deduped = dedupe_candidates(candidates)
    report = ProfileExpansionReport(
        profile_id=profile_id,
        candidate_count=len(deduped),
        candidates=deduped,
        blocked_rules=[
            "网页补充学生资料不得直接覆盖本地资料",
            "候选字段默认 unconfirmed，用户确认后才可写入 StudentProfile",
            "行为/软技能推断必须标记 inferred",
        ],
        summary=f"识别到 {len(deduped)} 个画像扩展候选，均需人工确认。",
    )
    workspace.write("profile_expansion_candidates", dump(report), "report_id")
    return report


def profile_expansion_sources(
    workspace: Workspace, profile: Optional[StudentProfile]
) -> list[tuple[str, str, str]]:
    sources: list[tuple[str, str, str]] = []
    if profile and profile.raw_text:
        sources.append(("profile_raw_text", profile.profile_id, profile.raw_text))

    manifest = workspace.read_user_document_manifest()
    for record in manifest.get("documents", []):
        relative = record.get("path") or ""
        path = (workspace.root / relative).resolve()
        if not path.is_file() or workspace.root not in path.parents:
            continue
        if path.suffix.lower() not in {".txt", ".md", ".json", ".csv"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        source_type = str(record.get("source_type") or record.get("category") or "user_document")
        sources.append((source_type, str(record.get("document_id") or relative), text))

    kb_manifest = workspace.knowledge_base_manifest_path()
    if kb_manifest.exists():
        try:
            manifest_data = json.loads(kb_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest_data = {"sources": []}
        for source in manifest_data.get("sources", []):
            if source.get("source_kind") not in {"web_url", "manual_text", "student_document"}:
                continue
            source_id = source.get("source_id", "")
            text_path = workspace.knowledge_base_sources_dir() / f"{source_id}.txt"
            if text_path.exists():
                sources.append(
                    (
                        str(source.get("source_kind") or "knowledge_base"),
                        str(source_id),
                        text_path.read_text(encoding="utf-8", errors="ignore"),
                    )
                )
    return sources


def parse_candidate_fields(text: str) -> dict[str, list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result: dict[str, list[str]] = {
        "research_interests": [],
        "skills": [],
        "projects": [],
        "publications": [],
        "competitions": [],
    }
    for keyword in KEYWORD_POOL:
        if keyword.lower() in text.lower():
            field = (
                "skills"
                if keyword in {"Python", "PyTorch", "FastAPI", "LaTeX", "SQL", "Linux"}
                else "research_interests"
            )
            result[field].append(keyword)
    for line in lines:
        if any(token in line for token in ["项目", "系统", "平台", "研究"]) and len(line) <= 180:
            result["projects"].append(line)
        if (
            any(token in line for token in ["论文", "arXiv", "会议", "期刊", "投稿"])
            and len(line) <= 180
        ):
            result["publications"].append(line)
        if any(token in line for token in ["竞赛", "奖", "挑战杯", "互联网+"]) and len(line) <= 180:
            result["competitions"].append(line)
    return {field: list(dict.fromkeys(values))[:8] for field, values in result.items()}


def current_profile_values(profile: Optional[StudentProfile]) -> dict[str, set[str]]:
    if not profile:
        return {}
    return {
        "research_interests": set(profile.research_interests),
        "skills": set(profile.skills),
        "projects": set(profile.projects),
        "publications": set(profile.publications),
        "competitions": set(profile.competitions),
    }


def dedupe_candidates(
    candidates: Iterable[ProfileExpansionCandidate],
) -> list[ProfileExpansionCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[ProfileExpansionCandidate] = []
    for candidate in candidates:
        key = (candidate.field_name, candidate.value)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def build_gap_plan(
    workspace: Workspace,
    target: Target,
    profile: Optional[StudentProfile],
    advisor: Optional[AdvisorProfile],
    application: Optional[ApplicationRecord],
    match: Optional[MatchReport],
    readiness: Optional[ReadinessScoreReport],
    quality_reports: list[MaterialQualityReport],
    materials: list[GeneratedMaterial],
    retriever: Optional[KnowledgeBaseRetriever] = None,
) -> GapPlan:
    readiness_target = None
    if readiness:
        readiness_target = next(
            (item for item in readiness.target_scores if item.target_id == target.target_id),
            None,
        )
    gaps: list[GapPlanItem] = []

    if match:
        for gap in match.gaps[:5]:
            title = str(gap.get("point") or gap.get("dimension") or "匹配分析存在缺口")
            gaps.append(
                GapPlanItem(
                    category="profile_gap",
                    title=title,
                    source="match_report",
                    severity="medium",
                    evidence_refs=[match.match_id],
                    actions=[str(gap.get("suggestion") or "补充对应证据后重新生成匹配分析")],
                )
            )
    else:
        gaps.append(
            GapPlanItem(
                category="profile_gap",
                title="尚未生成单目标匹配报告",
                source="workflow_state",
                severity="medium",
                actions=["先运行匹配分析，再针对 gaps 补材料"],
            )
        )

    if advisor and advisor.admission_requirements:
        profile_text = " ".join(
            (profile.projects if profile else [])
            + (profile.publications if profile else [])
            + (profile.skills if profile else [])
            + [profile.gpa if profile else "", profile.rank if profile else ""]
        )
        for requirement in advisor.admission_requirements[:5]:
            if not any(term in profile_text for term in tokenize_terms(requirement)):
                gaps.append(
                    GapPlanItem(
                        category="advisor_requirement",
                        title=f"导师/项目要求待对齐：{requirement}",
                        source="advisor_profile",
                        severity="medium",
                        evidence_refs=advisor.source_ids,
                        actions=["准备一段可证据化回应，或确认该要求是否为硬门槛"],
                    )
                )
    elif not advisor or not advisor.source_ids:
        gaps.append(
            GapPlanItem(
                category="source_quality",
                title="导师来源不足，要求和招生状态不可靠",
                source="advisor_sources",
                severity="high",
                actions=["补充导师主页、学院通知或招生简章正文"],
            )
        )

    failed_quality = [
        report
        for report in quality_reports
        if report.target_id == target.target_id and not report.passed
    ]
    for report in failed_quality[:4]:
        messages = [
            str(item.get("message", "")) for item in report.checks if not item.get("passed")
        ]
        gaps.append(
            GapPlanItem(
                category="material_audit",
                title="材料质量检查存在风险",
                source="quality_report",
                severity="high" if report.risk_level == "high" else "medium",
                evidence_refs=[report.quality_id, report.material_id],
                actions=messages[:3] or ["根据 quality report 修改材料"],
            )
        )

    if not any(item.material_type == "interview_questions" for item in materials):
        gaps.append(
            GapPlanItem(
                category="interview_prep",
                title="尚未生成面试问答准备材料",
                source="generated_materials",
                severity="low",
                actions=["生成面试问题并补充项目可解释版本"],
            )
        )

    urgency = deadline_state(target.deadline or (application.deadline if application else ""))
    if urgency in {"soon", "unknown", "passed"}:
        gaps.append(
            GapPlanItem(
                category="deadline_risk",
                title={
                    "soon": "deadline 接近",
                    "unknown": "deadline 未确认",
                    "passed": "deadline 已过",
                }[urgency],
                source="application_deadline",
                severity="high" if urgency != "unknown" else "medium",
                actions=["确认最新通知中的截止日期和材料清单"],
            )
        )

    resource_refs = []
    if retriever:
        query = f"{target.school} {target.college} 推免 保研 截止日期 材料 流程"
        hits = retriever.search(
            query,
            source_kinds=["policy", "web_url", "manual_text"],
            limit=3,
            include_unconfirmed=True,
        ).hits
        resource_refs = [hit.evidence_ref for hit in hits]
        resource_links = [hit.url for hit in hits if hit.url]
        snippets = [hit.snippet for hit in hits if hit.snippet]
        if hits:
            gaps.append(
                GapPlanItem(
                    category="policy_resource",
                    title="可引用的保研流程/材料资源",
                    source="rag",
                    severity="low",
                    evidence_refs=resource_refs,
                    actions=snippets[:3],
                    resource_links=resource_links,
                )
            )

    heatmap = heatmap_from_gaps(gaps)
    next_actions = next_actions_from_gaps(gaps)
    plan = GapPlan(
        target_id=target.target_id,
        target_name=target.name,
        readiness_score=readiness_target.score if readiness_target else 0,
        heatmap=heatmap,
        gaps=gaps,
        summary=f"识别到 {len(gaps)} 个待处理 gap，优先处理高风险项和 deadline。",
        next_actions=next_actions,
    )
    workspace.write("gap_plans", dump(plan), "plan_id")
    return plan


def heatmap_from_gaps(gaps: list[GapPlanItem]) -> dict[str, int]:
    weights = {"low": 1, "medium": 2, "high": 3}
    heatmap: dict[str, int] = {}
    for gap in gaps:
        heatmap[gap.category] = heatmap.get(gap.category, 0) + weights.get(gap.severity, 2)
    return heatmap


def next_actions_from_gaps(gaps: list[GapPlanItem]) -> list[str]:
    ranked = sorted(
        gaps, key=lambda item: {"high": 3, "medium": 2, "low": 1}[item.severity], reverse=True
    )
    actions: list[str] = []
    for gap in ranked:
        actions.extend(gap.actions)
        if len(actions) >= 6:
            break
    return list(dict.fromkeys(actions))[:6]


def source_connector_registry_status() -> SourceConnectorRegistryStatus:
    return SourceConnectorRegistryStatus(
        supported_source_types=[
            "school_homepage",
            "college_notice",
            "advisor_homepage",
            "admission_system",
        ],
        access_policy="第一版仅保留连接器骨架；不绕过登录、验证码、付费墙、robots/ToS 或明确禁止自动访问的来源。",
        implemented=False,
    )


def tokenize_terms(text: str) -> list[str]:
    return [
        item
        for item in re.split(r"[\s，,、；;。:：/|（）()《》<>]+", text)
        if len(item.strip()) >= 2
    ]


def collection_as(workspace: Workspace, collection: str, model):
    return [model(**item) for item in workspace.list(collection)]


def latest_typed(workspace: Workspace, collection: str, model):
    item = workspace.latest(collection)
    return model(**item) if item else None


def path_exists(path: Path) -> bool:
    return path.exists()
