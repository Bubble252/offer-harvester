from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from evaluation import run_rag_memory_evaluation  # noqa: E402

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "evaluation_set"


def test_rag_memory_evaluation_runner_records_metrics(tmp_path):
    report_path = tmp_path / "reports" / "rag_memory_eval.json"

    report = run_rag_memory_evaluation(
        FIXTURE_ROOT,
        workspace_dir=tmp_path / "workspace",
        storage_backend="sqlite",
        reset_workspace=True,
        report_path=report_path,
    )

    summary = report["summary"]
    assert summary["retrieval_case_count"] == 15
    assert 0.0 <= summary["recall_at_5"] <= 1.0
    assert 0.0 <= summary["mrr"] <= 1.0
    assert summary["expired_policy_rejection_rate"] == 1.0
    assert summary["rejected_leakage_rate"] == 0.0
    assert summary["evidence_audit_pass_rate"] >= 0.0
    assert summary["auditor_pass_rate_on_current_bundles"] == summary["evidence_audit_pass_rate"]
    assert summary["privacy_safety_rate"] == 1.0
    assert summary["teacher_retrieval_metrics"]["count"] == 5
    assert summary["policy_retrieval_metrics"]["count"] == 5
    assert summary["student_retrieval_metrics"]["count"] == 5
    assert summary["email_signal_accuracy"] == 1.0
    assert summary["feedback_candidate_created"] is True
    assert report_path.exists()
    assert report["retrieval"][0]["evidence_bundle_id"]
