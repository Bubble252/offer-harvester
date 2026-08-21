from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


ProfileConfirmationStatus = Literal["unconfirmed", "confirmed", "rejected", "needs_review"]


class StudentProfile(BaseModel):
    profile_id: str = Field(default_factory=lambda: new_id("profile"))
    name: str = "未命名学生"
    education: str = ""
    gpa: str = ""
    rank: str = ""
    research_interests: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    competitions: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    raw_text: str = ""
    source_document_ids: List[str] = Field(default_factory=list)
    evidence_map: Dict[str, List[str]] = Field(default_factory=dict)
    confirmation_map: Dict[str, ProfileConfirmationStatus] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=now_iso)


class AdvisorSourceCreate(BaseModel):
    advisor_id: str = ""
    source_type: Literal[
        "advisor_homepage",
        "lab_homepage",
        "admission_notice",
        "publication_page",
        "manual_text",
        "school_profile",
        "other",
    ] = "advisor_homepage"
    url: str = ""
    manual_text: str = ""
    title: str = ""
    trusted: bool = True


class UserDocumentRecord(BaseModel):
    document_id: str = Field(default_factory=lambda: new_id("doc"))
    category: str = "manual_inputs"
    path: str
    original_filename: str = ""
    source_type: Literal["local_upload", "manual_input", "web_supplement"] = "manual_input"
    content_hash: str = ""
    uploaded_at: str = Field(default_factory=now_iso)
    trusted: bool = True
    confirmed: bool = False
    notes: str = ""


class UserDocumentManifest(BaseModel):
    documents: List[UserDocumentRecord] = Field(default_factory=list)


class AdvisorSource(BaseModel):
    source_id: str = Field(default_factory=lambda: new_id("src"))
    source_type: str = "advisor_homepage"
    url: str = ""
    title: str = ""
    fetch_status: Literal["success", "failed", "manual"] = "manual"
    fetched_at: str = Field(default_factory=now_iso)
    content_hash: str = ""
    raw_text: str = ""
    cleaned_text: str = ""
    language: str = "zh"
    trusted: bool = True
    fetch_error: str = ""
    notes: str = ""


class AdvisorProfile(BaseModel):
    advisor_id: str = Field(default_factory=lambda: new_id("advisor"))
    name_zh: str = ""
    name_en: str = ""
    title: str = ""
    school: str = ""
    college: str = ""
    department: str = ""
    lab_name: str = ""
    homepage_url: str = ""
    lab_url: str = ""
    scholar_url: str = ""
    dblp_url: str = ""
    email: str = ""
    education: str = ""
    career: List[str] = Field(default_factory=list)
    honors: List[str] = Field(default_factory=list)
    research_directions: List[str] = Field(default_factory=list)
    representative_papers: List[str] = Field(default_factory=list)
    research_projects: List[str] = Field(default_factory=list)
    recent_focus: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    recruiting_status: Literal["open", "closed", "unknown"] = "unknown"
    student_type: List[str] = Field(default_factory=list)
    admission_requirements: List[str] = Field(default_factory=list)
    preferred_student_profile: List[str] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    identity_confirmed: bool = False
    source_ids: List[str] = Field(default_factory=list)
    evidence_map: Dict[str, List[str]] = Field(default_factory=dict)
    last_verified_at: str = Field(default_factory=now_iso)


class AdvisorProfileUpdate(BaseModel):
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    title: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    department: Optional[str] = None
    lab_name: Optional[str] = None
    homepage_url: Optional[str] = None
    lab_url: Optional[str] = None
    scholar_url: Optional[str] = None
    dblp_url: Optional[str] = None
    email: Optional[str] = None
    education: Optional[str] = None
    career: Optional[List[str]] = None
    honors: Optional[List[str]] = None
    research_directions: Optional[List[str]] = None
    representative_papers: Optional[List[str]] = None
    research_projects: Optional[List[str]] = None
    recent_focus: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    recruiting_status: Optional[Literal["open", "closed", "unknown"]] = None
    student_type: Optional[List[str]] = None
    admission_requirements: Optional[List[str]] = None
    preferred_student_profile: Optional[List[str]] = None
    risk_notes: Optional[List[str]] = None
    identity_confirmed: Optional[bool] = None


class TargetCreate(BaseModel):
    name: str = ""
    target_type: Literal["advisor", "lab", "program"] = "advisor"
    advisor_id: str = ""
    school: str = ""
    college: str = ""
    program_name: str = ""
    degree_track: Literal["master", "phd", "direct_phd", "unknown"] = "unknown"
    application_round: Literal[
        "summer_camp", "pre_recommendation", "final_recommendation", "other"
    ] = "summer_camp"
    deadline: str = ""
    source_ids: List[str] = Field(default_factory=list)


class AdvisorTargetCreate(BaseModel):
    name: str = ""
    degree_track: Literal["master", "phd", "direct_phd", "unknown"] = "unknown"
    application_round: Literal[
        "summer_camp", "pre_recommendation", "final_recommendation", "other"
    ] = "summer_camp"
    deadline: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    next_action: str = ""


class Target(BaseModel):
    target_id: str = Field(default_factory=lambda: new_id("target"))
    name: str
    target_type: str = "advisor"
    advisor_id: str = ""
    school: str = ""
    college: str = ""
    program_name: str = ""
    degree_track: str = "unknown"
    application_round: str = "summer_camp"
    deadline: str = ""
    contact_required: bool = True
    materials_required: List[str] = Field(
        default_factory=lambda: ["中文简历", "成绩单", "科研项目介绍", "个人陈述"]
    )
    status: str = "researching"
    priority: Literal["high", "medium", "low"] = "medium"
    source_ids: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class MatchReport(BaseModel):
    match_id: str = Field(default_factory=lambda: new_id("match"))
    profile_id: str = ""
    target_id: str
    fit_score: int
    tier: Literal["strong_fit", "reasonable_fit", "weak_fit", "unknown"]
    summary: str
    strengths: List[Dict[str, Any]] = Field(default_factory=list)
    gaps: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class GeneratedMaterial(BaseModel):
    material_id: str = Field(default_factory=lambda: new_id("mat"))
    target_id: str
    material_type: str
    title: str
    content: str
    evidence: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class ApplicationRecord(BaseModel):
    application_id: str = Field(default_factory=lambda: new_id("app"))
    target_id: str
    status: str = "researching"
    deadline: str = ""
    last_contact_at: str = ""
    next_action: str = ""
    materials: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class ApplicationUpdate(BaseModel):
    status: Optional[
        Literal[
            "draft",
            "researching",
            "ready_to_contact",
            "contacted",
            "replied",
            "materials_preparing",
            "submitted",
            "shortlisted",
            "interview_scheduled",
            "interview_done",
            "accepted",
            "rejected",
            "withdrawn",
        ]
    ] = None
    deadline: Optional[str] = None
    last_contact_at: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[List[str]] = None


class MaterialQualityReport(BaseModel):
    quality_id: str = Field(default_factory=lambda: new_id("quality"))
    material_id: str
    target_id: str
    passed: bool
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    created_at: str = Field(default_factory=now_iso)


class MaterialVersion(BaseModel):
    version_id: str = Field(default_factory=lambda: new_id("matver"))
    material_id: str
    target_id: str
    material_type: str
    stage: Literal["draft", "reviewed", "user_edited", "final"] = "draft"
    content: str
    source_run_id: str = ""
    notes: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class AgentRun(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    target_id: str
    workflow: str
    status: Literal["running", "completed", "failed"] = "running"
    input_summary: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Dict[str, Any] = Field(default_factory=dict)
    risk_tags: List[str] = Field(default_factory=list)
    error: str = ""
    started_at: str = Field(default_factory=now_iso)
    ended_at: str = ""


class WorkflowEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    run_id: str
    target_id: str
    workflow: str
    event_type: Literal[
        "workflow_started",
        "draft_started",
        "draft_completed",
        "review_started",
        "review_completed",
        "audit_started",
        "audit_completed",
        "quality_completed",
        "final_saved",
        "workflow_failed",
    ]
    status: Literal["started", "completed", "failed"] = "completed"
    agent_name: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class PresentationGenerationRequest(BaseModel):
    outline_material_id: str = ""


class PresentationTaskRecord(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("ppt_task"))
    target_id: str
    outline_material_id: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    progress: int = 0
    output_filename: str = ""
    message: str = ""
    error: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
