from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass
class VectorRecord:
    chunk_id: str
    source_id: str
    vector: List[float]
    text: str = ""
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


class TextSearchStore(Protocol):
    def search_text(self, query: str, *, limit: int = 20) -> List[VectorSearchResult]: ...


class JsonVectorStore:
    """A transparent local vector adapter; suitable for small workspaces."""

    backend_name = "json"

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

    def search_text(self, query: str, *, limit: int = 20) -> List[VectorSearchResult]:
        terms = [term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]+", query or "")]
        if not terms:
            return []
        results = []
        for record in self.records():
            haystack = record.text.lower()
            matched = sum(term in haystack for term in terms)
            if matched:
                results.append(
                    VectorSearchResult(
                        chunk_id=record.chunk_id,
                        source_id=record.source_id,
                        score=round(matched / len(terms), 6),
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


class SqliteVectorStore:
    """SQLite FTS5 text index plus a dependency-free local vector table."""

    backend_name = "sqlite"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def replace(self, records: Iterable[VectorRecord], *, index_version: str) -> None:
        items = list(records)
        with self._connect() as connection:
            connection.execute("DELETE FROM vectors")
            connection.execute("DELETE FROM chunks_fts")
            connection.executemany(
                """
                INSERT INTO vectors (
                    chunk_id, source_id, vector_json, text, content_hash,
                    model_name, model_version, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.chunk_id,
                        item.source_id,
                        json.dumps(item.vector, ensure_ascii=False),
                        item.text,
                        item.content_hash,
                        item.model_name,
                        item.model_version,
                        json.dumps(item.metadata, ensure_ascii=False, sort_keys=True),
                    )
                    for item in items
                ],
            )
            connection.executemany(
                """
                INSERT INTO chunks_fts (chunk_id, source_id, text)
                VALUES (?, ?, ?)
                """,
                [(item.chunk_id, item.source_id, item.text) for item in items],
            )
            connection.execute(
                """
                INSERT INTO index_meta (key, value) VALUES ('index_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (index_version,),
            )

    def records(self) -> List[VectorRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, source_id, vector_json, text, content_hash,
                       model_name, model_version, metadata_json
                FROM vectors ORDER BY rowid
                """
            ).fetchall()
        return [_record_from_row(row) for row in rows]

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
            results.append(
                VectorSearchResult(
                    chunk_id=record.chunk_id,
                    source_id=record.source_id,
                    score=round(cosine_similarity(query_vector, record.vector), 6),
                    metadata=record.metadata,
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[: max(limit, 0)]

    def search_text(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> List[VectorSearchResult]:
        match_query = _fts_query(query)
        if not match_query:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, source_id, bm25(chunks_fts) AS rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (match_query, max(limit, 0)),
            ).fetchall()
        results = [
            VectorSearchResult(
                chunk_id=row[0],
                source_id=row[1],
                score=round(1.0 / (1.0 + abs(float(row[2]))), 6),
            )
            for row in rows
        ]
        return results or _lexical_record_search(query, self.records(), limit=limit)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    chunk_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    text TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT '',
                    model_version TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    source_id UNINDEXED,
                    text
                );
                CREATE TABLE IF NOT EXISTS index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )


class ChromaVectorStore:
    """Optional Chroma adapter; the dependency is imported only when requested."""

    backend_name = "chroma"

    def __init__(self, collection):
        self.collection = collection

    @classmethod
    def from_path(cls, path: Path, *, collection_name: str = "grad_apply_chunks"):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "Chroma is optional; install chromadb only when this backend is enabled"
            ) from exc
        client = chromadb.PersistentClient(path=str(path))
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return cls(collection)

    def replace(self, records: Iterable[VectorRecord], *, index_version: str) -> None:
        items = list(records)
        existing = self.collection.get(include=[])
        existing_ids = existing.get("ids", []) if existing else []
        if existing_ids:
            self.collection.delete(ids=existing_ids)
        if not items:
            return
        self.collection.add(
            ids=[item.chunk_id for item in items],
            embeddings=[item.vector for item in items],
            documents=[item.text for item in items],
            metadatas=[_chroma_metadata(item, index_version) for item in items],
        )

    def search(
        self,
        query_vector: List[float],
        *,
        limit: int = 20,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        kwargs = {
            "query_embeddings": [query_vector],
            "n_results": max(limit, 0),
            "include": ["metadatas", "distances"],
        }
        if metadata_filter:
            kwargs["where"] = _chroma_filter(metadata_filter)
        result = self.collection.query(**kwargs)
        ids = _first_nested(result.get("ids", []))
        distances = _first_nested(result.get("distances", []))
        metadatas = _first_nested(result.get("metadatas", []))
        output = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = float(distances[index]) if index < len(distances) else 1.0
            output.append(
                VectorSearchResult(
                    chunk_id=str(chunk_id),
                    source_id=str(metadata.get("source_id", "")),
                    score=round(1.0 / (1.0 + max(distance, 0.0)), 6),
                    metadata=_restore_chroma_metadata(metadata),
                )
            )
        return output


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
        "text": record.text,
        "content_hash": record.content_hash,
        "model_name": record.model_name,
        "model_version": record.model_version,
        "metadata": record.metadata,
    }


def _record_from_row(row: sqlite3.Row) -> VectorRecord:
    return VectorRecord(
        chunk_id=row["chunk_id"],
        source_id=row["source_id"],
        vector=json.loads(row["vector_json"]),
        text=row["text"],
        content_hash=row["content_hash"],
        model_name=row["model_name"],
        model_version=row["model_version"],
        metadata=json.loads(row["metadata_json"]),
    )


def _lexical_record_search(
    query: str,
    records: List[VectorRecord],
    *,
    limit: int,
) -> List[VectorSearchResult]:
    terms = re.findall(r"[\w\u4e00-\u9fff]+", query or "")
    if not terms:
        return []
    results = []
    for record in records:
        matched = sum(term.lower() in record.text.lower() for term in terms)
        if matched:
            results.append(
                VectorSearchResult(
                    chunk_id=record.chunk_id,
                    source_id=record.source_id,
                    score=round(matched / len(terms), 6),
                    metadata=record.metadata,
                )
            )
    return sorted(results, key=lambda item: item.score, reverse=True)[: max(limit, 0)]


def _fts_query(query: str) -> str:
    terms = re.findall(r"[\w\u4e00-\u9fff]+", query or "")
    return " AND ".join('"' + term.replace('"', "") + '"' for term in terms)


def _chroma_metadata(record: VectorRecord, index_version: str) -> Dict[str, Any]:
    metadata = {
        "source_id": record.source_id,
        "content_hash": record.content_hash,
        "model_name": record.model_name,
        "model_version": record.model_version,
        "index_version": index_version,
        "_metadata_json": json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
    }
    for key, value in record.metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[key] = "" if value is None else value
        else:
            metadata[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return metadata


def _chroma_filter(filters: Dict[str, Any]) -> Dict[str, Any]:
    if len(filters) == 1:
        key, value = next(iter(filters.items()))
        if isinstance(value, list):
            return {key: {"$in": value}}
        return {key: {"$eq": value}}
    return {
        "$and": [
            {key: {"$in": value} if isinstance(value, list) else {"$eq": value}}
            for key, value in filters.items()
        ]
    }


def _restore_chroma_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    raw = metadata.pop("_metadata_json", "")
    if not raw:
        return metadata
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return metadata


def _first_nested(value):
    if not value:
        return []
    if isinstance(value[0], list):
        return value[0]
    return value
