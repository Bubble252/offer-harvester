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
- verified public policy/advisor sample seed metadata, stored as URL + summary + authority fields rather than full page bodies
- optional TRL `SFTTrainer` LoRA training path with HuggingFace Trainer fallback
- optional TRL `DPOTrainer` LoRA training path from `preference_pairs.jsonl`
- Qwen 0.5B LoRA smoke training result under ignored `workspace/`

Not implemented in this stage:

- production-quality model training
- GRPO training
- Ray/vLLM
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
  --replace-public-kb-seed \
  --include-real-public-samples
```

Prepare a default Qwen 0.5B LoRA dry run:

```bash
python tools/train_agentic_rl.py
```

Run offline Agentic RL evaluation:

```bash
python tools/evaluate_agentic_rl.py
```

Check optional training dependencies:

```bash
python tools/train_agentic_rl.py --check-deps
```

Start local SFT only after installing the optional ML stack and explicitly
allowing training:

```bash
python tools/train_agentic_rl.py \
  --mode sft \
  --allow-actual-training \
  --trainer-backend trl-sft \
  --max-steps 3 \
  --max-seq-length 512 \
  --batch-size 1 \
  --grad-accum 2
```

Prepare a default DPO dry run from preference pairs:

```bash
python tools/train_agentic_rl.py --mode dpo
```

Start local DPO only after installing the optional ML stack and explicitly
allowing training:

```bash
python tools/train_agentic_rl.py \
  --mode dpo \
  --allow-actual-training \
  --trainer-backend trl-dpo \
  --max-steps 3 \
  --max-seq-length 512 \
  --learning-rate 5e-6 \
  --batch-size 1 \
  --grad-accum 2
```

The exporter writes:

- `trajectories.jsonl`
- `sft_messages.jsonl`
- `preference_pairs.jsonl`
- `grpo_rollouts.jsonl`
- `dataset_manifest.json`
- `dataset_report.json`

The training dry run writes:

- `train.jsonl`
- `valid.jsonl`
- `test.jsonl`
- `training_config.json`
- `training_manifest.json`
- `report.md`

The real SFT smoke run additionally writes:

- `adapter/adapter_model.safetensors`
- `trainer/checkpoint-*/trainer_state.json`
- `base_vs_adapter_eval.json`
- `base_vs_adapter_eval.md`
- `training_result.json`
- `training_result.md`

The real DPO smoke run additionally writes:

- `adapter/adapter_model.safetensors`
- `trainer/checkpoint-*/trainer_state.json`
- `sft_dpo_eval.json`
- `sft_dpo_eval.md`
- `training_result.json`
- `training_result.md`

The offline evaluator writes:

- `agentic_rl_evaluation.json`
- `agentic_rl_evaluation.md`

## Cloud Boundary

Only records from `PublicKBStore` are eligible for Supabase sync. The public KB
schema contains source metadata, record metadata, chunk text, and optional
vector columns. Private profile facts, uploaded resumes, transcripts, API keys,
and raw student documents must remain local.

If live sync is needed, set `PUBLIC_KB_DATABASE_URL` in an ignored local env file
or run the generated SQL in Supabase SQL Editor. Do not commit local env files or
SQL dumps containing private data.

## Training Boundary

The current implementation can prepare data and run small local SFT and DPO
smoke trains. Positive SFT rows are filtered by acceptance/reward. Weaker
outputs are preserved in preference and rollout files, so DPO can learn from
chosen/rejected boundaries and future GRPO experiments can learn from grouped
rollouts instead of treating every output as a target.

The default local training target is `Qwen/Qwen2.5-0.5B-Instruct` with LoRA
`r=8`, `alpha=16`, and adapter-only output. This is intended for an 8 GB GPU
smoke test. Larger models, GRPO, Ray, and vLLM remain optional future paths.

The first verified smoke result used 306 trajectories and 153 SFT rows. TRL
SFTTrainer completed 3 optimizer steps and produced a loadable adapter plus a
base-vs-adapter smoke report. The report uses a lightweight lexical heuristic;
it proves training and loading, not final application quality.

The first verified DPO smoke result used 153 preference pairs, split into
123/15/15 train/validation/test rows. TRL DPOTrainer completed 3 optimizer
steps and produced a loadable DPO adapter plus an SFT-vs-DPO-vs-base smoke
report. The smoke eval used 2 rows; base, SFT adapter, and DPO adapter all
scored 0.15 with the lightweight heuristic, so this proves the DPO loop can run
and be compared, not that quality improved.

Generated evaluation outputs are privacy-scanned and masked before report
storage. This matters because base models can hallucinate phone-like or
key-like strings even when the training data itself is clean.

The first optimization scene is:

```text
RAG Query Planner -> Evidence Retrieval -> EvidenceAudit -> Audit Fix -> RewardV2
```

This scene is intentionally public-data first because it has clearer reward
signals and lower privacy risk than direct personal-material generation.

## Training Roadmap

The agreed order is:

1. offline evaluation runner
2. more real public policy/advisor samples
3. TRL `SFTTrainer`
4. Qwen 0.5B LoRA smoke train
5. base vs adapter smoke report, then API/rule baselines
6. TRL `DPOTrainer`
7. TRL `GRPOTrainer`

Heavy ML packages are optional. Install them only in a training environment:

```bash
python3.10 -m venv workspace/.venv-train
workspace/.venv-train/bin/python -m pip install -U pip
workspace/.venv-train/bin/python -m pip install \
  'torch>=2.5,<2.6' \
  'transformers>=4.46,<4.47' \
  'peft>=0.13,<0.14' \
  'accelerate>=0.34' \
  'datasets>=2.21' \
  'trl>=0.12,<0.13' \
  'pydantic>=2,<3'
```

These pins matter because newer TRL/Transformers/PEFT combinations can require
distributed tensor APIs that are not available in the local CUDA stack.

The default app install still avoids torch, TRL, and model downloads.
