# Advisor Due Diligence

[简体中文](advisor-due-diligence.zh-CN.md) | [Skills Guide](../skills.md)

**Status:** incubating Product Skill. Run it in **Skill Lab** or through the optional DSH
adapter. It depends on the Offer Harvester control plane and is not separately installable.

## Use It For

- checking whether one advisor identity is sufficiently resolved
- reviewing saved public advisor and lab sources before outreach
- finding source gaps, unknowns, and questions to verify
- separating public evidence from community risk signals

## Before You Run It

Select one saved advisor. Optionally link an application target. The useful minimum is:

- one advisor with at least one saved public or manually supplied source
- a stable `advisor_id`
- optional target context and user notes

## Run In Skill Lab

1. Open **Skill Lab** from the Offer Harvester sidebar.
2. Select **Advisor Due Diligence**.
3. Choose one advisor and, if useful, a related application target.
4. Generate the candidate report.
5. Review source references, unknowns, risk tags, and suggested follow-up questions.

## Output And Boundary

The report separates official/public evidence, unresolved coverage gaps, review questions, and
community risk signals. Community material is never promoted to an official advisor fact. The
Skill cannot contact an advisor, update application status, or write confirmed facts.

## Optional DSH Entry

The DSH adapter exposes `offer_harvester_advisor_due_diligence` with `advisor:report`. It is
candidate-only and uses the same control-plane evidence rules. See the
[DSH guide](../deepseek-harness.md).

## Synthetic Example

See the [minimal synthetic input](../../../skills/advisor-due-diligence/examples/minimal-input.json)
and [expected output shape](../../../skills/advisor-due-diligence/examples/expected-output.md).
