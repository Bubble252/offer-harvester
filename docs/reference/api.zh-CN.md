# HTTP API 参考

[English](api.md)

## 真相源

运行中的 FastAPI 应用是 API 的唯一真相源：

- 交互式参考：`/docs`
- OpenAPI JSON：`/openapi.json`
- 源码装配：`app/backend/main.py`

Markdown 只解释工作流和隐私边界，不替代生成的 OpenAPI schema。修改 API 后运行
`python tools/check_openapi_contract.py`。

## 请求约定

- JSON 请求和响应使用 `main.py`、`models.py` 中声明的 Pydantic 模型。
- ID 是不透明字符串，例如 `profile_*`、`target_*`、`material_*` 和 `run_*`。
- MVP 的部分请求模型允许空列表和空字符串；不要仅凭结果存在就认为任务完成，应检查
  response 中的证据和风险发现。
- 产生 candidate 的接口不代表最终保存或外部操作。
- 除非路由声明了更具体的模型，错误响应采用 FastAPI 标准 HTTP 错误格式。

## 接口分组

| Tag | 主要路径 | 用途 |
| --- | --- | --- |
| Application | `/api/health`、`/api/llm/status`、`/` | 服务状态和浏览器入口 |
| Profile | `/api/profile`、`/api/profile/upload`、`/api/user-documents` | 原始文件、画像字段和确认 |
| Advisors and targets | `/api/advisors`、`/api/advisor-sources`、`/api/targets` | 公开来源、导师身份和目标 |
| Materials | `/api/targets/*/materials/*`、`/api/generated`、`/api/tasks` | 候选材料和 PPTX 任务 |
| Evidence and RAG | `/api/knowledge-base`、`/api/rag`、`/api/readiness-score` | 来源、检索、证据包和准备度 |
| Memory and feedback | `/api/memory`、`/api/agent-runs`、`/api/procedural-candidates` | 分层记忆和 trace |
| Workflow operations | `/api/templates`、`/api/source-connectors`、`/api/pdf`、`/api/ocr`、`/api/email-signals`、`/api/email-connectors` | 本地工作流和只读邮箱候选项 |
| Skills | `/api/skills`、`/api/skill-executions` | Skill 目录和候选执行 |
| Integrations | `/api/plugin/*`、`/api/pipeline-sync/status` | 受控外部适配器 |

## 稳定示例

### 健康检查

```bash
curl http://127.0.0.1:8000/api/health
```

### 查看 Skill

```bash
curl http://127.0.0.1:8000/api/skills
```

每个目录项都暴露状态、版本、`no_send`、写权限、来源策略和私有数据策略。

### 搜索 RAG

```bash
curl --get http://127.0.0.1:8000/api/rag/search \
  --data-urlencode 'q=推免申请截止日期' \
  --data-urlencode 'top_k=5'
```

检索结果包含来源元数据和证据引用，但不会自动成为 confirmed fact。

### 执行产品化 Skill

```bash
curl -X POST http://127.0.0.1:8000/api/skills/contact-email-coach/run \
  -H 'Content-Type: application/json' \
  -d '{"target_id":"target_demo","mode":"new"}'
```

结果是带证据、风险和 trace 的 candidate，不会发送邮件、写入最终材料或更新 tracker。

### 查看 DSH 插件状态

```bash
curl http://127.0.0.1:8000/api/plugin/status
```

服务配置为 `token` 模式时，远程插件请求需要单独的 scoped token。详见
[DSH 指南](../guides/deepseek-harness.zh-CN.md)。

### 查看只读邮件连接器状态

```bash
curl http://127.0.0.1:8000/api/email-connectors/gmail/status
```

Gmail 和 QQ 同步只创建可审查的信号候选项。凭据留在系统 keyring，只有候选项 approve
流程才可能更新 tracker。详见[只读邮件连接器](../guides/email-connectors.zh-CN.md)。

### 浏览器证据候选项

```bash
curl -X POST http://127.0.0.1:8000/api/plugin/browser/evidence-candidates \
  -H 'Content-Type: application/json' \
  -d '{"source_url":"https://example.edu/page","page_title":"Example","selected_text":"用户选中的公开网页文本。"}'
```

这个集成接口只保存未验证的证据候选项。网页文本仍要经过正常来源审查，不能直接变成导师事实。

## 兼容性策略

项目仍处于 `0.y.z` 阶段。优先增加字段和接口，但 `1.0.0` 之前仍可能有破坏性变化。
API 变更应同时完成：

1. 更新 Pydantic 模型。
2. 更新 OpenAPI 契约测试。
3. 更新中英文公开文档。
4. 在 CHANGELOG 写明隐私和回滚边界。
