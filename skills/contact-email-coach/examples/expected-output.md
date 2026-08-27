# Expected Output Shape / 预期输出结构

This fully synthetic example documents the output contract, not a real email.

- `candidate_status`: `candidate` or `needs_review`
- `material`: a contact-email draft with one target and evidence references
- `review`: reviewer findings and revision requests
- `evidence_audit`: supported, unsupported, stale, and confirmation-needed claims
- `quality`: material-quality findings
- `risk_tags`: include an unconfirmed-field or evidence gap when applicable

The result is `candidate-only` and `no-send`. It cannot send an email, update a tracker,
or confirm profile fields.

本完全虚构示例只说明输出契约，不是可发送邮件。结果必须保持 `candidate-only` 和
`no-send`，不能发送邮件、更新 tracker 或确认 profile 字段。
