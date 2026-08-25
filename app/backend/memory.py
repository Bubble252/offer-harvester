from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from models import new_id, now_iso
from pydantic import BaseModel, Field

MemoryKind = Literal["fact", "working", "episodic", "semantic", "procedural", "feedback"]
MEMORY_KINDS: tuple[str, ...] = (
    "fact",
    "working",
    "episodic",
    "semantic",
    "procedural",
    "feedback",
)
MemoryStatus = Literal[
    "candidate",
    "confirmed",
    "rejected",
    "expired",
    "superseded",
    "archived",
    "tombstone",
]
PromotionTarget = Literal["profile", "knowledge_base", "tracker", "template", "skill", "rule"]
PromotionStatus = Literal["candidate", "approved", "rejected", "applied"]

AUTHORITY_RANK = {
    "user_confirmed": 100,
    "official": 90,
    "audited_knowledge": 80,
    "user": 70,
    "local_upload": 65,
    "web_supplement": 50,
    "session_summary": 35,
    "llm": 20,
    "inferred": 10,
}

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
    run_id: str = ""
    negative: bool = False
    blocked_patterns: List[str] = Field(default_factory=list)
    last_confirmed_at: str = ""
    last_used_at: str = ""
    usage_count: int = 0
    decay_policy: str = ""
    created_event_ref: str = ""
    last_verified_at: str = ""
    deletion_reason: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    expires_at: str = ""
    notes: str = ""


class MemorySummary(BaseModel):
    total: int = 0
    by_kind: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    latest_keys: List[str] = Field(default_factory=list)


class MemoryLayerIndex(BaseModel):
    total: int = 0
    by_kind: Dict[str, int] = Field(default_factory=dict)
    by_scope: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    layer_files: Dict[str, str] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=now_iso)


class MemoryPromotionCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("mpc"))
    memory_id: str
    target: PromotionTarget
    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)
    source_status: MemoryStatus = "candidate"
    status: PromotionStatus = "candidate"
    reason: str = ""
    requires_user_confirmation: bool = True
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class SessionSummary(BaseModel):
    run_id: str
    goal: str = ""
    key_facts: List[str] = Field(default_factory=list)
    confirmed_items: List[str] = Field(default_factory=list)
    unconfirmed_items: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)


class FeedbackRecord(BaseModel):
    feedback_id: str = Field(default_factory=lambda: new_id("fb"))
    feedback_type: str
    subject_ref: str = ""
    before_ref: str = ""
    after_ref: str = ""
    issue_category: str = ""
    accepted: Optional[bool] = None
    evidence_refs: List[str] = Field(default_factory=list)
    suggested_candidate_type: Literal["skill", "rule", "prompt", "none"] = "none"
    created_at: str = Field(default_factory=now_iso)


class LocalMemoryManager:
    """Append-only local memory with explicit confirmation transitions."""

    def __init__(self, workspace_or_path):
        self.root = _memory_root(workspace_or_path)
        self.path = self.root / "records.jsonl"
        self.layers_dir = self.root / "layers"
        self.index_path = self.root / "index.json"
        self.promotions_path = self.root / "promotion_candidates.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)
        self.layers_dir.mkdir(parents=True, exist_ok=True)

    def write_candidate(
        self,
        *,
        kind: MemoryKind,
        key: str,
        value: Dict[str, Any],
        scope: str = "workspace",
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
        created_event_ref: str = "",
        run_id: str = "",
        negative: bool = False,
        blocked_patterns: Optional[List[str]] = None,
        decay_policy: str = "",
    ) -> MemoryRecord:
        refs = list(dict.fromkeys([source_ref] + list(source_refs or [])))
        refs = [ref for ref in refs if ref]
        record = MemoryRecord(
            kind=kind,
            scope=scope,
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
            created_event_ref=created_event_ref,
            run_id=run_id,
            negative=negative,
            blocked_patterns=blocked_patterns or [],
            decay_policy=decay_policy,
            last_verified_at=now_iso() if authority in {"user", "official"} else "",
        )
        self._append(record)
        return record

    def confirm(self, memory_id: str) -> MemoryRecord:
        return self._transition(
            memory_id,
            "confirmed",
            extra={"last_confirmed_at": now_iso()},
        )

    def reject(self, memory_id: str, *, reason: str = "") -> MemoryRecord:
        return self._transition(memory_id, "rejected", note=reason)

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
        scope: str = "workspace",
        source_ref: str = "",
        source_refs: Optional[List[str]] = None,
        authority: str = "user",
        confidence: float = 0.0,
        retention: str = "long_term",
        sensitivity: Literal["low", "medium", "high"] = "medium",
        notes: str = "",
        created_event_ref: str = "",
        run_id: str = "",
    ) -> MemoryRecord:
        records = self.records()
        old_index = _find_index(records, old_memory_id)
        old = records[old_index]
        _ensure_transition(old.status, "superseded")
        replacement = MemoryRecord(
            kind=kind,
            scope=scope,
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
            created_event_ref=created_event_ref,
            run_id=run_id,
            last_verified_at=now_iso() if authority in {"user", "official"} else "",
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

    def write_working_memory(
        self,
        *,
        run_id: str,
        key: str,
        value: Dict[str, Any],
        source_refs: Optional[List[str]] = None,
        notes: str = "",
    ) -> MemoryRecord:
        if not run_id.strip():
            raise ValueError("run_id is required for working memory")
        return self.write_candidate(
            kind="working",
            scope=f"workflow:{run_id}",
            key=key,
            value=value,
            source_refs=source_refs,
            authority="session_summary",
            confidence=0.5,
            retention="short_term",
            run_id=run_id,
            notes=notes,
        )

    def create_session_summary(self, summary: SessionSummary) -> MemoryRecord:
        return self.write_candidate(
            kind="episodic",
            scope=f"workflow:{summary.run_id}",
            key=f"session_summary.{summary.run_id}",
            value=summary.model_dump() if hasattr(summary, "model_dump") else summary.dict(),
            source_refs=summary.evidence_refs,
            authority="session_summary",
            confidence=0.7,
            retention="long_term",
            run_id=summary.run_id,
            notes="generated session summary; original WorkflowEvent records remain replayable",
        )

    def write_negative_memory(
        self,
        *,
        key: str,
        value: Dict[str, Any],
        scope: str = "workspace",
        reason: str = "",
        blocked_patterns: Optional[List[str]] = None,
        source_ref: str = "",
    ) -> MemoryRecord:
        return self.write_candidate(
            kind="semantic",
            scope=scope,
            key=key,
            value=value,
            source_ref=source_ref,
            authority="user_confirmed",
            confidence=1.0,
            negative=True,
            blocked_patterns=blocked_patterns or [key],
            notes=reason,
        )

    def is_blocked_by_negative_memory(self, text: str, *, scope: str = "workspace") -> bool:
        normalized = _normalize_text(text)
        for record in self.search(
            "",
            kinds=["semantic"],
            scopes=[scope, "workspace", "global"],
            include_candidates=True,
            include_negative=True,
        ):
            if not record.negative or record.status not in {"candidate", "confirmed"}:
                continue
            patterns = record.blocked_patterns or [record.key]
            if any(_normalize_text(pattern) in normalized for pattern in patterns if pattern):
                return True
        return False

    def write_feedback(self, feedback: FeedbackRecord, *, scope: str = "workspace") -> MemoryRecord:
        payload = feedback.model_dump() if hasattr(feedback, "model_dump") else feedback.dict()
        return self.write_candidate(
            kind="feedback",
            scope=scope,
            key=f"feedback.{feedback.issue_category or feedback.feedback_type}.{feedback.feedback_id}",
            value=payload,
            source_refs=feedback.evidence_refs,
            authority="user" if feedback.accepted is not None else "inferred",
            confidence=0.8 if feedback.accepted is not None else 0.4,
            notes="feedback memory can only create skill/rule/prompt candidates",
        )

    def create_promotion_candidate(
        self,
        memory_id: str,
        *,
        target: PromotionTarget,
        reason: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> MemoryPromotionCandidate:
        record = self.get(memory_id)
        if record.status != "confirmed":
            raise ValueError("Only confirmed memory can create promotion candidates")
        if record.negative and target in {"profile", "tracker"}:
            raise ValueError("Negative memory cannot be promoted into profile or tracker")
        candidate = MemoryPromotionCandidate(
            memory_id=memory_id,
            target=target,
            payload=payload or _default_promotion_payload(record),
            evidence_refs=record.source_refs or ([record.source_ref] if record.source_ref else []),
            source_status=record.status,
            reason=reason,
        )
        self._append_promotion(candidate)
        return candidate

    def promotion_candidates(
        self,
        *,
        status: Optional[PromotionStatus] = None,
        target: Optional[PromotionTarget] = None,
    ) -> List[MemoryPromotionCandidate]:
        items = _read_jsonl(self.promotions_path, MemoryPromotionCandidate)
        if status:
            items = [item for item in items if item.status == status]
        if target:
            items = [item for item in items if item.target == target]
        return items

    def update_promotion_status(
        self,
        candidate_id: str,
        status: PromotionStatus,
        *,
        reason: str = "",
    ) -> MemoryPromotionCandidate:
        candidates = self.promotion_candidates()
        for index, candidate in enumerate(candidates):
            if candidate.candidate_id == candidate_id:
                updated = candidate.model_copy(
                    update={
                        "status": status,
                        "reason": _append_note(candidate.reason, reason),
                        "updated_at": now_iso(),
                    }
                )
                candidates[index] = updated
                self._rewrite_promotions(candidates)
                return updated
        raise KeyError(f"Memory promotion candidate not found: {candidate_id}")

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
        if memory_id == conflict_memory_id:
            raise ValueError("A memory record cannot conflict with itself")
        first = records[first_index]
        second = records[second_index]
        if "tombstone" in {first.status, second.status}:
            raise ValueError("Tombstone records cannot participate in conflicts")
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
        _ensure_transition(record.status, "tombstone")
        tombstone = record.model_copy(
            update={
                "status": "tombstone",
                "value": {},
                "confidence": 0.0,
                "source_ref": "",
                "source_refs": [],
                "updated_at": now_iso(),
                "notes": _append_note(record.notes, reason or "deleted"),
                "deletion_reason": reason or "deleted",
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
        kinds: Optional[Iterable[MemoryKind]] = None,
        scopes: Optional[Iterable[str]] = None,
        source_refs: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        output = []
        for record in self.records():
            if not _matches_filters(record, kinds=kinds, scopes=scopes, source_refs=source_refs):
                continue
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
        kinds: Optional[Iterable[MemoryKind]] = None,
        scopes: Optional[Iterable[str]] = None,
        source_refs: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        events = []
        for record in self.records():
            if not _matches_filters(record, kinds=kinds, scopes=scopes, source_refs=source_refs):
                continue
            if record.status == "tombstone" and not include_deleted:
                continue
            events.append(
                {
                    "memory_id": record.memory_id,
                    "kind": record.kind,
                    "scope": record.scope,
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
        scopes: Optional[Iterable[str]] = None,
        include_candidates: bool = True,
        include_rejected: bool = False,
        include_historical: bool = False,
        include_negative: bool = False,
        limit: int = 20,
    ) -> List[MemoryRecord]:
        terms = [term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]+", query or "")]
        allowed_kinds = set(kinds or [])
        allowed_scopes = set(scopes or [])
        records = []
        for record in self.ranked_records():
            if allowed_kinds and record.kind not in allowed_kinds:
                continue
            if allowed_scopes and record.scope not in allowed_scopes:
                continue
            if not include_negative and record.negative:
                continue
            if not include_candidates and record.status == "candidate":
                continue
            if not include_rejected and record.status in {"rejected", "tombstone"}:
                continue
            if not include_historical and record.status in {"expired", "superseded", "archived"}:
                continue
            haystack = json.dumps(record.value, ensure_ascii=False).lower() + record.key.lower()
            if terms and not all(term in haystack for term in terms):
                continue
            records.append(record)
        return records[-max(limit, 0) :]

    def ranked_records(self) -> List[MemoryRecord]:
        return sorted(
            self.records(),
            key=lambda record: (
                _status_rank(record.status),
                AUTHORITY_RANK.get(record.authority, 0),
                record.confidence,
                record.updated_at,
            ),
        )

    def get(self, memory_id: str) -> MemoryRecord:
        return self.records()[_find_index(self.records(), memory_id)]

    def delete_matching(
        self,
        *,
        kinds: Optional[Iterable[MemoryKind]] = None,
        scopes: Optional[Iterable[str]] = None,
        source_refs: Optional[Iterable[str]] = None,
        reason: str = "",
    ) -> List[MemoryRecord]:
        records = self.records()
        changed: List[MemoryRecord] = []
        for index, record in enumerate(records):
            if record.status == "tombstone":
                continue
            if not _matches_filters(record, kinds=kinds, scopes=scopes, source_refs=source_refs):
                continue
            _ensure_transition(record.status, "tombstone")
            tombstone = record.model_copy(
                update={
                    "status": "tombstone",
                    "value": {},
                    "confidence": 0.0,
                    "source_ref": "",
                    "source_refs": [],
                    "updated_at": now_iso(),
                    "notes": _append_note(record.notes, reason or "bulk deleted"),
                    "deletion_reason": reason or "bulk deleted",
                }
            )
            records[index] = tombstone
            changed.append(tombstone)
        if changed:
            self._rewrite(records)
        return changed

    def records(self) -> List[MemoryRecord]:
        records = _read_jsonl(self.path, MemoryRecord)
        if records:
            return records
        merged: Dict[str, MemoryRecord] = {}
        for kind in MEMORY_KINDS:
            for record in _read_jsonl(self._layer_path(kind), MemoryRecord):
                merged[record.memory_id] = record
        return list(merged.values())

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
        extra: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        records = self.records()
        for index, record in enumerate(records):
            if record.memory_id == memory_id:
                _ensure_transition(record.status, status)
                updates = {
                    "status": status,
                    "updated_at": now_iso(),
                    "notes": _append_note(record.notes, note),
                }
                updates.update(extra or {})
                updated = record.model_copy(update=updates)
                records[index] = updated
                self._rewrite(records)
                return updated
        raise KeyError(f"Memory record not found: {memory_id}")

    def _append(self, record: MemoryRecord) -> None:
        payload = record.model_dump() if hasattr(record, "model_dump") else record.dict()
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        with self._layer_path(record.kind).open("a", encoding="utf-8") as handle:
            handle.write(line)
        self._write_index(self.records())

    def _rewrite(self, records: List[MemoryRecord]) -> None:
        self._write_jsonl(self.path, records)
        for kind in MEMORY_KINDS:
            self._write_jsonl(
                self._layer_path(kind),
                [record for record in records if record.kind == kind],
            )
        self._write_index(records)

    def _layer_path(self, kind: str) -> Path:
        path = self.layers_dir / kind / "records.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _append_promotion(self, candidate: MemoryPromotionCandidate) -> None:
        with self.promotions_path.open("a", encoding="utf-8") as handle:
            payload = (
                candidate.model_dump() if hasattr(candidate, "model_dump") else candidate.dict()
            )
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _rewrite_promotions(self, candidates: List[MemoryPromotionCandidate]) -> None:
        self._write_jsonl(self.promotions_path, candidates)

    def _write_index(self, records: List[MemoryRecord]) -> None:
        by_kind: Dict[str, int] = {}
        by_scope: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for record in records:
            by_kind[record.kind] = by_kind.get(record.kind, 0) + 1
            by_scope[record.scope] = by_scope.get(record.scope, 0) + 1
            by_status[record.status] = by_status.get(record.status, 0) + 1
        index = MemoryLayerIndex(
            total=len(records),
            by_kind=by_kind,
            by_scope=by_scope,
            by_status=by_status,
            layer_files={
                kind: str(self._layer_path(kind).relative_to(self.root)) for kind in MEMORY_KINDS
            },
        )
        payload = index.model_dump() if hasattr(index, "model_dump") else index.dict()
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")

    def _write_jsonl(self, path: Path, records: Iterable[BaseModel]) -> None:
        records = list(records)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
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
    return _memory_root(workspace_or_path) / "records.jsonl"


def _memory_root(workspace_or_path) -> Path:
    root = workspace_or_path.root if hasattr(workspace_or_path, "root") else Path(workspace_or_path)
    return Path(root) / "memory"


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


def _read_jsonl(path: Path, model):
    if not path.exists():
        return []
    return [
        model(**json.loads(line)) for line in path.read_text("utf-8").splitlines() if line.strip()
    ]


def _matches_filters(
    record: MemoryRecord,
    *,
    kinds: Optional[Iterable[MemoryKind]] = None,
    scopes: Optional[Iterable[str]] = None,
    source_refs: Optional[Iterable[str]] = None,
) -> bool:
    allowed_kinds = set(kinds or [])
    allowed_scopes = set(scopes or [])
    allowed_sources = set(source_refs or [])
    if allowed_kinds and record.kind not in allowed_kinds:
        return False
    if allowed_scopes and record.scope not in allowed_scopes:
        return False
    if allowed_sources:
        refs = set(record.source_refs or ([record.source_ref] if record.source_ref else []))
        if not refs.intersection(allowed_sources):
            return False
    return True


def _status_rank(status: MemoryStatus) -> int:
    return {
        "confirmed": 60,
        "candidate": 50,
        "rejected": 20,
        "expired": 10,
        "superseded": 5,
        "archived": 1,
        "tombstone": 0,
    }[status]


def _normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[\w\u4e00-\u9fff]+", (text or "").lower()))


def _default_promotion_payload(record: MemoryRecord) -> Dict[str, Any]:
    return {
        "kind": record.kind,
        "scope": record.scope,
        "key": record.key,
        "value": record.value,
        "authority": record.authority,
        "confidence": record.confidence,
        "source_refs": record.source_refs or ([record.source_ref] if record.source_ref else []),
    }
