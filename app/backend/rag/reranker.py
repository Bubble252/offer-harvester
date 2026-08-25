from __future__ import annotations

from typing import Callable, List, Optional, Protocol

from local_model_runtime import LocalRuntimeEndpoint, post_json
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


class ApiReranker:
    """HTTP reranker adapter for API or local services with a common rerank shape."""

    name = "api-reranker"

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str = "",
        path: str = "/rerank",
        timeout: int = 30,
        request_fn: Optional[Callable[[str, dict], dict]] = None,
    ):
        self.runtime = LocalRuntimeEndpoint(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model_name = model_name
        self.path = path
        self._request_fn = request_fn
        self.name = f"api-reranker:{model_name}"

    def rerank(self, query: str, hits: List[RAGSearchHit]) -> List[RAGSearchHit]:
        if not hits:
            return []
        documents = [hit.snippet for hit in hits]
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
        }
        endpoint = self.runtime.endpoint(self.path)
        data = (
            self._request_fn(endpoint, payload)
            if self._request_fn is not None
            else post_json(
                endpoint,
                payload,
                api_key=self.runtime.api_key,
                timeout=self.runtime.timeout,
            )
        )
        scores = _parse_rerank_scores(data, expected_count=len(hits))
        ranked = []
        for index, score in scores:
            hit = hits[index]
            hit.rerank_score = round(float(score), 6)
            hit.retrieval_explanation = (
                f"keyword={hit.keyword_score:.3f}; "
                f"vector={hit.vector_score:.3f}; "
                f"reranker={self.name}"
            )
            ranked.append(hit)
        return sorted(ranked, key=lambda hit: hit.rerank_score, reverse=True)


class LocalOpenAICompatibleReranker(ApiReranker):
    """Named adapter for local reranker services exposed over HTTP."""

    name = "local-openai-compatible-reranker"

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str = "",
        path: str = "/rerank",
        timeout: int = 30,
        request_fn: Optional[Callable[[str, dict], dict]] = None,
    ):
        super().__init__(
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            path=path,
            timeout=timeout,
            request_fn=request_fn,
        )
        self.name = f"local-reranker:{model_name}"


def _parse_rerank_scores(data: dict, *, expected_count: int) -> List[tuple[int, float]]:
    raw_results = data.get("results", data.get("data", []))
    if not isinstance(raw_results, list):
        raise ValueError("Reranker returned invalid results")
    scores = []
    seen = set()
    for position, item in enumerate(raw_results):
        if not isinstance(item, dict):
            raise ValueError("Reranker returned invalid result items")
        index = item.get("index", item.get("document_index", position))
        score = item.get("relevance_score", item.get("score"))
        if not isinstance(index, int) or index < 0 or index >= expected_count:
            raise ValueError("Reranker returned an invalid document index")
        if score is None:
            raise ValueError("Reranker returned a result without score")
        scores.append((index, float(score)))
        seen.add(index)
    for index in range(expected_count):
        if index not in seen:
            scores.append((index, 0.0))
    return scores
