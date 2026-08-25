"""Public admissions knowledge-base records and local workspace storage.

The public KB is deliberately separate from private student facts.  It stores
source metadata, structured admissions facts, and chunks that can be indexed by
the existing RAG pipeline.  It never treats an embedding as the source of
truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Type

from models import new_id, now_iso
from pydantic import BaseModel, Field

PublicRecordKind = Literal[
    "university",
    "college",
    "program",
    "advisor",
    "policy",
    "deadline",
    "faq",
]

AuthorityLevel = Literal[
    "university_official",
    "graduate_school_official",
    "college_official",
    "advisor_official",
    "admissions_platform",
    "manual_summary",
    "unofficial",
    "unknown",
]

AuditStatus = Literal["pending", "passed", "needs_review", "failed"]


class PublicKBSource(BaseModel):
    source_id: str = Field(default_factory=lambda: new_id("pubsrc"))
    source_kind: str = "public_web"
    title: str = ""
    url: str = ""
    publisher: str = ""
    authority_level: AuthorityLevel = "unknown"
    published_at: str = ""
    fetched_at: str = Field(default_factory=now_iso)
    valid_for_year: Optional[int] = None
    content_hash: str = ""
    robots_status: str = "unknown"
    tos_status: str = "unknown"
    privacy_scope: Literal["public"] = "public"
    audit_status: AuditStatus = "pending"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicKBRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: new_id("pubrec"))
    record_kind: PublicRecordKind
    university_id: str = ""
    college_id: str = ""
    name: str = ""
    aliases: List[str] = Field(default_factory=list)
    summary: str = ""
    structured_facts: Dict[str, Any] = Field(default_factory=dict)
    source_refs: List[str] = Field(default_factory=list)
    valid_for_year: Optional[int] = None
    status: Literal["candidate", "active", "superseded", "archived"] = "candidate"
    audit_status: AuditStatus = "pending"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class PublicKBChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: new_id("pubchunk"))
    record_id: str
    source_id: str
    title: str = ""
    text: str
    url: str = ""
    content_hash: str = ""
    valid_for_year: Optional[int] = None
    authority_level: AuthorityLevel = "unknown"
    audit_status: AuditStatus = "pending"
    embedding_route: Literal["local", "external_public", "none"] = "none"
    embedding_model: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicKBManifest(BaseModel):
    schema_version: str = "public-kb.v1"
    name: str = "PublicAdmissionsKnowledgeBase"
    scope: Literal["public_only"] = "public_only"
    target_groups: List[str] = Field(
        default_factory=lambda: ["all_985", "strong_211", "specialized_strong_universities"]
    )
    universities: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


PUBLIC_KB_TARGET_UNIVERSITIES: List[Dict[str, Any]] = [
    {
        "university_id": "pku",
        "name": "北京大学",
        "aliases": ["Peking University", "PKU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "tsinghua",
        "name": "清华大学",
        "aliases": ["Tsinghua University", "THU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "ruc",
        "name": "中国人民大学",
        "aliases": ["Renmin University of China", "RUC"],
        "groups": ["985"],
    },
    {
        "university_id": "buaa",
        "name": "北京航空航天大学",
        "aliases": ["Beihang University", "BUAA"],
        "groups": ["985"],
    },
    {"university_id": "bit", "name": "北京理工大学", "aliases": ["BIT"], "groups": ["985"]},
    {"university_id": "bnu", "name": "北京师范大学", "aliases": ["BNU"], "groups": ["985"]},
    {"university_id": "cau", "name": "中国农业大学", "aliases": ["CAU"], "groups": ["985"]},
    {"university_id": "muc", "name": "中央民族大学", "aliases": ["MUC"], "groups": ["985"]},
    {
        "university_id": "nankai",
        "name": "南开大学",
        "aliases": ["Nankai University"],
        "groups": ["985"],
    },
    {
        "university_id": "tju",
        "name": "天津大学",
        "aliases": ["Tianjin University", "TJU"],
        "groups": ["985"],
    },
    {
        "university_id": "dlut",
        "name": "大连理工大学",
        "aliases": ["DUT", "DLUT"],
        "groups": ["985"],
    },
    {
        "university_id": "neu",
        "name": "东北大学",
        "aliases": ["Northeastern University"],
        "groups": ["985"],
    },
    {
        "university_id": "jlu",
        "name": "吉林大学",
        "aliases": ["Jilin University", "JLU"],
        "groups": ["985"],
    },
    {"university_id": "hit", "name": "哈尔滨工业大学", "aliases": ["HIT"], "groups": ["985", "c9"]},
    {
        "university_id": "fudan",
        "name": "复旦大学",
        "aliases": ["Fudan University"],
        "groups": ["985", "c9"],
    },
    {"university_id": "sjtu", "name": "上海交通大学", "aliases": ["SJTU"], "groups": ["985", "c9"]},
    {
        "university_id": "tongji",
        "name": "同济大学",
        "aliases": ["Tongji University"],
        "groups": ["985"],
    },
    {"university_id": "ecnu", "name": "华东师范大学", "aliases": ["ECNU"], "groups": ["985"]},
    {
        "university_id": "nju",
        "name": "南京大学",
        "aliases": ["Nanjing University", "NJU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "seu",
        "name": "东南大学",
        "aliases": ["Southeast University", "SEU"],
        "groups": ["985"],
    },
    {
        "university_id": "zju",
        "name": "浙江大学",
        "aliases": ["Zhejiang University", "ZJU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "ustc",
        "name": "中国科学技术大学",
        "aliases": ["USTC"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "xmu",
        "name": "厦门大学",
        "aliases": ["Xiamen University", "XMU"],
        "groups": ["985"],
    },
    {
        "university_id": "sdu",
        "name": "山东大学",
        "aliases": ["Shandong University", "SDU"],
        "groups": ["985"],
    },
    {"university_id": "ouc", "name": "中国海洋大学", "aliases": ["OUC"], "groups": ["985"]},
    {
        "university_id": "whu",
        "name": "武汉大学",
        "aliases": ["Wuhan University", "WHU"],
        "groups": ["985"],
    },
    {"university_id": "hust", "name": "华中科技大学", "aliases": ["HUST"], "groups": ["985"]},
    {
        "university_id": "hnu",
        "name": "湖南大学",
        "aliases": ["Hunan University"],
        "groups": ["985"],
    },
    {
        "university_id": "csu",
        "name": "中南大学",
        "aliases": ["Central South University", "CSU"],
        "groups": ["985"],
    },
    {"university_id": "nudt", "name": "国防科技大学", "aliases": ["NUDT"], "groups": ["985"]},
    {
        "university_id": "sysu",
        "name": "中山大学",
        "aliases": ["Sun Yat-sen University", "SYSU"],
        "groups": ["985"],
    },
    {"university_id": "scut", "name": "华南理工大学", "aliases": ["SCUT"], "groups": ["985"]},
    {
        "university_id": "scu",
        "name": "四川大学",
        "aliases": ["Sichuan University", "SCU"],
        "groups": ["985"],
    },
    {"university_id": "uestc", "name": "电子科技大学", "aliases": ["UESTC"], "groups": ["985"]},
    {
        "university_id": "cqu",
        "name": "重庆大学",
        "aliases": ["Chongqing University", "CQU"],
        "groups": ["985"],
    },
    {
        "university_id": "xjtu",
        "name": "西安交通大学",
        "aliases": ["Xi'an Jiaotong University", "XJTU"],
        "groups": ["985", "c9"],
    },
    {
        "university_id": "nwpu",
        "name": "西北工业大学",
        "aliases": ["NPU", "NWPU"],
        "groups": ["985"],
    },
    {
        "university_id": "lzu",
        "name": "兰州大学",
        "aliases": ["Lanzhou University", "LZU"],
        "groups": ["985"],
    },
    {"university_id": "nwafu", "name": "西北农林科技大学", "aliases": ["NWAFU"], "groups": ["985"]},
    {
        "university_id": "bupt",
        "name": "北京邮电大学",
        "aliases": ["BUPT"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "nuaa",
        "name": "南京航空航天大学",
        "aliases": ["NUAA"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "njust",
        "name": "南京理工大学",
        "aliases": ["NJUST"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "xidian",
        "name": "西安电子科技大学",
        "aliases": ["Xidian University"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "bjut",
        "name": "北京工业大学",
        "aliases": ["BJUT"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "bjtu",
        "name": "北京交通大学",
        "aliases": ["BJTU"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "ustb",
        "name": "北京科技大学",
        "aliases": ["USTB"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "cup",
        "name": "中国石油大学",
        "aliases": ["China University of Petroleum"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cugb",
        "name": "中国地质大学",
        "aliases": ["China University of Geosciences"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cumt",
        "name": "中国矿业大学",
        "aliases": ["China University of Mining and Technology"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cufe",
        "name": "中央财经大学",
        "aliases": ["CUFE"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "suibe",
        "name": "上海对外经贸大学",
        "aliases": ["SUIBE"],
        "groups": ["specialized_strong"],
    },
    {
        "university_id": "uibe",
        "name": "对外经济贸易大学",
        "aliases": ["UIBE"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "shufe",
        "name": "上海财经大学",
        "aliases": ["SHUFE"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cuel",
        "name": "中南财经政法大学",
        "aliases": ["ZUEL"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cupl",
        "name": "中国政法大学",
        "aliases": ["CUPL"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "bfsu",
        "name": "北京外国语大学",
        "aliases": ["BFSU"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "shisu",
        "name": "上海外国语大学",
        "aliases": ["SISU"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "cuc",
        "name": "中国传媒大学",
        "aliases": ["CUC"],
        "groups": ["strong_211", "specialized_strong"],
    },
    {
        "university_id": "dhu",
        "name": "东华大学",
        "aliases": ["Donghua University"],
        "groups": ["strong_211"],
    },
    {
        "university_id": "jiangnan",
        "name": "江南大学",
        "aliases": ["Jiangnan University"],
        "groups": ["strong_211"],
    },
]


class PublicKBValidationIssue(BaseModel):
    record_id: str = ""
    source_id: str = ""
    level: Literal["error", "warning"]
    code: str
    message: str


class PublicKBValidationReport(BaseModel):
    valid: bool
    source_count: int = 0
    record_count: int = 0
    chunk_count: int = 0
    issues: List[PublicKBValidationIssue] = Field(default_factory=list)


class PublicKBSeedResult(BaseModel):
    source_count: int = 0
    record_count: int = 0
    chunk_count: int = 0
    university_count: int = 0
    target_groups: List[str] = Field(default_factory=list)


class PublicKBStore:
    """JSONL-backed public KB store under ``workspace/public_kb``."""

    def __init__(self, workspace_or_path: Any):
        root = (
            workspace_or_path.root
            if hasattr(workspace_or_path, "root")
            else Path(workspace_or_path)
        )
        self.root = Path(root) / "public_kb"
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self.sources_path = self.root / "sources.jsonl"
        self.records_path = self.root / "records.jsonl"
        self.chunks_path = self.root / "chunks.jsonl"

    def save_manifest(self, manifest: PublicKBManifest) -> PublicKBManifest:
        self.manifest_path.write_text(_dump(manifest), encoding="utf-8")
        return manifest

    def load_manifest(self) -> PublicKBManifest:
        if not self.manifest_path.exists():
            return PublicKBManifest()
        return PublicKBManifest(**json.loads(self.manifest_path.read_text(encoding="utf-8")))

    def append_source(self, source: PublicKBSource) -> PublicKBSource:
        _append_jsonl(self.sources_path, source)
        return source

    def append_record(self, record: PublicKBRecord) -> PublicKBRecord:
        _append_jsonl(self.records_path, record)
        return record

    def append_chunk(self, chunk: PublicKBChunk) -> PublicKBChunk:
        _append_jsonl(self.chunks_path, chunk)
        return chunk

    def replace_sources(self, sources: Iterable[PublicKBSource]) -> None:
        _write_jsonl(self.sources_path, sources)

    def replace_records(self, records: Iterable[PublicKBRecord]) -> None:
        _write_jsonl(self.records_path, records)

    def replace_chunks(self, chunks: Iterable[PublicKBChunk]) -> None:
        _write_jsonl(self.chunks_path, chunks)

    def sources(self) -> List[PublicKBSource]:
        return _read_jsonl(self.sources_path, PublicKBSource)

    def records(self) -> List[PublicKBRecord]:
        return _read_jsonl(self.records_path, PublicKBRecord)

    def chunks(self) -> List[PublicKBChunk]:
        return _read_jsonl(self.chunks_path, PublicKBChunk)

    def validate(self) -> PublicKBValidationReport:
        sources = self.sources()
        records = self.records()
        chunks = self.chunks()
        source_ids = {item.source_id for item in sources}
        record_ids = {item.record_id for item in records}
        issues: List[PublicKBValidationIssue] = []
        for source in sources:
            if not source.url and source.source_kind == "public_web":
                issues.append(
                    PublicKBValidationIssue(
                        source_id=source.source_id,
                        level="error",
                        code="missing_url",
                        message="公开网页来源必须有 URL",
                    )
                )
            if source.valid_for_year is None and source.source_kind in {"policy", "public_web"}:
                issues.append(
                    PublicKBValidationIssue(
                        source_id=source.source_id,
                        level="warning",
                        code="missing_valid_year",
                        message="政策或网页来源缺少适用年份，只能进入 needs_review",
                    )
                )
        for record in records:
            if not record.source_refs:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=record.record_id,
                        level="error",
                        code="missing_source_ref",
                        message="公开知识事实必须绑定至少一个来源",
                    )
                )
            missing = [ref for ref in record.source_refs if ref not in source_ids]
            if missing:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=record.record_id,
                        level="error",
                        code="unknown_source_ref",
                        message=f"未知 source_id: {', '.join(missing)}",
                    )
                )
            if record.record_kind in {"policy", "deadline"} and record.valid_for_year is None:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=record.record_id,
                        level="warning",
                        code="policy_without_year",
                        message="政策和截止日期缺少年份，不能作为当前建议",
                    )
                )
        for chunk in chunks:
            if chunk.source_id not in source_ids:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=chunk.record_id,
                        source_id=chunk.source_id,
                        level="error",
                        code="unknown_chunk_source",
                        message="chunk 引用了不存在的 source_id",
                    )
                )
            if chunk.record_id not in record_ids:
                issues.append(
                    PublicKBValidationIssue(
                        record_id=chunk.record_id,
                        source_id=chunk.source_id,
                        level="error",
                        code="unknown_chunk_record",
                        message="chunk 引用了不存在的 record_id",
                    )
                )
        return PublicKBValidationReport(
            valid=not any(issue.level == "error" for issue in issues),
            source_count=len(sources),
            record_count=len(records),
            chunk_count=len(chunks),
            issues=issues,
        )

    def search(self, query: str, *, limit: int = 10) -> List[PublicKBRecord]:
        terms = {term.lower() for term in query.split() if term.strip()}
        if not terms:
            return self.records()[:limit]
        scored = []
        for record in self.records():
            haystack = " ".join(
                [
                    record.name,
                    record.summary,
                    *record.aliases,
                    json.dumps(record.structured_facts, ensure_ascii=False),
                ]
            ).lower()
            score = sum(term in haystack for term in terms)
            if score:
                scored.append((score, record.updated_at, record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in scored[:limit]]


def _dump(model: BaseModel) -> str:
    payload = model.model_dump() if hasattr(model, "model_dump") else model.dict()
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _append_jsonl(path: Path, model: BaseModel) -> None:
    payload = model.model_dump() if hasattr(model, "model_dump") else model.dict()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path, model_type: Type[BaseModel]) -> List[Any]:
    if not path.exists():
        return []
    return [
        model_type(**json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def iter_public_records(store: PublicKBStore) -> Iterable[PublicKBRecord]:
    """Yield only public records eligible for remote synchronization."""

    yield from (record for record in store.records() if record.audit_status != "failed")


def default_public_kb_manifest() -> PublicKBManifest:
    groups = sorted({group for item in PUBLIC_KB_TARGET_UNIVERSITIES for group in item["groups"]})
    return PublicKBManifest(
        target_groups=groups,
        universities=PUBLIC_KB_TARGET_UNIVERSITIES,
    )


def seed_target_universities(store: PublicKBStore, *, replace: bool = False) -> PublicKBSeedResult:
    """Seed stable public university entities without inventing policy details."""

    manifest = default_public_kb_manifest()
    source = PublicKBSource(
        source_id="pubsrc_target_university_scope_v1",
        source_kind="manual_summary",
        title="重点高校公开知识库首批范围",
        publisher="Offer Harvester local planning",
        authority_level="manual_summary",
        valid_for_year=None,
        privacy_scope="public",
        audit_status="passed",
        metadata={
            "scope_note": "All 985 universities plus user-confirmed strong 211/specialized schools.",
            "requires_policy_sources": True,
        },
    )
    records: List[PublicKBRecord] = []
    chunks: List[PublicKBChunk] = []
    for item in PUBLIC_KB_TARGET_UNIVERSITIES:
        university_id = str(item["university_id"])
        name = str(item["name"])
        aliases = [str(alias) for alias in item.get("aliases", [])]
        groups = [str(group) for group in item.get("groups", [])]
        record = PublicKBRecord(
            record_id=f"pubrec_university_{university_id}",
            record_kind="university",
            university_id=university_id,
            name=name,
            aliases=aliases,
            summary=f"{name} 属于公开知识库首批目标院校，后续政策、学院和导师事实必须绑定官方来源。",
            structured_facts={
                "groups": groups,
                "policy_detail_status": "needs_official_source",
                "private_student_data_allowed": False,
            },
            source_refs=[source.source_id],
            status="active",
            audit_status="passed",
        )
        chunk = PublicKBChunk(
            chunk_id=f"pubchunk_university_{university_id}_scope",
            record_id=record.record_id,
            source_id=source.source_id,
            title=f"{name} 公开知识库范围记录",
            text=(
                f"{name}（别名：{', '.join(aliases) or '无'}）已纳入保研公开知识库目标范围。"
                "该记录只表示院校实体和范围，不表示任何具体招生政策。"
            ),
            authority_level="manual_summary",
            audit_status="passed",
            embedding_route="external_public",
            metadata={"groups": groups, "university_id": university_id},
        )
        records.append(record)
        chunks.append(chunk)
    if replace:
        store.save_manifest(manifest)
        store.replace_sources([source])
        store.replace_records(records)
        store.replace_chunks(chunks)
    else:
        store.save_manifest(manifest)
        existing_source_ids = {item.source_id for item in store.sources()}
        existing_record_ids = {item.record_id for item in store.records()}
        existing_chunk_ids = {item.chunk_id for item in store.chunks()}
        if source.source_id not in existing_source_ids:
            store.append_source(source)
        for record in records:
            if record.record_id not in existing_record_ids:
                store.append_record(record)
        for chunk in chunks:
            if chunk.chunk_id not in existing_chunk_ids:
                store.append_chunk(chunk)
    return PublicKBSeedResult(
        source_count=1,
        record_count=len(records),
        chunk_count=len(chunks),
        university_count=len(records),
        target_groups=manifest.target_groups,
    )


def _write_jsonl(path: Path, models: Iterable[BaseModel]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for model in models:
            payload = model.model_dump() if hasattr(model, "model_dump") else model.dict()
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
