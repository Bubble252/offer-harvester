from __future__ import annotations

import urllib.error
from pathlib import Path

import main as backend_main
from models import SourceConnectorLiveTestRequest, SourceConnectorLiveTestResult
from source_connector_registry import (
    FetchResult,
    merge_live_test_results,
    run_source_connector_live_test,
    scan_source_connector_registry,
)
from storage import Workspace

ROOT = Path(__file__).resolve().parents[1]


def fake_fetcher(url: str) -> FetchResult:
    if url.endswith("/robots.txt"):
        return FetchResult(
            status=200,
            headers={"content-type": "text/plain"},
            body=b"User-agent: *\nAllow: /\n",
        )
    return FetchResult(
        status=200,
        headers={"content-type": "text/html; charset=utf-8"},
        body=b"<html><title>Public notice</title><body>admission deadline</body></html>",
    )


def test_live_test_requires_tos_acknowledgement():
    result = run_source_connector_live_test(
        ROOT,
        "college_notice_generic_zh",
        "https://example.edu/notice/2026",
        query="推免 通知 截止日期 材料",
        fetcher=fake_fetcher,
    )

    assert result.status == "skipped"
    assert result.registration_eligible is False
    assert "ToS" in result.error


def test_live_test_passes_only_for_public_declared_url():
    result = run_source_connector_live_test(
        ROOT,
        "college_notice_generic_zh",
        "https://example.edu/notice/2026",
        query="推免 通知 截止日期 材料",
        tos_acknowledged=True,
        fetcher=fake_fetcher,
    )

    assert result.status == "passed"
    assert result.registration_eligible is True
    assert result.robots_status == "allowed"
    assert result.http_status == 200
    assert result.response_hash.startswith("sha256:")
    assert result.response_bytes > 0


def test_live_test_rejects_url_outside_manifest_pattern():
    result = run_source_connector_live_test(
        ROOT,
        "advisor_homepage_generic_zh",
        "https://example.edu/private/2026",
        query="导师 姓名 研究方向 邮箱",
        tos_acknowledged=True,
        fetcher=fake_fetcher,
    )

    assert result.status == "failed"
    assert result.registration_eligible is False
    assert "url_pattern_mismatch" in result.error


def test_live_test_does_not_save_page_body():
    result = run_source_connector_live_test(
        ROOT,
        "advisor_homepage_generic_zh",
        "https://example.edu/faculty/a",
        query="导师 姓名 研究方向 邮箱",
        tos_acknowledged=True,
        fetcher=fake_fetcher,
    )

    assert result.status == "passed"
    assert not hasattr(result, "body")
    serialized = result.model_dump_json() if hasattr(result, "model_dump_json") else result.json()
    assert "Public notice" not in serialized


def test_missing_robots_file_is_allowed_with_warning():
    def fetch_without_robots(url: str) -> FetchResult:
        if url.endswith("/robots.txt"):
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)
        return fake_fetcher(url)

    result = run_source_connector_live_test(
        ROOT,
        "advisor_homepage_generic_zh",
        "https://example.edu/faculty/a",
        query="导师 姓名 研究方向 邮箱",
        tos_acknowledged=True,
        fetcher=fetch_without_robots,
    )

    assert result.status == "passed"
    assert result.robots_status == "allowed"
    assert any("不存在" in note for note in result.notes)


def test_registry_marks_connector_registrable_only_after_live_test():
    status = scan_source_connector_registry(ROOT)
    connector = next(
        item for item in status.connectors if item.connector_id == "advisor_homepage_generic_zh"
    )
    assert connector.active is True
    assert connector.registration_eligible is False

    result = SourceConnectorLiveTestResult(
        connector_id=connector.connector_id,
        status="passed",
        registration_eligible=True,
    )
    merged = merge_live_test_results(status, [result])
    updated = next(
        item for item in merged.connectors if item.connector_id == connector.connector_id
    )
    assert updated.live_test_status == "passed"
    assert updated.registration_eligible is True
    assert merged.registrable_count >= 1


def test_live_test_api_persists_result_and_refreshes_registry(tmp_path, monkeypatch):
    previous_workspace = backend_main.workspace
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    expected = SourceConnectorLiveTestResult(
        connector_id="advisor_homepage_generic_zh",
        url="https://example.edu/faculty/a",
        query="导师 姓名 研究方向 邮箱",
        status="passed",
        registration_eligible=True,
    )
    monkeypatch.setattr(
        backend_main,
        "run_source_connector_live_test",
        lambda *args, **kwargs: expected,
    )
    try:
        saved = backend_main.run_source_connector_test(
            "advisor_homepage_generic_zh",
            SourceConnectorLiveTestRequest(
                url=expected.url,
                query=expected.query,
                tos_acknowledged=True,
            ),
        )
        assert saved.result_id == expected.result_id
        assert workspace.list("source_connector_live_tests")
        status = backend_main.get_source_connector_status()
        connector = next(
            item for item in status.connectors if item.connector_id == "advisor_homepage_generic_zh"
        )
        assert connector.registration_eligible is True
        assert status.registrable_count >= 1
    finally:
        backend_main.workspace = previous_workspace
