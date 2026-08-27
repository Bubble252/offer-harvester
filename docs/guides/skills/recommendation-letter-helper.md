# Recommendation Letter Helper

[简体中文](recommendation-letter-helper.zh-CN.md) | [Skills Guide](../skills.md)

**Status:** incubating Product Skill. Run it in **Skill Lab** or through the optional DSH
adapter. It requires the Offer Harvester control plane and is not a separately installable tool.

## Use It For

- preparing a concise recommendation request
- organizing a factual evidence packet for a recommender
- drafting a clearly labeled reference-only candidate for the recommender to revise

## Before You Run It

Provide the recommender name and relationship. Optionally select an application target. The
control plane resolves profile evidence and retains field confirmation state.

## Run In Skill Lab

1. Open **Skill Lab** and select **Recommendation Letter Helper**.
2. Optionally choose an application target.
3. Enter the recommender name and relationship.
4. Generate a candidate packet.
5. Review evidence status and risk findings before copying or downloading the result.

## Output And Boundary

The output may include a request message, factual evidence packet, and a `reference-only` draft.
The recommender must revise, approve, and submit their own letter. The Skill cannot impersonate a
recommender, send a request, submit a letter, confirm profile fields, or update tracker state.

## Optional DSH Entry

The DSH adapter exposes `offer_harvester_recommendation_letter_helper` with `skill:run`.
It returns only a candidate through the same controlled API. See the
[DSH guide](../deepseek-harness.md).

## Synthetic Example

See the
[minimal synthetic input](../../../skills/recommendation-letter-helper/examples/minimal-input.json)
and
[expected output shape](../../../skills/recommendation-letter-helper/examples/expected-output.md).
