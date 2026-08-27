from __future__ import annotations

import difflib
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

from models import (
    CustomTemplateCreateRequest,
    CustomTemplateRecord,
    CustomTemplateUpdateRequest,
    TemplateDiffReport,
    TemplateRegistryItem,
    TemplateRegistryStatus,
    TemplateRenderPreview,
    TemplateValidationIssue,
    TemplateVersionRecord,
    now_iso,
)
from storage import Workspace

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


def scan_template_registry(
    project_root: Path,
    workspace_root: Path | None = None,
) -> TemplateRegistryStatus:
    template_root = default_template_root(project_root)
    templates = []
    if template_root.exists():
        for manifest_path in sorted(template_root.glob("*/TEMPLATE.md")):
            templates.append(parse_template_manifest(manifest_path, template_root))

    custom_templates = load_custom_templates(workspace_root)

    validation_errors = [
        issue
        for template in templates
        for issue in template.validation_issues
        if issue.severity == "error"
    ]
    active_count = sum(1 for template in templates if template.active)
    custom_validation_errors = [
        issue
        for template in custom_templates
        for issue in template.validation_issues
        if issue.severity == "error"
    ]
    return TemplateRegistryStatus(
        template_root=template_root.relative_to(project_root).as_posix(),
        workspace_template_root=(
            Path("workspace/templates").as_posix() if workspace_root else "workspace/templates"
        ),
        supported_template_types=SUPPORTED_TEMPLATE_TYPES,
        activation_policy="模板只有在 manifest 完整、变量完整、样例渲染通过且无隐私字面量时才能激活。",
        privacy_policy="模板必须 profile-agnostic，只允许变量占位符和匿名样例，不包含真实姓名、邮箱、成绩、导师联系信息或材料正文。",
        implemented=True,
        template_count=len(templates),
        active_count=active_count,
        custom_template_count=len(custom_templates),
        custom_active_count=sum(item.active for item in custom_templates),
        templates=templates,
        custom_templates=custom_templates,
        validation_errors=validation_errors + custom_validation_errors,
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


def load_custom_templates(workspace_root: Path | None) -> list[CustomTemplateRecord]:
    if workspace_root is None:
        return []
    workspace = Workspace(str(workspace_root))
    manifest = workspace.read_template_workspace_manifest()
    records = []
    for raw in manifest.get("templates", []):
        try:
            records.append(CustomTemplateRecord(**raw))
        except Exception:
            continue
    return records


def create_custom_template(
    workspace: Workspace,
    payload: CustomTemplateCreateRequest,
) -> CustomTemplateRecord:
    if not payload.name.strip() or not payload.content.strip():
        raise ValueError("模板名称和内容不能为空。")
    template_id = make_custom_template_id(payload.name, workspace)
    record = CustomTemplateRecord(
        template_id=template_id,
        name=payload.name.strip(),
        template_type=payload.template_type,
        description=payload.description,
        status=payload.status,
        content=payload.content,
        variables=payload.variables,
        sample_context={str(key): str(value) for key, value in payload.sample_context.items()},
        applicable_scenarios=payload.applicable_scenarios,
        style_rules=payload.style_rules,
        privacy_rules=payload.privacy_rules,
        validation_methods=payload.validation_methods,
        managed_block=payload.managed_block,
    )
    refresh_custom_template_validation(record)
    ensure_template_status_allowed(record)
    append_template_version(workspace, record, "", payload.note)
    save_custom_template(workspace, record, note=payload.note)
    return record


def create_custom_template_from_document(
    workspace: Workspace,
    document: str,
    fallback_name: str,
    fallback_type: str,
    description: str = "",
) -> CustomTemplateRecord:
    manifest = extract_json_block(document)
    body = extract_code_block(document, "template")
    if manifest and body:
        payload = CustomTemplateCreateRequest(
            name=str(manifest.get("name") or fallback_name),
            template_type=str(manifest.get("template_type") or fallback_type),
            description=str(manifest.get("description") or description),
            content=body,
            variables=as_str_list(manifest.get("variables")),
            sample_context={
                str(key): str(value)
                for key, value in (manifest.get("sample_context") or {}).items()
            },
            applicable_scenarios=as_str_list(manifest.get("applicable_scenarios")),
            style_rules=as_str_list(manifest.get("style_rules")),
            privacy_rules=as_str_list(manifest.get("privacy_rules")),
            validation_methods=as_str_list(manifest.get("validation_methods")),
            managed_block=str(manifest.get("managed_block") or ""),
        )
    else:
        payload = CustomTemplateCreateRequest(
            name=fallback_name,
            template_type=fallback_type,
            description=description,
            content=document,
        )
    return create_custom_template(workspace, payload)


def update_custom_template(
    workspace: Workspace,
    template_id: str,
    payload: CustomTemplateUpdateRequest,
) -> CustomTemplateRecord:
    record = get_custom_template(workspace, template_id)
    previous_content = record.content
    changes = (
        payload.model_dump(exclude_none=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_none=True)
    )
    changes.pop("note", None)
    for key, value in changes.items():
        setattr(record, key, value)
    refresh_custom_template_validation(record)
    ensure_template_status_allowed(record)
    if record.content != previous_content:
        append_template_version(workspace, record, previous_content, payload.note)
    record.updated_at = now_iso()
    save_custom_template(workspace, record)
    return record


def set_custom_template_status(
    workspace: Workspace,
    template_id: str,
    status: str,
) -> CustomTemplateRecord:
    record = get_custom_template(workspace, template_id)
    if status not in {"draft", "validated", "active", "disabled", "archived"}:
        raise ValueError("不支持的模板生命周期状态。")
    record.status = status  # type: ignore[assignment]
    refresh_custom_template_validation(record)
    ensure_template_status_allowed(record)
    record.updated_at = now_iso()
    save_custom_template(workspace, record)
    return record


def get_custom_template(workspace: Workspace, template_id: str) -> CustomTemplateRecord:
    manifest = workspace.read_template_workspace_manifest()
    for raw in manifest.get("templates", []):
        if raw.get("template_id") == template_id:
            return CustomTemplateRecord(**raw)
    raise ValueError("未找到对应的用户模板。")


def get_custom_template_diff(
    workspace: Workspace,
    template_id: str,
    from_version_id: str = "",
    to_version_id: str = "",
) -> TemplateDiffReport:
    record = get_custom_template(workspace, template_id)
    if not record.versions:
        raise ValueError("该模板还没有可比较的版本。")
    from_version = next(
        (item for item in record.versions if item.version_id == from_version_id),
        record.versions[0],
    )
    to_version = next(
        (item for item in record.versions if item.version_id == to_version_id),
        record.versions[-1],
    )
    diff_text = to_version.diff_text if to_version.version_id != from_version.version_id else ""
    if not diff_text:
        diff_text = build_version_diff(workspace, from_version, to_version)
    return TemplateDiffReport(
        template_id=template_id,
        from_version_id=from_version.version_id,
        to_version_id=to_version.version_id,
        diff_text=diff_text,
        summary=(
            "两个版本内容一致。"
            if not diff_text
            else f"比较版本 {from_version.version_index} -> {to_version.version_index}。"
        ),
    )


def save_custom_template(
    workspace: Workspace, record: CustomTemplateRecord, note: str = ""
) -> None:
    template_dir = workspace.template_workspace_template_dir(record.template_id)
    template_dir.mkdir(parents=True, exist_ok=True)
    record.content_path = (Path("templates") / record.template_id / "content.md").as_posix()
    (workspace.root / record.content_path).write_text(record.content, encoding="utf-8")
    template_manifest = template_dir / "manifest.json"
    template_manifest.write_text(
        json.dumps(model_dump(record), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if note:
        record.updated_at = now_iso()
    manifest = workspace.read_template_workspace_manifest()
    templates = [
        item
        for item in manifest.get("templates", [])
        if item.get("template_id") != record.template_id
    ]
    templates.append(model_dump(record))
    workspace.write_template_workspace_manifest({"templates": templates})


def refresh_custom_template_validation(record: CustomTemplateRecord) -> None:
    if not record.variables:
        record.variables = extract_template_variables(record.content)
    manifest = {
        "template_id": record.template_id,
        "name": record.name,
        "template_type": record.template_type,
        "description": record.description,
        "variables": record.variables,
        "sample_context": record.sample_context,
        "applicable_scenarios": record.applicable_scenarios,
        "style_rules": record.style_rules,
        "privacy_rules": record.privacy_rules,
        "validation_methods": record.validation_methods,
        "managed_block": record.managed_block,
    }
    text = json.dumps(manifest, ensure_ascii=False) + "\n" + record.content
    issues = validate_manifest(manifest) + validate_template_privacy(text)
    preview = render_template_preview(record.content, record.variables, record.sample_context)
    if not preview.passed:
        issues.append(error("sample_render_failed", "样例渲染失败，存在未提供样例值的变量。"))
    record.validation_issues = issues
    record.render_preview = preview
    record.active = record.status == "active" and not any(
        item.severity == "error" for item in issues
    )


def ensure_template_status_allowed(record: CustomTemplateRecord) -> None:
    has_errors = any(item.severity == "error" for item in record.validation_issues)
    if record.status in {"validated", "active"} and has_errors:
        raise ValueError("模板校验未通过，不能进入 validated 或 active 状态。")
    if record.status == "active":
        record.active = True
    else:
        record.active = False


def append_template_version(
    workspace: Workspace,
    record: CustomTemplateRecord,
    previous_content: str,
    note: str = "",
) -> TemplateVersionRecord:
    version_index = record.version_count + 1
    version_id = f"{record.template_id}_v{version_index}"
    version_path = Path("templates") / record.template_id / "versions" / f"{version_id}.md"
    (workspace.root / version_path).parent.mkdir(parents=True, exist_ok=True)
    (workspace.root / version_path).write_text(record.content, encoding="utf-8")
    version = TemplateVersionRecord(
        version_id=version_id,
        template_id=record.template_id,
        version_index=version_index,
        content_hash=f"sha256:{hashlib.sha256(record.content.encode('utf-8')).hexdigest()}",
        content_path=version_path.as_posix(),
        note=note,
        diff_text="\n".join(
            difflib.unified_diff(
                previous_content.splitlines(),
                record.content.splitlines(),
                fromfile=f"version-{version_index - 1}",
                tofile=f"version-{version_index}",
                lineterm="",
            )
        ),
    )
    record.content_path = (Path("templates") / record.template_id / "content.md").as_posix()
    record.versions.append(version)
    record.version_count = version_index
    record.latest_version_id = version.version_id
    return version


def build_version_diff(
    workspace: Workspace,
    from_version: TemplateVersionRecord,
    to_version: TemplateVersionRecord,
) -> str:
    from_path = workspace.root / from_version.content_path
    to_path = workspace.root / to_version.content_path
    from_text = from_path.read_text(encoding="utf-8") if from_path.exists() else ""
    to_text = to_path.read_text(encoding="utf-8") if to_path.exists() else ""
    return "\n".join(
        difflib.unified_diff(
            from_text.splitlines(),
            to_text.splitlines(),
            fromfile=f"version-{from_version.version_index}",
            tofile=f"version-{to_version.version_index}",
            lineterm="",
        )
    )


def make_custom_template_id(name: str, workspace: Workspace) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "template"
    digest = hashlib.sha256(f"{name}:{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    template_id = f"custom-{base[:32]}-{digest}"
    while any(
        item.get("template_id") == template_id
        for item in workspace.read_template_workspace_manifest().get("templates", [])
    ):
        digest = hashlib.sha256(f"{template_id}:{datetime.now().isoformat()}".encode()).hexdigest()[
            :8
        ]
        template_id = f"custom-{base[:32]}-{digest}"
    return template_id


def model_dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def extract_template_variables(template_text: str) -> list[str]:
    candidates = re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", template_text)
    candidates.extend(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", template_text))
    return list(dict.fromkeys(candidates))


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
