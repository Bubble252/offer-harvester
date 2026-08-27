---
name: evidence-claim-audit
description: Audit graduate-application claims against supplied evidence and return supported, unsupported, stale, or confirmation-required findings. Use when drafting or reviewing contact emails, statements, recommendation packets, advisor reports, policy summaries, or structured claim lists.
---

# Evidence Claim Audit

1. Read `references/input-output.md` before accepting a new schema or status.
2. Normalize each claim into text, claim type, source refs, and a proposed status.
3. Mark a claim `supported` only when supplied evidence directly covers it.
4. Mark missing or conflicting support as `unsupported`, old time-sensitive support as `stale`, and profile uncertainty as `needs_confirmation`.
5. Preserve source refs and state why a claim is blocked. Do not invent citations.

## Hard Boundaries

- Treat supplied evidence as candidate context, not permission to write profile, tracker, memory, or final material records.
- Never convert an unconfirmed web fact into a confirmed student fact.
- Never hide a rejection, conflict, expiry, or missing source behind a neutral score.
- Return review findings and candidate revisions only. Do not send messages or submit applications.

Run `scripts/validate_claim_audit.py --input <claims.json>` before publishing a fixture.

## 中文说明

1. 接受新 schema 或状态前，先阅读 `references/input-output.md`。
2. 将每条 claim 规范为文本、类型、来源引用和建议状态。
3. 只有提供的证据直接覆盖 claim 时才标为 `supported`。
4. 缺证据或证据冲突标为 `unsupported`；时效性证据过期标为 `stale`；画像不确定标为 `needs_confirmation`。
5. 保留来源引用和阻塞原因，不得编造引文。

### 强制边界

- 提供的证据只是候选上下文，不能据此写入 profile、tracker、memory 或最终材料。
- 不得把未确认网页事实升级为已确认学生事实。
- 不得用中性分数掩盖 rejected、conflict、expiry 或缺来源。
- 只返回审计结论和候选修改，不发送消息、不提交申请。
