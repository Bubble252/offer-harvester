from __future__ import annotations

from typing import List, Protocol

from models import RAGSearchHit


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: List[RAGSearchHit]) -> List[RAGSearchHit]: ...


class NoopReranker:
    """Explicit placeholder for a future cross-encoder or API reranker."""

    name = "noop"

    def rerank(self, query: str, hits: List[RAGSearchHit]) -> List[RAGSearchHit]:
        for hit in hits:
            hit.rerank_score = hit.score
        return sorted(hits, key=lambda hit: hit.rerank_score, reverse=True)


class LexicalReranker:
    """Explainable local reranker that rewards exact query phrase overlap."""

    name = "lexical-lite"

    def rerank(self, query: str, hits: List[RAGSearchHit]) -> List[RAGSearchHit]:
        phrases = [item.strip().lower() for item in query.split() if item.strip()]
        for hit in hits:
            exact_bonus = sum(0.03 for phrase in phrases if phrase in hit.snippet.lower())
            hit.rerank_score = round(hit.score + min(exact_bonus, 0.15), 6)
            hit.retrieval_explanation = (
                f"keyword={hit.keyword_score:.3f}; "
                f"vector={hit.vector_score:.3f}; "
                f"reranker={self.name}"
            )
        return sorted(hits, key=lambda hit: hit.rerank_score, reverse=True)
