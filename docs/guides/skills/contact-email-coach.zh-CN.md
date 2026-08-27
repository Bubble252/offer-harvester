# 套磁信教练

[English](contact-email-coach.md) | [Skills 指南](../skills.zh-CN.md)

**状态：** 主仓孵化中的 Product Skill。可在 Offer Harvester 的 **Skill Lab** 中运行，
也可通过可选 DeepSeek Harness（DSH）adapter 调用；它不是可单独安装的软件包。

## 适用场景

- 新写第一封导师套磁邮件
- 修改已有候选稿
- 根据已保存导师证据强化匹配表述
- 降低无证据或夸大的表述
- 准备 follow-up 候选稿

## 运行前准备

先创建或选择一个申请目标。控制面会解析关联的 profile、导师和证据。最低需要：

- 一个关联导师或导师来源的申请目标
- 学生 profile 证据；未确认字段仍会显示为待复核
- 一个模式：`new`、`rewrite`、`advisor_alignment`、`reduce_exaggeration` 或 `follow_up`

## 在 Skill Lab 中运行

1. 启动 Offer Harvester，在侧栏打开 **Skill Lab**。
2. 选择 **套磁信教练**。
3. 选择一个申请目标和工作模式。
4. 生成候选结果，查看草稿、证据引用、风险标签和审计。
5. 完成复核后再复制或下载候选稿。

## 输出与边界

输出包括候选邮件、reviewer 发现、EvidenceAudit、质量发现和来源引用。它始终是
`candidate-only` 和 `no-send`：不能发送邮件、修改申请 tracker 或覆盖 confirmed profile。

## 可选 DSH 入口

主仓内孵化的 DSH adapter 提供 `offer_harvester_draft_contact_email`，需要 `skill:run`
scope。它调用同一受控 API，只返回 candidate。详见
[DSH 指南](../deepseek-harness.zh-CN.md)。

## 完全虚构示例

可阅读[最小合成输入](../../../skills/contact-email-coach/examples/minimal-input.json)和
[预期输出结构](../../../skills/contact-email-coach/examples/expected-output.md)了解公开契约。
它们仅用于说明上下文，不是可直接发送的 HTTP payload。
