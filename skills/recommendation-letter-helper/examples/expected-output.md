# Expected Output Shape / 预期输出结构

This fully synthetic example documents the candidate contract, not a submitted recommendation.

- `candidate_status`: `candidate` or `needs_review`
- `request_message`: a request candidate for the student to review
- `evidence_packet`: factual highlights with field confirmation status
- `reference_only_draft`: a clearly labeled draft for the recommender to revise
- `review`, `evidence_audit`, `quality`, and `risk_tags`: reviewable quality signals

The helper must not impersonate a recommender, send a request, submit a letter, or confirm
candidate facts. The result is `candidate-only` and `no-send`.

本完全虚构示例只说明候选契约，不是已提交推荐信。该 Skill 不能冒充推荐人、发送请求、
提交推荐信或确认候选事实；结果始终是 `candidate-only` 和 `no-send`。
