from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from models import RAGChunk, RAGSearchHit, StudentProfile
from storage import Workspace

from rag.chunking import tokenize
from rag.embeddings import EmbeddingProvider, HashEmbeddingProvider
from rag.evidence_graph import EvidenceBundle, LocalEvidenceGraphStore, build_evidence_bundle
from rag.index import KnowledgeBaseIndex
from rag.reranker import NoopReranker, Reranker


@dataclass
class RetrievalResult:
    query: str
    hits: List[RAGSearchHit]
    rebuilt: bool = False
    evidence_bundle: Optional[EvidenceBundle] = None


class KnowledgeBaseRetriever:
    def __init__(
        self,
        workspace: Workspace,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        reranker: Reranker | None = None,
    ):
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()
        self.index = KnowledgeBaseIndex(
            workspace,
            embedding_provider=self.embedding_provider,
        )
        self.reranker = reranker or NoopReranker()
        self.evidence_store = LocalEvidenceGraphStore(workspace)

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
        try:
            hits = rank_hybrid_chunks(
                query,
                filtered,
                vector_store=self.index.vector_store,
                embedding_provider=self.embedding_provider,
                reranker=self.reranker,
                limit=limit,
            )
        except (OSError, RuntimeError, ValueError):
            # A broken or missing vector adapter must never block evidence retrieval.
            hits = rank_chunks(query, filtered)[: max(limit, 0)]
        bundle = build_evidence_bundle(
            query,
            hits,
            query_plan={
                "retrieval": "hybrid",
                "source_kinds": source_kinds or [],
                "limit": limit,
                "include_unconfirmed": include_unconfirmed,
                "include_historical": include_historical,
                "as_of_year": as_of_year,
            },
        )
        self.evidence_store.save(bundle)
        return RetrievalResult(query=query, hits=hits, rebuilt=rebuilt, evidence_bundle=bundle)


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
            _make_hit(chunk, total, keyword_score=total, vector_score=0.0, query_terms=query_terms)
        )
    return sorted(hits, key=lambda hit: hit.score, reverse=True)


def rank_hybrid_chunks(
    query: str,
    chunks: Iterable[RAGChunk],
    *,
    vector_store,
    embedding_provider: EmbeddingProvider,
    reranker: Reranker,
    limit: int,
) -> List[RAGSearchHit]:
    chunks = list(chunks)
    if not chunks:
        return []
    keyword_hits = {hit.chunk_id: hit for hit in rank_chunks(query, chunks)}
    query_vector = embedding_provider.embed_query(query)
    vector_hits = {
        item.chunk_id: item for item in vector_store.search(query_vector, limit=max(limit * 8, 20))
    }
    if not vector_hits:
        return list(keyword_hits.values())[: max(limit, 0)]

    candidates = []
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    max_keyword = max((hit.score for hit in keyword_hits.values()), default=1.0)
    for chunk_id in set(keyword_hits) | set(vector_hits):
        chunk = chunk_by_id.get(chunk_id)
        if not chunk:
            continue
        keyword_score = keyword_hits.get(chunk_id).score if chunk_id in keyword_hits else 0.0
        vector_score = max(vector_hits.get(chunk_id).score, 0.0) if chunk_id in vector_hits else 0.0
        combined = 0.58 * (keyword_score / max_keyword) + 0.42 * max(vector_score, 0.0)
        if combined <= 0:
            continue
        hit = _make_hit(
            chunk,
            combined,
            keyword_score=keyword_score,
            vector_score=vector_score,
            query_terms=tokenize(query),
        )
        hit.retrieval_explanation = (
            f"keyword={keyword_score:.3f}; vector={vector_score:.3f}; reranker=pending"
        )
        candidates.append(hit)
    reranked = reranker.rerank(query, candidates)
    for hit in reranked:
        hit.score = round(hit.rerank_score or hit.score, 4)
        hit.confidence = round(min(1.0, hit.score), 4)
    return reranked[: max(limit, 0)]


def _make_hit(
    chunk: RAGChunk,
    total: float,
    *,
    keyword_score: float,
    vector_score: float,
    query_terms: List[str],
) -> RAGSearchHit:
    historical = bool(chunk.valid_for_year and chunk.valid_for_year < current_year())
    return RAGSearchHit(
        source_id=chunk.source_id,
        chunk_id=chunk.chunk_id,
        source_kind=chunk.source_kind,
        source_subtype=chunk.source_subtype,
        title=chunk.title,
        url=chunk.url,
        fetched_at=chunk.fetched_at,
        content_hash=chunk.content_hash,
        valid_for_year=chunk.valid_for_year,
        score=round(total, 4),
        keyword_score=round(keyword_score, 4),
        vector_score=round(vector_score, 4),
        rerank_score=round(total, 4),
        confidence=round(min(1.0, total / 6.0), 4),
        snippet=make_snippet(chunk.text, query_terms),
        evidence_ref=f"{chunk.source_id}#{chunk.chunk_id}",
        needs_confirmation=not chunk.confirmed,
        historical=historical,
        metadata=chunk.metadata,
    )


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
