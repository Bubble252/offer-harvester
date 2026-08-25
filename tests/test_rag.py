import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

import main as backend_main  # noqa: E402
from agents import run_contact_email_workflow  # noqa: E402
from memory import LocalMemoryManager  # noqa: E402
from models import (  # noqa: E402
    AdvisorSource,
    ApplicationArchiveRequest,
    ApplicationRecord,
    BatchTriageRequest,
    CommunicationDraftRequest,
    EmailSignalDecisionRequest,
    EmailSignalImportRequest,
    GapPlanRequest,
    GeneratedMaterial,
    KnowledgeBaseSourceCreate,
    MaterialVersion,
    PipelineSyncRequest,
    PresentationGenerationRequest,
    RAGSearchHit,
    Target,
)
from rag import (  # noqa: E402
    ApiEmbeddingProvider,
    ChromaVectorStore,
    Claim,
    EvidenceBundle,
    HashEmbeddingProvider,
    KnowledgeBaseIndex,
    KnowledgeBaseRetriever,
    LexicalReranker,
    PrivacyAwareEmbeddingProvider,
    SqliteVectorStore,
    VectorRecord,
    build_evidence_bundle,
    detect_conflicts,
)
from services import build_profile_from_text, make_match, parse_advisor_profile  # noqa: E402
from storage import Workspace  # noqa: E402


def test_rag_indexes_manual_knowledge_student_docs_and_advisor_sources(tmp_path):
    workspace = Workspace(str(tmp_path))
    document = workspace.save_user_document(
        "匿名学生\n项目：多模态论文问答系统，使用 PyTorch 实现。".encode("utf-8"),
        "resume.txt",
        category="resumes",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
    )
    source = AdvisorSource(
        source_type="manual_text",
        title="张三教授主页",
        raw_text="张三教授研究方向包括多模态学习和大模型推理，接收推免硕士。",
        cleaned_text="张三教授研究方向包括多模态学习和大模型推理，接收推免硕士。",
        trusted=True,
    )
    workspace.write("advisor_sources", dump(source), "source_id")

    index = KnowledgeBaseIndex(workspace)
    policy = index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="某大学预推免通知",
            text="预推免报名截止日期为 2026 年 9 月 10 日，材料包括成绩单、简历和推荐信。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    manifest = index.rebuild()

    assert manifest["source_count"] == 3
    assert manifest["chunk_count"] >= 3

    retriever = KnowledgeBaseRetriever(workspace)
    policy_hits = retriever.search("预推免 截止日期 材料", source_kinds=["policy"]).hits
    student_hits = retriever.search("多模态 PyTorch 项目", source_kinds=["student_document"]).hits
    advisor_hits = retriever.search("张三 多模态 推免", source_kinds=["advisor_source"]).hits

    assert policy_hits[0].source_id == policy.source_id
    assert policy_hits[0].valid_for_year == 2026
    assert student_hits[0].source_id == document.document_id
    assert student_hits[0].source_subtype == "resumes"
    assert student_hits[0].needs_confirmation is True
    assert advisor_hits[0].source_id == source.source_id
    assert "#" in policy_hits[0].evidence_ref


def test_retrieval_persists_evidence_bundle_with_lineage(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="某学院预推免通知",
            text="2026 年预推免报名截止日期为 9 月 10 日，申请材料包括成绩单和中文简历。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()

    retrieval = KnowledgeBaseRetriever(workspace).search("预推免 截止日期 成绩单", limit=3)

    assert retrieval.evidence_bundle is not None
    bundle = retrieval.evidence_bundle
    assert bundle.bundle_id
    assert bundle.snapshots
    assert bundle.snapshots[0].snapshot_id == bundle.snapshot_ids[0]
    assert bundle.retrieval_refs == [hit.evidence_ref for hit in retrieval.hits]
    assert bundle.snapshot_ids
    assert bundle.lineages[0].source_id == retrieval.hits[0].source_id
    assert bundle.claims[0].source_refs[0] == retrieval.hits[0].evidence_ref
    assert workspace.read("evidence_bundles", bundle.bundle_id)["bundle_id"] == bundle.bundle_id


def test_evidence_bundle_detects_explicit_claim_conflicts():
    first = {
        "source_id": "src_policy_a",
        "chunk_id": "chunk_a",
        "source_kind": "policy",
        "title": "A 学院通知",
        "score": 0.9,
        "confidence": 0.9,
        "snippet": "截止日期为 9 月 10 日。",
        "evidence_ref": "src_policy_a#chunk_a",
    }
    second = {
        **first,
        "source_id": "src_policy_b",
        "chunk_id": "chunk_b",
        "title": "B 学院通知",
        "snippet": "截止日期为 9 月 20 日。",
        "evidence_ref": "src_policy_b#chunk_b",
    }
    hits = [RAGSearchHit(**first), RAGSearchHit(**second)]
    bundle = build_evidence_bundle("截止日期", hits)
    bundle.claims[0].claim_key = "deadline:target_demo"
    bundle.claims[0].value = "2026-09-10"
    bundle.claims[1].claim_key = "deadline:target_demo"
    bundle.claims[1].value = "2026-09-20"
    bundle.conflicts = detect_conflicts(bundle.claims, bundle.links)

    assert bundle.conflicts
    assert bundle.conflicts[0].claim_key == "deadline:target_demo"


def test_contact_email_workflow_adds_rag_evidence_refs(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="保研材料清单",
            text="保研套磁前建议准备中文简历、成绩单和一页科研项目摘要。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()

    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：多模态论文问答系统")
    advisor_source = AdvisorSource(
        source_type="manual_text",
        title="李四教授主页",
        raw_text="李四教授研究方向包括多模态学习。",
        cleaned_text="李四教授研究方向包括多模态学习。",
        trusted=True,
    )
    advisor = parse_advisor_profile([advisor_source])
    target = Target(
        name="某大学李四教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=advisor.source_ids,
    )
    match = make_match(profile, target, advisor)

    result = run_contact_email_workflow(
        profile,
        target,
        advisor,
        match,
        retriever=KnowledgeBaseRetriever(workspace),
    )

    assert any("#chunk_" in item for item in result.material.evidence)
    retrieval_event = next(
        event for event in result.events if event.event_type == "retrieval_completed"
    )
    assert retrieval_event.payload["evidence_bundle_id"]
    assert retrieval_event.payload["claim_count"] >= 1
    graph_event = next(
        event
        for event in result.events
        if event.agent_name == "EvidenceGraph" and event.event_type == "audit_completed"
    )
    assert graph_event.payload["bundle_claim_count"] >= retrieval_event.payload["claim_count"]
    saved_bundle = workspace.read(
        "evidence_bundles",
        retrieval_event.payload["evidence_bundle_id"],
    )
    assert saved_bundle["audit_ref"] == result.agent_run.run_id
    assert saved_bundle["snapshots"]


def test_contact_email_endpoint_records_audit_feedback_loop(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    profile = build_profile_from_text("匿名学生\n某大学计算机学院\n项目：多模态论文问答系统")
    target = Target(name="某大学李四教授课题组")
    workspace.write("profiles", dump(profile), "profile_id")
    workspace.write("targets", dump(target), "target_id")

    payload = backend_main.generate_contact_email(target.target_id)

    feedback_loop = payload["feedback_loop"]
    assert feedback_loop is not None
    assert feedback_loop.feedback_memory_ids
    assert feedback_loop.procedural_candidate_ids
    assert LocalMemoryManager(workspace).search("", kinds=["feedback"])
    assert workspace.list("procedural_candidates")


def test_evidence_bundle_audit_feedback_endpoint_persists_memory(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)
    bundle = EvidenceBundle(
        query="推免申请材料",
        retrieval_refs=["policy_old#chunk_1"],
        claims=[
            Claim(
                claim_key="policy_materials",
                claim_type="policy_fact",
                text="旧年度推免申请材料说明。",
                status="stale",
                source_refs=["policy_old#chunk_1"],
                needs_confirmation=True,
            )
        ],
    )
    backend_main.rag_retriever.evidence_store.save(bundle)

    payload = backend_main.audit_evidence_bundle_feedback(bundle.bundle_id)

    assert payload["evidence_bundle"].audit_status == "needs_review"
    assert payload["feedback_loop"].feedback_memory_ids
    assert LocalMemoryManager(workspace).search("", kinds=["feedback"])
    assert workspace.read("evidence_bundles", bundle.bundle_id)["audit_ref"]


def test_rag_blocks_expired_policy_by_default_but_can_return_historical(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    expired = index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="旧版预推免通知",
            text="旧版通知写明 2024 年截止日期为 9 月 1 日。",
            valid_for_year=2024,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()

    retriever = KnowledgeBaseRetriever(workspace)
    current_hits = retriever.search(
        "预推免 截止日期",
        source_kinds=["policy"],
        as_of_year=2026,
    ).hits
    historical_hits = retriever.search(
        "预推免 截止日期",
        source_kinds=["policy"],
        as_of_year=2026,
        include_historical=True,
    ).hits

    assert all(hit.source_id != expired.source_id for hit in current_hits)
    assert historical_hits
    assert historical_hits[0].source_id == expired.source_id
    assert historical_hits[0].historical is True


def test_rag_excludes_rejected_student_documents(tmp_path):
    workspace = Workspace(str(tmp_path))
    document = workspace.save_user_document(
        "匿名学生\n项目：多模态论文问答系统，使用 PyTorch 实现。".encode("utf-8"),
        "resume.txt",
        category="resumes",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
    )
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统，使用 PyTorch 实现。",
        source_document_ids=[document.document_id],
    )
    profile.confirmation_map["projects"] = "rejected"

    index = KnowledgeBaseIndex(workspace)
    index.rebuild()
    retriever = KnowledgeBaseRetriever(workspace)

    allowed_hits = retriever.search(
        "多模态 PyTorch 项目",
        source_kinds=["student_document"],
    ).hits
    blocked_hits = retriever.search(
        "多模态 PyTorch 项目",
        source_kinds=["student_document"],
        profile=profile,
    ).hits

    assert allowed_hits
    assert not blocked_hits


def test_rag_rebuild_persists_vectors_and_hybrid_scores(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace, embedding_provider=HashEmbeddingProvider(dimension=32))
    source = index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="2026 推免流程",
            text="2026 年推免申请流程包括网上报名、材料审核和面试确认。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )

    manifest = index.rebuild()
    assert manifest["index_version"] == "hybrid-json-v1"
    assert manifest["embedding_dimension"] == 32
    assert workspace.rag_vectors_path().exists()

    hits = (
        KnowledgeBaseRetriever(
            workspace,
            embedding_provider=HashEmbeddingProvider(dimension=32),
            reranker=LexicalReranker(),
        )
        .search("推免申请流程", source_kinds=["policy"])
        .hits
    )
    assert hits[0].source_id == source.source_id
    assert hits[0].content_hash.startswith("sha256:")
    assert hits[0].keyword_score >= 0
    assert hits[0].vector_score > 0
    assert hits[0].rerank_score > 0
    assert "vector=" in hits[0].retrieval_explanation


def test_sqlite_storage_persists_fts_and_local_vectors(tmp_path):
    store = SqliteVectorStore(tmp_path / "rag.sqlite3")
    store.replace(
        [
            VectorRecord(
                chunk_id="chunk_deadline",
                source_id="policy_a",
                vector=[1.0, 0.0],
                text="报名截止日期为 2026 年 9 月 10 日。",
                metadata={"source_kind": "policy", "embedding_route": "local"},
            ),
            VectorRecord(
                chunk_id="chunk_research",
                source_id="advisor_a",
                vector=[0.0, 1.0],
                text="导师研究方向是多模态学习。",
                metadata={"source_kind": "advisor_source", "embedding_route": "local"},
            ),
        ],
        index_version="test-sqlite-v1",
    )

    text_hits = store.search_text("截止日期")
    vector_hits = store.search([1.0, 0.0], metadata_filter={"source_kind": "policy"})

    assert text_hits[0].chunk_id == "chunk_deadline"
    assert vector_hits[0].chunk_id == "chunk_deadline"
    assert store.records()[0].text


def test_sqlite_index_and_retriever_use_same_evidence_contract(tmp_path):
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace, storage_backend="sqlite")
    source = index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="SQLite 政策样本",
            text="推免报名截止日期为 2026 年 9 月 10 日。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    manifest = index.rebuild()
    retrieval = KnowledgeBaseRetriever(
        workspace,
        storage_backend="sqlite",
    ).search("报名截止日期", source_kinds=["policy"])

    assert manifest["storage_backend"] == "sqlite"
    assert workspace.rag_sqlite_path().exists()
    assert retrieval.hits[0].source_id == source.source_id
    assert retrieval.evidence_bundle is not None


def test_chroma_adapter_supports_injected_collection_without_dependency():
    class FakeCollection:
        def __init__(self):
            self.items = {}

        def get(self, include=None):
            return {"ids": list(self.items)}

        def delete(self, ids):
            for item_id in ids:
                self.items.pop(item_id, None)

        def add(self, ids, embeddings, documents, metadatas):
            for item_id, vector, document, metadata in zip(ids, embeddings, documents, metadatas):
                self.items[item_id] = (vector, document, metadata)

        def query(self, query_embeddings, n_results, include, where=None):
            query = query_embeddings[0]
            candidates = []
            for item_id, (vector, _, metadata) in self.items.items():
                if where and not _fake_where_matches(metadata, where):
                    continue
                distance = sum((left - right) ** 2 for left, right in zip(query, vector))
                candidates.append((distance, item_id, metadata))
            candidates.sort()
            selected = candidates[:n_results]
            return {
                "ids": [[item_id for _, item_id, _ in selected]],
                "distances": [[distance for distance, _, _ in selected]],
                "metadatas": [[metadata for _, _, metadata in selected]],
            }

    store = ChromaVectorStore(FakeCollection())
    store.replace(
        [
            VectorRecord(
                chunk_id="chunk_a",
                source_id="source_a",
                vector=[1.0, 0.0],
                text="公开政策",
                metadata={"source_kind": "policy"},
            ),
        ],
        index_version="test-chroma-v1",
    )

    hits = store.search([1.0, 0.0], metadata_filter={"source_kind": "policy"})

    assert hits[0].chunk_id == "chunk_a"
    assert hits[0].source_id == "source_a"


def test_chroma_backend_falls_back_to_json_when_adapter_missing(tmp_path, monkeypatch):
    def raise_missing(*args, **kwargs):
        raise RuntimeError("chromadb not available")

    monkeypatch.setattr("rag.index.ChromaVectorStore.from_path", raise_missing)
    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace, storage_backend="chroma")
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="Chroma fallback policy",
            text="公开政策说明需要保留本地回退。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    manifest = index.rebuild()

    assert manifest["requested_storage_backend"] == "chroma"
    assert manifest["storage_backend"] == "json"
    assert manifest["storage_fallback_reason"]
    assert workspace.rag_vectors_path().exists()


def test_privacy_embedding_router_never_sends_student_text_to_public_provider(tmp_path):
    public_calls = []

    def public_embed(texts):
        public_calls.extend(texts)
        return [[0.0, 1.0] for _ in texts]

    router = PrivacyAwareEmbeddingProvider(
        local_provider=HashEmbeddingProvider(dimension=2),
        public_provider=ApiEmbeddingProvider(
            model_name="public-api",
            dimension=2,
            embed_fn=public_embed,
        ),
        allow_external_public=True,
    )
    workspace = Workspace(str(tmp_path))
    workspace.save_user_document(
        "匿名学生\n项目：私有研究经历。".encode("utf-8"),
        "resume.txt",
        category="resumes",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
    )
    index = KnowledgeBaseIndex(
        workspace,
        embedding_provider=router,
        storage_backend="sqlite",
    )
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="公开政策",
            text="公开报名截止日期为 9 月 10 日。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()
    retriever = KnowledgeBaseRetriever(
        workspace,
        embedding_provider=router,
        storage_backend="sqlite",
    )
    public_hits = retriever.search(
        "公开报名截止日期",
        source_kinds=["policy"],
        allow_external_public_query=True,
    ).hits

    assert public_calls
    assert all("私有研究经历" not in text for text in public_calls)
    records = SqliteVectorStore(workspace.rag_sqlite_path()).records()
    assert any(item.metadata["embedding_route"] == "local" for item in records)
    assert any(item.metadata["embedding_route"] == "external_public" for item in records)
    assert public_hits


def _fake_where_matches(metadata, where):
    if "$and" in where:
        return all(_fake_where_matches(metadata, item) for item in where["$and"])
    for key, condition in where.items():
        if "$eq" in condition and metadata.get(key) != condition["$eq"]:
            return False
        if "$in" in condition and metadata.get(key) not in condition["$in"]:
            return False
    return True


def test_rag_falls_back_to_bm25_when_vector_provider_fails(tmp_path):
    class BrokenEmbeddingProvider(HashEmbeddingProvider):
        def embed_query(self, query):
            raise RuntimeError("vector service unavailable")

    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="报名通知",
            text="本年度推免报名通知说明，网上报名截止日期为 9 月 10 日，请在截止前完成材料提交。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()

    hits = (
        KnowledgeBaseRetriever(
            workspace,
            embedding_provider=BrokenEmbeddingProvider(),
        )
        .search("报名截止日期", source_kinds=["policy"])
        .hits
    )
    assert hits
    assert hits[0].keyword_score > 0
    assert hits[0].vector_score == 0
    assert hits[0].score > 0


def test_rag_rebuild_records_bm25_fallback_when_embedding_batch_fails(tmp_path):
    class BrokenBatchEmbeddingProvider(HashEmbeddingProvider):
        def embed_texts(self, texts):
            raise RuntimeError("embedding batch unavailable")

    workspace = Workspace(str(tmp_path))
    index = KnowledgeBaseIndex(
        workspace,
        embedding_provider=BrokenBatchEmbeddingProvider(),
    )
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="推免流程说明",
            text="本通知说明本年度推免申请流程。申请人需要先完成网上报名，再提交成绩单、个人陈述和科研材料，学校完成材料审核后统一安排面试确认，具体时间以学院后续通知为准。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )

    manifest = index.rebuild()
    assert manifest["vector_status"] == "fallback_bm25"
    assert index.load_chunks()


def test_web_supplement_upload_only_creates_preview(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    payload = asyncio.run(
        backend_main.upload_profile(
            file=None,
            text="张三教授主页：研究方向是多模态学习。",
            category="web_supplements",
        )
    )
    assert payload["confirmed"] is False
    supplement = payload["supplement"]
    preview = payload["preview"]
    assert supplement.source_type == "web_supplement"
    assert preview.name == "未命名学生"
    assert workspace.read_user_document_manifest()["documents"]
    assert backend_main.latest_profile() is None


def test_readiness_score_endpoint_persists_report(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\nGPA 3.8/4.0\n项目：多模态论文问答系统",
        source_document_ids=["doc_profile"],
    )
    workspace.write("profiles", dump(profile), "profile_id")
    source = AdvisorSource(
        source_type="manual_text",
        title="李四教授主页",
        raw_text="李四教授研究方向包括多模态学习。",
        cleaned_text="李四教授研究方向包括多模态学习。",
        trusted=True,
    )
    workspace.write("advisor_sources", dump(source), "source_id")
    advisor = parse_advisor_profile([source])
    workspace.write("advisors", dump(advisor), "advisor_id")
    target = Target(
        name="某大学李四教授课题组",
        advisor_id=advisor.advisor_id,
        source_ids=advisor.source_ids,
        deadline="2026-09-10",
    )
    workspace.write("targets", dump(target), "target_id")
    workspace.write(
        "applications",
        dump(
            ApplicationRecord(
                target_id=target.target_id,
                status="contacted",
                deadline=target.deadline,
                next_action="准备套磁材料",
            )
        ),
        "application_id",
    )

    report = backend_main.score_readiness()

    assert report.total_score >= 0
    assert report.score_id
    assert workspace.list("readiness_scores")
    assert workspace.latest("readiness_scores")["score_id"] == report.score_id


def test_presentation_generation_persists_params_and_quality_report(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    target = Target(name="某大学李四教授课题组")
    workspace.write("targets", dump(target), "target_id")
    outline = GeneratedMaterial(
        target_id=target.target_id,
        material_type="ppt_outline",
        title="面试 PPT 大纲",
        content="""# 5 分钟保研面试展示 PPT 大纲

## 1. 封面
- 标题：匿名学生

## 2. 教育背景
- 学校：某大学

## 3. 项目经历
- 项目：多模态问答

## 4. 方向匹配
- 导师方向：多模态学习

## 5. 未来计划
- 阅读课题组论文
""",
    )
    workspace.write("generated", dump(outline), "material_id")

    task = backend_main.generate_presentation(
        target.target_id,
        PresentationGenerationRequest(
            outline_material_id=outline.material_id,
            num_slides=3,
            duration_minutes=4,
            length_factor="concise",
        ),
    )

    quality_reports = workspace.list("presentation_quality_reports")
    assert task.status == "completed"
    assert task.engine_name == "LocalPptxAdapter"
    assert task.generation_params["num_slides"] == 3
    assert task.quality_score > 0
    assert quality_reports[-1]["quality_id"] == task.quality_report_id
    assert (workspace.root / "generated" / "presentations" / task.output_filename).exists()


def test_lifecycle_endpoints_persist_archive_and_sync_runs(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\n项目：多模态论文问答系统",
        source_document_ids=["doc_profile"],
    )
    workspace.write("profiles", dump(profile), "profile_id")
    target = Target(name="某大学李四教授课题组", deadline="2026-09-10")
    workspace.write("targets", dump(target), "target_id")
    application = ApplicationRecord(
        target_id=target.target_id,
        status="contacted",
        deadline=target.deadline,
        last_contact_at="2026-08-01T12:00:00+08:00",
    )
    workspace.write("applications", dump(application), "application_id")
    material = GeneratedMaterial(
        target_id=target.target_id,
        material_type="contact_email",
        title="套磁邮件",
        content="老师您好，我关注多模态学习。",
        evidence=[profile.profile_id, target.target_id],
    )
    workspace.write("generated", dump(material), "material_id")

    archive = backend_main.create_target_archive(
        target.target_id,
        ApplicationArchiveRequest(material_ids=[material.material_id], stage="contacted"),
    )
    draft = backend_main.create_communication_draft(
        target.target_id,
        CommunicationDraftRequest(kind="follow_up", source_material_ids=[material.material_id]),
    )
    email_status = backend_main.get_email_sync_status(provider="gmail")
    pipeline_status = backend_main.get_pipeline_sync_status(PipelineSyncRequest(provider="notion"))

    assert workspace.read("application_archives", archive.archive_id)
    assert workspace.read("communications", draft.communication_id)
    assert email_status.read_only
    assert pipeline_status.direction == "one_way_export"
    assert len(workspace.list("sync_runs")) == 2


def test_email_signal_endpoints_import_and_apply_candidate(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    target = Target(name="某大学王教授课题组", deadline="2026-09-10")
    workspace.write("targets", dump(target), "target_id")
    application = ApplicationRecord(target_id=target.target_id, status="contacted")
    workspace.write("applications", dump(application), "application_id")

    result = backend_main.import_email_signals(
        EmailSignalImportRequest(
            provider="gmail",
            raw_text="""Subject: 某大学王教授课题组 拟录取通知
From: wang@example.edu
Date: 2026-08-23
恭喜，你已获得拟录取资格，请后续确认。
""",
        )
    )

    candidate = result.candidates[0]
    approved = backend_main.approve_email_signal(
        candidate.candidate_id,
        EmailSignalDecisionRequest(user_note="用户确认该邮件可信。"),
    )

    saved_application = workspace.read("applications", application.application_id)
    assert approved.status == "approved"
    assert saved_application["status"] == "offer"
    assert workspace.list("application_archives")


def test_memory_endpoints_write_confirm_search_and_create_promotion(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace

    memory = backend_main.create_memory_candidate(
        backend_main.MemoryWriteRequest(
            kind="fact",
            scope="student:demo",
            key="student.award",
            value={"award": "校级优秀学生"},
            source_ref="doc_awards#1",
            confidence=0.8,
        )
    )
    assert memory.status == "candidate"
    assert backend_main.list_memory(q="student.award", include_candidates=False) == []

    confirmed = backend_main.confirm_memory(memory.memory_id)
    assert confirmed.status == "confirmed"
    assert backend_main.list_memory(q="student.award", include_candidates=False)[0].memory_id == (
        memory.memory_id
    )

    promotion = backend_main.create_memory_promotion_candidate(
        confirmed.memory_id,
        backend_main.MemoryPromotionRequest(
            target="profile",
            reason="用户确认奖项可以进入学生画像",
        ),
    )
    assert promotion.status == "candidate"
    assert backend_main.list_memory_promotion_candidates(target="profile")[0].candidate_id == (
        promotion.candidate_id
    )


def test_stage16_strategy_endpoints_persist_reports(tmp_path):
    workspace = Workspace(str(tmp_path))
    backend_main.workspace = workspace
    backend_main.rag_index = KnowledgeBaseIndex(workspace)
    backend_main.rag_retriever = KnowledgeBaseRetriever(workspace)

    document = workspace.save_user_document(
        "补充项目：RAG 保研政策问答系统，使用 FastAPI 和 Python 实现。".encode("utf-8"),
        "project.md",
        category="research_projects",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
    )
    profile = build_profile_from_text(
        "匿名学生\n某大学计算机学院\nGPA 3.8/4.0\n项目：多模态论文问答系统",
        source_document_ids=[document.document_id],
    )
    workspace.write("profiles", dump(profile), "profile_id")
    target = Target(name="某大学王教授课题组", deadline="2026-09-10")
    workspace.write("targets", dump(target), "target_id")
    workspace.write(
        "applications",
        dump(ApplicationRecord(target_id=target.target_id, deadline=target.deadline)),
        "application_id",
    )

    triage = backend_main.create_target_triage_report(BatchTriageRequest())
    expansion = backend_main.create_profile_expansion_report()
    gap_plan = backend_main.create_gap_plan(GapPlanRequest(target_id=target.target_id))
    template_status = backend_main.get_template_registry_status()
    connector_status = backend_main.get_source_connector_status()

    assert triage.items[0].target_id == target.target_id
    assert triage.items[0].preliminary is True
    assert expansion.candidate_count >= 1
    assert gap_plan.target_id == target.target_id
    assert template_status.implemented is True
    assert template_status.template_count >= 2
    assert template_status.active_count >= 2
    assert all(template.render_preview.passed for template in template_status.templates)
    assert connector_status.implemented is True
    assert connector_status.connector_count >= 2
    assert connector_status.active_count >= 2
    assert all(connector.field_mapping for connector in connector_status.connectors)
    assert workspace.list("target_triage_reports")
    assert workspace.list("profile_expansion_candidates")
    assert workspace.list("gap_plans")
    assert workspace.list("template_registry")
    assert workspace.list("source_connectors")


def test_rag_ignores_generated_outputs_as_fact_sources(tmp_path):
    workspace = Workspace(str(tmp_path))
    workspace.save_user_document(
        "匿名学生\n项目：多模态论文问答系统。".encode("utf-8"),
        "resume.txt",
        category="resumes",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
    )

    index = KnowledgeBaseIndex(workspace)
    index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="保研材料清单",
            text="保研套磁前建议准备中文简历、成绩单和一页科研项目摘要。",
            valid_for_year=2026,
            trusted=True,
            confirmed=True,
        )
    )
    retriever = KnowledgeBaseRetriever(workspace)
    baseline_manifest = index.rebuild()
    baseline_hits = retriever.search(
        "保研 材料",
        source_kinds=["student_document", "advisor_source", "policy"],
    ).hits

    generated = GeneratedMaterial(
        target_id="target_demo",
        material_type="contact_email",
        title="草稿",
        content="RAGFACTBLOCK20260822UNIQUE",
    )
    workspace.write(
        "generated",
        dump(generated),
        "material_id",
    )
    version = MaterialVersion(
        material_id="mat_demo",
        target_id="target_demo",
        material_type="contact_email",
        stage="draft",
        content="RAGFACTBLOCK20260822UNIQUE",
        source_run_id="run_demo",
    )
    workspace.write(
        "material_versions",
        dump(version),
        "version_id",
    )
    manifest = index.rebuild()
    after_hits = retriever.search(
        "保研 材料",
        source_kinds=["student_document", "advisor_source", "policy"],
    ).hits

    assert baseline_manifest["source_count"] == 2
    assert manifest["source_count"] == 2
    assert [hit.source_id for hit in after_hits] == [hit.source_id for hit in baseline_hits]
    assert workspace.read("generated", generated.material_id) is not None
    assert workspace.read("material_versions", version.version_id) is not None


def dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()
