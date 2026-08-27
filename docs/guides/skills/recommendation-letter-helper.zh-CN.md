# 推荐信助手

[English](recommendation-letter-helper.md) | [Skills 指南](../skills.zh-CN.md)

**状态：** 主仓孵化中的 Product Skill。可在 **Skill Lab** 或可选 DSH adapter 中运行。
它需要 Offer Harvester 控制面，不是可单独安装的工具。

## 适用场景

- 准备简洁的推荐信请求
- 为推荐人整理事实型素材包
- 生成明确标为 `reference-only`、供推荐人改写的候选草稿

## 运行前准备

填写推荐人姓名和关系，可选选择一个申请目标。控制面会解析 profile 证据并保留字段确认状态。

## 在 Skill Lab 中运行

1. 打开 **Skill Lab**，选择 **推荐信助手**。
2. 可选选择一个申请目标。
3. 填写推荐人姓名和关系。
4. 生成候选素材包。
5. 在复制或下载结果前复核证据状态和风险发现。

## 输出与边界

输出可能包含请求邮件、事实素材包和 `reference-only` 草稿。推荐人必须自行改写、确认和提交
推荐信。该 Skill 不能冒充推荐人、发送请求、提交推荐信、确认 profile 字段或修改 tracker。

## 可选 DSH 入口

DSH adapter 提供 `offer_harvester_recommendation_letter_helper`，需要 `skill:run` scope。
它通过同一受控 API 只返回 candidate。详见
[DSH 指南](../deepseek-harness.zh-CN.md)。

## 完全虚构示例

可阅读
[最小合成输入](../../../skills/recommendation-letter-helper/examples/minimal-input.json)和
[预期输出结构](../../../skills/recommendation-letter-helper/examples/expected-output.md)。
