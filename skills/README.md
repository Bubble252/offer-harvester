# Offer Harvester Skills

[简体中文](README.zh-CN.md)

This directory contains two deliberately different kinds of Skills:

- **Portable Skills**: small, host-neutral instructions and validators that work from supplied inputs and never access an Offer Harvester workspace directly.
- **Product Skills**: task-focused adapters with a dedicated Skill Lab UI. They call the FastAPI control plane and return reviewable candidates, not final actions.

The canonical machine-readable index is [`catalog.json`](catalog.json). A catalog entry names the Skill category, version, input-data boundary, write permission, source policy, and state truth source.

## P0 Catalog

| Skill | Type | Output | Boundary |
| --- | --- | --- | --- |
| `evidence-claim-audit` | Portable | supported / unsupported / stale / confirmation-needed findings | never writes facts |
| `source-connector-authoring` | Portable | public-source connector manifest candidate | no robots/ToS bypass |
| `profile-field-normalization` | Portable | normalized profile field candidates | never confirms fields |
| [`contact-email-coach`](../docs/guides/skills/contact-email-coach.md) | Product, incubating | reviewed contact-email candidate | Skill Lab only; never sends email |
| [`advisor-due-diligence`](../docs/guides/skills/advisor-due-diligence.md) | Product, incubating | evidence-grounded advisor review | Skill Lab only; community content is only a risk signal |
| [`recommendation-letter-helper`](../docs/guides/skills/recommendation-letter-helper.md) | Product, incubating | request and recommender packet candidate | Skill Lab only; never impersonates or submits |

## How They Relate To The Application

```text
Skill protocol
-> SkillRegistry / SkillExecution adapter
-> FastAPI control plane
-> existing Agent + EvidenceAudit workflow
-> candidate result, AgentRun, WorkflowEvent
-> user review in Skill Lab
```

Only the control plane can access the workspace. It retains evidence and confirmation rules. `no_send` applies to every current catalog item.
The Product Skills also include standalone-ready manifests, schemas, and synthetic fixtures.
They remain incubating until a separate repository, runner, and host compatibility CI exist.

## Validation

Run the portable Skill fixtures:

```bash
python skills/evidence-claim-audit/scripts/validate_claim_audit.py \
  --input skills/evidence-claim-audit/scripts/claim_fixture.json
python skills/source-connector-authoring/scripts/validate_manifest.py \
  --input skills/source-connector-authoring/scripts/manifest_fixture.json
python skills/profile-field-normalization/scripts/validate_fields.py \
  --input skills/profile-field-normalization/scripts/fields_fixture.json
```

Run the product adapter tests from the repository root:

```bash
./.venv/bin/pytest -q tests/test_skills_dsh.py
make PYTHON=./.venv/bin/python skills-check
```

## Future Hosts

The current native host is the Offer Harvester Skill Lab. A DeepSeek Harness adapter lives under [`integrations/deepseek_harness/`](../integrations/deepseek_harness/). Codex and Claude thin pointers, external installers, and standalone repositories are intentionally deferred until these interfaces stabilize.
