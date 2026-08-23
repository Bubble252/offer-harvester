from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Optional

from models import KnowledgeBaseSource, RAGChunk

CHUNK_RULES = {
    "resumes": ("resume", 360, 560),
    "manual_inputs": ("resume", 360, 560),
    "transcripts": ("transcript", 720, 1200),
    "research_projects": ("project", 420, 680),
    "publications": ("paper", 420, 680),
    "personal_statements": ("statement", 460, 760),
    "advisor_homepage": ("advisor_page", 500, 820),
    "lab_homepage": ("advisor_page", 500, 820),
    "publication_page": ("advisor_page", 500, 820),
    "school_profile": ("advisor_page", 500, 820),
    "admission_notice": ("policy", 380, 620),
    "policy": ("policy", 380, 620),
    "deadline": ("policy", 320, 520),
    "material_requirements": ("policy", 380, 620),
    "web_url": ("web", 460, 760),
}


def normalize_text(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_source(
    source: KnowledgeBaseSource,
    *,
    target_chars: int = 480,
    max_chars: int = 760,
) -> List[RAGChunk]:
    text = normalize_text(source.cleaned_text or source.raw_text)
    if not text:
        return []

    chunk_rule, target_chars, max_chars = chunk_budget_for_source(
        source, target_chars=target_chars, max_chars=max_chars
    )
    blocks = split_blocks_for_source(source, text)
    chunks: List[RAGChunk] = []
    section_path: List[str] = []
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
        body = normalize_text("\n".join(buffer))
        buffer = []
        if not body:
            return
        for piece in split_long_text(body, max_chars=max_chars):
            chunks.append(make_chunk(source, piece, section_path, chunk_rule=chunk_rule))

    for block in blocks:
        heading = parse_heading(block)
        if heading:
            flush()
            section_path = section_path_for_heading(section_path, heading)
            continue
        if sum(len(item) for item in buffer) + len(block) > target_chars and buffer:
            flush()
        buffer.append(block)
    flush()
    return chunks


def chunk_budget_for_source(
    source: KnowledgeBaseSource,
    *,
    target_chars: int,
    max_chars: int,
) -> tuple[str, int, int]:
    subtype = (source.source_subtype or source.source_kind or "").strip().lower()
    return CHUNK_RULES.get(subtype, ("generic", target_chars, max_chars))


def split_blocks_for_source(source: KnowledgeBaseSource, text: str) -> List[str]:
    subtype = (source.source_subtype or source.source_kind or "").strip().lower()
    if subtype == "transcripts":
        return split_transcript_blocks(text)
    if subtype in {
        "resumes",
        "manual_inputs",
        "research_projects",
        "publications",
        "personal_statements",
    }:
        return split_resume_blocks(text)
    if source.source_kind == "policy" or subtype in {
        "policy",
        "admission_notice",
        "deadline",
        "material_requirements",
    }:
        return split_policy_blocks(text)
    return split_blocks(text)


def split_resume_blocks(text: str) -> List[str]:
    return split_blocks(text)


def split_transcript_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if parse_heading(clean):
            if current:
                blocks.append("\n".join(current))
                current = []
            blocks.append(clean)
            continue
        current.append(clean)
        if len(current) >= 8 or sum(len(item) for item in current) >= 320:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def split_policy_blocks(text: str) -> List[str]:
    blocks = split_blocks(text)
    merged: List[str] = []
    buffer: List[str] = []
    for block in blocks:
        if parse_heading(block):
            if buffer:
                merged.append("\n".join(buffer))
                buffer = []
            merged.append(block)
            continue
        buffer.append(block)
        if len("\n".join(buffer)) >= 420:
            merged.append("\n".join(buffer))
            buffer = []
    if buffer:
        merged.append("\n".join(buffer))
    return merged


def split_blocks(text: str) -> List[str]:
    raw_blocks = re.split(r"\n\s*\n", text)
    blocks: List[str] = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if len(lines) == 1:
            blocks.append(lines[0])
            continue
        current: List[str] = []
        for line in lines:
            if parse_heading(line):
                if current:
                    blocks.append("\n".join(current))
                    current = []
                blocks.append(line)
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current))
    return blocks


def parse_heading(block: str) -> Optional[str]:
    line = block.strip()
    if not line or "\n" in line:
        return None
    if line.startswith("#"):
        return line.lstrip("#").strip()
    if len(line) <= 36 and re.match(
        r"^((\d+|[一二三四五六七八九十]+)[.、．]|第[一二三四五六七八九十\d]+[章节部分]|[A-Z][.)])",
        line,
    ):
        return line
    if len(line) <= 24 and any(
        token in line for token in ["背景", "经历", "项目", "论文", "要求", "材料", "截止", "流程"]
    ):
        return line
    return None


def section_path_for_heading(current: List[str], heading: str) -> List[str]:
    heading = heading.strip()
    if not current:
        return [heading]
    if re.match(r"^(#|一[、.]|1[.、．]|第[一\d])", heading):
        return [heading]
    return (current[:1] + [heading])[-3:]


def split_long_text(text: str, *, max_chars: int) -> Iterable[str]:
    if len(text) <= max_chars:
        yield text
        return
    sentences = re.split(r"(?<=[。！？!?；;])", text)
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + len(sentence) > max_chars:
            yield current.strip()
            current = sentence
        else:
            current = f"{current}{sentence}" if current else sentence
    if current:
        yield current.strip()


def make_chunk(
    source: KnowledgeBaseSource,
    text: str,
    section_path: List[str],
    *,
    chunk_rule: str,
) -> RAGChunk:
    digest = hashlib.sha256(f"{source.source_id}\n{text}".encode("utf-8")).hexdigest()
    return RAGChunk(
        chunk_id=f"chunk_{digest[:16]}",
        source_id=source.source_id,
        source_kind=source.source_kind,
        source_subtype=source.source_subtype,
        title=source.title,
        section_path=section_path,
        text=text,
        token_count=len(tokenize(text)),
        url=source.url,
        fetched_at=source.fetched_at,
        content_hash=f"sha256:{digest}",
        trusted=source.trusted,
        confirmed=source.confirmed,
        valid_for_year=source.valid_for_year,
        metadata={
            "source_ref": source.source_ref,
            "notes": source.notes,
            "chunk_rule": chunk_rule,
        },
    )


def tokenize(text: str) -> List[str]:
    return [
        token.lower()
        for token in re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_+#.-]+", text or "")
        if token.strip()
    ]
