from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urlparse

from llm_client import extract_advisor_profile_with_llm
from models import (
    AdvisorProfile,
    AdvisorSource,
    AdvisorSourceCreate,
    ApplicationRecord,
    GeneratedMaterial,
    MatchReport,
    MaterialQualityReport,
    ReadinessDimensionScore,
    ReadinessScoreReport,
    ReadinessTargetScore,
    StudentProfile,
    Target,
    now_iso,
)
from quality.checks import (
    profile_confirmation_map,
    usable_list_profile_field,
    usable_scalar_profile_field,
)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: List[str] = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = False

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return normalize_text("\n".join(self.parts))


def normalize_text(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_terms(text: str) -> List[str]:
    candidates = re.split(r"[，,、；;。\n/|]+", text)
    return [item.strip() for item in candidates if len(item.strip()) >= 2]


def pick_lines(text: str, tokens: List[str], limit: int = 5) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    hits = []
    for line in lines:
        if any(token in line for token in tokens) and line not in hits:
            hits.append(line[:180])
        if len(hits) >= limit:
            break
    return hits


def first_match(text: str, patterns: List[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).strip()
    return ""


def keyword_hits(text: str, keywords: List[str]) -> List[str]:
    return [kw for kw in keywords if kw and kw.lower() in text.lower()]


def values_from_llm_items(items) -> List[str]:
    values = []
    if not isinstance(items, list):
        return values
    for item in items:
        if isinstance(item, dict):
            value = str(item.get("value", "")).strip()
            evidence = str(item.get("evidence", "")).strip()
            confidence = float(item.get("confidence") or 0)
            if value and evidence and confidence >= 0.5:
                values.append(value)
        elif isinstance(item, str) and item.strip():
            values.append(item.strip())
    return list(dict.fromkeys(values))


def merge_advisor_profile_with_llm(
    advisor: AdvisorProfile, llm_data: Optional[dict], source_ids: List[str]
) -> AdvisorProfile:
    if not llm_data:
        return advisor
    data = advisor.model_dump() if hasattr(advisor, "model_dump") else advisor.dict()
    scalar_fields = [
        "name_zh",
        "name_en",
        "title",
        "school",
        "college",
        "department",
        "lab_name",
        "email",
    ]
    for field in scalar_fields:
        value = str(llm_data.get(field, "")).strip()
        if value and not data.get(field):
            data[field] = value

    list_fields = [
        "research_directions",
        "representative_papers",
        "research_projects",
        "admission_requirements",
        "preferred_student_profile",
        "recent_focus",
    ]
    for field in list_fields:
        values = values_from_llm_items(llm_data.get(field))
        merged = list(dict.fromkeys((data.get(field) or []) + values))
        data[field] = merged
        if values:
            data.setdefault("evidence_map", {})[field] = source_ids

    recruiting_status = llm_data.get("recruiting_status")
    if (
        recruiting_status in {"open", "closed", "unknown"}
        and data.get("recruiting_status") == "unknown"
    ):
        data["recruiting_status"] = recruiting_status
        if recruiting_status != "unknown":
            data.setdefault("evidence_map", {})["recruiting"] = source_ids

    risks = llm_data.get("risk_notes") if isinstance(llm_data.get("risk_notes"), list) else []
    missing = (
        llm_data.get("missing_fields") if isinstance(llm_data.get("missing_fields"), list) else []
    )
    notes = [str(item).strip() for item in risks + missing if str(item).strip()]
    data["risk_notes"] = list(dict.fromkeys((data.get("risk_notes") or []) + notes))
    data["keywords"] = list(
        dict.fromkeys((data.get("keywords") or []) + data.get("research_directions", []))
    )
    data["identity_confirmed"] = bool(
        data.get("name_zh")
        and (data.get("school") or data.get("college") or data.get("homepage_url"))
    )
    return AdvisorProfile(**data)


def validate_public_url(url: str) -> str:
    """Reject local addresses so source fetching cannot reach private services."""

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("仅支持包含域名的 HTTP/HTTPS URL")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("不允许抓取本机或局域网地址")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return parsed.geturl()
    if address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError("不允许抓取内网地址")
    return parsed.geturl()


def fetch_url_text(url: str) -> tuple[str, str]:
    url = validate_public_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GradApplyWorkflow/0.1",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read(2_000_000)
        content_type = response.headers.get("content-type", "")
    encoding = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type)
    if match:
        encoding = match.group(1)
    html = raw.decode(encoding, errors="ignore")
    parser = TextExtractor()
    parser.feed(html)
    return html, parser.text() or normalize_text(html)


def build_profile_from_text(
    text: str, source_document_ids: Optional[List[str]] = None
) -> StudentProfile:
    source_document_ids = source_document_ids or []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)
    name = "未命名学生"
    for line in lines[:8]:
        if 2 <= len(line) <= 12 and not re.search(r"\d|@|大学|学院|项目|经历", line):
            name = line
            break
    interests = keyword_hits(
        joined,
        [
            "大模型",
            "多模态",
            "机器学习",
            "深度学习",
            "计算机视觉",
            "自然语言处理",
            "智能体",
            "数据挖掘",
            "推荐系统",
        ],
    )
    skills = keyword_hits(
        joined,
        [
            "Python",
            "PyTorch",
            "TensorFlow",
            "Java",
            "C++",
            "SQL",
            "Linux",
            "LaTeX",
            "FastAPI",
            "Vue",
        ],
    )
    projects = [
        line
        for line in lines
        if any(token in line for token in ["项目", "系统", "平台", "研究", "实验"])
    ][:8]
    publications = [
        line
        for line in lines
        if any(token in line for token in ["论文", "arXiv", "会议", "期刊", "投稿"])
    ][:5]
    competitions = [
        line
        for line in lines
        if any(token in line for token in ["竞赛", "奖", "挑战杯", "互联网+"])
    ][:6]
    risks = []
    if not publications:
        risks.append("暂未识别到明确论文成果")
    if not re.search(r"GPA|绩点|排名|前\s*\d+%", joined, re.I):
        risks.append("暂未识别到明确 GPA 或排名")
    education = next((line for line in lines if "大学" in line or "学院" in line), "")
    gpa = first_match(
        joined,
        [
            r"((?:GPA|绩点)\s*[:：]?\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)",
        ],
    )
    rank = first_match(
        joined,
        [
            r"((?:排名\s*[:：]?\s*)?(?:前\s*)?\d+\s*%)",
            r"(排名\s*[:：]?\s*\d+\s*/\s*\d+)",
        ],
    )
    evidence_map = profile_evidence_map(
        source_document_ids,
        education=education,
        text=joined,
        interests=interests,
        projects=projects,
        publications=publications,
        competitions=competitions,
        skills=skills,
    )
    return StudentProfile(
        name=name,
        education=education,
        gpa=gpa,
        rank=rank,
        research_interests=interests,
        projects=projects,
        publications=publications,
        competitions=competitions,
        skills=skills,
        risks=risks,
        raw_text=joined,
        source_document_ids=source_document_ids,
        evidence_map=evidence_map,
        confirmation_map=profile_confirmation_map(
            name=name,
            education=education,
            gpa=gpa,
            rank=rank,
            interests=interests,
            projects=projects,
            publications=publications,
            competitions=competitions,
            skills=skills,
        ),
    )


def profile_evidence_map(
    source_document_ids: List[str],
    education: str,
    text: str,
    interests: List[str],
    projects: List[str],
    publications: List[str],
    competitions: List[str],
    skills: List[str],
) -> dict:
    if not source_document_ids:
        return {}
    evidence = {}
    if education:
        evidence["education"] = source_document_ids
    if re.search(r"GPA|绩点", text, re.I):
        evidence["gpa"] = source_document_ids
    if re.search(r"排名|前\s*\d+%", text, re.I):
        evidence["rank"] = source_document_ids
    if interests:
        evidence["research_interests"] = source_document_ids
    if projects:
        evidence["projects"] = source_document_ids
    if publications:
        evidence["publications"] = source_document_ids
    if competitions:
        evidence["competitions"] = source_document_ids
    if skills:
        evidence["skills"] = source_document_ids
    return evidence


def create_advisor_source(payload: AdvisorSourceCreate) -> AdvisorSource:
    raw_text = payload.manual_text.strip()
    cleaned_text = normalize_text(raw_text)
    fetch_status = "manual"
    title = payload.title
    fetch_error = ""
    if payload.url:
        try:
            raw, cleaned = fetch_url_text(payload.url)
            raw_text = raw
            cleaned_text = cleaned
            fetch_status = "success"
            title = title or payload.url
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            fetch_error = str(exc)
            fetch_status = "failed" if not raw_text else "manual"
            cleaned_text = cleaned_text or f"URL 抓取失败：{exc}"
    return AdvisorSource(
        source_type=payload.source_type,
        url=payload.url,
        title=title,
        fetch_status=fetch_status,
        content_hash=(
            f"sha256:{hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}" if raw_text else ""
        ),
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        trusted=payload.trusted,
        fetch_error=fetch_error,
    )


def parse_advisor_profile(sources: List[AdvisorSource]) -> AdvisorProfile:
    text = "\n".join(source.cleaned_text for source in sources)
    url = next((source.url for source in sources if source.url), "")
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    directions = keyword_hits(
        text,
        [
            "大模型",
            "多模态",
            "机器学习",
            "深度学习",
            "计算机视觉",
            "自然语言处理",
            "智能体",
            "知识图谱",
            "推荐系统",
            "数据挖掘",
        ],
    )
    student_type = []
    if "直博" in text or "博士" in text:
        student_type.append("direct_phd")
    if "硕士" in text or "研究生" in text:
        student_type.append("master")
    if not student_type:
        student_type.append("unknown")
    name = ""
    title = ""
    for token in split_terms(text[:500]):
        match = re.search(r"([\u4e00-\u9fa5]{2,4}?)(副教授|助理教授|教授|研究员|讲师)", token)
        if match:
            name, title = match.group(1), match.group(2)
            break
    if not title:
        title = first_match(text, [r"(副教授|助理教授|教授|研究员|讲师|博士生导师|硕士生导师)"])
    school = first_match(text, [r"([\u4e00-\u9fa5A-Za-z]+大学)", r"([\u4e00-\u9fa5A-Za-z]+研究院)"])
    college = first_match(text, [r"([\u4e00-\u9fa5A-Za-z]+学院)", r"([\u4e00-\u9fa5A-Za-z]+系)"])
    if school and college.startswith(school):
        college = college[len(school) :]
    lab_name = first_match(
        text, [r"([\u4e00-\u9fa5A-Za-z0-9]+实验室)", r"([\u4e00-\u9fa5A-Za-z0-9]+课题组)"]
    )
    for prefix in [school + college, school, college]:
        if prefix and lab_name.startswith(prefix):
            lab_name = lab_name[len(prefix) :]
    name_en = first_match(text, [r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"])
    recruiting_status = "unknown"
    if any(token in text for token in ["招收", "招生", "欢迎报考", "欢迎申请", "接收推免"]):
        recruiting_status = "open"
    if any(token in text for token in ["暂不招生", "停止招生", "名额已满"]):
        recruiting_status = "closed"
    representative_papers = pick_lines(text, ["论文", "paper", "arXiv", "会议", "期刊", "发表"], 5)
    research_projects = pick_lines(text, ["项目", "课题", "基金", "NSFC", "重点研发"], 5)
    admission_requirements = pick_lines(
        text, ["招生", "招收", "要求", "推免", "硕士", "博士", "直博"], 6
    )
    preferred_student_profile = pick_lines(
        text, ["欢迎", "希望", "要求", "基础", "能力", "编程", "数学"], 5
    )
    risk_notes = []
    if not sources:
        risk_notes.append("缺少导师来源")
    if sources and not any(source.trusted for source in sources):
        risk_notes.append("当前来源均未标记为可信")
    if not directions:
        risk_notes.append("未识别到明确研究方向")
    if not email_match:
        risk_notes.append("未识别到公开邮箱")
    source_ids = [source.source_id for source in sources]
    evidence_map = {
        "identity": source_ids if name or title or school or college else [],
        "research_directions": source_ids if directions else [],
        "recruiting": source_ids
        if recruiting_status != "unknown" or admission_requirements
        else [],
        "contact": source_ids if email_match else [],
        "papers": source_ids if representative_papers else [],
        "projects": source_ids if research_projects else [],
        "risks": source_ids if risk_notes else [],
    }
    advisor = AdvisorProfile(
        name_zh=name,
        name_en=name_en,
        title=title,
        school=school,
        college=college,
        department=college,
        lab_name=lab_name,
        homepage_url=url,
        lab_url=next(
            (source.url for source in sources if source.source_type == "lab_homepage"), ""
        ),
        scholar_url=next((source.url for source in sources if "scholar.google" in source.url), ""),
        dblp_url=next((source.url for source in sources if "dblp" in source.url), ""),
        email=email_match.group(0) if email_match else "",
        research_directions=directions,
        representative_papers=representative_papers,
        research_projects=research_projects,
        recent_focus=directions[:3],
        keywords=directions,
        recruiting_status=recruiting_status,
        student_type=student_type,
        admission_requirements=admission_requirements,
        preferred_student_profile=preferred_student_profile,
        risk_notes=risk_notes,
        identity_confirmed=bool(name and (school or college or url)),
        source_ids=source_ids,
        evidence_map=evidence_map,
    )
    try:
        llm_data = extract_advisor_profile_with_llm(text)
        return merge_advisor_profile_with_llm(advisor, llm_data, source_ids)
    except Exception as exc:
        data = advisor.model_dump() if hasattr(advisor, "model_dump") else advisor.dict()
        data["risk_notes"] = list(
            dict.fromkeys(data.get("risk_notes", []) + [f"LLM 增强解析未完成：{exc}"])
        )
        return AdvisorProfile(**data)


def make_match(
    profile: Optional[StudentProfile], target: Target, advisor: Optional[AdvisorProfile]
) -> MatchReport:
    if profile is None:
        return MatchReport(
            target_id=target.target_id,
            fit_score=0,
            tier="unknown",
            summary="尚未建立学生画像，无法进行稳妥匹配分析。",
            gaps=[
                {
                    "point": "缺少学生资料",
                    "severity": "high",
                    "suggestion": "先上传简历、成绩和科研项目材料",
                }
            ],
        )
    advisor_keywords = advisor.keywords if advisor else []
    research_interests = usable_list_profile_field(profile, "research_interests")
    projects = usable_list_profile_field(profile, "projects")
    skills = usable_list_profile_field(profile, "skills")
    publications = usable_list_profile_field(profile, "publications")
    profile_text = " ".join(research_interests + projects + skills + publications)
    overlaps = keyword_hits(profile_text, advisor_keywords)
    score = min(
        95,
        45 + len(overlaps) * 12 + len(publications) * 6 + len(projects) * 3,
    )
    if not advisor_keywords:
        tier = "unknown"
        score = min(score, 55)
    elif score >= 78:
        tier = "strong_fit"
    elif score >= 58:
        tier = "reasonable_fit"
    else:
        tier = "weak_fit"
    strengths = []
    if overlaps:
        strengths.append(
            {
                "point": f"学生经历与导师方向存在交集：{'、'.join(overlaps)}",
                "student_evidence_ids": [profile.profile_id],
                "advisor_evidence_ids": advisor.source_ids if advisor else [],
            }
        )
    gaps = []
    for risk in profile.risks:
        gaps.append(
            {"point": risk, "severity": "medium", "suggestion": "在材料中用项目贡献和实验细节补足"}
        )
    if not advisor_keywords:
        gaps.append(
            {
                "point": "导师资料不足",
                "severity": "high",
                "suggestion": "补充导师主页、实验室主页或近期论文链接",
            }
        )
    summary = {
        "strong_fit": "学生经历和导师方向匹配度较高，可作为重点准备目标。",
        "reasonable_fit": "学生经历与导师方向有相关性，适合作为稳妥准备目标。",
        "weak_fit": "当前证据支撑较弱，不建议作为主投目标。",
        "unknown": "信息不足，需补充学生或导师资料后再判断。",
    }[tier]
    return MatchReport(
        profile_id=profile.profile_id,
        target_id=target.target_id,
        fit_score=score,
        tier=tier,
        summary=summary,
        strengths=strengths,
        gaps=gaps,
        recommended_actions=[
            "准备一页科研项目摘要，突出可验证贡献",
            "套磁邮件中只陈述真实经历，避免承诺过度",
            "面试前准备项目动机、方法、结果和失败复盘",
        ],
    )


def make_contact_email(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
) -> GeneratedMaterial:
    advisor_name = advisor.name_zh or "老师" if advisor else "老师"
    directions = (
        "、".join(advisor.research_directions[:3])
        if advisor and advisor.research_directions
        else "您的研究方向"
    )
    education = usable_scalar_profile_field(profile, "education", "一名准备保研的本科生")
    projects = "；".join(usable_list_profile_field(profile, "projects")[:2]) or "相关科研项目"
    signature = usable_scalar_profile_field(profile, "name", "学生")
    subject = f"保研咨询：关于{directions}方向的硕博申请"
    body = f"""邮件标题：{subject}

{advisor_name}老师您好：

我是{education}，目前关注{directions}方向。阅读您的公开主页和招生信息后，我对课题组的研究内容很感兴趣，希望咨询硕博申请和后续科研训练的机会。

我的相关经历主要包括：{projects}。这些经历让我对问题建模、实验设计和结果分析有了初步训练，也希望在研究生阶段继续围绕相关方向深入学习。

如果您近期有招收硕士或直博学生的计划，我希望能进一步向您请教课题组的研究方向和申请要求。我可以补充发送中文简历、成绩单和一页科研项目摘要，供您参考。

感谢老师阅读，期待您的回复。

此致
敬礼
{signature}
"""
    evidence = [profile.profile_id, target.target_id]
    if advisor:
        evidence.extend(advisor.source_ids)
    if match:
        evidence.append(match.match_id)
    return GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title=subject,
        content=body,
        evidence=evidence,
    )


def make_interview_questions(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
    retriever=None,
) -> GeneratedMaterial:
    directions = advisor.research_directions if advisor else []
    rag_hits = _collect_rag_hits(
        retriever,
        _material_rag_query(profile, target, advisor),
        ["advisor_source", "policy", "student_document"],
        limit=4,
        profile=profile,
    )
    questions = [
        "请用 3 分钟介绍你的本科背景和科研经历。",
        "你最有代表性的科研/项目经历是什么？你的具体贡献是什么？",
        "这个项目中最困难的问题是什么？你如何解决？",
        "如果实验结果不理想，你会如何复盘和改进？",
        "你为什么对我们课题组感兴趣？",
    ]
    questions.extend([f"你如何理解{direction}方向的核心问题？" for direction in directions[:4]])
    if rag_hits:
        if any(getattr(hit, "source_kind", "") == "policy" for hit in rag_hits):
            questions.append("根据最新招生通知，申请流程和材料要求有哪些变化？")
        if any(getattr(hit, "source_kind", "") == "advisor_source" for hit in rag_hits):
            questions.append("你如何把自己的经历和导师近期研究方向对应起来？")
    if usable_list_profile_field(profile, "projects"):
        for risk in profile.risks:
            questions.append(f"你的材料中存在“{risk}”，如果老师追问，你会如何解释？")
    content = "\n".join(f"{idx}. {question}" for idx, question in enumerate(questions, 1))
    evidence = [profile.profile_id, target.target_id] + (advisor.source_ids if advisor else [])
    evidence.extend(
        getattr(hit, "evidence_ref", "") for hit in rag_hits if getattr(hit, "evidence_ref", "")
    )
    return GeneratedMaterial(
        target_id=target.target_id,
        material_type="interview_questions",
        title="中文面试问题清单",
        content=content,
        evidence=list(dict.fromkeys(evidence)),
    )


def make_ppt_outline(
    profile: StudentProfile,
    target: Target,
    advisor: Optional[AdvisorProfile],
    retriever=None,
) -> GeneratedMaterial:
    directions = (
        "、".join(advisor.research_directions[:3])
        if advisor and advisor.research_directions
        else "目标导师方向"
    )
    education = usable_scalar_profile_field(profile, "education", "待补充")
    grade = usable_scalar_profile_field(
        profile,
        "gpa",
        usable_scalar_profile_field(profile, "rank", "待补充"),
    )
    skills = usable_list_profile_field(profile, "skills")
    projects = usable_list_profile_field(profile, "projects")
    project = projects[0] if projects else "代表性科研/项目经历"
    display_name = usable_scalar_profile_field(profile, "name", "学生")
    rag_hits = _collect_rag_hits(
        retriever,
        _material_rag_query(profile, target, advisor),
        ["advisor_source", "policy", "student_document"],
        limit=4,
        profile=profile,
    )
    rag_note = ""
    if rag_hits:
        lines = [
            f"- {getattr(hit, 'title', '')}: {getattr(hit, 'snippet', '')}"
            for hit in rag_hits
            if getattr(hit, "title", "") or getattr(hit, "snippet", "")
        ]
        if lines:
            rag_note = "\n\n## 6. 可引用证据\n" + "\n".join(lines[:4])
    content = f"""# 5 分钟保研面试展示 PPT 大纲

## 1. 封面
- 标题：{display_name} - {target.name} 保研面试展示
- 目的：说明申请目标和展示主题
- 讲述重点：用一句话说明自己与目标方向的关系

## 2. 教育背景与能力概览
- 学校/专业：{education}
- 成绩/排名：{grade}
- 技能关键词：{"、".join(skills[:6]) or "待补充"}
- 讲述重点：突出能支撑科研训练的基础能力

## 3. 代表科研/项目经历
- 项目：{project}
- 讲述重点：问题背景、方法、个人贡献、结果和复盘
- 注意：只讲自己能解释清楚的部分

## 4. 与目标导师方向的匹配
- 导师方向：{directions}
- 匹配点：结合自己的项目、技能和兴趣说明相关性
- 讲述重点：避免泛泛表达，使用具体经历支撑

## 5. 未来研究计划与结束页
- 短期计划：补齐领域基础，阅读课题组相关论文
- 中期计划：在导师方向下寻找具体问题切入
- 结束语：表达希望进一步交流和接受指导
{rag_note}
"""
    evidence = [profile.profile_id, target.target_id] + (advisor.source_ids if advisor else [])
    evidence.extend(
        getattr(hit, "evidence_ref", "") for hit in rag_hits if getattr(hit, "evidence_ref", "")
    )
    return GeneratedMaterial(
        target_id=target.target_id,
        material_type="ppt_outline",
        title="5 分钟面试展示 PPT 大纲",
        content=content,
        evidence=list(dict.fromkeys(evidence)),
    )


def _material_rag_query(
    profile: StudentProfile, target: Target, advisor: Optional[AdvisorProfile]
) -> str:
    terms = [target.name, target.school, target.college, target.program_name]
    if advisor:
        terms.extend(advisor.research_directions[:3])
        terms.extend(advisor.admission_requirements[:3])
    terms.extend(usable_list_profile_field(profile, "projects")[:2])
    terms.extend(usable_list_profile_field(profile, "research_interests")[:2])
    return " ".join(item for item in terms if item)


def _collect_rag_hits(
    retriever,
    query: str,
    source_kinds: List[str],
    limit: int = 4,
    profile: Optional[StudentProfile] = None,
):
    if not retriever or not query.strip():
        return []
    try:
        retrieval = retriever.search(
            query,
            source_kinds=source_kinds,
            limit=limit,
            profile=profile,
        )
    except Exception:
        return []
    return list(getattr(retrieval, "hits", []) or [])


def audit_material(
    material: GeneratedMaterial,
    profile: StudentProfile,
    advisor: Optional[AdvisorProfile],
) -> MaterialQualityReport:
    """Compatibility wrapper for older imports from services."""

    from quality import audit_material as quality_audit_material

    return quality_audit_material(material, profile, advisor)


def build_workspace_report(
    profile: Optional[StudentProfile],
    targets: List[Target],
    applications: List[ApplicationRecord],
) -> dict:
    """Summarize saved work without predicting admission outcomes."""

    by_target = {item.target_id: item for item in applications}
    readiness = build_readiness_score_report(profile, targets, applications)
    lines = ["# 保研硕博申请进度报告", ""]
    lines.append(f"- 学生：{profile.name}" if profile else "- 学生资料：待补充")
    lines.append(f"- 目标数量：{len(targets)}")
    lines.append(f"- 申请准备度：{readiness.total_score} / 100（{readiness.status}）")
    lines.extend(["", "## 申请目标"])
    for target in targets:
        record = by_target.get(target.target_id)
        status = record.status if record else target.status
        action = record.next_action if record and record.next_action else "待补充下一步行动"
        lines.append(f"- {target.name}：{status}；下一步：{action}")
    if not targets:
        lines.append("- 尚未创建申请目标。")
    lines.extend(
        [
            "",
            "## 说明",
            "- 本报告仅汇总已保存资料和申请状态，不预测录取结果。",
            "- 导师资料与生成材料应在发送或提交前由用户复核。",
        ]
    )
    content = "\n".join(lines)
    return {
        "report_id": f"report_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}",
        "content": content,
        "target_count": len(targets),
        "created_at": now_iso(),
    }


def build_readiness_score_report(
    profile: Optional[StudentProfile],
    targets: List[Target],
    applications: List[ApplicationRecord],
    matches: Optional[List[MatchReport]] = None,
    materials: Optional[List[GeneratedMaterial]] = None,
    quality_reports: Optional[List[MaterialQualityReport]] = None,
    advisors: Optional[List[AdvisorProfile]] = None,
    presentation_tasks: Optional[List[dict]] = None,
    focus_target_id: str = "",
) -> ReadinessScoreReport:
    matches = matches or []
    materials = materials or []
    quality_reports = quality_reports or []
    advisors = advisors or []
    presentation_tasks = presentation_tasks or []
    by_target = {item.target_id: item for item in applications}
    match_by_target = _latest_by_target(matches, "target_id")
    advisor_by_id = {item.advisor_id: item for item in advisors}
    materials_by_target = _latest_materials_by_target(materials)
    quality_by_material = {item.material_id: item for item in quality_reports}
    presentation_by_target = _latest_by_target(presentation_tasks, "target_id")

    target_scores = [
        _build_target_readiness_score(
            profile,
            target,
            by_target.get(target.target_id),
            match_by_target.get(target.target_id),
            advisor_by_id.get(target.advisor_id),
            materials_by_target.get(target.target_id, []),
            quality_by_material,
            presentation_by_target.get(target.target_id),
        )
        for target in targets
    ]
    focus_target = next(
        (item for item in target_scores if item.target_id == focus_target_id),
        None,
    )
    if focus_target:
        dimensions = focus_target.dimensions
        total_score = focus_target.score
        status = focus_target.status
        summary = focus_target.summary
        high_priority_actions = list(focus_target.action_items)
        evidence_refs = _collect_evidence_refs(focus_target)
    else:
        dimensions = _aggregate_dimensions(target_scores, profile)
        total_score = _overall_readiness_score(target_scores, profile)
        status = _readiness_status(total_score)
        summary = _readiness_summary(total_score)
        high_priority_actions = _collect_priority_actions(target_scores, dimensions)
        evidence_refs = _collect_score_evidence_refs(target_scores, dimensions)
    fingerprint = {
        "profile_id": profile.profile_id if profile else "",
        "focus_target_id": focus_target_id,
        "total_score": total_score,
        "status": status,
        "targets": [
            {"target_id": item.target_id, "score": item.score, "status": item.status}
            for item in target_scores
        ],
        "dimensions": [
            {"name": item.name, "score": item.score, "weight": item.weight} for item in dimensions
        ],
        "actions": high_priority_actions,
    }
    score_id = f"readiness_{hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:12]}"
    return ReadinessScoreReport(
        score_id=score_id,
        profile_id=profile.profile_id if profile else "",
        scope="target" if focus_target_id else "overall",
        total_score=total_score,
        status=status,
        summary=summary,
        dimensions=dimensions,
        target_scores=target_scores,
        focus_target_id=focus_target_id,
        focus_target=focus_target,
        high_priority_actions=list(dict.fromkeys(high_priority_actions))[:8],
        evidence_refs=list(dict.fromkeys(evidence_refs))[:12],
    )


def _build_target_readiness_score(
    profile: Optional[StudentProfile],
    target: Target,
    application: Optional[ApplicationRecord],
    match: Optional[MatchReport],
    advisor: Optional[AdvisorProfile],
    materials: List[GeneratedMaterial],
    quality_by_material: dict,
    presentation_task: Optional[dict],
) -> ReadinessTargetScore:
    dimensions = [
        _profile_completeness_dimension(profile),
        _confirmation_reliability_dimension(profile),
        _target_match_dimension(match, advisor),
        _evidence_reliability_dimension(
            profile, target, advisor, match, materials, quality_by_material
        ),
        _material_quality_dimension(target, materials, quality_by_material),
        _timeline_risk_dimension(target, application),
        _interview_prep_dimension(target, materials, presentation_task),
        _workflow_completeness_dimension(
            profile, target, application, match, materials, presentation_task
        ),
    ]
    score = _weighted_score(dimensions)
    status = _readiness_status(score)
    summary = _readiness_summary(score)
    action_items = _collect_priority_actions(
        [
            ReadinessTargetScore(
                target_id=target.target_id,
                target_name=target.name,
                score=score,
                status=status,
                summary=summary,
                dimensions=dimensions,
                action_items=[],
            )
        ],
        dimensions,
    )
    return ReadinessTargetScore(
        target_id=target.target_id,
        target_name=target.name,
        score=score,
        status=status,
        summary=summary,
        dimensions=dimensions,
        action_items=list(dict.fromkeys(action_items))[:6],
        updated_at=now_iso(),
    )


def _profile_completeness_dimension(profile: Optional[StudentProfile]) -> ReadinessDimensionScore:
    field_weights = [
        ("name", 8, "姓名"),
        ("education", 14, "教育背景"),
        ("gpa", 14, "GPA"),
        ("rank", 14, "排名"),
        ("research_interests", 14, "研究兴趣"),
        ("projects", 18, "项目经历"),
        ("publications", 8, "论文成果"),
        ("competitions", 5, "竞赛奖项"),
        ("skills", 5, "技能关键词"),
    ]
    if not profile:
        return ReadinessDimensionScore(
            name="profile_completeness",
            label="学生画像完整度",
            score=0,
            weight=20,
            summary="尚未建立学生画像。",
            reasons=["没有可用的学生资料。"],
            action_items=["先上传简历、成绩单或手动粘贴原始资料。"],
        )
    total_weight = sum(weight for _, weight, _ in field_weights)
    score_sum = 0
    missing = []
    for field, weight, label in field_weights:
        value = getattr(profile, field, None)
        has_value = bool(value if not isinstance(value, list) else list(value))
        if has_value:
            score_sum += weight
        else:
            missing.append(label)
    score = round(score_sum / max(total_weight, 1) * 100)
    reasons = [f"缺少字段：{'、'.join(missing[:4])}"] if missing else ["核心字段已填写。"]
    actions = []
    if "GPA" in missing or "排名" in missing:
        actions.append("补充 GPA 和排名字段。")
    if "项目经历" in missing:
        actions.append("补充至少一个可解释的项目经历。")
    return ReadinessDimensionScore(
        name="profile_completeness",
        label="学生画像完整度",
        score=score,
        weight=20,
        summary="资料较完整" if score >= 80 else "资料还需补齐",
        reasons=reasons,
        action_items=actions or ["补齐缺失字段后再进入正式申请准备。"],
    )


def _confirmation_reliability_dimension(
    profile: Optional[StudentProfile],
) -> ReadinessDimensionScore:
    if not profile:
        return ReadinessDimensionScore(
            name="confirmation_reliability",
            label="字段确认可靠度",
            score=0,
            weight=15,
            summary="尚无字段确认信息。",
            reasons=["没有学生画像，无法判断字段确认状态。"],
            action_items=["先建立学生画像，再逐字段确认。"],
        )
    values = []
    for field, status in profile.confirmation_map.items():
        if getattr(profile, field, None):
            values.append((field, status))
    if not values:
        return ReadinessDimensionScore(
            name="confirmation_reliability",
            label="字段确认可靠度",
            score=35,
            weight=15,
            summary="暂未完成字段确认。",
            reasons=["已有资料但还未做字段级确认。"],
            action_items=["先确认 GPA、排名和项目经历。"],
        )
    status_scores = {"confirmed": 100, "unconfirmed": 72, "needs_review": 56, "rejected": 18}
    score = round(sum(status_scores.get(status, 50) for _, status in values) / len(values))
    rejected = [field for field, status in values if status == "rejected"]
    needs_review = [field for field, status in values if status == "needs_review"]
    unconfirmed = [field for field, status in values if status == "unconfirmed"]
    reasons = []
    if rejected:
        reasons.append(f"已否认字段：{'、'.join(rejected[:4])}")
    if needs_review:
        reasons.append(f"需复核字段：{'、'.join(needs_review[:4])}")
    if unconfirmed:
        reasons.append(f"未确认字段：{'、'.join(unconfirmed[:4])}")
    return ReadinessDimensionScore(
        name="confirmation_reliability",
        label="字段确认可靠度",
        score=score,
        weight=15,
        summary="确认状态较稳定" if score >= 80 else "字段确认仍需收敛",
        reasons=reasons or ["字段确认状态已建立。"],
        action_items=["优先把关键事实字段确认到 confirmed。"] if score < 80 else [],
    )


def _target_match_dimension(
    match: Optional[MatchReport],
    advisor: Optional[AdvisorProfile],
) -> ReadinessDimensionScore:
    if not match:
        return ReadinessDimensionScore(
            name="target_match",
            label="目标匹配度",
            score=20 if advisor else 0,
            weight=15,
            summary="尚未完成匹配分析。",
            reasons=["还没有可用的匹配报告。"],
            action_items=["先生成匹配分析，再把匹配点转化为材料。"],
        )
    score = max(0, min(100, match.fit_score))
    reasons = [match.summary]
    if advisor and not advisor.source_ids:
        reasons.append("导师来源证据不足。")
        score = max(0, score - 12)
    if any(gap.get("dimension") == "advisor_evidence" for gap in match.gaps):
        score = max(0, score - 8)
    if any(strength.get("dimension") == "rag_evidence" for strength in match.strengths):
        score = min(100, score + 4)
    return ReadinessDimensionScore(
        name="target_match",
        label="目标匹配度",
        score=score,
        weight=15,
        summary="有清晰匹配点" if score >= 75 else "匹配证据还不够强",
        reasons=reasons[:3],
        evidence_refs=_collect_match_evidence_refs(match),
        action_items=match.recommended_actions[:3],
    )


def _evidence_reliability_dimension(
    profile: Optional[StudentProfile],
    target: Target,
    advisor: Optional[AdvisorProfile],
    match: Optional[MatchReport],
    materials: List[GeneratedMaterial],
    quality_by_material: dict,
) -> ReadinessDimensionScore:
    profile_refs = list(profile.source_document_ids) if profile else []
    advisor_refs = list(advisor.source_ids) if advisor else []
    material_refs = [item.material_id for item in materials if item.evidence]
    match_refs = _collect_match_evidence_refs(match) if match else []
    evidence_refs = list(
        dict.fromkeys(profile_refs + advisor_refs + material_refs + match_refs + [target.target_id])
    )
    if not profile and not advisor:
        return ReadinessDimensionScore(
            name="evidence_reliability",
            label="证据可靠度",
            score=0,
            weight=12,
            summary="尚无事实来源。",
            reasons=["学生资料和导师来源都缺失。"],
            action_items=["先补学生资料和导师来源。"],
        )
    score = 45
    reasons = []
    if profile_refs:
        score += 20
        reasons.append("学生资料已绑定原始文件。")
    if advisor_refs:
        score += 20
        reasons.append("导师资料已绑定来源。")
    if match_refs:
        score += 10
        reasons.append("匹配结论包含可追溯证据。")
    if any(
        status in {"rejected", "needs_review"}
        for status in (profile.confirmation_map.values() if profile else [])
    ):
        score -= 12
        reasons.append("仍有需要复核或已否认的学生字段。")
    if any(
        isinstance(report, MaterialQualityReport) and not report.passed
        for report in quality_by_material.values()
        if getattr(report, "target_id", target.target_id) == target.target_id
    ):
        score -= 5
        reasons.append("部分材料质量检查未完全通过。")
    score = max(0, min(100, score))
    return ReadinessDimensionScore(
        name="evidence_reliability",
        label="证据可靠度",
        score=score,
        weight=12,
        summary="证据链较完整" if score >= 80 else "证据链还需补齐",
        reasons=reasons or ["事实来源已初步建立。"],
        evidence_refs=evidence_refs[:8],
        action_items=["把关键事实都绑到原始来源。"] if score < 80 else [],
    )


def _material_quality_dimension(
    target: Target,
    materials: List[GeneratedMaterial],
    quality_by_material: dict,
) -> ReadinessDimensionScore:
    if not materials:
        return ReadinessDimensionScore(
            name="material_quality",
            label="材料质量",
            score=25,
            weight=15,
            summary="尚未生成材料。",
            reasons=["还没有套磁邮件、面试问题或 PPT 大纲。"],
            action_items=["先生成套磁邮件，再补面试问题和 PPT 大纲。"],
        )
    relevant = [item for item in materials if item.target_id == target.target_id]
    if not relevant:
        return ReadinessDimensionScore(
            name="material_quality",
            label="材料质量",
            score=25,
            weight=15,
            summary="当前目标还没有材料。",
            reasons=["已有材料，但不属于当前目标。"],
            action_items=["为当前目标生成材料。"],
        )
    scores = []
    reasons = []
    actions = []
    required = {"contact_email", "interview_questions", "ppt_outline"}
    present_types = {item.material_type for item in relevant}
    for material in relevant:
        report = quality_by_material.get(material.material_id)
        if report and report.target_id != target.target_id:
            continue
        if report:
            if report.passed and report.risk_level == "low":
                scores.append(100)
            elif report.passed:
                scores.append(82)
                actions.append(f"微调 {material.material_type} 的措辞和结构。")
            elif report.risk_level == "medium":
                scores.append(56)
                actions.append(f"修订 {material.material_type} 中的风险项。")
            else:
                scores.append(34)
                actions.append(f"优先修复 {material.material_type} 的质量问题。")
            reasons.append(
                f"{material.material_type}：{('通过' if report.passed else '需复核')} / {report.risk_level}"
            )
        else:
            scores.append(58)
            reasons.append(f"{material.material_type}：尚未形成质量报告。")
    if required.issubset(present_types):
        scores.append(8)
    score = round(sum(scores) / max(len(scores), 1))
    return ReadinessDimensionScore(
        name="material_quality",
        label="材料质量",
        score=min(100, score),
        weight=15,
        summary="材料已具备初稿质量" if score >= 80 else "材料仍需修订",
        reasons=reasons[:4],
        action_items=list(dict.fromkeys(actions))[:4] or ["优先修订套磁邮件中的泛化表述。"],
    )


def _timeline_risk_dimension(
    target: Target,
    application: Optional[ApplicationRecord],
) -> ReadinessDimensionScore:
    deadline = (
        application.deadline if application and application.deadline else target.deadline
    ).strip()
    status = application.status if application else target.status
    if not deadline:
        return ReadinessDimensionScore(
            name="timeline_risk",
            label="时间线风险",
            score=60,
            weight=10,
            summary="尚未设置明确截止日期。",
            reasons=["缺少可判断的时间边界。"],
            action_items=["补充目标截止日期和关键材料节点。"],
        )
    parsed = _parse_date(deadline)
    if not parsed:
        return ReadinessDimensionScore(
            name="timeline_risk",
            label="时间线风险",
            score=55,
            weight=10,
            summary="截止日期格式待复核。",
            reasons=[f"无法解析截止日期：{deadline}"],
            action_items=["把截止日期改成标准日期格式。"],
        )
    days = (parsed.date() - datetime.now().date()).days
    if days < 0:
        score = 15
        summary = "截止日期已过。"
        actions = ["立刻复核当前目标是否还可推进。"]
    elif days <= 7:
        score = 28
        summary = "截止日期非常临近。"
        actions = ["优先完成材料定稿和提交。"]
    elif days <= 14:
        score = 48
        summary = "截止日期较近。"
        actions = ["尽快锁定材料版本并安排复核。"]
    elif days <= 30:
        score = 68
        summary = "时间仍然可控，但不能拖延。"
        actions = ["安排本周完成关键材料。"]
    else:
        score = 86
        summary = "时间较充裕。"
        actions = ["按周推进材料和联系计划。"]
    if status in {"submitted", "shortlisted", "interview_scheduled", "interview_done", "accepted"}:
        score = min(100, score + 8)
    return ReadinessDimensionScore(
        name="timeline_risk",
        label="时间线风险",
        score=score,
        weight=10,
        summary=summary,
        reasons=[f"截止日期：{deadline}", f"当前状态：{status}"],
        action_items=actions,
    )


def _interview_prep_dimension(
    target: Target,
    materials: List[GeneratedMaterial],
    presentation_task: Optional[dict],
) -> ReadinessDimensionScore:
    interview = next(
        (item for item in materials if item.material_type == "interview_questions"), None
    )
    ppt = next((item for item in materials if item.material_type == "ppt_outline"), None)
    complete_ppt = bool(presentation_task and presentation_task.get("status") == "completed")
    if not interview:
        return ReadinessDimensionScore(
            name="interview_prep",
            label="面试准备度",
            score=20 if not ppt else 45,
            weight=8,
            summary="还没有面试问题材料。",
            reasons=["缺少可练习的问题和追问清单。"],
            action_items=["先生成模拟面试题，再补讲稿。"],
        )
    score = 80
    reasons = ["已有面试问题材料。"]
    if ppt:
        score += 8
        reasons.append("PPT 大纲也已准备。")
    if complete_ppt:
        score += 8
        reasons.append("可编辑 PPTX 已生成。")
    return ReadinessDimensionScore(
        name="interview_prep",
        label="面试准备度",
        score=min(100, score),
        weight=8,
        summary="面试准备已启动" if score < 90 else "面试准备较充分",
        reasons=reasons,
        action_items=["把每个项目准备成 1 分钟、3 分钟和追问版本。"] if score < 90 else [],
    )


def _workflow_completeness_dimension(
    profile: Optional[StudentProfile],
    target: Target,
    application: Optional[ApplicationRecord],
    match: Optional[MatchReport],
    materials: List[GeneratedMaterial],
    presentation_task: Optional[dict],
) -> ReadinessDimensionScore:
    checkpoints = [
        (bool(profile), "学生资料"),
        (bool(target.advisor_id), "导师绑定"),
        (bool(match), "匹配分析"),
        (any(item.material_type == "contact_email" for item in materials), "套磁邮件"),
        (any(item.material_type == "interview_questions" for item in materials), "面试问题"),
        (any(item.material_type == "ppt_outline" for item in materials), "PPT 大纲"),
        (bool(application and application.status not in {"draft", "researching"}), "申请推进"),
        (bool(presentation_task and presentation_task.get("status") == "completed"), "PPTX"),
    ]
    hit_count = sum(1 for ok, _ in checkpoints if ok)
    score = round(hit_count / len(checkpoints) * 100)
    missing = [label for ok, label in checkpoints if not ok]
    return ReadinessDimensionScore(
        name="workflow_completeness",
        label="工作流完整度",
        score=score,
        weight=5,
        summary="主链路已较完整" if score >= 75 else "工作流还没闭合",
        reasons=[f"缺少：{'、'.join(missing[:5])}"]
        if missing
        else ["资料、匹配、材料和提交链路都已建立。"],
        action_items=["按资料 -> 匹配 -> 材料 -> 面试 -> 提交顺序补齐剩余节点。"]
        if score < 80
        else [],
    )


def _weighted_score(dimensions: List[ReadinessDimensionScore]) -> int:
    total_weight = sum(item.weight for item in dimensions) or 1
    value = sum(item.score * item.weight for item in dimensions) / total_weight
    return max(0, min(100, round(value)))


def _overall_readiness_score(
    target_scores: List[ReadinessTargetScore],
    profile: Optional[StudentProfile],
) -> int:
    if target_scores:
        return _weighted_score(
            [
                ReadinessDimensionScore(
                    name=item.target_id,
                    label=item.target_name,
                    score=item.score,
                    weight=1,
                    summary=item.summary,
                )
                for item in target_scores
            ]
        )
    if profile:
        return _profile_completeness_dimension(profile).score
    return 0


def _aggregate_dimensions(
    target_scores: List[ReadinessTargetScore],
    profile: Optional[StudentProfile],
) -> List[ReadinessDimensionScore]:
    if not target_scores:
        return [_profile_completeness_dimension(profile)]
    grouped: dict[str, List[ReadinessDimensionScore]] = {}
    for target_score in target_scores:
        for dimension in target_score.dimensions:
            grouped.setdefault(dimension.name, []).append(dimension)
    aggregated = []
    for name, dims in grouped.items():
        aggregated.append(
            ReadinessDimensionScore(
                name=name,
                label=dims[0].label,
                score=round(sum(item.score for item in dims) / len(dims)),
                weight=dims[0].weight,
                summary=dims[0].summary,
                reasons=_merge_unique([reason for item in dims for reason in item.reasons])[:4],
                evidence_refs=_merge_unique([ref for item in dims for ref in item.evidence_refs])[
                    :8
                ],
                action_items=_merge_unique(
                    [action for item in dims for action in item.action_items]
                )[:4],
            )
        )
    return sorted(aggregated, key=lambda item: item.weight, reverse=True)


def _collect_priority_actions(
    target_scores: List[ReadinessTargetScore],
    dimensions: List[ReadinessDimensionScore],
) -> List[str]:
    actions = []
    for item in dimensions:
        if item.score < 80:
            actions.extend(item.action_items)
    for target in sorted(target_scores, key=lambda item: item.score):
        if target.score < 75:
            actions.extend(target.action_items[:2])
    return _merge_unique(actions)


def _collect_score_evidence_refs(
    target_scores: List[ReadinessTargetScore],
    dimensions: List[ReadinessDimensionScore],
) -> List[str]:
    refs = []
    for item in dimensions:
        refs.extend(item.evidence_refs)
    for target in target_scores:
        refs.extend(_collect_evidence_refs(target))
    return _merge_unique(refs)


def _collect_evidence_refs(score: ReadinessTargetScore) -> List[str]:
    refs = []
    for dimension in score.dimensions:
        refs.extend(dimension.evidence_refs)
    return _merge_unique(refs)


def _collect_evidence_refs_from_dimensions(
    dimensions: List[ReadinessDimensionScore],
) -> List[str]:
    return _merge_unique([ref for dim in dimensions for ref in dim.evidence_refs])


def _collect_match_evidence_refs(match: Optional[MatchReport]) -> List[str]:
    if not match:
        return []
    refs = []
    for item in match.strengths + match.gaps:
        for key in ["evidence_refs", "student_evidence_ids", "advisor_evidence_ids"]:
            value = item.get(key) if isinstance(item, dict) else None
            if isinstance(value, list):
                refs.extend(str(entry) for entry in value if entry)
    return _merge_unique(refs)


def _latest_by_target(items, key_field: str):
    latest = {}
    for item in items:
        target_id = (
            getattr(item, key_field, None)
            if not isinstance(item, dict)
            else item.get(key_field, "")
        )
        if not target_id:
            continue
        current = latest.get(target_id)
        item_time = _item_created_at(item)
        if current is None or item_time >= _item_created_at(current):
            latest[target_id] = item
    return latest


def _latest_materials_by_target(materials: List[GeneratedMaterial]) -> dict:
    latest: dict[str, List[GeneratedMaterial]] = {}
    for material in materials:
        latest.setdefault(material.target_id, []).append(material)
    for target_id, items in latest.items():
        latest[target_id] = sorted(items, key=lambda item: item.created_at)
    return latest


def _parse_date(value: str) -> Optional[datetime]:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _item_created_at(item) -> str:
    if isinstance(item, dict):
        return str(item.get("created_at", "") or item.get("updated_at", "") or "")
    return str(getattr(item, "created_at", "") or getattr(item, "updated_at", "") or "")


def _readiness_status(score: int) -> str:
    if score >= 85:
        return "准备充分"
    if score >= 70:
        return "基本可投"
    if score >= 55:
        return "仍需补齐"
    return "准备不足"


def _readiness_summary(score: int) -> str:
    if score >= 85:
        return "资料、证据和材料链路已较完整，可以继续推进。"
    if score >= 70:
        return "当前已经具备推进条件，但还需要补几项关键缺口。"
    if score >= 55:
        return "有基础，但还不适合直接进入正式提交。"
    return "当前准备不足，建议先补齐资料和证据。"


def _merge_unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def ensure_application(
    target: Target, existing: Optional[ApplicationRecord] = None
) -> ApplicationRecord:
    if existing:
        return existing
    return ApplicationRecord(
        target_id=target.target_id,
        status=target.status,
        deadline=target.deadline,
        next_action="补充导师资料并准备套磁邮件",
    )
