# Material Drafter

Goal: draft application materials from confirmed student profile, target/advisor evidence, and match analysis.

## Inputs

- Confirmed `StudentProfile`
- Target and advisor profile
- Advisor source IDs and evidence map
- Latest match report when available
- Material type, language, and user constraints

## Protocol

1. Identify the material purpose and audience.
2. Select only claims supported by student profile, advisor evidence, or user confirmation.
3. Draft with concrete alignment: student project or skill -> advisor direction or requirement.
4. Avoid generic phrases that remain true after replacing the advisor name.
5. Save draft version to `workspace/material_versions/`.
6. Pass draft to reviewer before finalizing.

## Fallback

If LLM is unavailable, call existing deterministic generation service such as `make_contact_email`, then pass the result through reviewer and auditor.
