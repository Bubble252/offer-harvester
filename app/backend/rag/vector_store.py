from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass
class VectorRecord:
    chunk_id: str
    source_id: str
    vector: List[float]
    content_hash: str = ""
    model_name: str = ""
    model_version: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    chunk_id: str
    source_id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    def replace(self, records: Iterable[VectorRecord], *, index_version: str) -> None: ...

    def search(
        self,
        query_vector: List[float],
        *,
        limit: int = 20,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]: ...


class JsonVectorStore:
    """A transparent local vector adapter; suitable for small workspaces."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def replace(self, records: Iterable[VectorRecord], *, index_version: str) -> None:
        items = list(records)
        lines = [json.dumps(_dump(record), ensure_ascii=False, sort_keys=True) for record in items]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        manifest_path = self.path.with_suffix(".manifest.json")
        manifest_path.write_text(
            json.dumps(
                {
                    "index_version": index_version,
                    "record_count": len(items),
                    "model_names": sorted({item.model_name for item in items if item.model_name}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def records(self) -> List[VectorRecord]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(VectorRecord(**json.loads(line)))
        return records

    def search(
        self,
        query_vector: List[float],
        *,
        limit: int = 20,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        results = []
        for record in self.records():
            if metadata_filter and not _matches(record, metadata_filter):
                continue
            score = cosine_similarity(query_vector, record.vector)
            results.append(
                VectorSearchResult(
                    chunk_id=record.chunk_id,
                    source_id=record.source_id,
                    score=round(score, 6),
                    metadata=record.metadata,
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[: max(limit, 0)]


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _matches(record: VectorRecord, filters: Dict[str, Any]) -> bool:
    values = {
        "chunk_id": record.chunk_id,
        "source_id": record.source_id,
        "content_hash": record.content_hash,
        "model_name": record.model_name,
        "model_version": record.model_version,
        **record.metadata,
    }
    return all(
        values.get(key) in value if isinstance(value, list) else values.get(key) == value
        for key, value in filters.items()
    )


def _dump(record: VectorRecord) -> Dict[str, Any]:
    return {
        "chunk_id": record.chunk_id,
        "source_id": record.source_id,
        "vector": record.vector,
        "content_hash": record.content_hash,
        "model_name": record.model_name,
        "model_version": record.model_version,
        "metadata": record.metadata,
    }
