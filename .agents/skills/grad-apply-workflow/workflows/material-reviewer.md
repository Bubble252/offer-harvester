# Material Reviewer

Goal: review drafts for application quality, conservatism, and interview explainability.

## Checks

- Fact consistency with confirmed student profile
- Advisor-source grounding
- Direction fit specificity
- Template/generic wording
- Overclaiming or admission-probability language
- Missing risk disclosure where relevant
- Interview explainability for each project claim

## Output

Return reviewer notes with:

- `passed`
- `risk_level`
- `issues`
- `required_revisions`
- `optional_improvements`

Each issue should name the problematic sentence or section and explain the risk.
