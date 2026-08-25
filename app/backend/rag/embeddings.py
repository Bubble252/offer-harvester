from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol

from local_model_runtime import LocalRuntimeEndpoint, post_json

from rag.chunking import tokenize


class EmbeddingProvider(Protocol):
    """Small embedding contract shared by local and future API providers."""

    model_name: str
    model_version: str
    dimension: int

    def embed_texts(self, texts: List[str]) -> List[List[float]]: ...

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


PUBLIC_SOURCE_KINDS = frozenset({"advisor_source", "policy", "web_url", "public_web"})


@dataclass(frozen=True)
class EmbeddedVector:
    vector: List[float]
    model_name: str
    model_version: str
    dimension: int
    route: str


class PrivacyAwareEmbeddingProvider:
    """Route private data locally and public data to an explicitly enabled provider."""

    def __init__(
        self,
        *,
        local_provider: EmbeddingProvider | None = None,
        public_provider: EmbeddingProvider | None = None,
        allow_external_public: bool = False,
        public_source_kinds: frozenset[str] = PUBLIC_SOURCE_KINDS,
    ):
        self.local_provider = local_provider or HashEmbeddingProvider()
        self.public_provider = public_provider
        self.allow_external_public = allow_external_public
        self.public_source_kinds = public_source_kinds
        self.model_name = self.local_provider.model_name
        self.model_version = self.local_provider.model_version
        self.dimension = self.local_provider.dimension

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return self.local_provider.embed_texts(texts)

    def embed_query(self, query: str) -> List[float]:
        return self.local_provider.embed_query(query)

    def embed_texts_for_sources(
        self,
        texts: List[str],
        source_kinds: List[str],
    ) -> List[EmbeddedVector]:
        if len(texts) != len(source_kinds):
            raise ValueError("Embedding texts and source kinds must have equal lengths")
        routed: List[Optional[EmbeddedVector]] = [None] * len(texts)
        groups: dict[tuple[str, str], list[tuple[int, str, EmbeddingProvider]]] = {}
        for index, (text, source_kind) in enumerate(zip(texts, source_kinds)):
            provider, route = self._provider_for_source(source_kind)
            groups.setdefault((route, provider.model_name), []).append((index, text, provider))
        for (route, _), items in groups.items():
            provider = items[0][2]
            vectors = provider.embed_texts([text for _, text, _ in items])
            for (index, _, _), vector in zip(items, vectors):
                routed[index] = EmbeddedVector(
                    vector=vector,
                    model_name=provider.model_name,
                    model_version=provider.model_version,
                    dimension=provider.dimension,
                    route=route,
                )
        if any(item is None for item in routed):
            raise RuntimeError("Embedding router did not produce all vectors")
        return [item for item in routed if item is not None]

    def embed_query_for_sources(
        self,
        query: str,
        source_kinds: List[str],
        *,
        allow_external: bool = False,
    ) -> EmbeddedVector:
        provider, route = self._provider_for_query(source_kinds, allow_external=allow_external)
        return EmbeddedVector(
            vector=provider.embed_query(query),
            model_name=provider.model_name,
            model_version=provider.model_version,
            dimension=provider.dimension,
            route=route,
        )

    def _provider_for_source(self, source_kind: str) -> tuple[EmbeddingProvider, str]:
        if (
            self.allow_external_public
            and self.public_provider is not None
            and source_kind in self.public_source_kinds
        ):
            return self.public_provider, "external_public"
        return self.local_provider, "local"

    def _provider_for_query(
        self,
        source_kinds: List[str],
        *,
        allow_external: bool,
    ) -> tuple[EmbeddingProvider, str]:
        if (
            allow_external
            and source_kinds
            and all(kind in self.public_source_kinds for kind in source_kinds)
        ):
            return self._provider_for_source(source_kinds[0])
        return self.local_provider, "local"


@dataclass(frozen=True)
class HashEmbeddingProvider:
    """Deterministic, dependency-free embedding for local indexes and tests."""

    dimension: int = 64
    model_name: str = "hash-local"
    model_version: str = "v1"

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> List[float]:
        return self._embed(query)

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        terms = tokenize(text)
        if not terms:
            return vector
        for term in terms:
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [round(value / norm, 8) for value in vector] if norm else vector


class ApiEmbeddingProvider:
    """Adapter boundary for a future embedding API without adding an SDK now."""

    def __init__(
        self,
        *,
        model_name: str,
        model_version: str = "configured",
        dimension: int,
        embed_fn: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.dimension = dimension
        self._embed_fn = embed_fn

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self._embed_fn is None:
            raise RuntimeError(
                "ApiEmbeddingProvider requires an injected embed_fn; "
                "configure the provider at the application boundary"
            )
        vectors = self._embed_fn(texts)
        if len(vectors) != len(texts):
            raise ValueError("Embedding provider returned an unexpected batch size")
        if any(len(vector) != self.dimension for vector in vectors):
            raise ValueError("Embedding provider returned an unexpected vector dimension")
        return vectors

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


class OpenAICompatibleEmbeddingProvider:
    """Embedding provider for OpenAI-compatible local or remote HTTP services."""

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str = "",
        model_version: str = "configured",
        dimension: int | None = None,
        timeout: int = 30,
        request_fn: Optional[Callable[[str, dict], dict]] = None,
    ):
        self.runtime = LocalRuntimeEndpoint(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model_name = model_name
        self.model_version = model_version
        self.dimension = dimension or 0
        self._request_fn = request_fn

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        payload = {"model": self.model_name, "input": texts}
        endpoint = self.runtime.endpoint("/embeddings")
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
        vectors = _parse_openai_embedding_response(data, expected_count=len(texts))
        observed_dimension = len(vectors[0]) if vectors else 0
        if self.dimension and observed_dimension != self.dimension:
            raise ValueError("Embedding provider returned an unexpected vector dimension")
        if not self.dimension:
            self.dimension = observed_dimension
        return vectors

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


class LocalOpenAICompatibleEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    """Named adapter for local services such as Ollama, LM Studio, Xinference, or llama.cpp."""

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        api_key: str = "",
        model_version: str = "local-openai-compatible",
        dimension: int | None = None,
        timeout: int = 30,
        request_fn: Optional[Callable[[str, dict], dict]] = None,
    ):
        super().__init__(
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            model_version=model_version,
            dimension=dimension,
            timeout=timeout,
            request_fn=request_fn,
        )


def _parse_openai_embedding_response(
    data: dict,
    *,
    expected_count: int,
) -> List[List[float]]:
    items = data.get("data", [])
    if len(items) != expected_count:
        raise ValueError("Embedding provider returned an unexpected batch size")
    ordered = sorted(items, key=lambda item: item.get("index", 0))
    vectors = [item.get("embedding", []) for item in ordered]
    if any(not isinstance(vector, list) for vector in vectors):
        raise ValueError("Embedding provider returned invalid vectors")
    if not vectors:
        return []
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("Embedding provider returned inconsistent vector dimensions")
    return vectors
