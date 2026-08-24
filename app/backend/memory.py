from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from models import new_id, now_iso
from pydantic import BaseModel, Field

MemoryKind = Literal["fact", "working", "episodic", "semantic", "procedural", "feedback"]
MemoryStatus = Literal[
    "candidate",
    "confirmed",
    "rejected",
    "expired",
    "superseded",
    "archived",
    "tombstone",
]

ALLOWED_TRANSITIONS = {
    "candidate": {"confirmed", "rejected", "expired", "superseded", "archived", "tombstone"},
    "confirmed": {"rejected", "expired", "superseded", "archived", "tombstone"},
    "rejected": {"archived", "tombstone"},
    "expired": {"archived", "tombstone"},
    "superseded": {"archived", "tombstone"},
    "archived": {"tombstone"},
    "tombstone": set(),
}


class MemoryRecord(BaseModel):
    memory_id: str = Field(default_factory=lambda: new_id("mem"))
    kind: MemoryKind
    scope: str = "workspace"
    key: str
    value: Dict[str, Any] = Field(default_factory=dict)
    source_ref: str = ""
    source_refs: List[str] = Field(default_factory=list)
    authority: str = "user"
    confidence: float = 0.0
    status: MemoryStatus = "candidate"
    valid_from: str = ""
    valid_to: str = ""
    supersedes: List[str] = Field(default_factory=list)
    superseded_by: str = ""
    conflicts_with: List[str] = Field(default_factory=list)
    retention: str = "long_term"
    sensitivity: Literal["low", "medium", "high"] = "medium"
    version: int = 1
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    expires_at: str = ""
    notes: str = ""


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
        source_refs: Optional[List[str]] = None,
        authority: str = "user",
        confidence: float = 0.0,
        retention: str = "long_term",
        expires_at: str = "",
        valid_from: str = "",
        valid_to: str = "",
        sensitivity: Literal["low", "medium", "high"] = "medium",
        conflicts_with: Optional[List[str]] = None,
        notes: str = "",
    ) -> MemoryRecord:
        refs = list(dict.fromkeys([source_ref] + list(source_refs or [])))
        refs = [ref for ref in refs if ref]
        record = MemoryRecord(
            kind=kind,
            key=key,
            value=value,
            source_ref=source_ref,
            source_refs=refs,
            authority=authority,
            confidence=max(0.0, min(1.0, confidence)),
            retention=retention,
            expires_at=expires_at,
            valid_from=valid_from,
            valid_to=valid_to,
            sensitivity=sensitivity,
            conflicts_with=conflicts_with or [],
            notes=notes,
        )
        self._append(record)
        return record

    def confirm(self, memory_id: str) -> MemoryRecord:
        return self._transition(memory_id, "confirmed")

    def reject(self, memory_id: str) -> MemoryRecord:
        return self._transition(memory_id, "rejected")

    def expire(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
        return self._transition(memory_id, "expired", note=reason)

    def archive(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
        return self._transition(memory_id, "archived", note=reason)

    def supersede(
        self,
        old_memory_id: str,
        *,
        kind: MemoryKind,
        key: str,
        value: Dict[str, Any],
        source_ref: str = "",
        source_refs: Optional[List[str]] = None,
        authority: str = "user",
        confidence: float = 0.0,
        retention: str = "long_term",
        sensitivity: Literal["low", "medium", "high"] = "medium",
        notes: str = "",
    ) -> MemoryRecord:
        records = self.records()
        old_index = _find_index(records, old_memory_id)
        old = records[old_index]
        _ensure_transition(old.status, "superseded")
        replacement = MemoryRecord(
            kind=kind,
            key=key,
            value=value,
            source_ref=source_ref,
            source_refs=list(dict.fromkeys([source_ref] + list(source_refs or []))),
            authority=authority,
            confidence=max(0.0, min(1.0, confidence)),
            status="candidate",
            retention=retention,
            supersedes=[old_memory_id],
            sensitivity=sensitivity,
            version=old.version + 1,
            notes=notes,
        )
        records[old_index] = old.model_copy(
            update={
                "status": "superseded",
                "superseded_by": replacement.memory_id,
                "updated_at": now_iso(),
                "notes": _append_note(old.notes, notes or "superseded"),
            }
        )
        records.append(replacement)
        self._rewrite(records)
        return replacement

    def mark_conflict(
        self,
        memory_id: str,
        conflict_memory_id: str,
        *,
        reason: str = "",
    ) -> MemoryRecord:
        records = self.records()
        first_index = _find_index(records, memory_id)
        second_index = _find_index(records, conflict_memory_id)
        first = records[first_index]
        second = records[second_index]
        records[first_index] = first.model_copy(
            update={
                "conflicts_with": _unique(first.conflicts_with + [conflict_memory_id]),
                "updated_at": now_iso(),
                "notes": _append_note(first.notes, reason),
            }
        )
        records[second_index] = second.model_copy(
            update={
                "conflicts_with": _unique(second.conflicts_with + [memory_id]),
                "updated_at": now_iso(),
                "notes": _append_note(second.notes, reason),
            }
        )
        self._rewrite(records)
        return records[first_index]

    def delete(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
        records = self.records()
        index = _find_index(records, memory_id)
        record = records[index]
        tombstone = record.model_copy(
            update={
                "status": "tombstone",
                "value": {},
                "confidence": 0.0,
                "source_ref": "",
                "source_refs": [],
                "updated_at": now_iso(),
                "notes": _append_note(record.notes, reason or "deleted"),
            }
        )
        records[index] = tombstone
        self._rewrite(records)
        return tombstone

    def export_records(
        self,
        *,
        include_deleted: bool = False,
        include_high_sensitivity: bool = False,
    ) -> List[Dict[str, Any]]:
        output = []
        for record in self.records():
            if not include_deleted and record.status == "tombstone":
                continue
            payload = record.model_dump() if hasattr(record, "model_dump") else record.dict()
            if record.sensitivity == "high" and not include_high_sensitivity:
                payload = {
                    **payload,
                    "value": {},
                    "redacted": True,
                }
            output.append(payload)
        return output

    def replay(
        self,
        *,
        include_deleted: bool = True,
    ) -> List[Dict[str, Any]]:
        events = []
        for record in self.records():
            if record.status == "tombstone" and not include_deleted:
                continue
            events.append(
                {
                    "memory_id": record.memory_id,
                    "kind": record.kind,
                    "key": record.key,
                    "status": record.status,
                    "version": record.version,
                    "supersedes": record.supersedes,
                    "superseded_by": record.superseded_by,
                    "conflicts_with": record.conflicts_with,
                    "source_refs": record.source_refs
                    or ([record.source_ref] if record.source_ref else []),
                    "updated_at": record.updated_at,
                    "notes": record.notes,
                }
            )
        return events

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
            if not include_rejected and record.status in {"rejected", "tombstone"}:
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

    def _transition(
        self,
        memory_id: str,
        status: MemoryStatus,
        *,
        note: str = "",
    ) -> MemoryRecord:
        records = self.records()
        for index, record in enumerate(records):
            if record.memory_id == memory_id:
                _ensure_transition(record.status, status)
                updated = record.model_copy(
                    update={
                        "status": status,
                        "updated_at": now_iso(),
                        "notes": _append_note(record.notes, note),
                    }
                )
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


def _find_index(records: List[MemoryRecord], memory_id: str) -> int:
    for index, record in enumerate(records):
        if record.memory_id == memory_id:
            return index
    raise KeyError(f"Memory record not found: {memory_id}")


def _unique(values: Iterable[str]) -> List[str]:
    return [value for value in dict.fromkeys(values) if value]


def _append_note(current: str, note: str) -> str:
    note = (note or "").strip()
    if not note:
        return current
    return f"{current}\n{note}".strip() if current else note


def _ensure_transition(current: MemoryStatus, target: MemoryStatus) -> None:
    if current == target:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid memory status transition: {current} -> {target}")
