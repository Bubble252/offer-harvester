# Advisor Match Review

Goal: produce a conservative match analysis that ties student evidence to advisor evidence.

## Protocol

1. Load confirmed `StudentProfile`.
2. Load target advisor/profile and source evidence.
3. Compare research direction, project fit, publication gap, admissions requirements, student preference, and risk notes.
4. Produce strengths, gaps, recommended actions, fit score, and tier.
5. For each strength, include both student evidence and advisor evidence.
6. For each gap, include severity and a practical next action.

## Current Harness

- `app/backend/agents/match_analysis_agent.py`
- `MatchAnalysisAgent.analyze(profile, target, advisor)`
- API entry: `POST /api/targets/{target_id}/match`
- Persists `MatchReport`, `AgentRun`, and `WorkflowEvent` records.
- Rule fallback remains `services.make_match`.

## Guardrails

- Do not predict admission probability.
- Do not label a target as safe solely from keyword overlap.
- Do not hide gaps; phrase them as actionable risks.
