from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List

from models import (
    AdvisorSource,
    KnowledgeBaseSource,
    KnowledgeBaseSourceCreate,
    RAGChunk,
    now_iso,
)
from services import fetch_url_text
from storage import Workspace

from rag.chunking import chunk_source, normalize_text

TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv"}


class KnowledgeBaseIndex:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def add_source(self, payload: KnowledgeBaseSourceCreate) -> KnowledgeBaseSource:
        raw_text = payload.text.strip()
        cleaned_text = normalize_text(raw_text)
        url = payload.url.strip()
        if url:
            _, fetched_text = fetch_url_text(url)
            raw_text = fetched_text
            cleaned_text = normalize_text(fetched_text)
        if not cleaned_text:
            raise ValueError("Knowledge source text or URL content is required")

        source = KnowledgeBaseSource(
            source_kind=payload.source_kind,
            source_subtype=payload.source_subtype.strip()
            or payload.source_ref.strip()
            or payload.source_kind,
            title=payload.title or payload.url or payload.source_ref or "未命名知识条目",
            url=url,
            source_ref=payload.source_ref,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            content_hash=f"sha256:{hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}",
            valid_for_year=payload.valid_for_year,
            trusted=payload.trusted,
            confirmed=payload.confirmed,
            notes=payload.notes,
        )
        self._write_source(source)
        self._write_manifest(self.list_sources())
        return source

    def list_sources(self) -> List[KnowledgeBaseSource]:
        sources = []
        for path in sorted(self.workspace.knowledge_base_sources_dir().glob("*.json")):
            sources.append(KnowledgeBaseSource(**json.loads(path.read_text(encoding="utf-8"))))
        return sources

    def rebuild(self) -> Dict[str, object]:
        sources = list(self.iter_sources())
        chunks: List[RAGChunk] = []
        for source in sources:
            chunks.extend(chunk_source(source))
        self.write_chunks(chunks)
        manifest = {
            "rebuilt_at": now_iso(),
            "source_count": len(sources),
            "chunk_count": len(chunks),
            "source_ids": [source.source_id for source in sources],
            "index_version": "bm25-lite-v1",
        }
        self.workspace.rag_index_manifest_path().write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def load_chunks(self) -> List[RAGChunk]:
        path = self.workspace.rag_chunks_path()
        if not path.exists():
            return []
        chunks = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(RAGChunk(**json.loads(line)))
        return chunks

    def write_chunks(self, chunks: Iterable[RAGChunk]) -> None:
        path = self.workspace.rag_chunks_path()
        lines = [json.dumps(_dump(chunk), ensure_ascii=False, sort_keys=True) for chunk in chunks]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def iter_sources(self) -> Iterable[KnowledgeBaseSource]:
        # Only factual inputs are indexed here. Generated outputs stay in
        # generated/ and material_versions/ and are intentionally excluded.
        yield from self._student_document_sources()
        yield from self._advisor_sources()
        yield from self.list_sources()

    def _student_document_sources(self) -> Iterable[KnowledgeBaseSource]:
        manifest = self.workspace.read_user_document_manifest()
        for record in manifest.get("documents", []):
            document_id = record.get("document_id", "")
            relative_path = record.get("path", "")
            if not document_id or not relative_path:
                continue
            path = (self.workspace.root / relative_path).resolve()
            if not _is_within(path, self.workspace.root) or not path.exists():
                continue
            text = _read_text_file(path)
            if not text:
                continue
            yield KnowledgeBaseSource(
                source_id=document_id,
                source_kind="student_document",
                source_subtype=str(record.get("category") or "manual_inputs"),
                title=record.get("original_filename", "") or document_id,
                source_ref=relative_path,
                raw_text=text,
                cleaned_text=normalize_text(text),
                content_hash=record.get("content_hash", ""),
                trusted=bool(record.get("trusted", True)),
                confirmed=bool(record.get("confirmed", False)),
                notes=record.get("notes", ""),
            )

    def _advisor_sources(self) -> Iterable[KnowledgeBaseSource]:
        for item in self.workspace.list("advisor_sources"):
            source = AdvisorSource(**item)
            text = source.cleaned_text or source.raw_text
            if not text.strip():
                continue
            yield KnowledgeBaseSource(
                source_id=source.source_id,
                source_kind="advisor_source",
                source_subtype=source.source_type,
                title=source.title or source.url or source.source_type,
                url=source.url,
                source_ref=source.source_type,
                raw_text=source.raw_text,
                cleaned_text=source.cleaned_text,
                content_hash=source.content_hash,
                fetched_at=source.fetched_at,
                trusted=source.trusted,
                confirmed=source.trusted and source.fetch_status in {"success", "manual"},
                notes=source.notes or source.fetch_error,
            )

    def _write_source(self, source: KnowledgeBaseSource) -> None:
        path = self.workspace.knowledge_base_sources_dir() / f"{source.source_id}.json"
        path.write_text(json.dumps(_dump(source), ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_manifest(self, sources: List[KnowledgeBaseSource]) -> None:
        manifest = {
            "updated_at": now_iso(),
            "source_count": len(sources),
            "sources": [
                {
                    "source_id": source.source_id,
                    "source_kind": source.source_kind,
                    "source_subtype": source.source_subtype,
                    "title": source.title,
                    "url": source.url,
                    "valid_for_year": source.valid_for_year,
                    "trusted": source.trusted,
                    "confirmed": source.confirmed,
                }
                for source in sources
            ],
        }
        self.workspace.knowledge_base_manifest_path().write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _read_text_file(path: Path) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _dump(model) -> Dict[str, object]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()
