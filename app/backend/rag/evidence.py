from __future__ import annotations

from typing import Iterable, List

from models import RAGSearchHit


def evidence_refs(hits: Iterable[RAGSearchHit]) -> List[str]:
    return [hit.evidence_ref for hit in hits if hit.evidence_ref]


def format_evidence_bullets(hits: Iterable[RAGSearchHit]) -> List[str]:
    bullets = []
    for hit in hits:
        source = hit.title or hit.source_id
        location = f"（{hit.url}）" if hit.url else ""
        bullets.append(f"{source}{location}: {hit.snippet}")
    return bullets
