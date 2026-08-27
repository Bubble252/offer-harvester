# Skills 指南

[English](skills.md)

Offer Harvester 使用 Skill 把稳定的任务协议做成可复用能力，但不会把可信状态模型搬进 prompt 文件。

## 如何选择入口

| 需求 | 入口 |
| --- | --- |
| 在应用外审计已经提供的 claim | portable `evidence-claim-audit` |
| 编写公开来源 connector | portable `source-connector-authoring` |
| 规范化抽取出的 profile 字段 | portable `profile-field-normalization` |
| 写套磁信、尽调导师、准备推荐信素材包 | Skill Lab 产品化 Skill |

在应用侧栏打开 **Skill Lab** 即可运行产品化 Skill。每次执行都会输出 candidate、可见 evidence refs、risk tags，以及可追踪的 AgentRun / WorkflowEvent。

## 安全模型

- `confirmed`、`unconfirmed`、`needs_review`、`rejected` 字段继续使用既有含义。
- 被拒绝字段不会进入推荐信素材包证据。
- 未确认字段只能带着 review risk tag 出现在候选里。
- 产品化 Skill 不发送消息、不提交申请、不提升 memory、不修改 tracker。
- 社区内容只是风险信号；没有可复核证据时不能变成导师官方事实。

## Catalog 契约

[`skills/catalog.json`](../../skills/catalog.json) 是唯一 catalog。每个条目声明：

- `category`：`portable` 或 `product`
- `no_send`
- `write_permissions`
- `source_policy`
- `private_data_policy`
- `status_truth_source`

Portable Skill 刻意不读取 workspace。产品化 Skill 只能经受控 FastAPI adapter 使用数据，从而保留原有证据和确认门槛。

## 新增 Skill

1. 从一个用户任务和稳定输入输出契约开始。
2. 在 `SKILL.md` 写宿主无关的精炼指令。
3. 复杂格式写进 `references/`，确定性校验写进 `scripts/`。
4. 增加 catalog 条目和完全虚构的 fixture。
5. 产品化 Skill 要增加只写允许 candidate execution 的 adapter。
6. 在添加 UI 前先写清 no-send、no-final-write 边界。

不能借 Skill 绕过 profile、evidence、tracker、隐私或用户确认控制面。
