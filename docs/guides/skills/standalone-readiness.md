# Product Skill Standalone Readiness

[简体中文](standalone-readiness.zh-CN.md)

This page defines what “ready for a standalone repository” means for the three incubating Product Skills. They are still shipped inside Offer Harvester, but each package now has enough local contract files to be extracted later without guessing its boundary.

## Current Status

| Skill | Package candidate | Status |
| --- | --- | --- |
| `contact-email-coach` | `offer-harvester-skill-contact-email-coach` | standalone-ready, still incubating |
| `advisor-due-diligence` | `offer-harvester-skill-advisor-due-diligence` | standalone-ready, still incubating |
| `recommendation-letter-helper` | `offer-harvester-skill-recommendation-letter-helper` | standalone-ready, still incubating |

“Standalone-ready” does not mean “already standalone”. The current runtime still depends on the Offer Harvester control plane for workspace access, evidence audit, privacy routing, and candidate writes.

## Required Package Shape

Each Product Skill must contain:

- `SKILL.md`: concise agent-facing instructions.
- `agents/openai.yaml`: UI and host metadata.
- `references/contract.md`: human-readable behavior contract.
- `skill.manifest.json`: package name, entrypoints, dependencies, forbidden capabilities, and extraction status.
- `schemas/input.schema.json`: external input contract.
- `schemas/output.schema.json`: candidate output contract.
- `fixtures/*.json`: at least three fully synthetic cases covering `candidate`, `needs_review`, and `blocked`.
- `examples/minimal-input.json` and `examples/expected-output.md`: public minimal example.

Skill folders should not contain `README.md`, API keys, private user data, generated workspace records, checkpoints, or copied third-party project code.

## Host Boundary

A standalone-ready Product Skill may define an adapter, but the current main repository remains the source of truth for:

- profile confirmation state;
- advisor sources and evidence freshness;
- RAG and memory promotion;
- material review and EvidenceAudit;
- `AgentRun` and `WorkflowEvent` records;
- candidate persistence.

The skill may request a candidate execution. It must not send email, submit applications, overwrite confirmed profile fields, change tracker state, or promote memory.

## Extraction Checklist

Before creating a real standalone repository:

1. Copy only the package files listed in `skill.manifest.json`.
2. Replace Offer Harvester imports with a narrow host adapter interface.
3. Keep fixture tests green without a real workspace.
4. Add host compatibility tests against Offer Harvester API and DSH.
5. Add bilingual README, install guide, license, release notes, and screenshots in the new repository.
6. Keep the first standalone release marked pre-1.0 until input/output schema has stayed compatible across at least two releases.

## Validation

Run:

```bash
make PYTHON=./.venv/bin/python skills-check
./.venv/bin/python tools/plan_product_skill_export.py --all
```

The checker verifies package shape, manifest/catalog alignment, fixture coverage, synthetic-data markers, no-send boundary, and basic private-content guards.
The export planner prints the exact manifest-bound file list that would be copied into a future standalone repository.
