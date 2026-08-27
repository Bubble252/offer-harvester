# DeepSeek Harness 集成指南

[English](deepseek-harness.md)

DeepSeek Harness（DSH）是可选的外部 Agent 宿主。Offer Harvester 仍是控制面：它拥有 workspace、证据规则、用户确认、RAG 与记忆治理和审计轨迹。

## 已提供的 P0 工具

| DSH 工具 | Offer Harvester endpoint | 所需 scope |
| --- | --- | --- |
| `offer_harvester_draft_contact_email` | `/api/plugin/skills/contact-email-coach/run` | `skill:run` |
| `offer_harvester_advisor_due_diligence` | `/api/plugin/skills/advisor-due-diligence/run` | `advisor:report` |
| `offer_harvester_recommendation_letter_helper` | `/api/plugin/skills/recommendation-letter-helper/run` | `skill:run` |
| `offer_harvester_audit_material` | `/api/plugin/materials/audit` | `material:audit` |

实现位于 [`integrations/deepseek_harness/`](../../integrations/deepseek_harness/)。

## 配置步骤

1. 启动 Offer Harvester。
2. 将集成目录的 `cordis.yml.example` 复制到 DSH Cordis 组合配置。
3. 配置 `apiBaseUrl`、enabled tools、privacy mode 与超时。
4. 先在 local loopback 模式测试。
5. 需要远端访问前，把 Offer Harvester 服务端改为 token 模式，并使用独立 plugin token。

```bash
OFFER_HARVESTER_PLUGIN_AUTH_MODE=token
OFFER_HARVESTER_PLUGIN_TOKEN=<long-random-value>
OFFER_HARVESTER_PLUGIN_SCOPES=skill:run,material:audit,advisor:report,policy:read
OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE=false
```

这个 token 是 Offer Harvester 集成凭据，不是 LLM provider key。不能放进 Git、公开 DSH 配置或 prompt 文本。

可以从 JSON Schema 渲染配置的宿主可使用
[`settings.schema.json`](../../integrations/deepseek_harness/settings.schema.json)。
其中 token 是 password/write-only 字段，workspace label 仅用于展示；插件不能选择本地文件路径。

## 隐私与写入

`metadata_only` 是默认 DSH privacy mode，任何远程服务都应保持这一默认。`private` 需要服务端显式设置 `OFFER_HARVESTER_PLUGIN_ALLOW_REMOTE_PRIVATE=true` 才可能启用。

插件不能选择本地文件 workspace。运行中的 Offer Harvester 进程负责选择 workspace；DSH 只通过 HTTP 接收 candidate 输出。每次成功调用都会创建 candidate execution/audit trace，且任何工具都不能发送或提交。

## 当前限制

- 此集成是主仓内孵化的本地 adapter，还不是独立发布的 DSH package。
- 暂未提供 DSH 原生 settings 页面或持久化 secret store。
- 暂未实现政策 deadline、远程 profile 写入、OAuth 或直接社区爬取。
- 当前提供离线 HTTP 合约测试；挂载 TypeScript plugin 仍需要已安装的 DSH runtime。
