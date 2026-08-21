# Workflow Reporter

Goal: summarize application progress, generated materials, risks, and next actions.

## Protocol

1. Load workspace summaries from profiles, advisors, targets, matches, generated materials, quality reports, applications, presentation tasks, and agent runs.
2. Report current target status, next action, deadline, last contact, generated materials, and unresolved risks.
3. Separate demo/sample data from real user data.
4. Mention missing evidence and failed tasks explicitly.

## Guardrails

- Do not expose private raw documents in a report intended for open-source demo.
- Do not include API keys or raw `.env` content.
- Do not present generated suggestions as verified outcomes.
