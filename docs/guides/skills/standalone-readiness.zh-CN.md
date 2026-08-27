# 产品化 Skill 独立建库准备度

[English](standalone-readiness.md)

本文定义三个孵化中的 Product Skill 达到“足以未来独立建库”需要满足什么条件。它们当前仍随 Offer Harvester 主仓发布，但每个 Skill 包已经具备可检查的本地契约文件，后续拆仓时不需要重新猜边界。

## 当前状态

| Skill | 候选包名 | 状态 |
| --- | --- | --- |
| `contact-email-coach` | `offer-harvester-skill-contact-email-coach` | 可拆仓准备完成，但仍在主仓孵化 |
| `advisor-due-diligence` | `offer-harvester-skill-advisor-due-diligence` | 可拆仓准备完成，但仍在主仓孵化 |
| `recommendation-letter-helper` | `offer-harvester-skill-recommendation-letter-helper` | 可拆仓准备完成，但仍在主仓孵化 |

“可拆仓准备完成”不等于“已经独立运行”。当前运行时仍依赖 Offer Harvester 控制面来处理 workspace 访问、证据审计、隐私路由和 candidate 写入。

## 必需包结构

每个 Product Skill 必须包含：

- `SKILL.md`：简洁的 agent-facing 指令。
- `agents/openai.yaml`：UI 与宿主元数据。
- `references/contract.md`：人类可读的行为契约。
- `skill.manifest.json`：包名、入口、依赖、禁止能力和拆仓状态。
- `schemas/input.schema.json`：外部输入契约。
- `schemas/output.schema.json`：候选输出契约。
- `fixtures/*.json`：至少三套完全虚构用例，覆盖 `candidate`、`needs_review` 和 `blocked`。
- `examples/minimal-input.json` 与 `examples/expected-output.md`：公开最小示例。

Skill 目录内不应包含 `README.md`、API key、真实用户资料、workspace 生成记录、训练 checkpoint 或直接复制的第三方项目代码。

## 宿主边界

standalone-ready 的 Product Skill 可以定义 adapter，但当前主仓仍是以下内容的真相源：

- profile 字段确认状态；
- 导师来源与证据新鲜度；
- RAG 和 memory promotion；
- 材料审查与 EvidenceAudit；
- `AgentRun` 和 `WorkflowEvent` 记录；
- candidate 持久化。

Skill 可以请求一次 candidate execution，但不能发送邮件、提交申请、覆盖 confirmed profile 字段、修改 tracker 状态或提升 memory。

## 拆仓检查清单

真正创建独立仓库前：

1. 只复制 `skill.manifest.json` 中列出的包内文件。
2. 用窄接口 host adapter 替代 Offer Harvester 内部 import。
3. 在没有真实 workspace 的情况下保持 fixture tests 通过。
4. 增加针对 Offer Harvester API 和 DSH 的宿主兼容测试。
5. 在新仓库补齐中英文 README、安装指南、license、release notes 和截图。
6. 首个独立版本保持 pre-1.0，直到输入/输出 schema 至少连续两个版本没有破坏性变化。

## 校验

运行：

```bash
make PYTHON=./.venv/bin/python skills-check
./.venv/bin/python tools/plan_product_skill_export.py --all
```

检查器会验证包结构、manifest/catalog 对齐、fixture 覆盖、synthetic-data 标记、no-send 边界和基础私有内容防护。
导出规划器会打印未来拆仓时应复制的、受 manifest 约束的准确文件清单。
