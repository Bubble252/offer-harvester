# Contact Email Coach

[简体中文](contact-email-coach.zh-CN.md) | [Skills Guide](../skills.md)

**Status:** incubating Product Skill. Run it in the Offer Harvester **Skill Lab** or through
the optional DeepSeek Harness (DSH) adapter. It is not a separately installable package.

## Use It For

- drafting a first advisor contact email
- rewriting an existing candidate
- aligning a draft with saved advisor evidence
- reducing unsupported or exaggerated claims
- preparing a follow-up candidate

## Before You Run It

Create or select one application target. The control plane resolves the linked profile, advisor,
and evidence. The useful minimum is:

- one target with a linked advisor or advisor source
- profile evidence; unconfirmed fields remain visible to review
- a mode: `new`, `rewrite`, `advisor_alignment`, `reduce_exaggeration`, or `follow_up`

## Run In Skill Lab

1. Start Offer Harvester and open **Skill Lab** in the sidebar.
2. Select **Contact Email Coach**.
3. Choose one application target and a mode.
4. Generate a candidate, then inspect the draft, evidence references, risk tags, and audit.
5. Copy or download the candidate only after review.

## Output And Boundary

The output includes a candidate email, reviewer findings, EvidenceAudit, quality findings, and
source references. It is `candidate-only` and `no-send`: it cannot send email, update an
application tracker, or overwrite confirmed profile data.

## Optional DSH Entry

The incubating DSH adapter exposes `offer_harvester_draft_contact_email` with `skill:run`.
It calls the same controlled API and returns a candidate. See the
[DSH guide](../deepseek-harness.md).

## Synthetic Example

Use the [minimal synthetic input](../../../skills/contact-email-coach/examples/minimal-input.json)
and [expected output shape](../../../skills/contact-email-coach/examples/expected-output.md) to
understand the public contract. They are illustrative context, not a direct HTTP payload.
