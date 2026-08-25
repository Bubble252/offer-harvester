from __future__ import annotations

import difflib
from typing import Any, Dict, List, Literal, Optional

from agents.evidence_audit_agent import EvidenceAuditResult
from memory import FeedbackRecord, LocalMemoryManager
from models import GeneratedMaterial, MaterialQualityReport, MaterialVersion, new_id, now_iso
from pydantic import BaseModel, Field
from rag import EvidenceBundle

CandidateKind = Literal["skill", "rule", "prompt"]
CandidateStatus = Literal["candidate", "approved", "rejected", "active"]


class ProceduralCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("pcand"))
    candidate_kind: CandidateKind
    title: str
    source_feedback_ids: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    proposed_change: str = ""
    risk: Literal["low", "medium", "high"] = "medium"
    metrics: Dict[str, Any] = Field(default_factory=dict)
    status: CandidateStatus = "candidate"
    requires_approval: bool = True
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class FeedbackLoopResult(BaseModel):
    feedback_memory_ids: List[str] = Field(default_factory=list)
    procedural_candidate_ids: List[str] = Field(default_factory=list)
    evidence_bundle_id: str = ""
    audit_passed: bool = False
    notes: List[str] = Field(default_factory=list)


def record_evidence_audit_feedback(
    workspace,
    audit: EvidenceAuditResult,
    *,
    bundle: Optional[EvidenceBundle] = None,
    material: Optional[GeneratedMaterial] = None,
    quality: Optional[MaterialQualityReport] = None,
    subject_ref: str = "",
    run_id: str = "",
) -> FeedbackLoopResult:
    manager = LocalMemoryManager(workspace)
    feedback_ids: List[str] = []
    candidate_ids: List[str] = []
    evidence_refs = _bundle_refs(bundle)
    subject = (
        subject_ref
        or (material.material_id if material else "")
        or (bundle.bundle_id if bundle else run_id)
    )

    for message in audit.unsupported_claims:
        feedback = FeedbackRecord(
            feedback_type="evidence_audit",
            subject_ref=subject,
            issue_category=_issue_category(message),
            accepted=False,
            evidence_refs=evidence_refs,
            suggested_candidate_type="rule",
        )
        record = manager.write_feedback(feedback, scope=_scope_for_subject(subject))
        feedback_ids.append(record.memory_id)
        candidate_ids.append(
            _save_candidate(
                workspace,
                ProceduralCandidate(
                    candidate_kind="rule",
                    title="Require stronger evidence before generation output is accepted",
                    source_feedback_ids=[feedback.feedback_id, record.memory_id],
                    evidence_refs=evidence_refs,
                    proposed_change=f"Add or tighten a guard for audit issue: {message}",
                    risk="medium",
                    metrics={
                        "audit_passed": audit.passed,
                        "unsupported_count": len(audit.unsupported_claims),
                    },
                ),
            ).candidate_id
        )

    for message in audit.needs_confirmation:
        feedback = FeedbackRecord(
            feedback_type="evidence_audit",
            subject_ref=subject,
            issue_category="needs_confirmation",
            accepted=None,
            evidence_refs=evidence_refs,
            suggested_candidate_type="prompt",
        )
        record = manager.write_feedback(feedback, scope=_scope_for_subject(subject))
        feedback_ids.append(record.memory_id)
        candidate_ids.append(
            _save_candidate(
                workspace,
                ProceduralCandidate(
                    candidate_kind="prompt",
                    title="Surface unconfirmed facts before finalizing",
                    source_feedback_ids=[feedback.feedback_id, record.memory_id],
                    evidence_refs=evidence_refs,
                    proposed_change=f"Prompt reviewer to ask for confirmation: {message}",
                    risk="low",
                    metrics={"needs_confirmation_count": len(audit.needs_confirmation)},
                ),
            ).candidate_id
        )

    if bundle and bundle.conflicts:
        feedback = FeedbackRecord(
            feedback_type="rag_conflict",
            subject_ref=bundle.bundle_id,
            issue_category="evidence_conflict",
            accepted=None,
            evidence_refs=list(
                dict.fromkeys(
                    ref for conflict in bundle.conflicts for ref in conflict.evidence_refs
                )
            ),
            suggested_candidate_type="rule",
        )
        record = manager.write_feedback(feedback, scope="workspace")
        feedback_ids.append(record.memory_id)
        candidate_ids.append(
            _save_candidate(
                workspace,
                ProceduralCandidate(
                    candidate_kind="rule",
                    title="Resolve conflicting evidence before using retrieved claims",
                    source_feedback_ids=[feedback.feedback_id, record.memory_id],
                    evidence_refs=feedback.evidence_refs,
                    proposed_change="Require manual review when an EvidenceBundle has open conflicts.",
                    risk="high",
                    metrics={"conflict_count": len(bundle.conflicts)},
                ),
            ).candidate_id
        )

    if quality and not quality.passed:
        failed_checks = [
            str(check.get("code") or check.get("name") or check) for check in quality.checks
        ]
        feedback = FeedbackRecord(
            feedback_type="material_quality",
            subject_ref=quality.material_id,
            issue_category="quality_failed",
            accepted=False,
            evidence_refs=evidence_refs,
            suggested_candidate_type="skill",
        )
        record = manager.write_feedback(feedback, scope=_scope_for_subject(quality.material_id))
        feedback_ids.append(record.memory_id)
        candidate_ids.append(
            _save_candidate(
                workspace,
                ProceduralCandidate(
                    candidate_kind="skill",
                    title="Improve material reviewer checks",
                    source_feedback_ids=[feedback.feedback_id, record.memory_id],
                    evidence_refs=evidence_refs,
                    proposed_change=f"Add regression fixtures for failed quality checks: {', '.join(failed_checks[:6])}",
                    risk="medium",
                    metrics={
                        "risk_level": quality.risk_level,
                        "failed_check_count": len(failed_checks),
                    },
                ),
            ).candidate_id
        )

    return FeedbackLoopResult(
        feedback_memory_ids=list(dict.fromkeys(feedback_ids)),
        procedural_candidate_ids=list(dict.fromkeys(candidate_ids)),
        evidence_bundle_id=bundle.bundle_id if bundle else "",
        audit_passed=audit.passed,
        notes=["No feedback was created because the audit passed without warnings."]
        if not feedback_ids
        else [],
    )


def record_material_edit_feedback(
    workspace,
    before: MaterialVersion,
    after: MaterialVersion,
    *,
    accepted: bool,
    evidence_refs: Optional[List[str]] = None,
) -> FeedbackLoopResult:
    manager = LocalMemoryManager(workspace)
    diff_text = _diff(before.content, after.content)
    issue_category = "user_edit_accepted" if accepted else "user_edit_rejected"
    feedback = FeedbackRecord(
        feedback_type="material_edit",
        subject_ref=after.material_id,
        before_ref=before.version_id,
        after_ref=after.version_id,
        issue_category=issue_category,
        accepted=accepted,
        evidence_refs=evidence_refs or [],
        suggested_candidate_type="prompt" if accepted else "rule",
    )
    record = manager.write_feedback(feedback, scope=_scope_for_subject(after.material_id))
    candidate = _save_candidate(
        workspace,
        ProceduralCandidate(
            candidate_kind="prompt" if accepted else "rule",
            title="Learn from accepted material edit"
            if accepted
            else "Avoid rejected material edit pattern",
            source_feedback_ids=[feedback.feedback_id, record.memory_id],
            evidence_refs=evidence_refs or [],
            proposed_change=_summarize_diff(diff_text),
            risk="low" if accepted else "medium",
            metrics={
                "diff_lines": len(
                    [line for line in diff_text.splitlines() if line.startswith(("+", "-"))]
                )
            },
        ),
    )
    return FeedbackLoopResult(
        feedback_memory_ids=[record.memory_id],
        procedural_candidate_ids=[candidate.candidate_id],
        notes=[],
    )


def _save_candidate(workspace, candidate: ProceduralCandidate) -> ProceduralCandidate:
    payload = candidate.model_dump() if hasattr(candidate, "model_dump") else candidate.dict()
    workspace.write("procedural_candidates", payload, "candidate_id")
    return candidate


def _bundle_refs(bundle: Optional[EvidenceBundle]) -> List[str]:
    if not bundle:
        return []
    refs = list(bundle.retrieval_refs)
    refs.extend(ref for claim in bundle.claims for ref in claim.source_refs)
    return list(dict.fromkeys(ref for ref in refs if ref))


def _issue_category(message: str) -> str:
    if "过期" in message or "stale" in message.lower():
        return "stale_policy"
    if "缺少" in message or "没有" in message:
        return "missing_evidence"
    if "已否认" in message or "rejected" in message.lower():
        return "rejected_fact_leakage"
    return "unsupported_claim"


def _scope_for_subject(subject_ref: str) -> str:
    return f"workflow:{subject_ref}" if subject_ref else "workspace"


def _diff(before: str, after: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )


def _summarize_diff(diff_text: str) -> str:
    changed = [
        line
        for line in diff_text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    if not changed:
        return "No textual change detected; keep candidate inactive until reviewed."
    return "Review this user edit pattern before changing prompts or rules:\n" + "\n".join(
        changed[:12]
    )
