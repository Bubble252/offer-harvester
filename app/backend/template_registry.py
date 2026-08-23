from __future__ import annotations

import json
import re
from pathlib import Path
from string import Template
from typing import Any

from models import (
    TemplateRegistryItem,
    TemplateRegistryStatus,
    TemplateRenderPreview,
    TemplateValidationIssue,
)

SUPPORTED_TEMPLATE_TYPES = [
    "contact_email",
    "personal_statement",
    "research_proposal",
    "interview_qa",
    "ppt_reference",
    "application_summary",
]

REQUIRED_MANIFEST_KEYS = {
    "template_id",
    "name",
    "template_type",
    "variables",
    "sample_context",
    "applicable_scenarios",
    "style_rules",
    "privacy_rules",
    "validation_methods",
    "managed_block",
}

FORBIDDEN_PRIVACY_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "email_literal"),
    (re.compile(r"\b1[3-9]\d{9}\b"), "phone_literal"),
    (re.compile(r"\bGPA\s*[:：]?\s*\d+(?:\.\d+)?", re.I), "gpa_literal"),
    (re.compile(r"\b\d{4,}\s*/\s*\d{4,}\b"), "rank_literal"),
]


def default_template_root(project_root: Path) -> Path:
    return project_root / ".agents" / "skills" / "grad-apply-workflow" / "templates"


def scan_template_registry(project_root: Path) -> TemplateRegistryStatus:
    template_root = default_template_root(project_root)
    templates = []
    if template_root.exists():
        for manifest_path in sorted(template_root.glob("*/TEMPLATE.md")):
            templates.append(parse_template_manifest(manifest_path, template_root))

    validation_errors = [
        issue
        for template in templates
        for issue in template.validation_issues
        if issue.severity == "error"
    ]
    active_count = sum(1 for template in templates if template.active)
    return TemplateRegistryStatus(
        template_root=template_root.relative_to(project_root).as_posix(),
        supported_template_types=SUPPORTED_TEMPLATE_TYPES,
        activation_policy="模板只有在 manifest 完整、变量完整、样例渲染通过且无隐私字面量时才能激活。",
        privacy_policy="模板必须 profile-agnostic，只允许变量占位符和匿名样例，不包含真实姓名、邮箱、成绩、导师联系信息或材料正文。",
        implemented=True,
        template_count=len(templates),
        active_count=active_count,
        templates=templates,
        validation_errors=validation_errors,
    )


def parse_template_manifest(manifest_path: Path, template_root: Path) -> TemplateRegistryItem:
    text = manifest_path.read_text(encoding="utf-8")
    issues: list[TemplateValidationIssue] = []
    manifest = extract_json_block(text)
    template_body = extract_code_block(text, "template")

    if not manifest:
        issues.append(error("manifest_missing", "TEMPLATE.md 必须包含 json manifest 代码块。"))
        manifest = {}
    if not template_body:
        issues.append(error("template_missing", "TEMPLATE.md 必须包含 template 代码块。"))

    issues.extend(validate_manifest(manifest))
    issues.extend(validate_template_privacy(text))

    variables = as_str_list(manifest.get("variables"))
    sample_context = {
        str(key): str(value) for key, value in (manifest.get("sample_context") or {}).items()
    }
    render_preview = render_template_preview(template_body, variables, sample_context)
    if not render_preview.passed:
        issues.append(
            error(
                "sample_render_failed",
                "样例渲染失败，存在未提供样例值的变量。",
            )
        )

    active = not any(issue.severity == "error" for issue in issues)
    template_id = str(manifest.get("template_id") or manifest_path.parent.name)
    return TemplateRegistryItem(
        template_id=template_id,
        name=str(manifest.get("name") or template_id),
        template_type=str(manifest.get("template_type") or ""),
        version=str(manifest.get("version") or "0.1.0"),
        description=str(manifest.get("description") or ""),
        path=manifest_path.relative_to(template_root).as_posix(),
        variables=variables,
        sample_context=sample_context,
        applicable_scenarios=as_str_list(manifest.get("applicable_scenarios")),
        style_rules=as_str_list(manifest.get("style_rules")),
        privacy_rules=as_str_list(manifest.get("privacy_rules")),
        validation_methods=as_str_list(manifest.get("validation_methods")),
        managed_block=str(manifest.get("managed_block") or ""),
        active=active,
        profile_agnostic=not any(issue.code.endswith("_literal") for issue in issues),
        validation_issues=issues,
        render_preview=render_preview,
    )


def validate_manifest(manifest: dict[str, Any]) -> list[TemplateValidationIssue]:
    issues: list[TemplateValidationIssue] = []
    missing = sorted(key for key in REQUIRED_MANIFEST_KEYS if not manifest.get(key))
    for key in missing:
        issues.append(error("manifest_required_key", f"manifest 缺少必填字段：{key}。"))

    template_type = str(manifest.get("template_type") or "")
    if template_type and template_type not in SUPPORTED_TEMPLATE_TYPES:
        issues.append(error("unsupported_type", f"不支持的模板类型：{template_type}。"))

    variables = as_str_list(manifest.get("variables"))
    sample_context = manifest.get("sample_context") or {}
    if not isinstance(sample_context, dict):
        issues.append(error("sample_context_invalid", "sample_context 必须是对象。"))
        sample_context = {}
    for variable in variables:
        if variable not in sample_context:
            issues.append(error("sample_variable_missing", f"变量 {variable} 缺少样例值。"))
    return issues


def validate_template_privacy(text: str) -> list[TemplateValidationIssue]:
    issues: list[TemplateValidationIssue] = []
    for pattern, code in FORBIDDEN_PRIVACY_PATTERNS:
        if pattern.search(text):
            issues.append(error(code, "模板或 manifest 中疑似包含真实个人隐私字面量。"))
    return issues


def render_template_preview(
    template_body: str,
    variables: list[str],
    sample_context: dict[str, str],
) -> TemplateRenderPreview:
    normalized = to_string_template(template_body)
    unresolved = [
        variable
        for variable in variables
        if variable not in sample_context or sample_context.get(variable, "") == ""
    ]
    rendered = Template(normalized).safe_substitute(sample_context)
    unresolved.extend(find_unresolved_variables(rendered))
    unresolved = list(dict.fromkeys(unresolved))
    return TemplateRenderPreview(
        rendered=rendered.strip(),
        unresolved_variables=unresolved,
        passed=not unresolved,
    )


def extract_json_block(text: str) -> dict[str, Any]:
    block = extract_code_block(text, "json")
    if not block:
        return {}
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def extract_code_block(text: str, language: str) -> str:
    pattern = re.compile(rf"```{re.escape(language)}\s*\n(.*?)\n```", re.S)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def to_string_template(template_body: str) -> str:
    return re.sub(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", r"${\1}", template_body)


def find_unresolved_variables(rendered: str) -> list[str]:
    names = re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", rendered)
    return list(dict.fromkeys(names))


def as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def error(code: str, message: str) -> TemplateValidationIssue:
    return TemplateValidationIssue(code=code, message=message, severity="error")
