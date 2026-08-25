from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from agents.evidence_audit_agent import EvidenceAuditAgent
from feedback_loop import record_evidence_audit_feedback
from lifecycle import import_email_signal_candidates
from memory import LocalMemoryManager
from models import KnowledgeBaseSourceCreate, StudentProfile, now_iso
from rag import (
    Claim,
    EmbeddingProvider,
    EvidenceBundle,
    HashEmbeddingProvider,
    KnowledgeBaseIndex,
    KnowledgeBaseRetriever,
    LexicalReranker,
    configured_embedding_provider_from_env,
    configured_reranker_from_env,
)
from rag.reranker import NoopReranker, Reranker
from storage import Workspace

TEACHER_QUERIES = {
    "teacher_01": "AI for Science 强化学习 多模态 推理大语言模型",
    "teacher_02": "知识增强生成 科研智能体 证据链",
    "teacher_03": "机器学习系统 分布式训练 高效推理",
    "teacher_04": "视觉语言模型 图文对齐 多模态评测",
    "teacher_05": "数据挖掘 图学习 教育智能",
}

POLICY_QUERIES = {
    "policy_01": "推免 报名 材料提交 导师联系 面试环节",
    "policy_02": "截止日期 补交材料 盖章成绩单 英语证明",
    "policy_03": "夏令营 报名说明 复试安排 邮件报名",
    "policy_04": "材料模板 网页填报 系统确认 提交格式",
    "policy_05": "拟录取 候补 通知方式 接受确认期限",
}

STUDENT_QUERIES = {
    "student_01": "多模态学习 论文检索问答系统",
    "student_02": "知识图谱 推荐系统 图学习",
    "student_03": "高效推理 分布式训练 机器学习系统",
    "student_04": "视觉语言模型 图文对齐",
    "student_05": "教育智能 数据挖掘",
}

EMAIL_EXPECTED = {
    "email_01": "interview_invitation",
    "email_02": "material_request",
    "email_03": "advisor_reply",
    "email_04": "offer",
    "email_05": "rejection",
}


def run_rag_memory_evaluation(
    fixture_root: Path,
    *,
    workspace_dir: Optional[Path] = None,
    storage_backend: str = "sqlite",
    embedding_provider_name: str = "hash",
    reranker_name: str = "noop",
    reset_workspace: bool = False,
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    fixture_root = fixture_root.resolve()
    manifest = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    if workspace_dir is None:
        with tempfile.TemporaryDirectory(prefix="grad_apply_eval_") as tmp:
            return _run_eval(
                fixture_root,
                manifest,
                Workspace(tmp),
                storage_backend=storage_backend,
                embedding_provider_name=embedding_provider_name,
                reranker_name=reranker_name,
                report_path=report_path,
            )
    if reset_workspace:
        _reset_eval_workspace(workspace_dir)
    return _run_eval(
        fixture_root,
        manifest,
        Workspace(str(workspace_dir)),
        storage_backend=storage_backend,
        embedding_provider_name=embedding_provider_name,
        reranker_name=reranker_name,
        report_path=report_path,
    )


def _run_eval(
    fixture_root: Path,
    manifest: Dict[str, Any],
    workspace: Workspace,
    *,
    storage_backend: str,
    embedding_provider_name: str,
    reranker_name: str,
    report_path: Optional[Path],
) -> Dict[str, Any]:
    embedding_provider = _make_embedding_provider(embedding_provider_name)
    source_map = _index_fixture_sources(
        fixture_root,
        manifest,
        workspace,
        storage_backend,
        embedding_provider,
    )
    retriever = _make_eval_retriever(
        workspace,
        storage_backend,
        reranker_name,
        embedding_provider,
    )

    teacher_results = _evaluate_retrieval_group(
        retriever,
        source_map,
        TEACHER_QUERIES,
        source_kind="advisor_source",
        label="teacher_pages",
        allow_external_public_query=True,
    )
    policy_results = _evaluate_retrieval_group(
        retriever,
        source_map,
        POLICY_QUERIES,
        source_kind="policy",
        label="policy_pages",
        allow_external_public_query=True,
    )
    student_results = _evaluate_retrieval_group(
        retriever,
        source_map,
        STUDENT_QUERIES,
        source_kind="student_document",
        label="student_profiles",
        allow_external_public_query=False,
    )
    email_results = _evaluate_email_signals(fixture_root, manifest, workspace)
    expired_policy = _evaluate_expired_policy_rejection(
        workspace, storage_backend, reranker_name, embedding_provider
    )
    rejected_leakage = _evaluate_rejected_student_leakage(
        workspace, storage_backend, reranker_name, embedding_provider
    )
    audit_feedback = _evaluate_audit_feedback_loop(workspace)

    retrieval_results = teacher_results + policy_results + student_results
    report = {
        "report_id": "rag_memory_eval_2026_q3",
        "created_at": now_iso(),
        "fixture_set_id": manifest.get("set_id", ""),
        "storage_backend": storage_backend,
        "embedding": embedding_provider.model_name,
        "embedding_model_version": embedding_provider.model_version,
        "reranker": _make_reranker(reranker_name).name,
        "summary": {
            "retrieval_case_count": len(retrieval_results),
            "recall_at_1": _rate(item["rank"] <= 1 for item in retrieval_results),
            "recall_at_3": _rate(item["rank"] <= 3 for item in retrieval_results),
            "recall_at_5": _rate(item["rank"] <= 5 for item in retrieval_results),
            "mrr": round(mean(_reciprocal_rank(item["rank"]) for item in retrieval_results), 4)
            if retrieval_results
            else 0.0,
            "citation_correctness_at_1": _rate(
                item["top_source_id"] == item["gold_source_id"] for item in retrieval_results
            ),
            "avg_source_diversity_at_5": round(
                mean(item["source_diversity_at_5"] for item in retrieval_results), 4
            )
            if retrieval_results
            else 0.0,
            "expired_policy_rejection_rate": 1.0 if expired_policy["passed"] else 0.0,
            "rejected_leakage_rate": 0.0 if rejected_leakage["passed"] else 1.0,
            "email_signal_accuracy": _rate(item["passed"] for item in email_results),
            "auditor_pass_rate_on_current_bundles": _rate(
                item["audit_passed"] for item in retrieval_results
            ),
            "feedback_candidate_created": audit_feedback["feedback_candidate_created"],
        },
        "retrieval": retrieval_results,
        "email_signals": email_results,
        "expired_policy": expired_policy,
        "rejected_student_leakage": rejected_leakage,
        "audit_feedback": audit_feedback,
        "notes": [
            "This report evaluates the configured local/API RAG stack.",
            "Private student fixtures are kept on the local embedding route unless explicitly changed in code.",
            "No OCR, MongoDB, Redis, Chroma service, Milvus, or GPU dependency is used.",
        ],
    }
    output = report_path or (
        workspace.root / "reports" / f"rag_memory_eval_2026_q3_{reranker_name}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(output)
    return report


def _index_fixture_sources(
    fixture_root: Path,
    manifest: Dict[str, Any],
    workspace: Workspace,
    storage_backend: str,
    embedding_provider: EmbeddingProvider,
) -> Dict[str, str]:
    index = KnowledgeBaseIndex(
        workspace,
        storage_backend=storage_backend,
        embedding_provider=embedding_provider,
    )
    source_map: Dict[str, str] = {}
    for item in manifest["items"]["teacher_pages"]:
        source = _add_text_source(
            index,
            fixture_root,
            item,
            source_kind="advisor_source",
            source_ref=item["item_id"],
        )
        source_map[item["item_id"]] = source.source_id
    for item in manifest["items"]["policy_pages"]:
        source = _add_text_source(
            index,
            fixture_root,
            item,
            source_kind="policy",
            source_ref=item["item_id"],
        )
        source_map[item["item_id"]] = source.source_id
    for item in manifest["items"]["student_profiles"]:
        text = json.dumps(
            json.loads((fixture_root / item["path"]).read_text(encoding="utf-8")),
            ensure_ascii=False,
        )
        document = workspace.save_user_document(
            text.encode("utf-8"),
            f"{item['item_id']}.json",
            category="manual_inputs",
            source_type="manual_input",
            trusted=True,
            confirmed=False,
            notes=f"evaluation fixture {item['item_id']}",
        )
        source_map[item["item_id"]] = document.document_id
    index.rebuild()
    return source_map


def _add_text_source(
    index: KnowledgeBaseIndex,
    fixture_root: Path,
    item: Dict[str, Any],
    *,
    source_kind: str,
    source_ref: str,
):
    return index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind=source_kind,
            source_subtype=item.get("source_kind", ""),
            title=item["title"],
            url="",
            source_ref=source_ref,
            text=(fixture_root / item["path"]).read_text(encoding="utf-8"),
            valid_for_year=item.get("valid_for_year"),
            trusted=bool(item.get("trusted", True)),
            confirmed=bool(item.get("confirmed", False)),
            notes=f"fixture_url={item.get('source_url', '')}",
        )
    )


def _evaluate_retrieval_group(
    retriever: KnowledgeBaseRetriever,
    source_map: Dict[str, str],
    queries: Dict[str, str],
    *,
    source_kind: str,
    label: str,
    allow_external_public_query: bool,
) -> List[Dict[str, Any]]:
    results = []
    for item_id, query in queries.items():
        retrieval = retriever.search(
            query,
            source_kinds=[source_kind],
            include_unconfirmed=True,
            include_historical=False,
            as_of_year=2026,
            limit=5,
            allow_external_public_query=allow_external_public_query,
        )
        gold_source_id = source_map[item_id]
        source_ids = [hit.source_id for hit in retrieval.hits]
        rank = source_ids.index(gold_source_id) + 1 if gold_source_id in source_ids else 999
        audit = EvidenceAuditAgent().audit_evidence_bundle(retrieval.evidence_bundle)
        results.append(
            {
                "group": label,
                "item_id": item_id,
                "query": query,
                "gold_source_id": gold_source_id,
                "top_source_id": source_ids[0] if source_ids else "",
                "rank": rank,
                "hit_count": len(retrieval.hits),
                "recall_at_5": rank <= 5,
                "mrr": _reciprocal_rank(rank),
                "citation_correct_at_1": bool(source_ids and source_ids[0] == gold_source_id),
                "source_diversity_at_5": len(set(source_ids)),
                "evidence_bundle_id": retrieval.evidence_bundle.bundle_id,
                "bundle_claim_count": len(retrieval.evidence_bundle.claims),
                "bundle_conflict_count": len(retrieval.evidence_bundle.conflicts),
                "audit_passed": audit.passed,
                "top_titles": [hit.title for hit in retrieval.hits[:3]],
                "top_scores": [hit.score for hit in retrieval.hits[:3]],
            }
        )
    return results


def _evaluate_email_signals(
    fixture_root: Path,
    manifest: Dict[str, Any],
    workspace: Workspace,
) -> List[Dict[str, Any]]:
    results = []
    for item in manifest["items"]["email_signals"]:
        raw_text = (fixture_root / item["path"]).read_text(encoding="utf-8")
        result = import_email_signal_candidates(
            workspace,
            "gmail",
            raw_text,
            targets=[],
            applications=[],
            advisors=[],
        )
        signal_type = result.candidates[0].signal_type if result.candidates else ""
        expected = EMAIL_EXPECTED[item["item_id"]]
        results.append(
            {
                "item_id": item["item_id"],
                "expected_signal_type": expected,
                "actual_signal_type": signal_type,
                "passed": signal_type == expected,
                "candidate_count": len(result.candidates),
            }
        )
    return results


def _evaluate_expired_policy_rejection(
    workspace: Workspace,
    storage_backend: str,
    reranker_name: str,
    embedding_provider: EmbeddingProvider,
) -> Dict[str, Any]:
    index = KnowledgeBaseIndex(
        workspace,
        storage_backend=storage_backend,
        embedding_provider=embedding_provider,
    )
    source = index.add_source(
        KnowledgeBaseSourceCreate(
            source_kind="policy",
            title="2025 过期推免截止日期样本",
            source_ref="expired_policy_probe",
            text="2025 年推免报名截止日期为 2025 年 9 月 1 日。",
            valid_for_year=2025,
            trusted=True,
            confirmed=True,
        )
    )
    index.rebuild()
    retriever = _make_eval_retriever(workspace, storage_backend, reranker_name, embedding_provider)
    current = retriever.search(
        "2025 推免报名截止日期",
        source_kinds=["policy"],
        include_historical=False,
        as_of_year=2026,
        limit=5,
        allow_external_public_query=True,
    )
    historical = retriever.search(
        "2025 推免报名截止日期",
        source_kinds=["policy"],
        include_historical=True,
        as_of_year=2026,
        limit=5,
        allow_external_public_query=True,
    )
    current_sources = [hit.source_id for hit in current.hits]
    historical_sources = [hit.source_id for hit in historical.hits]
    return {
        "probe_source_id": source.source_id,
        "current_hit_count": len(current.hits),
        "historical_hit_count": len(historical.hits),
        "blocked_from_current": source.source_id not in current_sources,
        "available_when_historical": source.source_id in historical_sources,
        "passed": source.source_id not in current_sources
        and source.source_id in historical_sources,
    }


def _evaluate_rejected_student_leakage(
    workspace: Workspace,
    storage_backend: str,
    reranker_name: str,
    embedding_provider: EmbeddingProvider,
) -> Dict[str, Any]:
    rejected_document = workspace.save_user_document(
        "项目：已否认的量子计算顶会论文。".encode("utf-8"),
        "rejected_project.txt",
        category="research_projects",
        source_type="local_upload",
        trusted=True,
        confirmed=False,
        notes="rejected leakage probe",
    )
    profile = StudentProfile(
        name="匿名学生 rejected probe",
        projects=["已否认的量子计算顶会论文"],
        confirmation_map={"projects": "rejected"},
        evidence_map={"projects": [rejected_document.document_id]},
    )
    index = KnowledgeBaseIndex(
        workspace,
        storage_backend=storage_backend,
        embedding_provider=embedding_provider,
    )
    index.rebuild()
    retrieval = _make_eval_retriever(
        workspace,
        storage_backend,
        reranker_name,
        embedding_provider,
    ).search(
        "量子计算 顶会论文",
        source_kinds=["student_document"],
        include_unconfirmed=True,
        profile=profile,
        limit=5,
    )
    leaked = any(hit.source_id == rejected_document.document_id for hit in retrieval.hits)
    return {
        "rejected_source_id": rejected_document.document_id,
        "hit_count": len(retrieval.hits),
        "leaked": leaked,
        "passed": not leaked,
    }


def _evaluate_audit_feedback_loop(workspace: Workspace) -> Dict[str, Any]:
    bundle = EvidenceBundle(
        query="过期政策反馈探针",
        retrieval_refs=["expired_policy_probe#chunk_1"],
        claims=[
            Claim(
                claim_key="policy.deadline",
                claim_type="policy_fact",
                text="旧年度政策被召回。",
                status="stale",
                source_refs=["expired_policy_probe#chunk_1"],
                needs_confirmation=True,
            )
        ],
    )
    audit = EvidenceAuditAgent().audit_evidence_bundle(bundle)
    feedback = record_evidence_audit_feedback(workspace, audit, bundle=bundle)
    feedback_records = LocalMemoryManager(workspace).search("", kinds=["feedback"])
    candidates = workspace.list("procedural_candidates")
    return {
        "audit_passed": audit.passed,
        "feedback_memory_count": len(feedback_records),
        "procedural_candidate_count": len(candidates),
        "feedback_candidate_created": bool(
            feedback.feedback_memory_ids and feedback.procedural_candidate_ids
        ),
    }


def _rate(values) -> float:
    values = list(values)
    return round(sum(1 for value in values if value) / len(values), 4) if values else 0.0


def _reciprocal_rank(rank: int) -> float:
    return round(1 / rank, 4) if rank and rank < 999 else 0.0


def _make_eval_retriever(
    workspace: Workspace,
    storage_backend: str,
    reranker_name: str,
    embedding_provider: EmbeddingProvider,
) -> KnowledgeBaseRetriever:
    return KnowledgeBaseRetriever(
        workspace,
        storage_backend=storage_backend,
        embedding_provider=embedding_provider,
        reranker=_make_reranker(reranker_name),
    )


def _make_reranker(reranker_name: str) -> Reranker:
    if reranker_name == "lexical":
        return LexicalReranker()
    if reranker_name == "noop":
        return NoopReranker()
    if reranker_name in {"env", "siliconflow", "api", "local"}:
        env = dict(os.environ)
        if reranker_name != "env":
            env["RAG_RERANKER"] = reranker_name
        return configured_reranker_from_env(env)
    raise ValueError(f"Unsupported evaluation reranker: {reranker_name}")


def _make_embedding_provider(embedding_provider_name: str) -> EmbeddingProvider:
    if embedding_provider_name == "hash":
        return HashEmbeddingProvider()
    if embedding_provider_name in {"env", "siliconflow", "api", "local"}:
        env = dict(os.environ)
        if embedding_provider_name != "env":
            env["RAG_EMBEDDING_PROVIDER"] = embedding_provider_name
        return configured_embedding_provider_from_env(env)
    raise ValueError(f"Unsupported evaluation embedding provider: {embedding_provider_name}")


def _reset_eval_workspace(path: Path) -> None:
    path = path.resolve()
    if not path.exists():
        return
    temp_root = Path(tempfile.gettempdir()).resolve()
    is_temp = temp_root in path.parents
    is_named_eval = path.name.startswith("workspace.eval") or any(
        part.startswith("workspace.eval") for part in path.parts
    )
    if not is_temp and not is_named_eval:
        raise ValueError(f"Refusing to reset non-evaluation workspace: {path}")
    shutil.rmtree(path)
