from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from models import RAGChunk, RAGSearchHit, StudentProfile
from storage import Workspace

from rag.chunking import tokenize
from rag.index import KnowledgeBaseIndex


@dataclass
class RetrievalResult:
    query: str
    hits: List[RAGSearchHit]
    rebuilt: bool = False


class KnowledgeBaseRetriever:
    def __init__(self, workspace: Workspace):
        self.index = KnowledgeBaseIndex(workspace)

    def search(
        self,
        query: str,
        *,
        source_kinds: Optional[List[str]] = None,
        limit: int = 5,
        include_unconfirmed: bool = True,
        include_historical: bool = False,
        as_of_year: Optional[int] = None,
        profile: Optional[StudentProfile] = None,
        auto_rebuild: bool = True,
    ) -> RetrievalResult:
        query = query.strip()
        if not query:
            return RetrievalResult(query=query, hits=[])

        chunks = self.index.load_chunks()
        rebuilt = False
        if not chunks and auto_rebuild:
            self.index.rebuild()
            chunks = self.index.load_chunks()
            rebuilt = True

        filtered = [
            chunk
            for chunk in chunks
            if (not source_kinds or chunk.source_kind in source_kinds)
            and (include_unconfirmed or chunk.confirmed or chunk.trusted)
            and _is_relevant_year(
                chunk,
                as_of_year=as_of_year,
                include_historical=include_historical,
            )
            and not _is_rejected_student_chunk(chunk, profile)
        ]
        hits = rank_chunks(query, filtered)[: max(limit, 0)]
        return RetrievalResult(query=query, hits=hits, rebuilt=rebuilt)


def rank_chunks(query: str, chunks: Iterable[RAGChunk]) -> List[RAGSearchHit]:
    query_terms = tokenize(query)
    if not query_terms:
        return []
    chunks = list(chunks)
    if not chunks:
        return []

    doc_terms = [tokenize(chunk.text) for chunk in chunks]
    document_frequency = Counter()
    for terms in doc_terms:
        document_frequency.update(set(terms))

    avg_len = sum(len(terms) for terms in doc_terms) / max(len(doc_terms), 1)
    hits: List[RAGSearchHit] = []
    for chunk, terms in zip(chunks, doc_terms):
        score = bm25_score(query_terms, terms, document_frequency, len(chunks), avg_len)
        phrase_bonus = phrase_overlap_bonus(query, chunk.text)
        trust_bonus = 0.08 if chunk.trusted else 0.0
        confirm_bonus = 0.08 if chunk.confirmed else 0.0
        historical = bool(chunk.valid_for_year and chunk.valid_for_year < current_year())
        historical_penalty = 0.4 if historical else 0.0
        total = score + phrase_bonus + trust_bonus + confirm_bonus
        total -= historical_penalty
        if total <= 0:
            continue
        hits.append(
            RAGSearchHit(
                source_id=chunk.source_id,
                chunk_id=chunk.chunk_id,
                source_kind=chunk.source_kind,
                source_subtype=chunk.source_subtype,
                title=chunk.title,
                url=chunk.url,
                fetched_at=chunk.fetched_at,
                valid_for_year=chunk.valid_for_year,
                score=round(total, 4),
                confidence=round(min(1.0, total / 6.0), 4),
                snippet=make_snippet(chunk.text, query_terms),
                evidence_ref=f"{chunk.source_id}#{chunk.chunk_id}",
                needs_confirmation=not chunk.confirmed,
                historical=historical,
                metadata=chunk.metadata,
            )
        )
    return sorted(hits, key=lambda hit: hit.score, reverse=True)


def _is_relevant_year(
    chunk: RAGChunk,
    *,
    as_of_year: Optional[int],
    include_historical: bool,
) -> bool:
    year = chunk.valid_for_year
    if year is None:
        return True
    compare_year = as_of_year or current_year()
    if year < compare_year and not include_historical:
        return False
    return True


def _is_rejected_student_chunk(chunk: RAGChunk, profile: Optional[StudentProfile]) -> bool:
    if not profile or chunk.source_kind != "student_document":
        return False
    rejected_fields = {
        field
        for field, status in profile.confirmation_map.items()
        if status == "rejected" and profile.evidence_map.get(field)
    }
    if not rejected_fields:
        return False
    blocked_source_ids = {
        source_id for field in rejected_fields for source_id in profile.evidence_map.get(field, [])
    }
    return chunk.source_id in blocked_source_ids


def current_year() -> int:
    return datetime.now().year


def bm25_score(
    query_terms: List[str],
    terms: List[str],
    document_frequency: Counter,
    document_count: int,
    avg_len: float,
) -> float:
    counts = Counter(terms)
    length = len(terms) or 1
    k1 = 1.5
    b = 0.75
    score = 0.0
    for term in query_terms:
        tf = counts.get(term, 0)
        if not tf:
            continue
        df = document_frequency.get(term, 0)
        idf = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
        denom = tf + k1 * (1 - b + b * length / max(avg_len, 1.0))
        score += idf * (tf * (k1 + 1)) / denom
    return score


def phrase_overlap_bonus(query: str, text: str) -> float:
    bonus = 0.0
    for phrase in split_query_phrases(query):
        if len(phrase) >= 2 and phrase in text:
            bonus += min(0.5, len(phrase) / 20)
    return bonus


def split_query_phrases(query: str) -> List[str]:
    return [
        item.strip() for item in query.replace("，", " ").replace("、", " ").split() if item.strip()
    ]


def make_snippet(text: str, query_terms: List[str], *, width: int = 180) -> str:
    if len(text) <= width:
        return text
    lowered = text.lower()
    positions = [lowered.find(term) for term in query_terms if lowered.find(term) >= 0]
    start = max(min(positions) - 40, 0) if positions else 0
    snippet = text[start : start + width].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if start + width < len(text):
        snippet = f"{snippet}..."
    return snippet
