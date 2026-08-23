from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from models import UserDocumentRecord

USER_DOCUMENT_CATEGORIES = {
    "resumes",
    "transcripts",
    "research_projects",
    "publications",
    "awards",
    "personal_statements",
    "manual_inputs",
    "web_supplements",
    "misc",
}

ALLOWED_USER_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".docx",
    ".md",
    ".txt",
    ".json",
    ".csv",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
}


class Workspace:
    def __init__(self, root: Optional[str] = None):
        env_root = os.environ.get("WORKSPACE_DIR")
        self.root = Path(root or env_root or "../../workspace").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in [
            "profiles",
            "user_documents",
            "advisor_sources",
            "advisors",
            "targets",
            "matches",
            "applications",
            "application_archives",
            "communications",
            "email_signal_candidates",
            "generated",
            "material_versions",
            "quality_reports",
            "agent_runs",
            "workflow_events",
            "presentation_tasks",
            "reference_presentations",
            "presentation_prechecks",
            "presentation_quality_reports",
            "reports",
            "readiness_scores",
            "target_triage_reports",
            "profile_expansion_candidates",
            "gap_plans",
            "template_registry",
            "templates",
            "source_connectors",
            "source_connector_live_tests",
            "pdf_readability_reports",
            "sync_runs",
            "knowledge_base",
            "rag_index",
        ]:
            (self.root / name).mkdir(exist_ok=True)
        for name in USER_DOCUMENT_CATEGORIES:
            (self.root / "user_documents" / name).mkdir(exist_ok=True)
        (self.root / "knowledge_base" / "sources").mkdir(parents=True, exist_ok=True)
        (self.root / "rag_index").mkdir(parents=True, exist_ok=True)

    def path(self, collection: str, item_id: str) -> Path:
        return self.root / collection / f"{item_id}.json"

    def write(self, collection: str, item: Dict[str, Any], id_field: str) -> Dict[str, Any]:
        item_id = item[id_field]
        self.path(collection, item_id).write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return item

    def read(self, collection: str, item_id: str) -> Optional[Dict[str, Any]]:
        path = self.path(collection, item_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, collection: str) -> List[Dict[str, Any]]:
        items = []
        for path in sorted((self.root / collection).glob("*.json")):
            items.append(json.loads(path.read_text(encoding="utf-8")))
        return items

    def latest(self, collection: str) -> Optional[Dict[str, Any]]:
        items = self.list(collection)
        return items[-1] if items else None

    def user_document_manifest_path(self) -> Path:
        return self.root / "user_documents" / "manifest.json"

    def read_user_document_manifest(self) -> Dict[str, Any]:
        path = self.user_document_manifest_path()
        if not path.exists():
            return {"documents": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_user_document_manifest(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        self.user_document_manifest_path().write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def template_workspace_dir(self) -> Path:
        return self.root / "templates"

    def template_workspace_manifest_path(self) -> Path:
        return self.template_workspace_dir() / "manifest.json"

    def template_workspace_template_dir(self, template_id: str) -> Path:
        return self.template_workspace_dir() / template_id

    def read_template_workspace_manifest(self) -> Dict[str, Any]:
        path = self.template_workspace_manifest_path()
        if not path.exists():
            return {"templates": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_template_workspace_manifest(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        self.template_workspace_manifest_path().write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def knowledge_base_dir(self) -> Path:
        return self.root / "knowledge_base"

    def knowledge_base_sources_dir(self) -> Path:
        return self.knowledge_base_dir() / "sources"

    def knowledge_base_manifest_path(self) -> Path:
        return self.knowledge_base_dir() / "manifest.json"

    def rag_index_dir(self) -> Path:
        return self.root / "rag_index"

    def rag_chunks_path(self) -> Path:
        return self.rag_index_dir() / "chunks.jsonl"

    def rag_vectors_path(self) -> Path:
        return self.rag_index_dir() / "vectors.jsonl"

    def rag_index_manifest_path(self) -> Path:
        return self.rag_index_dir() / "manifest.json"

    def save_user_document(
        self,
        content: bytes,
        original_filename: str,
        category: str = "manual_inputs",
        source_type: str = "manual_input",
        trusted: bool = True,
        confirmed: bool = False,
        notes: str = "",
    ) -> UserDocumentRecord:
        if not content:
            raise ValueError("User document content is required")
        category = category if category in USER_DOCUMENT_CATEGORIES else "misc"
        filename = safe_filename(original_filename or "manual_input.txt")
        suffix = Path(filename).suffix.lower()
        if source_type == "manual_input" and not suffix:
            filename = f"{filename}.txt"
            suffix = ".txt"
        if suffix not in ALLOWED_USER_DOCUMENT_SUFFIXES:
            raise ValueError(f"Unsupported user document format: {suffix or 'no extension'}")

        digest = hashlib.sha256(content).hexdigest()
        timestamp = datetime.now().astimezone().strftime("%Y%m%d%H%M%S")
        stem = Path(filename).stem or "document"
        stored_name = f"{stem}_{timestamp}_{digest[:10]}{suffix}"
        relative_path = Path("user_documents") / category / stored_name
        output_path = self.root / relative_path
        output_path.write_bytes(content)

        record = UserDocumentRecord(
            category=category,
            path=relative_path.as_posix(),
            original_filename=original_filename or filename,
            source_type=source_type,  # type: ignore[arg-type]
            content_hash=f"sha256:{digest}",
            trusted=trusted,
            confirmed=confirmed,
            notes=notes,
        )
        manifest = self.read_user_document_manifest()
        documents = manifest.setdefault("documents", [])
        documents.append(record.model_dump() if hasattr(record, "model_dump") else record.dict())
        self.write_user_document_manifest(manifest)
        return record


def safe_filename(value: str) -> str:
    name = Path(value).name.strip() or "document.txt"
    name = re.sub(r"[\x00-\x1f\x7f/\\:]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name)
    if len(name) > 120:
        suffix = Path(name).suffix
        name = name[: 120 - len(suffix)] + suffix
    return name or "document.txt"
