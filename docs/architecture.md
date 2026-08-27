# Architecture

[简体中文](architecture.zh-CN.md)

## System Boundary

Offer Harvester is a local-first control plane. The browser, external agents, optional
providers, and future workers are clients or adapters; they do not become the source of truth.

```text
Browser / Skill Lab / optional DSH plugin
                    |
                    v
            FastAPI control plane
                    |
      +-------------+-------------+
      |             |             |
  Agent workflow  RAG + evidence  Memory + feedback
      |             |             |
      +-------------+-------------+
                    |
          Local workspace storage
```

The control plane owns:

- profile and original-document persistence
- field-level confirmation state
- advisor and policy evidence
- candidate material lifecycle
- EvidenceAudit and quality gates
- memory promotion decisions
- application tracker and user-approved state changes
- privacy routing and no-send behavior

## Module Map

| Area | Location | Responsibility |
| --- | --- | --- |
| API and control plane | `app/backend/main.py` | FastAPI routes, dependency wiring, OpenAPI |
| Domain models | `app/backend/models.py` | Pydantic records and request/response shapes |
| Workspace | `app/backend/storage.py` | Local JSON/file persistence and manifests |
| Agent workflow | `app/backend/agents/` | Draft, review, audit, advisor, match, and SWARM protocols |
| RAG | `app/backend/rag/` | Chunking, embeddings, retrieval, reranking, evidence bundles |
| Memory | `app/backend/memory.py` | Layered memory lifecycle and promotion candidates |
| Quality | `app/backend/quality/` | Material checks and risk findings |
| Skills | `skills/`, `app/backend/skill_*.py` | Portable contracts, product adapters, Skill Lab execution |
| Integrations | `integrations/` | Neutral adapters and optional external runtimes |
| Frontend | `app/frontend/` | Local browser workspace and product Skill UI |
| Tools | `tools/` | Demo seeders, evaluations, lint, safety, and release checks |

## Request Lifecycle

```text
Frontend or adapter request
-> FastAPI request model
-> domain service / Agent workflow
-> RAG and EvidenceBundle when needed
-> reviewer and EvidenceAudit
-> candidate result + trace
-> user confirmation
-> controlled workspace write
```

An adapter may request a candidate or report. It may not directly import storage internals
to mutate confirmed profile, tracker, final materials, public knowledge, or promoted memory.

## Agent Boundaries

The core material path is:

```text
MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent
```

SWARM is a controlled parallel protocol for tasks that have independent evidence slices,
such as advisor-source extraction and retrieval evaluation. It is not a reason to split
simple CRUD or field updates into separate agents. A future pi-agent or DeepSeek Harness
runtime can execute a bounded subtask through an adapter; Python remains the orchestrator.

## Data Ownership

- `workspace/` is the local source of truth for user data and runtime records.
- `workspace.example/` and `workspace.demo/` are synthetic examples only.
- Public knowledge records preserve source metadata, timestamps, hashes, validity, and
  evidence references. Historical or unconfirmed information is not silently promoted.
- Markdown, HTML, PPTX, and reports are derived views. They do not override structured state.

## Optional Heavy Components

The default stack uses local files, deterministic fallbacks, and lightweight adapters.
SQLite/FTS, Chroma, Milvus, Redis, MongoDB, PaddleOCR, local PyTorch models, ViT,
vLLM, and Kubernetes remain replaceable extensions. Each must preserve evidence references,
privacy routing, cancellation, fallback behavior, and user confirmation.
