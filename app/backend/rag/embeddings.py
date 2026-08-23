from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol

from rag.chunking import tokenize


class EmbeddingProvider(Protocol):
    """Small embedding contract shared by local and future API providers."""

    model_name: str
    model_version: str
    dimension: int

    def embed_texts(self, texts: List[str]) -> List[List[float]]: ...

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


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
