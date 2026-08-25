"""Supabase/Postgres public-KB sync adapter.

Only public admissions records are eligible.  The adapter defaults to dry-run
when no connection string is configured and never accepts private workspace
collections as input.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from public_kb import (
    PublicKBChunk,
    PublicKBRecord,
    PublicKBSource,
    PublicKBStore,
    iter_public_records,
)

SUPABASE_SCHEMA_SQL = """create extension if not exists vector;

create table if not exists public.public_kb_sources (
  source_id text primary key,
  source_kind text not null,
  title text not null default '',
  url text not null default '',
  publisher text not null default '',
  authority_level text not null default 'unknown',
  published_at timestamptz null,
  fetched_at timestamptz not null,
  valid_for_year integer null,
  content_hash text not null default '',
  robots_status text not null default 'unknown',
  tos_status text not null default 'unknown',
  privacy_scope text not null default 'public',
  audit_status text not null default 'pending',
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.public_kb_records (
  record_id text primary key,
  record_kind text not null,
  university_id text not null default '',
  college_id text not null default '',
  name text not null default '',
  aliases jsonb not null default '[]'::jsonb,
  summary text not null default '',
  structured_facts jsonb not null default '{}'::jsonb,
  source_refs jsonb not null default '[]'::jsonb,
  valid_for_year integer null,
  status text not null default 'candidate',
  audit_status text not null default 'pending',
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.public_kb_chunks (
  chunk_id text primary key,
  record_id text not null references public.public_kb_records(record_id),
  source_id text not null references public.public_kb_sources(source_id),
  title text not null default '',
  text text not null,
  url text not null default '',
  content_hash text not null default '',
  valid_for_year integer null,
  authority_level text not null default 'unknown',
  audit_status text not null default 'pending',
  embedding_route text not null default 'none',
  embedding_model text not null default '',
  embedding vector null,
  metadata jsonb not null default '{}'::jsonb
);
"""


@dataclass
class SyncResult:
    mode: str
    source_count: int = 0
    record_count: int = 0
    chunk_count: int = 0
    uploaded: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class SupabasePublicKBSync:
    def __init__(self, database_url: Optional[str] = None, *, dry_run: Optional[bool] = None):
        self.database_url = database_url or os.environ.get("PUBLIC_KB_DATABASE_URL", "").strip()
        self.dry_run = (not self.database_url) if dry_run is None else dry_run

    @property
    def mode(self) -> str:
        return "dry-run" if self.dry_run else "postgres"

    def schema_sql(self) -> str:
        return SUPABASE_SCHEMA_SQL

    def schema_statements(self) -> List[str]:
        return _split_sql_statements(SUPABASE_SCHEMA_SQL)

    def data_sql(self, store: PublicKBStore) -> str:
        report = store.validate()
        if not report.valid:
            errors = "; ".join(issue.message for issue in report.issues if issue.level == "error")
            raise ValueError(f"Public KB is invalid: {errors}")
        sources = store.sources()
        records = list(iter_public_records(store))
        record_ids = {record.record_id for record in records}
        chunks = [chunk for chunk in store.chunks() if chunk.record_id in record_ids]
        lines = [SUPABASE_SCHEMA_SQL.rstrip(), ""]
        lines.extend(_source_insert_sql(source) for source in sources)
        lines.extend(_record_insert_sql(record) for record in records)
        lines.extend(_chunk_insert_sql(chunk) for chunk in chunks)
        return "\n".join(lines) + "\n"

    def write_data_sql(self, store: PublicKBStore, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.data_sql(store), encoding="utf-8")
        return path

    def sync(self, store: PublicKBStore) -> SyncResult:
        report = store.validate()
        if not report.valid:
            return SyncResult(
                mode=self.mode,
                source_count=report.source_count,
                record_count=report.record_count,
                chunk_count=report.chunk_count,
                errors=[issue.message for issue in report.issues if issue.level == "error"],
            )
        sources = store.sources()
        records = list(iter_public_records(store))
        chunks = [
            chunk for chunk in store.chunks() if chunk.record_id in {r.record_id for r in records}
        ]
        if self.dry_run:
            return SyncResult(
                mode="dry-run",
                source_count=len(sources),
                record_count=len(records),
                chunk_count=len(chunks),
                skipped=len(records) + len(chunks),
            )
        return self._sync_postgres(sources, records, chunks)

    def _sync_postgres(
        self,
        sources: Iterable[PublicKBSource],
        records: Iterable[PublicKBRecord],
        chunks: Iterable[PublicKBChunk],
    ) -> SyncResult:
        try:
            import psycopg
        except ImportError as exc:
            return SyncResult(mode="postgres", errors=[f"psycopg is required for live sync: {exc}"])
        sources = list(sources)
        records = list(records)
        chunks = list(chunks)
        try:
            with psycopg.connect(self.database_url) as connection:
                with connection.cursor() as cursor:
                    for statement in self.schema_statements():
                        cursor.execute(statement)
                    for source in sources:
                        cursor.execute(
                            """insert into public.public_kb_sources
                            (source_id, source_kind, title, url, publisher, authority_level,
                             published_at, fetched_at, valid_for_year, content_hash,
                             robots_status, tos_status, privacy_scope, audit_status, metadata)
                            values (%s,%s,%s,%s,%s,%s,nullif(%s,'')::timestamptz,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                            on conflict (source_id) do update set title=excluded.title,
                              fetched_at=excluded.fetched_at, content_hash=excluded.content_hash,
                              audit_status=excluded.audit_status, metadata=excluded.metadata""",
                            _source_params(source),
                        )
                    for record in records:
                        cursor.execute(
                            """insert into public.public_kb_records
                            (record_id, record_kind, university_id, college_id, name, aliases,
                             summary, structured_facts, source_refs, valid_for_year, status,
                             audit_status, created_at, updated_at)
                            values (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                            on conflict (record_id) do update set summary=excluded.summary,
                              structured_facts=excluded.structured_facts, status=excluded.status,
                              audit_status=excluded.audit_status, updated_at=excluded.updated_at""",
                            _record_params(record),
                        )
                    for chunk in chunks:
                        cursor.execute(
                            """insert into public.public_kb_chunks
                            (chunk_id, record_id, source_id, title, text, url, content_hash,
                             valid_for_year, authority_level, audit_status, embedding_route,
                             embedding_model, metadata)
                            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                            on conflict (chunk_id) do update set text=excluded.text,
                              content_hash=excluded.content_hash, metadata=excluded.metadata""",
                            _chunk_params(chunk),
                        )
            return SyncResult(
                "postgres", len(sources), len(records), len(chunks), len(records) + len(chunks)
            )
        except Exception as exc:  # pragma: no cover - exercised only with live credentials
            return SyncResult(
                "postgres", len(sources), len(records), len(chunks), errors=[str(exc)]
            )


def _dump(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _split_sql_statements(sql: str) -> List[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _source_params(source: PublicKBSource) -> Tuple[Any, ...]:
    return (
        source.source_id,
        source.source_kind,
        source.title,
        source.url,
        source.publisher,
        source.authority_level,
        source.published_at,
        source.fetched_at,
        source.valid_for_year,
        source.content_hash,
        source.robots_status,
        source.tos_status,
        source.privacy_scope,
        source.audit_status,
        _dump(source.metadata),
    )


def _record_params(record: PublicKBRecord) -> Tuple[Any, ...]:
    return (
        record.record_id,
        record.record_kind,
        record.university_id,
        record.college_id,
        record.name,
        _dump(record.aliases),
        record.summary,
        _dump(record.structured_facts),
        _dump(record.source_refs),
        record.valid_for_year,
        record.status,
        record.audit_status,
        record.created_at,
        record.updated_at,
    )


def _chunk_params(chunk: PublicKBChunk) -> Tuple[Any, ...]:
    return (
        chunk.chunk_id,
        chunk.record_id,
        chunk.source_id,
        chunk.title,
        chunk.text,
        chunk.url,
        chunk.content_hash,
        chunk.valid_for_year,
        chunk.authority_level,
        chunk.audit_status,
        chunk.embedding_route,
        chunk.embedding_model,
        _dump(chunk.metadata),
    )


def _source_insert_sql(source: PublicKBSource) -> str:
    values = [
        _sql_str(source.source_id),
        _sql_str(source.source_kind),
        _sql_str(source.title),
        _sql_str(source.url),
        _sql_str(source.publisher),
        _sql_str(source.authority_level),
        _sql_timestamp(source.published_at),
        _sql_timestamp(source.fetched_at),
        _sql_int(source.valid_for_year),
        _sql_str(source.content_hash),
        _sql_str(source.robots_status),
        _sql_str(source.tos_status),
        _sql_str(source.privacy_scope),
        _sql_str(source.audit_status),
        f"{_sql_str(_dump(source.metadata))}::jsonb",
    ]
    return (
        "insert into public.public_kb_sources "
        "(source_id, source_kind, title, url, publisher, authority_level, "
        "published_at, fetched_at, valid_for_year, content_hash, robots_status, "
        "tos_status, privacy_scope, audit_status, metadata) values "
        f"({', '.join(values)}) on conflict (source_id) do update set "
        "title=excluded.title, fetched_at=excluded.fetched_at, "
        "content_hash=excluded.content_hash, audit_status=excluded.audit_status, "
        "metadata=excluded.metadata;"
    )


def _record_insert_sql(record: PublicKBRecord) -> str:
    values = [
        _sql_str(record.record_id),
        _sql_str(record.record_kind),
        _sql_str(record.university_id),
        _sql_str(record.college_id),
        _sql_str(record.name),
        f"{_sql_str(_dump(record.aliases))}::jsonb",
        _sql_str(record.summary),
        f"{_sql_str(_dump(record.structured_facts))}::jsonb",
        f"{_sql_str(_dump(record.source_refs))}::jsonb",
        _sql_int(record.valid_for_year),
        _sql_str(record.status),
        _sql_str(record.audit_status),
        _sql_timestamp(record.created_at),
        _sql_timestamp(record.updated_at),
    ]
    return (
        "insert into public.public_kb_records "
        "(record_id, record_kind, university_id, college_id, name, aliases, "
        "summary, structured_facts, source_refs, valid_for_year, status, "
        "audit_status, created_at, updated_at) values "
        f"({', '.join(values)}) on conflict (record_id) do update set "
        "summary=excluded.summary, structured_facts=excluded.structured_facts, "
        "status=excluded.status, audit_status=excluded.audit_status, "
        "updated_at=excluded.updated_at;"
    )


def _chunk_insert_sql(chunk: PublicKBChunk) -> str:
    values = [
        _sql_str(chunk.chunk_id),
        _sql_str(chunk.record_id),
        _sql_str(chunk.source_id),
        _sql_str(chunk.title),
        _sql_str(chunk.text),
        _sql_str(chunk.url),
        _sql_str(chunk.content_hash),
        _sql_int(chunk.valid_for_year),
        _sql_str(chunk.authority_level),
        _sql_str(chunk.audit_status),
        _sql_str(chunk.embedding_route),
        _sql_str(chunk.embedding_model),
        f"{_sql_str(_dump(chunk.metadata))}::jsonb",
    ]
    return (
        "insert into public.public_kb_chunks "
        "(chunk_id, record_id, source_id, title, text, url, content_hash, "
        "valid_for_year, authority_level, audit_status, embedding_route, "
        "embedding_model, metadata) values "
        f"({', '.join(values)}) on conflict (chunk_id) do update set "
        "text=excluded.text, content_hash=excluded.content_hash, metadata=excluded.metadata;"
    )


def _sql_str(value: Any) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def _sql_timestamp(value: str) -> str:
    return "null" if not value else f"{_sql_str(value)}::timestamptz"


def _sql_int(value: Optional[int]) -> str:
    return "null" if value is None else str(int(value))
