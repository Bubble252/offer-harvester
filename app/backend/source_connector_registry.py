from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from urllib import robotparser
from urllib.parse import urlsplit, urlunsplit

from models import (
    SourceConnectorLiveTestResult,
    SourceConnectorRegistryItem,
    SourceConnectorRegistryStatus,
    TemplateValidationIssue,
    now_iso,
)
from services import validate_public_url

SUPPORTED_SOURCE_TYPES = [
    "school_homepage",
    "college_notice",
    "advisor_homepage",
    "admission_system",
]

REQUIRED_MANIFEST_KEYS = {
    "connector_id",
    "name",
    "source_type",
    "url_patterns",
    "field_mapping",
    "access_rules",
    "robots_policy",
    "tos_policy",
    "test_queries",
    "fallback",
    "output_scope",
}

FORBIDDEN_ACCESS_TERMS = [
    "bypass",
    "captcha bypass",
    "login bypass",
    "绕过验证码",
    "绕过登录",
    "绕过付费墙",
]

LIVE_USER_AGENT = "GradApplyWorkflowConnectorTest/0.1"
MAX_LIVE_RESPONSE_BYTES = 256_000


@dataclass
class FetchResult:
    status: int
    headers: Dict[str, str]
    body: bytes


Fetcher = Callable[[str], FetchResult]


class PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_connector_root(project_root: Path) -> Path:
    return project_root / ".agents" / "skills" / "grad-apply-workflow" / "source_connectors"


def scan_source_connector_registry(project_root: Path) -> SourceConnectorRegistryStatus:
    connector_root = default_connector_root(project_root)
    connectors = []
    if connector_root.exists():
        for manifest_path in sorted(connector_root.glob("*/CONNECTOR.md")):
            connectors.append(parse_connector_manifest(manifest_path, connector_root))

    validation_errors = [
        issue
        for connector in connectors
        for issue in connector.validation_issues
        if issue.severity == "error"
    ]
    return SourceConnectorRegistryStatus(
        connector_root=connector_root.relative_to(project_root).as_posix(),
        supported_source_types=SUPPORTED_SOURCE_TYPES,
        access_policy=(
            "连接器只描述来源读取、字段映射、访问规则和失败兜底；不内置通用爬虫，"
            "不绕过登录、验证码、付费墙、robots/ToS 或明确禁止自动访问的来源。"
        ),
        implemented=True,
        connector_count=len(connectors),
        active_count=sum(1 for connector in connectors if connector.active),
        connectors=connectors,
        validation_errors=validation_errors,
    )


def merge_live_test_results(
    status: SourceConnectorRegistryStatus,
    results: list[SourceConnectorLiveTestResult],
    now: datetime | None = None,
) -> SourceConnectorRegistryStatus:
    now = now or datetime.now().astimezone()
    latest_by_connector: dict[str, SourceConnectorLiveTestResult] = {}
    for result in results:
        previous = latest_by_connector.get(result.connector_id)
        if previous is None or result.checked_at >= previous.checked_at:
            latest_by_connector[result.connector_id] = result
    for connector in status.connectors:
        result = latest_by_connector.get(connector.connector_id)
        if not result:
            continue
        connector.live_test_status = result.status
        connector.live_test_id = result.result_id
        connector.registration_eligible = result.registration_eligible
        connector.last_live_test_at = result.checked_at
        checked_at = parse_datetime(result.checked_at)
        if checked_at:
            next_refresh = checked_at + timedelta(days=connector.refresh_interval_days)
            connector.next_refresh_at = next_refresh.isoformat()
            connector.refresh_due = next_refresh <= now
            connector.refresh_state = "due" if connector.refresh_due else "fresh"
            if connector.refresh_due:
                connector.registration_eligible = False
                connector.refresh_state = "stale"
        if result.status in {"failed", "skipped"}:
            connector.registration_eligible = False
            connector.refresh_state = "needs_review"
        elif result.status != "passed":
            connector.refresh_state = "needs_review"
    for connector in status.connectors:
        if connector.live_test_status == "not_run":
            connector.refresh_state = "not_tested"
    status.registrable_count = sum(
        1 for connector in status.connectors if connector.registration_eligible
    )
    return status


def run_source_connector_live_test(
    project_root: Path,
    connector_id: str,
    url: str,
    *,
    query: str = "",
    tos_acknowledged: bool = False,
    fetcher: Optional[Fetcher] = None,
) -> SourceConnectorLiveTestResult:
    """Run one bounded public URL check without persisting page content."""

    fetcher = fetcher or fetch_public_resource
    status = scan_source_connector_registry(project_root)
    connector = next(
        (item for item in status.connectors if item.connector_id == connector_id),
        None,
    )
    result = SourceConnectorLiveTestResult(
        connector_id=connector_id,
        url=url.strip(),
        query=query.strip(),
        tos_acknowledged=tos_acknowledged,
        fallback=(connector.fallback if connector else "") or "请改用手动粘贴来源正文。",
    )
    if connector is None:
        return _failed(result, "connector_not_found", "未找到对应的 connector manifest。")
    if not connector.active:
        return _failed(result, "manifest_invalid", "manifest 校验未通过，不能执行 live test。")
    if not tos_acknowledged:
        result.status = "skipped"
        result.error = "执行前必须确认遵守该来源的 robots.txt 和 ToS。"
        result.notes.append(connector.tos_policy)
        return result

    selected_query = query.strip() or (connector.test_queries[0] if connector.test_queries else "")
    if selected_query not in connector.test_queries:
        return _failed(result, "query_not_declared", "测试查询必须来自 connector manifest。")
    result.query = selected_query

    try:
        normalized_url = validate_public_url(url)
    except ValueError as exc:
        return _failed(result, "url_invalid", str(exc))
    if not any(_url_matches_pattern(normalized_url, pattern) for pattern in connector.url_patterns):
        return _failed(
            result, "url_pattern_mismatch", "目标 URL 不匹配 connector manifest 的 URL pattern。"
        )
    result.url = normalized_url

    robots_status, robots_note = check_robots_policy(normalized_url, fetcher)
    result.robots_status = robots_status
    if robots_note:
        result.notes.append(robots_note)
    if robots_status != "allowed":
        return _failed(result, "robots_not_allowed", "robots.txt 未允许自动访问该 URL。")

    try:
        response = fetcher(normalized_url)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return _failed(result, "fetch_failed", f"公开网页访问失败：{exc}")
    result.http_status = response.status
    result.content_type = response.headers.get("content-type", "")
    result.response_bytes = len(response.body)
    result.response_hash = f"sha256:{hashlib.sha256(response.body).hexdigest()}"
    if not 200 <= response.status < 300:
        return _failed(result, "http_status", f"公开网页返回 HTTP {response.status}。")
    if not response.body:
        return _failed(result, "empty_response", "公开网页返回空响应。")
    if not _is_readable_content_type(result.content_type):
        return _failed(result, "content_type", "响应不是可读取的 HTML 或纯文本页面。")

    result.status = "passed"
    result.registration_eligible = True
    result.notes.append("只记录响应元数据和 hash，不保存网页正文。")
    return result


def fetch_public_resource(url: str) -> FetchResult:
    validate_public_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": LIVE_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    opener = urllib.request.build_opener(PublicRedirectHandler())
    with opener.open(request, timeout=8) as response:
        body = response.read(MAX_LIVE_RESPONSE_BYTES)
        headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
        return FetchResult(status=int(response.status), headers=headers, body=body)


def check_robots_policy(url: str, fetcher: Fetcher) -> Tuple[str, str]:
    parsed = urlsplit(url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        response = fetcher(robots_url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "allowed", "robots.txt 不存在，按公开页面继续检查，但仍需遵守 ToS。"
        return "unavailable", f"robots.txt 返回 HTTP {exc.code}，默认不执行自动访问。"
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return "unavailable", f"robots.txt 检查失败：{exc}"
    if response.status == 404:
        return "allowed", "robots.txt 不存在，按公开页面继续检查，但仍需遵守 ToS。"
    if not 200 <= response.status < 300:
        return "unavailable", f"robots.txt 返回 HTTP {response.status}，默认不执行自动访问。"
    parser = robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.body.decode("utf-8", errors="ignore").splitlines())
    if not parser.can_fetch(LIVE_USER_AGENT, url):
        return "blocked", "robots.txt 禁止当前 connector 访问该 URL。"
    return "allowed", "robots.txt 允许当前 connector 访问该 URL。"


def _url_matches_pattern(url: str, pattern: str) -> bool:
    expression = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return bool(re.match(expression, url, re.IGNORECASE))


def _is_readable_content_type(content_type: str) -> bool:
    normalized = content_type.lower()
    return not normalized or any(
        value in normalized for value in ("text/html", "application/xhtml+xml", "text/plain")
    )


def _failed(
    result: SourceConnectorLiveTestResult,
    code: str,
    message: str,
) -> SourceConnectorLiveTestResult:
    result.status = "failed"
    result.registration_eligible = False
    result.error = f"{code}: {message}"
    result.checked_at = now_iso()
    return result


def parse_connector_manifest(
    manifest_path: Path,
    connector_root: Path,
) -> SourceConnectorRegistryItem:
    text = manifest_path.read_text(encoding="utf-8")
    issues: list[TemplateValidationIssue] = []
    manifest = extract_json_block(text)
    if not manifest:
        issues.append(error("manifest_missing", "CONNECTOR.md 必须包含 json manifest 代码块。"))
        manifest = {}

    issues.extend(validate_manifest(manifest, text))
    connector_id = str(manifest.get("connector_id") or manifest_path.parent.name)
    active = not any(issue.severity == "error" for issue in issues)
    return SourceConnectorRegistryItem(
        connector_id=connector_id,
        name=str(manifest.get("name") or connector_id),
        source_type=str(manifest.get("source_type") or ""),
        version=str(manifest.get("version") or "0.1.0"),
        description=str(manifest.get("description") or ""),
        path=manifest_path.relative_to(connector_root).as_posix(),
        url_patterns=as_str_list(manifest.get("url_patterns")),
        field_mapping=as_str_dict(manifest.get("field_mapping")),
        access_rules=as_str_list(manifest.get("access_rules")),
        robots_policy=str(manifest.get("robots_policy") or ""),
        tos_policy=str(manifest.get("tos_policy") or ""),
        test_queries=as_str_list(manifest.get("test_queries")),
        test_urls=as_str_list(manifest.get("test_urls")),
        fallback=str(manifest.get("fallback") or ""),
        output_scope=str(manifest.get("output_scope") or "workspace_or_fork"),  # type: ignore[arg-type]
        refresh_interval_days=max(1, int(manifest.get("refresh_interval_days") or 7)),
        active=active,
        validation_issues=issues,
    )


def validate_manifest(
    manifest: dict[str, Any],
    raw_text: str,
) -> list[TemplateValidationIssue]:
    issues: list[TemplateValidationIssue] = []
    missing = sorted(key for key in REQUIRED_MANIFEST_KEYS if not manifest.get(key))
    for key in missing:
        issues.append(error("manifest_required_key", f"manifest 缺少必填字段：{key}。"))

    source_type = str(manifest.get("source_type") or "")
    if source_type and source_type not in SUPPORTED_SOURCE_TYPES:
        issues.append(error("unsupported_source_type", f"不支持的来源类型：{source_type}。"))

    url_patterns = as_str_list(manifest.get("url_patterns"))
    if not url_patterns:
        issues.append(error("url_patterns_missing", "必须提供至少一个 URL pattern。"))
    for pattern in url_patterns:
        if not (pattern.startswith("https://") or pattern.startswith("http://")):
            issues.append(
                error("url_pattern_invalid", f"URL pattern 必须显式声明协议：{pattern}。")
            )
        if any(token in pattern for token in ["localhost", "127.0.0.1", "0.0.0.0"]):
            issues.append(
                error("url_pattern_private", f"URL pattern 不允许指向本机或内网：{pattern}。")
            )

    field_mapping = as_str_dict(manifest.get("field_mapping"))
    if not field_mapping:
        issues.append(error("field_mapping_missing", "必须声明字段映射。"))
    required_fields = {"title", "source_url", "raw_text"}
    missing_fields = sorted(required_fields - set(field_mapping))
    for field in missing_fields:
        issues.append(error("field_mapping_required", f"字段映射缺少：{field}。"))

    if not as_str_list(manifest.get("test_queries")):
        issues.append(error("test_queries_missing", "必须提供测试查询或样例 URL。"))
    for test_url in as_str_list(manifest.get("test_urls")):
        try:
            validate_public_url(test_url)
        except ValueError as exc:
            issues.append(error("test_url_invalid", f"测试 URL 不合法：{exc}"))
        if url_patterns and not any(
            _url_matches_pattern(test_url, pattern) for pattern in url_patterns
        ):
            issues.append(error("test_url_pattern_mismatch", "测试 URL 不匹配 URL pattern。"))
    if str(manifest.get("output_scope") or "") != "workspace_or_fork":
        issues.append(
            error("output_scope_invalid", "connector 输出必须留在用户 workspace 或 fork。")
        )

    combined = raw_text.lower()
    if any(term.lower() in combined for term in FORBIDDEN_ACCESS_TERMS):
        issues.append(error("forbidden_access_rule", "connector 不允许声明绕过访问限制。"))
    return issues


def extract_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def as_str_dict(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(key).strip()}


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def error(code: str, message: str) -> TemplateValidationIssue:
    return TemplateValidationIssue(code=code, message=message, severity="error")
