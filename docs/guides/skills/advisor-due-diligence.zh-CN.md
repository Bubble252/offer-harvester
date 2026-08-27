# 导师尽调

[English](advisor-due-diligence.md) | [Skills 指南](../skills.zh-CN.md)

**状态：** 主仓孵化中的 Product Skill。可在 **Skill Lab** 或可选 DSH adapter 中运行。
它依赖 Offer Harvester 控制面，不是可单独安装的软件包。

## 适用场景

- 检查单一导师身份是否已充分消歧
- 在联系前审查已保存的导师和实验室公开来源
- 找出来源缺口、未知项和需要追问的问题
- 分离公开证据与社区风险信号

## 运行前准备

选择一个已保存导师，可选关联一个申请目标。最低需要：

- 一个至少带有一条公开来源或用户手动来源的导师
- 稳定的 `advisor_id`
- 可选的目标上下文和用户备注

## 在 Skill Lab 中运行

1. 在 Offer Harvester 侧栏打开 **Skill Lab**。
2. 选择 **导师尽调**。
3. 选择一个导师；需要时再关联一个申请目标。
4. 生成候选报告。
5. 复核来源引用、未知项、风险标签和建议追问。

## 输出与边界

报告会分离官方/公开证据、未解决的覆盖缺口、复核问题和社区风险信号。社区材料永远不能
提升为导师官方事实。该 Skill 不能联系导师、修改申请状态或写入 confirmed fact。

## 可选 DSH 入口

DSH adapter 提供 `offer_harvester_advisor_due_diligence`，需要 `advisor:report` scope。
它只返回 candidate，并使用同一套控制面证据规则。详见
[DSH 指南](../deepseek-harness.zh-CN.md)。

## 完全虚构示例

可阅读[最小合成输入](../../../skills/advisor-due-diligence/examples/minimal-input.json)和
[预期输出结构](../../../skills/advisor-due-diligence/examples/expected-output.md)。
