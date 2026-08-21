from __future__ import annotations

import re
from typing import List

from models import StudentProfile

PROFILE_FIELD_LABELS = {
    "name": "姓名",
    "education": "教育背景",
    "gpa": "GPA",
    "rank": "排名",
    "research_interests": "研究兴趣",
    "projects": "项目经历",
    "publications": "论文成果",
    "competitions": "竞赛奖项",
    "skills": "技能关键词",
}


def profile_confirmation_map(
    name: str,
    education: str,
    gpa: str,
    rank: str,
    interests: List[str],
    projects: List[str],
    publications: List[str],
    competitions: List[str],
    skills: List[str],
) -> dict:
    values = {
        "name": name if name != "未命名学生" else "",
        "education": education,
        "gpa": gpa,
        "rank": rank,
        "research_interests": interests,
        "projects": projects,
        "publications": publications,
        "competitions": competitions,
        "skills": skills,
    }
    return {field: "unconfirmed" for field, value in values.items() if value}


def profile_field_status(profile: StudentProfile, field: str) -> str:
    return profile.confirmation_map.get(field, "unconfirmed")


def usable_scalar_profile_field(profile: StudentProfile, field: str, fallback: str = "") -> str:
    if profile_field_status(profile, field) == "rejected":
        return fallback
    return str(getattr(profile, field, "") or fallback)


def usable_list_profile_field(profile: StudentProfile, field: str) -> List[str]:
    if profile_field_status(profile, field) == "rejected":
        return []
    return list(getattr(profile, field, []) or [])


def profile_fields_used_in_content(profile: StudentProfile, content: str) -> List[str]:
    used = []
    scalar_values = {
        "name": profile.name if profile.name != "未命名学生" else "",
        "education": profile.education,
        "gpa": profile.gpa,
        "rank": profile.rank,
    }
    for field, value in scalar_values.items():
        if value and value in content:
            used.append(field)

    if ("GPA" in content or "绩点" in content) and profile.gpa and "gpa" not in used:
        used.append("gpa")
    if (
        ("排名" in content or re.search(r"前\s*\d+\s*%", content))
        and profile.rank
        and "rank" not in used
    ):
        used.append("rank")

    for field in [
        "research_interests",
        "projects",
        "publications",
        "competitions",
        "skills",
    ]:
        values = getattr(profile, field, []) or []
        if any(value and value in content for value in values):
            used.append(field)
    return list(dict.fromkeys(used))


def profile_confirmation_issues(
    profile: StudentProfile, content: str
) -> tuple[List[str], List[str]]:
    used_fields = profile_fields_used_in_content(profile, content)
    rejected = [
        PROFILE_FIELD_LABELS.get(field, field)
        for field in used_fields
        if profile.confirmation_map.get(field) == "rejected"
    ]
    needs_confirmation = [
        PROFILE_FIELD_LABELS.get(field, field)
        for field in used_fields
        if profile.confirmation_map.get(field, "unconfirmed") in {"unconfirmed", "needs_review"}
    ]
    return rejected, needs_confirmation
