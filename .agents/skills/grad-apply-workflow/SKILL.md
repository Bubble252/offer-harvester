---
name: grad-apply-workflow
description: Evidence-grounded graduate application workflow protocols for this repository. Use when working on student profile intake, advisor/source intake, advisor matching, contact email/material drafting, reviewer/auditor checks, interview prep, presentation planning, local user document storage, material versioning, or Agent workflow records in grad-apply-workflow.
---

# Grad Apply Workflow

Use this skill to run this repository's graduate-application Agent workflows without mixing protocol with business code.

## Core Rules

- Treat this skill as protocol only. Keep executable business logic in `app/backend/`, storage code in `app/backend/storage.py`, adapters in `integrations/`, and tests in `tests/`.
- Prefer existing project services as tools before inventing new behavior: profile parsing, advisor source intake, advisor parsing, matching, material generation, interview prep, PPT outline, quality audit, and local PPTX generation.
- Do not scan `workspace/` freely. For student source documents, read `workspace/user_documents/manifest.json` first and only use manifest-registered paths.
- Do not write unconfirmed web-sourced student facts into final `StudentProfile`. Web student information is supplemental until user-confirmed.
- Preserve evidence for every advisor claim and every material claim that mentions grades, rank, papers, projects, awards, advisor direction, admissions requirements, or lab details.
- Save final user-facing materials under `workspace/generated/`; save draft/review/user-edited/final versions under `workspace/material_versions/`; save Agent run summaries under `workspace/agent_runs/`.
- Keep real user documents, `.env`, API keys, generated workspace data, and external reference project copies out of Git.

## Workflow Selection

- Student source intake: read `workflows/student-profile-intake.md` and `references/data-locations.md`.
- Advisor source intake: read `workflows/advisor-intake.md` and `references/evidence-rules.md`.
- Advisor matching review: read `workflows/advisor-match-review.md` and `references/evidence-rules.md`.
- Contact email or application material generation: read `workflows/material-drafter.md`, then `workflows/material-reviewer.md`, then `workflows/evidence-auditor.md`.
- Interview preparation: read `workflows/interview-prep.md`.
- Presentation/PPT planning: read `workflows/presentation-planner.md`.
- Progress or demo reporting: read `workflows/workflow-reporter.md`.
- Privacy, safety, or repository-boundary questions: read `references/safety-rules.md`.

## Default Agent Chain

For contact email and similar materials, use this sequence:

```text
MaterialDraftAgent
-> MaterialReviewAgent
-> EvidenceAuditAgent
-> user confirmation/edit
-> final GeneratedMaterial
```

When LLM access is unavailable, the drafter may call the existing deterministic service as fallback. Reviewer and auditor must still run rule-based checks.

## Required Output Shape

For any generated material workflow, return or persist:

- `draft`: first material candidate
- `review`: reviewer notes with concrete risks
- `evidence_audit`: claim-by-claim source status
- `revision`: revised material after review/audit
- `quality_report`: pass/fail, risk level, and unresolved issues

## Implementation Boundary

- Add orchestration code under `app/backend/agents/`.
- Add storage primitives only where backend code already owns workspace IO.
- Keep `.agents/skills/grad-apply-workflow/` portable and free of project secrets, generated workspace data, and copied external code.
- If a rule conflicts with `docs/03_execution_plan.md`, update the planning doc and this skill together.
