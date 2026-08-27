# RAG and Memory Evaluation Report

Date: 2026-08-25

## Scope

This report records the first deterministic evaluation baseline for the local RAG, EvidenceAudit, and memory-feedback loop.

Evaluated stack:

- Storage backend: SQLite FTS5 + local vector records
- Embedding: `HashEmbeddingProvider`
- Reranker baselines: `NoopReranker` and `LexicalReranker`
- Evidence layer: `EvidenceBundle`, source snapshots, chunk lineage, claim/link/conflict records
- Feedback layer: `EvidenceAudit -> feedback memory -> procedural candidate`

Explicitly not used:

- Chroma service, Milvus, MongoDB, Redis
- OCR, PyTorch, GPU inference, pi-agent, online RL

The original baseline did not use real embedding or reranker APIs. A follow-up SiliconFlow API run was added below as an optional comparison.

## Command

```bash
python tools/evaluate_rag_memory.py --workspace workspace.eval/noop --storage-backend sqlite --reranker noop
python tools/evaluate_rag_memory.py --workspace workspace.eval/lexical --storage-backend sqlite --reranker lexical
python tools/evaluate_rag_memory.py --workspace workspace.eval/siliconflow_real --storage-backend sqlite --embedding-provider env --reranker env
```

The evaluation workspace is ignored by Git. Use a fresh workspace per run to avoid duplicate indexed sources affecting ranking.
The CLI resets the evaluation workspace by default; use `--keep-workspace` only when intentionally debugging persisted state.

## Dataset

Fixture set: `tests/fixtures/evaluation_set`

- 5 teacher page summaries
- 5 policy page summaries
- 5 email signal fixtures
- 5 anonymous student profile fixtures

The fixtures are anonymous structural baselines. They are not a substitute for school-specific live policy pages.

## Results

| Metric | NoopReranker | LexicalReranker |
| --- | ---: | ---: |
| Retrieval cases | 15 | 15 |
| Recall@1 | 0.9333 | 0.9333 |
| Recall@3 | 1.0000 | 1.0000 |
| Recall@5 | 1.0000 | 1.0000 |
| MRR | 0.9556 | 0.9556 |
| Citation correctness@1 | 0.9333 | 0.9333 |
| Avg source diversity@5 | 3.7333 | 3.8000 |
| Expired-policy rejection rate | 1.0000 | 1.0000 |
| Rejected leakage rate | 0.0000 | 0.0000 |
| Email signal accuracy | 1.0000 | 1.0000 |
| Auditor pass rate on current bundles | 1.0000 | 1.0000 |
| Feedback candidate created | true | true |

## Interpretation

The current lightweight stack is good enough for local MVP regression:

- Gold source is found within top 5 for all fixed retrieval cases.
- Top-1 citation correctness is high on short controlled fixtures.
- Expired policy probes are blocked from current retrieval and still available when historical retrieval is explicitly enabled.
- Rejected student-document leakage is blocked.
- Email signal fixtures are classified correctly.
- EvidenceAudit failures can create feedback memory and procedural candidates without activating them.

The result does not prove production-grade RAG quality. The current fixture set is short, clean, and mostly keyword-aligned. The next meaningful upgrade is to add live or manually captured school policy pages and real teacher pages, then compare this baseline against API embeddings and API/local rerankers.

## SiliconFlow API Comparison

Configuration:

- `RAG_STORAGE_BACKEND=sqlite`
- `RAG_EMBEDDING_PROVIDER=siliconflow`
- `RAG_RERANKER=siliconflow`
- Embedding model: `BAAI/bge-m3`
- Reranker model: `BAAI/bge-reranker-v2-m3`

API probes:

- Embedding probe passed for public policy query, route `external_public`, dimension 1024.
- Rerank probe passed for public policy snippets, top result matched the deadline snippet.
- Index route check confirmed:
  - 5 advisor chunks used SiliconFlow embedding, route `external_public`.
  - 7 policy chunks used SiliconFlow embedding, route `external_public`.
  - 6 student document chunks stayed on local `hash-local`, route `local`.

| Metric | Hash + Noop baseline | SiliconFlow embedding + rerank |
| --- | ---: | ---: |
| Retrieval cases | 15 | 15 |
| Recall@1 | 0.9333 | 0.7333 |
| Recall@3 | 1.0000 | 1.0000 |
| Recall@5 | 1.0000 | 1.0000 |
| MRR | 0.9556 | 0.8444 |
| Citation correctness@1 | 0.9333 | 0.7333 |
| Avg source diversity@5 | 3.8000 | 4.4667 |
| Expired-policy rejection rate | 1.0000 | 1.0000 |
| Rejected leakage rate | 0.0000 | 0.0000 |
| Email signal accuracy | 1.0000 | 1.0000 |
| Auditor pass rate on current bundles | 1.0000 | 1.0000 |
| Feedback candidate created | true | true |

Interpretation:

- SiliconFlow API connectivity is valid.
- The privacy route is working: public advisor/policy chunks can use external embedding, student chunks remain local.
- On this small keyword-aligned fixture set, SiliconFlow improves source diversity but reduces top-1 ranking.
- Do not switch the default stack to SiliconFlow yet. Keep `hash/noop` as the deterministic regression baseline, and use SiliconFlow as an experiment on real noisy teacher and policy pages.

## Next Decision

Do not introduce Milvus, Redis, MongoDB, GPU reranker, or local PyTorch embedding yet.

Reasonable next experiments:

- Add 5-10 real 2026 policy pages from target schools.
- Add 5-10 real teacher/lab pages with noisy formatting.
- Compare `HashEmbeddingProvider` against an OpenAI-compatible embedding API on public-only sources.
- Compare `NoopReranker` / `LexicalReranker` against an API reranker or lightweight local cross-encoder.
- Track citation correctness and auditor pass rate as the main upgrade gates.

## Agentic RL Candidate Evaluation

On August 26, 2026, the public RAG Query Planner and EvidenceAudit repair
candidate was evaluated separately from this retrieval baseline. The evaluation
used 120 generated task cases from 10 source-disjoint public metadata records.
The completion-only SFT, conservative DPO, and conservative GRPO adapters each
reached a task pass rate of `1.0000` with zero hard failures; the base model
reached `0.0000` with 58 hard failures.

This does not replace the retrieval metrics above or make the adapter a default
runtime. The candidate remains restricted to public summary-metadata planning
and audit repair, with fact writes blocked and EvidenceAudit plus user
confirmation required. The GRPO run had zero within-group reward variance, so
the next iteration must add reward-diverse rollouts and independent human or
semantic evaluation before claiming reinforcement-learning benefit.
