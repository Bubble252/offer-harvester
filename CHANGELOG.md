# Changelog

All notable changes to this project are documented here.

The format follows Keep a Changelog-style sections, and versions follow Semantic Versioning. The project is still in the `0.y.z` MVP stage, so public APIs may change before `1.0.0`.

## [Unreleased]

### Planned

- Optional real Gmail / QQ OAuth after the pasted-email signal workflow is stable.
- Optional real PPTAgent runtime integration through `PptAgentAdapter`.
- Optional external pipeline writeback for Notion / Feishu after privacy rules are finalized.

## [0.2.0-rc.1] - 2026-08-27

### Added

- Offer Harvester public documentation hub with bilingual quickstart, architecture, API,
  configuration, security, contribution, and release guides.
- Release candidate metadata, Makefile commands, OpenAPI categorization, API contract checks,
  public-boundary checks, and GitHub collaboration templates.
- Skill Lab documentation and a DeepSeek Harness adapter guide with scoped-token and no-send
  boundaries.
- New project logo assets optimized for GitHub README and local navigation.

### Changed

- Renamed the public product and API title from Grad Apply Workflow to Offer Harvester.
- Positioned the release as `0.2.0-rc.1`, not a stable `v1.0.0` promise.
- Centralized supported public documentation and removed historical planning reports from the
  primary navigation.

### Security

- Release checks reject common public-boundary leaks such as secrets and private absolute paths
  in supported public documentation.
- External-agent tools remain candidate-only, no-send, and unable to write confirmed profile,
  final material, tracker, or memory-promotion state directly.

### Known limits

- The default application remains local-first and does not include real OAuth sync, an external
  PPTAgent runtime, Redis workers, or a published DSH package.
- The browser workspace is Chinese-first in this release candidate; public documentation is
  bilingual.

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
