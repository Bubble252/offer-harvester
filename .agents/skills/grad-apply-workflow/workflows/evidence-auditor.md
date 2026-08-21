# Evidence Auditor

Goal: verify whether generated material claims are grounded in allowed evidence.

## Allowed Evidence

- Confirmed `StudentProfile`
- Manifest-registered user documents
- User-confirmed manual input
- Advisor sources and advisor evidence map
- Saved match report with evidence references

## Protocol

1. Split the material into audit-sized claims.
2. Classify each claim as student fact, advisor fact, match interpretation, recommendation, or style text.
3. Attach source IDs for factual claims.
4. Flag unsupported, exaggerated, ambiguous, or unverifiable claims.
5. Require revision before final material is written to `workspace/generated/`.

## Output

Use statuses: `supported`, `needs_confirmation`, `unsupported`, `too_broad`, `style_only`.
