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


class KnowledgeBaseSourceCreate(BaseModel):
    source_kind: Literal[
        "student_document", "advisor_source", "policy", "manual_text", "web_url"
    ] = "manual_text"
    source_subtype: str = ""
    title: str = ""
    text: str = ""
    url: str = ""
    source_ref: str = ""
    valid_for_year: Optional[int] = None
    trusted: bool = True
    confirmed: bool = False
    notes: str = ""


class KnowledgeBaseSource(BaseModel):
    source_id: str = Field(default_factory=lambda: new_id("kb"))
    source_kind: Literal[
        "student_document", "advisor_source", "policy", "manual_text", "web_url"
    ] = "manual_text"
    source_subtype: str = ""
    title: str = ""
    url: str = ""
    source_ref: str = ""
    raw_text: str = ""
    cleaned_text: str = ""
    content_hash: str = ""
    valid_for_year: Optional[int] = None
    fetched_at: str = Field(default_factory=now_iso)
    trusted: bool = True
    confirmed: bool = False
    notes: str = ""


class RAGChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: new_id("chunk"))
    source_id: str
    source_kind: str = ""
    source_subtype: str = ""
    title: str = ""
    section_path: List[str] = Field(default_factory=list)
    text: str = ""
    token_count: int = 0
    url: str = ""
    fetched_at: str = Field(default_factory=now_iso)
    content_hash: str = ""
    trusted: bool = True
    confirmed: bool = False
    valid_for_year: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGSearchHit(BaseModel):
    source_id: str
    chunk_id: str
    source_kind: str = ""
    source_subtype: str = ""
    title: str = ""
    url: str = ""
    fetched_at: str = ""
    content_hash: str = ""
    valid_for_year: Optional[int] = None
    score: float = 0.0
    keyword_score: float = 0.0
    vector_score: float = 0.0
    rerank_score: float = 0.0
    confidence: float = 0.0
    snippet: str = ""
    evidence_ref: str = ""
    retrieval_explanation: str = ""
    needs_confirmation: bool = False
    historical: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


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


LifecycleStatus = Literal[
    "draft",
    "drafted",
    "researching",
    "ready_to_contact",
    "contacted",
    "replied",
    "materials_preparing",
    "submitted",
    "shortlisted",
    "interview",
    "interview_scheduled",
    "interview_done",
    "waitlist",
    "offer",
    "accepted",
    "rejected",
    "no_response",
    "withdrawn",
]


class ApplicationUpdate(BaseModel):
    status: Optional[LifecycleStatus] = None
    deadline: Optional[str] = None
    last_contact_at: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[List[str]] = None


class ApplicationArchiveRequest(BaseModel):
    material_ids: List[str] = Field(default_factory=list)
    stage: LifecycleStatus = "drafted"
    notes: str = ""


class ApplicationArchive(BaseModel):
    archive_id: str = Field(default_factory=lambda: new_id("archive"))
    target_id: str
    target_name: str = ""
    stage: LifecycleStatus = "drafted"
    archive_path: str = ""
    target_snapshot_path: str = ""
    application_snapshot_path: str = ""
    submitted_material_paths: List[str] = Field(default_factory=list)
    communication_paths: List[str] = Field(default_factory=list)
    outcome_path: str = ""
    lessons_path: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class OutcomeUpdate(BaseModel):
    stage: LifecycleStatus = "submitted"
    outcome_date: str = ""
    feedback: str = ""
    user_reflection: str = ""
    calibration_signals: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


class CommunicationDraftRequest(BaseModel):
    kind: Literal["follow_up", "thank_you"] = "follow_up"
    source_material_ids: List[str] = Field(default_factory=list)
    note: str = ""


class CommunicationDraft(BaseModel):
    communication_id: str = Field(default_factory=lambda: new_id("comm"))
    target_id: str
    kind: Literal["follow_up", "thank_you"] = "follow_up"
    title: str = ""
    content: str = ""
    source_material_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    archive_path: str = ""
    status: Literal["draft"] = "draft"
    created_at: str = Field(default_factory=now_iso)


class EmailSignalCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("emailsig"))
    provider: Literal["gmail", "qq", "unknown"] = "unknown"
    target_id: str = ""
    target_name: str = ""
    signal_type: str = ""
    proposed_status: LifecycleStatus = "replied"
    subject: str = ""
    sender: str = ""
    received_at: str = ""
    body_excerpt: str = ""
    source_hash: str = ""
    evidence_summary: str = ""
    action_summary: str = ""
    confidence: float = 0.0
    status: Literal["needs_user_confirmation", "approved", "rejected", "needs_review"] = (
        "needs_user_confirmation"
    )
    user_note: str = ""
    created_at: str = Field(default_factory=now_iso)
    decided_at: str = ""


class EmailSignalImportRequest(BaseModel):
    provider: Literal["gmail", "qq", "unknown"] = "unknown"
    raw_text: str = ""


class EmailSignalDecisionRequest(BaseModel):
    user_note: str = ""
    apply_to_outcome: bool = True
    override_status: Optional[LifecycleStatus] = None


class EmailSignalSyncResult(BaseModel):
    provider: Literal["gmail", "qq", "unknown"] = "unknown"
    configured: bool = False
    read_only: bool = True
    candidates: List[EmailSignalCandidate] = Field(default_factory=list)
    message: str = ""
    created_at: str = Field(default_factory=now_iso)


class PipelineSyncRequest(BaseModel):
    provider: Literal["notion", "feishu", "google_sheets"] = "notion"


class PipelineSyncResult(BaseModel):
    provider: Literal["notion", "feishu", "google_sheets"] = "notion"
    configured: bool = False
    direction: Literal["one_way_export"] = "one_way_export"
    exported_fields: List[str] = Field(default_factory=list)
    skipped_fields: List[str] = Field(default_factory=list)
    message: str = ""
    created_at: str = Field(default_factory=now_iso)


class BatchTriageRequest(BaseModel):
    target_ids: List[str] = Field(default_factory=list)
    include_all_targets: bool = True


class TargetTriageItem(BaseModel):
    target_id: str
    target_name: str
    triage_score: int = 0
    tier: Literal["priority", "watch", "hold", "blocked"] = "watch"
    preliminary: bool = True
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    hard_gates: List[str] = Field(default_factory=list)
    deadline_urgency: str = "unknown"
    evidence_summary: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    recommended_next_actions: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class BatchTriageReport(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("triage"))
    scope: str = "target_pool"
    target_count: int = 0
    preliminary: bool = True
    summary: str = ""
    items: List[TargetTriageItem] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class ProfileExpansionCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("pexpand"))
    profile_id: str = ""
    field_name: str
    value: str
    source_type: str = ""
    source_ref: str = ""
    inference_method: str = "rule_extract"
    confidence: float = 0.0
    status: ProfileConfirmationStatus = "unconfirmed"
    inferred: bool = False
    evidence_refs: List[str] = Field(default_factory=list)
    notes: str = ""
    created_at: str = Field(default_factory=now_iso)


class ProfileExpansionReport(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("pexpand_report"))
    profile_id: str = ""
    candidate_count: int = 0
    candidates: List[ProfileExpansionCandidate] = Field(default_factory=list)
    blocked_rules: List[str] = Field(default_factory=list)
    summary: str = ""
    created_at: str = Field(default_factory=now_iso)


class GapPlanRequest(BaseModel):
    target_id: str = ""


class GapPlanItem(BaseModel):
    gap_id: str = Field(default_factory=lambda: new_id("gap"))
    category: Literal[
        "advisor_requirement",
        "profile_gap",
        "material_audit",
        "interview_prep",
        "deadline_risk",
        "source_quality",
        "policy_resource",
    ]
    title: str
    source: str = ""
    severity: Literal["low", "medium", "high"] = "medium"
    evidence_refs: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    resource_links: List[str] = Field(default_factory=list)
    status: Literal["open", "closed"] = "open"


class GapPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: new_id("gap_plan"))
    target_id: str
    target_name: str = ""
    readiness_score: int = 0
    heatmap: Dict[str, int] = Field(default_factory=dict)
    gaps: List[GapPlanItem] = Field(default_factory=list)
    summary: str = ""
    next_actions: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class TemplateValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "error"


class TemplateRenderPreview(BaseModel):
    rendered: str = ""
    unresolved_variables: List[str] = Field(default_factory=list)
    passed: bool = False


class TemplateRegistryItem(BaseModel):
    template_id: str
    name: str = ""
    template_type: str = ""
    version: str = "0.1.0"
    description: str = ""
    path: str = ""
    variables: List[str] = Field(default_factory=list)
    sample_context: Dict[str, str] = Field(default_factory=dict)
    applicable_scenarios: List[str] = Field(default_factory=list)
    style_rules: List[str] = Field(default_factory=list)
    privacy_rules: List[str] = Field(default_factory=list)
    validation_methods: List[str] = Field(default_factory=list)
    managed_block: str = ""
    active: bool = False
    profile_agnostic: bool = True
    validation_issues: List[TemplateValidationIssue] = Field(default_factory=list)
    render_preview: TemplateRenderPreview = Field(default_factory=TemplateRenderPreview)


class TemplateRegistryStatus(BaseModel):
    registry_id: str = Field(default_factory=lambda: new_id("tmplreg"))
    template_root: str = ".agents/skills/grad-apply-workflow/templates"
    workspace_template_root: str = "workspace/templates"
    supported_template_types: List[str] = Field(default_factory=list)
    activation_policy: str = ""
    privacy_policy: str = ""
    implemented: bool = False
    template_count: int = 0
    active_count: int = 0
    custom_template_count: int = 0
    custom_active_count: int = 0
    templates: List[TemplateRegistryItem] = Field(default_factory=list)
    custom_templates: List["CustomTemplateRecord"] = Field(default_factory=list)
    validation_errors: List[TemplateValidationIssue] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


TemplateLifecycleStatus = Literal["draft", "validated", "active", "disabled", "archived"]


class TemplateVersionRecord(BaseModel):
    version_id: str = Field(default_factory=lambda: new_id("tmplver"))
    template_id: str
    version_index: int = 0
    content_hash: str = ""
    content_path: str = ""
    note: str = ""
    diff_text: str = ""
    created_at: str = Field(default_factory=now_iso)


class CustomTemplateRecord(BaseModel):
    template_id: str
    name: str = ""
    template_type: str = ""
    description: str = ""
    status: TemplateLifecycleStatus = "draft"
    active: bool = False
    content: str = ""
    content_path: str = ""
    version_count: int = 0
    latest_version_id: str = ""
    versions: List[TemplateVersionRecord] = Field(default_factory=list)
    variables: List[str] = Field(default_factory=list)
    sample_context: Dict[str, str] = Field(default_factory=dict)
    applicable_scenarios: List[str] = Field(default_factory=list)
    style_rules: List[str] = Field(default_factory=list)
    privacy_rules: List[str] = Field(default_factory=list)
    validation_methods: List[str] = Field(default_factory=list)
    managed_block: str = ""
    validation_issues: List[TemplateValidationIssue] = Field(default_factory=list)
    render_preview: TemplateRenderPreview = Field(default_factory=TemplateRenderPreview)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class CustomTemplateCreateRequest(BaseModel):
    name: str
    template_type: str
    content: str
    description: str = ""
    status: TemplateLifecycleStatus = "draft"
    variables: List[str] = Field(default_factory=list)
    sample_context: Dict[str, str] = Field(default_factory=dict)
    applicable_scenarios: List[str] = Field(default_factory=lambda: ["user_custom"])
    style_rules: List[str] = Field(default_factory=lambda: ["保留事实证据，不使用夸大承诺。"])
    privacy_rules: List[str] = Field(default_factory=lambda: ["不得写入真实个人隐私字面量。"])
    validation_methods: List[str] = Field(default_factory=lambda: ["sample_render", "privacy_scan"])
    managed_block: str = "workspace_custom_template"
    note: str = ""


class CustomTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TemplateLifecycleStatus] = None
    variables: Optional[List[str]] = None
    sample_context: Optional[Dict[str, str]] = None
    applicable_scenarios: Optional[List[str]] = None
    style_rules: Optional[List[str]] = None
    privacy_rules: Optional[List[str]] = None
    validation_methods: Optional[List[str]] = None
    managed_block: Optional[str] = None
    note: str = ""


class CustomTemplateUploadResponse(BaseModel):
    template: CustomTemplateRecord
    filename: str = ""


class TemplateDiffReport(BaseModel):
    diff_id: str = Field(default_factory=lambda: new_id("tmpldiff"))
    template_id: str
    from_version_id: str = ""
    to_version_id: str = ""
    diff_text: str = ""
    summary: str = ""
    created_at: str = Field(default_factory=now_iso)


class SourceConnectorRegistryItem(BaseModel):
    connector_id: str
    name: str = ""
    source_type: str = ""
    version: str = "0.1.0"
    description: str = ""
    path: str = ""
    url_patterns: List[str] = Field(default_factory=list)
    field_mapping: Dict[str, str] = Field(default_factory=dict)
    access_rules: List[str] = Field(default_factory=list)
    robots_policy: str = ""
    tos_policy: str = ""
    test_queries: List[str] = Field(default_factory=list)
    test_urls: List[str] = Field(default_factory=list)
    fallback: str = ""
    output_scope: Literal["workspace_or_fork", "builtin_default"] = "workspace_or_fork"
    active: bool = False
    live_test_status: Literal["not_run", "passed", "failed", "skipped"] = "not_run"
    live_test_id: str = ""
    registration_eligible: bool = False
    refresh_interval_days: int = 7
    refresh_state: Literal["not_tested", "fresh", "due", "stale", "needs_review"] = "not_tested"
    last_live_test_at: str = ""
    next_refresh_at: str = ""
    refresh_due: bool = False
    validation_issues: List[TemplateValidationIssue] = Field(default_factory=list)


class SourceConnectorRegistryStatus(BaseModel):
    registry_id: str = Field(default_factory=lambda: new_id("connectorreg"))
    connector_root: str = ".agents/skills/grad-apply-workflow/source_connectors"
    supported_source_types: List[str] = Field(default_factory=list)
    access_policy: str = ""
    implemented: bool = False
    connector_count: int = 0
    active_count: int = 0
    registrable_count: int = 0
    connectors: List[SourceConnectorRegistryItem] = Field(default_factory=list)
    validation_errors: List[TemplateValidationIssue] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class SourceConnectorLiveTestRequest(BaseModel):
    url: str
    query: str = ""
    tos_acknowledged: bool = False


class SourceConnectorLiveTestResult(BaseModel):
    result_id: str = Field(default_factory=lambda: new_id("connector_test"))
    connector_id: str
    url: str = ""
    query: str = ""
    status: Literal["passed", "failed", "skipped"] = "skipped"
    registration_eligible: bool = False
    robots_status: Literal["allowed", "blocked", "unavailable", "not_checked"] = "not_checked"
    tos_acknowledged: bool = False
    http_status: Optional[int] = None
    content_type: str = ""
    response_bytes: int = 0
    response_hash: str = ""
    checked_at: str = Field(default_factory=now_iso)
    error: str = ""
    fallback: str = ""
    notes: List[str] = Field(default_factory=list)


class SourceConnectorRefreshRequest(BaseModel):
    tos_acknowledged: bool = False
    query: str = ""


class SourceConnectorRefreshReport(BaseModel):
    connector_id: str
    refresh_due: bool = False
    refresh_state: Literal["not_tested", "fresh", "due", "stale", "needs_review"] = "not_tested"
    next_refresh_at: str = ""
    last_live_test_at: str = ""
    live_test_status: Literal["not_run", "passed", "failed", "skipped"] = "not_run"
    registration_eligible: bool = False
    checked_at: str = Field(default_factory=now_iso)


class MaterialQualityReport(BaseModel):
    quality_id: str = Field(default_factory=lambda: new_id("quality"))
    material_id: str
    target_id: str
    passed: bool
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    pdf_readability_report_id: str = ""
    created_at: str = Field(default_factory=now_iso)


class PdfReadabilityIssue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class PdfReadabilityReport(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("pdfcheck"))
    filename: str = ""
    material_id: str = ""
    source_document_id: str = ""
    content_hash: str = ""
    parser_name: str = ""
    page_count: int = 0
    extractable_pages: int = 0
    blank_pages: int = 0
    text_layer_detected: bool = False
    needs_ocr: bool = False
    readable: bool = False
    expected_fields: List[str] = Field(default_factory=list)
    extracted_fields: List[str] = Field(default_factory=list)
    issues: List[PdfReadabilityIssue] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
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


class ReadinessDimensionScore(BaseModel):
    name: str
    label: str
    score: int
    weight: int
    summary: str
    reasons: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)


class ReadinessTargetScore(BaseModel):
    target_id: str
    target_name: str
    score: int
    status: str
    summary: str
    dimensions: List[ReadinessDimensionScore] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class ReadinessScoreReport(BaseModel):
    score_id: str = Field(default_factory=lambda: new_id("readiness"))
    profile_id: str = ""
    scope: str = "overall"
    total_score: int = 0
    status: str = "待补充"
    summary: str = ""
    dimensions: List[ReadinessDimensionScore] = Field(default_factory=list)
    target_scores: List[ReadinessTargetScore] = Field(default_factory=list)
    focus_target_id: str = ""
    focus_target: Optional[ReadinessTargetScore] = None
    high_priority_actions: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


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
        "extraction_started",
        "extraction_completed",
        "match_started",
        "match_completed",
        "retrieval_completed",
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
    reference_file_id: str = ""
    presentation_type: Literal["interview_intro", "research_project", "application_summary"] = (
        "interview_intro"
    )
    duration_minutes: int = 5
    num_slides: int = 5
    length_factor: Literal["concise", "standard", "detailed"] = "standard"
    sim_bound: float = 0.35
    hide_small_pic_ratio: float = 0.08
    keep_in_background: bool = True
    error_exit: bool = False


class ReferencePresentationRecord(BaseModel):
    reference_id: str = Field(default_factory=lambda: new_id("ppt_ref"))
    original_filename: str = ""
    path: str = ""
    content_hash: str = ""
    uploaded_at: str = Field(default_factory=now_iso)
    notes: str = ""


class PresentationPrecheckIssue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    slide_index: Optional[int] = None


class PresentationPrecheckReport(BaseModel):
    precheck_id: str = Field(default_factory=lambda: new_id("ppt_precheck"))
    reference_id: str = ""
    filename: str = ""
    passed: bool = True
    slide_count: int = 0
    total_shape_count: int = 0
    max_shapes_per_slide: int = 0
    functional_pages: Dict[str, bool] = Field(default_factory=dict)
    issues: List[PresentationPrecheckIssue] = Field(default_factory=list)
    fallback_allowed: bool = True
    created_at: str = Field(default_factory=now_iso)


class PresentationQualityReport(BaseModel):
    quality_id: str = Field(default_factory=lambda: new_id("ppt_quality"))
    task_id: str = ""
    target_id: str = ""
    outline_material_id: str = ""
    engine_name: str = "LocalPptxAdapter"
    content_score: int = 0
    design_score: int = 0
    coherence_score: int = 0
    total_score: int = 0
    issues: List[PresentationPrecheckIssue] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class PresentationTaskRecord(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("ppt_task"))
    target_id: str
    outline_material_id: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    progress: int = 0
    output_filename: str = ""
    message: str = ""
    error: str = ""
    engine_name: str = "LocalPptxAdapter"
    fallback_reason: str = ""
    reference_file_id: str = ""
    quality_report_id: str = ""
    quality_score: int = 0
    generation_params: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
