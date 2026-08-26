from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, List, Optional

from models import (
    OcrExtractionReport,
    PdfReadabilityIssue,
    ProfileExpansionCandidate,
    StudentProfile,
)
from services import normalize_text
from storage import Workspace
from strategy import dedupe_candidates, parse_candidate_fields


class PaddleOcrAdapter:
    """Optional local OCR adapter.

    The dependency is intentionally loaded lazily so the default application
    remains installable without PaddlePaddle or GPU packages.
    """

    name = "paddleocr-optional"

    def __init__(self, engine: Any | None = None):
        self._engine = engine

    def available(self) -> bool:
        if self._engine is not None:
            return True
        try:
            import paddleocr  # noqa: F401
        except Exception:
            return False
        return True

    def extract_text(self, path: Path) -> str:
        engine = self._engine or self._make_engine()
        result = engine.ocr(str(path), cls=True)
        return normalize_text("\n".join(_iter_paddle_text(result)))

    def _make_engine(self):
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise RuntimeError("PaddleOCR is not installed") from exc
        return PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)


def build_ocr_extraction_report(
    workspace: Workspace,
    content: bytes,
    filename: str,
    *,
    expected_fields: Optional[List[str]] = None,
    material_id: str = "",
    manual_text: str = "",
    profile: Optional[StudentProfile] = None,
    adapter: Optional[PaddleOcrAdapter] = None,
) -> OcrExtractionReport:
    expected = [item.strip().lower() for item in (expected_fields or []) if item.strip()]
    adapter = adapter or PaddleOcrAdapter()
    issues: list[PdfReadabilityIssue] = []
    suggestions: list[str] = []
    document = workspace.save_user_document(
        content,
        filename or "ocr_source",
        category=_category_for_filename(filename),
        source_type="local_upload",
        trusted=True,
        confirmed=False,
        notes="OCR 预检原始文件；抽取结果只作为候选字段，需用户确认后才能写入 profile。",
    )

    extracted_text = normalize_text(manual_text)
    adapter_status = "manual_text" if extracted_text else "unavailable"
    available = bool(extracted_text)
    if not extracted_text:
        source_path = workspace.root / document.path
        if adapter.available():
            try:
                extracted_text = adapter.extract_text(source_path)
                adapter_status = "available"
                available = True
            except (OSError, RuntimeError, ValueError) as exc:
                adapter_status = "failed"
                issues.append(
                    PdfReadabilityIssue(
                        code="ocr_adapter_failed",
                        message=f"OCR 适配器执行失败：{exc}",
                        severity="warning",
                    )
                )
        else:
            issues.append(
                PdfReadabilityIssue(
                    code="ocr_adapter_unavailable",
                    message="未检测到 PaddleOCR；请安装可选依赖或粘贴 OCR 后文本。",
                    severity="info",
                )
            )

    if not extracted_text:
        suggestions.append("先粘贴 OCR 后文本，或在本地环境安装 PaddleOCR 后重试。")
    candidates = _candidate_fields_from_ocr(
        extracted_text,
        profile=profile,
        source_ref=document.document_id,
    )
    if expected:
        found = {candidate.field_name for candidate in candidates}
        missing = [field for field in expected if field not in found]
        if missing:
            issues.append(
                PdfReadabilityIssue(
                    code="ocr_expected_fields_missing",
                    message=f"OCR 文本未识别到关键候选字段：{'、'.join(missing)}。",
                    severity="warning",
                )
            )
            suggestions.append("检查扫描件清晰度、旋转方向和关键字段是否被遮挡。")

    report = OcrExtractionReport(
        filename=Path(filename or "ocr_source").name,
        material_id=material_id,
        source_document_id=document.document_id,
        profile_id=profile.profile_id if profile else "",
        adapter_name=adapter.name,
        adapter_status=adapter_status,
        available=available,
        extracted_text=extracted_text,
        text_hash=f"sha256:{hashlib.sha256(extracted_text.encode('utf-8')).hexdigest()}"
        if extracted_text
        else "",
        expected_fields=expected,
        candidate_count=len(candidates),
        candidate_fields=[_dump(candidate) for candidate in candidates],
        issues=issues,
        suggestions=suggestions,
    )
    workspace.write("ocr_extraction_reports", _dump(report), "report_id")
    if candidates:
        expansion = _profile_expansion_report_from_ocr(report, candidates)
        workspace.write("profile_expansion_candidates", _dump(expansion), "report_id")
    return report


def _candidate_fields_from_ocr(
    text: str,
    *,
    profile: Optional[StudentProfile],
    source_ref: str,
) -> List[ProfileExpansionCandidate]:
    if not text.strip():
        return []
    existing = {
        "research_interests": set(profile.research_interests) if profile else set(),
        "skills": set(profile.skills) if profile else set(),
        "projects": set(profile.projects) if profile else set(),
        "publications": set(profile.publications) if profile else set(),
        "competitions": set(profile.competitions) if profile else set(),
    }
    scalar_existing = {
        "name": "" if not profile or profile.name == "未命名学生" else profile.name,
        "education": profile.education if profile else "",
        "gpa": profile.gpa if profile else "",
        "rank": profile.rank if profile else "",
    }
    candidates: list[ProfileExpansionCandidate] = []
    for field_name, value in _parse_scalar_candidates(text).items():
        if value == scalar_existing.get(field_name, ""):
            continue
        candidates.append(
            ProfileExpansionCandidate(
                profile_id=profile.profile_id if profile else "",
                field_name=field_name,
                value=value,
                source_type="ocr_candidate",
                source_ref=source_ref,
                inference_method="ocr_pattern_extract",
                confidence=0.66,
                status="unconfirmed",
                inferred=False,
                evidence_refs=[source_ref],
                notes="OCR 标量字段候选必须由用户确认后才能写入 StudentProfile。",
            )
        )
    for field_name, values in parse_candidate_fields(text).items():
        for value in values:
            if value in existing.get(field_name, set()):
                continue
            inferred = field_name in {"skills", "research_interests"}
            candidates.append(
                ProfileExpansionCandidate(
                    profile_id=profile.profile_id if profile else "",
                    field_name=field_name,
                    value=value,
                    source_type="ocr_candidate",
                    source_ref=source_ref,
                    inference_method="ocr_keyword_extract" if inferred else "ocr_line_extract",
                    confidence=0.48 if inferred else 0.62,
                    status="unconfirmed",
                    inferred=inferred,
                    evidence_refs=[source_ref],
                    notes="OCR 候选字段可能有识别错误，必须由用户确认后才能写入 StudentProfile。",
                )
            )
    return dedupe_candidates(candidates)


def _parse_scalar_candidates(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    patterns = {
        "name": [r"(?:姓名|Name)[:：\s]+([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z·.\s]{1,24})"],
        "education": [
            r"(?:学校|院校|本科院校|University|School)[:：\s]+([\u4e00-\u9fffA-Za-z0-9（）()·.\s]{2,60})"
        ],
        "gpa": [
            r"(?:GPA|绩点|平均学分绩点)[:：\s]*([0-9](?:\.\d{1,3})?\s*/\s*[0-9](?:\.\d{1,3})?)",
            r"(?:GPA|绩点|平均学分绩点)[:：\s]*([0-9](?:\.\d{1,3})?)",
        ],
        "rank": [
            r"(?:排名|Rank)[:：\s]*(前\s*\d+(?:\.\d+)?\s*%|\d+\s*/\s*\d+)",
            r"(?:专业前|年级前)\s*(\d+(?:\.\d+)?\s*%)",
        ],
    }
    for field_name, field_patterns in patterns.items():
        for pattern in field_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                result[field_name] = re.sub(r"\s+", " ", match.group(1)).strip(" ：:")
                break
    return result


def _profile_expansion_report_from_ocr(
    report: OcrExtractionReport,
    candidates: Iterable[ProfileExpansionCandidate],
):
    from models import ProfileExpansionReport

    items = list(candidates)
    return ProfileExpansionReport(
        profile_id=report.profile_id,
        candidate_count=len(items),
        candidates=items,
        blocked_rules=[
            "OCR 输出只作为候选字段，不自动覆盖正式 StudentProfile",
            "扫描件识别可能存在错字、漏字和字段串位，必须人工确认",
            "用户确认前，材料生成必须把这些事实视为 unconfirmed",
        ],
        summary=f"OCR 预检识别到 {len(items)} 个画像扩展候选，均需人工确认。",
    )


def _category_for_filename(filename: str) -> str:
    lower = (filename or "").lower()
    if "transcript" in lower or "成绩" in lower:
        return "transcripts"
    if "award" in lower or "证书" in lower:
        return "awards"
    if "resume" in lower or "简历" in lower:
        return "resumes"
    return "manual_inputs"


def _iter_paddle_text(result: Any) -> Iterable[str]:
    if not result:
        return []
    parts: list[str] = []

    def visit(value: Any) -> None:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[1], (list, tuple))
            and value[1]
            and isinstance(value[1][0], str)
        ):
            parts.append(value[1][0])
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(result)
    return parts


def _dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()
