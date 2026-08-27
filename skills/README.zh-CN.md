# Offer Harvester Skills

[English](README.md)

本目录刻意区分两类 Skill：

- **Portable Skill**：宿主无关的小型协议和校验器，只基于提供的输入工作，不能直接访问 Offer Harvester workspace。
- **产品化 Skill**：带任务化 Skill Lab UI 的受控适配器。它们调用 FastAPI 控制面，只返回可审阅候选，不产生最终外部动作。

机器可读的统一入口是 [`catalog.json`](catalog.json)。其中记录 Skill 分类、版本、数据边界、写权限、来源策略和状态真源。

## P0 目录

| Skill | 类型 | 输出 | 边界 |
| --- | --- | --- | --- |
| `evidence-claim-audit` | Portable | supported / unsupported / stale / needs-confirmation 审计结论 | 不写入事实 |
| `source-connector-authoring` | Portable | 公开来源 connector manifest 候选 | 不绕过 robots/ToS |
| `profile-field-normalization` | Portable | 规范化 profile 字段候选 | 不自动确认字段 |
| [`contact-email-coach`](../docs/guides/skills/contact-email-coach.zh-CN.md) | 产品化、孵化中 | 审核后的套磁邮件候选 | 仅通过 Skill Lab；不发送邮件 |
| [`advisor-due-diligence`](../docs/guides/skills/advisor-due-diligence.zh-CN.md) | 产品化、孵化中 | 有证据的导师尽调报告 | 仅通过 Skill Lab；口碑内容仅是风险信号 |
| [`recommendation-letter-helper`](../docs/guides/skills/recommendation-letter-helper.zh-CN.md) | 产品化、孵化中 | 推荐信请求与素材包候选 | 仅通过 Skill Lab；不冒充、不提交 |

## 与主应用的关系

```text
Skill 协议
-> SkillRegistry / SkillExecution adapter
-> FastAPI 控制面
-> 既有 Agent + EvidenceAudit 工作流
-> candidate 结果、AgentRun、WorkflowEvent
-> 用户在 Skill Lab 中复核
```

只有控制面可以访问 workspace，并继续执行证据和确认状态规则。当前 catalog 中的所有 Skill 均为 `no_send`。

## 校验

运行 Portable Skill fixture：

```bash
python skills/evidence-claim-audit/scripts/validate_claim_audit.py \
  --input skills/evidence-claim-audit/scripts/claim_fixture.json
python skills/source-connector-authoring/scripts/validate_manifest.py \
  --input skills/source-connector-authoring/scripts/manifest_fixture.json
python skills/profile-field-normalization/scripts/validate_fields.py \
  --input skills/profile-field-normalization/scripts/fields_fixture.json
```

从仓库根目录运行产品 adapter 测试：

```bash
./.venv/bin/pytest -q tests/test_skills_dsh.py
```

## 后续宿主

当前原生宿主是 Offer Harvester 的 Skill Lab。DeepSeek Harness 适配器位于 [`integrations/deepseek_harness/`](../integrations/deepseek_harness/)。Codex/Claude 薄指针、跨宿主安装器和独立仓库会在接口稳定后再做。
