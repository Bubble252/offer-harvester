# Skills Guide

[简体中文](skills.zh-CN.md)

Offer Harvester uses Skills to make stable task protocols reusable without moving its trusted state model into prompt files.

## Choose The Right Entry Point

| Need | Entry point |
| --- | --- |
| Audit supplied claims outside the application | portable `evidence-claim-audit` |
| Design a public-source connector | portable `source-connector-authoring` |
| Normalize extracted profile fields | portable `profile-field-normalization` |
| Draft a contact email, review an advisor, or prepare a recommendation packet | Skill Lab product Skills |

Open **Skill Lab** in the application sidebar to run a product Skill. Each run produces a candidate, visible evidence references, risk tags, and a traceable AgentRun / WorkflowEvent record.

## Safety Model

- `confirmed`, `unconfirmed`, `needs_review`, and `rejected` profile fields retain their existing meaning.
- Rejected fields are excluded from recommendation packet evidence.
- Unconfirmed fields may appear in a candidate only with review risk tags.
- No product Skill sends messages, submits applications, promotes memory, or changes tracker state.
- Community information is a risk signal. It must not become an official advisor fact without reviewable evidence.

## Catalog Contract

[`skills/catalog.json`](../../skills/catalog.json) is the only catalog. Every item declares:

- `category`: `portable` or `product`
- `no_send`
- `write_permissions`
- `source_policy`
- `private_data_policy`
- `status_truth_source`

Portable Skills are intentionally workspace-free. Product Skills may use data only through a controlled FastAPI adapter. This keeps the output useful while preserving the existing evidence and confirmation gates.

## Create A New Skill

1. Start with one user task and a stable input/output contract.
2. Put host-neutral instructions in `SKILL.md`.
3. Put detailed formats in `references/` and deterministic checks in `scripts/`.
4. Add a catalog entry and a synthetic fixture.
5. For a product Skill, add an adapter that writes only allowed candidate execution records.
6. Add an explicit no-send, no-final-write boundary before adding UI.

Do not use a Skill to bypass the profile, evidence, tracker, privacy, or confirmation control planes.
