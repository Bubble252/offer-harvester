from __future__ import annotations

import os
from typing import Callable, List, Optional, Protocol

from local_model_runtime import LocalRuntimeEndpoint, post_json
from models import RAGSearchHit

from rag.embeddings import PUBLIC_SOURCE_KINDS


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


class PrivacyAwareReranker:
    """Route reranking externally only when all candidates are public sources."""

    def __init__(
        self,
        *,
        local_reranker: Reranker | None = None,
        public_reranker: Reranker | None = None,
        allow_external_public: bool = False,
        public_source_kinds: frozenset[str] = PUBLIC_SOURCE_KINDS,
    ):
        self.local_reranker = local_reranker or NoopReranker()
        self.public_reranker = public_reranker
        self.allow_external_public = allow_external_public
        self.public_source_kinds = public_source_kinds
        self.name = (
            f"privacy-aware:{self.public_reranker.name}"
            if self.public_reranker
            else f"privacy-aware:{self.local_reranker.name}"
        )

    def rerank(self, query: str, hits: List[RAGSearchHit]) -> List[RAGSearchHit]:
        if (
            self.allow_external_public
            and self.public_reranker is not None
            and hits
            and all(hit.source_kind in self.public_source_kinds for hit in hits)
        ):
            return self.public_reranker.rerank(query, hits)
        ranked = self.local_reranker.rerank(query, hits)
        for hit in ranked:
            hit.retrieval_explanation = f"{hit.retrieval_explanation}; route=local_private_safe"
        return ranked


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
        extra_payload: Optional[dict] = None,
        request_fn: Optional[Callable[[str, dict], dict]] = None,
    ):
        self.runtime = LocalRuntimeEndpoint(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model_name = model_name
        self.path = path
        self.extra_payload = extra_payload or {}
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
        payload.update(self.extra_payload)
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
        extra_payload: Optional[dict] = None,
        request_fn: Optional[Callable[[str, dict], dict]] = None,
    ):
        super().__init__(
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            path=path,
            timeout=timeout,
            extra_payload=extra_payload,
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


def configured_reranker_from_env(env: Optional[dict[str, str]] = None) -> Reranker:
    """Build the configured reranker, falling back locally when optional API config is incomplete."""

    env = env or os.environ
    mode = (env.get("RAG_RERANKER") or "noop").strip().lower()
    if mode in {"", "noop", "none"}:
        return NoopReranker()
    if mode in {"lexical", "lexical-lite"}:
        return LexicalReranker()
    if mode == "siliconflow":
        api_key = env.get("SILICONFLOW_API_KEY", "").strip()
        model = env.get("SILICONFLOW_RERANK_MODEL", "BAAI/bge-reranker-v2-m3").strip()
        base_url = env.get("SILICONFLOW_RERANK_BASE_URL", "https://api.siliconflow.cn/v1").strip()
        if not api_key or not model or not base_url:
            return NoopReranker()
        extra_payload = {
            "return_documents": _env_bool(env.get("SILICONFLOW_RERANK_RETURN_DOCUMENTS"), False)
        }
        instruction = env.get("SILICONFLOW_RERANK_INSTRUCTION", "").strip()
        if instruction:
            extra_payload["instruction"] = instruction
        max_chunks = _env_int(env.get("SILICONFLOW_RERANK_MAX_CHUNKS_PER_DOC"))
        if max_chunks is not None:
            extra_payload["max_chunks_per_doc"] = max_chunks
        overlap = _env_int(env.get("SILICONFLOW_RERANK_OVERLAP_TOKENS"))
        if overlap is not None:
            extra_payload["overlap_tokens"] = overlap
        public_reranker = ApiReranker(
            base_url=base_url,
            model_name=model,
            api_key=api_key,
            path="/rerank",
            extra_payload=extra_payload,
        )
        return PrivacyAwareReranker(
            local_reranker=NoopReranker(),
            public_reranker=public_reranker,
            allow_external_public=True,
        )
    if mode == "api":
        api_key = env.get("RAG_RERANK_API_KEY", "").strip()
        model = env.get("RAG_RERANK_MODEL", "").strip()
        base_url = env.get("RAG_RERANK_BASE_URL", "").strip()
        path = env.get("RAG_RERANK_PATH", "/rerank").strip() or "/rerank"
        if not api_key or not model or not base_url:
            return NoopReranker()
        return ApiReranker(base_url=base_url, model_name=model, api_key=api_key, path=path)
    if mode == "local":
        model = env.get("LOCAL_RERANK_MODEL", "").strip()
        base_url = env.get("LOCAL_RERANK_BASE_URL", "").strip()
        path = env.get("LOCAL_RERANK_PATH", "/rerank").strip() or "/rerank"
        if not model or not base_url:
            return NoopReranker()
        return LocalOpenAICompatibleReranker(
            base_url=base_url,
            model_name=model,
            api_key=env.get("LOCAL_RERANK_API_KEY", ""),
            path=path,
        )
    return NoopReranker()


def _env_bool(value: Optional[str], default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(value: Optional[str]) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None
