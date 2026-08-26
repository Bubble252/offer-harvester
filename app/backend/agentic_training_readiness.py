"""Formal Agentic RL training readiness checks.

This is deliberately independent from model dependencies.  It answers whether
the dataset is safe and sufficiently structured for a first formal LoRA run,
not whether the current machine can download or train a model.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal

from agentic_training import (
    DatasetSplitConfig,
    load_grpo_rollouts,
    load_preference_pairs,
    load_sft_messages,
    scan_privacy,
    split_rows,
)
from pydantic import BaseModel, Field

FORMAL_TASK_TYPES = ("rag_query_plan", "evidence_audit_fix", "policy_advisor_qa")
REQUIRED_TRACE_KINDS = {
    "query_plan",
    "retrieval",
    "evidence_audit",
    "audit_fix",
    "reward_v2",
    "safety_gate",
}


class FormalTrainingReadinessIssue(BaseModel):
    level: Literal["error", "warning"]
    code: str
    message: str


class FormalTrainingReadinessReport(BaseModel):
    schema_version: str = "agentic-rl-formal-training-readiness.v1"
    dataset_dir: str
    ready: bool = False
    first_formal_train_scope: str = (
        "public-summary-only, deterministic harness rollouts; not a production quality claim"
    )
    collection_summary: Dict[str, Any] = Field(default_factory=dict)
    row_counts: Dict[str, int] = Field(default_factory=dict)
    train_task_counts: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    source_split_counts: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    source_split_source_counts: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    source_split_overlaps: Dict[str, List[str]] = Field(default_factory=dict)
    rollout_quality: Dict[str, Any] = Field(default_factory=dict)
    trace_quality: Dict[str, Any] = Field(default_factory=dict)
    privacy_scan_hits: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    issues: List[FormalTrainingReadinessIssue] = Field(default_factory=list)


def evaluate_formal_training_readiness(
    dataset_dir: Path,
    *,
    min_train_samples_per_task: int = 50,
    min_source_records: int = 15,
    min_rollouts_per_group: int = 3,
    min_valid_source_records: int = 1,
    min_test_source_records: int = 1,
    split_config: DatasetSplitConfig | None = None,
) -> FormalTrainingReadinessReport:
    """Check dataset governance before a non-smoke SFT/DPO/GRPO run."""

    dataset_dir = Path(dataset_dir)
    issues: List[FormalTrainingReadinessIssue] = []
    collection = _read_json(dataset_dir / "rollout_collection_report.json")
    manifest = _read_json(dataset_dir / "dataset_manifest.json")
    trajectories = _read_jsonl(dataset_dir / "trajectories.jsonl")
    try:
        sft_rows = load_sft_messages(dataset_dir)
        dpo_rows = load_preference_pairs(dataset_dir)
        grpo_rows = load_grpo_rollouts(dataset_dir)
    except FileNotFoundError as exc:
        issues.append(_issue("error", "missing_dataset_file", str(exc)))
        return _report(dataset_dir, collection, {}, {}, {}, {}, {}, [], {}, {}, issues)

    if collection.get("execution_mode") != "offline_real_agent_chain":
        issues.append(
            _issue(
                "error",
                "missing_executed_rollout_provenance",
                "Formal training requires a collector report from the executed public agent chain.",
            )
        )
    if collection.get("privacy_scope") != "public_only":
        issues.append(
            _issue(
                "error",
                "non_public_collection_scope",
                "The first formal training dataset must be public-only.",
            )
        )
    if collection.get("body_storage") != "summary_only_metadata":
        issues.append(
            _issue(
                "error",
                "unexpected_body_storage",
                "The rollout collector must not retain web-page bodies in the formal dataset.",
            )
        )
    if manifest.get("privacy_scope") != "anonymized_or_public_only":
        issues.append(
            _issue(
                "error",
                "invalid_dataset_manifest_privacy_scope",
                "Dataset manifest must declare anonymized_or_public_only privacy scope.",
            )
        )

    source_record_ids = {
        source for row in [*sft_rows, *dpo_rows, *grpo_rows] for source in _source_records(row)
    }
    if len(source_record_ids) < min_source_records:
        issues.append(
            _issue(
                "error",
                "too_few_public_sources",
                f"Need at least {min_source_records} distinct public source records; found {len(source_record_ids)}.",
            )
        )

    split_config = split_config or DatasetSplitConfig()
    datasets = {"sft": sft_rows, "dpo": dpo_rows, "grpo": grpo_rows}
    train_task_counts: Dict[str, Dict[str, int]] = {}
    split_counts: Dict[str, Dict[str, int]] = {}
    split_source_counts: Dict[str, Dict[str, int]] = {}
    overlaps: Dict[str, List[str]] = {}
    for name, rows in datasets.items():
        splits = split_rows(rows, split_config)
        split_counts[name] = {split: len(items) for split, items in splits.items()}
        split_source_counts[name] = {
            split: len({source for row in items for source in _source_records(row)})
            for split, items in splits.items()
        }
        train_counts = _task_counts(splits["train"])
        train_task_counts[name] = train_counts
        for task_type in FORMAL_TASK_TYPES:
            if train_counts.get(task_type, 0) < min_train_samples_per_task:
                issues.append(
                    _issue(
                        "error",
                        "insufficient_train_task_coverage",
                        f"{name} train split needs at least {min_train_samples_per_task} "
                        f"{task_type} rows; found {train_counts.get(task_type, 0)}.",
                    )
                )
        if split_source_counts[name].get("valid", 0) < min_valid_source_records:
            issues.append(
                _issue(
                    "error",
                    "insufficient_validation_source_coverage",
                    f"{name} valid split needs at least {min_valid_source_records} source records; "
                    f"found {split_source_counts[name].get('valid', 0)}.",
                )
            )
        if split_source_counts[name].get("test", 0) < min_test_source_records:
            issues.append(
                _issue(
                    "error",
                    "insufficient_test_source_coverage",
                    f"{name} test split needs at least {min_test_source_records} source records; "
                    f"found {split_source_counts[name].get('test', 0)}.",
                )
            )
        overlap = _source_split_overlap(splits)
        overlaps[name] = overlap
        if overlap:
            issues.append(
                _issue(
                    "error",
                    "source_split_leakage",
                    f"{name} has source records in multiple splits: {', '.join(overlap[:5])}.",
                )
            )
        if not all(_source_records(row) for row in rows):
            issues.append(
                _issue(
                    "error",
                    "missing_source_provenance",
                    f"{name} contains rows without source_records provenance.",
                )
            )

    rollout_quality = _rollout_quality(grpo_rows, min_rollouts_per_group)
    if rollout_quality["invalid_group_count"]:
        issues.append(
            _issue(
                "error",
                "invalid_rollout_group",
                f"{rollout_quality['invalid_group_count']} GRPO groups do not have "
                f"{min_rollouts_per_group}+ candidates with a reward spread.",
            )
        )
    trace_quality = _trace_quality(trajectories)
    if trace_quality["missing_required_trace_count"]:
        issues.append(
            _issue(
                "error",
                "missing_agent_trace",
                f"{trace_quality['missing_required_trace_count']} trajectories are missing "
                "query/retrieval/audit/fix/reward/safety observations.",
            )
        )

    privacy_hits = [
        *_privacy_hits(sft_rows, dataset_kind="sft"),
        *_privacy_hits(dpo_rows, dataset_kind="dpo"),
        *_privacy_hits(grpo_rows, dataset_kind="grpo"),
    ]
    if privacy_hits:
        issues.append(
            _issue(
                "error",
                "privacy_scan_hit",
                "Formal training data contains unmasked private-looking values.",
            )
        )

    limitations = [
        "Rollouts execute the local deterministic harness; they are not yet model-generated online rollouts.",
        "Public samples retain only source metadata and summaries. Original pages must be rechecked before facts enter product decisions.",
        "Passing this report permits a first controlled LoRA experiment, not automatic deployment of the adapter.",
    ]
    return _report(
        dataset_dir,
        collection,
        {
            "sft": len(sft_rows),
            "dpo": len(dpo_rows),
            "grpo": len(grpo_rows),
            "trajectories": len(trajectories),
        },
        train_task_counts,
        split_counts,
        split_source_counts,
        overlaps,
        privacy_hits,
        rollout_quality,
        trace_quality,
        issues,
        limitations=limitations,
    )


def write_formal_training_readiness(
    report: FormalTrainingReadinessReport,
    output_path: Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _rollout_quality(rows: Iterable[Dict[str, Any]], minimum: int) -> Dict[str, Any]:
    invalid = 0
    spreads: List[float] = []
    for row in rows:
        rollouts = row.get("rollouts", [])
        if not isinstance(rollouts, list) or len(rollouts) < minimum:
            invalid += 1
            continue
        values = [_reward_total(item) for item in rollouts if isinstance(item, dict)]
        if len(values) < minimum or max(values) <= min(values):
            invalid += 1
            continue
        spreads.append(max(values) - min(values))
    return {
        "group_count": len(list(rows)) if not isinstance(rows, list) else len(rows),
        "invalid_group_count": invalid,
        "min_rollouts_per_group": minimum,
        "reward_spread_min": min(spreads) if spreads else 0.0,
        "reward_spread_avg": round(sum(spreads) / max(len(spreads), 1), 4),
    }


def _trace_quality(trajectories: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    missing = 0
    observed: Counter[str] = Counter()
    for trajectory in trajectories:
        total += 1
        kinds = {
            str(item.get("kind", ""))
            for item in trajectory.get("observations", [])
            if isinstance(item, dict)
        }
        observed.update(kinds)
        if not REQUIRED_TRACE_KINDS.issubset(kinds):
            missing += 1
    return {
        "trajectory_count": total,
        "missing_required_trace_count": missing,
        "required_trace_kinds": sorted(REQUIRED_TRACE_KINDS),
        "observed_trace_counts": dict(sorted(observed.items())),
    }


def _source_split_overlap(splits: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    locations: Dict[str, set[str]] = defaultdict(set)
    for split, rows in splits.items():
        for row in rows:
            for source in _source_records(row):
                locations[source].add(split)
    return sorted(source for source, values in locations.items() if len(values) > 1)


def _source_records(row: Dict[str, Any]) -> List[str]:
    value = row.get("source_records", [])
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _task_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    return dict(sorted(Counter(str(row.get("task_type", "unknown")) for row in rows).items()))


def _privacy_hits(rows: Iterable[Dict[str, Any]], *, dataset_kind: str) -> List[str]:
    hits: List[str] = []
    for index, row in enumerate(rows):
        payload = _trainable_text(row, dataset_kind=dataset_kind)
        hits.extend(scan_privacy(payload, row_id=f"row_{index}"))
    return sorted(set(hits))


def _trainable_text(row: Dict[str, Any], *, dataset_kind: str) -> str:
    if dataset_kind == "sft":
        return "\n".join(
            str(message.get("content", ""))
            for message in row.get("messages", [])
            if isinstance(message, dict)
        )
    if dataset_kind == "dpo":
        return "\n".join(
            [
                str(row.get("prompt", "")),
                str(row.get("chosen", "")),
                str(row.get("rejected", "")),
            ]
        )
    if dataset_kind == "grpo":
        outputs = [
            str(rollout.get("output", ""))
            for rollout in row.get("rollouts", [])
            if isinstance(rollout, dict)
        ]
        return "\n".join([str(row.get("prompt", "")), *outputs])
    return ""


def _reward_total(rollout: Dict[str, Any]) -> float:
    reward = rollout.get("reward", {})
    if isinstance(reward, dict):
        value = reward.get("total", 0.0)
    else:
        value = 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _issue(
    level: Literal["error", "warning"], code: str, message: str
) -> FormalTrainingReadinessIssue:
    return FormalTrainingReadinessIssue(level=level, code=code, message=message)


def _report(
    dataset_dir: Path,
    collection: Dict[str, Any],
    row_counts: Dict[str, int],
    train_task_counts: Dict[str, Dict[str, int]],
    split_counts: Dict[str, Dict[str, int]],
    split_source_counts: Dict[str, Dict[str, int]],
    overlaps: Dict[str, List[str]],
    privacy_hits: List[str],
    rollout_quality: Dict[str, Any],
    trace_quality: Dict[str, Any],
    issues: List[FormalTrainingReadinessIssue],
    *,
    limitations: List[str] | None = None,
) -> FormalTrainingReadinessReport:
    return FormalTrainingReadinessReport(
        dataset_dir=str(dataset_dir),
        ready=not any(item.level == "error" for item in issues),
        collection_summary=collection,
        row_counts=row_counts,
        train_task_counts=train_task_counts,
        source_split_counts=split_counts,
        source_split_source_counts=split_source_counts,
        source_split_overlaps=overlaps,
        rollout_quality=rollout_quality,
        trace_quality=trace_quality,
        privacy_scan_hits=privacy_hits,
        limitations=limitations or [],
        issues=issues,
    )


__all__ = [
    "FORMAL_TASK_TYPES",
    "FormalTrainingReadinessIssue",
    "FormalTrainingReadinessReport",
    "evaluate_formal_training_readiness",
    "write_formal_training_readiness",
]
