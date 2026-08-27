# Offer Harvester DeepSeek Harness Integration

[简体中文](README.zh-CN.md)

This directory is an incubating local adapter for DeepSeek Harness (DSH). It exposes controlled Offer Harvester candidates as DSH tools without making DSH the source of truth.

## What It Exposes

- `offer_harvester_draft_contact_email`
- `offer_harvester_advisor_due_diligence`
- `offer_harvester_recommendation_letter_helper`
- `offer_harvester_audit_material`

Every tool is candidate-only and `no_send`. The Offer Harvester FastAPI control plane owns profile data, evidence audit, user confirmation, and workspace persistence.

## Safety Contract

- No email, recommendation letter, form, or application is sent or submitted.
- The adapter cannot write a profile, policy record, or tracker status directly.
- Community or reputation text is only a review signal, never a confirmed fact.
- Material audit produces a trace and report but never changes the material being audited.
- DSH requests use the smallest scope needed: `skill:run`, `advisor:report`, or `material:audit`.

## Local Setup

1. Start Offer Harvester at `http://127.0.0.1:8000`.
2. Copy `cordis.yml.example` into a DSH composition and adjust `apiBaseUrl`.
3. For local loopback development, leave `OFFER_HARVESTER_PLUGIN_AUTH_MODE=local`.
4. For any remote deployment, set `OFFER_HARVESTER_PLUGIN_AUTH_MODE=token`, set a long random `OFFER_HARVESTER_PLUGIN_TOKEN`, and configure the same token in the DSH plugin.
5. Keep `privacyMode: metadata_only` unless the server explicitly permits remote private data.

`workspaceLabel` is intentionally not a filesystem path. Workspace selection remains server-owned to prevent a DSH tool from choosing arbitrary local directories.

Hosts that can render settings from JSON Schema can use
[`settings.schema.json`](settings.schema.json). It declares the URL, token,
privacy mode, timeout, enabled tool list, and display-only workspace label.
`pluginToken` is marked write-only and must never be exported with an example.

## Verification

```bash
cd integrations/deepseek_harness
npm test
```

The tests are offline HTTP-contract tests. Installing a DSH runtime is optional for this repository; use the official DSH runtime and its documented Cordis loader when you want to mount `src/plugin.ts`.

## Boundary

This is not a standalone DSH distribution and does not copy the DSH runtime. It is an adapter boundary designed for a later published package or separate repository after the interface stabilizes.
