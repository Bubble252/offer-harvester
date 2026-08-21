from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import run_contact_email_workflow
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from llm_client import llm_configured
from models import (
    AdvisorProfile,
    AdvisorProfileUpdate,
    AdvisorSource,
    AdvisorSourceCreate,
    AdvisorTargetCreate,
    ApplicationRecord,
    ApplicationUpdate,
    GeneratedMaterial,
    MatchReport,
    PresentationGenerationRequest,
    PresentationTaskRecord,
    StudentProfile,
    Target,
    TargetCreate,
    UserDocumentManifest,
    now_iso,
)
from quality import audit_material
from services import (
    build_profile_from_text,
    build_workspace_report,
    create_advisor_source,
    ensure_application,
    make_interview_questions,
    make_match,
    make_ppt_outline,
    parse_advisor_profile,
)
from storage import Workspace

from integrations.presentation_engine import LocalPptxAdapter, PresentationRequest

APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = APP_ROOT / "frontend"

app = FastAPI(title="Grad Apply Workflow", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
workspace = Workspace(str(PROJECT_ROOT / "workspace"))
ppt_adapter = LocalPptxAdapter()


def dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def latest_profile() -> Optional[StudentProfile]:
    item = workspace.latest("profiles")
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


def latest_match(target_id: str):
    matches = [item for item in workspace.list("matches") if item["target_id"] == target_id]
    return MatchReport(**matches[-1]) if matches else None


def save_material_with_quality(material: GeneratedMaterial):
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile is required for quality audit")
    workspace.write("generated", dump(material), "material_id")
    target = get_target_or_404(material.target_id)
    quality = audit_material(material, profile, advisor_for_target(target))
    workspace.write("quality_reports", dump(quality), "quality_id")
    return {"material": material, "quality": quality}


def get_presentation_task_or_404(task_id: str) -> PresentationTaskRecord:
    item = workspace.read("presentation_tasks", task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Presentation task not found")
    return PresentationTaskRecord(**item)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/llm/status")
def llm_status():
    return {"configured": llm_configured()}


@app.post("/api/profile/upload")
async def upload_profile(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    category: str = Form("manual_inputs"),
):
    content_parts = []
    source_document_ids = []
    if text.strip():
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
        content_parts.append(text)
    if file:
        blob = await file.read()
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
        content_parts.append(blob.decode("utf-8", errors="ignore"))
    content = "\n\n".join(part for part in content_parts if part.strip())
    if not content.strip():
        raise HTTPException(status_code=400, detail="Profile text is required")
    profile = build_profile_from_text(content, source_document_ids=source_document_ids)
    workspace.write("profiles", dump(profile), "profile_id")
    return profile


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
    advisor = parse_advisor_profile(sources)
    if advisor_id:
        advisor.advisor_id = advisor_id
    workspace.write("advisors", dump(advisor), "advisor_id")
    return {"source": source, "advisor": advisor}


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
    report = make_match(latest_profile(), target, advisor_for_target(target))
    workspace.write("matches", dump(report), "match_id")
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
    material = make_interview_questions(profile, target, advisor_for_target(target))
    return save_material_with_quality(material)


@app.post("/api/targets/{target_id}/materials/ppt-outline")
def generate_ppt_outline(target_id: str):
    profile = latest_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile is required")
    target = get_target_or_404(target_id)
    material = make_ppt_outline(profile, target, advisor_for_target(target))
    return save_material_with_quality(material)


@app.get("/api/generated")
def list_generated():
    return workspace.list("generated")


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
    task = PresentationTaskRecord(
        target_id=target.target_id,
        outline_material_id=outline.material_id,
        status="running",
        progress=15,
        message="正在生成可编辑 PPTX。",
        updated_at=now_iso(),
    )
    workspace.write("presentation_tasks", dump(task), "task_id")
    try:
        result = ppt_adapter.generate(
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
    item = workspace.read("applications", application_id)
    if not item:
        raise HTTPException(status_code=404, detail="Application not found")
    changes = {key: value for key, value in dump(updates).items() if value is not None}
    item.update(changes)
    item["updated_at"] = now_iso()
    record = ApplicationRecord(**item)
    workspace.write("applications", dump(record), "application_id")
    return record


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
