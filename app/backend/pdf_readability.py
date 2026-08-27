from __future__ import annotations

import hashlib
import re
from pathlib import Path

from models import PdfReadabilityIssue, PdfReadabilityReport

FIELD_ALIASES = {
    "name": ["姓名", "name"],
    "email": ["邮箱", "email", "e-mail"],
    "phone": ["手机", "电话", "phone", "tel"],
    "school": ["学校", "school", "university"],
    "project": ["项目", "project", "科研"],
    "gpa": ["gpa", "绩点"],
}


def inspect_pdf_bytes(
    content: bytes,
    filename: str = "document.pdf",
    expected_fields: list[str] | None = None,
) -> PdfReadabilityReport:
    expected = [item.strip().lower() for item in (expected_fields or []) if item.strip()]
    digest = hashlib.sha256(content).hexdigest() if content else ""
    issues: list[PdfReadabilityIssue] = []
    suggestions: list[str] = []

    valid_header = content.startswith(b"%PDF-")
    has_eof = b"%%EOF" in content[-2048:] if content else False
    page_count = len(re.findall(rb"/Type\s*/Page\b", content))
    text_blocks = re.findall(rb"\bBT\b(.*?)\bET\b", content, flags=re.S)
    extracted_text = extract_literal_text(text_blocks)
    text_layer_detected = bool(text_blocks and extracted_text.strip())
    extracted_fields = [
        field for field in expected if field in detect_fields(extracted_text, content)
    ]
    blank_pages = max(page_count - min(page_count, len(text_blocks)), 0)

    if not valid_header:
        issues.append(PdfReadabilityIssue("invalid_header", "文件不是有效的 PDF 文件。", "error"))
    if not has_eof:
        issues.append(PdfReadabilityIssue("missing_eof", "PDF 缺少结束标记，可能被截断。", "error"))
    if page_count == 0:
        issues.append(PdfReadabilityIssue("page_count_unknown", "无法识别 PDF 页数。", "error"))
    if not text_layer_detected:
        issues.append(
            PdfReadabilityIssue(
                code="text_layer_missing",
                message="未检测到可提取文本层，可能是扫描件或字体内容无法解析。",
                severity="warning",
            )
        )
        suggestions.append("对扫描件执行 OCR 后重新导出，并保留可搜索文本层。")
    if blank_pages:
        issues.append(
            PdfReadabilityIssue(
                code="blank_pages_possible",
                message=f"约有 {blank_pages} 页未检测到文本对象，请人工检查是否为空白页。",
                severity="warning",
            )
        )
        suggestions.append("删除空白页，或确认图片型页面是否需要 OCR。")

    missing_fields = [field for field in expected if field not in extracted_fields]
    if missing_fields:
        issues.append(
            PdfReadabilityIssue(
                code="key_fields_missing",
                message=f"未提取到关键字段：{'、'.join(missing_fields)}。",
                severity="warning",
            )
        )
        suggestions.append("检查关键字段是否被转成图片、乱码或不可复制的字体。")

    hard_failures = any(issue.severity == "error" for issue in issues)
    readable = bool(
        valid_header
        and has_eof
        and page_count > 0
        and text_layer_detected
        and not missing_fields
        and not hard_failures
    )
    return PdfReadabilityReport(
        filename=Path(filename).name,
        content_hash=f"sha256:{digest}" if digest else "",
        parser_name="stdlib_pdf_probe_v1",
        page_count=page_count,
        extractable_pages=max(page_count - blank_pages, 0) if text_layer_detected else 0,
        blank_pages=blank_pages,
        text_layer_detected=text_layer_detected,
        needs_ocr=not text_layer_detected,
        readable=readable,
        expected_fields=expected,
        extracted_fields=extracted_fields,
        issues=issues,
        suggestions=suggestions,
    )


def extract_literal_text(text_blocks: list[bytes]) -> str:
    parts: list[str] = []
    for block in text_blocks:
        for match in re.finditer(rb"\((.*?)\)\s*Tj", block, flags=re.S):
            value = match.group(1).replace(rb"\\(", b"(").replace(rb"\\)", b")")
            parts.append(value.decode("utf-8", errors="replace"))
        if not parts:
            parts.append(block.decode("utf-8", errors="replace"))
    return "\n".join(parts)


def detect_fields(text: str, raw_content: bytes) -> set[str]:
    normalized = f"{text}\n{raw_content.decode('latin-1', errors='ignore')}".lower()
    found = set()
    for field, aliases in FIELD_ALIASES.items():
        if any(alias.lower() in normalized for alias in aliases):
            found.add(field)
    return found
