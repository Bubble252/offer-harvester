# Data Locations

Use these locations consistently.

## Existing Workspace Directories

```text
workspace/
├── profiles/
├── advisor_sources/
├── advisors/
├── targets/
├── matches/
├── applications/
├── generated/
├── quality_reports/
├── presentation_tasks/
└── reports/
```

## Planned Workspace Directories

```text
workspace/
├── user_documents/
├── material_versions/
└── agent_runs/
```

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
