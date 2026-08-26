"""Train-ready Agentic RL records, rewards, and dataset export.

This module records decisions and evaluations without starting training.  The
exporter produces portable JSONL that an optional SFT/DPO/GRPO experiment can
consume later, while the application remains free of torch/TRL dependencies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from models import new_id, now_iso
from pydantic import BaseModel, Field
from rl_foundation import RLDataSample

ActionName = Literal[
    "retrieve",
    "rerank",
    "draft",
    "review",
    "audit",
    "ask_user",
    "update_candidate",
    "generate_ppt",
    "sync_status",
    "follow_up",
    "plan_query",
    "fix_audit",
    "judge_reward",
    "safety_check",
]


class TrajectoryAction(BaseModel):
    action_id: str = Field(default_factory=lambda: new_id("action"))
    name: ActionName
    input_refs: List[str] = Field(default_factory=list)
    output_refs: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class TrajectoryObservation(BaseModel):
    observation_id: str = Field(default_factory=lambda: new_id("obs"))
    kind: str
    refs: List[str] = Field(default_factory=list)
    value: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class AgentTrajectory(BaseModel):
    trajectory_id: str = Field(default_factory=lambda: new_id("trajectory"))
    task_type: str
    workspace_ref: str = ""
    run_id: str = ""
    target_id: str = ""
    input_summary: str = ""
    prompt: str = ""
    expected_output: str = ""
    candidate_group_id: str = ""
    policy_version: str = "baseline"
    prompt_version: str = ""
    skill_version: str = ""
    template_version: str = ""
    privacy_route: Literal[
        "private_local", "public_external_allowed", "anonymized_external_allowed"
    ] = "private_local"
    actions: List[TrajectoryAction] = Field(default_factory=list)
    observations: List[TrajectoryObservation] = Field(default_factory=list)
    output: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    audit_status: str = "unknown"
    user_feedback: Dict[str, Any] = Field(default_factory=dict)
    final_outcome: Dict[str, Any] = Field(default_factory=dict)
    source_records: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class RewardV2Breakdown(BaseModel):
    trajectory_id: str
    total: float = 0.0
    terms: Dict[str, float] = Field(default_factory=dict)
    hard_failures: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    judge_score: Optional[float] = None
    judge_unavailable: bool = True


class RewardV2:
    """Explainable reward with safety terms treated as hard gates."""

    name = "reward-v2"

    def score(
        self,
        trajectory: AgentTrajectory,
        *,
        judge_score: Optional[float] = None,
    ) -> RewardV2Breakdown:
        feedback = trajectory.user_feedback
        audit = trajectory.audit_status
        terms = {
            "evidence_coverage": 0.2 if trajectory.evidence_refs else -0.35,
            "audit_pass": 0.25 if audit in {"passed", "audited"} else -0.2,
            "user_acceptance": 0.2 if feedback.get("accepted") is True else 0.0,
            "specificity": 0.1 if len(trajectory.output.strip()) >= 80 else -0.05,
            "action_appropriateness": self._action_score(trajectory),
            "privacy_safety": 0.15
            if trajectory.privacy_route != "private_local" or feedback.get("private_safe", True)
            else -0.4,
        }
        if "citation_correct" in feedback:
            terms["citation_correctness"] = 0.12 if feedback["citation_correct"] else -0.2
        if "factuality_confirmed" in feedback:
            terms["factuality"] = 0.1 if feedback["factuality_confirmed"] else -0.2
        if feedback.get("evidence_conflict_open"):
            terms["evidence_conflict_penalty"] = -0.15
        authority_score = feedback.get("authority_score")
        if isinstance(authority_score, (int, float)):
            bounded_authority = max(0.0, min(1.0, float(authority_score)))
            terms["source_authority"] = round((bounded_authority - 0.5) * 0.1, 4)
        hard_failures: List[str] = []
        reasons: List[str] = []
        if feedback.get("rejected_fact_used"):
            hard_failures.append("rejected_fact_used")
            reasons.append("输出使用了 rejected profile fact")
        if feedback.get("expired_policy_used"):
            hard_failures.append("expired_policy_used")
            reasons.append("输出使用了过期政策")
        if feedback.get("privacy_violation"):
            hard_failures.append("privacy_violation")
            reasons.append("存在隐私路由违规")
        if feedback.get("citation_correct") is False:
            hard_failures.append("citation_incorrect")
            reasons.append("引用未指向支持该结论的证据")
        if feedback.get("factuality_confirmed") is False:
            hard_failures.append("factuality_failed")
            reasons.append("输出存在已确认的事实错误")
        if not trajectory.evidence_refs:
            reasons.append("缺少 EvidenceBundle 引用")
        if audit not in {"passed", "audited"}:
            reasons.append("EvidenceAudit 尚未通过")
        total = sum(terms.values())
        if hard_failures:
            total = -1.0
        if judge_score is not None:
            bounded = max(0.0, min(1.0, float(judge_score)))
            terms["offline_judge"] = round((bounded - 0.5) * 0.2, 4)
            total += terms["offline_judge"]
        return RewardV2Breakdown(
            trajectory_id=trajectory.trajectory_id,
            total=round(max(-1.0, min(1.0, total)), 4),
            terms={key: round(value, 4) for key, value in terms.items()},
            hard_failures=hard_failures,
            reasons=reasons,
            evidence_refs=list(trajectory.evidence_refs),
            judge_score=judge_score,
            judge_unavailable=judge_score is None,
        )

    @staticmethod
    def _action_score(trajectory: AgentTrajectory) -> float:
        names = {action.name for action in trajectory.actions}
        if trajectory.audit_status not in {"passed", "audited"} and "audit" not in names:
            return -0.2
        if not trajectory.evidence_refs and "retrieve" not in names:
            return -0.15
        if trajectory.user_feedback.get("needs_user_confirmation") and "ask_user" not in names:
            return -0.15
        return 0.1


class TrainReadyDatasetExporter:
    """Export anonymized, portable records for later SFT/DPO/GRPO runs."""

    def __init__(self, output_dir: Any):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        trajectories: Iterable[AgentTrajectory],
        rewards: Optional[Iterable[RewardV2Breakdown]] = None,
    ) -> Dict[str, int]:
        items = list(trajectories)
        reward_by_id = {item.trajectory_id: item for item in (rewards or [])}
        counts = {"trajectories": 0, "sft_messages": 0, "preference_pairs": 0, "grpo_rollouts": 0}
        self._write_jsonl("trajectories.jsonl", [self._trajectory_row(item) for item in items])
        sft_rows = [
            self._sft_row(item, reward_by_id.get(item.trajectory_id))
            for item in items
            if item.output and self._is_sft_eligible(item, reward_by_id.get(item.trajectory_id))
        ]
        self._write_jsonl("sft_messages.jsonl", sft_rows)
        grouped = self._group_by_prompt(items)
        preference_rows = []
        grpo_rows = []
        for _, group in grouped.items():
            if len(group) >= 2:
                ordered = sorted(
                    group,
                    key=lambda item: (
                        reward_by_id.get(
                            item.trajectory_id,
                            RewardV2Breakdown(trajectory_id=item.trajectory_id),
                        ).total
                    ),
                    reverse=True,
                )
                chosen = next(
                    (item for item in ordered if item.user_feedback.get("accepted") is True),
                    ordered[0],
                )
                hard_negatives = [
                    item
                    for item in ordered
                    if item.user_feedback.get("preference_negative") is True
                ]
                rejected = hard_negatives[0] if hard_negatives else ordered[-1]
                preference_rows.append(self._preference_row(chosen, rejected, reward_by_id))
            grpo_rows.append(
                {
                    "id": _group_id_for(group[0]),
                    "prompt": _safe_text(_prompt_for(group[0])),
                    "task_type": group[0].task_type,
                    "candidate_group_id": group[0].candidate_group_id,
                    "source_records": list(
                        dict.fromkeys(
                            source_record for item in group for source_record in item.source_records
                        )
                    ),
                    "rollouts": [
                        self._rollout_row(item, reward_by_id.get(item.trajectory_id))
                        for item in group
                    ],
                }
            )
        self._write_jsonl("preference_pairs.jsonl", preference_rows)
        self._write_jsonl("grpo_rollouts.jsonl", grpo_rows)
        counts.update(
            {
                "trajectories": len(items),
                "sft_messages": len(sft_rows),
                "preference_pairs": len(preference_rows),
                "grpo_rollouts": len(grpo_rows),
            }
        )
        manifest = {
            "schema_version": "agentic-rl-export.v1",
            "anonymized": True,
            "allowed_training_use": True,
            "privacy_scope": "anonymized_or_public_only",
            "source_scope": sorted({item.privacy_route for item in items}),
            "provenance_fields": ["candidate_group_id", "source_records"],
            "files": counts,
            "created_at": now_iso(),
        }
        (self.output_dir / "dataset_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return counts

    def _trajectory_row(self, trajectory: AgentTrajectory) -> Dict[str, Any]:
        return _dump_model(trajectory)

    def _sft_row(
        self,
        trajectory: AgentTrajectory,
        reward: Optional[RewardV2Breakdown],
    ) -> Dict[str, Any]:
        return {
            "id": trajectory.trajectory_id,
            "task_type": trajectory.task_type,
            "candidate_group_id": trajectory.candidate_group_id,
            "source_records": list(trajectory.source_records),
            "messages": [
                {"role": "user", "content": _safe_text(_prompt_for(trajectory))},
                {"role": "assistant", "content": _safe_text(trajectory.output)},
            ],
            "evidence_refs": trajectory.evidence_refs,
            "reward": reward.total if reward else None,
        }

    def _preference_row(
        self,
        chosen: AgentTrajectory,
        rejected: AgentTrajectory,
        rewards: Dict[str, RewardV2Breakdown],
    ) -> Dict[str, Any]:
        return {
            "id": new_id("preference"),
            "task_type": chosen.task_type,
            "candidate_group_id": chosen.candidate_group_id,
            "source_records": list(
                dict.fromkeys([*chosen.source_records, *rejected.source_records])
            ),
            "prompt": _safe_text(_prompt_for(chosen)),
            "chosen": _safe_text(chosen.output),
            "rejected": _safe_text(rejected.output),
            "chosen_reward": rewards.get(chosen.trajectory_id).total
            if rewards.get(chosen.trajectory_id)
            else None,
            "rejected_reward": rewards.get(rejected.trajectory_id).total
            if rewards.get(rejected.trajectory_id)
            else None,
        }

    def _rollout_row(
        self,
        trajectory: AgentTrajectory,
        reward: Optional[RewardV2Breakdown],
    ) -> Dict[str, Any]:
        return {
            "trajectory_id": trajectory.trajectory_id,
            "source_records": list(trajectory.source_records),
            "output": _safe_text(trajectory.output),
            "actions": [action.name for action in trajectory.actions],
            "evidence_refs": trajectory.evidence_refs,
            "reward": _dump_model(reward) if reward else None,
        }

    @staticmethod
    def _is_sft_eligible(
        trajectory: AgentTrajectory,
        reward: Optional[RewardV2Breakdown],
    ) -> bool:
        # SFT needs one unambiguous target behavior. Review-only, partial, and
        # unsafe trajectories remain useful as DPO/GRPO negatives, but they
        # must not dilute the accepted execution path.
        del reward
        return trajectory.user_feedback.get("accepted") is True

    @staticmethod
    def _group_by_prompt(trajectories: List[AgentTrajectory]) -> Dict[str, List[AgentTrajectory]]:
        grouped: Dict[str, List[AgentTrajectory]] = {}
        for item in trajectories:
            key = (
                item.candidate_group_id
                or f"{item.task_type}:{item.target_id}:{item.prompt_version}"
            )
            grouped.setdefault(key, []).append(item)
        return grouped

    def _write_jsonl(self, filename: str, rows: Iterable[Dict[str, Any]]) -> None:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def trajectory_to_rl_sample(trajectory: AgentTrajectory) -> RLDataSample:
    """Bridge new trajectory records to the existing RL foundation schema."""

    return RLDataSample(
        task_type=trajectory.task_type,
        student_summary="[ANON]" if trajectory.privacy_route != "private_local" else "",
        prompt=_safe_text(_prompt_for(trajectory)),
        model_output=_safe_text(trajectory.output),
        reviewer_feedback=[
            str(item.value.get("reason", ""))
            for item in trajectory.observations
            if item.kind == "feedback"
        ],
        evidence_refs=trajectory.evidence_refs,
        evidence_status=trajectory.audit_status,
        accepted=trajectory.user_feedback.get("accepted") is True,
        anonymized=True,
        source_run_id=trajectory.run_id,
    )


def _dump_model(model: Optional[BaseModel]) -> Optional[Dict[str, Any]]:
    if model is None:
        return None
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _group_id_for(trajectory: AgentTrajectory) -> str:
    return (
        trajectory.candidate_group_id
        or f"{trajectory.task_type}:{trajectory.target_id}:{trajectory.prompt_version}"
    )


def _safe_text(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text or "")
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[PHONE]", text)
    return text


def _prompt_for(trajectory: AgentTrajectory) -> str:
    return trajectory.prompt or trajectory.input_summary or trajectory.task_type
