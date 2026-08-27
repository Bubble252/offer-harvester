from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from models import new_id, now_iso
from pydantic import BaseModel, Field


class RLDataSample(BaseModel):
    sample_id: str = Field(default_factory=lambda: new_id("rlsample"))
    task_type: str
    student_summary: str = ""
    prompt: str = ""
    model_output: str = ""
    user_edit: str = ""
    reviewer_feedback: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    evidence_status: str = "unknown"
    quality_score: float = 0.0
    accepted: bool = False
    anonymized: bool = False
    source_run_id: str = ""
    source_version_id: str = ""
    created_at: str = Field(default_factory=now_iso)


class RewardBreakdown(BaseModel):
    sample_id: str
    total: float = 0.0
    terms: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    judge_score: Optional[float] = None
    online_training_allowed: bool = False


class RewardFunction(Protocol):
    name: str

    def score(self, sample: RLDataSample) -> RewardBreakdown: ...


class RuleBasedReward:
    name = "rule-based-v1"

    def score(self, sample: RLDataSample) -> RewardBreakdown:
        terms = {
            "evidence_coverage": 0.25 if sample.evidence_refs else -0.3,
            "quality": max(-0.2, min(0.3, (sample.quality_score - 70) / 100)),
            "acceptance": 0.25 if sample.accepted else 0.0,
            "factuality_gate": 0.2 if sample.evidence_status in {"confirmed", "audited"} else -0.2,
            "template_penalty": -0.1 if _looks_generic(sample.model_output) else 0.0,
        }
        reasons = []
        if not sample.evidence_refs:
            reasons.append("缺少 evidence 引用")
        if sample.evidence_status not in {"confirmed", "audited"}:
            reasons.append("证据状态未达到确认或审计通过")
        if _looks_generic(sample.model_output):
            reasons.append("输出可能过于模板化")
        return RewardBreakdown(
            sample_id=sample.sample_id,
            total=round(sum(terms.values()), 4),
            terms=terms,
            reasons=reasons,
            evidence_refs=list(sample.evidence_refs),
        )


class JudgeClient(Protocol):
    name: str

    def judge(self, sample: RLDataSample) -> Optional[float]: ...


class DisabledJudgeClient:
    name = "disabled"

    def judge(self, sample: RLDataSample) -> Optional[float]:
        return None


class CallableJudgeClient:
    def __init__(self, judge_fn: Callable[[RLDataSample], float], name: str = "injected-judge"):
        self.judge_fn = judge_fn
        self.name = name

    def judge(self, sample: RLDataSample) -> Optional[float]:
        score = float(self.judge_fn(sample))
        return max(0.0, min(1.0, score))


class DatasetBuilder:
    """Stores only anonymized offline candidates, never a training trigger."""

    def __init__(self, workspace_or_path):
        root = (
            workspace_or_path.root
            if hasattr(workspace_or_path, "root")
            else Path(workspace_or_path)
        )
        self.path = Path(root) / "rl" / "dataset.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def build_sample(self, **kwargs: Any) -> RLDataSample:
        sample = RLDataSample(**kwargs)
        if not sample.anonymized:
            sample = sample.model_copy(
                update={
                    "student_summary": anonymize_text(sample.student_summary),
                    "prompt": anonymize_text(sample.prompt),
                    "model_output": anonymize_text(sample.model_output),
                    "user_edit": anonymize_text(sample.user_edit),
                    "anonymized": True,
                }
            )
        return sample

    def append(self, sample: RLDataSample) -> RLDataSample:
        if not sample.anonymized:
            raise ValueError("Only anonymized samples may be persisted")
        payload = sample.model_dump() if hasattr(sample, "model_dump") else sample.dict()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return sample

    def records(self) -> List[RLDataSample]:
        if not self.path.exists():
            return []
        return [
            RLDataSample(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


class ExperimentRecord(BaseModel):
    experiment_id: str = Field(default_factory=lambda: new_id("rlexp"))
    task_type: str
    baseline_version: str
    candidate_version: str
    baseline_score: float
    candidate_score: float
    delta: float = 0.0
    notes: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class ExperimentTracker:
    def __init__(self, workspace_or_path):
        root = (
            workspace_or_path.root
            if hasattr(workspace_or_path, "root")
            else Path(workspace_or_path)
        )
        self.path = Path(root) / "rl" / "experiments.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def compare(
        self,
        *,
        task_type: str,
        baseline_version: str,
        candidate_version: str,
        baseline_score: float,
        candidate_score: float,
        notes: Optional[List[str]] = None,
    ) -> ExperimentRecord:
        record = ExperimentRecord(
            task_type=task_type,
            baseline_version=baseline_version,
            candidate_version=candidate_version,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            delta=round(candidate_score - baseline_score, 4),
            notes=notes or [],
        )
        payload = record.model_dump() if hasattr(record, "model_dump") else record.dict()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def records(self) -> List[ExperimentRecord]:
        if not self.path.exists():
            return []
        return [
            ExperimentRecord(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


def evaluate_sample(
    sample: RLDataSample,
    *,
    reward: Optional[RewardFunction] = None,
    judge: Optional[JudgeClient] = None,
) -> RewardBreakdown:
    breakdown = (reward or RuleBasedReward()).score(sample)
    judge_score = (judge or DisabledJudgeClient()).judge(sample)
    if judge_score is not None:
        breakdown.judge_score = judge_score
        breakdown.terms["offline_judge"] = round((judge_score - 0.5) * 0.2, 4)
        breakdown.total = round(breakdown.total + breakdown.terms["offline_judge"], 4)
    return breakdown


def anonymize_text(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text or "")
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[PHONE]", text)
    text = re.sub(r"\b(?:姓名|学生|同学)[:：]\s*[^\s，。；;]+", "学生：[ANON]", text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{text} [sample:{digest}]" if text else f"[sample:{digest}]"


def _looks_generic(text: str) -> bool:
    generic_tokens = ("老师您好", "希望有机会", "感谢您阅读", "此致敬礼")
    return len(text.strip()) < 80 or sum(token in text for token in generic_tokens) >= 2


@dataclass
class OfflineRLBoundary:
    """Marker object documenting that this package never starts model training."""

    training_enabled: bool = False
    allowed_inputs: tuple[str, ...] = ("anonymized_dataset", "offline_config")
