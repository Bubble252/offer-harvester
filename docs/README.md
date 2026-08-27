# Offer Harvester Documentation

[简体中文](README.zh-CN.md)

This is the supported public documentation hub. The local execution plan and early planning drafts are deliberately excluded from Git; historical reports are retained for traceability but are not the source of current product promises.

## Start Here

- [Repository README](../README.md): scope, limitations, and local quickstart.
- [Quickstart and Demo](getting-started.md): install, run the synthetic demo, and troubleshoot local startup.
- [Architecture](architecture.md): control-plane boundaries, runtime modules, and data ownership.
- [HTTP API Reference](reference/api.md): OpenAPI source of truth and stable endpoint groups.
- [Configuration](reference/configuration.md): environment variables, providers, and local-first defaults.
- [Security and Privacy](operations/security.md): public boundary and no-send rules.
- [Contribution Guide](operations/contributing.md): development commands, commit rules, and pull requests.
- [Release Guide](operations/release.md): pre-release checklist, tag process, and rollback.
- [Skills Guide](guides/skills.md): portable Skills, product Skills, and the Skill Lab.
- [Contact Email Coach](guides/skills/contact-email-coach.md): contact-email candidate workflow.
- [Advisor Due Diligence](guides/skills/advisor-due-diligence.md): source-grounded advisor review.
- [Recommendation Letter Helper](guides/skills/recommendation-letter-helper.md): request and evidence-packet workflow.
- [Product Skill Standalone Readiness](guides/skills/standalone-readiness.md): package shape, extraction checklist, and validation command for future standalone repositories.
- [DeepSeek Harness Guide](guides/deepseek-harness.md): optional external-agent adapter.

## Product References

- [Demo Walkthrough Record](11_demo_walkthrough.md)
- [Public KB and Agentic RL Foundation](18_public_kb_agentic_rl_foundation.md)
- [RAG and Memory Evaluation Report](16_rag_memory_evaluation_report.md)
- [Local Model Runtime](17_local_model_runtime.md)

## Contributor References

- [Contributing](../CONTRIBUTING.md) | [中文](../CONTRIBUTING.zh-CN.md)
- [Security](../SECURITY.md) | [中文](../SECURITY.zh-CN.md)
- [Changelog](../CHANGELOG.md) | [中文](../CHANGELOG.zh-CN.md)
- [Reference Project Gap Audit](13_reference_project_gap_audit.md)

The FastAPI `/docs` and `/openapi.json` are the HTTP contract source of truth. Markdown explains intended use and boundaries; it does not override the running OpenAPI schema.
