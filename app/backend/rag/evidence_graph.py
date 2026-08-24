from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Literal, Optional

from models import RAGSearchHit, new_id, now_iso
from pydantic import BaseModel, Field

EvidenceLinkRelation = Literal["supports", "contradicts", "qualifies", "context"]
EvidenceClaimStatus = Literal[
    "supported",
    "needs_confirmation",
    "unsupported",
    "stale",
    "contradicted",
]
ConflictStatus = Literal["open", "resolved", "accepted", "rejected"]


class SourceSnapshot(BaseModel):
    """A point-in-time, hash-addressed representation of a source."""

    snapshot_id: str = Field(default_factory=lambda: new_id("snapshot"))
    source_id: str
    source_kind: str = ""
    source_subtype: str = ""
    title: str = ""
    url: str = ""
    captured_at: str = Field(default_factory=now_iso)
    fetched_at: str = ""
    valid_for_year: Optional[int] = None
    content_hash: str = ""
    authority: str = "unknown"
    trust: float = 0.0
    status: Literal["current", "historical", "failed", "manual"] = "current"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChunkLineage(BaseModel):
    """Links a retrieved chunk back to its source snapshot and hierarchy."""

    lineage_id: str = Field(default_factory=lambda: new_id("lineage"))
    snapshot_id: str
    source_id: str
    chunk_id: str
    parent_chunk_id: str = ""
    section_path: List[str] = Field(default_factory=list)
    content_hash: str = ""
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Claim(BaseModel):
    claim_id: str = Field(default_factory=lambda: new_id("claim"))
    claim_key: str = ""
    claim_type: str = "retrieved_context"
    text: str = ""
    value: Any = None
    status: EvidenceClaimStatus = "needs_confirmation"
    confidence: float = 0.0
    subject_ref: str = ""
    predicate: str = ""
    object_ref: str = ""
    source_refs: List[str] = Field(default_factory=list)
    evidence_link_ids: List[str] = Field(default_factory=list)
    valid_for_year: Optional[int] = None
    needs_confirmation: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceLink(BaseModel):
    link_id: str = Field(default_factory=lambda: new_id("elink"))
    claim_id: str = ""
    snapshot_id: str = ""
    source_id: str = ""
    chunk_id: str = ""
    evidence_ref: str = ""
    relation: EvidenceLinkRelation = "context"
    strength: float = 0.0
    snippet: str = ""
    content_hash: str = ""
    retrieval_score: float = 0.0
    retrieval_explanation: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConflictSet(BaseModel):
    conflict_id: str = Field(default_factory=lambda: new_id("conflict"))
    claim_key: str
    claim_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    status: ConflictStatus = "open"
    explanation: str = ""
    resolution_ref: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class EvidenceBundle(BaseModel):
    """Auditable evidence package passed between retrieval and agents."""

    bundle_id: str = Field(default_factory=lambda: new_id("bundle"))
    query: str = ""
    created_at: str = Field(default_factory=now_iso)
    query_plan: Dict[str, Any] = Field(default_factory=dict)
    snapshot_ids: List[str] = Field(default_factory=list)
    lineages: List[ChunkLineage] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    links: List[EvidenceLink] = Field(default_factory=list)
    conflicts: List[ConflictSet] = Field(default_factory=list)
    retrieval_refs: List[str] = Field(default_factory=list)
    audit_status: Literal["pending", "passed", "needs_review", "failed"] = "pending"
    audit_ref: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LocalEvidenceGraphStore:
    """Workspace-backed bundle store; external graph/vector databases are optional."""

    def __init__(self, workspace):
        self.workspace = workspace

    def save(self, bundle: EvidenceBundle) -> EvidenceBundle:
        payload = bundle.model_dump() if hasattr(bundle, "model_dump") else bundle.dict()
        self.workspace.write("evidence_bundles", payload, "bundle_id")
        return bundle

    def get(self, bundle_id: str) -> Optional[EvidenceBundle]:
        payload = self.workspace.read("evidence_bundles", bundle_id)
        return EvidenceBundle(**payload) if payload else None

    def list(self) -> List[EvidenceBundle]:
        return [EvidenceBundle(**item) for item in self.workspace.list("evidence_bundles")]


def build_evidence_bundle(
    query: str,
    hits: Iterable[RAGSearchHit],
    *,
    query_plan: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> EvidenceBundle:
    """Turn retrieval hits into a stable, source-traceable evidence package."""

    snapshots: Dict[tuple[str, str], SourceSnapshot] = {}
    lineages: List[ChunkLineage] = []
    claims: List[Claim] = []
    links: List[EvidenceLink] = []

    for hit in hits:
        snapshot_key = (hit.source_id, hit.content_hash)
        snapshot = snapshots.get(snapshot_key)
        if snapshot is None:
            snapshot = SourceSnapshot(
                source_id=hit.source_id,
                source_kind=hit.source_kind,
                source_subtype=hit.source_subtype,
                title=hit.title,
                url=hit.url,
                fetched_at=hit.fetched_at,
                valid_for_year=hit.valid_for_year,
                content_hash=hit.content_hash,
                authority=str(hit.metadata.get("authority", "unknown")),
                trust=_bounded_score(hit.metadata.get("trust", 1.0 if not hit.historical else 0.5)),
                status="historical" if hit.historical else "current",
                metadata=dict(hit.metadata),
            )
            snapshots[snapshot_key] = snapshot

        lineage = ChunkLineage(
            snapshot_id=snapshot.snapshot_id,
            source_id=hit.source_id,
            chunk_id=hit.chunk_id,
            section_path=_as_string_list(hit.metadata.get("section_path")),
            content_hash=hit.content_hash,
            char_start=_optional_int(hit.metadata.get("char_start")),
            char_end=_optional_int(hit.metadata.get("char_end")),
            metadata=dict(hit.metadata),
        )
        lineages.append(lineage)

        claim = Claim(
            claim_key=f"retrieved:{hit.evidence_ref or hit.chunk_id}",
            claim_type="retrieved_context",
            text=hit.snippet,
            status="needs_confirmation"
            if hit.needs_confirmation
            else ("stale" if hit.historical else "supported"),
            confidence=_bounded_score(hit.confidence),
            source_refs=[hit.evidence_ref or f"{hit.source_id}#{hit.chunk_id}"],
            valid_for_year=hit.valid_for_year,
            needs_confirmation=hit.needs_confirmation or hit.historical,
            metadata={"source_snapshot_id": snapshot.snapshot_id},
        )
        link = EvidenceLink(
            claim_id=claim.claim_id,
            snapshot_id=snapshot.snapshot_id,
            source_id=hit.source_id,
            chunk_id=hit.chunk_id,
            evidence_ref=hit.evidence_ref or f"{hit.source_id}#{hit.chunk_id}",
            relation="context",
            strength=_bounded_score(hit.confidence),
            snippet=hit.snippet,
            content_hash=hit.content_hash,
            retrieval_score=_bounded_score(hit.score),
            retrieval_explanation=hit.retrieval_explanation,
            metadata=dict(hit.metadata),
        )
        claim.evidence_link_ids.append(link.link_id)
        claims.append(claim)
        links.append(link)

    bundle = EvidenceBundle(
        query=query,
        query_plan=query_plan or {"retrieval": "hybrid", "source_count": len(snapshots)},
        snapshot_ids=[snapshot.snapshot_id for snapshot in snapshots.values()],
        lineages=lineages,
        claims=claims,
        links=links,
        retrieval_refs=[link.evidence_ref for link in links],
        metadata=metadata or {},
    )
    bundle.conflicts = detect_conflicts(bundle.claims, bundle.links)
    return bundle


def attach_audit_claims(
    bundle: EvidenceBundle,
    audit_claims: Iterable[Dict[str, Any]],
    *,
    audit_ref: str = "",
    passed: bool = False,
) -> EvidenceBundle:
    """Add backend audit claims without allowing an auditor to erase conflicts."""

    claims = list(bundle.claims)
    links = list(bundle.links)
    links_by_ref = {link.evidence_ref: link for link in links}
    for item in audit_claims:
        source_refs = [str(ref) for ref in item.get("source_ids", []) if ref]
        status = _audit_status(str(item.get("status", "needs_confirmation")))
        claim = Claim(
            claim_key=str(item.get("claim_type", "audit_claim")),
            claim_type=str(item.get("claim_type", "audit_claim")),
            text=str(item.get("message", "")),
            status=status,
            confidence=1.0 if status == "supported" else 0.0,
            source_refs=source_refs,
            needs_confirmation=status in {"needs_confirmation", "stale"},
            metadata={"audit": True},
        )
        for ref in source_refs:
            link = links_by_ref.get(ref)
            if link:
                claim.evidence_link_ids.append(link.link_id)
            else:
                links.append(
                    EvidenceLink(
                        claim_id=claim.claim_id,
                        evidence_ref=ref,
                        source_id=ref,
                        relation="supports" if status == "supported" else "context",
                        strength=claim.confidence,
                    )
                )
        claims.append(claim)

    result = bundle.model_copy(
        update={
            "claims": claims,
            "links": links,
            "audit_ref": audit_ref,
            "audit_status": "passed" if passed else "needs_review",
        }
    )
    result.conflicts = detect_conflicts(result.claims, result.links)
    return result


def detect_conflicts(
    claims: Iterable[Claim],
    links: Iterable[EvidenceLink],
) -> List[ConflictSet]:
    """Detect only explicit same-key disagreements; never infer a conflict from ranking."""

    claims_by_key: Dict[str, List[Claim]] = defaultdict(list)
    for claim in claims:
        if claim.claim_key:
            claims_by_key[claim.claim_key].append(claim)
    links_by_claim = defaultdict(list)
    for link in links:
        links_by_claim[link.claim_id].append(link)

    conflicts = []
    for claim_key, grouped in claims_by_key.items():
        values = {_claim_value(claim) for claim in grouped if _claim_value(claim)}
        if len(values) < 2:
            continue
        refs = [
            link.evidence_ref
            for claim in grouped
            for link in links_by_claim.get(claim.claim_id, [])
            if link.evidence_ref
        ]
        conflicts.append(
            ConflictSet(
                claim_key=claim_key,
                claim_ids=[claim.claim_id for claim in grouped],
                evidence_refs=list(dict.fromkeys(refs)),
                explanation="同一 claim_key 存在多个不同值，需人工确认来源和适用时间。",
            )
        )
    return conflicts


def _claim_value(claim: Claim) -> str:
    if claim.value is not None:
        return str(claim.value).strip().lower()
    return claim.text.strip().lower()


def _audit_status(status: str) -> EvidenceClaimStatus:
    if status in {"supported", "unsupported", "needs_confirmation", "stale", "contradicted"}:
        return status  # type: ignore[return-value]
    return "needs_confirmation"


def _bounded_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _as_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []
