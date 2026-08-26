"""Offline evaluation for Agentic RL trajectories and train-ready datasets."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Literal

from agentic_rl import AgentTrajectory, RewardV2, RewardV2Breakdown
from models import now_iso
from pydantic import BaseModel, Field


class StrategySummary(BaseModel):
    strategy: str
    sample_count: int = 0
    avg_reward: float = 0.0
    min_reward: float = 0.0
    max_reward: float = 0.0
    hard_failure_count: int = 0
    hard_failures: Dict[str, int] = Field(default_factory=dict)
    audit_status_counts: Dict[str, int] = Field(default_factory=dict)
    privacy_route_counts: Dict[str, int] = Field(default_factory=dict)
    task_type_counts: Dict[str, int] = Field(default_factory=dict)
    action_counts: Dict[str, int] = Field(default_factory=dict)
    term_averages: Dict[str, float] = Field(default_factory=dict)


class StrategyComparison(BaseModel):
    baseline_strategy: str
    candidate_strategy: str
    baseline_avg_reward: float = 0.0
    candidate_avg_reward: float = 0.0
    delta: float = 0.0
    recommendation: Literal["promote_candidate", "hold_candidate", "insufficient_data"]


class PreferenceEvaluation(BaseModel):
    pair_count: int = 0
    chosen_better_count: int = 0
    avg_reward_margin: float = 0.0


class AgenticEvaluationReport(BaseModel):
    schema_version: str = "agentic-rl-evaluation.v1"
    dataset_dir: str
    created_at: str = Field(default_factory=now_iso)
    judge_provider: Literal["disabled", "mock"] = "disabled"
    trajectory_count: int = 0
    strategy_summaries: List[StrategySummary] = Field(default_factory=list)
    comparisons: List[StrategyComparison] = Field(default_factory=list)
    preference_evaluation: PreferenceEvaluation = Field(default_factory=PreferenceEvaluation)
    global_failure_modes: Dict[str, int] = Field(default_factory=dict)
    recommendation: str = "hold"
    notes: List[str] = Field(default_factory=list)


def evaluate_agentic_dataset(
    dataset_dir: Path,
    *,
    task_type: str = "",
    strategy: str = "",
    judge_provider: Literal["disabled", "mock"] = "disabled",
    min_samples_for_promotion: int = 20,
    min_reward_for_promotion: float = 0.6,
) -> AgenticEvaluationReport:
    trajectories = load_trajectories(dataset_dir / "trajectories.jsonl")
    if task_type:
        trajectories = [item for item in trajectories if item.task_type == task_type]
    if strategy:
        trajectories = [item for item in trajectories if strategy_id(item) == strategy]
    reward = RewardV2()
    rewards = [
        reward.score(item, judge_score=mock_judge_score(item) if judge_provider == "mock" else None)
        for item in trajectories
    ]
    summaries = [
        summarize_strategy(name, group, rewards)
        for name, group in group_by_strategy(trajectories).items()
    ]
    comparisons = compare_strategies(summaries, min_samples_for_promotion, min_reward_for_promotion)
    preference_eval = evaluate_preference_pairs(dataset_dir / "preference_pairs.jsonl")
    failures = Counter()
    for breakdown in rewards:
        failures.update(breakdown.hard_failures)
    notes = []
    if not trajectories:
        notes.append("No trajectories matched the selected filters.")
    if judge_provider == "mock":
        notes.append("Mock judge is deterministic and intended only for local smoke tests.")
    return AgenticEvaluationReport(
        dataset_dir=str(dataset_dir),
        judge_provider=judge_provider,
        trajectory_count=len(trajectories),
        strategy_summaries=summaries,
        comparisons=comparisons,
        preference_evaluation=preference_eval,
        global_failure_modes=dict(sorted(failures.items())),
        recommendation=overall_recommendation(summaries, comparisons),
        notes=notes,
    )


def load_trajectories(path: Path) -> List[AgentTrajectory]:
    if not path.exists():
        raise FileNotFoundError(f"Missing trajectories file: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [AgentTrajectory(**row) for row in rows]


def group_by_strategy(trajectories: Iterable[AgentTrajectory]) -> Dict[str, List[AgentTrajectory]]:
    groups: Dict[str, List[AgentTrajectory]] = defaultdict(list)
    for trajectory in trajectories:
        groups[strategy_id(trajectory)].append(trajectory)
    return dict(groups)


def strategy_id(trajectory: AgentTrajectory) -> str:
    parts = [
        trajectory.policy_version or "baseline",
        trajectory.prompt_version or "prompt-default",
        trajectory.skill_version or "skill-default",
        trajectory.template_version or "template-default",
    ]
    return "/".join(parts)


def summarize_strategy(
    strategy: str,
    trajectories: List[AgentTrajectory],
    rewards: List[RewardV2Breakdown],
) -> StrategySummary:
    reward_by_id = {item.trajectory_id: item for item in rewards}
    selected_rewards = [
        reward_by_id[item.trajectory_id]
        for item in trajectories
        if item.trajectory_id in reward_by_id
    ]
    reward_values = [item.total for item in selected_rewards]
    hard_failures = Counter()
    term_totals: Dict[str, float] = defaultdict(float)
    for item in selected_rewards:
        hard_failures.update(item.hard_failures)
        for term, value in item.terms.items():
            term_totals[term] += value
    action_counts = Counter(
        action.name for trajectory in trajectories for action in trajectory.actions
    )
    return StrategySummary(
        strategy=strategy,
        sample_count=len(trajectories),
        avg_reward=_avg(reward_values),
        min_reward=min(reward_values) if reward_values else 0.0,
        max_reward=max(reward_values) if reward_values else 0.0,
        hard_failure_count=sum(hard_failures.values()),
        hard_failures=dict(sorted(hard_failures.items())),
        audit_status_counts=dict(
            sorted(Counter(item.audit_status for item in trajectories).items())
        ),
        privacy_route_counts=dict(
            sorted(Counter(item.privacy_route for item in trajectories).items())
        ),
        task_type_counts=dict(sorted(Counter(item.task_type for item in trajectories).items())),
        action_counts=dict(sorted(action_counts.items())),
        term_averages={
            term: round(total / len(selected_rewards), 4)
            for term, total in sorted(term_totals.items())
            if selected_rewards
        },
    )


def compare_strategies(
    summaries: List[StrategySummary],
    min_samples_for_promotion: int,
    min_reward_for_promotion: float,
) -> List[StrategyComparison]:
    by_name = {summary.strategy: summary for summary in summaries}
    baseline = next(
        (summary for summary in summaries if summary.strategy.startswith("baseline/")),
        None,
    )
    comparisons: List[StrategyComparison] = []
    if not baseline:
        return comparisons
    for candidate in summaries:
        if candidate.strategy == baseline.strategy:
            continue
        recommendation: Literal["promote_candidate", "hold_candidate", "insufficient_data"] = (
            "hold_candidate"
        )
        if candidate.sample_count < min_samples_for_promotion:
            recommendation = "insufficient_data"
        elif (
            candidate.avg_reward >= min_reward_for_promotion
            and candidate.avg_reward > baseline.avg_reward
            and candidate.hard_failure_count == 0
        ):
            recommendation = "promote_candidate"
        comparisons.append(
            StrategyComparison(
                baseline_strategy=baseline.strategy,
                candidate_strategy=candidate.strategy,
                baseline_avg_reward=baseline.avg_reward,
                candidate_avg_reward=by_name[candidate.strategy].avg_reward,
                delta=round(candidate.avg_reward - baseline.avg_reward, 4),
                recommendation=recommendation,
            )
        )
    return comparisons


def evaluate_preference_pairs(path: Path) -> PreferenceEvaluation:
    if not path.exists():
        return PreferenceEvaluation()
    margins: List[float] = []
    chosen_better = 0
    pair_count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        chosen = row.get("chosen_reward")
        rejected = row.get("rejected_reward")
        if isinstance(chosen, (int, float)) and isinstance(rejected, (int, float)):
            pair_count += 1
            margin = float(chosen) - float(rejected)
            margins.append(margin)
            if margin > 0:
                chosen_better += 1
    return PreferenceEvaluation(
        pair_count=pair_count,
        chosen_better_count=chosen_better,
        avg_reward_margin=_avg(margins),
    )


def mock_judge_score(trajectory: AgentTrajectory) -> float:
    if trajectory.user_feedback.get("privacy_violation") or trajectory.user_feedback.get(
        "rejected_fact_used"
    ):
        return 0.0
    if trajectory.evidence_refs and trajectory.audit_status in {"passed", "audited"}:
        return 0.8
    if trajectory.evidence_refs:
        return 0.55
    return 0.25


def overall_recommendation(
    summaries: List[StrategySummary],
    comparisons: List[StrategyComparison],
) -> str:
    if any(item.recommendation == "promote_candidate" for item in comparisons):
        return "promote_candidate"
    if not summaries:
        return "no_data"
    if any(summary.hard_failure_count for summary in summaries):
        return "hold_due_to_hard_failures"
    return "hold"


def write_evaluation_report(report: AgenticEvaluationReport, output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "agentic_rl_evaluation.json"
    md_path = output_dir / "agentic_rl_evaluation.md"
    json_path.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_evaluation_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_evaluation_markdown(report: AgenticEvaluationReport) -> str:
    lines = [
        "# Agentic RL Offline Evaluation",
        "",
        f"- dataset: `{report.dataset_dir}`",
        f"- trajectories: `{report.trajectory_count}`",
        f"- judge_provider: `{report.judge_provider}`",
        f"- recommendation: `{report.recommendation}`",
        "",
        "## Strategy Summaries",
        "",
    ]
    for summary in report.strategy_summaries:
        lines.extend(
            [
                f"### {summary.strategy}",
                "",
                f"- samples: `{summary.sample_count}`",
                f"- avg_reward: `{summary.avg_reward}`",
                f"- min/max reward: `{summary.min_reward}` / `{summary.max_reward}`",
                f"- hard_failures: `{summary.hard_failures}`",
                f"- audit_status: `{summary.audit_status_counts}`",
                f"- actions: `{summary.action_counts}`",
                "",
            ]
        )
    lines.extend(["## Comparisons", ""])
    if not report.comparisons:
        lines.append("- none")
    for comparison in report.comparisons:
        lines.append(
            "- "
            f"{comparison.candidate_strategy}: delta={comparison.delta}, "
            f"recommendation={comparison.recommendation}"
        )
    lines.extend(
        [
            "",
            "## Preference Pairs",
            "",
            f"- pairs: `{report.preference_evaluation.pair_count}`",
            f"- chosen_better: `{report.preference_evaluation.chosen_better_count}`",
            f"- avg_margin: `{report.preference_evaluation.avg_reward_margin}`",
            "",
            "## Notes",
            "",
        ]
    )
    if not report.notes:
        lines.append("- none")
    else:
        lines.extend(f"- {note}" for note in report.notes)
    return "\n".join(lines) + "\n"


def _avg(values: List[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
