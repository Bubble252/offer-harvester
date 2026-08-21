# Student Profile Intake

Goal: turn local student materials into a confirmed `StudentProfile` with source traceability.

## Source Order

```text
local upload / pasted text
-> web supplement
-> user confirmation
-> profiles/
```

## Protocol

1. Read `workspace/user_documents/manifest.json`.
2. Load only manifest-registered documents relevant to the requested profile task.
3. Extract candidate fields: education, GPA, rank, research interests, projects, publications, competitions, skills, and risk notes.
4. Attach `document_id`, source category, and confidence to each candidate field.
5. Show conflicts and missing high-value fields before writing final profile data.
6. Write confirmed structured profile to `workspace/profiles/`.

## Guardrails

- Do not let student web supplements overwrite local evidence without confirmation.
- Mark unconfirmed facts explicitly.
- Keep raw files in `workspace/user_documents/`; do not copy them into `profiles/`.
