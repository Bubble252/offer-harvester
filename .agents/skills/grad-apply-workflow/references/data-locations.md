# Data Locations

Use these locations consistently.

## Workspace Directories

```text
workspace/
├── profiles/
├── user_documents/
├── advisor_sources/
├── advisors/
├── targets/
├── matches/
├── applications/
├── application_archives/
├── communications/
├── email_signal_candidates/
├── generated/
├── material_versions/
├── quality_reports/
├── agent_runs/
├── workflow_events/
├── presentation_tasks/
├── reports/
├── readiness_scores/
├── target_triage_reports/
├── profile_expansion_candidates/
├── gap_plans/
├── template_registry/
├── source_connectors/
├── sync_runs/
├── knowledge_base/
└── rag_index/
```

## Portable Registry Directories

```text
.agents/skills/grad-apply-workflow/
├── templates/
└── source_connectors/
```

`templates/` stores reusable `TEMPLATE.md` manifests and anonymous sample templates.
`source_connectors/` stores `CONNECTOR.md` manifests that describe URL patterns, field mappings, access rules, test queries, and manual fallback behavior. Connector manifests are not crawlers.

## User Documents

```text
workspace/user_documents/
├── resumes/
├── transcripts/
├── research_projects/
├── publications/
├── awards/
├── personal_statements/
├── manual_inputs/
├── web_supplements/
└── misc/
```

Allowed source file formats: `.pdf`, `.docx`, `.md`, `.txt`, `.json`, `.csv`, `.xlsx`, `.png`, `.jpg`, `.jpeg`.

Read `workspace/user_documents/manifest.json` before loading student files. Each entry should record `document_id`, `category`, `path`, `original_filename`, `source_type`, `content_hash`, `uploaded_at`, `trusted`, `confirmed`, and `notes`.
