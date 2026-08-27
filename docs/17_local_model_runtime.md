# Local Model Runtime Plan

This project stays lightweight by default, but keeps optional local model adapters for private data and offline experiments.

## Current Machine Baseline

Checked on 2026-08-25:

- CPU: Intel Core i9-14900HX, 32 threads
- Memory: 32GB
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU, 8GB VRAM
- CUDA runtime shown by `nvidia-smi`: 12.8
- Main project disk: nearly full at the time of diagnosis

The immediate blocker for local models is disk space, not GPU capability. As of
August 26, 2026, this workspace has roughly 9.6GB free. Downloading models or
enabling Chroma/PaddleOCR should wait until at least 30GB is free. 80GB+ is
safer.

## Default Path

The default runtime remains:

- OpenAI-compatible API only when explicitly configured
- `HashEmbeddingProvider` fallback
- JSON/SQLite local RAG storage
- lexical or noop reranker
- no `torch`, `transformers`, `PaddleOCR`, vLLM, Milvus, MongoDB, or Redis in the main dependency path

## Optional Local Path

Supported by adapter skeletons:

- `LocalOpenAICompatibleLLMProvider`
- `LocalOpenAICompatibleEmbeddingProvider`
- `LocalOpenAICompatibleReranker`
- `tools/diagnose_local_models.py`

Recommended local services:

- Ollama
- LM Studio
- Xinference
- llama.cpp server

Recommended model scale for 8GB VRAM:

- Qwen 1.5B / 3B / 7B quantized models
- BGE small/base embedding
- lightweight reranker
- small-batch PaddleOCR later, behind an optional adapter

Not recommended on this machine as the default path:

- Milvus multi-service deployment
- vLLM high-concurrency serving
- Qwen 14B+ without aggressive quantization
- batch ViT PPT visual analysis
- Ray/FSDP/RL training

## Environment Variables

```bash
RAG_EMBEDDING_PROVIDER=hash
RAG_RERANKER=noop

LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen2.5:7b-instruct-q4
LOCAL_LLM_API_KEY=
LOCAL_LLM_WIRE_API=chat

LOCAL_EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_EMBEDDING_MODEL=bge-small
LOCAL_EMBEDDING_DIMENSION=384
LOCAL_RERANK_BASE_URL=http://127.0.0.1:8009/v1
LOCAL_RERANK_MODEL=bge-reranker-base
```

These variables are optional. If they are absent, the project must still run through local fallback providers.

## SiliconFlow API Route

SiliconFlow can be used as an optional public API route for embedding and reranking. It is not enabled by default.

```bash
RAG_EMBEDDING_PROVIDER=siliconflow
RAG_RERANKER=siliconflow
SILICONFLOW_API_KEY=your-local-env-only-key

SILICONFLOW_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
SILICONFLOW_EMBEDDING_ENCODING_FORMAT=float
SILICONFLOW_EMBEDDING_DIMENSION=

SILICONFLOW_RERANK_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_RERANK_MODEL=BAAI/bge-reranker-v2-m3
SILICONFLOW_RERANK_RETURN_DOCUMENTS=false
```

The full operation URLs also work:

```bash
SILICONFLOW_EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1/embeddings
SILICONFLOW_RERANK_BASE_URL=https://api.siliconflow.cn/v1/rerank
```

If `SILICONFLOW_API_KEY` is missing, the project falls back to `HashEmbeddingProvider` and `NoopReranker`.

## Privacy Rule

Private user material stays local by default:

- resumes
- transcripts
- email text
- personal statements
- profile fields
- application status

Public material may use external API routes only when explicitly enabled:

- advisor public pages
- school policy pages
- official admission notices
- public lab pages

SiliconFlow should first be used for public advisor and policy sources. Private student files, pasted email text, and unconfirmed profile facts should stay on the local route unless the user explicitly allows external processing.

The adapter layer must record provider name, model name, route, and fallback reason, but must not log raw private text or API keys.

## Diagnostic Command

```bash
python tools/diagnose_local_models.py
python tools/diagnose_local_models.py --base-url http://127.0.0.1:11434/v1
```

The command checks hardware, disk space, GPU availability, and optional OpenAI-compatible `/v1/models` connectivity. It does not send user content.
