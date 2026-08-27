# HTTP API Reference

[简体中文](api.zh-CN.md)

## Source Of Truth

The running FastAPI application is the API source of truth:

- Interactive reference: `/docs`
- OpenAPI JSON: `/openapi.json`
- Source wiring: `app/backend/main.py`

Markdown documents explain workflows and privacy boundaries. They do not replace the
generated OpenAPI schema. Run `python tools/check_openapi_contract.py` after API changes.

## Request Conventions

- JSON request and response bodies use the Pydantic models declared in `main.py` and
  `models.py`.
- IDs are opaque strings such as `profile_*`, `target_*`, `material_*`, and `run_*`.
- Empty lists and empty strings are valid in several MVP request models; inspect the
  response and evidence findings before treating a result as complete.
- Candidate-producing endpoints do not imply final save or external action.
- Errors use FastAPI's standard HTTP error response unless a route declares a more specific
  response model.

## Endpoint Groups

| Tag | Main paths | Purpose |
| --- | --- | --- |
| Application | `/api/health`, `/api/llm/status`, `/` | Service status and browser shell |
| Profile | `/api/profile`, `/api/profile/upload`, `/api/user-documents` | Original files, profile fields, confirmation |
| Advisors and targets | `/api/advisors`, `/api/advisor-sources`, `/api/targets` | Public sources, advisor identity, targets |
| Materials | `/api/targets/*/materials/*`, `/api/generated`, `/api/tasks` | Candidate materials and PPTX tasks |
| Evidence and RAG | `/api/knowledge-base`, `/api/rag`, `/api/readiness-score` | Sources, search, bundles, readiness |
| Memory and feedback | `/api/memory`, `/api/agent-runs`, `/api/procedural-candidates` | Governed memory and traces |
| Workflow operations | `/api/templates`, `/api/source-connectors`, `/api/pdf`, `/api/ocr`, `/api/email-signals` | Local workflow support |
| Skills | `/api/skills`, `/api/skill-executions` | Skill catalog and candidate execution |
| Integrations | `/api/plugin/*`, `/api/pipeline-sync/status` | Scoped external adapters |

## Stable Examples

### Health

```bash
curl http://127.0.0.1:8000/api/health
```

### List Skills

```bash
curl http://127.0.0.1:8000/api/skills
```

Every catalog entry exposes its status, version, `no_send` flag, write permissions,
source policy, and private-data policy.

### Search RAG

```bash
curl --get http://127.0.0.1:8000/api/rag/search \
  --data-urlencode 'q=推免申请截止日期' \
  --data-urlencode 'top_k=5'
```

Search hits contain source metadata and evidence references. They are not automatically
confirmed facts.

### Run A Product Skill

```bash
curl -X POST http://127.0.0.1:8000/api/skills/contact-email-coach/run \
  -H 'Content-Type: application/json' \
  -d '{"target_id":"target_demo","mode":"new"}'
```

The result is a candidate with evidence/risk metadata and a trace. It does not send email,
write a final material, or update the tracker.

### DSH Plugin Status

```bash
curl http://127.0.0.1:8000/api/plugin/status
```

Remote plugin requests use a separate scoped token when the server is configured in
`token` mode. See the [DSH guide](../guides/deepseek-harness.md).

## Compatibility Policy

The project is in the `0.y.z` stage. Additive fields and endpoints are preferred, but
breaking changes are possible before `1.0.0`. Keep API changes paired with:

1. Pydantic model updates.
2. OpenAPI contract test updates.
3. English and Chinese public documentation updates.
4. A changelog entry with privacy and rollback boundaries.
