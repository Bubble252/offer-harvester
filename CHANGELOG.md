# Changelog

All notable changes to this project are documented here.

The format follows Keep a Changelog-style sections, and versions follow Semantic Versioning. The project is still in the `0.y.z` MVP stage, so public APIs may change before `1.0.0`.

## [Unreleased]

### Planned

- Release polish for README, screenshots, and GitHub release notes.
- Optional real Gmail / QQ OAuth after the pasted-email signal workflow is stable.
- Optional real PPTAgent runtime integration through `PptAgentAdapter`.
- Optional external pipeline writeback for Notion / Feishu after privacy rules are finalized.

## [0.1.0] - 2026-08-23

### Added

- Local FastAPI + static frontend workspace for recommendation-based graduate applications.
- Student profile upload, original document manifest, field-level evidence, and confirmation states.
- Advisor public-source intake with URL fetch, pasted fallback text, source persistence, profile extraction, and manual advisor editing.
- Application target tracker with deadline, lifecycle status, next action, archive, outcome, follow-up, and thank-you draft support.
- Fit analysis, Chinese contact email, interview question, and PPT outline generation.
- Reviewable material workflow: `MaterialDraftAgent -> MaterialReviewAgent -> EvidenceAuditAgent`.
- Quality reports for generated materials, unconfirmed facts, rejected facts, evidence coverage, and risk levels.
- Lightweight RAG layer over student documents, advisor sources, generated outputs, and manually added policy knowledge.
- Application readiness score with dashboard and target-level views.
- Batch target triage, profile expansion candidates, gap / upskill plans, template registry, and source connector manifest registry.
- Editable 16:9 PPTX generation through `LocalPptxAdapter`.
- Reference PPTX upload, hash persistence, rule-based precheck, generation parameters, fallback reason, and PPT quality scoring.
- Pasted-email signal workflow for advisor replies, interviews, material requests, rejections, offers, waitlists, and user-confirmed tracker updates.
- Demo workspace, screenshot walkthrough, and open-source readiness documentation.
- Portable project skills under `.agents/skills/grad-apply-workflow/`.
- GitHub CI, ruff, pytest, documentation lint, and repository security guards.
- OpenAI-compatible LLM configuration, including Responses API wire support for compatible providers.

### Changed

- README upgraded to a release-oriented open-source entry point with badges, quickstart, documentation links, privacy rules, and optional integration boundaries.
- Logo optimized for README and web loading.
- Demo walkthrough updated to describe the current end-to-end workflow and optional future integration boundaries.
- Release notes workflow added through `.github/release.yml`.

### Security

- `workspace/`, `.env`, real student documents, generated private materials, mailbox text, binary office files, and local planning drafts are ignored by Git.
- Security guards block common secret files, external project copy risks, and unsafe workspace artifacts.
- Email signal import is read-only and pasted-text based in the MVP; candidates require user approval before writing tracker, archive, or outcome.
- Generated materials are drafts and are never sent automatically.

### Boundaries

- No admission probability prediction.
- No automatic email sending.
- No real Gmail / QQ OAuth in the MVP.
- No real Notion / Feishu writeback in the MVP.
- No default `torch`, ViT, PPTAgent runtime, `oaib`, MongoDB, Redis, Chroma, reranker, PaddleOCR, or K8s dependency.
