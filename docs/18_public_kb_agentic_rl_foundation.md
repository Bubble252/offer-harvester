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
- 17 verified public policy/advisor metadata samples across 2026 historical regression records and a 2027 current-cycle notice
- optional TRL `SFTTrainer` LoRA training path with HuggingFace Trainer fallback
- optional TRL `DPOTrainer` LoRA training path from `preference_pairs.jsonl`
- optional TRL `GRPOTrainer` LoRA training path from `grpo_rollouts.jsonl`
- one controlled, source-disjoint Qwen 0.5B LoRA SFT -> DPO -> GRPO run under ignored `workspace/`
- grouped RAG regression metrics for teacher pages, policy pages, and private student fixtures
- optional local PaddleOCR precheck adapter with manual-text fallback and candidate-only profile extraction
- RewardV2 citation correctness, factuality, source-authority, and conflict terms with hard gates for failed citation/factuality

Not implemented in this stage:

- production-quality model training
- production GRPO training or online policy rollout
- Ray/vLLM
- MongoDB/Redis/Kubernetes
- private student data upload
- automatic policy fact creation without official source evidence
- automatic confirmation or profile writes from OCR output

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
./.venv/bin/python tools/build_agentic_rl_dataset.py \
  --workspace ./workspace \
  --replace-public-kb-seed \
  --include-real-public-samples
```

Collect replayable traces through the public-only RAG/Audit/Reward harness:

```bash
PYTHONPATH=app/backend ./.venv/bin/python tools/collect_agentic_rl_rollouts.py \
  --workspace ./workspace.eval/agentic_rl_rollouts \
  --output-dir ./workspace.eval/formal_public_rollout_v1/rl/train_ready
```

Check the formal training gate. It requires public summary-only provenance,
source-disjoint splits, 15+ source records, 50+ training rows per task, three
reward-diverse candidates per GRPO group, complete agent traces, and no
privacy-pattern hits:

```bash
PYTHONPATH=app/backend ./.venv/bin/python tools/check_agentic_rl_readiness.py \
  --dataset-dir ./workspace.eval/formal_public_rollout_v1/rl/train_ready
```

Prepare a default Qwen 0.5B LoRA dry run:

```bash
python tools/train_agentic_rl.py
```

Run offline Agentic RL evaluation:

```bash
./.venv/bin/python tools/evaluate_agentic_rl.py
```

Run deterministic RAG and memory regression evaluation:

```bash
./.venv/bin/python tools/evaluate_rag_memory.py \
  --workspace ./workspace.eval \
  --storage-backend sqlite \
  --embedding-provider hash \
  --reranker noop
```

The RAG report records Recall@1/3/5, MRR, citation correctness@1,
EvidenceAudit pass rate, privacy safety, rejected-field leakage, expired-policy
rejection, and per-group metrics for teacher, policy, and student fixtures.

OCR is exposed as `POST /api/ocr/precheck`. It accepts a local source file and
optionally manually pasted OCR text. When the optional PaddleOCR dependency is
not installed, the endpoint returns an explicit unavailable state rather than
falling back to a remote service. Any detected profile values are stored only
as `ProfileExpansionCandidate` records with `unconfirmed` status.

The optional adapter accepts standard PaddleOCR result structures. PaddleOCR is
not installed by default: on August 26, 2026, this workspace had roughly
9.6 GB free, below the project's 30 GB local-model/OCR safety threshold. The
zero-dependency path retains the local original file and accepts manually
pasted OCR text for candidate extraction.

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

Prepare a default GRPO dry run from rollout groups:

```bash
python tools/train_agentic_rl.py --mode grpo
```

Start local GRPO only after installing the optional ML stack and explicitly
allowing training:

```bash
python tools/train_agentic_rl.py \
  --mode grpo \
  --allow-actual-training \
  --trainer-backend trl-grpo \
  --max-steps 3 \
  --max-prompt-length 384 \
  --max-completion-length 64 \
  --grpo-num-generations 2 \
  --grpo-temperature 0.7 \
  --learning-rate 1e-6 \
  --batch-size 2 \
  --grad-accum 1
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

The real GRPO smoke run additionally writes:

- `adapter/adapter_model.safetensors`
- `trainer/checkpoint-*/trainer_state.json`
- `sft_dpo_grpo_eval.json`
- `sft_dpo_grpo_eval.md`
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

The current implementation can prepare data and run small local SFT, DPO, and
GRPO smoke trains. Positive SFT rows are filtered by acceptance/reward. Weaker
outputs are preserved in preference and rollout files, so DPO can learn from
chosen/rejected boundaries and GRPO can learn from generated completions scored
against grouped rollout references instead of treating every output as a target.

The default local training target is `Qwen/Qwen2.5-0.5B-Instruct` with LoRA
`r=8`, `alpha=16`, and adapter-only output. This is intended for an 8 GB GPU
smoke test. Larger models, Ray, and vLLM remain optional future paths.

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

The first verified GRPO smoke result used 153 rollout groups, split into
123/15/15 train/validation/test rows. TRL GRPOTrainer completed 3 optimizer
steps with `num_generations=2`, `max_completion_length=64`, and a lightweight
reference reward derived from the best stored rollout in each group. The smoke
eval used 2 rows; base, DPO adapter, and GRPO adapter scored 0.24, while the
SFT adapter scored 0.2045. This proves the GRPO loop can train, save, load, and
compare adapters, not that the adapter is ready for production.

Generated evaluation outputs are privacy-scanned and masked before report
storage. This matters because base models can hallucinate phone-like or
key-like strings even when the training data itself is clean.

The latest reproducible public-KB rebuild creates 342 trajectories from 60
university entities plus 17 public policy/advisor metadata records. It exports
171 SFT rows, 171 preference pairs, and 171 GRPO rollout groups. The rollout
set deliberately retains 171 rejected candidates: the evaluator should observe
hard failures for unsupported citations, false facts, expired policy use, and
rejected facts. This is expected negative supervision, not a model-quality
result.

## First Controlled Training Result

On August 26, 2026, the project completed its first controlled local
SFT -> DPO -> GRPO run on a source-disjoint, public-only rollout dataset. The
collector executed the existing deterministic agent chain:

```text
QueryPlanner -> Retriever -> EvidenceAudit -> EvidenceAuditFix -> RewardV2 -> SafetyGate
```

The source material contains metadata and summaries only. It does not store
web-page bodies, call an LLM, or automatically promote retrieved facts into
product state.

| Item | Result |
| --- | --- |
| Public policy/advisor source records | 17 |
| Task types | `rag_query_plan`, `evidence_audit_fix`, `policy_advisor_qa` |
| Scenarios per source/task | 4 |
| Candidate groups / candidates | 204 / 612 |
| SFT rows | 408; source-disjoint split `360/24/24` |
| DPO pairs | 204; source-disjoint split `180/12/12` |
| GRPO groups | 204; source-disjoint split `180/12/12` |
| Candidate rollouts per GRPO group | 3, with reward spread |
| Feedback-memory records from audit issues | 153 |

Formal readiness passed before training. The first run used
`Qwen/Qwen2.5-0.5B-Instruct`, LoRA `r=8`, `alpha=16`, cached local weights,
an RTX 4060 Laptop GPU with 8 GB VRAM, and adapter-only output:

| Phase | Steps | Initialization | Lightweight held-out result |
| --- | ---: | --- | --- |
| SFT | 24 | base Qwen | `0.1937 -> 0.3465` |
| DPO | 24 | SFT adapter | base/SFT/DPO = `0.2069 / 0.3463 / 0.3836` |
| GRPO | 16 | DPO adapter | base/SFT/DPO/GRPO = `0.2319 / 0.3713 / 0.4169 / 0.3845` |

SFT loss decreased from `4.6324` to `2.8007`. DPO completed with a clear
chosen/rejected separation, but that pair set is intentionally easy and should
not be treated as a general preference-quality score. GRPO completed after the
LoRA gradient-checkpoint initialization was fixed; the first two logged
gradient norms were `NaN`, then subsequent steps were finite. Its lightweight
score was lower than the DPO adapter by `0.0324`, so the DPO adapter is the
current experimental candidate and the GRPO adapter must not be selected by
default.

These outputs prove the controlled training sequence, adapter handoff,
privacy gate, source-disjoint split, save/load path, and evaluation reporting.
They do **not** prove production quality. The evaluation is a lightweight
lexical/reference heuristic and the collector uses deterministic harness
rollouts rather than model-generated online rollouts.

The post-training offline evaluator intentionally keeps promotion conservative:
on the same 612 trajectories, it reported 204 citation-incorrect candidates,
204 factuality-failed candidates, and 51 expired-policy violations in the
negative/needs-review population. Its recommendation was
`hold_due_to_hard_failures`. This validates the hard-gate behavior and means
that no adapter is promoted to the application's default model from this run.
The next experiment must improve the source-grounded evaluator and data
quality before increasing training scale.

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

Steps 1-7 now have one controlled local run. The next training work should add
more independent public sources and human-reviewed traces, strengthen reward
functions, add a semantic/task-level evaluator, and run fixed regression
evaluation before increasing steps or model size. The DPO adapter remains the
baseline candidate until a later experiment beats it on those stronger gates.

## Current Evaluation Baseline

The deterministic `hash-local` embedding plus `noop` reranker run on the fixed
15-case RAG/memory regression set produced:

| Metric | Result |
| --- | ---: |
| Recall@1 / @3 / @5 | 0.9333 / 1.0000 / 1.0000 |
| MRR | 0.9556 |
| Citation correctness@1 | 0.9333 |
| EvidenceAudit pass rate | 1.0000 |
| Privacy safety | 1.0000 |
| Expired-policy rejection | 1.0000 |
| Rejected-profile leakage | 0.0000 |

Teacher and policy groups each reached top-1 recall of 1.0. The private student
group reached top-1 recall of 0.8, so the local hash/noop baseline remains a
regression guard only. Any default change to an API embedding or reranker
provider must compare these group-level figures and preserve the local-only
route for private materials.

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
  'trl>=0.15,<0.16' \
  'pydantic>=2,<3'
```

These pins matter because `trl>=0.15` is needed for GRPOTrainer while newer
TRL/Transformers/PEFT combinations can require distributed tensor APIs that are
not available in the local CUDA stack.

The default app install still avoids torch, TRL, and model downloads.
