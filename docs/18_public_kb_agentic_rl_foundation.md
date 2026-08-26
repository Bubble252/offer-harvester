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
- 55 official-domain public policy/advisor metadata candidates, stored as URL + summary + authority fields rather than full page bodies
- source-disjoint task-level generated evaluation with EvidenceAudit and privacy hard gates
- optional TRL `SFTTrainer` LoRA training path with HuggingFace Trainer fallback
- optional TRL `DPOTrainer` LoRA training path from `preference_pairs.jsonl`
- optional TRL `GRPOTrainer` LoRA training path from `grpo_rollouts.jsonl`
- one controlled Qwen 0.5B LoRA SFT -> DPO -> GRPO candidate run under ignored `workspace/`
- grouped RAG regression metrics for teacher pages, policy pages, and private student fixtures
- optional local PaddleOCR precheck adapter with manual-text fallback and candidate-only profile extraction
- RewardV2 citation correctness, factuality, source-authority, and conflict terms with hard gates for failed citation/factuality

Not implemented in this stage:

- production-quality model training
- production deployment or online policy rollout
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

Run the source-disjoint generated task evaluator after each stage. It evaluates
the base model and supplied adapters with the same fixed held-out sources, then
enforces SFT/DPO/GRPO stage gates:

```bash
workspace/.venv-train/bin/python tools/evaluate_agentic_rl_task_level.py \
  --dataset-dir workspace.eval/agentic_rl_usability_control/rl/usability_dataset \
  --output-dir workspace/rl/evaluations/candidate_task_level \
  --sft-adapter workspace/rl/training_runs/<sft-run>/adapter \
  --dpo-adapter workspace/rl/training_runs/<dpo-run>/adapter \
  --grpo-adapter workspace/rl/training_runs/<grpo-run>/adapter \
  --min-valid-sources 2 \
  --min-test-sources 10 \
  --max-cases 120 \
  --prompt-format instruction
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

The training path is local, opt-in, and adapter-only. It uses
`Qwen/Qwen2.5-0.5B-Instruct` with LoRA `r=8`, `alpha=16` in an isolated Python
environment. The application does not import `torch`, load an adapter, or make
an Agentic RL model its default runtime.

Positive SFT rows require accepted, evidence-safe outputs. DPO retains weaker
chosen/rejected pairs, and GRPO retains grouped rollout references. Generated
answers are privacy-scanned and pass EvidenceAudit before they can receive a
positive task-level result.

## Controlled Candidate Experiment

On August 26, 2026, the project completed a second controlled
`SFT -> DPO -> GRPO` candidate sequence. The optimization scene is:

```text
QueryPlanner -> Retriever -> EvidenceAudit -> Audit Fix -> RewardV2 -> SafetyGate
```

All source data are public, official-domain summary metadata. The system stores
URL, publisher, authority, year, short summary, and hash only. It does not
store web-page bodies, private student information, API keys, or automatically
promote facts into product state.

| Item | Result |
| --- | --- |
| Public policy/advisor metadata candidates | 55 across 18 target institutions |
| Important source caveat | Candidates are not a claim that 55 page bodies were live-verified |
| Task types | `rag_query_plan`, `evidence_audit_fix`, `policy_advisor_qa` |
| Candidate groups / trajectories | 660 / 2,640 |
| SFT / DPO / GRPO rows | 660 / 660 / 660 |
| Per-task source-disjoint split | train/valid/test = `160/20/40` |
| Held-out task evaluator | 120 cases from 10 unseen source records |
| SFT run | 360 steps; completion-only labels; loss `0.2694`; peak VRAM `1.892/2.070 GiB` allocated/reserved |
| Conservative DPO run | 60 steps from SFT; `lr=2e-7`, `beta=0.0005`; peak VRAM `1.688/2.045 GiB` |
| Conservative GRPO run | 30 steps from DPO; 2 generations, `lr=2e-7`, `beta=0.01`, temperature `0.4`; peak VRAM `1.506/1.777 GiB` |

The final evaluator uses generated model answers rather than reference-text
overlap. It checks protocol fields, official-source and year boundaries,
query/audit actions, EvidenceAudit, privacy, unsupported policy detail, and
unsupported dates or counts. The latter categories are hard failures.

| Variant | Avg task score | Pass rate | Hard failures |
| --- | ---: | ---: | ---: |
| Base Qwen | `0.1529` | `0.0000` | 58 |
| Completion-only SFT | `1.0000` | `1.0000` | 0 |
| Conservative DPO | `1.0000` | `1.0000` | 0 |
| Conservative GRPO | `1.0000` | `1.0000` | 0 |

The automatic stage gates all passed:

1. SFT exceeded the base threshold.
2. DPO met the absolute safety gate and did not regress from SFT.
3. GRPO met the absolute safety gate and did not regress from DPO.

The GRPO adapter is therefore the current **explicit, controlled candidate**
for public RAG query-planning and EvidenceAudit repair experiments. It remains
blocked from automatic fact adoption, profile/tracker writes, email sending,
policy assertions, and the default LLM runtime. Retriever, EvidenceAudit,
policy-validity checks, and user confirmation remain mandatory.

## Limits And Next Experiment

This result is stronger than the earlier smoke tests because it uses a
source-disjoint generated task evaluator with hard safety gates. It is still
not production-quality evidence:

- Held-out sources use the same public-metadata task protocol, so the benchmark
  can be saturated by a model that consistently follows that protocol.
- The 30-step GRPO run reported zero within-group reward standard deviation.
  The adapter weights changed, but this does not establish a distinct
  reinforcement-learning gain over DPO.
- No live web-page body collection, human preference labels, real user
  outcomes, or external LLM judge was used.

Before increasing model size, steps, or making any runtime selection, the next
experiment must add independently authored policy/teacher page samples,
human-reviewed chosen/rejected traces, reward-diverse model rollouts, and a
separate semantic or human evaluation set. The earlier smoke experiments remain
historical pipeline checks only and are superseded by this candidate report.

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
