"""Small, deterministic Agent protocols for the Agentic RL loop.

These are deliberately policy/adapter objects rather than autonomous LLM
clients.  A future model or pi-agent runtime can implement the same methods;
the control plane keeps ownership of facts, evidence, and writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal

from agentic_rl import (
    ActionName,
    AgentTrajectory,
    RewardV2,
    TrajectoryAction,
    TrajectoryObservation,
)

PrivacyRoute = Literal[
    "private_local",
    "public_external_allowed",
    "anonymized_external_allowed",
]


@dataclass
class QueryPlan:
    queries: List[str]
    source_filters: List[str]
    needs_user_confirmation: bool = False
    reason: str = ""


class QueryPlannerAgent:
    name = "QueryPlannerAgent"
    model_role = "router_or_extractor"

    def plan(self, task: str, *, missing_evidence: Iterable[str] = ()) -> QueryPlan:
        gaps = [item for item in missing_evidence if item]
        queries = [task.strip()] if task.strip() else []
        queries.extend(f"{task} {gap}" for gap in gaps)
        return QueryPlan(
            queries=list(dict.fromkeys(queries)),
            source_filters=["policy", "advisor_source", "web_url"],
            needs_user_confirmation=not bool(queries),
            reason="补齐证据缺口" if gaps else "使用原始任务检索公开证据",
        )


class EvidenceAuditFixAgent:
    name = "EvidenceAuditFixAgent"
    model_role = "critic_or_auditor"

    def propose(
        self,
        issues: Iterable[str],
        *,
        available_evidence: Iterable[str] = (),
    ) -> List[Dict[str, Any]]:
        evidence = list(available_evidence)
        actions = []
        for issue in issues:
            if "过期" in issue or "缺少" in issue or "证据" in issue:
                actions.append({"action": "retrieve", "reason": issue, "evidence_refs": evidence})
            elif "rejected" in issue:
                actions.append({"action": "ask_user", "reason": issue})
            else:
                actions.append({"action": "downgrade_claim", "reason": issue})
        return actions


class RewardJudgeAgent:
    name = "RewardJudgeAgent"
    model_role = "judge"

    def score(self, trajectory: AgentTrajectory):
        return RewardV2().score(trajectory)


class TrajectoryBuilderAgent:
    name = "TrajectoryBuilderAgent"
    model_role = "rule_local"

    def build(
        self,
        *,
        task_type: str,
        input_summary: str = "",
        prompt: str = "",
        output: str,
        evidence_refs: Iterable[str] = (),
        audit_status: str = "unknown",
        privacy_route: PrivacyRoute = "private_local",
        actions: Iterable[ActionName] = (),
        run_id: str = "",
        target_id: str = "",
        candidate_group_id: str = "",
    ) -> AgentTrajectory:
        trajectory = AgentTrajectory(
            task_type=task_type,
            input_summary=input_summary,
            prompt=prompt,
            output=output,
            evidence_refs=list(evidence_refs),
            audit_status=audit_status,
            privacy_route=privacy_route,
            run_id=run_id,
            target_id=target_id,
            candidate_group_id=candidate_group_id,
            actions=[TrajectoryAction(name=action) for action in actions],
        )
        trajectory.observations.append(
            TrajectoryObservation(
                kind="audit", value={"status": audit_status}, refs=list(evidence_refs)
            )
        )
        return trajectory


class SafetyGateAgent:
    name = "SafetyGateAgent"
    model_role = "auditor"

    def check(self, trajectory: AgentTrajectory) -> Dict[str, Any]:
        blocked: List[str] = []
        if trajectory.user_feedback.get("rejected_fact_used"):
            blocked.append("rejected_fact_used")
        if trajectory.user_feedback.get("privacy_violation"):
            blocked.append("privacy_violation")
        if trajectory.user_feedback.get("auto_send_requested"):
            blocked.append("auto_send_forbidden")
        return {
            "allowed": not blocked,
            "blocked_reasons": blocked,
            "requires_confirmation": bool(blocked),
        }


__all__ = [
    "EvidenceAuditFixAgent",
    "QueryPlan",
    "QueryPlannerAgent",
    "RewardJudgeAgent",
    "SafetyGateAgent",
    "TrajectoryBuilderAgent",
]
