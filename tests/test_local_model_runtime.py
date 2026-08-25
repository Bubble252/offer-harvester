import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from llm_client import configured_llm_provider  # noqa: E402
from local_model_runtime import (  # noqa: E402
    LocalRuntimeEndpoint,
    check_openai_compatible_service,
    diagnose_hardware,
)
from models import RAGSearchHit  # noqa: E402
from rag import (  # noqa: E402
    ApiReranker,
    LocalOpenAICompatibleEmbeddingProvider,
    LocalOpenAICompatibleReranker,
    OpenAICompatibleEmbeddingProvider,
    PrivacyAwareEmbeddingProvider,
    PrivacyAwareReranker,
    configured_embedding_provider_from_env,
    configured_reranker_from_env,
)


def test_runtime_endpoint_accepts_full_operation_url():
    runtime = LocalRuntimeEndpoint(base_url="https://api.siliconflow.cn/v1/rerank")

    assert runtime.endpoint("/rerank") == "https://api.siliconflow.cn/v1/rerank"


def test_local_embedding_provider_parses_openai_compatible_response():
    calls = []

    def fake_request(endpoint, payload):
        calls.append((endpoint, payload))
        return {
            "data": [
                {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                {"index": 1, "embedding": [0.0, 1.0, 0.0]},
            ]
        }

    provider = LocalOpenAICompatibleEmbeddingProvider(
        base_url="http://127.0.0.1:11434/v1",
        model_name="bge-small",
        dimension=3,
        request_fn=fake_request,
    )

    vectors = provider.embed_texts(["公开政策", "导师主页"])

    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert calls[0][0] == "http://127.0.0.1:11434/v1/embeddings"
    assert calls[0][1]["model"] == "bge-small"


def test_siliconflow_embedding_provider_from_env_uses_official_shape():
    provider = configured_embedding_provider_from_env(
        {
            "RAG_EMBEDDING_PROVIDER": "siliconflow",
            "SILICONFLOW_API_KEY": "test-key",
            "SILICONFLOW_EMBEDDING_BASE_URL": "https://api.siliconflow.cn/v1/embeddings",
            "SILICONFLOW_EMBEDDING_MODEL": "BAAI/bge-m3",
            "SILICONFLOW_EMBEDDING_DIMENSION": "4",
            "SILICONFLOW_EMBEDDING_ENCODING_FORMAT": "float",
        }
    )
    calls = []

    def fake_request(endpoint, payload):
        calls.append((endpoint, payload))
        return {"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3, 0.4]}]}

    assert isinstance(provider, PrivacyAwareEmbeddingProvider)
    assert isinstance(provider.public_provider, OpenAICompatibleEmbeddingProvider)
    provider.public_provider._request_fn = fake_request

    result = provider.embed_query_for_sources(
        "推免政策",
        ["policy"],
        allow_external=True,
    )
    assert result.vector == [0.1, 0.2, 0.3, 0.4]
    assert result.route == "external_public"
    assert calls[0][0] == "https://api.siliconflow.cn/v1/embeddings"
    assert calls[0][1] == {
        "model": "BAAI/bge-m3",
        "input": ["推免政策"],
        "encoding_format": "float",
        "dimensions": 4,
    }


def test_local_reranker_reorders_hits_without_changing_content():
    def fake_request(endpoint, payload):
        assert endpoint == "http://127.0.0.1:8009/v1/rerank"
        assert payload["documents"] == ["first", "second"]
        return {
            "results": [
                {"index": 1, "relevance_score": 0.91},
                {"index": 0, "relevance_score": 0.2},
            ]
        }

    reranker = LocalOpenAICompatibleReranker(
        base_url="http://127.0.0.1:8009/v1",
        model_name="bge-reranker",
        request_fn=fake_request,
    )
    hits = [
        RAGSearchHit(source_id="s1", chunk_id="c1", snippet="first", score=0.4),
        RAGSearchHit(source_id="s2", chunk_id="c2", snippet="second", score=0.3),
    ]

    ranked = reranker.rerank("query", hits)

    assert [hit.chunk_id for hit in ranked] == ["c2", "c1"]
    assert ranked[0].snippet == "second"
    assert ranked[0].rerank_score == 0.91
    assert "local-reranker:bge-reranker" in ranked[0].retrieval_explanation


def test_siliconflow_reranker_from_env_uses_official_shape():
    reranker = configured_reranker_from_env(
        {
            "RAG_RERANKER": "siliconflow",
            "SILICONFLOW_API_KEY": "test-key",
            "SILICONFLOW_RERANK_BASE_URL": "https://api.siliconflow.cn/v1/rerank",
            "SILICONFLOW_RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
            "SILICONFLOW_RERANK_RETURN_DOCUMENTS": "false",
        }
    )
    calls = []

    def fake_request(endpoint, payload):
        calls.append((endpoint, payload))
        return {"results": [{"index": 0, "relevance_score": 0.88}]}

    assert isinstance(reranker, PrivacyAwareReranker)
    assert isinstance(reranker.public_reranker, ApiReranker)
    reranker.public_reranker._request_fn = fake_request
    hits = [
        RAGSearchHit(
            source_id="s1",
            chunk_id="c1",
            source_kind="policy",
            snippet="报名截止日期",
            score=0.4,
        )
    ]

    ranked = reranker.rerank("推免报名什么时候截止", hits)

    assert ranked[0].rerank_score == 0.88
    assert calls[0][0] == "https://api.siliconflow.cn/v1/rerank"
    assert calls[0][1] == {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": "推免报名什么时候截止",
        "documents": ["报名截止日期"],
        "top_n": 1,
        "return_documents": False,
    }


def test_siliconflow_reranker_does_not_send_private_student_hits():
    reranker = configured_reranker_from_env(
        {
            "RAG_RERANKER": "siliconflow",
            "SILICONFLOW_API_KEY": "test-key",
            "SILICONFLOW_RERANK_BASE_URL": "https://api.siliconflow.cn/v1/rerank",
            "SILICONFLOW_RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
        }
    )
    calls = []

    def fake_request(endpoint, payload):
        calls.append((endpoint, payload))
        return {"results": [{"index": 0, "relevance_score": 0.88}]}

    assert isinstance(reranker, PrivacyAwareReranker)
    assert isinstance(reranker.public_reranker, ApiReranker)
    reranker.public_reranker._request_fn = fake_request
    hits = [
        RAGSearchHit(
            source_id="private",
            chunk_id="private_chunk",
            source_kind="student_document",
            snippet="私有科研经历",
            score=0.4,
        )
    ]

    ranked = reranker.rerank("科研经历", hits)

    assert ranked[0].chunk_id == "private_chunk"
    assert ranked[0].rerank_score == 0.4
    assert calls == []


def test_configured_llm_provider_prefers_local_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen-local")

    provider = configured_llm_provider()

    assert provider.name == "local-openai-compatible"
    assert provider.model == "qwen-local"


def test_check_openai_compatible_service_with_fake_get(monkeypatch):
    def fake_urlopen(request, timeout):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"data":[{"id":"qwen-local"},{"id":"bge-small"}]}'

        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = check_openai_compatible_service(
        LocalRuntimeEndpoint(base_url="http://127.0.0.1:11434/v1")
    )

    assert result["ok"] is True
    assert result["models"] == ["qwen-local", "bge-small"]


def test_diagnose_hardware_reports_disk_and_gpu(tmp_path):
    def fake_runner(args, timeout):
        assert args[0] == "nvidia-smi"
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="NVIDIA GeForce RTX 4060 Laptop GPU, 8188, 1024, 570.190\n",
            stderr="",
        )

    report = diagnose_hardware(workspace_path=tmp_path, min_free_gb=0.01, runner=fake_runner)

    assert report["disk"]["ok_for_model_downloads"] is True
    assert report["gpu"]["available"] is True
    assert report["gpu"]["memory_total_mb"] == 8188
    assert report["recommendation"] == "quantized_1_5b_3b_7b_and_small_reranker"
