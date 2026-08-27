# Profile Field Contract / 学生画像字段契约

Supported confirmation states are `unconfirmed`, `confirmed`, `rejected`, and `needs_review`.

Every normalized field candidate requires `field_name`, `value`, `source_refs`, `status`, and `source_type`. `source_type` distinguishes local uploads, manual input, OCR candidates, and web supplements.

本 Skill 只能产出候选字段补丁。`confirmed` 只能来自用户明确确认；网页补充和 OCR 结果默认是 `unconfirmed` 或 `needs_review`。
