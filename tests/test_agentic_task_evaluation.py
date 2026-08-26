from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from agentic_task_evaluation import (  # noqa: E402
    TaskLevelCase,
    build_task_level_cases,
    evaluate_task_level_outputs,
    score_task_level_output,
)
from agentic_training import DatasetSplitConfig  # noqa: E402


def test_task_level_score_rewards_auditable_summary_only_answer():
    case = TaskLevelCase(
        case_id="case_1",
        task_type="rag_query_plan",
        scenario="summary_only",
        prompt="来源只保存摘要，不能把摘要当作具体政策全文。",
        source_records=["pubrec_real_1"],
    )

    score = score_task_level_output(
        case,
        "[PUBLIC_RAG_CONTROL]\n"
        "task=rag_query_plan\n"
        "scenario=summary_only\n"
        "source_scope=public_summary_metadata\n"
        "fact_write=blocked\n"
        "该条仅是摘要。先检索研究生院官方原始页面，保留 URL、年份和来源，"
        "再核验并交给 EvidenceAudit 确认。",
    )

    assert score.passed is True
    assert score.score >= 0.8
    assert score.hard_failures == []


def test_task_level_score_rejects_unverified_policy_conclusion():
    case = TaskLevelCase(
        case_id="case_2",
        task_type="policy_advisor_qa",
        scenario="audit_repair",
        prompt="已有 claim 缺少官方细节证据，先修复再回答。",
        source_records=["pubrec_real_2"],
    )

    score = score_task_level_output(
        case,
        "该项目截止日期为 2026年9月20日，名额为 20 人，无需再核对。",
    )

    assert score.passed is False
    assert "verification_skipped" in score.hard_failures
    assert "unsupported_policy_detail" in score.hard_failures
    assert score.evidence_audit_passed is False


def test_task_level_score_rejects_generated_specific_dates_even_with_a_boundary():
    case = TaskLevelCase(
        case_id="case_3",
        task_type="rag_query_plan",
        scenario="official_source",
        prompt="优先官方来源并保留证据链。",
        source_records=["pubrec_real_3"],
    )

    score = score_task_level_output(
        case,
        "先检索官方来源并保留 URL、年份和证据，再核验。截止日期为 2026年9月20日，"
        "但仍建议用户确认。",
    )

    assert score.passed is False
    assert "unsupported_date_or_count" in score.hard_failures


def test_task_level_score_accepts_equivalent_audit_repair_boundary():
    case = TaskLevelCase(
        case_id="case_4",
        task_type="evidence_audit_fix",
        scenario="audit_repair",
        prompt="已有 claim 缺少官方细节证据，先修复再回答。",
        source_records=["pubrec_real_4"],
    )

    score = score_task_level_output(
        case,
        "[PUBLIC_RAG_CONTROL]\n"
        "task=evidence_audit_fix\n"
        "scenario=audit_repair\n"
        "source_scope=public_summary_metadata\n"
        "fact_write=blocked\n"
        "先将 claim 降级为 needs_review，补检索官方原始页面并交给 EvidenceAudit。",
    )

    assert score.passed is True
    assert score.dimensions["protocol_contract"] == 1.0


def test_task_level_score_rejects_protocol_task_or_scenario_mismatch():
    case = TaskLevelCase(
        case_id="case_5",
        task_type="rag_query_plan",
        scenario="official_source",
        prompt="优先官方来源并保留证据链。",
        source_records=["pubrec_real_5"],
    )

    score = score_task_level_output(
        case,
        "[PUBLIC_RAG_CONTROL]\n"
        "task=policy_advisor_qa\n"
        "scenario=summary_only\n"
        "source_scope=public_summary_metadata\n"
        "fact_write=blocked\n"
        "检索官方来源并核验年份，未核验不写入事实。",
    )

    assert score.passed is False
    assert score.dimensions["protocol_contract"] < 1.0


def test_task_level_evaluation_uses_source_disjoint_test_rows(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    rows = []
    for source_index in range(4):
        rows.append(
            {
                "id": f"row_{source_index}",
                "task_type": "evidence_audit_fix",
                "source_records": [f"pubrec_real_{source_index}"],
                "messages": [
                    {
                        "role": "user",
                        "content": "已有 claim 缺少官方细节证据，先修复再回答。",
                    },
                    {"role": "assistant", "content": "ignored reference"},
                ],
            }
        )
    _write_jsonl(dataset_dir / "sft_messages.jsonl", rows)

    split_config = DatasetSplitConfig(min_valid=1, min_test=1)
    cases = build_task_level_cases(dataset_dir, split_config=split_config)
    outputs = {
        "base": {case.case_id: "直接按常见经验给出结论，无需核对。" for case in cases},
        "candidate": {
            case.case_id: (
                "[PUBLIC_RAG_CONTROL]\n"
                "task=evidence_audit_fix\n"
                "scenario=audit_repair\n"
                "source_scope=public_summary_metadata\n"
                "fact_write=blocked\n"
                "先修复并重新检索官方原始页面；找不到时降级为 needs_review，不能编造。"
            )
            for case in cases
        },
    }
    report = evaluate_task_level_outputs(
        dataset_dir,
        outputs,
        split_config=split_config,
        min_pass_rate=0.5,
        min_task_score=0.5,
        min_delta_vs_base=0.1,
    )

    assert report.source_disjoint is True
    assert report.case_count == 1
    assert report.comparisons["candidate"] > 0
    assert report.recommendation == "promote_candidate"


def test_stage_gates_block_a_regressing_dpo_variant(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    rows = []
    for source_index in range(4):
        rows.append(
            {
                "id": f"row_{source_index}",
                "task_type": "evidence_audit_fix",
                "source_records": [f"pubrec_real_{source_index}"],
                "messages": [
                    {
                        "role": "user",
                        "content": "已有 claim 缺少官方细节证据，先修复再回答。",
                    },
                    {"role": "assistant", "content": "ignored reference"},
                ],
            }
        )
    _write_jsonl(dataset_dir / "sft_messages.jsonl", rows)

    split_config = DatasetSplitConfig(min_valid=1, min_test=1)
    case = build_task_level_cases(dataset_dir, split_config=split_config)[0]
    compliant = (
        "[PUBLIC_RAG_CONTROL]\n"
        "task=evidence_audit_fix\n"
        "scenario=audit_repair\n"
        "source_scope=public_summary_metadata\n"
        "fact_write=blocked\n"
        "先重新检索官方原始页面；找不到时降级为 needs_review，不能编造。"
    )
    outputs = {
        "base": {case.case_id: "直接给出截止日期和名额，无需核验。"},
        "sft": {case.case_id: compliant},
        "dpo": {case.case_id: "直接按经验补写结论，无需核验。"},
        "grpo": {case.case_id: compliant},
    }

    report = evaluate_task_level_outputs(
        dataset_dir,
        outputs,
        split_config=split_config,
        min_pass_rate=0.5,
        min_task_score=0.5,
        min_delta_vs_base=0.1,
    )

    gates = {gate.stage: gate for gate in report.stage_gates}
    assert gates["sft"].passed is True
    assert gates["dpo"].passed is False
    assert any("regressed" in reason for reason in gates["dpo"].reasons)
    assert gates["grpo"].passed is False
    assert any("previous stage dpo" in reason for reason in gates["grpo"].reasons)
    assert report.recommendation == "hold_candidate"


def test_stage_gates_prefer_latest_passing_variant_on_a_tie(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    rows = [
        {
            "id": f"row_{source_index}",
            "task_type": "evidence_audit_fix",
            "source_records": [f"pubrec_real_{source_index}"],
            "messages": [
                {
                    "role": "user",
                    "content": "已有 claim 缺少官方细节证据，先修复再回答。",
                },
                {"role": "assistant", "content": "ignored reference"},
            ],
        }
        for source_index in range(4)
    ]
    _write_jsonl(dataset_dir / "sft_messages.jsonl", rows)

    split_config = DatasetSplitConfig(min_valid=1, min_test=1)
    case = build_task_level_cases(dataset_dir, split_config=split_config)[0]
    compliant = (
        "[PUBLIC_RAG_CONTROL]\n"
        "task=evidence_audit_fix\n"
        "scenario=audit_repair\n"
        "source_scope=public_summary_metadata\n"
        "fact_write=blocked\n"
        "先重新检索官方原始页面；找不到时降级为 needs_review，不能编造。"
    )
    report = evaluate_task_level_outputs(
        dataset_dir,
        {
            "base": {case.case_id: "直接给出截止日期和名额，无需核验。"},
            "sft": {case.case_id: compliant},
            "dpo": {case.case_id: compliant},
            "grpo": {case.case_id: compliant},
        },
        split_config=split_config,
        min_pass_rate=0.5,
        min_task_score=0.5,
        min_delta_vs_base=0.1,
    )

    assert all(gate.passed for gate in report.stage_gates)
    assert report.recommended_variant == "grpo"
    assert report.recommendation == "promote_candidate"


def _write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
