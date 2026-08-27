# Offer Harvester

English | [简体中文](README.zh-CN.md)

<p align="center">
  <img src="docs/assets/brand/offer-harvester-logo.png" alt="Offer Harvester logo" width="180" />
</p>

<p align="center">
  <a href="https://github.com/Bubble252/offer-harvester/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Bubble252/offer-harvester/actions/workflows/ci.yml/badge.svg" /></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green" />
  <img alt="Local first" src="https://img.shields.io/badge/data-local--first-2f855a" />
</p>

Local-first, evidence-governed workspace for recommendation-based graduate applications. It turns profile evidence and public advisor sources into auditable target research, fit analysis, application materials, interview preparation, editable PPTX decks, and application tracking.

**Release candidate:** `0.2.0-rc.1`. The project does not predict admission probability, send emails automatically, or replace user review.

## What It Does

- Saves local student materials and extracts a structured profile with field-level evidence.
- Collects advisor and lab information from public URLs or pasted fallback text.
- Creates application targets and tracks status, deadlines, notes, archives, and outcomes.
- Generates fit analysis, contact email drafts, interview questions, and PPT outlines.
- Runs a `drafter -> reviewer -> evidence auditor` material workflow with quality reports.
- Builds an editable 16:9 PPTX through the local fallback adapter.
- Supports lightweight RAG over student documents, advisor sources, generated materials, and policy knowledge.
- Identifies pasted email signals such as replies, interviews, material requests, rejections, offers, and waitlists, then writes them only after user confirmation.
- Provides a Skill Lab for three reviewable, no-send product Skills.

## Product Skills

These are **incubating Product Skills**, not separately installable packages. They run through
the Offer Harvester control plane so that evidence, confirmation, privacy, and no-send rules
remain enforced.

| Skill | Use it for | Input | Output | Entry |
| --- | --- | --- | --- | --- |
| [Contact Email Coach](docs/guides/skills/contact-email-coach.md) | Drafting or revising advisor contact emails | Target, profile, advisor evidence, mode | Candidate email, review, evidence audit, quality findings | Skill Lab or optional DSH tool |
| [Advisor Due Diligence](docs/guides/skills/advisor-due-diligence.md) | Reviewing an advisor before outreach | Advisor, public sources, optional target and notes | Evidence coverage, unknowns, review questions, risk signals | Skill Lab or optional DSH tool |
| [Recommendation Letter Helper](docs/guides/skills/recommendation-letter-helper.md) | Preparing a recommender request and factual packet | Recommender context, target, profile evidence | Request candidate, evidence packet, reference-only draft | Skill Lab or optional DSH tool |

Every Product Skill is `candidate-only` and `no-send`: it cannot send email, submit an
application, overwrite confirmed profile data, change tracker state, or promote memory.
See the [Skills Guide](docs/guides/skills.md) for portable Skill reuse and host boundaries.

## Quickstart

```bash
git clone https://github.com/Bubble252/offer-harvester.git
cd offer-harvester
python -m venv .venv
. .venv/bin/activate
python -m pip install -r app/backend/requirements.txt ruff
make run
```

Open:

```text
http://127.0.0.1:8000
```

For reproducible synthetic demo data:

```bash
make demo
```

The local API contract is available at `http://127.0.0.1:8000/docs`; the browser workspace is at `http://127.0.0.1:8000`.

## Product Flow

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
- [Quickstart and Demo](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [HTTP API Reference](docs/reference/api.md)
- [Configuration](docs/reference/configuration.md)
- [Security and Privacy](docs/operations/security.md)
- [Contribution Guide](docs/operations/contributing.md)
- [Release Guide](docs/operations/release.md)
- [Skills Guide](docs/guides/skills.md)
- [DeepSeek Harness Guide](docs/guides/deepseek-harness.md)
- [NOTICE](NOTICE)
- [CONTRIBUTING](CONTRIBUTING.md) | [中文](CONTRIBUTING.zh-CN.md)
- [SECURITY](SECURITY.md) | [中文](SECURITY.zh-CN.md)
- [CHANGELOG](CHANGELOG.md)

The historical project reports remain in the repository for traceability. The documentation hub above is the supported public documentation surface.

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

Optional or future capabilities remain behind adapter boundaries:

- OpenAI-compatible LLM providers for enhanced extraction or drafting.
- PPTAgent runtime for future reference-template learning and advanced slide editing.
- Vision / OCR providers for future scanned documents or visual PPT checks.
- Gmail / QQ OAuth and Notion / Feishu sync for future real external integrations.
- DeepSeek Harness is an optional external-agent adapter; it calls controlled candidate-only APIs and is not required to run the app.
- MongoDB, Redis, Chroma, reranker, PaddleOCR, or K8s only after local-first limits are reached.

The default code path does not depend on `torch`, ViT model weights, `oaib`, external PPTAgent source trees, or a cloud database.

## Development

Run the release gate before opening a pull request:

```bash
make verify
```

Use Conventional Commits. For feature, privacy, data-model, or integration changes, include commit body sections for background, changes, verification, and boundaries. See the [Contribution Guide](docs/operations/contributing.md).

## Release Notes

Changes are tracked in [CHANGELOG.md](CHANGELOG.md). Release notes follow Keep a Changelog-style sections and GitHub release note grouping from [.github/release.yml](.github/release.yml).

`0.2.0-rc.1` is a pre-release candidate. Do not describe it as a stable `v1.0.0` release until the release checklist and manual demo acceptance have passed.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

Reference projects and borrowing boundaries are documented in [NOTICE](NOTICE), [docs/13_reference_project_gap_audit.md](docs/13_reference_project_gap_audit.md), and [docs/14_release_readme_polish_reference.md](docs/14_release_readme_polish_reference.md). The repository keeps its own implementation and neutral adapter names instead of copying external project source trees.
