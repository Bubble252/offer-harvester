# Changelog

## Unreleased

### Added

- Initial MVP skeleton.
- Local workflow dashboard for profiles, advisor sources, targets, generated
  materials, quality checks, Markdown downloads, and progress reports.
- Editable 16:9 violet-theme PPTX generation from the five-slide interview
  outline, including task status and download endpoints.
- Advisor intake flow with source fallback, detailed advisor fields, evidence
  mapping, multi-source profile updates, and one-click target creation.
- Optional LLM-enhanced advisor extraction through local environment variables,
  with rule-based fallback, evidence-gated merging, and secret redaction.
- Responses API support for the GPT-5.5 provider configured in cc-switch.
- Advisor profile editing in the Web UI, backed by a `PUT /api/advisors/{id}`
  endpoint so manually corrected fields feed target creation and materials.
