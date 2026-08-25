# Public KB and Agentic RL Foundation

This document records the first train-ready implementation for the public
admissions knowledge base and Agentic RL data layer.

## Scope

Implemented now:

- local `PublicAdmissionsKnowledgeBase` schema under `workspace/public_kb/`
- all 985 universities plus the first strong 211/specialized target list as public entity records
- Supabase/Postgres + pgvector schema and dry-run sync adapter
- SQL dump output for schema plus public KB upserts
- `AgentTrajectory`, `RewardV2`, SFT/DPO/GRPO-style JSONL export
- deterministic QueryPlanner, EvidenceAuditFix, RewardJudge, TrajectoryBuilder and SafetyGate agent protocols

Not implemented in this stage:

- real model training
- torch/TRL/Ray/vLLM
- MongoDB/Redis/Kubernetes
- private student data upload
- automatic policy fact creation without official source evidence

## Commands

Seed and validate the public KB:

```bash
python tools/sync_public_kb.py \
  --workspace ./workspace \
  --seed-target-universities \
  --replace
```

Generate Supabase/Postgres SQL without connecting to the cloud database:

```bash
python tools/sync_public_kb.py \
  --workspace ./workspace \
  --seed-target-universities \
  --data-sql-out ./workspace/public_kb/supabase_public_kb.sql
```

Build train-ready Agentic RL data:

```bash
python tools/build_agentic_rl_dataset.py \
  --workspace ./workspace \
  --replace-public-kb-seed
```

The exporter writes:

- `trajectories.jsonl`
- `sft_messages.jsonl`
- `preference_pairs.jsonl`
- `grpo_rollouts.jsonl`
- `dataset_manifest.json`
- `dataset_report.json`

## Cloud Boundary

Only records from `PublicKBStore` are eligible for Supabase sync. The public KB
schema contains source metadata, record metadata, chunk text, and optional
vector columns. Private profile facts, uploaded resumes, transcripts, API keys,
and raw student documents must remain local.

If live sync is needed, set `PUBLIC_KB_DATABASE_URL` in an ignored local env file
or run the generated SQL in Supabase SQL Editor. Do not commit local env files or
SQL dumps containing private data.

## Training Boundary

The current implementation prepares data for later training but does not train
weights. Positive SFT rows are filtered by acceptance/reward. Weaker outputs are
preserved in preference and rollout files, so future DPO/GRPO experiments can
learn from contrastive outcomes instead of treating every output as a target.

The first optimization scene is:

```text
RAG Query Planner -> Evidence Retrieval -> EvidenceAudit -> Audit Fix -> RewardV2
```

This scene is intentionally public-data first because it has clearer reward
signals and lower privacy risk than direct personal-material generation.
