from __future__ import annotations

from datetime import datetime
from pathlib import Path

from models import (
    CustomTemplateCreateRequest,
    CustomTemplateUpdateRequest,
    SourceConnectorLiveTestResult,
)
from pdf_readability import inspect_pdf_bytes
from source_connector_registry import merge_live_test_results, scan_source_connector_registry
from storage import Workspace
from template_registry import (
    create_custom_template,
    get_custom_template_diff,
    scan_template_registry,
    set_custom_template_status,
    update_custom_template,
)

ROOT = Path(__file__).resolve().parents[1]


def test_custom_template_has_local_versions_lifecycle_and_diff(tmp_path):
    workspace = Workspace(str(tmp_path))
    record = create_custom_template(
        workspace,
        CustomTemplateCreateRequest(
            name="我的套磁模板",
            template_type="contact_email",
            content="尊敬的{{advisor_name}}老师：\n我是{{name}}。",
            sample_context={"advisor_name": "张教授", "name": "匿名学生"},
        ),
    )

    assert record.status == "draft"
    assert record.version_count == 1
    assert (workspace.root / record.content_path).exists()

    updated = update_custom_template(
        workspace,
        record.template_id,
        CustomTemplateUpdateRequest(
            content="尊敬的{{advisor_name}}老师：\n我是{{name}}，希望申请贵组。",
            note="补充申请意图",
        ),
    )
    assert updated.version_count == 2
    diff = get_custom_template_diff(workspace, record.template_id)
    assert "申请贵组" in diff.diff_text

    active = set_custom_template_status(workspace, record.template_id, "active")
    assert active.active is True
    disabled = set_custom_template_status(workspace, record.template_id, "disabled")
    assert disabled.active is False

    status = scan_template_registry(ROOT, workspace.root)
    assert status.custom_template_count == 1
    assert status.custom_active_count == 0
    assert status.custom_templates[0].version_count == 2


def test_connector_becomes_stale_after_seven_days():
    status = scan_source_connector_registry(ROOT)
    connector = next(
        item for item in status.connectors if item.connector_id == "advisor_homepage_generic_zh"
    )
    result = SourceConnectorLiveTestResult(
        connector_id=connector.connector_id,
        status="passed",
        registration_eligible=True,
        checked_at="2026-08-01T10:00:00+08:00",
    )
    merged = merge_live_test_results(
        status,
        [result],
        now=datetime.fromisoformat("2026-08-23T10:00:00+08:00"),
    )
    refreshed = next(
        item for item in merged.connectors if item.connector_id == connector.connector_id
    )
    assert refreshed.refresh_state == "stale"
    assert refreshed.refresh_due is True
    assert refreshed.registration_eligible is False


def test_pdf_readability_probe_checks_text_and_key_fields():
    pdf = (
        b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n"
        + "BT (姓名) Tj (email) Tj ET\n%%EOF".encode("utf-8")
    )
    report = inspect_pdf_bytes(pdf, "resume.pdf", ["name", "email"])
    assert report.readable is True
    assert report.page_count == 1
    assert report.text_layer_detected is True
    assert report.extracted_fields == ["name", "email"]
    assert report.needs_ocr is False


def test_pdf_scan_without_text_layer_needs_ocr():
    pdf = b"%PDF-1.7\n1 0 obj << /Type /Page >> endobj\n%%EOF"
    report = inspect_pdf_bytes(pdf, "scan.pdf", ["name"])
    assert report.readable is False
    assert report.needs_ocr is True
    assert any(issue.code == "text_layer_missing" for issue in report.issues)
