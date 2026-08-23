from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from models import new_id, now_iso
from pydantic import BaseModel, Field

MemoryKind = Literal["fact", "working", "episodic", "semantic", "procedural", "feedback"]
MemoryStatus = Literal["candidate", "confirmed", "rejected", "expired"]


class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: new_id("mem"))
    kind: MemoryKind
    scope: str = "workspace"
    key: str
    value: Dict[str, Any] = Field(default_factory=dict)
    source_ref: str = ""
    confidence: float = 0.0
    status: MemoryStatus = "candidate"
    retention: str = "long_term"
    version: int = 1
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    expires_at: str = ""


class MemorySummary(BaseModel):
    total: int = 0
    by_kind: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    latest_keys: List[str] = Field(default_factory=list)


class LocalMemoryManager:
    """Append-only local memory with explicit confirmation transitions."""

    def __init__(self, workspace_or_path):
        self.path = _memory_path(workspace_or_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_candidate(
        self,
        *,
        kind: MemoryKind,
        key: str,
        value: Dict[str, Any],
        source_ref: str = "",
        confidence: float = 0.0,
        retention: str = "long_term",
        expires_at: str = "",
    ) -> MemoryRecord:
        record = MemoryRecord(
            kind=kind,
            key=key,
            value=value,
            source_ref=source_ref,
            confidence=max(0.0, min(1.0, confidence)),
            retention=retention,
            expires_at=expires_at,
        )
        self._append(record)
        return record

    def confirm(self, memory_id: str) -> MemoryRecord:
        return self._transition(memory_id, "confirmed")

    def reject(self, memory_id: str) -> MemoryRecord:
        return self._transition(memory_id, "rejected")

    def search(
        self,
        query: str,
        *,
        kinds: Optional[Iterable[MemoryKind]] = None,
        include_candidates: bool = True,
        include_rejected: bool = False,
        limit: int = 20,
    ) -> List[MemoryRecord]:
        terms = [term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]+", query or "")]
        allowed_kinds = set(kinds or [])
        records = []
        for record in self.records():
            if allowed_kinds and record.kind not in allowed_kinds:
                continue
            if not include_candidates and record.status == "candidate":
                continue
            if not include_rejected and record.status == "rejected":
                continue
            haystack = json.dumps(record.value, ensure_ascii=False).lower() + record.key.lower()
            if terms and not all(term in haystack for term in terms):
                continue
            records.append(record)
        return records[-max(limit, 0) :]

    def records(self) -> List[MemoryRecord]:
        if not self.path.exists():
            return []
        return [
            MemoryRecord(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def summarize(self) -> MemorySummary:
        records = self.records()
        by_kind: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for record in records:
            by_kind[record.kind] = by_kind.get(record.kind, 0) + 1
            by_status[record.status] = by_status.get(record.status, 0) + 1
        return MemorySummary(
            total=len(records),
            by_kind=by_kind,
            by_status=by_status,
            latest_keys=[record.key for record in records[-5:]],
        )

    def _transition(self, memory_id: str, status: MemoryStatus) -> MemoryRecord:
        records = self.records()
        for index, record in enumerate(records):
            if record.memory_id == memory_id:
                updated = record.model_copy(update={"status": status, "updated_at": now_iso()})
                records[index] = updated
                self._rewrite(records)
                return updated
        raise KeyError(f"Memory record not found: {memory_id}")

    def _append(self, record: MemoryRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            payload = record.model_dump() if hasattr(record, "model_dump") else record.dict()
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _rewrite(self, records: List[MemoryRecord]) -> None:
        self.path.write_text(
            "\n".join(
                json.dumps(
                    record.model_dump() if hasattr(record, "model_dump") else record.dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                for record in records
            )
            + ("\n" if records else ""),
            encoding="utf-8",
        )


def _memory_path(workspace_or_path) -> Path:
    root = workspace_or_path.root if hasattr(workspace_or_path, "root") else Path(workspace_or_path)
    return Path(root) / "memory" / "records.jsonl"
