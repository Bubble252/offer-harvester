from __future__ import annotations

import hashlib
import ipaddress
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urlparse

from models import (
    AdvisorProfile,
    AdvisorSource,
    AdvisorSourceCreate,
    ApplicationRecord,
    GeneratedMaterial,
    MaterialQualityReport,
    MatchReport,
    StudentProfile,
    Target,
    now_iso,
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


def keyword_hits(text: str, keywords: List[str]) -> List[str]:
    return [kw for kw in keywords if kw and kw.lower() in text.lower()]


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


def build_profile_from_text(text: str) -> StudentProfile:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)
    name = "未命名学生"
    for line in lines[:8]:
        if 2 <= len(line) <= 12 and not re.search(r"\d|@|大学|学院|项目|经历", line):
            name = line
            break
    interests = keyword_hits(
        joined,
        ["大模型", "多模态", "机器学习", "深度学习", "计算机视觉", "自然语言处理", "智能体", "数据挖掘", "推荐系统"],
    )
    skills = keyword_hits(
        joined,
        ["Python", "PyTorch", "TensorFlow", "Java", "C++", "SQL", "Linux", "LaTeX", "FastAPI", "Vue"],
    )
    projects = [
        line
        for line in lines
        if any(token in line for token in ["项目", "系统", "平台", "研究", "实验"])
    ][:8]
    publications = [line for line in lines if any(token in line for token in ["论文", "arXiv", "会议", "期刊", "投稿"])][:5]
    competitions = [line for line in lines if any(token in line for token in ["竞赛", "奖", "挑战杯", "互联网+"])][:6]
    risks = []
    if not publications:
        risks.append("暂未识别到明确论文成果")
    if not re.search(r"GPA|绩点|排名|前\s*\d+%", joined, re.I):
        risks.append("暂未识别到明确 GPA 或排名")
    return StudentProfile(
        name=name,
        education=next((line for line in lines if "大学" in line or "学院" in line), ""),
        research_interests=interests,
        projects=projects,
        publications=publications,
        competitions=competitions,
        skills=skills,
        risks=risks,
        raw_text=joined,
    )


def create_advisor_source(payload: AdvisorSourceCreate) -> AdvisorSource:
    raw_text = payload.manual_text.strip()
    cleaned_text = normalize_text(raw_text)
    fetch_status = "manual"
    title = payload.title
    if payload.url:
        try:
            raw, cleaned = fetch_url_text(payload.url)
            raw_text = raw
            cleaned_text = cleaned
            fetch_status = "success"
            title = title or payload.url
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            fetch_status = "failed" if not raw_text else "manual"
            cleaned_text = cleaned_text or f"URL 抓取失败：{exc}"
    return AdvisorSource(
        source_type=payload.source_type,
        url=payload.url,
        title=title,
        fetch_status=fetch_status,
        content_hash=(
            f"sha256:{hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}"
            if raw_text
            else ""
        ),
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        trusted=payload.trusted,
    )


def parse_advisor_profile(sources: List[AdvisorSource]) -> AdvisorProfile:
    text = "\n".join(source.cleaned_text for source in sources)
    url = next((source.url for source in sources if source.url), "")
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    directions = keyword_hits(
        text,
        ["大模型", "多模态", "机器学习", "深度学习", "计算机视觉", "自然语言处理", "智能体", "知识图谱", "推荐系统", "数据挖掘"],
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
        match = re.search(r"([\u4e00-\u9fa5]{2,4})(教授|副教授|研究员|讲师)", token)
        if match:
            name, title = match.group(1), match.group(2)
            break
    return AdvisorProfile(
        name_zh=name,
        title=title,
        homepage_url=url,
        email=email_match.group(0) if email_match else "",
        research_directions=directions,
        recent_focus=directions[:3],
        keywords=directions,
        student_type=student_type,
        source_ids=[source.source_id for source in sources],
    )


def make_match(
    profile: Optional[StudentProfile], target: Target, advisor: Optional[AdvisorProfile]
) -> MatchReport:
    if profile is None:
        return MatchReport(
            target_id=target.target_id,
            fit_score=0,
            tier="unknown",
            summary="尚未建立学生画像，无法进行稳妥匹配分析。",
            gaps=[{"point": "缺少学生资料", "severity": "high", "suggestion": "先上传简历、成绩和科研项目材料"}],
        )
    advisor_keywords = advisor.keywords if advisor else []
    profile_text = " ".join(profile.research_interests + profile.projects + profile.skills + profile.publications)
    overlaps = keyword_hits(profile_text, advisor_keywords)
    score = min(95, 45 + len(overlaps) * 12 + len(profile.publications) * 6 + len(profile.projects) * 3)
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
        gaps.append({"point": risk, "severity": "medium", "suggestion": "在材料中用项目贡献和实验细节补足"})
    if not advisor_keywords:
        gaps.append({"point": "导师资料不足", "severity": "high", "suggestion": "补充导师主页、实验室主页或近期论文链接"})
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
    directions = "、".join(advisor.research_directions[:3]) if advisor and advisor.research_directions else "您的研究方向"
    projects = "；".join(profile.projects[:2]) or "相关科研项目"
    subject = f"保研咨询：关于{directions}方向的硕博申请"
    body = f"""邮件标题：{subject}

{advisor_name}老师您好：

我是{profile.education or '一名准备保研的本科生'}，目前关注{directions}方向。阅读您的公开主页和招生信息后，我对课题组的研究内容很感兴趣，希望咨询硕博申请和后续科研训练的机会。

我的相关经历主要包括：{projects}。这些经历让我对问题建模、实验设计和结果分析有了初步训练，也希望在研究生阶段继续围绕相关方向深入学习。

如果您近期有招收硕士或直博学生的计划，我希望能进一步向您请教课题组的研究方向和申请要求。我可以补充发送中文简历、成绩单和一页科研项目摘要，供您参考。

感谢老师阅读，期待您的回复。

此致
敬礼
{profile.name}
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
    profile: StudentProfile, target: Target, advisor: Optional[AdvisorProfile]
) -> GeneratedMaterial:
    directions = advisor.research_directions if advisor else []
    questions = [
        "请用 3 分钟介绍你的本科背景和科研经历。",
        "你最有代表性的科研/项目经历是什么？你的具体贡献是什么？",
        "这个项目中最困难的问题是什么？你如何解决？",
        "如果实验结果不理想，你会如何复盘和改进？",
        "你为什么对我们课题组感兴趣？",
    ]
    questions.extend([f"你如何理解{direction}方向的核心问题？" for direction in directions[:4]])
    for risk in profile.risks:
        questions.append(f"你的材料中存在“{risk}”，如果老师追问，你会如何解释？")
    content = "\n".join(f"{idx}. {question}" for idx, question in enumerate(questions, 1))
    return GeneratedMaterial(
        target_id=target.target_id,
        material_type="interview_questions",
        title="中文面试问题清单",
        content=content,
        evidence=[profile.profile_id, target.target_id] + (advisor.source_ids if advisor else []),
    )


def make_ppt_outline(
    profile: StudentProfile, target: Target, advisor: Optional[AdvisorProfile]
) -> GeneratedMaterial:
    directions = "、".join(advisor.research_directions[:3]) if advisor and advisor.research_directions else "目标导师方向"
    project = profile.projects[0] if profile.projects else "代表性科研/项目经历"
    content = f"""# 5 分钟保研面试展示 PPT 大纲

## 1. 封面
- 标题：{profile.name} - {target.name} 保研面试展示
- 目的：说明申请目标和展示主题
- 讲述重点：用一句话说明自己与目标方向的关系

## 2. 教育背景与能力概览
- 学校/专业：{profile.education or '待补充'}
- 成绩/排名：{profile.gpa or profile.rank or '待补充'}
- 技能关键词：{'、'.join(profile.skills[:6]) or '待补充'}
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
"""
    return GeneratedMaterial(
        target_id=target.target_id,
        material_type="ppt_outline",
        title="5 分钟面试展示 PPT 大纲",
        content=content,
        evidence=[profile.profile_id, target.target_id] + (advisor.source_ids if advisor else []),
    )


def audit_material(
    material: GeneratedMaterial,
    profile: StudentProfile,
    advisor: Optional[AdvisorProfile],
) -> MaterialQualityReport:
    """Block unsupported claims from being treated as reviewed application material."""

    advisor_sources = advisor.source_ids if advisor else []
    prohibited = ["保证录取", "稳上", "必然录取", "百分之百"]
    found = [phrase for phrase in prohibited if phrase in material.content]
    profile_terms = profile.projects + profile.publications + profile.competitions
    checks = [
        {
            "name": "evidence_present",
            "passed": bool(material.evidence),
            "message": "材料已关联证据。" if material.evidence else "材料缺少可追溯证据。",
        },
        {
            "name": "advisor_source_present",
            "passed": not advisor_sources
            or any(item in advisor_sources for item in material.evidence),
            "message": "导师相关内容已关联来源。"
            if advisor_sources
            else "导师资料不足，需人工核对方向表述。",
        },
        {
            "name": "no_admission_claim",
            "passed": not found,
            "message": "未发现录取承诺。"
            if not found
            else f"发现高风险表达：{'、'.join(found)}",
        },
        {
            "name": "student_fact_anchor",
            "passed": not profile_terms
            or any(term and term in material.content for term in profile_terms),
            "message": "材料引用了学生已记录经历。"
            if profile_terms
            else "学生经历较少，建议人工核对材料。",
        },
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


def build_workspace_report(
    profile: Optional[StudentProfile],
    targets: List[Target],
    applications: List[ApplicationRecord],
) -> dict:
    """Summarize saved work without predicting admission outcomes."""

    by_target = {item.target_id: item for item in applications}
    lines = ["# 保研硕博申请进度报告", ""]
    lines.append(f"- 学生：{profile.name}" if profile else "- 学生资料：待补充")
    lines.append(f"- 目标数量：{len(targets)}")
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
