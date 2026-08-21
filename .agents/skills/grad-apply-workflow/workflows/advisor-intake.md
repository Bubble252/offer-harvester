# Advisor Intake

Goal: turn advisor public sources or pasted text into an evidence-bound `AdvisorSource` and `AdvisorProfile`.

## Source Order

```text
advisor web page / lab page / admission notice / publication page
-> manual paste fallback
-> AdvisorSource
-> AdvisorProfile
```

## Protocol

1. Accept public HTTP/HTTPS URLs or manual text.
2. Reject localhost, private IPs, and local network URLs.
3. Save raw source text, cleaned text, fetch status, fetch error, trust flag, and content hash.
4. Extract advisor identity, school, college, lab, email, directions, recruiting status, student type, papers, projects, requirements, preferred student profile, recent focus, and risks.
5. Attach source IDs in `evidence_map`.
6. When LLM extraction is used, accept only fields with evidence and sufficient confidence.

## Guardrails

- Do not infer unknown advisor facts from general knowledge.
- Do not merge two similarly named professors without identity confirmation.
- Keep failed fetch records; they are part of the audit trail.
