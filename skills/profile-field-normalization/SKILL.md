---
name: profile-field-normalization
description: Normalize graduate-application profile fields while preserving field evidence, source provenance, confidence, and confirmation status. Use when extracting or merging resumes, transcripts, project notes, manual entries, OCR candidates, or web supplements into a reviewable profile candidate.
---

# Profile Field Normalization

1. Read `references/field-contract.md` before changing field names or statuses.
2. Normalize text conservatively; preserve original wording in source evidence.
3. Keep local uploads, user input, OCR candidates, and web supplements distinct.
4. Set extracted values to `unconfirmed` unless the user explicitly confirms them.
5. Exclude `rejected` fields from all generated material candidates.

## Hard Boundaries

- Never silently merge a web supplement into the trusted profile.
- Never downgrade a user-confirmed field based on an unverified inference.
- Do not discard evidence refs, conflicting values, or negative user feedback.
- Return a candidate patch only; the control plane owns confirmed profile writes.

Run `scripts/validate_fields.py --input <profile-fields.json>` before adding a fixture or adapter output.

## 中文说明

1. 修改字段名或状态前先阅读 `references/field-contract.md`。
2. 保守规范化文本，并在来源证据中保留原始表述。
3. 区分本地上传、用户输入、OCR 候选和网页补充资料。
4. 除非用户显式确认，否则抽取值均标为 `unconfirmed`。
5. 所有生成材料候选均排除 `rejected` 字段。

### 强制边界

- 不得将网页补充资料静默合并到可信 profile。
- 不得基于未验证推断降低用户已确认字段。
- 不得丢弃证据引用、冲突值或用户负反馈。
- 只返回候选 patch；confirmed profile 只能由控制面写入。
