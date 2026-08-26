from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import AdvisorExtractionAgent, MatchAnalysisAgent, run_contact_email_workflow
from agents.evidence_audit_agent import EvidenceAuditAgent
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from feedback_loop import record_evidence_audit_feedback, record_material_edit_feedback
from lifecycle import (
    apply_email_signal_candidate,
    build_application_archive,
    email_signal_sync_status,
    generate_communication_draft,
    import_email_signal_candidates,
    pipeline_sync_status,
    reject_email_signal_candidate,
    should_generate_follow_up,
    update_outcome,
)
from llm_client import llm_configured, load_local_env
from memory import MEMORY_KINDS, LocalMemoryManager, MemoryKind, PromotionTarget
from models import (
    AdvisorProfile,
    AdvisorProfileUpdate,
    AdvisorSource,
    AdvisorSourceCreate,
    AdvisorTargetCreate,
    ApplicationArchive,
    ApplicationArchiveRequest,
    ApplicationRecord,
    ApplicationUpdate,
    BatchTriageReport,
    BatchTriageRequest,
    CommunicationDraft,
    CommunicationDraftRequest,
    CustomTemplateCreateRequest,
    CustomTemplateRecord,
    CustomTemplateUpdateRequest,
    EmailSignalCandidate,
    EmailSignalDecisionRequest,
    EmailSignalImportRequest,
    EmailSignalSyncResult,
    GapPlan,
    GapPlanRequest,
    GeneratedMaterial,
    KnowledgeBaseSourceCreate,
    MatchReport,
    MaterialQualityReport,
    MaterialVersion,
    OcrExtractionReport,
    OutcomeUpdate,
    PdfReadabilityReport,
    PipelineSyncRequest,
    PipelineSyncResult,
    PresentationGenerationRequest,
    PresentationPrecheckReport,
    PresentationQualityReport,
    PresentationTaskRecord,
    ProfileExpansionReport,
    ReadinessScoreReport,
    ReferencePresentationRecord,
    SourceConnectorLiveTestRequest,
    SourceConnectorLiveTestResult,
    SourceConnectorRegistryStatus,
    StudentProfile,
    Target,
    TargetCreate,
    TemplateDiffReport,
    TemplateRegistryStatus,
    UserDocumentManifest,
    now_iso,
)
from ocr_adapter import build_ocr_extraction_report
from pdf_readability import inspect_pdf_bytes
from presentation_quality import build_presentation_quality_report, save_reference_presentation
from pydantic import BaseModel, Field
from quality import audit_material
from rag import (
    KnowledgeBaseIndex,
    KnowledgeBaseRetriever,
    configured_embedding_provider_from_env,
    configured_reranker_from_env,
)
from services import (
    build_profile_from_text,
    build_readiness_score_report,
    build_workspace_report,
    create_advisor_source,
    ensure_application,
    fetch_url_text,
    make_interview_questions,
    make_ppt_outline,
)
from source_connector_registry import (
    merge_live_test_results,
    run_source_connector_live_test,
    scan_source_connector_registry,
)
from storage import Workspace
from strategy import (
    build_batch_triage_report,
    build_gap_plan,
    build_profile_expansion_report,
)
from template_registry import (
    create_custom_template,
    get_custom_template,
    get_custom_template_diff,
    scan_template_registry,
    set_custom_template_status,
    update_custom_template,
)

from integrations.presentation_engine import LocalPptxAdapter, PresentationRequest

APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = APP_ROOT / "frontend"
load_local_env()

app = FastAPI(title="Grad Apply Workflow", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
workspace = Workspace(os.environ.get("WORKSPACE_DIR") or str(PROJECT_ROOT / "workspace"))
ppt_adapter = LocalPptxAdapter()
rag_storage_backend = os.environ.get("RAG_STORAGE_BACKEND", "json").strip().lower() or "json"
rag_embedding_provider = configured_embedding_provider_from_env()
rag_reranker = configured_reranker_from_env()
rag_index = KnowledgeBaseIndex(
    workspace,
    embedding_provider=rag_embedding_provider,
    storage_backend=rag_storage_backend,
)
rag_retriever = KnowledgeBaseRetriever(
    workspace,
    embedding_provider=rag_embedding_provider,
    reranker=rag_reranker,
    storage_backend=rag_storage_backend,
)


def dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


class MemoryWriteRequest(BaseModel):
    kind: MemoryKind
    key: str
    value: Dict[str, Any] = Field(default_factory=dict)
    scope: str = "workspace"
    source_ref: str = ""
    source_refs: List[str] = Field(default_factory=list)
    authority: str = "user"
    confidence: float = 0.0
    retention: str = "long_term"
    sensitivity: Literal["low", "medium", "high"] = "medium"
    notes: str = ""
    negative: bool = False
    blocked_patterns: List[str] = Field(default_factory=list)


class MemoryTransitionRequest(BaseModel):
    reason: str = ""


class MemoryPromotionRequest(BaseModel):
    target: PromotionTarget
    reason: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)


class MaterialEditFeedbackRequest(BaseModel):
    before_version_id: str
    after_version_id: str
    accepted: bool = True
    evidence_refs: List[str] = Field(default_factory=list)


def memory_manager() -> LocalMemoryManager:
    return LocalMemoryManager(workspace)


def _validate_memory_kind(kind: str) -> MemoryKind:
    if kind not in MEMORY_KINDS:
        raise HTTPException(status_code=400, detail=f"Unsupported memory kind: {kind}")
    return kind


def latest_profile() -> Optional[StudentProfile]:
    item = workspace.latest("profiles")
    return StudentProfile(**item) if item else None


def profile_for_id(profile_id: str) -> Optional[StudentProfile]:
    if not profile_id:
        return None
    item = workspace.read("profiles", profile_id)
    return StudentProfile(**item) if item else None


def get_target_or_404(target_id: str) -> Target:
    item = workspace.read("targets", target_id)
    if not item:
        raise HTTPException(status_code=404, detail="Target not found")
    return Target(**item)


def advisor_for_target(target: Target) -> Optional[AdvisorProfile]:
    if not target.advisor_id:
        return None
    item = workspace.read("advisors", target.advisor_id)
    return AdvisorProfile(**item) if item else None


def get_advisor_or_404(advisor_id: str) -> AdvisorProfile:
    item = workspace.read("advisors", advisor_id)
    if not item:
        raise HTTPException(status_code=404, detail="Advisor not found")
    return AdvisorProfile(**item)


def get_application_or_404(application_id: str) -> ApplicationRecord:
    item = workspace.read("applications", application_id)
    if not item:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationRecord(**item)


def application_for_target(target: Target) -> ApplicationRecord:
    applications = [
        ApplicationRecord(**item)
        for item in workspace.list("applications")
        if item.get("target_id") == target.target_id
    ]
    if applications:
        return applications[-1]
    app_record = ensure_application(target)
    workspace.write("applications", dump(app_record), "application_id")
    return app_record


def latest_match(target_id: str):
    matches = [item for item in workspace.list("matches") if item["target_id"] == target_id]
    return MatchReport(**matches[-1]) if matches else None


def materials_for_target(target_id: str, material_ids: Optional[list[str]] = None):
    items = [
        GeneratedMaterial(**item)
        for item in workspace.list("generated")
        if item.get("target_id") == target_id
    ]
    if material_ids:
        allowed = set(material_ids)
        items = [item for item in items if item.material_id in allowed]
    return items


def save_material_with_quality(material: GeneratedMaterial):
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile is required for quality audit")
    workspace.write("generated", dump(material), "material_id")
    target = get_target_or_404(material.target_id)
    quality = audit_material(material, profile, advisor_for_target(target))
    workspace.write("quality_reports", dump(quality), "quality_id")
    return {"material": material, "quality": quality}


def score_readiness(target_id: str = "") -> ReadinessScoreReport:
    profile = latest_profile()
    targets = [Target(**item) for item in workspace.list("targets")]
    applications = [ApplicationRecord(**item) for item in workspace.list("applications")]
    matches = [MatchReport(**item) for item in workspace.list("matches")]
    materials = [GeneratedMaterial(**item) for item in workspace.list("generated")]
    quality_reports = [MaterialQualityReport(**item) for item in workspace.list("quality_reports")]
    advisors = [AdvisorProfile(**item) for item in workspace.list("advisors")]
    presentation_tasks = workspace.list("presentation_tasks")
    report = build_readiness_score_report(
        profile,
        targets,
        applications,
        matches=matches,
        materials=materials,
        quality_reports=quality_reports,
        advisors=advisors,
        presentation_tasks=presentation_tasks,
        focus_target_id=target_id,
    )
    workspace.write("readiness_scores", dump(report), "score_id")
    return report


def get_presentation_task_or_404(task_id: str) -> PresentationTaskRecord:
    item = workspace.read("presentation_tasks", task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Presentation task not found")
    return PresentationTaskRecord(**item)


def get_email_signal_or_404(candidate_id: str) -> EmailSignalCandidate:
    item = workspace.read("email_signal_candidates", candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="Email signal candidate not found")
    return EmailSignalCandidate(**item)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/llm/status")
def llm_status():
    return {"configured": llm_configured()}


@app.get("/api/memory/summary")
def get_memory_summary():
    return memory_manager().summarize()


@app.get("/api/memory")
def list_memory(
    q: str = "",
    kind: str = "",
    scope: str = "",
    include_candidates: bool = True,
    include_rejected: bool = False,
    include_historical: bool = False,
    include_negative: bool = False,
):
    kinds = [_validate_memory_kind(kind)] if kind else None
    scopes = [scope] if scope else None
    return memory_manager().search(
        q,
        kinds=kinds,
        scopes=scopes,
        include_candidates=include_candidates,
        include_rejected=include_rejected,
        include_historical=include_historical,
        include_negative=include_negative,
    )


@app.post("/api/memory")
def create_memory_candidate(payload: MemoryWriteRequest):
    return memory_manager().write_candidate(**dump(payload))


@app.post("/api/memory/{memory_id}/confirm")
def confirm_memory(memory_id: str):
    try:
        return memory_manager().confirm(memory_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory record not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/memory/{memory_id}/reject")
def reject_memory(memory_id: str, payload: MemoryTransitionRequest = MemoryTransitionRequest()):
    try:
        return memory_manager().reject(memory_id, reason=payload.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory record not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/memory/{memory_id}/promotion-candidates")
def create_memory_promotion_candidate(memory_id: str, payload: MemoryPromotionRequest):
    try:
        return memory_manager().create_promotion_candidate(
            memory_id,
            target=payload.target,
            reason=payload.reason,
            payload=payload.payload or None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory record not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/memory-promotion-candidates")
def list_memory_promotion_candidates(status: str = "", target: str = ""):
    return memory_manager().promotion_candidates(
        status=status or None,
        target=target or None,
    )


@app.post("/api/profile/upload")
async def upload_profile(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    category: str = Form("manual_inputs"),
):
    content_parts = []
    source_document_ids = []
    if text.strip():
        content_parts.append(text)
        if category != "web_supplements":
            document = workspace.save_user_document(
                text.encode("utf-8"),
                "profile_manual_input.txt",
                category="manual_inputs",
                source_type="manual_input",
                trusted=True,
                confirmed=False,
                notes="学生资料页手动粘贴内容",
            )
            source_document_ids.append(document.document_id)
    if file:
        blob = await file.read()
        content_parts.append(blob.decode("utf-8", errors="ignore"))
        if category != "web_supplements":
            document = workspace.save_user_document(
                blob,
                file.filename or "uploaded_profile.txt",
                category=category,
                source_type="local_upload",
                trusted=True,
                confirmed=False,
                notes="学生资料页上传文件",
            )
            source_document_ids.append(document.document_id)
    content = "\n\n".join(part for part in content_parts if part.strip())
    if not content.strip():
        raise HTTPException(status_code=400, detail="Profile text is required")
    if category == "web_supplements":
        document = workspace.save_user_document(
            content.encode("utf-8"),
            "web_supplement.txt",
            category="web_supplements",
            source_type="web_supplement",
            trusted=True,
            confirmed=False,
            notes="网页补充资料，需用户确认后才能进入正式 profile",
        )
        preview = build_profile_from_text(content, source_document_ids=[document.document_id])
        rag_index.rebuild()
        return {
            "supplement": document,
            "preview": preview,
            "confirmed": False,
        }
    profile = build_profile_from_text(content, source_document_ids=source_document_ids)
    workspace.write("profiles", dump(profile), "profile_id")
    rag_index.rebuild()
    return profile


@app.post("/api/profile/web-supplement")
async def upload_web_supplement(
    url: str = Form(""),
    text: str = Form(""),
):
    raw_text = text.strip()
    notes = "网页补充资料"
    if url.strip():
        raw_html, raw_text = fetch_url_text(url)
        notes = f"网页补充资料：{url.strip()}"
        content_bytes = raw_html.encode("utf-8", errors="ignore")
        filename = "web_supplement.html"
    elif raw_text:
        content_bytes = raw_text.encode("utf-8")
        filename = "web_supplement.txt"
    else:
        raise HTTPException(status_code=400, detail="Web supplement text or URL is required")
    document = workspace.save_user_document(
        content_bytes,
        filename,
        category="web_supplements",
        source_type="web_supplement",
        trusted=True,
        confirmed=False,
        notes=notes,
    )
    preview = build_profile_from_text(raw_text, source_document_ids=[document.document_id])
    rag_index.rebuild()
    return {
        "supplement": document,
        "preview": preview,
        "confirmed": False,
    }


@app.get("/api/user-documents")
def list_user_documents():
    return UserDocumentManifest(**workspace.read_user_document_manifest())


@app.get("/api/profile")
def get_profile():
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not created")
    return profile


@app.put("/api/profile")
def update_profile(profile: StudentProfile):
    profile.updated_at = now_iso()
    workspace.write("profiles", dump(profile), "profile_id")
    return profile


@app.post("/api/advisor-sources")
def create_source(payload: AdvisorSourceCreate):
    source = create_advisor_source(payload)
    workspace.write("advisor_sources", dump(source), "source_id")
    sources = [source]
    advisor_id = payload.advisor_id
    if advisor_id:
        existing = get_advisor_or_404(advisor_id)
        for source_id in existing.source_ids:
            item = workspace.read("advisor_sources", source_id)
            if item:
                sources.append(AdvisorSource(**item))
    result = AdvisorExtractionAgent().extract(sources, advisor_id=advisor_id)
    advisor = result.advisor
    workspace.write("advisors", dump(advisor), "advisor_id")
    workspace.write("agent_runs", dump(result.agent_run), "run_id")
    for event in result.events:
        workspace.write("workflow_events", dump(event), "event_id")
    rag_index.rebuild()
    return {
        "source": source,
        "advisor": advisor,
        "agent_run": result.agent_run,
        "events": result.events,
    }


@app.get("/api/advisor-sources")
def list_sources():
    return workspace.list("advisor_sources")


@app.get("/api/advisor-sources/{source_id}")
def get_source(source_id: str):
    item = workspace.read("advisor_sources", source_id)
    if not item:
        raise HTTPException(status_code=404, detail="Advisor source not found")
    return item


@app.get("/api/advisors")
def list_advisors():
    return workspace.list("advisors")


@app.get("/api/advisors/{advisor_id}")
def get_advisor(advisor_id: str):
    return get_advisor_or_404(advisor_id)


@app.put("/api/advisors/{advisor_id}")
def update_advisor(advisor_id: str, updates: AdvisorProfileUpdate):
    advisor = get_advisor_or_404(advisor_id)
    data = dump(advisor)
    changes = {key: value for key, value in dump(updates).items() if value is not None}
    if "source_ids" in changes or "advisor_id" in changes:
        raise HTTPException(status_code=400, detail="Advisor identity fields cannot be replaced")
    data.update(changes)
    data["last_verified_at"] = now_iso()
    if data.get("research_directions") and not data.get("keywords"):
        data["keywords"] = data["research_directions"]
    advisor = AdvisorProfile(**data)
    workspace.write("advisors", dump(advisor), "advisor_id")
    return advisor


@app.post("/api/advisors/{advisor_id}/target")
def create_target_from_advisor(advisor_id: str, payload: AdvisorTargetCreate):
    advisor = get_advisor_or_404(advisor_id)
    display_name = advisor.name_zh or advisor.name_en or "未命名导师"
    target_name = payload.name or " ".join(
        item for item in [advisor.school, advisor.college, display_name, "课题组"] if item
    )
    if not target_name.strip():
        raise HTTPException(status_code=400, detail="Advisor profile is too sparse")
    target = Target(
        name=target_name,
        target_type="advisor",
        advisor_id=advisor.advisor_id,
        school=advisor.school,
        college=advisor.college or advisor.department,
        program_name=advisor.lab_name,
        degree_track=payload.degree_track,
        application_round=payload.application_round,
        deadline=payload.deadline,
        priority=payload.priority,
        source_ids=advisor.source_ids,
    )
    workspace.write("targets", dump(target), "target_id")
    next_action = payload.next_action or "复核导师来源证据，并准备一页科研项目摘要"
    app_record = ensure_application(target)
    app_record.next_action = next_action
    workspace.write("applications", dump(app_record), "application_id")
    return {"target": target, "application": app_record}


@app.post("/api/targets")
def create_target(payload: TargetCreate):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Target name is required")
    target = Target(**dump(payload))
    workspace.write("targets", dump(target), "target_id")
    app_record = ensure_application(target)
    workspace.write("applications", dump(app_record), "application_id")
    return target


@app.get("/api/targets")
def list_targets():
    return workspace.list("targets")


@app.get("/api/targets/{target_id}")
def get_target(target_id: str):
    return get_target_or_404(target_id)


@app.patch("/api/targets/{target_id}")
def update_target(target_id: str, updates: dict):
    target = get_target_or_404(target_id)
    data = dump(target)
    data.update(updates)
    data["updated_at"] = now_iso()
    target = Target(**data)
    workspace.write("targets", dump(target), "target_id")
    return target


@app.post("/api/targets/{target_id}/match")
def generate_match(target_id: str):
    target = get_target_or_404(target_id)
    result = MatchAnalysisAgent().analyze(
        latest_profile(),
        target,
        advisor_for_target(target),
        retriever=rag_retriever,
    )
    report = result.report
    workspace.write("matches", dump(report), "match_id")
    workspace.write("agent_runs", dump(result.agent_run), "run_id")
    for event in result.events:
        workspace.write("workflow_events", dump(event), "event_id")
    return report


@app.get("/api/targets/{target_id}/match")
def get_match(target_id: str):
    item = latest_match(target_id)
    if not item:
        raise HTTPException(status_code=404, detail="Match report not generated")
    return item


@app.post("/api/targets/{target_id}/materials/contact-email")
def generate_contact_email(target_id: str):
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile is required")
    target = get_target_or_404(target_id)
    result = run_contact_email_workflow(
        profile,
        target,
        advisor_for_target(target),
        latest_match(target_id),
        retriever=rag_retriever,
        workspace=workspace,
    )
    for version in result.versions:
        workspace.write("material_versions", dump(version), "version_id")
    for event in result.events:
        workspace.write("workflow_events", dump(event), "event_id")
    workspace.write("generated", dump(result.material), "material_id")
    workspace.write("quality_reports", dump(result.quality), "quality_id")
    workspace.write("agent_runs", dump(result.agent_run), "run_id")
    return {
        "material": result.material,
        "quality": result.quality,
        "draft": result.draft,
        "review": result.review,
        "evidence_audit": result.evidence_audit,
        "feedback_loop": result.feedback_loop,
        "revision": result.revision,
        "events": result.events,
        "agent_run": result.agent_run,
    }


@app.post("/api/targets/{target_id}/materials/interview-questions")
def generate_interview_questions(target_id: str):
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile is required")
    target = get_target_or_404(target_id)
    material = make_interview_questions(
        profile,
        target,
        advisor_for_target(target),
        retriever=rag_retriever,
    )
    return save_material_with_quality(material)


@app.post("/api/targets/{target_id}/materials/ppt-outline")
def generate_ppt_outline(target_id: str):
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile is required")
    target = get_target_or_404(target_id)
    material = make_ppt_outline(
        profile,
        target,
        advisor_for_target(target),
        retriever=rag_retriever,
    )
    return save_material_with_quality(material)


@app.get("/api/generated")
def list_generated():
    return workspace.list("generated")


@app.get("/api/procedural-candidates")
def list_procedural_candidates():
    return workspace.list("procedural_candidates")


@app.get("/api/agent-runs")
def list_agent_runs():
    return workspace.list("agent_runs")


@app.get("/api/agent-runs/{run_id}/events")
def list_agent_run_events(run_id: str):
    run = workspace.read("agent_runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return [event for event in workspace.list("workflow_events") if event.get("run_id") == run_id]


@app.get("/api/generated/{material_id}")
def get_generated_material(material_id: str):
    item = workspace.read("generated", material_id)
    if not item:
        raise HTTPException(status_code=404, detail="Generated material not found")
    return item


@app.get("/api/generated/{material_id}/download")
def download_generated_material(material_id: str):
    item = workspace.read("generated", material_id)
    if not item:
        raise HTTPException(status_code=404, detail="Generated material not found")
    filename = f"{material_id}.md"
    return PlainTextResponse(
        item["content"],
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/generated/{material_id}/edit-feedback")
def create_material_edit_feedback(material_id: str, payload: MaterialEditFeedbackRequest):
    before = workspace.read("material_versions", payload.before_version_id)
    after = workspace.read("material_versions", payload.after_version_id)
    if not before or not after:
        raise HTTPException(status_code=404, detail="Material version not found")
    before_version = MaterialVersion(**before)
    after_version = MaterialVersion(**after)
    if before_version.material_id != material_id or after_version.material_id != material_id:
        raise HTTPException(status_code=400, detail="Material versions do not belong to material")
    return record_material_edit_feedback(
        workspace,
        before_version,
        after_version,
        accepted=payload.accepted,
        evidence_refs=payload.evidence_refs,
    )


@app.post("/api/knowledge-base/sources")
def create_knowledge_base_source(payload: KnowledgeBaseSourceCreate):
    try:
        source = rag_index.add_source(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rag_index.rebuild()
    return source


@app.get("/api/knowledge-base/sources")
def list_knowledge_base_sources():
    return rag_index.list_sources()


@app.post("/api/rag/rebuild")
def rebuild_rag_index():
    return rag_index.rebuild()


@app.get("/api/rag/search")
def search_rag(
    query: str,
    source_kind: Optional[str] = None,
    limit: int = 5,
    include_unconfirmed: bool = True,
    include_historical: bool = False,
    as_of_year: Optional[int] = None,
    allow_external_public_query: bool = False,
):
    source_kinds = [source_kind] if source_kind else None
    return rag_retriever.search(
        query,
        source_kinds=source_kinds,
        limit=limit,
        include_unconfirmed=include_unconfirmed,
        include_historical=include_historical,
        as_of_year=as_of_year,
        allow_external_public_query=allow_external_public_query,
    )


@app.get("/api/rag/evidence-bundles")
def list_evidence_bundles():
    return workspace.list("evidence_bundles")


@app.get("/api/rag/evidence-bundles/{bundle_id}")
def get_evidence_bundle(bundle_id: str):
    bundle = workspace.read("evidence_bundles", bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    return bundle


@app.post("/api/rag/evidence-bundles/{bundle_id}/audit-feedback")
def audit_evidence_bundle_feedback(bundle_id: str):
    bundle = rag_retriever.evidence_store.get(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    audit = EvidenceAuditAgent().audit_evidence_bundle(bundle)
    feedback = record_evidence_audit_feedback(workspace, audit, bundle=bundle)
    bundle.audit_status = "passed" if audit.passed else "needs_review"
    bundle.audit_ref = feedback.feedback_memory_ids[0] if feedback.feedback_memory_ids else ""
    rag_retriever.evidence_store.save(bundle)
    return {"audit": audit, "feedback_loop": feedback, "evidence_bundle": bundle}


@app.get("/api/readiness-score")
def get_readiness_score(target_id: str = "") -> ReadinessScoreReport:
    return score_readiness(target_id=target_id)


@app.get("/api/target-triage")
def list_target_triage_reports():
    return workspace.list("target_triage_reports")


@app.post("/api/target-triage")
def create_target_triage_report(
    payload: BatchTriageRequest = BatchTriageRequest(),
) -> BatchTriageReport:
    profile = latest_profile()
    targets = [Target(**item) for item in workspace.list("targets")]
    advisors = [AdvisorProfile(**item) for item in workspace.list("advisors")]
    applications = [ApplicationRecord(**item) for item in workspace.list("applications")]
    matches = [MatchReport(**item) for item in workspace.list("matches")]
    readiness = score_readiness()
    target_ids = payload.target_ids if not payload.include_all_targets else None
    return build_batch_triage_report(
        workspace,
        profile,
        targets,
        advisors,
        applications,
        matches,
        readiness,
        target_ids=target_ids,
    )


@app.get("/api/profile-expansion")
def list_profile_expansion_reports():
    return workspace.list("profile_expansion_candidates")


@app.post("/api/profile-expansion")
def create_profile_expansion_report() -> ProfileExpansionReport:
    return build_profile_expansion_report(workspace, latest_profile())


@app.get("/api/gap-plans")
def list_gap_plans():
    return workspace.list("gap_plans")


@app.post("/api/gap-plans")
def create_gap_plan(payload: GapPlanRequest) -> GapPlan:
    if not payload.target_id:
        raise HTTPException(status_code=400, detail="target_id is required")
    target = get_target_or_404(payload.target_id)
    profile = latest_profile()
    application = application_for_target(target)
    readiness = score_readiness(target_id=target.target_id)
    quality_reports = [
        MaterialQualityReport(**item)
        for item in workspace.list("quality_reports")
        if item.get("target_id") == target.target_id
    ]
    materials = materials_for_target(target.target_id)
    return build_gap_plan(
        workspace,
        target,
        profile,
        advisor_for_target(target),
        application,
        latest_match(target.target_id),
        readiness,
        quality_reports,
        materials,
        retriever=rag_retriever,
    )


@app.get("/api/template-registry/status")
def get_template_registry_status() -> TemplateRegistryStatus:
    status = scan_template_registry(PROJECT_ROOT, workspace.root)
    workspace.write("template_registry", dump(status), "registry_id")
    return status


@app.post("/api/templates")
def create_template(payload: CustomTemplateCreateRequest) -> CustomTemplateRecord:
    try:
        record = create_custom_template(workspace, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_template_registry_status()
    return record


@app.post("/api/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    template_type: str = Form("contact_email"),
    name: str = Form(""),
    description: str = Form(""),
) -> CustomTemplateRecord:
    filename = file.filename or "custom-template.md"
    if Path(filename).suffix.lower() not in {".md", ".txt"}:
        raise HTTPException(status_code=400, detail="自定义文本模板只支持 .md 或 .txt。")
    content = (await file.read()).decode("utf-8", errors="replace")
    payload = CustomTemplateCreateRequest(
        name=name.strip() or Path(filename).stem,
        template_type=template_type,
        description=description,
        content=content,
    )
    try:
        record = create_custom_template(workspace, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_template_registry_status()
    return record


@app.get("/api/templates/{template_id}")
def get_template(template_id: str) -> CustomTemplateRecord:
    try:
        return get_custom_template(workspace, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/templates/{template_id}")
def edit_template(
    template_id: str,
    payload: CustomTemplateUpdateRequest,
) -> CustomTemplateRecord:
    try:
        record = update_custom_template(workspace, template_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_template_registry_status()
    return record


@app.patch("/api/templates/{template_id}/lifecycle")
def change_template_lifecycle(template_id: str, payload: dict) -> CustomTemplateRecord:
    try:
        record = set_custom_template_status(workspace, template_id, str(payload.get("status", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    get_template_registry_status()
    return record


@app.get("/api/templates/{template_id}/diff")
def diff_template_versions(
    template_id: str,
    from_version_id: str = "",
    to_version_id: str = "",
) -> TemplateDiffReport:
    try:
        return get_custom_template_diff(workspace, template_id, from_version_id, to_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/source-connectors/status")
def get_source_connector_status() -> SourceConnectorRegistryStatus:
    status = scan_source_connector_registry(PROJECT_ROOT)
    live_tests = [
        SourceConnectorLiveTestResult(**item)
        for item in workspace.list("source_connector_live_tests")
    ]
    status = merge_live_test_results(status, live_tests)
    workspace.write("source_connectors", dump(status), "registry_id")
    return status


@app.post("/api/source-connectors/{connector_id}/live-test")
def run_source_connector_test(
    connector_id: str,
    payload: SourceConnectorLiveTestRequest,
) -> SourceConnectorLiveTestResult:
    result = run_source_connector_live_test(
        PROJECT_ROOT,
        connector_id,
        payload.url,
        query=payload.query,
        tos_acknowledged=payload.tos_acknowledged,
    )
    workspace.write("source_connector_live_tests", dump(result), "result_id")
    return result


@app.post("/api/source-connectors/{connector_id}/refresh")
def refresh_source_connector(
    connector_id: str,
    payload: SourceConnectorLiveTestRequest,
) -> SourceConnectorLiveTestResult:
    """Manually rerun a bounded public connector test after refresh is due."""
    return run_source_connector_test(connector_id, payload)


@app.get("/api/source-connectors/live-tests")
def list_source_connector_live_tests() -> List[SourceConnectorLiveTestResult]:
    return [
        SourceConnectorLiveTestResult(**item)
        for item in workspace.list("source_connector_live_tests")
    ]


@app.post("/api/pdf/readability-check")
async def check_pdf_readability(
    file: UploadFile = File(...),
    expected_fields: str = Form("name,email"),
    material_id: str = Form(""),
) -> PdfReadabilityReport:
    content = await file.read()
    fields = [item.strip() for item in expected_fields.split(",") if item.strip()]
    report = inspect_pdf_bytes(content, file.filename or "document.pdf", fields)
    report.material_id = material_id
    workspace.write("pdf_readability_reports", dump(report), "report_id")
    if material_id:
        quality_items = [
            MaterialQualityReport(**item)
            for item in workspace.list("quality_reports")
            if item.get("material_id") == material_id
        ]
        if quality_items:
            quality = quality_items[-1]
            quality.pdf_readability_report_id = report.report_id
            quality.checks.append(
                {
                    "name": "pdf_readability",
                    "passed": report.readable,
                    "message": (
                        "PDF 可读性检查通过。" if report.readable else "PDF 需要人工复核或 OCR。"
                    ),
                    "report_id": report.report_id,
                    "needs_ocr": report.needs_ocr,
                    "issues": [issue.message for issue in report.issues],
                }
            )
            if not report.readable:
                quality.passed = False
                quality.risk_level = "high" if report.needs_ocr else "medium"
            workspace.write("quality_reports", dump(quality), "quality_id")
    return report


@app.get("/api/pdf/readability-reports")
def list_pdf_readability_reports() -> List[PdfReadabilityReport]:
    return [PdfReadabilityReport(**item) for item in workspace.list("pdf_readability_reports")]


@app.post("/api/ocr/precheck")
async def run_ocr_precheck(
    file: UploadFile = File(...),
    expected_fields: str = Form(""),
    material_id: str = Form(""),
    profile_id: str = Form(""),
    manual_text: str = Form(""),
) -> OcrExtractionReport:
    fields = [item.strip() for item in expected_fields.split(",") if item.strip()]
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="OCR source file is required")
    try:
        return build_ocr_extraction_report(
            workspace,
            content,
            file.filename or "ocr_source",
            expected_fields=fields,
            material_id=material_id,
            manual_text=manual_text,
            profile=profile_for_id(profile_id) or latest_profile(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/ocr/reports")
def list_ocr_reports() -> List[OcrExtractionReport]:
    return [OcrExtractionReport(**item) for item in workspace.list("ocr_extraction_reports")]


@app.get("/api/reference-presentations")
def list_reference_presentations() -> List[ReferencePresentationRecord]:
    return [
        ReferencePresentationRecord(**item) for item in workspace.list("reference_presentations")
    ]


@app.post("/api/reference-presentations")
async def upload_reference_presentation(
    file: UploadFile = File(...),
) -> Dict[str, Union[ReferencePresentationRecord, PresentationPrecheckReport]]:
    content = await file.read()
    try:
        reference, precheck = save_reference_presentation(
            workspace,
            content,
            file.filename or "reference.pptx",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"reference": reference, "precheck": precheck}


@app.get("/api/presentation-prechecks")
def list_presentation_prechecks() -> List[PresentationPrecheckReport]:
    return [PresentationPrecheckReport(**item) for item in workspace.list("presentation_prechecks")]


@app.get("/api/presentation-quality-reports")
def list_presentation_quality_reports() -> List[PresentationQualityReport]:
    return [
        PresentationQualityReport(**item) for item in workspace.list("presentation_quality_reports")
    ]


@app.post("/api/targets/{target_id}/ppt")
def generate_presentation(
    target_id: str, payload: PresentationGenerationRequest = PresentationGenerationRequest()
):
    target = get_target_or_404(target_id)
    outline_item = (
        workspace.read("generated", payload.outline_material_id)
        if payload.outline_material_id
        else None
    )
    if not outline_item:
        candidates = [
            item
            for item in workspace.list("generated")
            if item["target_id"] == target_id and item["material_type"] == "ppt_outline"
        ]
        outline_item = candidates[-1] if candidates else None
    if not outline_item:
        raise HTTPException(status_code=400, detail="Generate a PPT outline before creating PPTX")

    outline = GeneratedMaterial(**outline_item)
    reference_path = None
    if payload.reference_file_id:
        reference_item = workspace.read("reference_presentations", payload.reference_file_id)
        if not reference_item:
            raise HTTPException(status_code=404, detail="Reference presentation not found")
        reference = ReferencePresentationRecord(**reference_item)
        reference_path = workspace.root / reference.path
        if not reference_path.exists():
            raise HTTPException(status_code=404, detail="Reference presentation file not found")

    task = PresentationTaskRecord(
        target_id=target.target_id,
        outline_material_id=outline.material_id,
        status="running",
        progress=15,
        message="正在生成可编辑 PPTX。",
        reference_file_id=payload.reference_file_id,
        generation_params=dump(payload),
        updated_at=now_iso(),
    )
    workspace.write("presentation_tasks", dump(task), "task_id")
    try:
        result = ppt_adapter.generate(
            PresentationRequest(
                title=f"{target.name}_面试展示",
                outline=outline.content,
                output_dir=workspace.root / "generated" / "presentations",
                reference_file=reference_path,
                presentation_type=payload.presentation_type,
                duration_minutes=payload.duration_minutes,
                num_slides=payload.num_slides,
                length_factor=payload.length_factor,
                metadata={
                    "target_id": target.target_id,
                    "sim_bound": str(payload.sim_bound),
                    "hide_small_pic_ratio": str(payload.hide_small_pic_ratio),
                    "keep_in_background": str(payload.keep_in_background),
                    "error_exit": str(payload.error_exit),
                },
            )
        )
        if not result.output_path:
            raise RuntimeError(result.message or "未生成 PPTX 文件")
        quality = build_presentation_quality_report(task, outline, result, payload)
        workspace.write("presentation_quality_reports", dump(quality), "quality_id")
        task.status = "completed"
        task.progress = 100
        task.output_filename = result.output_path.name
        task.message = result.message
        task.engine_name = result.engine_name
        task.fallback_reason = result.fallback_reason
        task.quality_report_id = quality.quality_id
        task.quality_score = quality.total_score
    except Exception as exc:
        task.status = "failed"
        task.progress = 100
        task.message = "PPTX 生成失败。"
        task.error = str(exc)
    task.updated_at = now_iso()
    workspace.write("presentation_tasks", dump(task), "task_id")
    return task


@app.get("/api/tasks/{task_id}")
def get_presentation_task(task_id: str):
    return get_presentation_task_or_404(task_id)


@app.get("/api/tasks/{task_id}/download")
def download_presentation(task_id: str):
    task = get_presentation_task_or_404(task_id)
    if task.status != "completed" or not task.output_filename:
        raise HTTPException(status_code=409, detail="Presentation is not ready for download")
    path = workspace.root / "generated" / "presentations" / task.output_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Presentation output not found")
    return FileResponse(
        path,
        media_type=("application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        filename=path.name,
    )


@app.get("/api/applications")
def list_applications():
    return workspace.list("applications")


@app.patch("/api/applications/{application_id}")
def update_application(application_id: str, updates: ApplicationUpdate):
    record = get_application_or_404(application_id)
    item = dump(record)
    changes = {key: value for key, value in dump(updates).items() if value is not None}
    item.update(changes)
    item["updated_at"] = now_iso()
    record = ApplicationRecord(**item)
    workspace.write("applications", dump(record), "application_id")
    return record


@app.get("/api/application-archives")
def list_application_archives():
    return workspace.list("application_archives")


@app.get("/api/targets/{target_id}/archive")
def get_target_archive(target_id: str):
    get_target_or_404(target_id)
    archives = [
        item
        for item in workspace.list("application_archives")
        if item.get("target_id") == target_id
    ]
    if not archives:
        raise HTTPException(status_code=404, detail="Application archive not created")
    return archives[-1]


@app.post("/api/targets/{target_id}/archive")
def create_target_archive(
    target_id: str,
    payload: ApplicationArchiveRequest = ApplicationArchiveRequest(),
) -> ApplicationArchive:
    target = get_target_or_404(target_id)
    application = application_for_target(target)
    materials = materials_for_target(target_id, payload.material_ids)
    archive = build_application_archive(
        workspace,
        target,
        application,
        materials,
        stage=payload.stage,
        notes=payload.notes,
    )
    application.status = payload.stage
    application.updated_at = now_iso()
    application.next_action = "记录 outcome 或生成后续沟通草稿"
    workspace.write("applications", dump(application), "application_id")
    return archive


@app.put("/api/targets/{target_id}/outcome")
def put_target_outcome(target_id: str, payload: OutcomeUpdate) -> ApplicationArchive:
    target = get_target_or_404(target_id)
    application = application_for_target(target)
    archive = update_outcome(workspace, target, application, payload)
    application.status = payload.stage
    application.updated_at = now_iso()
    application.notes = list(
        dict.fromkeys(
            application.notes
            + [f"{payload.outcome_date or now_iso()} outcome 更新：{archive.outcome_path}"]
        )
    )
    application.next_action = "根据 outcome 复盘结果调整下一步计划"
    workspace.write("applications", dump(application), "application_id")
    return archive


@app.get("/api/communications")
def list_communications():
    return workspace.list("communications")


@app.post("/api/targets/{target_id}/communications")
def create_communication_draft(
    target_id: str,
    payload: CommunicationDraftRequest,
) -> CommunicationDraft:
    target = get_target_or_404(target_id)
    application = application_for_target(target)
    profile = latest_profile()
    advisor = advisor_for_target(target)
    selected = materials_for_target(target_id, payload.source_material_ids)
    if payload.kind == "follow_up" and not should_generate_follow_up(application):
        raise HTTPException(
            status_code=409,
            detail="Follow-up is not due yet or max attempts have been reached",
        )
    return generate_communication_draft(
        workspace,
        target,
        application,
        profile,
        advisor,
        selected or materials_for_target(target_id),
        payload,
    )


@app.post("/api/email-sync/status")
def get_email_sync_status(provider: str = "unknown") -> EmailSignalSyncResult:
    result = email_signal_sync_status(provider)
    workspace.write(
        "sync_runs",
        {
            "sync_id": f"email_sync_{now_iso().replace(':', '').replace('+', '_')}",
            "kind": "email_signal_sync",
            **dump(result),
        },
        "sync_id",
    )
    return result


@app.get("/api/email-signals")
def list_email_signal_candidates() -> List[EmailSignalCandidate]:
    return [EmailSignalCandidate(**item) for item in workspace.list("email_signal_candidates")]


@app.post("/api/email-signals/import")
def import_email_signals(payload: EmailSignalImportRequest) -> EmailSignalSyncResult:
    if not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="Email text is required")
    targets = [Target(**item) for item in workspace.list("targets")]
    applications = [ApplicationRecord(**item) for item in workspace.list("applications")]
    advisors = [AdvisorProfile(**item) for item in workspace.list("advisors")]
    result = import_email_signal_candidates(
        workspace,
        payload.provider,
        payload.raw_text,
        targets,
        applications,
        advisors,
    )
    workspace.write(
        "sync_runs",
        {
            "sync_id": f"email_import_{now_iso().replace(':', '').replace('+', '_')}",
            "kind": "email_signal_import",
            **dump(result),
        },
        "sync_id",
    )
    return result


@app.post("/api/email-signals/{candidate_id}/approve")
def approve_email_signal(
    candidate_id: str,
    payload: EmailSignalDecisionRequest = EmailSignalDecisionRequest(),
) -> EmailSignalCandidate:
    candidate = get_email_signal_or_404(candidate_id)
    if not candidate.target_id:
        raise HTTPException(status_code=409, detail="Candidate has no matched target")
    target = get_target_or_404(candidate.target_id)
    application = application_for_target(target)
    return apply_email_signal_candidate(workspace, candidate, target, application, payload)


@app.post("/api/email-signals/{candidate_id}/reject")
def reject_email_signal(
    candidate_id: str,
    payload: EmailSignalDecisionRequest = EmailSignalDecisionRequest(),
) -> EmailSignalCandidate:
    candidate = get_email_signal_or_404(candidate_id)
    return reject_email_signal_candidate(workspace, candidate, payload)


@app.post("/api/pipeline-sync/status")
def get_pipeline_sync_status(payload: PipelineSyncRequest) -> PipelineSyncResult:
    result = pipeline_sync_status(payload)
    workspace.write(
        "sync_runs",
        {
            "sync_id": f"pipeline_sync_{payload.provider}_{now_iso().replace(':', '').replace('+', '_')}",
            "kind": "pipeline_sync",
            **dump(result),
        },
        "sync_id",
    )
    return result


@app.get("/api/report")
def get_report():
    profile = latest_profile()
    targets = [Target(**item) for item in workspace.list("targets")]
    applications = [ApplicationRecord(**item) for item in workspace.list("applications")]
    report = build_workspace_report(profile, targets, applications)
    workspace.write("reports", report, "report_id")
    return report


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
