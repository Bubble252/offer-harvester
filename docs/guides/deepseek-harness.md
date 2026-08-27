# DeepSeek Harness Integration Guide

[简体中文](deepseek-harness.zh-CN.md)

DeepSeek Harness (DSH) is an optional external agent host. Offer Harvester stays the control plane: it owns the workspace, evidence rules, user confirmation, RAG and memory governance, and audit trail.

## Included P0 Tools

| DSH tool | Offer Harvester endpoint | Required scope |
| --- | --- | --- |
| `offer_harvester_draft_contact_email` | `/api/plugin/skills/contact-email-coach/run` | `skill:run` |
| `offer_harvester_advisor_due_diligence` | `/api/plugin/skills/advisor-due-diligence/run` | `advisor:report` |
| `offer_harvester_recommendation_letter_helper` | `/api/plugin/skills/recommendation-letter-helper/run` | `skill:run` |
| `offer_harvester_audit_material` | `/api/plugin/materials/audit` | `material:audit` |

The implementation is at [`integrations/deepseek_harness/`](../../integrations/deepseek_harness/).

## Setup

1. Start Offer Harvester.
2. Copy the integration's `cordis.yml.example` into a DSH Cordis composition.
3. Configure `apiBaseUrl`, enabled tools, privacy mode, and a request timeout.
4. Test with local loopback mode first.
5. Before remote use, change the Offer Harvester server to token mode and supply a separate plugin token.

```bash
OFFER_HARVESTER_PLUGIN_AUTH_MODE=token
OFFER_HARVESTER_PLUGIN_TOKEN=<long-random-value>
OFFER_HARVESTER_PLUGIN_SCOPES=skill:run,material:audit,advisor:report,policy:read
OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE=false
```

The token is an Offer Harvester integration credential, not an LLM provider key. Never put it in Git, a public DSH configuration, or prompt text.

Hosts that render configuration from JSON Schema can use
[`settings.schema.json`](../../integrations/deepseek_harness/settings.schema.json).
It includes a password/write-only token field and a display-only workspace label;
the plugin cannot select a local filesystem path.

## Privacy And Writes

`metadata_only` is the default DSH privacy mode. It should remain the default for any remote server. `private` requires explicit server opt-in through `OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE=true`.

The plugin cannot choose a filesystem workspace. The running Offer Harvester process chooses its workspace; DSH receives only candidate outputs through HTTP. All successful calls create candidate execution/audit traces, and no tool can send or submit anything.

## Current Limits

- The integration is an incubating local adapter, not a standalone published DSH package.
- It does not provide a DSH-native settings page or persistent secret store.
- It does not implement policy deadline checks, remote profile writes, OAuth, or direct community crawling.
- It has offline HTTP-contract tests; mounting the TypeScript plugin requires an installed DSH runtime.
