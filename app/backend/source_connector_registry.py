from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from models import (
    SourceConnectorRegistryItem,
    SourceConnectorRegistryStatus,
    TemplateValidationIssue,
)

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
        fallback=str(manifest.get("fallback") or ""),
        output_scope=str(manifest.get("output_scope") or "workspace_or_fork"),  # type: ignore[arg-type]
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


def error(code: str, message: str) -> TemplateValidationIssue:
    return TemplateValidationIssue(code=code, message=message, severity="error")
