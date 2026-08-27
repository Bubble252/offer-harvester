# Offer Harvester

English | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="app/frontend/assets/logo.png" alt="Offer Harvester logo" width="180" />
</p>

<p align="center">
  <a href="https://github.com/Bubble252/offer-harvester/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Bubble252/offer-harvester/actions/workflows/ci.yml/badge.svg" /></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green" />
  <img alt="Local first" src="https://img.shields.io/badge/data-local--first-2f855a" />
</p>

Local-first Web workspace for recommendation-based graduate applications. It helps students turn real profile evidence and public advisor sources into auditable target research, fit analysis, Chinese application materials, interview preparation, editable PPTX decks, and application tracking.

The project is currently an MVP. It does not predict admission probability, does not send emails automatically, and does not replace user review.

## What It Does

- Saves local student materials and extracts a structured profile with field-level evidence.
- Collects advisor and lab information from public URLs or pasted fallback text.
- Creates application targets and tracks status, deadlines, notes, archives, and outcomes.
- Generates fit analysis, contact email drafts, interview questions, and PPT outlines.
- Runs a `drafter -> reviewer -> evidence auditor` material workflow with quality reports.
- Builds an editable 16:9 PPTX through the local fallback adapter.
- Supports lightweight RAG over student documents, advisor sources, generated materials, and policy knowledge.
- Identifies pasted email signals such as replies, interviews, material requests, rejections, offers, and waitlists, then writes them only after user confirmation.
- Provides a Skill Lab for three reviewable, no-send product Skills: contact email coaching, advisor due diligence, and recommendation packets.

## Quickstart

```bash
git clone https://github.com/Bubble252/offer-harvester.git
cd offer-harvester
python -m pip install -r app/backend/requirements.txt
cd app/backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

For demo data, point the backend at `workspace.demo`:

```bash
cd app/backend
WORKSPACE_DIR=/path/to/offer-harvester/workspace.demo uvicorn main:app --host 127.0.0.1 --port 8000
```

## Demo

Screenshot walkthrough: [docs/11_demo_walkthrough.md](docs/11_demo_walkthrough.md)

Core flow:

```text
Student profile
-> field evidence and confirmation
-> advisor public sources
-> application target
-> fit analysis
-> reviewed contact email
-> interview questions and PPTX
-> lifecycle tracker and email signals
```

## Documentation

- [Documentation Hub](docs/README.md)
- [Skills Guide](docs/guides/skills.md)
- [DeepSeek Harness Guide](docs/guides/deepseek-harness.md)
- [Demo Walkthrough](docs/11_demo_walkthrough.md)
- [Open Source Readiness](docs/10_open_source_readiness.md)
- [Release README Polish Reference](docs/14_release_readme_polish_reference.md)
- [Reference Project Gap Audit](docs/13_reference_project_gap_audit.md)
- [Wenshu Agent Reference](docs/12_wenshu_agent_reference.md)
- [NOTICE](NOTICE)
- [CONTRIBUTING](CONTRIBUTING.md)
- [SECURITY](SECURITY.md)
- [CHANGELOG](CHANGELOG.md)

Early planning docs under `docs/01_*.md` through `docs/09_*.md` are local planning drafts and are ignored by Git by default.

## Data And Privacy

Real student materials, advisor contact records, generated drafts, archives, RAG indexes, and pasted email text belong in `workspace/`, which is ignored by Git.

Do not commit:

- `.env` or API keys
- real resumes, transcripts, recommendation letters, or certificates
- real contact emails or pasted mailbox exports
- generated materials for real users
- copied external project directories

Generated materials are drafts. Users must verify facts and send messages themselves.

## Optional Integrations

The MVP runs without external LLMs or heavy model dependencies.

Optional or future capabilities are intentionally behind adapter boundaries:

- OpenAI-compatible LLM providers for enhanced extraction or drafting.
- PPTAgent runtime for future reference-template learning and advanced slide editing.
- Vision / OCR providers for future scanned documents or visual PPT checks.
- Gmail / QQ OAuth and Notion / Feishu sync for future real external integrations.
- DeepSeek Harness is an optional external-agent adapter; it calls controlled candidate-only APIs and is not required to run the app.
- MongoDB, Redis, Chroma, reranker, PaddleOCR, or K8s only after local-first limits are reached.

The default code path does not depend on `torch`, ViT model weights, `oaib`, external PPTAgent source trees, or a cloud database.

## Development

Run the standard checks before opening a pull request:

```bash
ruff check app tests
ruff format --check app tests
pytest -q
node --check app/frontend/app.js
python -m compileall -q app integrations tests
python tools/lint_docs.py
python tools/security_guards.py
```

The project uses Conventional Commits. For feature, privacy, data model, or integration changes, include commit body sections for background, changes, verification, and boundaries.

## Release Notes

Changes are tracked in [CHANGELOG.md](CHANGELOG.md). Release notes follow Keep a Changelog-style sections and GitHub release note grouping from [.github/release.yml](.github/release.yml).

The first stable MVP tag is planned as `v0.1.0`.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

Reference projects and borrowing boundaries are documented in [NOTICE](NOTICE), [docs/13_reference_project_gap_audit.md](docs/13_reference_project_gap_audit.md), and [docs/14_release_readme_polish_reference.md](docs/14_release_readme_polish_reference.md). The repository keeps its own implementation and neutral adapter names instead of copying external project source trees.
